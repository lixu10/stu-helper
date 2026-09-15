from __future__ import annotations

from contextlib import asynccontextmanager
import csv
import io
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.analytics import calculate_academic_analytics
from app.calculation import calculate_dashboard, score_to_grade_point
from app.comprehensive import (
    calculate_comprehensive,
    evaluate_item,
    prepare_comprehensive_item,
    public_comprehensive_rule,
)
from app.competition_calendar import public_competition_calendar
from app.database import (
    add_comprehensive_item,
    create_app_session,
    current_user,
    delete_app_session,
    delete_comprehensive_item,
    get_comprehensive_profile,
    get_selected_rule,
    init_database,
    list_comprehensive_items,
    list_courses,
    resolve_app_session,
    set_sync_state,
    set_selected_rule,
    sync_school_grades,
    update_comprehensive_item,
    update_comprehensive_profile,
    update_course,
    upsert_school_user,
)
from app.integrations.buaa import (
    DEFAULT_TERMS,
    SESSION_COOKIE,
    BuaaAuthenticationError,
    BuaaSessionExpired,
    BuaaUpstreamError,
    buaa_sessions,
)
from app.rules import list_public_rules, public_rule


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
logger = logging.getLogger(__name__)
APP_SESSION_COOKIE = "student_helper_app_session"
APP_SESSION_MAX_AGE = 30 * 24 * 60 * 60


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield
    await buaa_sessions.close_all()


app = FastAPI(
    title="Student Helper",
    version="0.2.0",
    description="北航学习成绩综合计算平台",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class CoursePatch(BaseModel):
    score: str | None = None
    score_scale: str = Field(default="percentage", pattern="^(percentage|five_level|pass_fail)$")
    selected_for_rule: bool = False

    @field_validator("score")
    @classmethod
    def clean_score(cls, value: str | None):
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ScenarioRequest(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("scores")
    @classmethod
    def valid_scores(cls, value: dict[str, float]):
        if any(score < 0 or score > 100 for score in value.values()):
            raise ValueError("情景成绩必须在 0 到 100 之间")
        return value


class SchoolLoginRequest(BaseModel):
    flow_id: str = Field(min_length=20, max_length=200)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    captcha: str | None = Field(default=None, max_length=32)

    @field_validator("username", "captcha")
    @classmethod
    def strip_login_fields(cls, value: str | None):
        return value.strip() if value is not None else value


class SchoolSyncRequest(BaseModel):
    terms: list[str] = Field(default_factory=lambda: list(DEFAULT_TERMS), max_length=12)

    @field_validator("terms")
    @classmethod
    def unique_terms(cls, value: list[str]):
        cleaned = list(dict.fromkeys(term.strip() for term in value))
        if not cleaned:
            raise ValueError("至少选择一个学期")
        return cleaned


class RuleSelectionRequest(BaseModel):
    rule_id: str = Field(min_length=3, max_length=120)


class ComprehensiveSettingsRequest(BaseModel):
    use_current_gpa: bool = True
    manual_base_gpa: float | None = Field(default=None, ge=0, le=4)


class ComprehensiveItemRequest(BaseModel):
    kind: str = Field(min_length=3, max_length=64)
    values: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=500)

    @field_validator("kind", "note")
    @classmethod
    def clean_comprehensive_text(cls, value: str):
        return value.strip()


async def _school_session(request: Request):
    return await buaa_sessions.get_session(request.cookies.get(SESSION_COOKIE))


async def _local_user_id(request: Request) -> int:
    session = await _school_session(request)
    if session:
        return session.local_user_id
    return resolve_app_session(request.cookies.get(APP_SESSION_COOKIE)) or 1


async def _require_account(request: Request) -> int:
    user_id = await _local_user_id(request)
    if user_id == 1:
        raise HTTPException(
            status_code=401,
            detail={"code": "account_required", "message": "请先登录学校账户"},
        )
    return user_id


def _upstream_http_error(exc: BuaaUpstreamError) -> HTTPException:
    status = 401 if isinstance(exc, BuaaAuthenticationError) else 502
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/v1/me")
async def me(request: Request):
    return current_user(await _local_user_id(request))


@app.get("/api/v1/dashboard")
async def dashboard(request: Request):
    user_id = await _local_user_id(request)
    return calculate_dashboard(list_courses(user_id), rule_id=get_selected_rule(user_id))


@app.get("/api/v1/analytics")
async def analytics(request: Request, target_gpa: float = 3.8):
    if target_gpa < 0 or target_gpa > 4:
        raise HTTPException(status_code=422, detail="目标 GPA 必须在 0 到 4 之间")
    return calculate_academic_analytics(
        list_courses(await _local_user_id(request)), target_gpa=target_gpa
    )


@app.get("/api/v1/competition-calendar")
def competition_calendar():
    return public_competition_calendar()


@app.get("/api/v1/courses")
async def courses(request: Request):
    user_id = await _local_user_id(request)
    return calculate_dashboard(list_courses(user_id), rule_id=get_selected_rule(user_id))["courses"]


@app.patch("/api/v1/courses/{course_id}")
async def patch_course(course_id: int, payload: CoursePatch, request: Request):
    user_id = await _local_user_id(request)
    try:
        score_to_grade_point(payload.score, payload.score_scale)
        update_course(
            course_id,
            payload.score,
            payload.score_scale,
            payload.selected_for_rule,
            user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="课程不存在")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "status": "updated",
        "dashboard": calculate_dashboard(
            list_courses(user_id), rule_id=get_selected_rule(user_id)
        ),
    }


