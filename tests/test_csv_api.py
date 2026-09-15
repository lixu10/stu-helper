from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.comprehensive import prepare_comprehensive_item
from app.main import APP_SESSION_COOKIE, app


def test_csv_exported_files_can_be_imported_back(monkeypatch):
    db_path = Path("tmp/test-csv-api.db").resolve()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    try:
        with TestClient(app) as client:
            user_id = database.upsert_school_user("24999996", "CSV 接口测试")
            database.add_comprehensive_item(
                user_id,
                prepare_comprehensive_item(
                    "volunteering",
                    {"hours": 120},
                    "已审核",
                ),
            )
            token = database.create_app_session(user_id)
            client.cookies.set(APP_SESSION_COOKIE, token)

            course_export = client.get("/api/v1/export/courses.csv")
            assert course_export.status_code == 200
            assert course_export.content.startswith("课程代码".encode("utf-8-sig"))
            course_import = client.post(
                "/api/v1/import/courses.csv",
                content=course_export.content,
                headers={"Content-Type": "text/csv; charset=utf-8"},
            )
            assert course_import.status_code == 200
            assert course_import.json()["total"] > 0

            comprehensive_export = client.get("/api/v1/export/comprehensive.csv")
            assert comprehensive_export.status_code == 200
            assert comprehensive_export.content.startswith("项目类型标识".encode("utf-8-sig"))
            comprehensive_import = client.post(
                "/api/v1/import/comprehensive.csv",
                content=comprehensive_export.content,
                headers={"Content-Type": "text/csv; charset=utf-8"},
            )
            assert comprehensive_import.status_code == 200
            assert comprehensive_import.json() == {
                "status": "imported",
                "created": 0,
                "updated": 1,
                "total": 1,
            }
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)
