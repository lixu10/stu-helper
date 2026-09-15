from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.course_matching import normalize_course_name


COMPREHENSIVE_RULE_ID = "soft-where-2023-reference"


def option(value: str, label: str, **metadata: Any) -> dict:
    return {"value": value, "label": label, **metadata}


ACADEMIC_YEARS = [option(str(year), f"第 {year} 学年") for year in range(1, 4)]
SEMESTERS = [option(str(term), f"第 {term} 学期") for term in range(1, 7)]
AUTHORS = [option(str(rank), f"第{label}作者") for rank, label in zip(range(1, 4), "一二三")]
AWARD_RANKS = [
    option("1", "第一档（一等奖；设特等奖时选特等奖）"),
    option("2", "第二档"),
    option("3", "第三档"),
]

FENGRU_TRACKS = [
    option("main", "主赛道制作组 / 论文组"),
    option("philosophy", "主赛道哲社组"),
    option("red", "红旅赛道"),
    option("discipline-agent", "“学科智能体”专项竞赛"),
    option("industry-special", "产业赛道 / 其他主赛道专项竞赛"),
    option("innovation-cup", "主赛道创新杯专项竞赛（不额外加分）"),
    option("creative", "学生创意赛道"),
    option("valid", "有效项目但未获奖"),
]
FENGRU_AWARDS = {
    "main": [option("1", "一等奖"), option("2", "二等奖"), option("3", "三等奖")],
    "philosophy": [option("1", "一等奖"), option("2", "二等奖"), option("3", "三等奖")],
    "red": [option("1", "金奖"), option("2", "银奖"), option("3", "铜奖")],
    "discipline-agent": [option("1", "金奖"), option("2", "银奖"), option("3", "铜奖")],
    "industry-special": [option("1", "一等奖"), option("2", "二等奖"), option("3", "三等奖")],
    "innovation-cup": [option("not-counted", "不单独计分")],
    "creative": [option("0", "特等奖"), option("1", "一等奖"), option("2", "二等奖"), option("3", "三等奖")],
    "valid": [option("valid", "未获奖")],
}
FENGRU_SCORES = {
    "main": [[0.1392, 0.0522, 0.0174], [0.1044, 0.0261, 0.0087], [0.0696, 0.0131, 0.0043]],
    "red": [[0.1044, 0.0261, 0.0087], [0.0696, 0.0131, 0.0043], [0.0464, 0.0087, 0.0029]],
    "industry": [[0.0696, 0.0174, 0.0058], [0.0522, 0.0087, 0.0029], [0.0348, 0.0043, 0.0017]],
    "creative": [0.0464, 0.0348, 0.0232, 0.0174],
}

TECH_COMPETITIONS = [
    option("innovation-national", "中国国际大学生创新大赛（国家级）", scoreClass="A"),
    option("challenge-academic-national", "“挑战杯”全国大学生课外学术科技作品竞赛", scoreClass="A"),
    option("challenge-business-national", "“挑战杯”中国大学生创业计划大赛", scoreClass="A"),
    option("asc-champion", "ASC 世界大学生超级计算机竞赛（国际级，冠亚季军）", scoreClass="B"),
    option("huawei-ict-international", "华为 ICT 大赛（国际级）", scoreClass="B"),
    option("robot-contest-international", "全国大学生机器人大赛（国际级）", scoreClass="B"),
    option("china-us-maker-final", "中美青年创客大赛（总决赛）", scoreClass="B"),
    option("career-planning-national", "全国大学生职业规划大赛（国家级）", scoreClass="B"),
    option("software-innovation", "全国大学生软件创新大赛（国家级）", scoreClass="B"),
    option("innovation-beijing", "中国国际大学生创新大赛（北京赛区）", scoreClass="B"),
    option("capital-challenge-academic", "“青创北京”“挑战杯”首都大学生课外学术科技作品竞赛", scoreClass="B"),
    option("capital-challenge-business", "“青创北京”“挑战杯”首都大学生创业计划竞赛", scoreClass="B"),
    option("asc-award", "ASC 世界大学生超级计算机竞赛（国际级，一二三等奖）", scoreClass="C"),
    option("software-cup", "中国软件杯（国家级）", scoreClass="C"),
    option("information-security", "全国大学生信息安全竞赛（国家级）", scoreClass="C"),
    option("college-computer", "中国高校计算机大赛（国家级）", scoreClass="C"),
    option("computer-design", "全国大学生计算机设计大赛（国家级）", scoreClass="C"),
    option("openatom", "开放原子大赛（国家级）", scoreClass="C"),
    option("huawei-ict-national", "华为 ICT 大赛（国家级）", scoreClass="C"),
    option("embedded-chip", "全国大学生嵌入式芯片与系统设计竞赛", scoreClass="C"),
    option("robot-ai", "中国机器人及人工智能大赛（国家级）", scoreClass="C"),
    option("robot-contest-national", "全国大学生机器人大赛（国家级）", scoreClass="C"),
    option("ican", "iCAN 大学生创新创业大赛（国家级）", scoreClass="C"),
    option("china-us-maker-regional", "中美青年创客大赛（分赛区）", scoreClass="C"),
    option("new-domain", "新域新质创新大赛（国家级）", scoreClass="C"),
    option("jingcai", "“京彩大创”北京大学生创新创业大赛", scoreClass="C"),
    option("career-planning-provincial", "全国大学生职业规划大赛（省部级）", scoreClass="C"),
]
TECH_COMPETITION_SCORES = {
    "A": [[0.2784, 0.1044, 0.0348], [0.2088, 0.0522, 0.0174], [0.1392, 0.0261, 0.0087]],
    "B": [[0.2088, 0.0783, 0.0261], [0.1392, 0.0348, 0.0116], [0.1044, 0.0196, 0.0065]],
    "C": [[0.1392, 0.0522, 0.0174], [0.1044, 0.0261, 0.0087], [0.0696, 0.0131, 0.0043]],
}

