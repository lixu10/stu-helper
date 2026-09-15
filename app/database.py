from __future__ import annotations

import os
import hashlib
import json
import sqlite3
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.calculation import CourseResult
from app.course_matching import build_school_course_key, match_rule_course, normalize_course_name
from app.rules import COURSE_BY_CODE, DEFAULT_RULE_ID


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("STUDENT_HELPER_DB", ROOT / "data" / "student-helper.db"))


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_database() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                cohort INTEGER NOT NULL,
                school TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                credits REAL NOT NULL,
                term_code TEXT NOT NULL,
                score_text TEXT,
                score_scale TEXT NOT NULL DEFAULT 'percentage',
                selected_for_rule INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'school',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code)
            );
            CREATE TABLE IF NOT EXISTS sync_state (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                auto_sync INTEGER NOT NULL DEFAULT 0,
                last_sync_at TEXT,
                detail TEXT
            );
            CREATE TABLE IF NOT EXISTS grade_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                term_code TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                payload_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                selected_rule_id TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS app_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_app_sessions_expires_at
                ON app_sessions(expires_at);
            CREATE TABLE IF NOT EXISTS comprehensive_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                rule_id TEXT NOT NULL DEFAULT 'soft-where-2023-reference',
                use_current_gpa INTEGER NOT NULL DEFAULT 1,
                manual_base_gpa REAL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS comprehensive_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT,
                values_json TEXT NOT NULL DEFAULT '{}',
                category_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                name TEXT NOT NULL,
                academic_year TEXT NOT NULL DEFAULT '',
                base_score REAL NOT NULL,
                factor REAL NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_comprehensive_items_user
                ON comprehensive_items(user_id, category_id);
            """
        )
        _ensure_column(db, "courses", "school_course_key", "TEXT")
        _ensure_column(db, "courses", "upstream_score_text", "TEXT")
        _ensure_column(db, "courses", "upstream_score_scale", "TEXT")
        _ensure_column(db, "courses", "upstream_updated_at", "TEXT")
        _ensure_column(db, "comprehensive_items", "kind", "TEXT")
        _ensure_column(db, "comprehensive_items", "values_json", "TEXT NOT NULL DEFAULT '{}'")
        db.execute(
            """
            UPDATE comprehensive_items
            SET kind = 'manual-' || category_id
            WHERE kind IS NULL OR kind = ''
            """
        )
        _repair_inconsistent_score_scales(db)
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            _seed_demo(db)
        _reconcile_normalized_course_matches(db)
        _reconcile_school_course_duplicates(db)


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _repair_inconsistent_score_scales(db: sqlite3.Connection) -> None:
    """Apply the current normalization policy to rows written by older versions."""
    rows = db.execute(
        """
        SELECT id, score_text, score_scale, upstream_score_text
        FROM courses
        WHERE source != 'manual' AND score_text IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        score_text = str(row["score_text"]).strip()
        corrected_scale = None
        if score_text in {"优秀", "良好", "中等", "及格", "不及格"}:
            corrected_scale = "five_level"
        elif score_text in {"通过", "不通过", "合格", "不合格"}:
            corrected_scale = "pass_fail"
        try:
            value = float(score_text)
        except (TypeError, ValueError):
            value = None
        if value is not None and 0 <= value <= 100:
            corrected_scale = "percentage"
        if corrected_scale and corrected_scale != row["score_scale"]:
            db.execute(
                """
                UPDATE courses SET
                    score_scale = ?,
                    upstream_score_scale = CASE
                        WHEN upstream_score_text IS NOT NULL THEN ?
                        ELSE upstream_score_scale
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (corrected_scale, corrected_scale, row["id"]),
            )


def _reconcile_normalized_course_matches(db: sqlite3.Connection) -> dict[str, int]:
    """Merge legacy school rows that differ from a rule only in safe formatting."""
    candidates: dict[tuple[int, str], list[sqlite3.Row]] = {}
    rows = db.execute(
        "SELECT * FROM courses WHERE source IN ('school', 'manual')"
    ).fetchall()
    for row in rows:
        if row["code"] in COURSE_BY_CODE:
            continue
        match = match_rule_course(row["code"], row["name"])
        if match:
            candidates.setdefault((int(row["user_id"]), match.course.code), []).append(row)

    merged = 0
    conflicts = 0
    for (user_id, rule_code), source_rows in candidates.items():
        # Multiple attempts need an explicit policy; never guess which attempt counts.
        if len(source_rows) != 1:
            conflicts += len(source_rows)
            continue
        source = source_rows[0]
        rule = COURSE_BY_CODE[rule_code]
        target = db.execute(
            "SELECT * FROM courses WHERE user_id = ? AND code = ?",
            (user_id, rule_code),
        ).fetchone()
        if target is None:
            db.execute(
                """
                UPDATE courses SET code = ?, name = ?, credits = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (rule.code, rule.name, source["credits"] or rule.credits, source["id"]),
            )
            merged += 1
            continue
        if target["source"] not in {"rule", "manual"}:
            conflicts += 1
            continue

        if (
            target["source"] == "manual"
            and source["source"] == "manual"
            and target["score_text"] != source["score_text"]
        ):
            conflicts += 1
            continue
        preserve_target_manual = target["source"] == "manual"
        preserve_manual = preserve_target_manual or source["source"] == "manual"
        db.execute(
            """
            UPDATE courses SET
                name = ?, credits = ?, term_code = ?, school_course_key = ?,
                upstream_score_text = ?, upstream_score_scale = ?,
                upstream_updated_at = COALESCE(?, CURRENT_TIMESTAMP),
                score_text = ?, score_scale = ?, source = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                rule.name,
                source["credits"] or rule.credits,
                source["term_code"],
                source["school_course_key"],
                source["upstream_score_text"] or source["score_text"],
                source["upstream_score_scale"] or source["score_scale"],
                source["upstream_updated_at"],
                target["score_text"] if preserve_target_manual else source["score_text"],
                target["score_scale"] if preserve_target_manual else source["score_scale"],
                "manual" if preserve_manual else "school",
                target["id"],
            ),
        )
        db.execute("DELETE FROM courses WHERE id = ?", (source["id"],))
        merged += 1
    return {"merged": merged, "conflicts": conflicts}


def _reconcile_school_course_duplicates(db: sqlite3.Connection) -> dict[str, int]:
    """Collapse rows created when an unstable upstream array index changed."""
    groups: dict[tuple[int, str, str, float], list[sqlite3.Row]] = {}
    rows = db.execute(
        "SELECT * FROM courses WHERE source = 'school' AND code LIKE 'BUAA-%'"
    ).fetchall()
    for row in rows:
        key = (
            int(row["user_id"]),
            str(row["term_code"]),
            normalize_course_name(row["name"]),
            round(float(row["credits"]), 6),
        )
        groups.setdefault(key, []).append(row)

    merged = 0
    conflicts = 0
    for group_rows in groups.values():
        non_empty_scores = {
            str(row["score_text"]).strip()
            for row in group_rows
            if row["score_text"] is not None and str(row["score_text"]).strip()
        }
        if len(non_empty_scores) > 1:
            conflicts += len(group_rows)
            continue

        winner = max(
            group_rows,
            key=lambda row: (
                row["score_text"] is not None and str(row["score_text"]).strip() != "",
                row["upstream_updated_at"] or "",
                int(row["id"]),
            ),
        )
        stable_key = build_school_course_key(
            str(winner["term_code"]), "", str(winner["name"]), float(winner["credits"])
        )
        generated_code = f"BUAA-{stable_key.upper()}"
        for row in group_rows:
            if row["id"] != winner["id"]:
                db.execute("DELETE FROM courses WHERE id = ?", (row["id"],))
                merged += 1
        db.execute(
            """
            UPDATE courses SET code = ?, school_course_key = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (generated_code, stable_key, winner["id"]),
        )
    return {"merged": merged, "conflicts": conflicts}


