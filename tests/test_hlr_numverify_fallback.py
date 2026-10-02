import requests


def test_numverify_105_does_not_retry_over_http(monkeypatch):
    from modules.hlr_lookup import HLRLookup

    monkeypatch.delenv("NUMVERIFY_ALLOW_HTTP", raising=False)
    calls = []

    class MockResp:
        status_code = 200

        def json(self):
            return {"success": False, "error": {"code": 105, "type": "https_access_restricted"}}

    def mock_get(url, *args, **kwargs):
        calls.append(url)
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_get)
    hlr = HLRLookup()
    hlr.api_key = "test-key"
    result = hlr.validate_phone("+14155552671")
    assert calls == ["https://apilayer.net/api/validate"]
    assert result["valid"] is True
    assert result["numverify_error"] == "HTTPS not available on this plan"
    assert "transport" not in result


def test_numverify_105_http_fallback_is_opt_in(monkeypatch):
    from modules.hlr_lookup import HLRLookup

    monkeypatch.setenv("NUMVERIFY_ALLOW_HTTP", "1")
    calls = []

    class MockResp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, *args, **kwargs):
        calls.append(url)
        if url.startswith("https://"):
            return MockResp({"success": False, "error": {"code": 105, "type": "https_access_restricted"}})
        return MockResp({
            "valid": True,
            "country_code": "US",
            "country_name": "United States",
            "location": "Novato",
            "carrier": "Example Mobile",
            "line_type": "mobile",
        })

    monkeypatch.setattr(requests, "get", mock_get)
    hlr = HLRLookup()
    hlr.api_key = "test-key"
    result = hlr.validate_phone("+14155552671")
    assert calls == [
        "https://apilayer.net/api/validate",
        "http://apilayer.net/api/validate",
    ]
    assert result["transport"] == "http"
    assert result["carrier"] == "Example Mobile"
    assert "numverify_error" not in result


def test_numverify_timeout_records_reason(monkeypatch):
    from modules.hlr_lookup import HLRLookup

    monkeypatch.delenv("NUMVERIFY_ALLOW_HTTP", raising=False)

    def mock_get(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", mock_get)
    hlr = HLRLookup()
    hlr.api_key = "test-key"
    result = hlr.validate_phone("+14155552671")
    assert result["valid"] is True
    assert result["numverify_error"] == "timeout"
    assert result["country_code"] == "US"
