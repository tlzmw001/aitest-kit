from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aitest_kit.console.app import create_app
from aitest_kit.console.editor_validation import validate_editor_content


def _client(root: Path) -> TestClient:
    return TestClient(create_app(initial_workspace=root, token="console-token"))


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def test_yaml_syntax_diagnostic_has_precise_location():
    diagnostics = validate_editor_content(
        "test_workspace/suites/demo/orders_smoke/suite.yaml",
        "target: demo\ncase_files: [\n",
        module_types={"multi_endpoint"},
    )

    syntax = next(item for item in diagnostics if item["code"] == "YAML_SYNTAX")
    assert syntax["severity"] == "error"
    assert syntax["source"] == "yaml"
    assert syntax["line"] == 3
    assert syntax["column"] == 1


def test_suite_yaml_reports_missing_required_fields():
    diagnostics = validate_editor_content(
        "test_workspace/suites/demo/orders_smoke/suite.yaml",
        "target: demo\ncase_files:\n  - business.md\n",
        module_types={"multi_endpoint"},
    )

    assert [(item["code"], item["message"]) for item in diagnostics] == [
        ("AITEST_REQUIRED_FIELD", "suite.yaml 缺少必填字段：module"),
        ("AITEST_REQUIRED_FIELD", "suite.yaml 缺少必填字段：suite"),
    ]


def test_python_syntax_diagnostic_does_not_execute_content():
    diagnostics = validate_editor_content(
        "test_workspace/targets/demo/modules/orders/harness.py",
        "raise RuntimeError('must not run')\ndef broken(:\n",
        module_types=set(),
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "PYTHON_SYNTAX"
    assert diagnostics[0]["line"] == 2


def test_profile_markdown_reports_unknown_top_level_field():
    diagnostics = validate_editor_content(
        "test_workspace/targets/demo/modules/orders/profile.md",
        "# Profile\n\n```yaml\nprofile_scope: module\nunknown_field: true\n```\n",
        module_types=set(),
    )

    assert any(
        item["code"] == "PROFILE_FIELD_UNKNOWN"
        and item["line"] == 5
        and "unknown_field" in item["message"]
        for item in diagnostics
    )


def test_editor_validation_api_validates_unsaved_content(console_workspace: Path):
    response = _client(console_workspace).post(
        "/api/editor/validate",
        headers=_headers(),
        json={
            "path": "test_workspace/suites/demo/orders_smoke/suite.yaml",
            "content": "target: demo\nmodule: orders\nsuite: orders_smoke\ncase_files: [\n",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["diagnostics"][0]["code"] == "YAML_SYNTAX"


def test_editor_validation_api_rejects_env_path(console_workspace: Path):
    response = _client(console_workspace).post(
        "/api/editor/validate",
        headers=_headers(),
        json={"path": ".env", "content": "DEMO_TOKEN=changed\n"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ENV_ACCESS_REQUIRED"


def test_editor_validation_api_rejects_oversized_content(console_workspace: Path):
    response = _client(console_workspace).post(
        "/api/editor/validate",
        headers=_headers(),
        json={
            "path": "test_workspace/suites/demo/orders_smoke/business.md",
            "content": "x" * (2 * 1024 * 1024 + 1),
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "EDITOR_CONTENT_TOO_LARGE"
