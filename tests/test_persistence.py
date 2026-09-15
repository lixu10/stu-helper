from pathlib import Path

from app import database
from app.comprehensive import prepare_comprehensive_item


def test_local_session_and_comprehensive_data_survive_new_connections(monkeypatch):
    db_path = Path("tmp/test-persistence.db").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    try:
        database.init_database()
        user_id = database.upsert_school_user("24999999", "持久化测试")

        token = database.create_app_session(user_id)
        database.update_comprehensive_profile(user_id, False, 3.75)
        item_id = database.add_comprehensive_item(
            user_id,
            prepare_comprehensive_item(
                "sports",
                {
                    "level": "school",
                    "placement": "first",
                    "projectType": "standard",
                    "form": "individual",
                    "academicYear": "2",
                    "projectName": "院运动会",
                },
                "审核通过",
            ),
        )

        assert database.resolve_app_session(token) == user_id
        assert database.get_comprehensive_profile(user_id)["manual_base_gpa"] == 3.75
        assert database.list_comprehensive_items(user_id)[0]["id"] == item_id
        assert database.list_comprehensive_items(user_id)[0]["values"]["projectName"] == "院运动会"

        database.delete_app_session(token)
        assert database.resolve_app_session(token) is None
        assert database.list_comprehensive_items(user_id)[0]["name"] == "院运动会"
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)
