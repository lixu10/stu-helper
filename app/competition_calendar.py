from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from typing import Any


UPDATED_AT = "2026-09-15"

CATEGORY_NAMES = {
    "technology": "专业相关科技竞赛",
    "discipline": "学科竞赛",
    "acm": "ACM 竞赛",
    "campus": "北航校内科创",
}

STATUS_NAMES = {
    "official": "官方已公布",
    "window": "官方周期",
    "estimated": "预计时间",
    "pending": "等待公布",
    "not-held": "本年不举办",
}


def schedule(
    start: str | None,
    end: str | None,
    label: str,
    status: str,
    source_url: str,
    source_title: str,
    *,
    stage: str = "主要赛程",
    basis: str = "",
    note: str = "",
) -> dict[str, Any]:
    return {
        "startDate": start,
        "endDate": end or start,
        "displayDate": label,
        "status": status,
        "statusName": STATUS_NAMES[status],
        "stage": stage,
        "basis": basis,
        "note": note,
        "source": {"title": source_title, "url": source_url},
    }


def event(
    event_id: str,
    name: str,
    category_id: str,
    policy_labels: list[str],
    schedule_2026: dict[str, Any],
    estimate_2027: tuple[str | None, str | None, str],
    *,
    aliases: list[str] | None = None,
    source_2027: tuple[str, str] | None = None,
    status_2027: str = "estimated",
    basis_2027: str = "按 2025/2026 实际赛程与推免方案表列月份推算",
    note_2027: str = "2027 官方通知尚未发布，请在报名前复核来源页。",
) -> dict[str, Any]:
    start_2027, end_2027, label_2027 = estimate_2027
    source = source_2027 or (
        schedule_2026["source"]["url"],
        schedule_2026["source"]["title"],
    )
    schedule_2027 = schedule(
        start_2027,
        end_2027,
        label_2027,
        status_2027,
        source[0],
        source[1],
        stage=schedule_2026["stage"],
        basis=basis_2027,
        note=note_2027,
    )
    return {
        "id": event_id,
        "name": name,
        "aliases": aliases or [],
        "categoryId": category_id,
        "categoryName": CATEGORY_NAMES[category_id],
        "policyLabels": policy_labels,
        "schedules": {2026: schedule_2026, 2027: schedule_2027},
    }


MOE_INNOVATION = "https://www.moe.gov.cn/srcsite/A08/s5672/202607/t20260731_1445670.html"
CHALLENGE = "https://www.tiaozhanbei.net/"


