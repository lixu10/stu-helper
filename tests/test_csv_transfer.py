import csv
import io
import json
from pathlib import Path

from app import database
from app.csv_transfer import parse_comprehensive_csv, parse_courses_csv


def csv_bytes(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def test_course_csv_round_trip_fields_and_atomic_merge(monkeypatch):
    db_path = Path("tmp/test-csv-courses.db").resolve()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    try:
        database.init_database()
        user_id = database.upsert_school_user("24999998", "CSV 课程测试")
        raw = csv_bytes(
            ["课程代码", "课程名称", "学期", "学分", "成绩", "成绩制", "计入方向课", "来源"],
            [["B3I091120", "离散数学(信息类)", "2025-2026-1", "4", "92", "percentage", "是", "school"]],
        )

        rows = parse_courses_csv(raw)
        first = database.import_courses(user_id, rows)
        second = database.import_courses(user_id, rows)
        course = next(item for item in database.list_courses(user_id) if item.code == "B3I091120")

        assert first == {"created": 1, "updated": 0, "total": 1}
        assert second == {"created": 0, "updated": 1, "total": 1}
        assert course.score_text == "92"
        assert course.selected_for_rule is True
        assert course.source == "manual"
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def test_comprehensive_csv_skips_summary_and_reimport_updates(monkeypatch):
    db_path = Path("tmp/test-csv-comprehensive.db").resolve()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    try:
        database.init_database()
        user_id = database.upsert_school_user("24999997", "CSV 综测测试")
        values = {
            "academicYear": "2",
            "achievement": "软件杯项目",
            "author": "1",
            "awardRank": "1",
            "competition": "software-cup",
            "specialTrack": "normal",
        }
        raw = csv_bytes(
            ["项目类型标识", "项目名称", "类别", "学年", "参数JSON", "基础分", "系数", "最终计入分", "是否计入", "备注"],
            [
                ["technology-competition", "软件杯项目", "科技创新", "2", json.dumps(values, ensure_ascii=False), "0.1392", "1", "0.1392", "是", "已审核"],
                ["汇总", "综测加分", "0.0696", "", "", "", "", "", "", ""],
            ],
        )

        items = parse_comprehensive_csv(raw)
        first = database.import_comprehensive_items(user_id, items)
        second = database.import_comprehensive_items(user_id, items)
        saved = database.list_comprehensive_items(user_id)

        assert first == {"created": 1, "updated": 0, "total": 1}
        assert second == {"created": 0, "updated": 1, "total": 1}
        assert len(saved) == 1
        assert saved[0]["name"] == "软件杯项目"
        assert saved[0]["note"] == "已审核"
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def test_course_csv_reports_the_failing_line():
    raw = csv_bytes(
        ["课程代码", "课程名称", "学期", "学分", "成绩", "成绩制"],
        [["X-1", "错误课程", "2026-2027-1", "2", "101", "percentage"]],
    )

    try:
        parse_courses_csv(raw)
    except ValueError as exc:
        assert "第 2 行" in str(exc)
        assert "0 到 100" in str(exc)
    else:
        raise AssertionError("invalid score should be rejected")
