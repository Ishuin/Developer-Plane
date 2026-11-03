import pytest
from fastapi.testclient import TestClient

from dcp.agents.base import AgentUnavailable
from dcp.api import create_app
from dcp.config import Settings
from dcp.envfile import load_env_file, write_env_values
from dcp.llm import build_chat_model


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "llm.db"),
        env_file=str(tmp_path / ".env"),
        ai_enabled=False, llm_api_key="", llm_model="", llm_provider="openai",
    )
    with TestClient(create_app(settings)) as c:
        yield c, tmp_path / ".env"


def _payload(**over):
    body = {"provider": "anthropic", "model": "claude-sonnet-5-5",
            "api_key": "sk-ant-secret-1234", "enabled": True}
    body.update(over)
    return body


def test_update_masks_key_and_persists_env(client):
    c, env_path = client
    view = c.put("/api/settings/llm", json=_payload()).json()
    assert view["has_key"] and view["key_hint"] == "…1234"
    assert "sk-ant-secret" not in str(view)
    assert "sk-ant-secret" not in str(c.get("/api/settings/llm").json())
    text = env_path.read_text()
    assert "DCP_LLM_PROVIDER=anthropic" in text and "DCP_LLM_API_KEY=sk-ant-secret-1234" in text


def test_blank_key_keeps_existing(client):
    c, _ = client
    c.put("/api/settings/llm", json=_payload())
    view = c.put("/api/settings/llm", json=_payload(api_key=None, model="other")).json()
    assert view["has_key"] and view["model"] == "other"


@pytest.mark.parametrize("bad", [
    {"provider": "cohere"}, {"model": "  "}, {"api_base": "ftp://x"},
])
def test_validation_rejects_bad_input(client, bad):
    c, _ = client
    assert c.put("/api/settings/llm", json=_payload(**bad)).status_code == 422


def test_connection_test_requires_config(client):
    c, _ = client
    assert c.post("/api/settings/llm/test").status_code == 400


def test_connection_test_redacts_key(client, monkeypatch):
    c, _ = client
    c.put("/api/settings/llm", json=_payload())

    def boom(_settings):
        raise RuntimeError("401 bad key sk-ant-secret-1234")

    monkeypatch.setattr("dcp.api.routes.llm_settings.check_connection", boom)
    res = c.post("/api/settings/llm/test")
    assert res.status_code == 502 and "sk-ant-secret" not in res.json()["detail"]


def test_build_chat_model_requires_credentials():
    with pytest.raises(AgentUnavailable):
        build_chat_model(Settings(ai_enabled=True, llm_api_key="", llm_model=""))
    with pytest.raises(AgentUnavailable):
        build_chat_model(Settings(ai_enabled=True, llm_api_key="k", llm_model="m",
                                  llm_provider="bogus"))


def test_env_file_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# keep me\nOTHER=1\nDCP_LLM_MODEL=old\n")
    write_env_values(path, {"DCP_LLM_MODEL": "new", "DCP_LLM_PROVIDER": "openai"})
    text = path.read_text()
    assert "# keep me" in text and "OTHER=1" in text and "DCP_LLM_MODEL=new" in text
    monkeypatch.delenv("DCP_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DCP_LLM_MODEL", "from-shell")
    load_env_file(path)
    import os
    assert os.environ["DCP_LLM_PROVIDER"] == "openai"
    assert os.environ["DCP_LLM_MODEL"] == "from-shell"
    monkeypatch.delenv("DCP_LLM_PROVIDER", raising=False)


def test_endpoint_change_requires_key_reentry(client):
    c, _ = client
    c.put("/api/settings/llm", json=_payload())
    res = c.put("/api/settings/llm", json=_payload(api_key=None, api_base="https://evil.example"))
    assert res.status_code == 400
    res = c.put("/api/settings/llm", json=_payload(api_key=None, provider="openai"))
    assert res.status_code == 400


def test_newline_injection_rejected(client, tmp_path):
    c, env_path = client
    res = c.put("/api/settings/llm", json=_payload(model="m\nDCP_AGENT_CMD=calc"))
    assert res.status_code == 422
    assert not env_path.exists() or "DCP_AGENT_CMD" not in env_path.read_text()
    with pytest.raises(ValueError):
        write_env_values(tmp_path / "x.env", {"DCP_LLM_MODEL": "a\nB=1"})


def test_loader_ignores_non_dcp_keys(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("PATH_X_EVIL=1\nDCP_OK_TEST=1\n")
    monkeypatch.delenv("PATH_X_EVIL", raising=False)
    monkeypatch.delenv("DCP_OK_TEST", raising=False)
    load_env_file(path)
    import os
    assert "PATH_X_EVIL" not in os.environ and os.environ["DCP_OK_TEST"] == "1"
    monkeypatch.delenv("DCP_OK_TEST", raising=False)
