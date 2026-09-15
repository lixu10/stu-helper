from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Iterable

from app.calculation import CourseResult, score_to_grade_point


def _valid_rows(courses: Iterable[CourseResult]) -> list[tuple[CourseResult, float]]:
    rows: list[tuple[CourseResult, float]] = []
    for course in courses:
        try:
            point = score_to_grade_point(course.score_text, course.score_scale)
        except (TypeError, ValueError):
            continue
        if point is not None and course.score_text is not None:
            rows.append((course, point))
    return rows


def _official_rule_courses(courses: list[CourseResult]) -> list[CourseResult]:
    fixed = [course for course in courses if course.rule and course.rule.mode == "gpa"]
    direction = [
        course
        for course in courses
        if course.rule and course.rule.mode == "direction" and course.selected_for_rule
    ]
    if sum(course.credits for course in direction if course.score_text is not None) < 6:
        direction = []
    return fixed + direction


def _aggregate(courses: Iterable[CourseResult]) -> dict:
    rows = _valid_rows(courses)
    credits = sum(course.credits for course, _ in rows)
    gpa = sum(course.credits * point for course, point in rows) / credits if credits else None
    percentage = [
        course
        for course, _ in rows
        if course.score_scale == "percentage" and course.score_text is not None
    ]
    percentage_credits = sum(course.credits for course in percentage)
    weighted = (
        sum(float(course.score_text) * course.credits for course in percentage)
        / percentage_credits
        if percentage_credits
        else None
    )
    arithmetic = (
        sum(float(course.score_text) for course in percentage) / len(percentage)
        if percentage
        else None
    )
    return {
        "gpa": round(gpa, 4) if gpa is not None else None,
        "weightedAverage": round(weighted, 2) if weighted is not None else None,
        "arithmeticAverage": round(arithmetic, 2) if arithmetic is not None else None,
        "credits": round(credits, 2),
        "courseCount": len(rows),
    }


def _score_for_grade_point(point: float) -> float | None:
    if point > 4:
        return None
    if point <= 0:
        return 0.0
    if point <= 1:
        return 60.0
    return 100.0 - sqrt((4.0 - point) * 1600.0 / 3.0)


def _target_projection(courses: list[CourseResult], target_gpa: float) -> dict:
    rule_courses = _official_rule_courses(courses)
    completed = _valid_rows(course for course in rule_courses if course.score_text is not None)
    pending = [
        course
        for course in rule_courses
        if course.rule and course.rule.mode == "gpa" and course.score_text is None
    ]
    current_credits = sum(course.credits for course, _ in completed)
    current_points = sum(course.credits * point for course, point in completed)
    pending_credits = sum(course.credits for course in pending)
    current_gpa = current_points / current_credits if current_credits else None

    if not pending_credits:
        met = current_gpa is not None and current_gpa + 1e-9 >= target_gpa
        return {
            "targetGpa": round(target_gpa, 4),
            "status": "already_met" if met else "no_pending_courses",
            "requiredAverageGradePoint": None,
            "requiredAverageScore": None,
            "pendingCredits": 0,
        }

    required_point = (
        target_gpa * (current_credits + pending_credits) - current_points
    ) / pending_credits
    if required_point <= 0:
        status = "already_met"
    elif required_point > 4:
        status = "unreachable"
    else:
        status = "reachable"
    required_score = _score_for_grade_point(required_point)
    return {
        "targetGpa": round(target_gpa, 4),
        "status": status,
        "requiredAverageGradePoint": round(max(0.0, required_point), 4),
        "requiredAverageScore": round(required_score, 2) if required_score is not None else None,
        "pendingCredits": round(pending_credits, 2),
    }