DISCIPLINE_COMPETITIONS = [
    option("math", "全国大学生数学竞赛（非数学类）"), option("modeling", "全国大学生数学建模竞赛"),
    option("mcm", "国际大学生数学建模竞赛（美赛）"), option("statistics-modeling", "全国大学生统计建模大赛"),
    option("physics", "全国部分地区大学生物理竞赛（非物理类 A 组）"), option("zhou-peiyuan", "全国周培源大学生力学竞赛"),
    option("buaa-physics", "北航物理竞赛"), option("english", "全国大学生英语竞赛"),
    option("fltrp", "“外研社·国才杯”全国大学生英语挑战赛"), option("21st-century", "“21 世纪杯”全国英语演讲比赛"),
    option("sflep-cross-cultural", "“外教社杯”全国高校学生跨文化能力大赛"), option("sflep-words", "“外教社·词达人杯”全国大学生英语词汇能力大赛"),
    option("systems", "全国大学生计算机系统能力大赛"), option("matiji", "“码蹄杯”全国大学生程序设计大赛"),
    option("baidu-star", "百度之星程序设计大赛"),
]
NORMAL_AWARDS = [option("special", "特等奖"), option("first", "一等奖"), option("second", "二等奖"), option("third", "三等奖")]
MCM_AWARDS = [option("outstanding", "Outstanding Winner"), option("finalist", "Finalist"), option("meritorious", "Meritorious Winner")]
DISCIPLINE_SCORES = {
    "national": {"special": 0.174, "first": 0.1392, "second": 0.0696, "third": 0.0348},
    "provincial": {"special": 0.1392, "first": 0.0696, "second": 0.0348, "third": 0.0174},
    "school": {"special": 0.0696, "first": 0.0348, "second": 0.0174, "third": 0.0087},
}
MCM_SCORES = {"outstanding": 0.1392, "finalist": 0.0696, "meritorious": 0.0348}

POSITIONS = [
    option("a", "A 类：执行主席团 / 分团委副书记 / 学院宣媒中心部长", score=0.0348),
    option("b", "B 类：各部部长 / 五星社团社长 / 大班长 / 党支部书记等", score=0.0261),
    option("c", "C 类：副部长 / 四星社团社长 / 班委 / 党支部支委等", score=0.0174),
    option("d", "D 类：三星社团社长 / 部门干事 / 小班班委等", score=0.0087),
]
RATINGS = [option("outstanding", "表现突出", factor=2), option("excellent", "优秀", factor=1.5), option("good", "良好", factor=1), option("pass", "基本合格", factor=0.5), option("fail", "不称职", factor=0)]
HONORS = [
    option("excellent-party-member", "优秀共产党员", city=0.0928, school=0.0464), option("excellent-party-worker", "优秀党务工作者", city=0.0928, school=0.0464),
    option("annual-person", "大学生年度人物", city=0.0928, school=0.0464), option("shen-yuan", "沈元奖章", city=None, school=0.0464),
    option("buaa-role-model", "北航榜样", city=None, school=0.0464), option("may-fourth", "五四奖章", city=0.0928, school=0.0464),
    option("three-good", "三好学生", city=0.0261, school=0.0087), option("student-leader", "优秀学生干部", city=0.0464, school=0.0116),
    option("league-leader", "优秀团干部", city=0.0464, school=0.0116), option("league-member", "优秀团员", city=0.0348, school=0.0087),
    option("volunteer", "十佳志愿者", city=0.0464, school=0.0232),
]

