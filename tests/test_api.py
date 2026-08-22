import requests

from fpl_toolkit.api import DraftApiClient, FPLApiError, FantasyApiClient


class _Response:
    def __init__(self, payload=None, status=200, json_error=None):
        self.payload = payload
        self.status_code = status
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def test_api_retries_a_transient_server_error(monkeypatch):
    responses = iter([_Response(status=503), _Response({"events": []})])
    calls = []
    monkeypatch.setattr("fpl_toolkit.api.requests.get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr("fpl_toolkit.api.time.sleep", calls.append)

    client = DraftApiClient(max_attempts=3, retry_backoff_seconds=0.25)

    assert client.bootstrap_static() == {"events": []}
    assert calls == [0.25]


def test_api_does_not_retry_an_invalid_json_payload(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "fpl_toolkit.api.requests.get",
        lambda *args, **kwargs: _Response(json_error=ValueError("invalid JSON")),
    )
    monkeypatch.setattr("fpl_toolkit.api.time.sleep", calls.append)

    client = DraftApiClient(max_attempts=3)

    try:
        client.bootstrap_static()
    except FPLApiError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("Invalid JSON should fail the collection")
    assert calls == []


def test_api_exhausts_retries_with_exponential_backoff(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "fpl_toolkit.api.requests.get",
        lambda *args, **kwargs: _Response(status=503),
    )
    monkeypatch.setattr("fpl_toolkit.api.time.sleep", calls.append)

    client = DraftApiClient(max_attempts=3, retry_backoff_seconds=0.5)

    try:
        client.bootstrap_static()
    except FPLApiError as exc:
        assert "after 3 attempt(s)" in str(exc)
    else:
        raise AssertionError("Repeated server failures should fail the collection")
    assert calls == [0.5, 1.0]


def test_standard_fpl_client_uses_public_read_only_endpoints(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/bootstrap-static/"):
            return _Response({"events": [], "elements": []})
        if url.endswith("/fixtures/"):
            return _Response([])
        if url.endswith("/entry/123/event/1/picks/"):
            return _Response({"picks": []})
        if url.endswith("/entry/123/history/"):
            return _Response({"current": []})
        if url.endswith("/entry/123/transfers/"):
            return _Response([])
        return _Response({"id": 123})

    monkeypatch.setattr("fpl_toolkit.api.requests.get", fake_get)
    client = FantasyApiClient(max_attempts=1)

    assert client.bootstrap_static()["events"] == []
    assert client.fixtures() == []
    assert client.entry("123")["id"] == 123
    assert client.entry_picks("123", 1) == {"picks": []}
    assert client.entry_history("123") == {"current": []}
    assert client.entry_transfers("123") == []
    assert calls == [
        "https://fantasy.premierleague.com/api/bootstrap-static/",
        "https://fantasy.premierleague.com/api/fixtures/",
        "https://fantasy.premierleague.com/api/entry/123/",
        "https://fantasy.premierleague.com/api/entry/123/event/1/picks/",
        "https://fantasy.premierleague.com/api/entry/123/history/",
        "https://fantasy.premierleague.com/api/entry/123/transfers/",
    ]
