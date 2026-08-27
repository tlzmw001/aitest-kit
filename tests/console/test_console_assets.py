from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from aitest_kit.console.app import create_app


def _client(root: Path) -> TestClient:
    return TestClient(create_app(initial_workspace=root, token="console-token"))


def _headers() -> dict[str, str]:
    return {"X-AITest-Console-Token": "console-token"}


def test_directory_browser_lists_only_directories_and_workspace_state(
    console_workspace: Path,
    tmp_path: Path,
):
    parent = tmp_path / "browse"
    child = parent / "child"
    initialized = parent / "initialized"
    hidden = parent / ".hidden"
    child.mkdir(parents=True)
    hidden.mkdir()
    (parent / "ordinary.txt").write_text("not returned", encoding="utf-8")
    (initialized / "aitest_config").mkdir(parents=True)
    (initialized / "aitest_config" / "aitest.yaml").write_text("workspace: {}\n", encoding="utf-8")
    (initialized / "test_workspace").mkdir()

    response = _client(console_workspace).get(
        "/api/directories",
        params={"path": str(parent)},
        headers=_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json()["directories"] == [
        {"name": ".hidden", "path": str(hidden), "initialized": False},
        {"name": "child", "path": str(child), "initialized": False},
        {"name": "initialized", "path": str(initialized), "initialized": True},
    ]


def test_directory_browser_rejects_non_directory(console_workspace: Path, tmp_path: Path):
    file_path = tmp_path / "plain.txt"
    file_path.write_text("content", encoding="utf-8")

    response = _client(console_workspace).get(
        "/api/directories",
        params={"path": str(file_path)},
        headers=_headers(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DIRECTORY_INVALID"


def test_create_target_module_suite_and_task_without_fake_cases(console_workspace: Path):
    client = _client(console_workspace)

    target = client.post(
        "/api/assets/targets",
        json={"name": "billing"},
        headers=_headers(),
    )
    assert target.status_code == 200, target.text

    options = client.get("/api/assets/options", headers=_headers())
    assert {item["name"] for item in options.json()["module_types"]} >= {"standard_http"}

    module = client.post(
        "/api/assets/modules",
        json={"target": "billing", "name": "invoice", "module_type": "standard_http"},
        headers=_headers(),
    )
    assert module.status_code == 200, module.text

    suite = client.post(
        "/api/assets/suites",
        json={"target": "billing", "module": "invoice", "name": "invoice-smoke"},
        headers=_headers(),
    )
    assert suite.status_code == 200, suite.text
    suite_data = next(
        item
        for target_item in suite.json()["targets"]
        if target_item["name"] == "billing"
        for module_item in target_item["modules"]
        for item in module_item["suites"]
    )
    assert suite_data["name"] == "invoice-smoke"
    assert suite_data["cases"] == []
    assert {asset["name"] for asset in suite_data["assets"]} == {
        "suite.yaml",
        "cases.md",
        "profile_invoice-smoke_suite.md",
    }
    module_yaml = yaml.safe_load(
        (console_workspace / "test_workspace/targets/billing/modules/invoice/module.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert module_yaml["registered_suites"][0]["suite"] == "invoice-smoke"

    task = client.post(
        "/api/assets/tasks",
        json={
            "name": "billing-nightly",
            "description": "Billing suites",
            "suite_files": [suite_data["manifest_path"]],
        },
        headers=_headers(),
    )
    assert task.status_code == 200, task.text
    created = next(item for item in task.json()["tasks"] if item["name"] == "billing-nightly")
    assert created["unit_count"] == 1


def test_create_rejects_invalid_python_asset_name_and_duplicate(console_workspace: Path):
    client = _client(console_workspace)

    invalid = client.post(
        "/api/assets/targets",
        json={"name": "not-importable"},
        headers=_headers(),
    )
    duplicate = client.post(
        "/api/assets/modules",
        json={"target": "demo", "name": "orders", "module_type": "standard_http"},
        headers=_headers(),
    )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "ASSET_NAME_INVALID"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ASSET_ALREADY_EXISTS"


def test_delete_preview_blocks_target_module_and_referenced_suite(console_workspace: Path):
    client = _client(console_workspace)

    target = client.post(
        "/api/assets/delete-preview",
        json={"kind": "target", "target": "demo"},
        headers=_headers(),
    ).json()
    module = client.post(
        "/api/assets/delete-preview",
        json={"kind": "module", "target": "demo", "module": "orders"},
        headers=_headers(),
    ).json()
    suite = client.post(
        "/api/assets/delete-preview",
        json={"kind": "suite", "target": "demo", "module": "orders", "suite": "orders_smoke"},
        headers=_headers(),
    ).json()

    assert target["can_delete"] is False
    assert "target 下仍有 module" in target["blockers"]
    assert module["blockers"] == ["module 下仍有 suite"]
    assert suite["blockers"] == ["suite 被 task nightly 引用"]
    assert suite["identity"] == {
        "kind": "suite",
        "target": "demo",
        "module": "orders",
        "suite": "orders_smoke",
    }


def test_suite_delete_requires_confirmation_then_unregisters_and_restores(console_workspace: Path):
    client = _client(console_workspace)
    created = client.post(
        "/api/assets/suites",
        json={"target": "demo", "module": "orders", "name": "temporary"},
        headers=_headers(),
    )
    assert created.status_code == 200, created.text
    identity = {"kind": "suite", "target": "demo", "module": "orders", "suite": "temporary"}

    unconfirmed = client.post(
        "/api/assets/delete",
        json={**identity, "confirmed": False},
        headers=_headers(),
    )
    assert unconfirmed.status_code == 403
    assert unconfirmed.json()["error"]["code"] == "ASSET_DELETE_CONFIRMATION_REQUIRED"

    deleted = client.post(
        "/api/assets/delete",
        json={**identity, "confirmed": True},
        headers=_headers(),
    )
    assert deleted.status_code == 200, deleted.text
    entry_id = deleted.json()["entry"]["entry_id"]
    assert not (console_workspace / "test_workspace/suites/demo/temporary").exists()
    module_data = yaml.safe_load(
        (console_workspace / "test_workspace/targets/demo/modules/orders/module.yaml").read_text(encoding="utf-8")
    )
    assert {item["suite"] for item in module_data["registered_suites"]} == {"orders_smoke"}

    restored = client.post(f"/api/trash/{entry_id}/restore", headers=_headers())
    assert restored.status_code == 200, restored.text
    assert (console_workspace / "test_workspace/suites/demo/temporary/cases.md").exists()
    module_data = yaml.safe_load(
        (console_workspace / "test_workspace/targets/demo/modules/orders/module.yaml").read_text(encoding="utf-8")
    )
    assert {item["suite"] for item in module_data["registered_suites"]} == {"orders_smoke", "temporary"}
    assert client.get("/api/trash", headers=_headers()).json()["entries"] == []


def test_restore_refuses_to_overwrite_registry_changed_after_suite_delete(console_workspace: Path):
    client = _client(console_workspace)
    created = client.post(
        "/api/assets/suites",
        json={"target": "demo", "module": "orders", "name": "conflict_suite"},
        headers=_headers(),
    )
    assert created.status_code == 200, created.text
    deleted = client.post(
        "/api/assets/delete",
        json={
            "kind": "suite",
            "target": "demo",
            "module": "orders",
            "suite": "conflict_suite",
            "confirmed": True,
        },
        headers=_headers(),
    )
    entry_id = deleted.json()["entry"]["entry_id"]
    module_path = console_workspace / "test_workspace/targets/demo/modules/orders/module.yaml"
    module_path.write_text(module_path.read_text(encoding="utf-8") + "# user edit\n", encoding="utf-8")

    restored = client.post(f"/api/trash/{entry_id}/restore", headers=_headers())

    assert restored.status_code == 409
    assert restored.json()["error"]["code"] == "TRASH_RESTORE_CONFLICT"
    assert not (console_workspace / "test_workspace/suites/demo/conflict_suite").exists()


def test_task_and_empty_target_deletes_are_recoverable(console_workspace: Path):
    client = _client(console_workspace)
    target = client.post(
        "/api/assets/targets",
        json={"name": "empty_target"},
        headers=_headers(),
    )
    assert target.status_code == 200, target.text

    deleted_target = client.post(
        "/api/assets/delete",
        json={"kind": "target", "target": "empty_target", "confirmed": True},
        headers=_headers(),
    )
    assert deleted_target.status_code == 200, deleted_target.text
    assert not (console_workspace / "test_workspace/targets/empty_target").exists()
    restored_target = client.post(
        f"/api/trash/{deleted_target.json()['entry']['entry_id']}/restore",
        headers=_headers(),
    )
    assert restored_target.status_code == 200, restored_target.text

    deleted_task = client.post(
        "/api/assets/delete",
        json={"kind": "task", "task": "nightly", "confirmed": True},
        headers=_headers(),
    )
    assert deleted_task.status_code == 200, deleted_task.text
    restored_task = client.post(
        f"/api/trash/{deleted_task.json()['entry']['entry_id']}/restore",
        headers=_headers(),
    )
    assert restored_task.status_code == 200, restored_task.text