CATEGORIES = (
    {"id": "technology", "name": "科技创新与学术研究", "shortName": "科技创新", "weight": 0.5, "cap": 0.2784},
    {"id": "discipline", "name": "学科竞赛", "shortName": "学科竞赛", "weight": 0.2, "cap": 0.3132},
    {"id": "service", "name": "社会工作与思想道德", "shortName": "社会工作", "weight": 0.2, "cap": 0.3132},
    {"id": "culture", "name": "文体活动", "shortName": "文体活动", "weight": 0.1, "cap": 0.2784},
)
CATEGORY_BY_ID = {category["id"]: category for category in CATEGORIES}


def select(key: str, label: str, options: list[dict] | None = None, **extra: Any) -> dict:
    return {"key": key, "label": label, "type": "select", "options": options or [], **extra}


def text(key: str, label: str, placeholder: str = "", required: bool = False) -> dict:
    return {"key": key, "label": label, "type": "text", "placeholder": placeholder, "required": required}


def number(key: str, label: str, default: float | None = None, **extra: Any) -> dict:
    return {"key": key, "label": label, "type": "number", "default": default, **extra}


ITEM_DEFINITIONS = [
    {"id": "fengru", "categoryId": "technology", "label": "冯如杯", "fields": [
        select("track", "赛道", FENGRU_TRACKS), select("award", "奖项", optionsBy={"field": "track", "values": FENGRU_AWARDS}),
        select("author", "作者顺序", AUTHORS, visibleWhen={"field": "track", "notIn": ["creative", "valid", "innovation-cup"]}),
        select("academicYear", "获奖学年", ACADEMIC_YEARS), text("achievement", "成果名称", "同一成果使用相同名称", True),
    ]},
    {"id": "technology-competition", "categoryId": "technology", "label": "专业相关科技竞赛", "fields": [
        select("competition", "竞赛", TECH_COMPETITIONS), select("awardRank", "奖项档次", AWARD_RANKS), select("author", "作者顺序", AUTHORS),
        select("specialTrack", "成果类型", [option("regular", "常规赛道"), option("special", "经认定的专项赛道")]),
        select("academicYear", "获奖学年", ACADEMIC_YEARS), text("achievement", "成果名称", "同一成果使用相同名称", True),
    ]},
    {"id": "innovation", "categoryId": "technology", "label": "大创项目", "fields": [
        select("level", "项目级别", [option("national", "国家级大创"), option("city", "市级大创"), option("school", "校级大创")]),
        select("outcome", "结题结果", optionsBy={"field": "level", "values": {"national": [option("annual", "入围年会"), option("excellent", "优秀"), option("good", "良好")], "city": [option("excellent", "优秀"), option("good", "良好")], "school": [option("excellent", "优秀")]} }),
        select("author", "作者顺序", AUTHORS), select("academicYear", "认定学年", ACADEMIC_YEARS), text("achievement", "项目名称", "同一项目使用相同名称", True),
    ]},
    {"id": "acm", "categoryId": "technology", "label": "ACM 竞赛", "fields": [
        select("level", "赛事", [option("ccpc", "CCPC"), option("regional", "ICPC 亚洲区域赛"), option("ec-final", "EC-Final"), option("world-final", "ICPC 全球总决赛")]),
        select("medal", "奖牌", [option("gold", "金奖"), option("silver", "银奖"), option("bronze", "铜奖")]), select("academicYear", "获奖学年", ACADEMIC_YEARS),
    ]},
    {"id": "paper", "categoryId": "technology", "label": "发表学术论文", "fields": [
        select("level", "论文级别", [option("ccf-a", "CCF A 类"), option("ccf-b", "CCF B 类"), option("ccf-c", "CCF C 类"), option("sci", "SCI 检索"), option("ei-journal", "EI 检索（期刊）"), option("ei-conference", "EI 检索（会议）")]),
        select("authorship", "署名方式", [option("first", "第一学生作者（非共同一作）"), option("cofirst", "共同一作")]),
        number("coauthorCount", "共同一作人数", 2, min=1, max=20, step=1, visibleWhen={"field": "authorship", "equals": "cofirst"}), text("paperName", "论文名称", "填写完整论文名称", True),
    ]},
    {"id": "discipline", "categoryId": "discipline", "label": "学科竞赛", "fields": [
        select("competition", "竞赛", DISCIPLINE_COMPETITIONS), select("level", "竞赛级别", [option("national", "国家级"), option("provincial", "省部级"), option("school", "校级")], visibleWhen={"field": "competition", "notEquals": "mcm"}),
        select("award", "奖项", optionsBy={"field": "competition", "values": {"mcm": MCM_AWARDS}, "default": NORMAL_AWARDS}), select("academicYear", "获奖学年", ACADEMIC_YEARS),
    ]},
    {"id": "service-position", "categoryId": "service", "label": "社会工作岗位", "fields": [
        select("position", "岗位", POSITIONS), text("positionName", "具体岗位", "填写岗位名称", True), select("rating", "考评等级", RATINGS), select("semester", "任职学期", SEMESTERS),
    ]},
    {"id": "collective-honor", "categoryId": "service", "label": "先进集体称号", "fields": [
        select("level", "称号级别", [option("city", "市级（含市级以上）"), option("school", "校级")]), select("academicYear", "获奖学年", ACADEMIC_YEARS), text("collectiveName", "集体名称", "同一集体使用相同名称", True),
    ]},
    {"id": "individual-honor", "categoryId": "service", "label": "个人先进称号", "fields": [
        select("level", "称号级别", [option("city", "市级（含市级以上）"), option("school", "校级")]),
        select("honor", "荣誉称号", optionsBy={"field": "level", "values": {"city": [option(item["value"], item["label"]) for item in HONORS if item.get("city") is not None], "school": [option(item["value"], item["label"]) for item in HONORS if item.get("school") is not None]}}), select("academicYear", "获奖学年", ACADEMIC_YEARS),
    ]},
    {"id": "volunteering", "categoryId": "service", "label": "志愿服务时长", "fields": [number("hours", "认证服务时长", 50, min=0, max=10000, step=0.5, suffix="小时")]},
    {"id": "social-practice", "categoryId": "service", "label": "社会实践", "fields": [
        select("achievementType", "认定类型", [option("individual", "校级及以上社会实践先进个人 / 先进工作者", score=0.0232), option("team-school", "校级及以上优秀实践队主要材料准备者 / 答辩者", score=0.0116), option("team-college", "院级优秀实践队主要材料准备者 / 答辩者", score=0.0086)]),
        select("academicYear", "获奖学年", ACADEMIC_YEARS), text("projectName", "实践项目", "同一项目使用相同名称", True),
    ]},
    {"id": "sports", "categoryId": "culture", "label": "体育活动", "fields": [
        select("level", "赛事级别", [option("city", "市级（含市级以上）"), option("school", "校级")]),
        select("placement", "名次", [option("first", "第一名"), option("second", "第二名"), option("third", "第三名"), option("four-eight", "第四至第八名"), option("completed", "报名参与并顺利完赛")]),
        select("projectType", "项目类别", [option("standard", "校院代表队 / 田径项目", factor=1), option("mass", "群众体育 / 院级球类项目", factor=0.8)]), select("form", "参赛形式", [option("individual", "个人项目", factor=1), option("team", "集体项目", factor=0.5)]),
        select("academicYear", "获奖学年", ACADEMIC_YEARS), text("projectName", "比赛项目", "同一项目使用相同名称", True),
    ]},
    {"id": "arts", "categoryId": "culture", "label": "文艺活动", "fields": [
        select("level", "活动级别", [option("city", "市级（含市级以上）"), option("school", "校级")]), select("award", "奖项", [option("first", "一等奖"), option("second", "二等奖"), option("third", "三等奖")]),
        select("form", "节目形式", [option("individual", "个人项目", factor=1), option("team", "集体项目", factor=0.5)]), select("academicYear", "获奖学年", ACADEMIC_YEARS), text("projectName", "活动项目", "同一项目使用相同名称", True),
    ]},
]
for category_id, label in (("technology", "科技创新"), ("discipline", "学科竞赛"), ("service", "社会工作与思想道德"), ("culture", "文体活动")):
    fields = [text("name", "加分项名称", "填写审核认定的项目名称", True), number("score", "认定原始分", None, min=0, max=10, step=0.0001)]
    if category_id == "discipline":
        fields.append(select("academicYear", "认定学年", ACADEMIC_YEARS))
    ITEM_DEFINITIONS.append({"id": f"manual-{category_id}", "categoryId": category_id, "label": f"{label}（审核认定）", "manual": True, "fields": fields})

