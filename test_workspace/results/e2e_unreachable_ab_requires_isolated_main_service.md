# E2E 不可达 AB 场景需要独立主服务测试环境

## 结论

`TC-E2E-005` 不是当前默认 generated 集成测试环境可直接执行的用例。它要求主服务以 `AB_SERVICE_URL={{unreachable_ab_base_url}}` 启动，用来验证内部打分链路在 AB 服务不可用时返回 HTTP 500。

当前默认集成环境会启动正常 AB 服务，并以 `AB_SERVICE_URL=http://127.0.0.1:8100` 启动主服务。在这个环境下执行 `TC-E2E-005` 会得到 HTTP 200，这是环境编排不满足用例前置，不是待测系统缺陷。

## 复现命令

```bash
python3 -m pytest test_workspace/tests/generated -v -m "not manual"
```

## 实际结果

```text
test_workspace/tests/generated/test_e2e_boundary.py::TestE2eBoundary::test_tc_e2e_005 FAILED
assert response.status_code == 500
E assert 200 == 500
```

## 期望前置

该用例需要 fixture 支持以下能力：

- 启动一个独立主服务实例。
- 该实例使用不可达的 `AB_SERVICE_URL`。
- 不修改仓库默认 `.env`。
- 不影响同一轮 generated 测试中依赖正常 AB 服务的其他用例。

## 当前处理

已将 `TC-E2E-005` 标记为 `[!可行性存疑]`，并从 `codegen_profile_e2e.md` 的 `case_flows` 中移除。等 fixture 支持独立主服务环境后，再恢复为可执行用例。
