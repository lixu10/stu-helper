from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.course_matching import build_school_course_key


logger = logging.getLogger(__name__)
SSO_LOGIN_URL = "https://sso.buaa.edu.cn/login"
SSO_LOGOUT_URL = "https://sso.buaa.edu.cn/logout"
SSO_CAPTCHA_URL = "https://sso.buaa.edu.cn/captcha"
UC_LOGIN_URL = (
    "https://uc.buaa.edu.cn/api/login?"
    "target=https%3A%2F%2Fuc.buaa.edu.cn%2F%23%2Fuser%2Flogin"
)
UC_STATUS_URL = "https://uc.buaa.edu.cn/api/uc/status"
GRADE_URL = "https://app.buaa.edu.cn/buaascore/wap/default/index"

DEFAULT_TERMS = (
    "2024-2025-1",
    "2024-2025-2",
    "2024-2025-3",
    "2025-2026-1",
    "2025-2026-2",
    "2025-2026-3",
    "2026-2027-1",
    "2026-2027-2",
)

SESSION_COOKIE = "student_helper_session"
FLOW_TTL = timedelta(minutes=10)
SESSION_IDLE_TTL = timedelta(hours=8)


class BuaaUpstreamError(RuntimeError):
    def __init__(self, message: str, code: str = "upstream_error"):
        super().__init__(message)
        self.code = code


class BuaaAuthenticationError(BuaaUpstreamError):
    pass


class BuaaSessionExpired(BuaaAuthenticationError):
    def __init__(self, message: str = "学校登录状态已过期，请重新登录"):
        super().__init__(message, "session_expired")