@app.get("/api/v1/rules/default")
def default_rule():
    return public_rule()


@app.post("/api/v1/scenarios/calculate")
async def scenario(payload: ScenarioRequest, request: Request):
    user_id = await _local_user_id(request)
    return calculate_dashboard(
        list_courses(user_id), payload.scores, rule_id=get_selected_rule(user_id)
    )


@app.get("/api/v1/rules")
async def rules(request: Request):
    user_id = await _local_user_id(request)
    return {"items": list_public_rules(), "selectedRuleId": get_selected_rule(user_id)}


@app.get("/api/v1/rules/{rule_id}")
def rule_detail(rule_id: str):
    try:
        return public_rule(rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="计分规则不存在") from exc


@app.put("/api/v1/preferences/rule")
async def select_rule(payload: RuleSelectionRequest, request: Request):
    try:
        rule = public_rule(payload.rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="计分规则不存在") from exc
    user_id = await _local_user_id(request)
    set_selected_rule(user_id, payload.rule_id)
    return {
        "status": "selected",
        "rule": rule,
        "dashboard": calculate_dashboard(list_courses(user_id), rule_id=payload.rule_id),
    }


def _comprehensive_payload(user_id: int, editable: bool) -> dict:
    profile = get_comprehensive_profile(user_id)
    items = list_comprehensive_items(user_id)
    current_dashboard = calculate_dashboard(
        list_courses(user_id), rule_id=get_selected_rule(user_id)
    )
    current_gpa = current_dashboard["metrics"]["gpa"]
    base_gpa = current_gpa if profile["use_current_gpa"] else profile["manual_base_gpa"]
    return {
        "editable": editable,
        "rule": public_comprehensive_rule(),
        "profile": {
            "useCurrentGpa": profile["use_current_gpa"],
            "manualBaseGpa": profile["manual_base_gpa"],
            "currentRuleGpa": current_gpa,
        },
        "calculation": calculate_comprehensive(base_gpa, items),
    }


@app.get("/api/v1/comprehensive")
async def comprehensive(request: Request):
    user_id = await _local_user_id(request)
    return _comprehensive_payload(user_id, editable=user_id != 1)


@app.post("/api/v1/comprehensive/preview")
def comprehensive_preview(payload: ComprehensiveItemRequest):
    try:
        return evaluate_item(payload.kind, payload.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put("/api/v1/comprehensive/settings")
async def comprehensive_settings(payload: ComprehensiveSettingsRequest, request: Request):
    user_id = await _require_account(request)
    if not payload.use_current_gpa and payload.manual_base_gpa is None:
        raise HTTPException(status_code=422, detail="手动模式需要填写基础 GPA")
    update_comprehensive_profile(user_id, payload.use_current_gpa, payload.manual_base_gpa)
    return _comprehensive_payload(user_id, editable=True)


@app.post("/api/v1/comprehensive/items")
async def create_comprehensive_item(payload: ComprehensiveItemRequest, request: Request):
    user_id = await _require_account(request)
    try:
        item = prepare_comprehensive_item(payload.kind, payload.values, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_comprehensive_item(user_id, item)
    return _comprehensive_payload(user_id, editable=True)


@app.put("/api/v1/comprehensive/items/{item_id}")
async def edit_comprehensive_item(
    item_id: int, payload: ComprehensiveItemRequest, request: Request
):
    user_id = await _require_account(request)
    try:
        item = prepare_comprehensive_item(payload.kind, payload.values, payload.note)
        update_comprehensive_item(user_id, item_id, item)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="综测项目不存在") from exc
    return _comprehensive_payload(user_id, editable=True)


@app.delete("/api/v1/comprehensive/items/{item_id}")
async def remove_comprehensive_item(item_id: int, request: Request):
    user_id = await _require_account(request)
    try:
        delete_comprehensive_item(user_id, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="综测项目不存在") from exc
    return _comprehensive_payload(user_id, editable=True)


@app.get("/api/v1/export/courses.csv")
async def export_courses_csv(request: Request):
    user_id = await _require_account(request)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["课程代码", "课程名称", "学期", "学分", "成绩", "成绩制", "来源"])
    for course in list_courses(user_id):
        writer.writerow(
            [
                course.code,
                course.name,
                course.term_code,
                course.credits,
                course.score_text or "",
                course.score_scale,
                course.source,
            ]
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="student-helper-courses.csv"'},
    )


