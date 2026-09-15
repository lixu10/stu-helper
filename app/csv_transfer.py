from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.calculation import score_to_grade_point
from app.comprehensive import prepare_comprehensive_item


MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 2000


def decode_csv(raw: bytes) -> list[dict[str, str]]:
    if not raw:
        raise ValueError("CSV 文件为空")
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError("CSV 文件不能超过 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV 必须使用 UTF-8 编码") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")
    reader.fieldnames = [str(name or "").strip() for name in reader.fieldnames]
    rows = [
        {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        for row in reader
        if any(str(value or "").strip() for value in row.values())
    ]
    if not rows:
        raise ValueError("CSV 没有数据行")
    if len(rows) > MAX_CSV_ROWS:
        raise ValueError(f"CSV 最多允许 {MAX_CSV_ROWS} 行")
    return rows


def _value(row: dict[str, str], *names: str, required: bool = False) -> str:
    value = next((row[name] for name in names if row.get(name, "") != ""), "")
    if required and not value:
        raise ValueError(f"缺少字段：{names[0]}")
    return value


def _yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"是", "1", "true", "yes", "y"}:
        return True
    if normalized in {"", "否", "0", "false", "no", "n"}:
        return False
    raise ValueError(f"无法识别的是/否值：{value}")


def parse_courses_csv(raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(decode_csv(raw), start=2):
        try:
            code = _value(row, "课程代码", "code", required=True)
            if code in seen:
                raise ValueError(f"课程代码重复：{code}")
            seen.add(code)
            name = _value(row, "课程名称", "name", required=True)
            credits = float(_value(row, "学分", "credits", required=True))
            if credits < 0 or credits > 50:
                raise ValueError("学分必须在 0 到 50 之间")
            score_text = _value(row, "成绩", "score") or None
            score_scale = _value(row, "成绩制", "score_scale") or "percentage"
            if score_scale not in {"percentage", "five_level", "pass_fail"}:
                raise ValueError(f"未知成绩制：{score_scale}")
            score_to_grade_point(score_text, score_scale)
            result.append(
                {
                    "code": code,
                    "name": name,
                    "term_code": _value(row, "学期", "term_code") or "未填写",
                    "credits": credits,
                    "score_text": score_text,
                    "score_scale": score_scale,
                    "selected_for_rule": _yes_no(
                        _value(row, "计入方向课", "selected_for_rule")
                    ),
                }
            )
        except ValueError as exc:
            raise ValueError(f"第 {line_number} 行：{exc}") from exc
    return result


def parse_comprehensive_csv(raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line_number, row in enumerate(decode_csv(raw), start=2):
        try:
            kind = _value(row, "项目类型标识", "kind", required=True)
            if kind == "汇总":
                continue
            raw_values = _value(row, "参数JSON", "values_json", required=True)
            values = json.loads(raw_values)
            if not isinstance(values, dict):
                raise ValueError("参数JSON必须是对象")
            result.append(
                prepare_comprehensive_item(
                    kind,
                    values,
                    _value(row, "备注", "note"),
                )
            )
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"第 {line_number} 行：{exc}") from exc
    if not result:
        raise ValueError("CSV 没有可导入的综测项目")
    return result


def safe_csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
