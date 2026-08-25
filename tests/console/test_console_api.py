from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.console.app import create_app


def _client(root: Path) -> TestClient:
    return TestClient(create_app(initial_workspace=root, token="console-token"))


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def test_console_requires_session_token(console_workspace: Path):
    response = _client(console_workspace).get("/api/workspace")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_console_rejects_session_token_in_query_string(console_workspace: Path):
    response = _client(console_workspace).get(
        "/api/workspace",
        params={"token": "console-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_open_workspace_returns_real_registry_tree(console_workspace: Path):
    response = _client(console_workspace).get("/api/workspace", headers=_headers())

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "workspace"
    assert data["counts"] == {"targets": 1, "modules": 1, "suites": 1, "cases": 1, "tasks": 1}
    assert data["targets"][0]["modules"][0]["suites"][0]["cases"][0]["id"] == "TC-ORD-001"
    assert data["recent_reports"][0]["run_id"] == "run-1"


def test_open_rejects_non_workspace(console_workspace: Path, tmp_path: Path):
    response = _client(console_workspace).post(
        "/api/workspace/open",
        headers=_headers(),
        json={"path": str(tmp_path / "missing")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKSPACE_INVALID"


def test_open_rejects_workspace_with_invalid_aitest_config(console_workspace: Path, tmp_path: Path):
    candidate = tmp_path / "candidate"
    (candidate / "aitest_config").mkdir(parents=True)
    (candidate / "test_workspace").mkdir()
    (candidate / "aitest_config" / "aitest.yaml").write_text("workspace: [\n", encoding="utf-8")

    response = _client(console_workspace).post(
        "/api/workspace/open",
        headers=_headers(),
        json={"path": str(candidate)},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKSPACE_INVALID"


def test_open_rejects_registry_asset_directory_outside_workspace(
    console_workspace: Path,
    tmp_path: Path,
):
    outside = tmp_path / "outside-reports"
    outside.mkdir()
    client = _client(console_workspace)
    target = console_workspace / "test_workspace" / "targets" / "demo" / "target.yaml"
    target.write_text(
        f"""target: demo
defaults:
  reports_dir: {outside}
""",
        encoding="utf-8",
    )

    response = client.post(
        "/api/workspace/open",
        headers=_headers(),
        json={"path": str(console_workspace)},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKSPACE_INVALID"


def test_open_uninitialized_directory_requires_explicit_initialization(
    console_workspace: Path,
    tmp_path: Path,
):
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    response = _client(console_workspace).post(
        "/api/workspace/open",
        headers=_headers(),
        json={"path": str(candidate)},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_NOT_INITIALIZED"
    assert list(candidate.iterdir()) == []


def test_initialize_workspace_requires_confirmation(console_workspace: Path, tmp_path: Path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    response = _client(console_workspace).post(
        "/api/workspace/initialize",
        headers=_headers(),
        json={"path": str(candidate), "confirmed": False},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_INIT_CONFIRMATION_REQUIRED"
    assert list(candidate.iterdir()) == []


def test_initialize_workspace_uses_packaged_template_then_opens_it(
    console_workspace: Path,
    tmp_path: Path,
):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    client = _client(console_workspace)

    response = client.post(
        "/api/workspace/initialize",
        headers=_headers(),
        json={"path": str(candidate), "confirmed": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["path"] == str(candidate.resolve())
    assert response.json()["counts"] == {"targets": 0, "modules": 0, "suites": 0, "cases": 0, "tasks": 0}
    assert (candidate / "aitest_config" / "aitest.yaml").is_file()
    assert (candidate / "test_workspace").is_dir()


def test_initialize_workspace_refuses_template_conflicts_without_writing(
    console_workspace: Path,
    tmp_path: Path,
):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    readme = candidate / "README.md"
    readme.write_text("user content\n", encoding="utf-8")

    response = _client(console_workspace).post(
        "/api/workspace/initialize",
        headers=_headers(),
        json={"path": str(candidate), "confirmed": True},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_INIT_CONFLICT"
    assert readme.read_text(encoding="utf-8") == "user content\n"
    assert not (candidate / "aitest_config").exists()


def test_initialize_workspace_refuses_partial_workspace_structure(
    console_workspace: Path,
    tmp_path: Path,
):
    candidate = tmp_path / "candidate"
    (candidate / "test_workspace").mkdir(parents=True)

    response = _client(console_workspace).post(
        "/api/workspace/initialize",
        headers=_headers(),
        json={"path": str(candidate), "confirmed": True},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_INVALID"
    assert not (candidate / "aitest_config").exists()


def test_initialize_workspace_rejects_symlinked_template_directory(
    console_workspace: Path,
    tmp_path: Path,
):
    candidate = tmp_path / "candidate"
    outside = tmp_path / "outside"
    candidate.mkdir()
    outside.mkdir()
    (candidate / "aitest_config").symlink_to(outside, target_is_directory=True)

    response = _client(console_workspace).post(
        "/api/workspace/initialize",
        headers=_headers(),
        json={"path": str(candidate), "confirmed": True},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKSPACE_INIT_CONFLICT"
    assert list(outside.iterdir()) == []


def test_reports_use_runs_as_authority_not_latest_duplicate(console_workspace: Path):
    response = _client(console_workspace).get("/api/reports", headers=_headers())

    assert response.status_code == 200
    reports = response.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["run_id"] == "run-1"


def test_workspace_snapshot_uses_configured_profile_and_report_paths(
    console_workspace: Path,
):
    config = console_workspace / "aitest_config" / "aitest.yaml"
    config.write_text(
        """workspace:
  paths:
    profile_dir: custom/targets
    reports_dir: custom/reports
""",
        encoding="utf-8",
    )
    (console_workspace / "custom").mkdir()
    (console_workspace / "test_workspace" / "targets").rename(console_workspace / "custom" / "targets")
    (console_workspace / "test_workspace" / "reports").rename(console_workspace / "custom" / "reports")
    (console_workspace / "custom" / "suites").mkdir()
    (console_workspace / "test_workspace" / "suites" / "demo").rename(
        console_workspace / "custom" / "suites" / "demo"
    )
    target_config = console_workspace / "custom" / "targets" / "demo" / "target.yaml"
    target_config.write_text(
        """target: demo
defaults:
  module_dir: custom/targets/demo/modules
  suite_dir: custom/suites/demo
  reports_dir: custom/reports/demo
""",
        encoding="utf-8",
    )

    response = _client(console_workspace).get("/api/workspace", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json()["counts"]["targets"] == 1
    assert response.json()["counts"]["suites"] == 1
    assert response.json()["recent_reports"][0]["run_id"] == "run-1"
    target_path = response.json()["targets"][0]["config_path"]
    loaded = _client(console_workspace).get(
        "/api/files",
        params={"path": target_path},
        headers=_headers(),
    )
    assert loaded.status_code == 200, loaded.text
    case_path = response.json()["targets"][0]["modules"][0]["suites"][0]["cases"][0]["source_path"]
    loaded_case = _client(console_workspace).get(
        "/api/files",
        params={"path": case_path},
        headers=_headers(),
    )
    assert loaded_case.status_code == 200, loaded_case.text
    assert loaded_case.json()["owner"] == "CASE"


def test_unknown_route_returns_structured_not_found(console_workspace: Path):
    response = _client(console_workspace).get("/api/not-a-route", headers=_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