def extract_execution(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    field = soup.select_one('input[name="execution"]')
    return str(field.get("value", "")).strip() if field else ""


def detect_captcha_id(html: str) -> str | None:
    match = re.search(
        r"config\.captcha\s*=\s*\{.*?id\s*:\s*['\"]([^'\"]+)['\"]",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else None


def find_login_error(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    selectors = (
        "div.alert.alert-danger#errorDiv p",
        "div.alert.alert-danger#errorDiv",
        "div.errors",
        "p.errors",
        "span.errors",
        ".tip-text",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if node and node.get_text(" ", strip=True):
            return node.get_text(" ", strip=True)
    return None


def is_password_expiry_page(html: str) -> bool:
    return bool(extract_execution(html)) and any(
        marker in html for marker in ("continueForm", "ignoreAndContinue", "账号存在安全风险", "密码过期")
    )


def build_login_form(html: str, username: str, password: str, captcha: str | None) -> tuple[str, dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#fm1") or soup.select_one("form[action]")
    action = str(form.get("action", SSO_LOGIN_URL)) if form else SSO_LOGIN_URL
    fields: dict[str, str] = {}
    if form:
        for item in form.select("input[name]"):
            name = str(item.get("name", "")).strip()
            input_type = str(item.get("type", "")).lower()
            if not name or input_type in {"submit", "button", "image"}:
                continue
            if input_type == "checkbox" and not item.has_attr("checked"):
                continue
            fields[name] = str(item.get("value", ""))

    fields.update({"username": username, "password": password, "submit": "登录"})
    fields.setdefault("type", "username_password")
    fields.setdefault("_eventId", "submit")
    execution = extract_execution(html)
    if execution:
        fields["execution"] = execution
    if captcha:
        # Different SSO page versions have used either or both names.
        fields["captcha"] = captcha
        fields["captchaResponse"] = captcha
    return urljoin(SSO_LOGIN_URL, action), fields


def infer_score_scale(score: Any, score_type: str | None = None) -> str:
    type_text = (score_type or "").strip()
    score_text = "" if score is None else str(score).strip()
    if score_text in {"优秀", "良好", "中等", "及格", "不及格"}:
        return "five_level"
    if score_text in {"通过", "不通过", "合格", "不合格"}:
        return "pass_fail"
    try:
        numeric_score = float(score_text)
        if 0 <= numeric_score <= 100:
            # Real BUAA data can label a numeric mark as 五级制 (e.g. 军事技能=90).
            # The displayed score is the strongest signal and remains auditable in raw snapshots.
            return "percentage"
    except (TypeError, ValueError):
        pass
    if "百分" in type_text:
        return "percentage"
    if "五级" in type_text:
        return "five_level"
    if any(token in type_text for token in ("二级", "通过", "合格")):
        return "pass_fail"
    # Unknown textual systems are excluded from GPA until manually confirmed.
    return "pass_fail"


def normalize_grade(term_code: str, raw: dict[str, Any], upstream_key: str = "") -> dict[str, Any]:
    name = str(raw.get("kcmc") or "未知课程").strip()
    code = str(raw.get("kch") or "").strip()
    credit_value = raw.get("xf")
    try:
        credits = float(credit_value)
    except (TypeError, ValueError):
        credits = 0.0
    score_value = raw.get("kccj")
    score = None if score_value is None or str(score_value).strip() == "" else str(score_value).strip()
    score_type = str(raw.get("fslx") or "").strip()
    # The API dictionary/list key is only a response position and changes when
    # courses are reordered. It must not participate in the persisted identity.
    school_key = build_school_course_key(term_code, code, name, credits)
    return {
        "school_key": school_key,
        "term_code": term_code,
        "code": code,
        "name": name,
        "credits": credits,
        "score": score,
        "score_scale": infer_score_scale(score, score_type),
        "score_type": score_type,
        "course_type": str(raw.get("kclx") or "").strip(),
        "raw": raw,
    }


def is_session_expired(response: httpx.Response, body: str) -> bool:
    final_url = str(response.url).lower()
    return (
        response.status_code == 401
        or "sso.buaa.edu.cn/login" in final_url
        or ("d.buaa.edu.cn" in final_url and "/login" in final_url)
        or 'name="execution"' in body.lower()
        or "统一身份认证" in body
    )


@dataclass
class LoginFlow:
    client: httpx.AsyncClient
    login_html: str
    captcha_id: str | None
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + FLOW_TTL)


@dataclass
class SchoolSession:
    client: httpx.AsyncClient
    username: str
    student_id: str
    name: str
    local_user_id: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class BuaaSessionManager:
    """Keeps upstream cookie jars in memory; passwords and cookies never enter SQLite."""

    def __init__(self, client_factory: Callable[[], httpx.AsyncClient] | None = None):
        self._client_factory = client_factory or self._new_client
        self._flows: dict[str, LoginFlow] = {}
        self._sessions: dict[str, SchoolSession] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _new_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=False,
            # Local proxy variables are frequently injected by IDEs and sandboxes.
            # BUAA SSO is public HTTPS, so direct access is safer unless explicitly enabled.
            trust_env=os.getenv("STUDENT_HELPER_TRUST_ENV", "0") == "1",
            headers={
                "User-Agent": "StudentHelper/1.0 (+local authorized BUAA student client)",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            },
        )

    async def _discard_expired(self) -> None:
        now = datetime.now(UTC)
        stale_flows = [key for key, value in self._flows.items() if value.expires_at <= now]
        stale_sessions = [
            key for key, value in self._sessions.items() if value.last_seen_at + SESSION_IDLE_TTL <= now
        ]
        for key in stale_flows:
            await self._flows.pop(key).client.aclose()
        for key in stale_sessions:
            await self._sessions.pop(key).client.aclose()

    async def preload(self) -> dict[str, Any]:
        async with self._lock:
            await self._discard_expired()
        client = self._client_factory()
        try:
            response = await client.get(SSO_LOGIN_URL)
            response = await self._follow_redirects(client, response)
            response.raise_for_status()
            html = response.text
            execution = extract_execution(html)
            if not execution:
                raise BuaaUpstreamError("未能读取统一认证登录上下文，请稍后重试", "login_context_missing")
            captcha_id = detect_captcha_id(html)
            captcha_image = None
            if captcha_id:
                captcha_response = await client.get(SSO_CAPTCHA_URL, params={"captchaId": captcha_id})
                captcha_response.raise_for_status()
                mime = captcha_response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
                captcha_image = f"data:{mime};base64," + base64.b64encode(captcha_response.content).decode()
            flow_id = secrets.token_urlsafe(32)
            async with self._lock:
                self._flows[flow_id] = LoginFlow(client, html, captcha_id)
            return {
                "flowId": flow_id,
                "captchaRequired": bool(captcha_id),
                "captchaImage": captcha_image,
                "expiresIn": int(FLOW_TTL.total_seconds()),
            }
        except BuaaUpstreamError:
            await client.aclose()
            raise
        except (httpx.HTTPError, ValueError) as exc:
            await client.aclose()
            logger.warning("BUAA SSO preload failed: %s: %s", type(exc).__name__, exc)
            raise BuaaUpstreamError("无法连接北航统一认证，请检查网络或稍后重试", "sso_unavailable") from exc

    async def login(
        self,
        flow_id: str,
        username: str,
        password: str,
        captcha: str | None,
        local_user_factory: Callable[[str, str], int],
    ) -> tuple[str, SchoolSession]:
        async with self._lock:
            await self._discard_expired()
            flow = self._flows.pop(flow_id, None)
        if not flow or flow.expires_at <= datetime.now(UTC):
            if flow:
                await flow.client.aclose()
            raise BuaaAuthenticationError("登录上下文已过期，请刷新验证码后重试", "login_flow_expired")
        if flow.captcha_id and not (captcha or "").strip():
            await flow.client.aclose()
            raise BuaaAuthenticationError("请输入验证码", "captcha_required")

        client = flow.client
        try:
            submit_url, fields = build_login_form(flow.login_html, username, password, captcha)
            response = await client.post(submit_url, data=fields)
            response = await self._follow_redirects(client, response)
            body = response.text

            if is_password_expiry_page(body):
                execution = extract_execution(body)
                response = await client.post(
                    str(response.url).split("?", 1)[0],
                    data={"execution": execution, "_eventId": "ignoreAndContinue"},
                )
                response = await self._follow_redirects(client, response)
                body = response.text

            error = find_login_error(body)
            if error or extract_execution(body) or response.status_code == 401:
                raise BuaaAuthenticationError(
                    error or "账号、密码或验证码错误",
                    "invalid_credentials",
                )

            await client.get(UC_LOGIN_URL, follow_redirects=True)
            status_response = await client.get(
                UC_STATUS_URL,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                },
                follow_redirects=True,
            )
            status_response.raise_for_status()
            payload = status_response.json()
            user_data = payload.get("data") if payload.get("code") == 0 else None
            student_id = str((user_data or {}).get("schoolid") or "").strip()
            name = str((user_data or {}).get("name") or "").strip()
            if not student_id:
                raise BuaaAuthenticationError("统一认证成功，但未能验证学生身份", "identity_unavailable")

            local_user_id = local_user_factory(student_id, name or username)
            token = secrets.token_urlsafe(48)
            session = SchoolSession(client, username, student_id, name or username, local_user_id)
            async with self._lock:
                self._sessions[token] = session
            return token, session
        except BuaaUpstreamError:
            await client.aclose()
            raise
        except (httpx.HTTPError, ValueError) as exc:
            await client.aclose()
            raise BuaaUpstreamError("学校认证服务响应异常，请稍后重试", "sso_response_error") from exc

    async def get_session(self, token: str | None) -> SchoolSession | None:
        if not token:
            return None
        async with self._lock:
            await self._discard_expired()
            session = self._sessions.get(token)
            if session:
                session.last_seen_at = datetime.now(UTC)
            return session

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        async with self._lock:
            session = self._sessions.pop(token, None)
        if not session:
            return
        try:
            await session.client.get(SSO_LOGOUT_URL, follow_redirects=True)
        except httpx.HTTPError:
            pass
        finally:
            await session.client.aclose()

    async def fetch_term(self, session: SchoolSession, term_code: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        match = re.fullmatch(r"(\d{4}-\d{4})-([123])", term_code.strip())
        if not match:
            raise BuaaUpstreamError(f"不支持的学期代码：{term_code}", "invalid_term")
        year, semester = match.groups()
        activation = await session.client.get(
            GRADE_URL,
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            follow_redirects=True,
        )
        activation_body = activation.text
        if is_session_expired(activation, activation_body):
            raise BuaaSessionExpired()
        if activation.status_code != 200:
            raise BuaaUpstreamError("成绩应用激活失败", "grade_activation_failed")

        response = await session.client.post(
            GRADE_URL,
            data={"year": year, "xq": semester},
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": GRADE_URL,
            },
            follow_redirects=True,
        )
        body = response.text
        if is_session_expired(response, body):
            raise BuaaSessionExpired()
        if response.status_code != 200:
            raise BuaaUpstreamError(f"成绩查询失败（HTTP {response.status_code}）", "grade_http_error")
        try:
            payload = response.json()
        except ValueError as exc:
            raise BuaaUpstreamError("成绩接口返回了无法识别的数据", "grade_parse_error") from exc
        if payload.get("e") != 0:
            raise BuaaUpstreamError(str(payload.get("m") or "成绩接口返回业务错误"), "grade_business_error")
        data = payload.get("d") or {}
        if isinstance(data, dict):
            rows = [normalize_grade(term_code, row, str(key)) for key, row in data.items() if isinstance(row, dict)]
        elif isinstance(data, list):
            rows = [normalize_grade(term_code, row, str(index)) for index, row in enumerate(data) if isinstance(row, dict)]
        else:
            raise BuaaUpstreamError("成绩接口数据结构已变化", "grade_contract_changed")
        return rows, payload

    async def close_all(self) -> None:
        async with self._lock:
            clients = [flow.client for flow in self._flows.values()] + [
                session.client for session in self._sessions.values()
            ]
            self._flows.clear()
            self._sessions.clear()
        await asyncio.gather(*(client.aclose() for client in clients), return_exceptions=True)

    @staticmethod
    async def _follow_redirects(
        client: httpx.AsyncClient, response: httpx.Response, maximum: int = 12
    ) -> httpx.Response:
        current = response
        for _ in range(maximum):
            if current.status_code not in {301, 302, 303, 307, 308}:
                return current
            location = current.headers.get("location")
            if not location:
                return current
            current = await client.get(urljoin(str(current.url), location))
        raise BuaaUpstreamError("统一认证重定向次数过多", "too_many_redirects")


buaa_sessions = BuaaSessionManager()
