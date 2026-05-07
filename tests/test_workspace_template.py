from pathlib import Path

from click.testing import CliRunner

from aitest_kit.cli import main
from aitest_kit.codegen.cli import codegen


def _write_demo_case(workspace: Path) -> None:
    module_dir = workspace / "test_workspace/cases/demo"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "business.md").write_text(
        """# demo 业务测试用例

## 共享配置

**接口**：`POST /demo`

**基础请求体（HTTP）**：

```json
{
  "user_id": "u_default",
  "reqId": "req_default"
}
```

**通用断言**：`response.code == 0`

---

## 一、基础场景

### TC-DEMO-001：demo case
- **优先级**：P1
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )


def _write_demo_profile(workspace: Path) -> None:
    profile_dir = workspace / "test_workspace/tests/fixtures"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "codegen_profile_demo.md").write_text(
        """```yaml
module_type: standard_http
extra_imports: []
```
""",
        encoding="utf-8",
    )


def test_init_command_copies_clean_project_workspace(tmp_path):
    target = tmp_path / "user_project"

    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code == 0
    assert (target / "aitest_config/config.yaml").exists()
    assert (target / "aitest_config/schemas/codegen_profile.schema.json").exists()
    assert (target / "test_workspace/tests/conftest.py").exists()
    assert "Copied files:" in result.output


def test_init_command_refuses_to_overwrite_existing_files(tmp_path):
    target = tmp_path / "user_project"
    target.mkdir()
    (target / "README.md").write_text("keep me", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target)])

    assert result.exit_code != 0
    assert "refusing to overwrite existing files" in result.output
    assert (target / "README.md").read_text(encoding="utf-8") == "keep me"


def test_init_command_force_overwrites_template_files(tmp_path):
    target = tmp_path / "user_project"
    target.mkdir()
    (target / "README.md").write_text("old", encoding="utf-8")

    result = CliRunner().invoke(main, ["init", "--target", str(target), "--force"])

    assert result.exit_code == 0
    assert "AITest Project Workspace Template" in (target / "README.md").read_text(encoding="utf-8")
    assert "Overwritten files: 1" in result.output


def test_codegen_validate_profile_uses_workspace_paths(tmp_path):
    target = tmp_path / "user_project"
    init_result = CliRunner().invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_demo_case(target)
    _write_demo_profile(target)

    result = CliRunner().invoke(
        codegen,
        ["demo", "--validate-profile", "--workspace", str(target)],
    )

    assert result.exit_code == 0
    assert "Profile validation summary: modules=1, errors=0, warnings=0" in result.output


def test_codegen_generation_writes_under_workspace(tmp_path):
    target = tmp_path / "user_project"
    init_result = CliRunner().invoke(main, ["init", "--target", str(target)])
    assert init_result.exit_code == 0
    _write_demo_case(target)
    _write_demo_profile(target)

    result = CliRunner().invoke(codegen, ["demo", "--workspace", str(target)])

    generated = target / "test_workspace/tests/generated/test_demo_business.py"
    assert result.exit_code == 0
    assert generated.exists()
    assert not Path("test_workspace/tests/generated/test_demo_business.py").exists()
