from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import isclose
from typing import Iterable

from app.rules import COURSE_BY_CODE, DEFAULT_RULE_ID, GROUPS, public_rule


FIVE_LEVEL_POINTS = {"优秀": 4.0, "良好": 3.5, "中等": 2.8, "及格": 1.7, "不及格": 0.0}
PASSING_TEXT = {"通过", "合格", "优秀", "良好", "中等", "及格"}


@dataclass(frozen=True)
class CourseResult:
    id: int
    code: str
    name: str
    credits: float
    term_code: str
    score_text: str | None
    score_scale: str
    selected_for_rule: bool = False
    source: str = "school"

    @property
    def rule(self):
        return COURSE_BY_CODE.get(self.code)


def score_to_grade_point(score: str | float | int | None, scale: str) -> float | None:
    if score is None or str(score).strip() == "":
        return None
    if scale == "pass_fail":
        return None
    if scale == "five_level":
        value = FIVE_LEVEL_POINTS.get(str(score).strip())
        if value is None:
            raise ValueError(f"未知的五级制成绩：{score}")
        return value
    if scale != "percentage":
        raise ValueError(f"未知成绩制：{scale}")
    try:
        value = float(score)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"百分制成绩不是有效数字：{score}") from exc
    if value < 0 or value > 100:
        raise ValueError("百分制成绩必须在 0 到 100 之间")
    if value < 60:
        return 0.0
    return 4.0 - 3.0 * (100.0 - value) ** 2 / 1600.0


def _passed(course: CourseResult) -> bool:
    if course.score_text is None:
        return False
    if course.score_scale == "pass_fail":
        return course.score_text.strip() in PASSING_TEXT
    point, _ = _grade_point_or_error(course)
    return point is not None and point > 0


def _grade_point_or_error(course: CourseResult) -> tuple[float | None, str | None]:
    try:
        return score_to_grade_point(course.score_text, course.score_scale), None
    except (TypeError, ValueError) as exc:
        return None, str(exc)


def _has_valid_gpa_score(course: CourseResult) -> bool:
    point, error = _grade_point_or_error(course)
    return course.score_text is not None and error is None and point is not None


def _weighted_gpa(courses: Iterable[CourseResult]) -> float | None:
    rows = []
    for course in courses:
        point, _ = _grade_point_or_error(course)
        if point is not None:
            rows.append((point, course.credits))
    credits = sum(credit for _, credit in rows)
    if not credits:
        return None
    return sum(point * credit for point, credit in rows) / credits


def _direction_combinations(courses: list[CourseResult], minimum: float = 6.0):
    valid = []
    for count in range(1, len(courses) + 1):
        for combo in combinations(courses, count):
            credits = sum(course.credits for course in combo)
            if credits + 1e-9 >= minimum:
                valid.append((credits, combo))
    if not valid:
        return []
    minimum_covered = min(credits for credits, _ in valid)
    return [combo for credits, combo in valid if isclose(credits, minimum_covered)]


def _course_payload(course: CourseResult) -> dict:
    rule = course.rule
    point, score_issue = _grade_point_or_error(course)
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "credits": course.credits,
        "termCode": course.term_code,
        "score": course.score_text,
        "scoreScale": course.score_scale,
        "gradePoint": round(point, 4) if point is not None else None,
        "group": rule.group if rule else "其他",
        "ruleMode": rule.mode if rule else "outside",
        "selectedForRule": course.selected_for_rule,
        "source": course.source,
        "status": "completed" if course.score_text is not None else "planned",
        "scoreIssue": score_issue,
    }


