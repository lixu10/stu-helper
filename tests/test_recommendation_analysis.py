from app.recommendation_analysis import (
    REFERENCE_ROWS,
    analyze_recommendation,
)


def test_reference_distribution_matches_the_two_page_notice():
    result = analyze_recommendation(3.80, 0.10)

    assert len(REFERENCE_ROWS) == 32
    assert result["source"]["rankingPopulation"] == 159
    assert result["source"]["lastPublishedRank"] == 34
    assert result["source"]["missingPublishedRanks"] == [30, 32]
    assert result["reference"]["comprehensive"] == {
        "min": 3.78,
        "q1": 3.8425,
        "median": 3.885,
        "q3": 3.9625,
        "max": 4.07,
        "mean": 3.8994,
    }
    assert result["reference"]["academicGpa"]["median"] == 3.795
    assert result["reference"]["addition"]["median"] == 0.1
    assert result["reference"]["gpaComprehensiveCorrelation"] == 0.776


def test_analysis_uses_historical_bands_without_claiming_probability():
    edge = analyze_recommendation(3.70, 0.08)
    high = analyze_recommendation(3.92, 0.10)

    assert edge["current"]["comprehensiveScore"] == 3.78
    assert edge["current"]["band"]["id"] == "edge"
    assert edge["current"]["position"]["sampleRankLabel"] == "31–32"
    assert high["current"]["band"]["id"] == "high"
    assert "无法据此计算真实录取概率" in high["methodology"]["limitation"]


def test_targets_and_scenarios_show_multiple_improvement_paths():
    result = analyze_recommendation(
        3.75,
        0.05,
        included_credits=88,
        remaining_credits=15.5,
    )
    median = next(item for item in result["targets"] if item["id"] == "median")

    assert median["gap"] == 0.085
    assert median["academicGpaNeeded"] == 3.835
    assert median["additionNeeded"] == 0.135
    assert median["balancedAcademicGpa"] == 3.7925
    assert median["balancedAddition"] == 0.0925
    assert len(result["scenarios"]) == 5
    assert result["completeness"]["ratio"] == 0.8502
