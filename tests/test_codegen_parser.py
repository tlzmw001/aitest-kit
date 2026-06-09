from __future__ import annotations

from pathlib import Path

from aitest_kit.codegen.parser import parse_case_file


def _write_case_file(tmp_path: Path, base_request_label: str) -> Path:
    path = tmp_path / "demo.md"
    path.write_text(
        f"""# demo cases

## 共享配置

**接口**：`POST /api/v1/demo`

**{base_request_label}**：

```json
{{
  "user_id": "u_default",
  "items": [
    {{
      "publishStatus": 1
    }}
  ]
}}
```

---

## 一、冒烟

### TC-DEMO-001：demo request
- **优先级**：P0
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )
    return path


def test_parser_treats_generic_base_request_as_default_json_body(tmp_path):
    result = parse_case_file(_write_case_file(tmp_path, "基础请求体"))

    assert result.errors == []
    assert result.shared_config.base_request_http == {
        "user_id": "u_default",
        "items": [{"publishStatus": 1}],
    }


def test_parser_treats_json_base_request_as_default_json_body(tmp_path):
    result = parse_case_file(_write_case_file(tmp_path, "基础请求体（JSON）"))

    assert result.errors == []
    assert result.shared_config.base_request_http == {
        "user_id": "u_default",
        "items": [{"publishStatus": 1}],
    }


def test_parser_treats_grpc_labeled_base_request_as_default_json_body(tmp_path):
    path = tmp_path / "demo.md"
    path.write_text(
        """# demo cases

## 共享配置

**接口**：`gRPC demo.Service/Call`

**基础请求体（gRPC）**：

```json
{
  "user_id": "u_default",
  "reqId": "r_default"
}
```

**标准前置**：
- 准备测试数据

---

## 一、冒烟

### TC-DEMO-001：demo request
- **优先级**：P0
- **断言**：`response.code == 0`
""",
        encoding="utf-8",
    )

    result = parse_case_file(path)

    assert result.errors == []
    assert result.shared_config.base_request_http == {
        "user_id": "u_default",
        "reqId": "r_default",
    }
    assert not hasattr(result.shared_config, "base_request_grpc")
    assert result.shared_config.preconditions == ["准备测试数据"]