def calculate_dashboard(
    courses: list[CourseResult],
    overrides: dict[str, float] | None = None,
    rule_id: str = DEFAULT_RULE_ID,
) -> dict:
    rule_definition = public_rule(rule_id)
    overrides = overrides or {}
    effective = []
    for course in courses:
        if course.code in overrides:
            effective.append(
                CourseResult(
                    **{
                        **course.__dict__,
                        "score_text": str(overrides[course.code]),
                        "score_scale": "percentage",
                    }
                )
            )
        else:
            effective.append(course)

    fixed_completed = [
        course
        for course in effective
        if course.rule
        and course.rule.mode == "gpa"
        and _has_valid_gpa_score(course)
    ]
    direction_completed = [
        course
        for course in effective
        if course.rule
        and course.rule.mode == "direction"
        and _has_valid_gpa_score(course)
    ]
    explicitly_selected = [course for course in direction_completed if course.selected_for_rule]
    selected_credits = sum(course.credits for course in explicitly_selected)
    direction_options = _direction_combinations(direction_completed)

    selection_required = bool(direction_options) and selected_credits < 6
    official_direction = explicitly_selected if selected_credits >= 6 else []
    official_courses = fixed_completed + official_direction
    official_gpa = _weighted_gpa(official_courses)

    pending_gpa_courses = [
        course
        for course in effective
        if course.rule and course.rule.mode == "gpa" and course.score_text is None
    ]
    completed_gpa_credits = sum(course.credits for course in official_courses)
    completed_gpa_points = sum(
        (_grade_point_or_error(course)[0] or 0) * course.credits
        for course in official_courses
    )
    pending_gpa_credits = sum(course.credits for course in pending_gpa_courses)
    future_credits = completed_gpa_credits + pending_gpa_credits
    future_min = completed_gpa_points / future_credits if future_credits else None
    future_max = (
        (completed_gpa_points + 4 * pending_gpa_credits) / future_credits
        if future_credits
        else None
    )

    option_gpas = [_weighted_gpa(fixed_completed + list(option)) for option in direction_options]
    option_gpas = [value for value in option_gpas if value is not None]

    percentage_rows = [
        course
        for course in official_courses
        if course.score_scale == "percentage" and course.score_text is not None
    ]
    weighted_score = None
    arithmetic_score = None
    if percentage_rows:
        total_credits = sum(course.credits for course in percentage_rows)
        weighted_score = (
            sum(float(course.score_text) * course.credits for course in percentage_rows)
            / total_credits
        )
        arithmetic_score = sum(float(course.score_text) for course in percentage_rows) / len(
            percentage_rows
        )

    group_progress = []
    for code, details in GROUPS.items():
        group_courses = [course for course in effective if course.rule and course.rule.group == code]
        if code == "F":
            direction = [course for course in group_courses if course.rule.mode == "direction"]
            pass_only = [course for course in group_courses if course.rule.mode == "pass_only"]
            done_direction = sum(course.credits for course in direction if _passed(course))
            done_pass_only = sum(1 for course in pass_only if _passed(course))
            complete = done_direction >= 6 and done_pass_only >= 4
            progress = min(done_direction / 6, 1) * 0.6 + min(done_pass_only / 4, 1) * 0.4
            current = f"{done_direction:g}/6 学分 · {done_pass_only}/4 门通过"
        elif details["kind"] == "credits":
            done = sum(course.credits for course in group_courses if _passed(course))
            complete = done + 1e-9 >= float(details["minimum"])
            progress = min(done / float(details["minimum"]), 1)
            current = f"{done:g}/{details['minimum']:g} 学分"
        else:
            done = sum(1 for course in group_courses if _passed(course))
            complete = done >= int(details["minimum"])
            progress = min(done / int(details["minimum"]), 1)
            current = f"{done}/{details['minimum']} 门"
        group_progress.append(
            {
                "code": code,
                "name": details["name"],
                "requirement": details["requirement"],
                "current": current,
                "progress": round(progress, 4),
                "complete": complete,
            }
        )

    course_payloads = [_course_payload(course) for course in effective]
    pending = [
        _course_payload(course)
        for course in effective
        if course.rule and course.score_text is None
    ]
    included_credits = sum(course.credits for course in official_courses)
    completed_count = sum(1 for course in effective if course.score_text is not None)
    projected = bool(overrides)
    return {
        "metrics": {
            "gpa": round(official_gpa, 4) if official_gpa is not None else None,
            "weightedAverage": round(weighted_score, 2) if weighted_score is not None else None,
            "arithmeticAverage": round(arithmetic_score, 2) if arithmetic_score is not None else None,
            "includedCredits": round(included_credits, 2),
            "completedCourses": completed_count,
            "projected": projected,
        },
        "directionSelection": {
            "required": selection_required,
            "selectedCredits": selected_credits,
            "candidateCredits": sum(course.credits for course in direction_completed),
            "range": {
                "min": round(min(option_gpas), 4) if option_gpas else None,
                "max": round(max(option_gpas), 4) if option_gpas else None,
            },
            "message": (
                "方向课超过 6 学分，规则原文未规定自动取舍，请确认计入课程。"
                if selection_required
                else "方向课选择已明确。"
            ),
        },
        "futureRange": {
            "min": round(future_min, 4) if future_min is not None else None,
            "max": round(future_max, 4) if future_max is not None else None,
            "remainingCredits": round(pending_gpa_credits, 2),
            "assumption": "规则内待修百分制课程分别全部按 0 分与 100 分计算；不包含未确认的方向课组合。",
        },
        "groups": group_progress,
        "courses": course_payloads,
        "pending": pending,
        "dataIssues": [
            {
                "courseId": course["id"],
                "courseCode": course["code"],
                "courseName": course["name"],
                "message": course["scoreIssue"],
            }
            for course in course_payloads
            if course["scoreIssue"]
        ],
        "rule": {
            "id": rule_definition["id"],
            "name": rule_definition["name"],
            "version": rule_definition["version"],
            "cutoff": "2027 春季",
        },
    }
