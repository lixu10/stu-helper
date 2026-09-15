from __future__ import annotations

from dataclasses import asdict, dataclass


DEFAULT_RULE_ID = "buaa-se-2024-postgrad-gpa"


@dataclass(frozen=True)
class RuleCourse:
    code: str
    name: str
    credits: float
    group: str
    mode: str = "gpa"


GROUPS = {
    "A": {"name": "数理基础课", "requirement": "6 门", "kind": "courses", "minimum": 6},
    "B": {"name": "工程基础课", "requirement": "4 门", "kind": "courses", "minimum": 4},
    "C": {"name": "外语课", "requirement": "6 学分", "kind": "credits", "minimum": 6},
    "D": {"name": "思政课", "requirement": "6 门", "kind": "courses", "minimum": 6},
    "E": {"name": "核心专业类", "requirement": "14 门", "kind": "courses", "minimum": 14},
    "F": {"name": "一般专业类", "requirement": "方向课 6 学分 + 4 门通过课", "kind": "mixed", "minimum": 6},
}


COURSES = [
    RuleCourse("B090011021", "工科数学分析（1）", 5, "A"),
    RuleCourse("B090011010", "工科高等代数", 6, "A"),
    RuleCourse("B090011022", "工科数学分析（2）", 5, "A"),
    RuleCourse("B190011004", "基础物理学A（1）", 4, "A"),
    RuleCourse("B090011018", "概率统计A", 3, "A"),
    RuleCourse("B190011007", "基础物理实验（1）", 1, "A"),
    RuleCourse("B370012005", "程序设计基础", 2, "B"),
    RuleCourse("B020012001", "电子设计基础训练", 2, "B"),
    RuleCourse("B060012004", "离散数学（信息类）", 2, "B"),
    RuleCourse("B060012005", "数据结构与程序设计（信息类）", 3, "B"),
    RuleCourse("B120013011", "英语阅读（1）", 1, "C"),
    RuleCourse("B120013012", "英语写作（1）", 0.5, "C"),
    RuleCourse("B120013013", "英语口语（1）", 0.5, "C"),
    RuleCourse("B120013014", "英语阅读（2）", 1, "C"),
    RuleCourse("B120013015", "英语写作（2）", 0.5, "C"),
    RuleCourse("T120013006", "英语口语（2）", 0.5, "C"),
    RuleCourse("B120013007", "英语阅读（3）", 1, "C"),
    RuleCourse("B120013008", "英语写作（3）", 1, "C"),
    RuleCourse("B280021001", "思想道德与法治", 3, "D"),
    RuleCourse("B280021002", "习近平新时代中国特色社会主义思想概论", 3, "D"),
    RuleCourse("B280021003", "中国近现代史纲要", 3, "D"),
    RuleCourse("B280021004", "毛泽东思想和中国特色社会主义理论体系概论", 3, "D"),
    RuleCourse("B280021005", "社会实践", 2, "D"),
    RuleCourse("B280021006", "马克思主义基本原理", 3, "D"),
    RuleCourse("B210031003", "离散数学（2）", 2, "E"),
    RuleCourse("B210031002", "计算机硬件基础（软件专业）", 4, "E"),
    RuleCourse("B210031004", "算法分析与设计", 3, "E"),
    RuleCourse("B210031001", "面向对象程序设计（Java）", 2.5, "E"),
    RuleCourse("B210031005", "数据管理技术", 3, "E"),
    RuleCourse("B210031006", "软件工程基础", 3, "E"),
    RuleCourse("B060031006", "操作系统", 4.5, "E"),
    RuleCourse("B210031007", "人工智能", 2, "E"),
    RuleCourse("T210031001", "计算机网络与应用", 3, "E"),
    RuleCourse("B060031011", "编译技术", 4.5, "E"),
    RuleCourse("B210031008", "软件系统分析与设计", 3, "E"),
    RuleCourse("T210031002", "软件过程与质量", 3, "E"),
    RuleCourse("B210031009", "程序设计实践", 2, "E"),
    RuleCourse("B210031010", "软件工程基础实践", 2, "E"),
    RuleCourse("B210032101", "分布式系统导论", 2, "F", "direction"),
    RuleCourse("B210032102", "并行程序设计", 2, "F", "direction"),
    RuleCourse("B210032103", "云计算技术基础", 2, "F", "direction"),
    RuleCourse("B210032104", "嵌入式软件设计", 2, "F", "direction"),
    RuleCourse("B210032105", "数值计算与算法", 2, "F", "direction"),
    RuleCourse("B210032106", "计算机辅助设计与制造", 2, "F", "direction"),
    RuleCourse("B210032107", "工业互联网技术基础", 2, "F", "direction"),
    RuleCourse("B210032108", "工业大数据技术", 2, "F", "direction"),
    RuleCourse("B210032109", "物联网技术基础", 2, "F", "direction"),
    RuleCourse("B210032110", "智能计算系统", 2, "F", "direction"),
    RuleCourse("B210032111", "图像处理和计算机视觉", 2, "F", "direction"),
    RuleCourse("B210032112", "智能软件工程", 2, "F", "direction"),
    RuleCourse("B210032113", "开源软件开发导论", 2, "F", "direction"),
    RuleCourse("B210032002", "英文科技写作（软件工程）", 2, "F", "pass_only"),
    RuleCourse("B210032001", "跨文化交流", 1, "F", "pass_only"),
    RuleCourse("B210032003", "软件工程伦理与职业规范", 1, "F", "pass_only"),
    RuleCourse("B210032005", "学科前沿讲座", 0.5, "F", "pass_only"),
]

COURSE_BY_CODE = {course.code: course for course in COURSES}


def public_rule(rule_id: str = DEFAULT_RULE_ID) -> dict:
    if rule_id != DEFAULT_RULE_ID:
        raise KeyError(rule_id)
    return {
        "id": DEFAULT_RULE_ID,
        "name": "软件学院推荐优秀应届本科毕业生免试攻读研究生的平均学分绩点成绩规则说明-2024级（发布版）",
        "version": "2025-09-17",
        "status": "official_document",
        "applies_to": "软件学院软件工程专业 2024 级",
        "cutoff": "2027 春季学期及之前",
        "formula": "课程绩点 = 4 - 3 × (100 - X)² / 1600（60 ≤ X ≤ 100）",
        "five_level": {"优秀": 4.0, "良好": 3.5, "中等": 2.8, "及格": 1.7, "不及格": 0.0},
        "pass_fail": "通过/不通过课程不累计学分绩点",
        "direction_selection": {
            "minimum_credits": 6,
            "policy": "manual_confirmation",
            "note": "原文未说明修超 6 学分后的选课顺序，系统不自动宣称某一组合为官方结果。",
        },
        "groups": [{"code": code, **details} for code, details in GROUPS.items()],
        "courses": [asdict(course) for course in COURSES],
    }


def list_public_rules() -> list[dict]:
    rule = public_rule()
    return [
        {
            "id": rule["id"],
            "label": "软件学院 2024 级 · 发布版",
            "name": rule["name"],
            "version": rule["version"],
            "status": rule["status"],
            "appliesTo": rule["applies_to"],
            "cutoff": rule["cutoff"],
        }
    ]