@app.get("/api/v1/export/data.json")
async def export_data_json(request: Request):
    user_id = await _require_account(request)
    return {
        "user": current_user(user_id),
        "selectedRuleId": get_selected_rule(user_id),
        "courses": [course.__dict__ for course in list_courses(user_id)],
        "comprehensive": _comprehensive_payload(user_id, editable=True),
    }


@app.get("/api/v1/integration/status")
async def integration_status(request: Request):
    session = await _school_session(request)
    persisted_user_id = resolve_app_session(request.cookies.get(APP_SESSION_COOKIE))
    user_id = session.local_user_id if session else (persisted_user_id or 1)
    user = current_user(user_id)
    local_authenticated = user_id != 1
    return {
        "mode": "school" if session else ("saved" if local_authenticated else "demo"),
        "authenticated": bool(session),
        "schoolAuthenticated": bool(session),
        "localAuthenticated": local_authenticated,
        "schoolLogin": "connected" if session else "not_connected",
        "passwordStored": False,
        "dataPersisted": True,
        "cookiePersistence": "local_session_30_days",
        "defaultTerms": list(DEFAULT_TERMS),
        "user": (
            {"name": user["name"], "studentId": user["studentId"]}
            if local_authenticated
            else None
        ),
        "sync": user.get("sync"),
        "upstream": {
            "gradeUrl": "https://app.buaa.edu.cn/buaascore/wap/default/index",
            "method": "POST",
            "fields": ["year", "xq"],
        },
        "message": (
            "已连接北航统一认证；数据已持久化，密码不会保存。"
            if session
            else (
                "已从本地数据库恢复个人数据；需要刷新学校成绩时再连接统一认证。"
                if local_authenticated
                else "当前显示脱敏演示数据，连接学校账户后可同步本人成绩。"
            )
        ),
    }


@app.post("/api/v1/integration/buaa/prelogin")
async def school_prelogin(response: Response):
    try:
        result = await buaa_sessions.preload()
    except BuaaUpstreamError as exc:
        raise _upstream_http_error(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@app.post("/api/v1/integration/buaa/login")
async def school_login(payload: SchoolLoginRequest, response: Response):
    try:
        token, session = await buaa_sessions.login(
            payload.flow_id,
            payload.username,
            payload.password,
            payload.captcha,
            upsert_school_user,
        )
    except BuaaUpstreamError as exc:
        raise _upstream_http_error(exc) from exc
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=os.getenv("STUDENT_HELPER_COOKIE_SECURE", "0") == "1",
        samesite="strict",
        max_age=8 * 60 * 60,
        path="/",
    )
    response.set_cookie(
        APP_SESSION_COOKIE,
        create_app_session(session.local_user_id),
        httponly=True,
        secure=os.getenv("STUDENT_HELPER_COOKIE_SECURE", "0") == "1",
        samesite="strict",
        max_age=APP_SESSION_MAX_AGE,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    saved_user = current_user(session.local_user_id)
    return {
        "status": "authenticated",
        "user": {"name": session.name, "studentId": session.student_id},
        "passwordStored": False,
        "hasSavedGrades": bool((saved_user.get("sync") or {}).get("last_sync_at")),
    }


@app.post("/api/v1/integration/buaa/sync")
async def school_sync(payload: SchoolSyncRequest, request: Request):
    session = await _school_session(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "请先连接北航统一认证"},
        )
    set_sync_state(session.local_user_id, "syncing", f"正在同步 {len(payload.terms)} 个学期。")
    grades_by_term: dict[str, list[dict]] = {}
    raw_by_term: dict[str, dict] = {}
    try:
        for term in payload.terms:
            grades, raw = await buaa_sessions.fetch_term(session, term)
            grades_by_term[term] = grades
            raw_by_term[term] = raw
    except BuaaSessionExpired as exc:
        set_sync_state(session.local_user_id, "session_expired", str(exc))
        raise _upstream_http_error(exc) from exc
    except BuaaUpstreamError as exc:
        set_sync_state(session.local_user_id, "sync_error", str(exc))
        raise _upstream_http_error(exc) from exc
    try:
        summary = sync_school_grades(session.local_user_id, grades_by_term, raw_by_term)
        dashboard = calculate_dashboard(
            list_courses(session.local_user_id),
            rule_id=get_selected_rule(session.local_user_id),
        )
    except Exception as exc:
        logger.exception("Failed to process synchronized grades for user_id=%s", session.local_user_id)
        set_sync_state(
            session.local_user_id,
            "sync_error",
            "成绩已读取，但本地处理失败；原始快照已保留。",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "local_grade_processing_error",
                "message": "成绩已读取，但本地处理失败；请升级后重试。",
            },
        ) from exc
    return {"status": "synced", "summary": summary, "dashboard": dashboard}


@app.post("/api/v1/integration/buaa/logout")
async def school_logout(request: Request, response: Response):
    await buaa_sessions.logout(request.cookies.get(SESSION_COOKIE))
    delete_app_session(request.cookies.get(APP_SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(APP_SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}


@app.post("/api/v1/session/logout")
async def account_logout(request: Request, response: Response):
    return await school_logout(request, response)
