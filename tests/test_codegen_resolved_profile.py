from __future__ import annotations

from aitest_kit.codegen.profile import (
    RuntimeProfile,
    load_profile_case_bodies,
    load_profile_case_flows,
    load_profile_extra_imports,
    load_profile_requests,
    load_profile_rules,
    load_profile_structured_assertions,
    load_profile_yaml,
)
from aitest_kit.codegen.profile_variables import load_profile_variables
from aitest_kit.codegen.resolved_profile import resolve_profile
from aitest_kit.registry.models import ModuleBinding


def test_resolve_profile_none_returns_empty_runtime_view():
    resolved = resolve_profile(None)

    assert resolved.raw == {}
    assert resolved.rules == []
    assert resolved.requests == {}
    assert resolved.structured_assertions == {}
    assert resolved.extra_imports == []
    assert resolved.case_bodies == {}
    assert resolved.case_flows == {}
    assert resolved.variables == {}
    assert resolved.module_type is None
    assert resolved.module_binding is None


def test_resolve_profile_empty_string_matches_empty_runtime_view():
    assert resolve_profile("") == resolve_profile(None)


def test_resolve_profile_path_matches_canonical_profile_loaders(tmp_path):
    profile_path = tmp_path / "profile_demo_suite.md"
    profile_path.write_text(
        """```yaml
assertion_rules:
  - name: ok
    pattern: response code is ok
    template: assert resp["code"] == 0
extra_imports:
  - from demo import Client
requests:
  TC-GW-001:
    overrides:
      tenant: demo
structured_assertions:
  TC-GW-001:
    - type: jsonpath_exists
      target: resp
      path: $.status
case_bodies:
  TC-GW-002: |
    assert True
case_flows:
  TC-GW-001:
    steps:
      - call: harness.health
        save_as: resp
variables:
  defaults:
    token:
      env: DEMO_TOKEN
```
""",
        encoding="utf-8",
    )

    resolved = resolve_profile(profile_path)

    assert resolved.raw == load_profile_yaml(profile_path)
    assert resolved.rules == load_profile_rules(profile_path)
    assert resolved.requests == load_profile_requests(profile_path)
    assert resolved.structured_assertions == load_profile_structured_assertions(profile_path)
    assert resolved.extra_imports == load_profile_extra_imports(profile_path)
    assert resolved.case_bodies == load_profile_case_bodies(profile_path)
    assert resolved.case_flows == load_profile_case_flows(profile_path)
    assert resolved.variables == load_profile_variables(load_profile_yaml(profile_path))
    assert resolved.module_binding is None
    assert resolved.case_flows["TC-GW-001"]["steps"][0] == {
        "call": "harness.health",
        "save_as": "resp",
    }


def test_resolve_runtime_profile_preserves_module_binding():
    binding = ModuleBinding(
        target="demo",
        module="gateway_api",
        fixture_import=(
            "from test_workspace.targets.demo.modules.gateway_api.fixture "
            "import setup_gateway_api"
        ),
        fixture_name="setup_gateway_api",
    )
    runtime = RuntimeProfile(
        data={
            "module_type": "multi_endpoint",
            "case_flows": {
                "TC-GW-001": {
                    "steps": [
                        {"call": "harness.health", "save_as": "resp"},
                    ],
                },
            },
        },
        module_binding=binding,
    )

    resolved = resolve_profile(runtime)

    assert resolved.raw == load_profile_yaml(runtime)
    assert resolved.case_flows == load_profile_case_flows(runtime)
    assert resolved.module_type == "multi_endpoint"
    assert resolved.module_binding == binding
