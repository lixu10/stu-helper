import pytest

from app.calculation import CourseResult, calculate_dashboard, score_to_grade_point


def course(
    code: str,
    score: str | None,
    credits: float,
    *,
    scale: str = "percentage",
    selected: bool = False,
    course_id: int = 1,
):
    return CourseResult(
        id=course_id,
        code=code,
        name=code,
        credits=credits,
        term_code="2026-2027-1",
        score_text=score,
        score_scale=scale,
        selected_for_rule=selected,
    )


def test_percentage_formula_boundaries():
    assert score_to_grade_point(100, "percentage") == 4
    assert score_to_grade_point(60, "percentage") == 1
    assert score_to_grade_point(59.9, "percentage") == 0
    assert round(score_to_grade_point(80, "percentage"), 4) == 3.25
    with pytest.raises(ValueError, match="百分制成绩不是有效数字"):
        score_to_grade_point("优秀", "percentage")


def test_five_level_and_pass_fail():
    assert score_to_grade_point("优秀", "five_level") == 4
    assert score_to_grade_point("良好", "five_level") == 3.5
    assert score_to_grade_point("中等", "five_level") == 2.8
    assert score_to_grade_point("及格", "five_level") == 1.7
    assert score_to_grade_point("不及格", "five_level") == 0
    assert score_to_grade_point("通过", "pass_fail") is None


def test_direction_courses_require_explicit_choice_when_over_six_credits():
    rows = [
        course("B090011021", "90", 5),
        course("B210032101", "90", 2, course_id=2),
        course("B210032102", "80", 2, course_id=3),
        course("B210032103", "70", 2, course_id=4),
        course("B210032104", "60", 2, course_id=5),
    ]
    result = calculate_dashboard(rows)
    selection = result["directionSelection"]
    assert selection["required"] is True
    assert selection["range"]["min"] < selection["range"]["max"]


def test_selected_direction_courses_join_weighted_gpa():
    rows = [
        course("B090011021", "100", 5),
        course("B210032101", "60", 2, selected=True, course_id=2),
        course("B210032102", "60", 2, selected=True, course_id=3),
        course("B210032103", "60", 2, selected=True, course_id=4),
    ]
    result = calculate_dashboard(rows)
    assert result["directionSelection"]["required"] is False
    assert result["metrics"]["includedCredits"] == 11
    assert result["metrics"]["gpa"] == round((4 * 5 + 1 * 6) / 11, 4)


def test_scenario_overrides_a_pending_course_without_mutating_input():
    rows = [course("B090011021", None, 5)]
    result = calculate_dashboard(rows, {"B090011021": 100})
    assert result["metrics"]["gpa"] == 4
    assert rows[0].score_text is None


def test_future_range_uses_zero_and_four_point_bounds_for_pending_required_courses():
    rows = [
        course("B090011021", "100", 5),
        course("B090011010", None, 5, course_id=2),
    ]
    result = calculate_dashboard(rows)
    assert result["futureRange"] == {
        "min": 2.0,
        "max": 4.0,
        "remainingCredits": 5.0,
        "assumption": "规则内待修百分制课程分别全部按 0 分与 100 分计算；不包含未确认的方向课组合。",
    }


def test_malformed_external_grade_is_reported_without_breaking_dashboard():
    rows = [
        course("B090011021", "100", 5),
        CourseResult(
            id=2,
            code="BUAA-MILITARY",
            name="军事技能",
            credits=2,
            term_code="2024-2025-1",
            score_text="90",
            score_scale="five_level",
            source="school",
        ),
    ]
    result = calculate_dashboard(rows)
    assert result["metrics"]["gpa"] == 4
    assert result["courses"][1]["gradePoint"] is None
    assert result["courses"][1]["scoreIssue"] == "未知的五级制成绩：90"
    assert result["dataIssues"][0]["courseName"] == "军事技能"


def test_malformed_rule_grade_is_excluded_instead_of_counted_or_crashing():
    rows = [course("B090011021", "90", 5, scale="five_level")]
    result = calculate_dashboard(rows)
    assert result["metrics"]["gpa"] is None
    assert result["metrics"]["includedCredits"] == 0
    assert len(result["dataIssues"]) == 1
