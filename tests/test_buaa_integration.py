import asyncio
from urllib.parse import parse_qs

import httpx

from app.integrations.buaa import (
    BuaaSessionManager,
    build_login_form,
    detect_captcha_id,
    extract_execution,
    infer_score_scale,
    normalize_grade,
)


LOGIN_HTML = """
<html><body>
  <form id="fm1" action="/login">
    <input type="hidden" name="execution" value="e1s1">
    <input type="hidden" name="type" value="username_password">
    <input name="username"><input type="password" name="password">
  </form>
</body></html>
"""


def test_login_page_parser_preserves_hidden_fields_and_overrides_credentials():
    action, fields = build_login_form(LOGIN_HTML, "24370001", "secret", None)
    assert action == "https://sso.buaa.edu.cn/login"
    assert fields["execution"] == "e1s1"
    assert fields["username"] == "24370001"
    assert fields["password"] == "secret"
    assert extract_execution(LOGIN_HTML) == "e1s1"


def test_captcha_and_score_type_contracts():
    html = "<script>config.captcha = { type: 'image', id: 'captcha-42' };</script>"
    assert detect_captcha_id(html) == "captcha-42"
    assert infer_score_scale("95", "百分制") == "percentage"
    assert infer_score_scale("90", "五级制") == "percentage"
    assert infer_score_scale("良好", "五级制") == "five_level"
    assert infer_score_scale("通过", "二级制") == "pass_fail"


def test_normalize_grade_keeps_upstream_fields_and_stable_key():
    raw = {
        "kcmc": "算法分析与设计",
        "kch": "B210031004",
        "xf": "3.0",
        "kccj": "91",
        "fslx": "百分制",
        "kclx": "必修",
    }
    first = normalize_grade("2025-2026-1", raw, "1")
    second = normalize_grade("2025-2026-1", raw, "99")
    assert first["credits"] == 3
    assert first["score"] == "91"
    assert first["score_scale"] == "percentage"
    assert first["school_key"] == second["school_key"]


def test_login_and_grade_sync_contract_without_retaining_password():
    seen = {"login_form": None, "grade_form": None}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and url == "https://sso.buaa.edu.cn/login":
            return httpx.Response(200, text=LOGIN_HTML)
        if request.method == "POST" and url == "https://sso.buaa.edu.cn/login":
            seen["login_form"] = parse_qs(request.content.decode())
            return httpx.Response(302, headers={"Location": "https://uc.buaa.edu.cn/landing"})
        if request.method == "GET" and url == "https://uc.buaa.edu.cn/landing":
            return httpx.Response(200, text="ok")
        if request.method == "GET" and url.startswith("https://uc.buaa.edu.cn/api/login?"):
            return httpx.Response(200, json={"code": 0})
        if request.method == "GET" and url == "https://uc.buaa.edu.cn/api/uc/status":
            return httpx.Response(200, json={"code": 0, "data": {"name": "Alice", "schoolid": "24370001"}})
        if request.method == "GET" and url == "https://app.buaa.edu.cn/buaascore/wap/default/index":
            return httpx.Response(200, text="<html>score home</html>")
        if request.method == "POST" and url == "https://app.buaa.edu.cn/buaascore/wap/default/index":
            seen["grade_form"] = parse_qs(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "e": 0,
                    "m": "",
                    "d": {
                        "1": {
                            "kcmc": "算法分析与设计",
                            "kch": "B210031004",
                            "xf": "3.0",
                            "kccj": "95",
                            "fslx": "百分制",
                            "kclx": "必修",
                        }
                    },
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {url}")

    transport = httpx.MockTransport(handler)
    manager = BuaaSessionManager(
        client_factory=lambda: httpx.AsyncClient(transport=transport, follow_redirects=False)
    )

    async def exercise():
        flow = await manager.preload()
        token, session = await manager.login(
            flow["flowId"], "24370001", "do-not-store", None, lambda _sid, _name: 7
        )
        rows, _ = await manager.fetch_term(session, "2025-2026-1")
        assert await manager.get_session(token) is session
        assert not hasattr(session, "password")
        assert rows[0]["code"] == "B210031004"
        await manager.close_all()

    asyncio.run(exercise())
    assert seen["login_form"]["password"] == ["do-not-store"]
    assert seen["grade_form"] == {"year": ["2025-2026"], "xq": ["1"]}