def _seed_demo(db: sqlite3.Connection) -> None:
    user_id = db.execute(
        "INSERT INTO users(student_id, name, cohort, school) VALUES (?, ?, ?, ?)",
        ("2437****", "北航同学", 2024, "软件学院"),
    ).lastrowid
    db.execute(
        "INSERT INTO sync_state(user_id, provider, status, auto_sync, last_sync_at, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            "demo",
            "demo_ready",
            0,
            "2026-09-15 00:18:00",
            "当前使用脱敏演示数据；接入学校接口后会替换为真实同步状态。",
        ),
    )
    scores = {
        "B090011021": (91, "percentage", "2024-2025-1", 0),
        "B090011010": (86, "percentage", "2024-2025-1", 0),
        "B090011022": (88, "percentage", "2024-2025-2", 0),
        "B190011004": (83, "percentage", "2024-2025-2", 0),
        "B090011018": (90, "percentage", "2025-2026-1", 0),
        "B190011007": ("良好", "five_level", "2025-2026-1", 0),
        "B370012005": (94, "percentage", "2024-2025-1", 0),
        "B020012001": (87, "percentage", "2024-2025-2", 0),
        "B060012004": (89, "percentage", "2024-2025-2", 0),
        "B060012005": (92, "percentage", "2024-2025-2", 0),
        "B120013011": (88, "percentage", "2024-2025-1", 0),
        "B120013012": (90, "percentage", "2024-2025-1", 0),
        "B120013013": ("优秀", "five_level", "2024-2025-1", 0),
        "B120013014": (86, "percentage", "2024-2025-2", 0),
        "B120013015": (91, "percentage", "2024-2025-2", 0),
        "T120013006": ("良好", "five_level", "2024-2025-2", 0),
        "B120013007": (89, "percentage", "2025-2026-1", 0),
        "B120013008": (93, "percentage", "2025-2026-1", 0),
        "B280021001": (90, "percentage", "2024-2025-1", 0),
        "B280021002": (88, "percentage", "2024-2025-1", 0),
        "B280021003": (92, "percentage", "2024-2025-2", 0),
        "B280021004": (86, "percentage", "2025-2026-1", 0),
        "B280021006": (84, "percentage", "2025-2026-2", 0),
        "B210031003": (93, "percentage", "2025-2026-1", 0),
        "B210031002": (85, "percentage", "2025-2026-1", 0),
        "B210031004": (90, "percentage", "2025-2026-1", 0),
        "B210031001": (94, "percentage", "2025-2026-1", 0),
        "B210031005": (88, "percentage", "2025-2026-2", 0),
        "B210031006": (91, "percentage", "2025-2026-2", 0),
        "B060031006": (87, "percentage", "2025-2026-2", 0),
        "B210031007": (89, "percentage", "2025-2026-2", 0),
        "B210031009": (95, "percentage", "2024-2025-3", 0),
        "B210031010": (92, "percentage", "2025-2026-3", 0),
        "B210032101": (90, "percentage", "2026-2027-1", 1),
        "B210032104": (86, "percentage", "2026-2027-1", 1),
        "B210032105": (93, "percentage", "2026-2027-1", 1),
        "B210032110": (88, "percentage", "2026-2027-1", 0),
        "B210032001": ("通过", "pass_fail", "2025-2026-2", 0),
        "B210032003": ("通过", "pass_fail", "2025-2026-2", 0),
    }
    term_defaults = {
        "D": "2026-2027-1",
        "E": "2026-2027-2",
        "F": "2026-2027-2",
    }
    for code, rule in COURSE_BY_CODE.items():
        score, scale, term, selected = scores.get(
            code, (None, "percentage", term_defaults.get(rule.group, "2026-2027-1"), 0)
        )
        db.execute(
            """
            INSERT INTO courses(
                user_id, code, name, credits, term_code, score_text,
                score_scale, selected_for_rule, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, code, rule.name, rule.credits, term, score, scale, selected, "demo"),
        )


def current_user(user_id: int = 1) -> dict:
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            row = db.execute("SELECT * FROM users ORDER BY id LIMIT 1").fetchone()
        sync = db.execute("SELECT * FROM sync_state WHERE user_id = ?", (row["id"],)).fetchone()
    return {
        "id": row["id"],
        "studentId": row["student_id"],
        "name": row["name"],
        "cohort": row["cohort"],
        "school": row["school"],
        "sync": dict(sync) if sync else None,
    }


def list_courses(user_id: int = 1) -> list[CourseResult]:
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM courses WHERE user_id = ? ORDER BY term_code, code", (user_id,)
        ).fetchall()
    return [
        CourseResult(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            credits=row["credits"],
            term_code=row["term_code"],
            score_text=row["score_text"],
            score_scale=row["score_scale"],
            selected_for_rule=bool(row["selected_for_rule"]),
            source=row["source"],
        )
        for row in rows
    ]


def update_course(
    course_id: int,
    score_text: str | None,
    score_scale: str,
    selected_for_rule: bool,
    user_id: int = 1,
) -> None:
    with connection() as db:
        exists = db.execute(
            "SELECT id FROM courses WHERE id = ? AND user_id = ?", (course_id, user_id)
        ).fetchone()
        if not exists:
            raise KeyError(course_id)
        db.execute(
            """
            UPDATE courses
            SET score_text = ?, score_scale = ?, selected_for_rule = ?,
                source = 'manual', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (score_text, score_scale, int(selected_for_rule), course_id),
        )