EVENTS: list[dict[str, Any]] = [
    event(
        "china-innovation",
        "中国国际大学生创新大赛",
        "technology",
        ["A 类：国家级", "B 类：北京赛区"],
        schedule("2026-07-01", "2026-11-30", "7—11月；报名8月10日—9月25日", "official", MOE_INNOVATION, "教育部 2026 大赛通知", stage="报名至总决赛"),
        ("2027-07-01", "2027-11-30", "预计7—11月"),
    ),
    event(
        "challenge-academic-national",
        "“挑战杯”全国大学生课外学术科技作品竞赛",
        "technology",
        ["A 类"],
        schedule(None, None, "双年赛：2026 年非主体赛事年", "not-held", CHALLENGE, "挑战杯官方网站", note="主体赛与创业计划赛交叉轮流举办。"),
        ("2027-03-01", "2027-11-30", "预计3—11月"),
        basis_2027="按挑战杯两项主体赛隔年交替及 2025 届赛程推算",
    ),
    event(
        "challenge-business-national",
        "“挑战杯”中国大学生创业计划竞赛",
        "technology",
        ["A 类"],
        schedule("2026-03-01", "2026-11-30", "3月起校赛；国赛周期至秋季", "window", CHALLENGE, "挑战杯官方网站", stage="校赛至国赛", note="全国主体赛最终日期以组委会后续通知为准。"),
        (None, None, "双年赛：预计 2027 年不举办主体赛"),
        status_2027="not-held",
        basis_2027="按挑战杯两项主体赛隔年交替推算",
    ),
    event(
        "asc",
        "ASC 世界大学生超级计算机竞赛",
        "technology",
        ["B 类：冠亚季军", "C 类：一二三等奖"],
        schedule("2026-05-16", "2026-05-20", "总决赛5月16—20日", "official", "https://www.asc-events.net/StudentChallenge/ASC26/final-competition.php", "ASC26 官方赛程", stage="总决赛", note="报名为2025年11月6日至2026年1月12日。"),
        ("2027-05-15", "2027-05-20", "预计5月中下旬"),
    ),
    event(
        "huawei-ict",
        "华为 ICT 大赛",
        "technology",
        ["B 类：国际级", "C 类：国家级"],
        schedule("2026-06-02", "2026-06-05", "全球总决赛6月2—5日", "official", "https://www.huawei.com/minisite/ict-competition-2025-2026-global/cn/", "华为 2025—2026 全球总决赛", stage="全球总决赛", note="中国区比赛属于同一年度赛季的前置阶段。"),
        ("2027-05-25", "2027-06-06", "预计5月末—6月初"),
    ),
    event(
        "robot-contest",
        "全国大学生机器人大赛",
        "technology",
        ["B 类：国际级", "C 类：国家级"],
        schedule("2026-05-01", "2026-08-31", "各赛项集中在5—8月", "window", "https://www.roboac.cn/", "全国大学生机器人大赛赛事平台", stage="分赛项决赛", note="Robocon、RoboMaster、ROBOTAC 等赛项日期不同。"),
        ("2027-05-01", "2027-08-31", "预计5—8月"),
    ),
    event(
        "china-us-maker",
        "中美青年创客大赛",
        "technology",
        ["B 类：总决赛", "C 类：分赛区"],
        schedule("2026-04-15", "2026-07-31", "分赛区4月中旬—6月；总决赛7月28—31日", "official", "https://chinaus-maker.cscse.edu.cn/", "2026 中美青年创客大赛官网", stage="报名至总决赛"),
        ("2027-04-15", "2027-07-31", "预计4月中旬—7月底"),
    ),
    event(
        "career-planning",
        "全国大学生职业规划大赛",
        "technology",
        ["B 类：国家级", "C 类：省部级"],
        schedule("2025-10-20", "2026-04-25", "2025年10月—2026年4月；国赛4月22—25日", "official", "https://www.moe.gov.cn/srcsite/A15/s7063/202510/t20251021_1417550.html", "教育部第三届大赛通知", stage="完整赛季"),
        ("2026-10-20", "2027-04-25", "预计2026年10月—2027年4月"),
        basis_2027="按第三届 2025—2026 完整赛季平移一年推算",
    ),
    event(
        "software-innovation",
        "全国大学生软件创新大赛",
        "technology",
        ["B 类"],
        schedule("2025-12-02", "2026-05-31", "报名至2月2日；总决赛5月30—31日", "official", "https://www.pses.com.cn/", "示范性软件学院联盟赛事信息", stage="完整赛季"),
        ("2026-12-01", "2027-05-31", "预计2026年12月—2027年5月底"),
        basis_2027="按 2025—2026 第十九届完整赛程平移一年推算",
    ),
    event(
        "capital-challenge-academic",
        "“青创北京”“挑战杯”首都大学生课外学术科技作品竞赛",
        "technology",
        ["B 类"],
        schedule(None, None, "双年赛：2026 年非主体赛事年", "not-held", "https://bj.tiaozhanbei.net/d1/news/notices", "北京挑战杯通知平台"),
        ("2027-03-01", "2027-07-31", "预计3—7月"),
        basis_2027="按首都挑战杯两项主体赛隔年交替及 2025 赛程推算",
    ),
    event(
        "capital-challenge-business",
        "“青创北京”“挑战杯”首都大学生创业计划竞赛",
        "technology",
        ["B 类"],
        schedule("2026-03-01", "2026-06-30", "3—5月参赛攻关，5—6月评审", "official", "https://www.bjyouth.gov.cn/news/workDynamics/762386997747781.html", "北京共青团 2026 专项赛安排", stage="校赛至市赛"),
        (None, None, "双年赛：预计 2027 年不举办主体赛"),
        status_2027="not-held",
        basis_2027="按首都挑战杯两项主体赛隔年交替推算",
    ),
    event(
        "china-software-cup",
        "中国软件杯大学生软件设计大赛",
        "technology",
        ["C 类"],
        schedule("2026-03-24", "2026-08-07", "报名3月24日—6月30日；总决赛8月", "official", "https://www.cnsoftbei.com/", "中国软件杯官网", stage="报名至总决赛"),
        ("2027-03-20", "2027-08-15", "预计3月下旬—8月中旬"),
    ),
    event(
        "information-security",
        "全国大学生信息安全竞赛",
        "technology",
        ["C 类"],
        schedule("2026-05-29", "2026-08-31", "作品赛5月29日启动；全国决赛8月", "official", "https://www.ciscn.cn/", "全国大学生信息安全竞赛官网", stage="作品赛与创新实践能力赛"),
        ("2027-05-20", "2027-08-31", "预计5月下旬—8月"),
    ),
    event(
        "college-computer",
        "中国高校计算机大赛",
        "technology",
        ["C 类"],
        schedule("2026-03-01", "2026-12-31", "系列赛各子赛项分布于3—12月", "window", "https://www.c4best.cn/", "中国高校计算机大赛平台", stage="系列赛", note="AIGC、网络技术、移动应用等子赛项独立发布日程。"),
        ("2027-03-01", "2027-12-31", "预计3—12月，各子赛项独立"),
    ),
    event(
        "computer-design",
        "中国大学生计算机设计大赛",
        "technology",
        ["C 类"],
        schedule("2026-03-01", "2026-08-31", "3月启动；各国赛区集中在7—8月", "window", "https://jsjds.blcu.edu.cn/info/1042/2294.htm", "2026 中国大学生计算机设计大赛通知", stage="校赛至国赛"),
        ("2027-03-01", "2027-08-31", "预计3—8月"),
    ),
    event(
        "openatom",
        "开放原子大赛",
        "technology",
        ["C 类"],
        schedule("2026-05-15", "2026-11-30", "首批赛项5月15日起报名；各赛项独立决赛", "window", "https://competition.openatom.tech/", "开放原子大赛官网", stage="分赛项赛程", note="操作系统专项赛报名截至7月28日，其他赛项时间不同。"),
        ("2027-05-01", "2027-11-30", "预计5—11月，各赛项独立"),
    ),
    event(
        "embedded-chip",
        "全国大学生嵌入式芯片与系统设计竞赛",
        "technology",
        ["C 类"],
        schedule("2026-02-10", "2026-08-13", "2月10日启动；应用赛道全国总决赛8月", "official", "https://www.socchina.net/home?trackType=1", "嵌入式芯片与系统设计竞赛官网", stage="应用赛道", note="芯片设计、FPGA 等专项赛可能延续至下半年。"),
        ("2027-02-10", "2027-08-20", "预计2月中旬—8月中旬"),
    ),
    event(
        "robot-ai",
        "中国机器人及人工智能大赛",
        "technology",
        ["C 类"],
        schedule("2026-03-01", "2026-08-01", "3月1日起报名；全国决赛7月24日—8月1日分场举行", "official", "https://www.caairobot.com/tag/notification/", "中国机器人及人工智能大赛官网", stage="报名至全国决赛"),
        ("2027-03-01", "2027-08-01", "预计3月—8月初"),
    ),
    event(
        "ican",
        "iCAN 大学生创新创业大赛",
        "technology",
        ["C 类"],
        schedule("2026-03-01", "2026-11-30", "3月启动；主赛道作品7月31日前提交，国赛预计秋季", "window", "https://www.g-ican.com/", "iCAN 大赛官网", stage="主赛道", note="挑战赛各赛题另设日期。"),
        ("2027-03-01", "2027-11-30", "预计3—11月"),
    ),
    event(
        "new-domain",
        "新域新质创新大赛",
        "technology",
        ["C 类"],
        schedule("2026-07-01", "2026-10-25", "7月启动；全国总决赛暂定10月25日", "official", "https://www.xyxzds.com/", "2026 新域新质创新大赛官网", stage="预选至全国总决赛"),
        ("2027-07-01", "2027-10-31", "预计7—10月"),
        basis_2027="按 2025、2026 两届均在秋季完成决赛推算",
    ),
    event(
        "jingcai",
        "“京彩大创”北京大学生创新创业大赛",
        "technology",
        ["C 类"],
        schedule("2026-04-08", "2026-06-30", "报名4月8日—5月15日；分赛道决赛6月中下旬", "official", "https://jw.beijing.gov.cn/tzgg/202605/t20260508_4641324.html", "北京市教委第五届京彩大创通知", stage="报名至分赛道决赛", note="总决赛具体日期仍待另行通知。"),
        ("2027-04-01", "2027-07-15", "预计4月—7月上旬"),
    ),
    event(
        "national-math",
        "全国大学生数学竞赛（非数学类）",
        "discipline",
        ["学科竞赛"],
        schedule("2026-11-14", "2026-11-14", "初赛11月14日9:00—11:30", "official", "https://www.cmathc.org.cn/tzgg/545.html", "第十八届全国大学生数学竞赛通知", stage="初赛", note="本届决赛预计于2027年4月举行。"),
        ("2027-04-01", "2027-04-30", "第十八届决赛预计4月；下一届初赛预计11月"),
        status_2027="window",
        basis_2027="第十八届官方通知已明确决赛预计 2027 年 4 月；下一届初赛按年度周期推算",
        note_2027="决赛具体日期将在 2027 年另行通知。",
    ),
    event(
        "cumcm",
        "全国大学生数学建模竞赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-09-10", "2026-09-13", "9月10日18:00—13日20:00", "official", "https://www.csiam.org.cn/upload/shuxue/69c3870950b04.pdf", "2026 全国大学生数学建模竞赛通知", stage="全国竞赛"),
        ("2027-09-09", "2027-09-12", "预计9月上旬，连续约3天"),
        basis_2027="按赛事长期固定在每年 9 月上旬及 2025/2026 周期推算",
    ),
    event(
        "mcm",
        "国际大学生数学建模竞赛（美赛）",
        "discipline",
        ["学科竞赛"],
        schedule("2026-01-29", "2026-02-02", "美东时间1月29日—2月2日", "official", "https://www.contest.comap.org/undergraduate/contests/mcm/instructions.php", "COMAP MCM/ICM 官方规则", stage="正式比赛"),
        ("2027-01-28", "2027-02-01", "美东时间1月28日—2月1日"),
        source_2027=("https://www.contest.comap.org/undergraduate/contests/mcm/instructions.php", "COMAP 2027 官方规则"),
        status_2027="official",
        basis_2027="COMAP 已正式公布",
        note_2027="北京时间约为1月29日至2月2日。",
    ),
    event(
        "statistics-modeling",
        "全国大学生统计建模大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-03-01", "2026-08-20", "3月启动；国赛现场答辩8月", "window", "https://www.ai-learning.net/", "全国大学生统计建模大赛官网", stage="论文赛至国赛"),
        ("2027-03-01", "2027-08-31", "预计3—8月"),
    ),
    event(
        "regional-physics",
        "全国部分地区大学生物理竞赛（非物理类 A 组）",
        "discipline",
        ["学科竞赛"],
        schedule("2026-12-01", "2026-12-15", "预计12月上旬，具体日期待北京赛区通知", "estimated", "https://www.bjwlxh.cn/Ch/wapNewsList.asp?SortID=2", "北京物理学会通知平台", stage="北京赛区", basis="推免方案表列每年12月，并参考2024、2025均于12月上旬举行"),
        ("2027-12-01", "2027-12-15", "预计12月上旬"),
    ),
    event(
        "zhou-peiyuan",
        "全国周培源大学生力学竞赛",
        "discipline",
        ["学科竞赛"],
        schedule(None, None, "两年一届：2026 年预计不举办个人赛", "not-held", "https://zpy.cstam.org.cn/", "全国周培源大学生力学竞赛官网", note="第十五届个人赛已于2025年5月举行。"),
        ("2027-05-01", "2027-05-31", "预计5月"),
        basis_2027="按两年一届及 2025 年第十五届个人赛时间推算",
    ),
    event(
        "buaa-physics",
        "北航物理竞赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-04-11", "2026-04-11", "决赛4月11日", "official", "https://news.buaa.edu.cn/info/1005/68693.htm", "北航第十一届物理学术竞赛报道", stage="决赛"),
        ("2027-04-01", "2027-04-30", "预计4月"),
    ),
    event(
        "neccs",
        "全国大学生英语竞赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-04-12", "2026-05-10", "初赛4月12日；决赛5月10日", "official", "https://www.chinaneccs.cn/", "全国大学生英语竞赛官网", stage="初赛与决赛"),
        ("2027-04-10", "2027-05-16", "预计4月初赛、5月决赛"),
    ),
    event(
        "fltrp",
        "“外研社·国才杯”全国大学生外语能力大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-09-01", "2026-12-15", "9—10月校赛；全国统一初赛10月11日；国赛预计冬季", "window", "https://ucc.fltrp.com/", "外研社·国才杯大赛官网", stage="校赛至国赛"),
        ("2027-09-01", "2027-12-15", "预计9—12月"),
        basis_2027="按 2025/2026 赛程及推免方案表列第四季度推算",
    ),
    event(
        "21st-century",
        "“21 世纪杯”全国英语演讲比赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-03-01", "2026-10-31", "校园赛3—4月；地区赛4—7月；国赛拟10月", "window", "https://contest.i21st.cn/", "21世纪杯官方网站", stage="校园赛至全国赛"),
        ("2027-03-01", "2027-10-31", "预计3—10月"),
        basis_2027="按 2025/2026 赛程及推免方案表列3—5月主要选拔期推算",
    ),
    event(
        "cross-cultural",
        "“外教社杯”全国高校学生跨文化能力大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-03-01", "2026-11-30", "3—4月校赛；省赛秋季；全国赛时间待通知", "window", "https://ict.sflep.com/", "外教社杯跨文化能力大赛官网", stage="校赛至全国赛"),
        ("2027-03-01", "2027-11-30", "预计3—11月"),
        basis_2027="按 2025/2026 赛程及推免方案表列7月传统节点推算",
    ),
    event(
        "words-talent",
        "“外教社·词达人杯”全国大学生英语词汇能力大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-04-14", "2026-09-19", "报名4月14—30日；校赛5月；省赛6月27日；国赛9月19日", "official", "https://wec.sflep.com/", "词达人赛事平台", stage="报名至全国决赛"),
        ("2027-04-15", "2027-09-20", "预计4月中旬—9月中旬"),
    ),
    event(
        "computer-systems",
        "全国大学生计算机系统能力大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-04-29", "2026-08-24", "4月下旬启动；主要赛道总决赛8月18—24日", "official", "https://www.csc-he.cn/", "全国大学生计算机系统能力大赛官网", stage="各系统赛道"),
        ("2027-04-20", "2027-08-31", "预计4月下旬—8月"),
    ),
    event(
        "matiji",
        "“码蹄杯”全国大学生程序设计大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-03-22", "2026-06-30", "初赛3月22日、4月26日、5月24日；决赛待通知", "official", "https://matiji.net/matibei", "码蹄杯大赛官网", stage="初赛至决赛"),
        ("2027-03-20", "2027-06-30", "预计3—6月"),
        basis_2027="按 2025/2026 多场初赛节奏及推免方案表列第二、三季度推算",
    ),
    event(
        "baidu-star",
        "百度之星程序设计大赛",
        "discipline",
        ["学科竞赛"],
        schedule("2026-08-23", "2026-10-17", "省赛8月23日、9月19日；国赛10月17日", "official", "https://astar.baidu.com/", "百度之星大赛官网", stage="省赛与国赛"),
        ("2027-08-20", "2027-10-20", "预计8月下旬—10月中旬"),
        basis_2027="按 2025/2026 实际赛程及推免方案表列8—9月推算",
    ),
    event(
        "acm-ccpc",
        "CCPC 中国大学生程序设计竞赛",
        "acm",
        ["ACM 单独计分表"],
        schedule("2026-04-01", "2026-11-30", "全国邀请赛春季；全国赛通常秋季", "window", "https://ccpc.io/", "CCPC 官方网站", stage="邀请赛与全国赛"),
        ("2027-04-01", "2027-11-30", "预计4—11月"),
    ),
    event(
        "acm-icpc-regional",
        "ICPC 亚洲区域赛",
        "acm",
        ["ACM 单独计分表"],
        schedule("2026-09-01", "2026-12-31", "线上预选9月；中国赛站集中在10—12月", "official", "https://icpc.pku.edu.cn/", "ICPC 北京总部 2026 EC 赛站汇总", stage="预选与区域赛"),
        ("2027-09-01", "2027-12-31", "预计9—12月"),
    ),
    event(
        "acm-ec-final",
        "ICPC Asia EC Final",
        "acm",
        ["ACM 单独计分表"],
        schedule("2026-01-31", "2026-02-02", "2025 赛季 EC Final：1月31日—2月2日", "official", "https://icpc.pku.edu.cn/", "ICPC 北京总部", stage="洲际决赛"),
        ("2027-01-25", "2027-02-08", "预计1月末—2月初"),
        basis_2027="按 2025 赛季 EC Final 于 2026 年 1—2 月举办的跨年周期推算",
    ),
    event(
        "acm-world-final",
        "ICPC 全球总决赛",
        "acm",
        ["ACM 单独计分表"],
        schedule("2026-08-15", "2026-09-15", "2026 世界总决赛具体日期以 ICPC 公告为准", "pending", "https://icpc.global/worldfinals/", "ICPC World Finals", stage="全球总决赛"),
        ("2027-08-15", "2027-09-15", "预计8月中旬—9月中旬"),
        basis_2027="按近届世界总决赛在 8—9 月举行的周期推算",
    ),
    event(
        "fengru",
        "北京航空航天大学“冯如杯”竞赛",
        "campus",
        ["科技创新单独计分表"],
        schedule("2026-04-01", "2026-05-31", "4月院审；5月16—31日集中答辩", "official", "https://www-fengrubei-net-443.e2.buaa.edu.cn/d1/website_notice", "第三十六届冯如杯公告", stage="院审与校级答辩"),
        ("2027-04-01", "2027-05-31", "预计4月院审、5月校级答辩"),
    ),
]


