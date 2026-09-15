from app.analytics import calculate_academic_analytics
from app.calculation import CourseResult


def course(course_id: int, code: str, score: str | None, credits: float, term: str):
    return CourseResult(
        id=course_id,
        code=code,
        name=code,
        credits=credits,
        term_code=term,
        score_text=score,
        score_scale="percentage",
    )


def test_analytics_builds_timeline_and_target_projection():
    rows = [
        course(1, "B090011021", "100", 5, "2024-2025-1"),
        course(2, "B090011010", None, 5, "2024-2025-2"),
        course(3, "OUTSIDE", "80", 2, "2024-2025-1"),
    ]

    result = calculate_academic_analytics(rows, target_gpa=3.8)

    assert result["overall"]["rule"]["gpa"] == 4
    assert result["overall"]["all"]["courseCount"] == 2
    assert result["timeline"][0]["term"] == "2024-2025-1"
    assert result["target"]["status"] == "reachable"
    assert result["target"]["pendingCredits"] == 5
    assert result["target"]["requiredAverageGradePoint"] == 3.6
    assert 85 < result["target"]["requiredAverageScore"] < 86
    assert result["opportunities"][0]["name"] == "B090011010"


def test_analytics_reports_unreachable_target():
    rows = [
        course(1, "B090011021", "60", 5, "2024-2025-1"),
        course(2, "B090011010", None, 1, "2024-2025-2"),
    ]

    result = calculate_academic_analytics(rows, target_gpa=4)

    assert result["target"]["status"] == "unreachable"
    assert result["target"]["requiredAverageScore"] is None


def test_regret_module_uses_exact_credit_weighted_counterfactual():
    rows = [
        course(1, "B090011021", "100", 5, "2024-2025-1"),
        course(2, "B090011010", "60", 5, "2024-2025-1"),
    ]

    result = calculate_academic_analytics(rows)
    regret = result["regretCourses"][0]

    assert result["summary"]["weightedGpa"] == 2.5
    assert regret["courseId"] == 2
    assert regret["gpaWithoutCourse"] == 4
    assert regret["gpaLiftIfExcluded"] == 1.5
    assert "课程绩点 × 课程学分" in result["calculationBasis"]