def import_courses(user_id: int, courses: list[dict]) -> dict[str, int]:
    """Atomically merge validated CSV rows by course code."""
    created = 0
    updated = 0
    with connection() as db:
        existing_codes = {
            str(row["code"])
            for row in db.execute("SELECT code FROM courses WHERE user_id = ?", (user_id,))
        }
        for course in courses:
            if course["code"] in existing_codes:
                updated += 1
            else:
                created += 1
                existing_codes.add(course["code"])
            db.execute(
                """
                INSERT INTO courses(
                    user_id, code, name, credits, term_code, score_text,
                    score_scale, selected_for_rule, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual')
                ON CONFLICT(user_id, code) DO UPDATE SET
                    name = excluded.name,
                    credits = excluded.credits,
                    term_code = excluded.term_code,
                    score_text = excluded.score_text,
                    score_scale = excluded.score_scale,
                    selected_for_rule = excluded.selected_for_rule,
                    source = 'manual',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    course["code"],
                    course["name"],
                    course["credits"],
                    course["term_code"],
                    course["score_text"],
                    course["score_scale"],
                    int(course["selected_for_rule"]),
                ),
            )
    return {"created": created, "updated": updated, "total": len(courses)}


def _cohort_from_student_id(student_id: str) -> int:
    prefix = student_id[:2]
    if prefix.isdigit():
        year = 2000 + int(prefix)
        if 2000 <= year <= 2100:
            return year
    return 2024


def upsert_school_user(student_id: str, name: str) -> int:
    """Create the local identity and its rule-course skeleton after SSO verification."""
    with connection() as db:
        row = db.execute("SELECT id FROM users WHERE student_id = ?", (student_id,)).fetchone()
        if row:
            user_id = int(row["id"])
            db.execute(
                "UPDATE users SET name = ?, cohort = ?, school = ? WHERE id = ?",
                (name, _cohort_from_student_id(student_id), "软件学院", user_id),
            )
        else:
            user_id = int(
                db.execute(
                    "INSERT INTO users(student_id, name, cohort, school) VALUES (?, ?, ?, ?)",
                    (student_id, name, _cohort_from_student_id(student_id), "软件学院"),
                ).lastrowid
            )
        db.execute(
            """
            INSERT INTO sync_state(user_id, provider, status, auto_sync, detail)
            VALUES (?, 'buaa', 'authenticated', 0, '学校身份已验证，等待同步成绩。')
            ON CONFLICT(user_id) DO UPDATE SET
                provider = 'buaa', status = 'authenticated', detail = excluded.detail
            """,
            (user_id,),
        )
        existing_codes = {
            item[0] for item in db.execute("SELECT code FROM courses WHERE user_id = ?", (user_id,))
        }
        for code, rule in COURSE_BY_CODE.items():
            if code in existing_codes:
                continue
            db.execute(
                """
                INSERT INTO courses(
                    user_id, code, name, credits, term_code, score_text,
                    score_scale, selected_for_rule, source
                ) VALUES (?, ?, ?, ?, ?, NULL, 'percentage', 0, 'rule')
                """,
                (user_id, code, rule.name, rule.credits, "待同步"),
            )
    return user_id


def set_sync_state(user_id: int, status: str, detail: str) -> None:
    with connection() as db:
        db.execute(
            """
            INSERT INTO sync_state(user_id, provider, status, auto_sync, detail)
            VALUES (?, 'buaa', ?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                provider = 'buaa', status = excluded.status, detail = excluded.detail
            """,
            (user_id, status, detail),
        )


def get_selected_rule(user_id: int) -> str:
    with connection() as db:
        row = db.execute(
            "SELECT selected_rule_id FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    return str(row["selected_rule_id"]) if row else DEFAULT_RULE_ID


def set_selected_rule(user_id: int, rule_id: str) -> None:
    with connection() as db:
        db.execute(
            """
            INSERT INTO user_preferences(user_id, selected_rule_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                selected_rule_id = excluded.selected_rule_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, rule_id),
        )


def sync_school_grades(
    user_id: int,
    grades_by_term: dict[str, list[dict]],
    raw_by_term: dict[str, dict],
) -> dict:
    """Atomically archive raw payloads and merge normalized school grades."""
    synced = 0
    manual_preserved = 0
    matched_by_name = 0
    with connection() as db:
        for term_code, payload in raw_by_term.items():
            payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            db.execute(
                """
                INSERT INTO grade_snapshots(user_id, term_code, payload_sha256, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, term_code, digest, payload_json),
            )

        for term_code, rows in grades_by_term.items():
            for grade in rows:
                match = match_rule_course(grade["code"], grade["name"])
                matched_rule = match.course if match else None
                if match and match.method != "course_code":
                    matched_by_name += 1
                code = matched_rule.code if matched_rule else grade["code"]
                name = matched_rule.name if matched_rule else grade["name"]
                if not code:
                    code = f"BUAA-{grade['school_key'].upper()}"
                existing = db.execute(
                    "SELECT id, source FROM courses WHERE user_id = ? AND code = ?",
                    (user_id, code),
                ).fetchone()
                if existing:
                    preserve_manual = existing["source"] == "manual"
                    if preserve_manual:
                        manual_preserved += 1
                    db.execute(
                        """
                        UPDATE courses SET
                            name = ?, credits = ?, term_code = ?, school_course_key = ?,
                            upstream_score_text = ?, upstream_score_scale = ?,
                            upstream_updated_at = CURRENT_TIMESTAMP,
                            score_text = CASE WHEN source = 'manual' THEN score_text ELSE ? END,
                            score_scale = CASE WHEN source = 'manual' THEN score_scale ELSE ? END,
                            source = CASE WHEN source = 'manual' THEN source ELSE 'school' END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (
                            name,
                            grade["credits"] or (matched_rule.credits if matched_rule else 0),
                            term_code,
                            grade["school_key"],
                            grade["score"],
                            grade["score_scale"],
                            grade["score"],
                            grade["score_scale"],
                            existing["id"],
                        ),
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO courses(
                            user_id, code, name, credits, term_code, score_text, score_scale,
                            selected_for_rule, source, school_course_key, upstream_score_text,
                            upstream_score_scale, upstream_updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'school', ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            user_id,
                            code,
                            name,
                            grade["credits"],
                            term_code,
                            grade["score"],
                            grade["score_scale"],
                            grade["school_key"],
                            grade["score"],
                            grade["score_scale"],
                        ),
                    )
                synced += 1
        db.execute(
            """
            INSERT INTO sync_state(user_id, provider, status, auto_sync, last_sync_at, detail)
            VALUES (?, 'buaa', 'synced', 0, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                provider = 'buaa', status = 'synced', last_sync_at = CURRENT_TIMESTAMP,
                detail = excluded.detail
            """,
            (
                user_id,
                f"已从学校同步 {synced} 条成绩，其中 {matched_by_name} 条按规范化课程名匹配；"
                f"保留 {manual_preserved} 条手工修正。",
            ),
        )
    return {
        "synced": synced,
        "matchedByName": matched_by_name,
        "manualPreserved": manual_preserved,
        "terms": len(grades_by_term),
    }


def _session_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_app_session(user_id: int, duration_days: int = 30) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=duration_days)
    with connection() as db:
        db.execute("DELETE FROM app_sessions WHERE expires_at <= ?", (now.isoformat(),))
        db.execute(
            """
            INSERT INTO app_sessions(user_id, token_hash, created_at, last_seen_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, _session_digest(token), now.isoformat(), now.isoformat(), expires_at.isoformat()),
        )
    return token


def resolve_app_session(token: str | None) -> int | None:
    if not token:
        return None
    now = datetime.now(UTC).isoformat()
    with connection() as db:
        row = db.execute(
            """
            SELECT user_id FROM app_sessions
            WHERE token_hash = ? AND expires_at > ?
            """,
            (_session_digest(token), now),
        ).fetchone()
        if not row:
            return None
        db.execute(
            "UPDATE app_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (now, _session_digest(token)),
        )
    return int(row["user_id"])


def delete_app_session(token: str | None) -> None:
    if not token:
        return
    with connection() as db:
        db.execute("DELETE FROM app_sessions WHERE token_hash = ?", (_session_digest(token),))


def get_comprehensive_profile(user_id: int) -> dict:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM comprehensive_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        return {
            "rule_id": "soft-where-2023-reference",
            "use_current_gpa": True,
            "manual_base_gpa": None,
        }
    return {
        "rule_id": row["rule_id"],
        "use_current_gpa": bool(row["use_current_gpa"]),
        "manual_base_gpa": row["manual_base_gpa"],
    }


def update_comprehensive_profile(
    user_id: int, use_current_gpa: bool, manual_base_gpa: float | None
) -> None:
    with connection() as db:
        db.execute(
            """
            INSERT INTO comprehensive_profiles(user_id, use_current_gpa, manual_base_gpa)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                use_current_gpa = excluded.use_current_gpa,
                manual_base_gpa = excluded.manual_base_gpa,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, int(use_current_gpa), manual_base_gpa),
        )