def _entry_for_year(item: dict[str, Any], year: int) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in item.items() if key != "schedules"}
    result.update(deepcopy(item["schedules"][year]))
    result["year"] = year
    result["searchText"] = " ".join(
        [result["name"], *result["aliases"], *result["policyLabels"]]
    )
    result["sortDate"] = result["startDate"] or f"{year}-12-31"
    return result


def public_competition_calendar() -> dict[str, Any]:
    entries = [
        _entry_for_year(item, year)
        for item in EVENTS
        for year in (2026, 2027)
    ]
    statuses = Counter(entry["status"] for entry in entries)
    categories = Counter(item["categoryId"] for item in EVENTS)
    return {
        "updatedAt": UPDATED_AT,
        "generatedAt": date.today().isoformat(),
        "years": [2026, 2027],
        "categories": [
            {"id": category_id, "name": name, "count": categories[category_id]}
            for category_id, name in CATEGORY_NAMES.items()
        ],
        "statuses": [
            {"id": status_id, "name": name, "count": statuses[status_id]}
            for status_id, name in STATUS_NAMES.items()
        ],
        "summary": {
            "uniqueCompetitions": len(EVENTS),
            "policyEntries": 47,
            "official2026": sum(
                entry["status"] in {"official", "window"} and entry["year"] == 2026
                for entry in entries
            ),
            "official2027": sum(
                entry["status"] in {"official", "window"} and entry["year"] == 2027
                for entry in entries
            ),
            "estimated2027": sum(
                entry["status"] == "estimated" and entry["year"] == 2027
                for entry in entries
            ),
        },
        "notice": "2027 年除已明确标注为官方公布的项目外，均按 2025/2026 实际赛程和推免方案表列月份推算。报名与参赛前请打开来源复核。",
        "items": entries,
    }
