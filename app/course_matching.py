from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

from app.rules import COURSE_BY_CODE, RuleCourse


@dataclass(frozen=True)
class CourseMatch:
    course: RuleCourse
    method: str


def normalize_course_name(name: str | None) -> str:
    """Normalize display-only differences without erasing meaningful course-name text."""
    normalized = unicodedata.normalize("NFKC", name or "").casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace() and character not in {"\u200b", "\ufeff"}
    )


def build_school_course_key(
    term_code: str, code: str | None, name: str | None, credits: float
) -> str:
    """Build an identity that stays stable when the upstream array order changes."""
    identity = "|".join(
        (
            term_code.strip(),
            (code or "").strip().upper(),
            normalize_course_name(name),
            f"{credits:g}",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _build_unique_name_index() -> dict[str, RuleCourse]:
    candidates: dict[str, list[RuleCourse]] = {}
    for course in COURSE_BY_CODE.values():
        candidates.setdefault(normalize_course_name(course.name), []).append(course)
    # A duplicate normalized name is deliberately not auto-matched.
    return {name: courses[0] for name, courses in candidates.items() if len(courses) == 1}


COURSE_BY_NORMALIZED_NAME = _build_unique_name_index()

# Add only aliases verified against an official rule. Fuzzy similarity is intentionally
# excluded: e.g. “人工智能导论” and “人工智能” can be two independent courses.
COURSE_NAME_ALIASES: dict[str, str] = {}


def match_rule_course(code: str | None, name: str | None) -> CourseMatch | None:
    normalized_code = (code or "").strip().upper()
    if normalized_code in COURSE_BY_CODE:
        return CourseMatch(COURSE_BY_CODE[normalized_code], "course_code")

    normalized_name = normalize_course_name(name)
    if not normalized_name:
        return None
    course = COURSE_BY_NORMALIZED_NAME.get(normalized_name)
    if course:
        return CourseMatch(course, "normalized_name")

    alias_code = COURSE_NAME_ALIASES.get(normalized_name)
    if alias_code:
        return CourseMatch(COURSE_BY_CODE[alias_code], "verified_alias")
    return None