def list_comprehensive_items(user_id: int) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM comprehensive_items WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            item["values"] = json.loads(item.pop("values_json") or "{}")
        except (TypeError, ValueError):
            item["values"] = {}
        items.append(item)
    return items


def add_comprehensive_item(user_id: int, item: dict) -> int:
    with connection() as db:
        return int(
            db.execute(
                """
                INSERT INTO comprehensive_items(
                    user_id, kind, values_json, category_id, item_type, name,
                    academic_year, base_score, factor, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    item.get("kind") or f"manual-{item['category_id']}",
                    json.dumps(item.get("values") or {}, ensure_ascii=False, separators=(",", ":")),
                    item["category_id"],
                    item["item_type"],
                    item["name"],
                    item["academic_year"],
                    item["base_score"],
                    item["factor"],
                    item["note"],
                ),
            ).lastrowid
        )


def import_comprehensive_items(user_id: int, items: list[dict]) -> dict[str, int]:
    """Atomically merge validated comprehensive rows by type and normalized values."""
    created = 0
    updated = 0
    with connection() as db:
        existing: dict[tuple[str, str], int] = {}
        for row in db.execute(
            "SELECT id, kind, values_json FROM comprehensive_items WHERE user_id = ?",
            (user_id,),
        ):
            try:
                normalized_values = json.dumps(
                    json.loads(row["values_json"] or "{}"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            except (TypeError, ValueError):
                normalized_values = str(row["values_json"])
            existing[(str(row["kind"]), normalized_values)] = int(row["id"])
        for item in items:
            values_json = json.dumps(
                item.get("values") or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            key = (str(item["kind"]), values_json)
            item_id = existing.get(key)
            if item_id is None:
                created += 1
                item_id = int(
                    db.execute(
                        """
                        INSERT INTO comprehensive_items(
                            user_id, kind, values_json, category_id, item_type, name,
                            academic_year, base_score, factor, note
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            item["kind"],
                            values_json,
                            item["category_id"],
                            item["item_type"],
                            item["name"],
                            item["academic_year"],
                            item["base_score"],
                            item["factor"],
                            item["note"],
                        ),
                    ).lastrowid
                )
                existing[key] = item_id
            else:
                updated += 1
                db.execute(
                    """
                    UPDATE comprehensive_items SET
                        category_id = ?, item_type = ?, name = ?, academic_year = ?,
                        base_score = ?, factor = ?, note = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        item["category_id"],
                        item["item_type"],
                        item["name"],
                        item["academic_year"],
                        item["base_score"],
                        item["factor"],
                        item["note"],
                        item_id,
                        user_id,
                    ),
                )
    return {"created": created, "updated": updated, "total": len(items)}


def update_comprehensive_item(user_id: int, item_id: int, item: dict) -> None:
    with connection() as db:
        cursor = db.execute(
            """
            UPDATE comprehensive_items SET
                kind = ?, values_json = ?, category_id = ?, item_type = ?, name = ?, academic_year = ?,
                base_score = ?, factor = ?, note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                item.get("kind") or f"manual-{item['category_id']}",
                json.dumps(item.get("values") or {}, ensure_ascii=False, separators=(",", ":")),
                item["category_id"],
                item["item_type"],
                item["name"],
                item["academic_year"],
                item["base_score"],
                item["factor"],
                item["note"],
                item_id,
                user_id,
            ),
        )
        if cursor.rowcount == 0:
            raise KeyError(item_id)


def delete_comprehensive_item(user_id: int, item_id: int) -> None:
    with connection() as db:
        cursor = db.execute(
            "DELETE FROM comprehensive_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(item_id)
