from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.console.app import create_app
from aitest_kit.console.files import env_secret_values


HEADERS = {"X-AITest-Console-Token": "console-token"}


def _client(root: Path) -> TestClient:
    return TestClient(create_app(initial_workspace=root, token="console-token"))


def test_source_file_read_and_hash_guarded_save(console_workspace: Path):
    client = _client(console_workspace)
    path = "test_workspace/suites/demo/orders_smoke/business.md"
    loaded = client.get("/api/files", params={"path": path}, headers=HEADERS)

    assert loaded.status_code == 200
    assert loaded.json()["owner"] == "CASE"
    assert loaded.json()["read_only"] is False

    saved = client.put(
        "/api/files",
        headers=HEADERS,
        json={"path": path, "content": loaded.json()["content"] + "\n新增说明\n", "sha256": loaded.json()["sha256"]},
    )
    assert saved.status_code == 200, saved.text

    conflict = client.put(
        "/api/files",
        headers=HEADERS,
        json={"path": path, "content": "stale", "sha256": loaded.json()["sha256"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "FILE_CONFLICT"


def test_generated_and_reports_are_read_only(console_workspace: Path):
    client = _client(console_workspace)
    for path in (
        "test_workspace/generated/demo/test_business.py",
        "test_workspace/reports/demo/orders/runs/run-1/result.json",
    ):
        loaded = client.get("/api/files", params={"path": path}, headers=HEADERS)
        assert loaded.status_code == 200
        assert loaded.json()["read_only"] is True
        saved = client.put(
            "/api/files",
            headers=HEADERS,
            json={"path": path, "content": "changed", "sha256": loaded.json()["sha256"]},
        )
        assert saved.status_code == 403
        assert saved.json()["error"]["code"] == "FILE_READ_ONLY"


def test_configured_generated_directory_is_read_only(console_workspace: Path):
    config = console_workspace / "aitest_config" / "aitest.yaml"
    config.write_text(
        """workspace:
  paths:
    generated_dir: custom/generated
    reports_dir: test_workspace/reports
""",
        encoding="utf-8",
    )
    generated = console_workspace / "custom" / "generated" / "test_custom.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("def test_custom():\n    pass\n", encoding="utf-8")
    client = _client(console_workspace)

    loaded = client.get("/api/files", params={"path": "custom/generated/test_custom.py"}, headers=HEADERS)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["owner"] == "GENERATED"
    assert loaded.json()["read_only"] is True

    saved = client.put(
        "/api/files",
        headers=HEADERS,
        json={
            "path": "custom/generated/test_custom.py",
            "content": "changed\n",
            "sha256": loaded.json()["sha256"],
        },
    )
    assert saved.status_code == 403
    assert saved.json()["error"]["code"] == "FILE_READ_ONLY"


def test_path_traversal_and_env_through_normal_file_api_are_rejected(console_workspace: Path):
    client = _client(console_workspace)

    traversal = client.get("/api/files", params={"path": "../secret.txt"}, headers=HEADERS)
    assert traversal.status_code == 403
    assert traversal.json()["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"

    env = client.get("/api/files", params={"path": ".env"}, headers=HEADERS)
    assert env.status_code == 403
    assert env.json()["error"]["code"] == "ENV_ACCESS_REQUIRED"


def test_git_metadata_is_outside_console_asset_scope(console_workspace: Path):
    git_dir = console_workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")

    response = _client(console_workspace).get("/api/files", params={"path": ".git/config"}, headers=HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PATH_NOT_ALLOWED"


def test_symlink_cannot_escape_workspace(console_workspace: Path, tmp_path: Path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret outside workspace\n", encoding="utf-8")
    link = console_workspace / "docs" / "escape.md"
    link.parent.mkdir()
    link.symlink_to(outside)

    response = _client(console_workspace).get("/api/files", params={"path": "docs/escape.md"}, headers=HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_env_is_masked_by_default_and_requires_explicit_reveal(console_workspace: Path):
    client = _client(console_workspace)
    metadata = client.get("/api/environment", headers=HEADERS)

    assert metadata.status_code == 200
    text = metadata.text
    assert "DEMO_TOKEN" in text
    assert "local-secret" not in text

    denied = client.post(
        "/api/environment/reveal", headers=HEADERS, json={"path": ".env", "confirmed": False}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ENV_ACCESS_REQUIRED"

    revealed = client.post(
        "/api/environment/reveal", headers=HEADERS, json={"path": ".env", "confirmed": True}
    )
    assert revealed.status_code == 200
    assert revealed.json()["content"] == "DEMO_TOKEN=local-secret\n"
    assert revealed.headers["cache-control"] == "no-store"


def test_env_save_validates_syntax_and_preserves_mode(console_workspace: Path):
    env_path = console_workspace / ".env"
    env_path.chmod(0o640)
    client = _client(console_workspace)
    revealed = client.post(
        "/api/environment/reveal", headers=HEADERS, json={"path": ".env", "confirmed": True}
    ).json()

    invalid = client.put(
        "/api/environment/files",
        headers=HEADERS,
        json={"path": ".env", "content": "INVALID_LINE\n", "sha256": revealed["sha256"], "confirmed": True},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "ENV_INVALID"
    assert env_path.read_text(encoding="utf-8") == "DEMO_TOKEN=local-secret\n"

    valid = client.put(
        "/api/environment/files",
        headers=HEADERS,
        json={"path": ".env", "content": "DEMO_TOKEN=changed\n", "sha256": revealed["sha256"], "confirmed": True},
    )
    assert valid.status_code == 200, valid.text
    assert env_path.read_text(encoding="utf-8") == "DEMO_TOKEN=changed\n"
    assert os.stat(env_path).st_mode & 0o777 == 0o640


def test_external_env_requires_exact_file_grant(console_workspace: Path, tmp_path: Path):
    external = tmp_path / "external.env"
    external.write_text("OUTSIDE_TOKEN=secret\n", encoding="utf-8")
    client = _client(console_workspace)

    denied = client.post(
        "/api/environment/reveal",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ENV_PATH_NOT_AUTHORIZED"

    granted = client.post(
        "/api/environment/grants",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert granted.status_code == 200

    revealed = client.post(
        "/api/environment/reveal",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert revealed.status_code == 200
    assert "OUTSIDE_TOKEN=secret" in revealed.json()["content"]

    saved = client.put(
        "/api/environment/files",
        headers=HEADERS,
        json={
            "path": str(external),
            "content": "OUTSIDE_TOKEN=changed\n",
            "sha256": revealed.json()["sha256"],
            "confirmed": True,
        },
    )
    assert saved.status_code == 200, saved.text
    assert external.read_text(encoding="utf-8") == "OUTSIDE_TOKEN=changed\n"


def test_task_external_env_requires_exact_file_grant(console_workspace: Path, tmp_path: Path):
    external = tmp_path / "task.env"
    external.write_text("TASK_OUTSIDE_TOKEN=secret\n", encoding="utf-8")
    task = console_workspace / "test_workspace" / "tasks" / "external.yaml"
    task.write_text(
        f"""schema_version: 1
name: external
env_files:
  - {external}
units: []
""",
        encoding="utf-8",
    )
    client = _client(console_workspace)

    denied = client.post(
        "/api/environment/reveal",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ENV_PATH_NOT_AUTHORIZED"

    granted = client.post(
        "/api/environment/grants",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert granted.status_code == 200

    revealed = client.post(
        "/api/environment/reveal",
        headers=HEADERS,
        json={"path": str(external), "confirmed": True},
    )
    assert revealed.status_code == 200


def test_database_url_is_included_in_job_redactions(console_workspace: Path, monkeypatch):
    secret = "postgres://user:password@localhost/db"
    monkeypatch.setenv("DATABASE_URL", secret)

    assert secret in env_secret_values(_client(console_workspace).app.state.console_runtime.workspace)


def test_env_response_hash_matches_content(console_workspace: Path):
    response = _client(console_workspace).post(
        "/api/environment/reveal", headers=HEADERS, json={"path": ".env", "confirmed": True}
    )
    content = response.json()["content"]
    assert response.json()["sha256"] == hashlib.sha256(content.encode()).hexdigest()
