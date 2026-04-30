# scene_routing 兜底分非法值降级缺陷

## 结论

`TC-ROUTE-010` 和 `TC-ROUTE-017` 暴露待测系统行为与当前 L1 规格不一致：当 `coupon:fallback:score:3001` 存在但值不是数字，且 `coupon:fallback:score:default=0.6` 存在时，服务返回的兜底分是配置默认值 `0.5`，没有继续读取 Redis 全局兜底分 `0.6`。

## 复现方式

前置：

```text
SET coupon:fallback:score:3001 not-a-number
SET coupon:fallback:score:default 0.6
```

请求命中 `policy_fallback_001`，使 `scene_id=3001` 进入兜底响应。

已复现命令：

```bash
python3 -m pytest test_workspace/tests/generated/test_scene_routing_boundary.py -v --tb=short
```

失败现象：

```text
TC-ROUTE-010:
assert resp["results"][0]["score"] == 0.6
E   assert 0.5 == 0.6

TC-ROUTE-017:
assert resp["results"][0]["score"] == 0.6
E   assert 0.5 == 0.6
```

## 根因定位

`coupon_system/services/redis_store.py` 的 `get_fallback_score(scene_id=...)` 在场景级 key 存在但无法转换为 float 时直接返回 `None`：

```python
if scene_val is not None:
    try:
        return float(scene_val)
    except ValueError:
        return None
```

调用方随后使用路由配置默认兜底分，因此不会继续读取 `coupon:fallback:score:default`。

## 影响

- Redis 场景级兜底分被错误写成非数字时，全局 Redis 兜底分不会生效。
- 当前行为与 `test_workspace/knowledge/L1/scene_routing.md` 中“场景级 -> 全局 -> 配置默认值”的三级 fallback 规则不一致。

## 测试侧处理

不修改 `coupon_system/` 源码。`TC-ROUTE-010` 和 `TC-ROUTE-017` 已在 Markdown 用例中标记为当前不可作为通过项生成，等待待测系统修复后移除标记并恢复执行。
