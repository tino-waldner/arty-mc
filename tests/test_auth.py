import requests  # type: ignore

from arty_mc.auth import AuthSession  # type: ignore


def test_auth_session_init():
    auth = AuthSession("https://example.com/", "user", "token")
    assert auth.base == "https://example.com"
    assert auth.session.auth == ("user", "token")


def test_get_request(requests_mock):
    base = "https://example.com"
    url = "/api/test"
    requests_mock.get(base + url, json={"status": "ok"})
    auth = AuthSession(base, "user", "token")
    result = auth.get(url)
    assert result["status"] == "ok"


def test_post_request(requests_mock):
    base = "https://example.com"
    url = "/api/upload"
    requests_mock.post(base + url, json={"result": "success"})
    auth = AuthSession(base, "user", "token")
    result = auth.post(url, {"file": "data"})
    assert result["result"] == "success"


def test_get_request_error(requests_mock):
    base = "https://example.com"
    url = "/api/error"
    requests_mock.get(base + url, status_code=500)
    auth = AuthSession(base, "user", "token")
    try:
        auth.get(url)
        assert False, "Expected HTTPError"
    except requests.exceptions.HTTPError:
        assert True