ITEM_BY_ID = {item["id"]: item for item in ITEM_DEFINITIONS}


def _find(options: list[dict], value: Any) -> dict | None:
    return next((item for item in options if item["value"] == str(value)), None)


def _visible(field: dict, values: dict) -> bool:
    condition = field.get("visibleWhen")
    if not condition:
        return True
    current = str(values.get(condition["field"], ""))
    if "equals" in condition:
        return current == condition["equals"]
    if "notEquals" in condition:
        return current != condition["notEquals"]
    if "notIn" in condition:
        return current not in condition["notIn"]
    return True


def _field_options(field: dict, values: dict) -> list[dict]:
    dynamic = field.get("optionsBy")
    if not dynamic:
        return field.get("options", [])
    selected = str(values.get(dynamic["field"], ""))
    return dynamic.get("values", {}).get(selected, dynamic.get("default", []))


def normalize_item_values(kind: str, submitted: dict[str, Any]) -> dict[str, Any]:
    definition = ITEM_BY_ID.get(kind)
    if not definition:
        raise ValueError("未知的综测项目类型")
    values = dict(submitted or {})
    normalized: dict[str, Any] = {}
    for field in definition["fields"]:
        if not _visible(field, {**values, **normalized}):
            continue
        key = field["key"]
        if field["type"] == "select":
            options = _field_options(field, {**values, **normalized})
            selected = str(values.get(key, ""))
            if not _find(options, selected):
                selected = options[0]["value"] if options else ""
            normalized[key] = selected
        elif field["type"] == "number":
            raw = values.get(key, field.get("default"))
            if raw in (None, ""):
                raise ValueError(f"请填写{field['label']}")
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field['label']}必须是数字") from exc
            if value < field.get("min", value) or value > field.get("max", value):
                raise ValueError(f"{field['label']}超出允许范围")
            normalized[key] = value
        else:
            value = str(values.get(key, "")).strip()
            if field.get("required") and not value:
                raise ValueError(f"请填写{field['label']}")
            normalized[key] = value
    return normalized