def calculate_academic_analytics(
    courses: list[CourseResult], target_gpa: float = 3.8
) -> dict:
    rule_courses = _official_rule_courses(courses)
    by_term: dict[str, list[CourseResult]] = defaultdict(list)
    for course in courses:
        if course.term_code != "待同步" and course.score_text is not None:
            by_term[course.term_code].append(course)

    timeline = []
    cumulative_rule_courses: list[CourseResult] = []
    for term in sorted(by_term):
        term_courses = by_term[term]
        term_rule_ids = {course.id for course in rule_courses if course.term_code == term}
        cumulative_rule_courses.extend(
            course for course in term_courses if course.id in term_rule_ids
        )
        timeline.append(
            {
                "term": term,
                "all": _aggregate(term_courses),
                "rule": _aggregate(course for course in term_courses if course.id in term_rule_ids),
                "cumulativeRule": _aggregate(cumulative_rule_courses),
            }
        )

    by_year: dict[str, list[CourseResult]] = defaultdict(list)
    for course in courses:
        if course.term_code != "待同步" and course.score_text is not None:
            year = course.term_code.rsplit("-", 1)[0]
            by_year[year].append(course)
    yearly = []
    rule_ids = {course.id for course in rule_courses}
    for year in sorted(by_year):
        year_courses = by_year[year]
        yearly.append(
            {
                "year": year,
                "all": _aggregate(year_courses),
                "rule": _aggregate(course for course in year_courses if course.id in rule_ids),
            }
        )

    completed_rule_rows = _valid_rows(
        course for course in rule_courses if course.score_text is not None
    )
    total_credits = sum(course.credits for course, _ in completed_rule_rows)
    current_gpa = (
        sum(course.credits * point for course, point in completed_rule_rows) / total_credits
        if total_credits
        else None
    )
    contributions = []
    regret_courses = []
    if current_gpa is not None:
        total_points = sum(course.credits * point for course, point in completed_rule_rows)
        for course, point in completed_rule_rows:
            contributions.append(
                {
                    "courseId": course.id,
                    "name": course.name,
                    "term": course.term_code,
                    "credits": course.credits,
                    "gradePoint": round(point, 4),
                    "gpaContribution": round(
                        course.credits * (point - current_gpa) / total_credits, 4
                    ),
                }
            )
            remaining_credits = total_credits - course.credits
            if remaining_credits > 0:
                without_course = (total_points - course.credits * point) / remaining_credits
                lift = without_course - current_gpa
                if lift > 1e-10:
                    regret_courses.append(
                        {
                            "courseId": course.id,
                            "code": course.code,
                            "name": course.name,
                            "term": course.term_code,
                            "credits": course.credits,
                            "score": course.score_text,
                            "gradePoint": round(point, 4),
                            "currentGpa": round(current_gpa, 4),
                            "gpaWithoutCourse": round(without_course, 4),
                            "gpaLiftIfExcluded": round(lift, 4),
                            "weightedGradePoints": round(course.credits * point, 4),
                            "creditShare": round(course.credits / total_credits, 4),
                        }
                    )
    contributions.sort(key=lambda item: abs(item["gpaContribution"]), reverse=True)
    regret_courses.sort(key=lambda item: item["gpaLiftIfExcluded"], reverse=True)

    group_performance = []
    for group in "ABCDEF":
        group_courses = [
            course
            for course in rule_courses
            if course.rule and course.rule.group == group and course.score_text is not None
        ]
        aggregate = _aggregate(group_courses)
        if aggregate["courseCount"]:
            group_performance.append({"group": group, **aggregate})

    point_bands = [
        ("3.7–4.0", 3.7, 4.01),
        ("3.0–3.7", 3.0, 3.7),
        ("2.0–3.0", 2.0, 3.0),
        ("1.0–2.0", 1.0, 2.0),
        ("0–1.0", 0.0, 1.0),
    ]
    distribution = []
    for label, lower, upper in point_bands:
        rows = [
            (course, point)
            for course, point in completed_rule_rows
            if lower <= point < upper
        ]
        credits = sum(course.credits for course, _ in rows)
        distribution.append(
            {
                "label": label,
                "courseCount": len(rows),
                "credits": round(credits, 2),
                "creditShare": round(credits / total_credits, 4) if total_credits else 0,
            }
        )

    volatility = None
    if current_gpa is not None and total_credits:
        volatility = sqrt(
            sum(course.credits * (point - current_gpa) ** 2 for course, point in completed_rule_rows)
            / total_credits
        )

    pending = [
        course
        for course in rule_courses
        if course.rule and course.rule.mode == "gpa" and course.score_text is None
    ]
    future_credits = total_credits + sum(course.credits for course in pending)
    opportunities = [
        {
            "courseId": course.id,
            "name": course.name,
            "credits": course.credits,
            "gpaSwing60To100": round(3 * course.credits / future_credits, 4)
            if future_credits
            else 0,
        }
        for course in pending
    ]
    opportunities.sort(key=lambda item: item["gpaSwing60To100"], reverse=True)

    return {
        "overall": {"all": _aggregate(courses), "rule": _aggregate(rule_courses)},
        "timeline": timeline,
        "academicYears": yearly,
        "target": _target_projection(courses, target_gpa),
        "contributions": contributions[:8],
        "regretCourses": regret_courses[:10],
        "opportunities": opportunities[:8],
        "groupPerformance": group_performance,
        "gradePointDistribution": distribution,
        "summary": {
            "weightedGradePoints": round(
                sum(course.credits * point for course, point in completed_rule_rows), 4
            ),
            "includedCredits": round(total_credits, 2),
            "weightedGpa": round(current_gpa, 4) if current_gpa is not None else None,
            "gradePointVolatility": round(volatility, 4) if volatility is not None else None,
        },
        "calculationBasis": "GPA = Σ(课程绩点 × 课程学分) / Σ课程学分。后悔药按移除单门课程后的加权 GPA 反事实差值排序。",
        "assumptions": {
            "all": "全部课程中可换算绩点的已有成绩。",
            "rule": "当前规则内课程；方向课仅在人工确认满 6 学分后计入。",
            "target": "假设剩余规则内百分制课程取得相同成绩，不包含尚未确认的方向课。",
        },
    }
