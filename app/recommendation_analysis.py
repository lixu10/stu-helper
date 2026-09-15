from __future__ import annotations

from math import sqrt
from statistics import fmean
from typing import Iterable


REFERENCE_SOURCE = {
    "fileName": "北京航空航天大学软件学院软件工程专业2023级本科生拟推免名单（普通推免生）.pdf",
    "publishedAt": "2026-09-08",
    "cohort": "软件工程专业 2023 级",
    "recommendationYear": 2027,
    "rankingPopulation": 159,
    "listedCount": 32,
    "lastPublishedRank": 34,
    "missingPublishedRanks": [30, 32],
}

# Only numeric columns needed for aggregate analysis are retained. Names and student IDs
# from the public notice are deliberately excluded from application data.
REFERENCE_ROWS = [
    (1, 4.07, 3.86),
    (2, 4.06, 3.88),
    (3, 4.06, 3.86),
    (4, 4.01, 3.92),
    (5, 3.99, 3.86),
    (6, 3.98, 3.84),
    (7, 3.98, 3.90),
    (8, 3.97, 3.82),
    (9, 3.96, 3.89),
    (10, 3.95, 3.82),
    (11, 3.94, 3.74),
    (12, 3.92, 3.88),
    (13, 3.90, 3.84),
    (14, 3.90, 3.75),
    (15, 3.90, 3.80),
    (16, 3.89, 3.76),
    (17, 3.88, 3.82),
    (18, 3.87, 3.79),
    (19, 3.87, 3.84),
    (20, 3.86, 3.76),
    (21, 3.86, 3.73),
    (22, 3.86, 3.84),
    (23, 3.85, 3.74),
    (24, 3.85, 3.72),
    (25, 3.82, 3.72),
    (26, 3.81, 3.79),
    (27, 3.81, 3.75),
    (28, 3.81, 3.77),
    (29, 3.80, 3.65),
    (31, 3.79, 3.72),
    (33, 3.78, 3.74),
    (34, 3.78, 3.67),
]


def _quantile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summary(values: list[float]) -> dict:
    return {
        "min": round(min(values), 4),
        "q1": round(_quantile(values, 0.25), 4),
        "median": round(_quantile(values, 0.5), 4),
        "q3": round(_quantile(values, 0.75), 4),
        "max": round(max(values), 4),
        "mean": round(fmean(values), 4),
    }


def _correlation(left: list[float], right: list[float]) -> float:
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else 0.0


COMPREHENSIVE_SCORES = [row[1] for row in REFERENCE_ROWS]
ACADEMIC_GPAS = [row[2] for row in REFERENCE_ROWS]
ADDITIONS = [round(row[1] - row[2], 4) for row in REFERENCE_ROWS]
COMPREHENSIVE_SUMMARY = _summary(COMPREHENSIVE_SCORES)
GPA_SUMMARY = _summary(ACADEMIC_GPAS)
ADDITION_SUMMARY = _summary(ADDITIONS)


def _position(value: float, reference: list[float]) -> dict:
    ahead = sum(item > value + 1e-9 for item in reference)
    equal = sum(abs(item - value) <= 1e-9 for item in reference)
    percentile = 100 * sum(item <= value + 1e-9 for item in reference) / len(reference)
    if value < min(reference) - 1e-9:
        rank_label = f"> {len(reference)}"
    elif equal > 1:
        rank_label = f"{ahead + 1}–{ahead + equal}"
    else:
        rank_label = str(ahead + 1)
    return {
        "percentile": round(percentile, 1),
        "sampleRank": ahead + 1 if value >= min(reference) - 1e-9 else None,
        "sampleRankLabel": rank_label,
        "sampleSize": len(reference),
    }


def _band(score: float) -> dict:
    if score >= COMPREHENSIVE_SUMMARY["q3"]:
        return {"id": "high", "label": "历史高位区", "tone": "strong", "message": "达到去年拟推免名单上四分位。"}
    if score >= COMPREHENSIVE_SUMMARY["median"]:
        return {"id": "upper", "label": "历史中上区", "tone": "strong", "message": "达到去年拟推免名单中位数。"}
    if score >= COMPREHENSIVE_SUMMARY["q1"]:
        return {"id": "middle", "label": "历史中位区", "tone": "steady", "message": "位于去年名单中间一半。"}
    if score >= COMPREHENSIVE_SUMMARY["min"]:
        return {"id": "edge", "label": "历史边缘区", "tone": "warning", "message": "进入去年名单分数范围，但接近下沿。"}
    if score >= COMPREHENSIVE_SUMMARY["min"] - 0.03:
        return {"id": "near", "label": "接近历史下沿", "tone": "warning", "message": "距离去年名单最低综合成绩不超过 0.03。"}
    return {"id": "lower", "label": "低于历史下沿", "tone": "danger", "message": "当前情景低于去年拟推免名单最低综合成绩。"}