def _label(kind: str, field_key: str, values: dict) -> str:
    field = next(item for item in ITEM_BY_ID[kind]["fields"] if item["key"] == field_key)
    selected = _find(_field_options(field, values), values.get(field_key))
    return selected["label"] if selected else ""


def _token(value: Any) -> str:
    return normalize_course_name(str(value or ""))


def evaluate_item(kind: str, submitted: dict[str, Any]) -> dict:
    values = normalize_item_values(kind, submitted)
    definition = ITEM_BY_ID[kind]
    category_id = definition["categoryId"]
    base, factor = 0.0, 1.0
    detail_parts: list[str] = []
    dedupe: list[str] = []
    constraints: list[dict] = []
    warnings: list[str] = []

    if kind == "fengru":
        track = values["track"]
        author_index = max(0, int(values.get("author", 1)) - 1)
        if track == "valid":
            base = 0.0025
        elif track == "innovation-cup":
            warnings.append("创新杯专项本身不额外加分；主赛道获奖请按对应主赛道申报。")
        elif track == "creative":
            base = FENGRU_SCORES["creative"][int(values["award"])]
        else:
            table_key = {"philosophy": "main", "discipline-agent": "red", "industry-special": "industry"}.get(track, track)
            base = FENGRU_SCORES[table_key][max(0, int(values["award"]) - 1)][author_index]
            if track == "philosophy":
                factor = 0.5
        detail_parts = [_label(kind, key, values) for key in ("track", "award", "author") if key in values]
        dedupe = [f"fengru-year:{values['academicYear']}", f"technology-achievement:{_token(values['achievement'])}"]
    elif kind == "technology-competition":
        competition = _find(TECH_COMPETITIONS, values["competition"])
        award_index, author_index = int(values["awardRank"]) - 1, int(values["author"]) - 1
        base = TECH_COMPETITION_SCORES[competition["scoreClass"]][award_index][author_index]
        if values["specialTrack"] == "special":
            factor = 0.5 if author_index == 0 else 1 / 3
        detail_parts = [_label(kind, key, values) for key in ("competition", "awardRank", "author", "specialTrack")]
        dedupe = [f"technology-achievement:{_token(values['achievement'])}"]
    elif kind == "innovation":
        scores = {"national": {"annual": [0.2088, 0.0783, 0.0261], "excellent": [0.1044, 0.0261, 0.0087], "good": [0.0261, 0, 0]}, "city": {"excellent": [0.0522, 0.013, 0], "good": [0.013, 0, 0]}, "school": {"excellent": [0.0174, 0.0032, 0]}}
        base = scores[values["level"]][values["outcome"]][int(values["author"]) - 1]
        detail_parts = [_label(kind, key, values) for key in ("level", "outcome", "author")]
        dedupe = ["innovation-undergraduate", f"technology-achievement:{_token(values['achievement'])}"]
    elif kind == "acm":
        scores = {"ccpc": {"gold": 0.0773, "silver": 0.0619, "bronze": 0.0464}, "regional": {"gold": 0.116, "silver": 0.0928, "bronze": 0.0696}, "ec-final": {"gold": 0.174, "silver": 0.1392, "bronze": 0.1044}, "world-final": {"gold": 0.2784, "silver": 0.232, "bronze": 0.174}}
        base = scores[values["level"]][values["medal"]]
        detail_parts = [_label(kind, key, values) for key in ("level", "medal")]
        dedupe = ["acm-undergraduate"]
    elif kind == "paper":
        scores = {"ccf-a": 0.174, "ccf-b": 0.1392, "ccf-c": 0.1276, "sci": 0.116, "ei-journal": 0.0928, "ei-conference": 0.0464}
        base = scores[values["level"]]
        if values["authorship"] == "cofirst":
            factor = 1 / max(1, int(values["coauthorCount"]))
        detail_parts = [_label(kind, key, values) for key in ("level", "authorship")]
        dedupe = [f"paper:{_token(values['paperName'])}"] + (["paper-cofirst"] if values["authorship"] == "cofirst" else [])
    elif kind == "discipline":
        base = MCM_SCORES[values["award"]] if values["competition"] == "mcm" else DISCIPLINE_SCORES[values["level"]][values["award"]]
        detail_parts = [_label(kind, key, values) for key in ("competition", "level", "award") if key in values]
        dedupe = [f"discipline-competition:{values['competition']}"]
        constraints = [{"kind": "cap", "key": f"discipline-year:{values['academicYear']}", "cap": 0.174, "label": f"第 {values['academicYear']} 学年学科竞赛"}]
    elif kind == "service-position":
        position, rating = _find(POSITIONS, values["position"]), _find(RATINGS, values["rating"])
        base, factor = position["score"], rating["factor"]
        detail_parts = [position["label"], rating["label"], _label(kind, "semester", values)]
        dedupe = [f"service-position:{values['semester']}:{_token(values['positionName'])}"]
        constraints = [{"kind": "topN", "key": f"service-semester:{values['semester']}", "count": 2, "label": f"第 {values['semester']} 学期社会工作岗位"}, {"kind": "cap", "key": f"service-semester:{values['semester']}", "cap": 0.0696, "label": f"第 {values['semester']} 学期社会工作岗位"}]
    elif kind == "collective-honor":
        base = 0.0232 if values["level"] == "city" else 0.0116
        detail_parts = [_label(kind, "level", values), _label(kind, "academicYear", values)]
        dedupe = [f"collective:{values['academicYear']}:{_token(values['collectiveName'])}"]
    elif kind == "individual-honor":
        honor = _find(HONORS, values["honor"])
        base = honor[values["level"]]
        detail_parts = [_label(kind, "level", values), honor["label"], _label(kind, "academicYear", values)]
        dedupe = [f"individual-honor:{values['academicYear']}:{values['level']}:{values['honor']}"]
        if values["level"] == "school":
            constraints = [{"kind": "topN", "key": f"school-honor-year:{values['academicYear']}", "count": 2, "label": f"第 {values['academicYear']} 学年校级个人先进称号"}]
    elif kind == "volunteering":
        hours = max(0, values["hours"])
        if 50 <= hours < 100:
            base = 0.0116
        elif 100 <= hours <= 200:
            base = 0.0232
        elif hours > 200:
            base = min(0.0464, 0.0232 + 0.0058 * int((hours - 200) // 50))
            if hours < 250:
                warnings.append("超过 200 小时后，每满 50 小时才增加 0.0058。")
        detail_parts = [f"{hours:g} 小时"]
        dedupe = ["volunteering-total"]
    elif kind == "social-practice":
        achievement = _find(ITEM_BY_ID[kind]["fields"][0]["options"], values["achievementType"])
        base = achievement["score"]
        detail_parts = [achievement["label"], _label(kind, "academicYear", values)]
        dedupe = [f"social-practice:{values['academicYear']}:{_token(values['projectName'])}"]
    elif kind == "sports":
        scores = {"city": {"first": 0.1392, "second": 0.1044, "third": 0.0696, "four-eight": 0.0348, "completed": 0.0174}, "school": {"first": 0.0696, "second": 0.0522, "third": 0.0348, "four-eight": 0.0174, "completed": 0.0087}}
        base = scores[values["level"]][values["placement"]]
        factor = _find(ITEM_BY_ID[kind]["fields"][2]["options"], values["projectType"])["factor"] * _find(ITEM_BY_ID[kind]["fields"][3]["options"], values["form"])["factor"]
        detail_parts = [_label(kind, key, values) for key in ("level", "placement", "projectType", "form")]
        dedupe = [f"culture-project:{values['academicYear']}:{_token(values['projectName'])}"]
    elif kind == "arts":
        scores = {"city": {"first": 0.1392, "second": 0.1044, "third": 0.0696}, "school": {"first": 0.0696, "second": 0.0522, "third": 0.0348}}
        base = scores[values["level"]][values["award"]]
        factor = _find(ITEM_BY_ID[kind]["fields"][2]["options"], values["form"])["factor"]
        detail_parts = [_label(kind, key, values) for key in ("level", "award", "form")]
        dedupe = [f"culture-project:{values['academicYear']}:{_token(values['projectName'])}"]
    elif kind.startswith("manual-"):
        base = values["score"]
        detail_parts = [values["name"]]
        if kind == "manual-discipline":
            dedupe = [f"discipline-manual:{_token(values['name'])}"]
            constraints = [{"kind": "cap", "key": f"discipline-year:{values['academicYear']}", "cap": 0.174, "label": f"第 {values['academicYear']} 学年学科竞赛"}]
        warnings.append("该分值由用户按评审认定结果手动填写。")

    name = next((str(values[key]) for key in ("achievement", "paperName", "positionName", "collectiveName", "projectName", "name") if values.get(key)), definition["label"])
    academic_year = str(values.get("academicYear") or values.get("semester") or "")
    return {"kind": kind, "values": values, "categoryId": category_id, "itemType": definition["label"], "name": name, "academicYear": academic_year, "baseScore": round(base, 4), "factor": round(factor, 6), "rawScore": round(base * factor, 6), "detail": " · ".join(part for part in detail_parts if part), "dedupeKeys": [key for key in dedupe if not key.endswith(":")], "constraints": constraints, "warnings": warnings}


def prepare_comprehensive_item(kind: str, values: dict[str, Any], note: str = "") -> dict:
    evaluated = evaluate_item(kind, values)
    return {"kind": kind, "values": evaluated["values"], "category_id": evaluated["categoryId"], "item_type": evaluated["itemType"], "name": evaluated["name"], "academic_year": evaluated["academicYear"], "base_score": evaluated["baseScore"], "factor": evaluated["factor"], "note": note.strip()}


def public_comprehensive_rule() -> dict:
    categories = []
    for category in CATEGORIES:
        item_types = [{"id": item["id"], "label": item["label"], "manual": item.get("manual", False)} for item in ITEM_DEFINITIONS if item["categoryId"] == category["id"]]
        categories.append({**category, "itemTypes": item_types})
    return {"id": COMPREHENSIVE_RULE_ID, "name": "软件学院综测折合方法（参考 2023 级）", "status": "reference", "sourceUrl": "https://github.com/Soft-Where-21/soft-where-21.github.io/blob/main/tool/comprehensive.html", "formula": "最终综合成绩 = 基础 GPA + Σ(规则调整及类别封顶后的原始分 × 类别权重)", "categories": categories, "items": ITEM_DEFINITIONS, "notice": "参考页面仅提供 2021–2023 级方案；2024 级结果以学院正式文件和审核为准。"}


def _legacy_evaluation(item: dict) -> dict:
    category_id = str(item.get("category_id") or item.get("categoryId") or "")
    base = max(0.0, float(item.get("base_score", item.get("baseScore", 0)) or 0))
    factor = max(0.0, float(item.get("factor", 1) or 0))
    name = str(item.get("name") or "未命名项目").strip()
    academic_year = str(item.get("academic_year") or item.get("academicYear") or "").strip()
    return {"kind": item.get("kind") or f"manual-{category_id}", "values": item.get("values") or {}, "categoryId": category_id, "itemType": str(item.get("item_type") or item.get("itemType") or "审核认定"), "name": name, "academicYear": academic_year, "baseScore": round(base, 4), "factor": round(factor, 6), "rawScore": round(base * factor, 6), "detail": str(item.get("note") or ""), "dedupeKeys": [f"legacy:{category_id}:{academic_year}:{_token(name)}"], "constraints": [], "warnings": ["旧版手工项目，仍按原始分和系数计算。"]}


def _apply_cap(rows: list[dict], cap: float, label: str, source_key: str, target_key: str) -> float:
    remaining = cap
    for row in sorted((item for item in rows if item["included"]), key=lambda item: (-item[source_key], item["originalIndex"])):
        credited = min(row[source_key], max(0.0, remaining))
        row[target_key] = round(credited, 6)
        remaining -= credited
        if credited + 1e-10 < row[source_key]:
            row["reasons"].append(f"{label}按 {cap:.4f} 分封顶")
    return sum(row[target_key] for row in rows if row["included"])


def calculate_comprehensive(base_gpa: float | None, items: list[dict]) -> dict:
    evaluated: list[dict] = []
    for index, item in enumerate(items):
        try:
            values = item.get("values")
            result = evaluate_item(str(item.get("kind")), values) if values else _legacy_evaluation(item)
        except (KeyError, TypeError, ValueError):
            result = _legacy_evaluation(item)
            result["warnings"].append("自动计分字段无效，已回退到保存的审核分值。")
        evaluated.append({**item, **result, "originalIndex": index, "included": result["categoryId"] in CATEGORY_BY_ID, "creditedScore": result["rawScore"], "finalScore": result["rawScore"], "weightedScore": 0.0, "reasons": []})

    dedupe_groups: dict[str, list[dict]] = defaultdict(list)
    for row in evaluated:
        for key in row["dedupeKeys"]:
            dedupe_groups[key].append(row)
    for rows in dedupe_groups.values():
        included = [row for row in rows if row["included"]]
        if len(included) <= 1:
            continue
        ordered = sorted(included, key=lambda row: (-row["rawScore"], row["originalIndex"]))
        winner = ordered[0]
        for row in ordered[1:]:
            row["included"], row["creditedScore"], row["finalScore"] = False, 0.0, 0.0
            row["reasons"].append(f"同类成果仅取最高项，已计入 {winner['itemType']}")

    topn_groups: dict[tuple[str, int], tuple[dict, list[dict]]] = {}
    cap_groups: dict[tuple[str, float], tuple[dict, list[dict]]] = {}
    for row in evaluated:
        for constraint in row["constraints"]:
            if constraint["kind"] == "topN":
                key = (constraint["key"], int(constraint["count"]))
                topn_groups.setdefault(key, (constraint, []))[1].append(row)
            elif constraint["kind"] == "cap":
                key = (constraint["key"], float(constraint["cap"]))
                cap_groups.setdefault(key, (constraint, []))[1].append(row)
    for constraint, rows in topn_groups.values():
        included = sorted((row for row in rows if row["included"]), key=lambda row: (-row["rawScore"], row["originalIndex"]))
        for row in included[int(constraint["count"]):]:
            row["included"], row["creditedScore"], row["finalScore"] = False, 0.0, 0.0
            row["reasons"].append(f"{constraint['label']}至多计入 {constraint['count']} 项")
    for constraint, rows in cap_groups.values():
        _apply_cap(rows, float(constraint["cap"]), constraint["label"], "creditedScore", "creditedScore")

    ledgers = []
    weighted_addition = 0.0
    for category in CATEGORIES:
        rows = [row for row in evaluated if row["categoryId"] == category["id"]]
        submitted = sum(row["rawScore"] for row in rows)
        adjusted = sum(row["creditedScore"] for row in rows if row["included"])
        for row in rows:
            row["finalScore"] = row["creditedScore"] if row["included"] else 0.0
        capped = _apply_cap(rows, category["cap"], category["shortName"], "creditedScore", "finalScore") if adjusted > category["cap"] + 1e-10 else adjusted
        for row in rows:
            row["weightedScore"] = round(row["finalScore"] * category["weight"], 6)
            row["reason"] = "；".join(row["reasons"]) or None
        weighted = capped * category["weight"]
        weighted_addition += weighted
        ledgers.append({**category, "submittedScore": round(submitted, 4), "ruleAdjustedScore": round(adjusted, 4), "cappedScore": round(capped, 4), "weightedScore": round(weighted, 5), "limited": submitted > adjusted + 1e-10 or adjusted > capped + 1e-10})

    valid_base = None if base_gpa is None else max(0.0, min(4.0, float(base_gpa)))
    for row in evaluated:
        row.pop("originalIndex", None)
    return {"baseGpa": round(valid_base, 4) if valid_base is not None else None, "categories": ledgers, "items": evaluated, "weightedAddition": round(weighted_addition, 5), "finalScore": round(valid_base + weighted_addition, 5) if valid_base is not None else None}
