from app.comprehensive import calculate_comprehensive, evaluate_item, public_comprehensive_rule


def item(item_id: int, category: str, name: str, score: float, factor: float = 1):
    return {
        "id": item_id,
        "category_id": category,
        "item_type": "审核认定",
        "name": name,
        "academic_year": "2025-2026",
        "base_score": score,
        "factor": factor,
        "note": "",
    }


def test_comprehensive_applies_category_weight_and_cap():
    result = calculate_comprehensive(
        3.5,
        [
            item(1, "technology", "成果甲", 0.2),
            item(2, "technology", "成果乙", 0.2),
            item(3, "culture", "活动甲", 0.1),
        ],
    )

    technology = result["categories"][0]
    assert technology["submittedScore"] == 0.4
    assert technology["cappedScore"] == 0.2784
    assert technology["weightedScore"] == 0.1392
    assert technology["limited"] is True
    assert result["weightedAddition"] == 0.1492
    assert result["finalScore"] == 3.6492


def test_comprehensive_deduplicates_same_achievement_by_highest_score():
    result = calculate_comprehensive(
        3.0,
        [
            item(1, "service", "志愿服务", 0.08),
            item(2, "service", "志愿服务", 0.1),
        ],
    )

    assert result["items"][0]["included"] is False
    assert "同类成果仅取最高项" in result["items"][0]["reason"]
    assert result["categories"][2]["submittedScore"] == 0.18
    assert result["categories"][2]["ruleAdjustedScore"] == 0.1
    assert result["weightedAddition"] == 0.02


def test_comprehensive_can_return_addition_without_base_gpa():
    result = calculate_comprehensive(None, [item(1, "discipline", "竞赛", 0.1)])

    assert result["weightedAddition"] == 0.02
    assert result["finalScore"] is None


def test_reference_rule_exposes_automatic_award_forms():
    rule = public_comprehensive_rule()

    assert len(rule["items"]) == 17
    fengru = next(item for item in rule["items"] if item["id"] == "fengru")
    assert [field["key"] for field in fengru["fields"]] == [
        "track",
        "award",
        "author",
        "academicYear",
        "achievement",
    ]


def test_fengru_and_technology_awards_are_scored_automatically():
    fengru = evaluate_item(
        "fengru",
        {
            "track": "main",
            "award": "1",
            "author": "1",
            "academicYear": "1",
            "achievement": "智能软件项目",
        },
    )
    special = evaluate_item(
        "technology-competition",
        {
            "competition": "software-cup",
            "awardRank": "1",
            "author": "1",
            "specialTrack": "special",
            "academicYear": "2",
            "achievement": "软件杯项目",
        },
    )

    assert fengru["baseScore"] == 0.1392
    assert fengru["rawScore"] == 0.1392
    assert special["baseScore"] == 0.1392
    assert special["factor"] == 0.5
    assert special["rawScore"] == 0.0696


def test_automatic_items_apply_yearly_cap_and_top_n_constraints():
    discipline_items = [
        {
            "kind": "discipline",
            "values": {
                "competition": competition,
                "level": "national",
                "award": "special",
                "academicYear": "1",
            },
        }
        for competition in ("math", "modeling")
    ]
    service_items = [
        {
            "kind": "service-position",
            "values": {
                "position": position,
                "positionName": f"岗位 {position}",
                "rating": "outstanding",
                "semester": "1",
            },
        }
        for position in ("a", "b", "c")
    ]

    result = calculate_comprehensive(3.5, discipline_items + service_items)

    discipline = result["categories"][1]
    assert discipline["submittedScore"] == 0.348
    assert discipline["ruleAdjustedScore"] == 0.174
    excluded_positions = [
        item for item in result["items"] if item["kind"] == "service-position" and not item["included"]
    ]
    assert len(excluded_positions) == 1
    assert "至多计入 2 项" in excluded_positions[0]["reason"]