def _scenario(label: str, academic_gpa: float, addition: float) -> dict:
    gpa = min(4.0, max(0.0, academic_gpa))
    bonus = max(0.0, addition)
    score = gpa + bonus
    return {
        "label": label,
        "academicGpa": round(gpa, 4),
        "addition": round(bonus, 4),
        "comprehensiveScore": round(score, 4),
        "position": _position(score, COMPREHENSIVE_SCORES),
        "band": _band(score),
    }


def analyze_recommendation(
    academic_gpa: float,
    comprehensive_addition: float,
    *,
    included_credits: float = 0,
    remaining_credits: float = 0,
) -> dict:
    if not 0 <= academic_gpa <= 4:
        raise ValueError("GPA 情景必须在 0 到 4 之间")
    if not 0 <= comprehensive_addition <= 0.5:
        raise ValueError("综测加分情景必须在 0 到 0.5 之间")

    current = _scenario("当前情景", academic_gpa, comprehensive_addition)
    current["academicPosition"] = _position(academic_gpa, ACADEMIC_GPAS)
    current["additionPosition"] = _position(comprehensive_addition, ADDITIONS)
    current["gapToHistoricalFloor"] = round(
        max(0.0, COMPREHENSIVE_SUMMARY["min"] - current["comprehensiveScore"]), 4
    )
    current["gapToMedian"] = round(
        max(0.0, COMPREHENSIVE_SUMMARY["median"] - current["comprehensiveScore"]), 4
    )

    total_credits = included_credits + remaining_credits
    completion_ratio = included_credits / total_credits if total_credits else 0
    if remaining_credits <= 0:
        completeness = "成绩基本完整"
    elif completion_ratio >= 0.85:
        completeness = "接近完整"
    elif completion_ratio >= 0.65:
        completeness = "仍有变动空间"
    else:
        completeness = "当前仍属早期估计"

    targets = []
    for target_id, label, score in (
        ("floor", "去年名单下沿", COMPREHENSIVE_SUMMARY["min"]),
        ("q1", "去年名单下四分位", COMPREHENSIVE_SUMMARY["q1"]),
        ("median", "去年名单中位", COMPREHENSIVE_SUMMARY["median"]),
        ("q3", "去年名单上四分位", COMPREHENSIVE_SUMMARY["q3"]),
    ):
        gap = max(0.0, score - current["comprehensiveScore"])
        targets.append(
            {
                "id": target_id,
                "label": label,
                "score": round(score, 4),
                "gap": round(gap, 4),
                "academicGpaNeeded": round(max(0.0, score - comprehensive_addition), 4),
                "additionNeeded": round(max(0.0, score - academic_gpa), 4),
                "balancedAcademicGpa": round(min(4.0, academic_gpa + gap / 2), 4),
                "balancedAddition": round(comprehensive_addition + gap / 2, 4),
            }
        )

    scenarios = [
        current,
        _scenario("仅提升 GPA", academic_gpa + 0.03, comprehensive_addition),
        _scenario("仅提升综测", academic_gpa, comprehensive_addition + 0.03),
        _scenario("均衡提升", academic_gpa + 0.02, comprehensive_addition + 0.02),
        _scenario("进取情景", academic_gpa + 0.05, comprehensive_addition + 0.05),
    ]

    return {
        "source": {
            **REFERENCE_SOURCE,
            "nominalListedRate": round(
                REFERENCE_SOURCE["listedCount"] / REFERENCE_SOURCE["rankingPopulation"], 4
            ),
            "privacy": "仅保留综合排名、综合成绩和 GPA 数值；不在系统数据中保存姓名、学号。",
        },
        "reference": {
            "comprehensive": COMPREHENSIVE_SUMMARY,
            "academicGpa": GPA_SUMMARY,
            "addition": ADDITION_SUMMARY,
            "gpaComprehensiveCorrelation": round(
                _correlation(ACADEMIC_GPAS, COMPREHENSIVE_SCORES), 3
            ),
        },
        "current": current,
        "completeness": {
            "includedCredits": round(included_credits, 2),
            "remainingCredits": round(remaining_credits, 2),
            "ratio": round(completion_ratio, 4),
            "label": completeness,
        },
        "targets": targets,
        "scenarios": scenarios,
        "methodology": {
            "primaryIndicator": "综合成绩相对去年拟推免名单分布的位置",
            "supportingIndicators": ["GPA 在名单中的分位", "综测加分在名单中的分位", "剩余课程占比"],
            "limitation": "名单只有拟推免者，没有未入围者及本届名额变化，无法据此计算真实录取概率；分层仅表示与去年入围样本的相对位置。",
        },
    }
