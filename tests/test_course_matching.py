import sqlite3

from app import database
from app.course_matching import match_rule_course, normalize_course_name


def test_normalizes_harmless_course_name_differences():
    cases = {
        "离散数学(信息类)": "B060012004",
        " 数据结构与程序设计 ( 信息类 ) ": "B060012005",
        "基础物理学A(1)": "B190011004",
        "基础物理实验(1)": "B190011007",
        "面向对象程序设计（JAVA）": "B210031001",
    }
    for school_name, expected_code in cases.items():
        match = match_rule_course("", school_name)
        assert match is not None
        assert match.course.code == expected_code
        assert match.method == "normalized_name"


def test_does_not_use_fuzzy_course_name_matching():
    assert match_rule_course("", "人工智能导论") is None
    assert match_rule_course("", "数据库原理与应用") is None
    assert match_rule_course("", "工科数学分析进阶（信息类）") is None


def test_normalization_keeps_meaningful_text():
    assert normalize_course_name("人工智能导论") != normalize_course_name("人工智能")


def test_startup_reconciles_a_legacy_generated_school_row():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE courses (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, code TEXT NOT NULL,
            name TEXT NOT NULL, credits REAL NOT NULL, term_code TEXT NOT NULL,
            score_text TEXT, score_scale TEXT NOT NULL, selected_for_rule INTEGER DEFAULT 0,
            source TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            school_course_key TEXT, upstream_score_text TEXT, upstream_score_scale TEXT,
            upstream_updated_at TEXT, UNIQUE(user_id, code)
        )
        """
    )
    db.execute(
        """
        INSERT INTO courses(user_id, code, name, credits, term_code, score_scale, source)
        VALUES (2, 'B060012004', '离散数学（信息类）', 2, '待同步', 'percentage', 'rule')
        """
    )
    db.execute(
        """
        INSERT INTO courses(
            user_id, code, name, credits, term_code, score_text, score_scale,
            source, school_course_key, upstream_score_text, upstream_score_scale
        ) VALUES (2, 'BUAA-LEGACY', '离散数学(信息类)', 2, '2024-2025-2',
                  '99', 'percentage', 'school', 'legacy-key', '99', 'percentage')
        """
    )

    result = database._reconcile_normalized_course_matches(db)
    repaired = db.execute(
        "SELECT * FROM courses WHERE user_id = 2 AND code = 'B060012004'"
    ).fetchone()
    duplicate = db.execute(
        "SELECT 1 FROM courses WHERE user_id = 2 AND code = 'BUAA-LEGACY'"
    ).fetchone()
    assert result == {"merged": 1, "conflicts": 0}
    assert repaired["name"] == "离散数学（信息类）"
    assert repaired["score_text"] == "99"
    assert repaired["term_code"] == "2024-2025-2"
    assert repaired["source"] == "school"
    assert duplicate is None
    db.close()
