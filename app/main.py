from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.calculation import calculate_dashboard, score_to_grade_point
from app.database import (
    current_user,
    get_selected_rule,
    init_database,
    list_courses,
    set_sync_state,
    set_selected_rule,
    sync_school_grades,
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield
    await buaa_sessions.close_all()


app = FastAPI(
    title="Student Helper",
    version="1.0.0",
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


async def _school_session(request: Request):
    return await buaa_sessions.get_session(request.cookies.get(SESSION_COOKIE))


async def _local_user_id(request: Request) -> int:
    session = await _school_session(request)
    return session.local_user_id if session else 1


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


@app.get("/api/v1/integration/status")
async def integration_status(request: Request):
    session = await _school_session(request)
    user = current_user(session.local_user_id if session else 1)
    return {
        "mode": "school" if session else "demo",
        "authenticated": bool(session),
        "schoolLogin": "connected" if session else "not_connected",
        "passwordStored": False,
        "cookiePersistence": "memory_only",
        "defaultTerms": list(DEFAULT_TERMS),
        "user": (
            {"name": session.name, "studentId": session.student_id} if session else None
        ),
        "sync": user.get("sync"),
        "upstream": {
            "gradeUrl": "https://app.buaa.edu.cn/buaascore/wap/default/index",
            "method": "POST",
            "fields": ["year", "xq"],
        },
        "message": (
            "已连接北航统一认证；学校 Cookie 只保存在当前服务进程内。"
            if session
            else "当前显示脱敏演示数据，连接学校账户后可同步本人成绩。"
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
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "authenticated",
        "user": {"name": session.name, "studentId": session.student_id},
        "passwordStored": False,
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
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}
