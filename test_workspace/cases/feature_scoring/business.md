# feature_scoring 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L1/feature_scoring
> 生成日期：2026-04-25

---

## 一、用户特征读取

### TC-FEAT-004：Redis 缺失用户特征字段时静默省略
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `redis_store` fixture 的方式初始化 `RedisStore`；执行 `config = load_config()`；使用 `FeatureStore(redis_store=redis_store, user_feature_keys=config.user_feature_keys, item_feature_file="data/item_features.tsv")` 初始化 `feature_store`；通过 `setup_user_features(redis_store, "u_feat_partial", {"gender": "female", "age": "28"})` 仅写入 2 个用户特征字段，不写入 `total_spend/purchase_frequency/register_days/is_new_user/is_member`。
- **输入**：调用 `feature_store.get_user_features("u_feat_partial")`
- **测试步骤**：
  1. 初始化 `redis_store`、`config` 和 `feature_store`，确保 `feature_store.user_feature_keys` 使用 `settings.yaml` 中定义的 7 个特征字段。
  2. 通过 `setup_user_features(...)` 仅写入 `gender="female"` 和 `age="28"`。
  3. 调用 `feature_store.get_user_features("u_feat_partial")`，保存返回值为 `features`。
  4. 断言 `features == {"gender": "female", "age": "28"}`。
  5. 断言 `"total_spend" not in features`、`"purchase_frequency" not in features`、`"register_days" not in features`、`"is_new_user" not in features`、`"is_member" not in features`。
- **预期结果**：返回结果只包含 Redis 中存在的字段 `gender` 和 `age`；缺失字段被静默省略，不抛异常。

## 二、打分路由

### TC-SCORE-001：external=0 时 ScoringClient 只走内部 gRPC 路径
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：业务
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052, external_host="localhost", external_port=50053)`；使用 `patch.object(client, "_score_internal_grpc", return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.31)])` 打桩内部路径；使用 `patch.object(client, "_score_external_http")` 监控外部路径且不设置返回值。
- **输入**：调用 `client.score(user_id="u_internal_route", scene_id=1001, user_features={"is_member": "false"}, context_features={"channel": "game"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}], external=0, request_id="req-score-001")`
- **测试步骤**：
  1. 初始化真实 `ScoringClient` 对象，不使用 `MagicMock(spec=ScoringClient)` 代替。
  2. 使用 `patch.object` 分别监控 `_score_internal_grpc` 与 `_score_external_http`。
  3. 调用输入中的 `client.score(...)`，显式传入 `external=0` 与 `request_id="req-score-001"`。
  4. 断言返回结果长度为 1，且 `result[0].item_id == "COUPON_ACT_001"`、`result[0].score == 0.31`。
  5. 断言 `_score_internal_grpc.assert_called_once_with(request_id="req-score-001", user_id="u_internal_route", scene_id=1001, user_features={"is_member": "false"}, context_features={"channel": "game"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}])`。
  6. 断言 `_score_external_http.assert_not_called()`。
- **预期结果**：`external=0` 时仅调用内部 gRPC 路径；返回值来自 `_score_internal_grpc`；外部 HTTP 路径完全不被调用。

### TC-SCORE-002：external=1 时 ScoringClient 只走外部 HTTP 路径
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：业务
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052, external_host="localhost", external_port=50053)`；使用 `patch.object(client, "_score_external_http", return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.46)])` 打桩外部路径；使用 `patch.object(client, "_score_internal_grpc")` 监控内部路径且不设置返回值。
- **输入**：调用 `client.score(user_id="u_external_route", scene_id=1001, user_features={"is_member": "true"}, context_features={"channel": "ad"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}], external=1, request_id="req-score-002")`
- **测试步骤**：
  1. 初始化真实 `ScoringClient` 对象。
  2. 使用 `patch.object` 分别监控 `_score_external_http` 与 `_score_internal_grpc`。
  3. 调用输入中的 `client.score(...)`，显式传入 `external=1` 与 `request_id="req-score-002"`。
  4. 断言返回结果长度为 1，且 `result[0].item_id == "COUPON_ACT_001"`、`result[0].score == 0.46`。
  5. 断言 `_score_external_http.assert_called_once_with(request_id="req-score-002", user_id="u_external_route", scene_id=1001, user_features={"is_member": "true"}, context_features={"channel": "ad"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}])`。
  6. 断言 `_score_internal_grpc.assert_not_called()`。
- **预期结果**：`external=1` 时仅调用外部 HTTP 路径；返回值来自 `_score_external_http`；内部 gRPC 路径完全不被调用。

## 三、身份传递与失败处理

### TC-SCORE-003：外部 HTTP 请求对 user_id 做 SHA-256 加盐哈希且不下发 route
- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052, external_host="localhost", external_port=50053, external_path="/score", external_user_id_salt="coupon_external_uid_salt")`；构造 `fake_response`，其中 `fake_response.raise_for_status()` 不抛异常，`fake_response.json()` 返回 `{"code": 0, "message": "success", "scores": [{"item_id": "COUPON_ACT_001", "score": 0.62}]}`；使用 `patch("coupon_system.services.scoring_client.httpx.post", return_value=fake_response)` 捕获 HTTP 请求。
- **输入**：调用 `client.score(user_id="u_ext_hash_001", scene_id=1001, user_features={"is_member": "true"}, context_features={"channel": "ad"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}], external=1, request_id="req-score-003")`
- **测试步骤**：
  1. 初始化 `ScoringClient`，保持 `external_user_id_salt="coupon_external_uid_salt"`。
  2. 使用 `patch("coupon_system.services.scoring_client.httpx.post", ...)` 拦截外部 HTTP 请求。
  3. 调用输入中的 `client.score(...)`。
  4. 读取 `httpx.post.call_args.kwargs["json"]`，保存为 `payload`。
  5. 断言 `payload["request_id"] == "req-score-003"`。
  6. 断言 `payload["user_id"] == "8e21e887e6d8821c837ee2d8564ea90c756083954b4e7f18a03fbf64cac6b2ab"`。
  7. 断言 `payload["user_id"] != "u_ext_hash_001"`，且 `"route" not in payload`。
  8. 断言返回结果为 `[ItemScore(item_id="COUPON_ACT_001", score=0.62)]`。
- **预期结果**：外部 HTTP 请求体中的 `user_id` 为 `sha256("coupon_external_uid_salt:u_ext_hash_001")` 的 64 位十六进制字符串 `8e21e887e6d8821c837ee2d8564ea90c756083954b4e7f18a03fbf64cac6b2ab`；请求体不包含 `route` 字段；返回结果正常解析为 1 条分数。

### TC-SCORE-004：内部 gRPC 请求保留明文 user_id 且请求结构不包含 route
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：业务
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052)`；从 `coupon_system.protos` 导入 `scoring_pb2`；构造 `FakeStub`，其 `Score(request, timeout)` 在保存 `captured["request"] = request`、`captured["timeout"] = timeout` 后返回 `scoring_pb2.ScoreResponse(code=0, message="success", scores=[scoring_pb2.ItemScore(item_id="COUPON_ACT_001", score=0.58)])`；使用 `patch.object(client, "_get_stub", return_value=FakeStub())` 注入假 stub。
- **输入**：调用 `client.score(user_id="u_plain_001", scene_id=1001, user_features={"gender": "male", "total_spend": "15000"}, context_features={"channel": "game"}, items=[{"item_id": "COUPON_ACT_001", "features": {"popularity": 0.4, "coupon_type": "discount", "value": 80, "min_spend": 5000, "expire_days": 3}}], external=0, request_id="req-score-004")`
- **测试步骤**：
  1. 初始化 `ScoringClient` 并导入 `scoring_pb2`。
  2. 使用 `patch.object(client, "_get_stub", return_value=FakeStub())` 注入可捕获请求体的 fake stub。
  3. 调用输入中的 `client.score(...)`，显式传入 `external=0`。
  4. 读取 `captured["request"]`。
  5. 断言 `captured["request"].request_id == "req-score-004"`、`captured["request"].user_id == "u_plain_001"`、`captured["request"].scene_id == 1001`。
  6. 断言 `dict(captured["request"].user_features) == {"gender": "male", "total_spend": "15000"}`。
  7. 断言 `dict(captured["request"].items[0].features)["coupon_type"] == "discount"`。
  8. 断言 `captured["request"].DESCRIPTOR.fields_by_name.get("route") is None`。
- **预期结果**：内部 gRPC 请求中的 `user_id` 以明文 `"u_plain_001"` 发送；请求结构只包含 `request_id/user_id/scene_id/user_features/context_features/items`，不存在 `route` 字段；返回结果成功解析为 `item_id="COUPON_ACT_001"`、`score=0.58`。

### TC-SCORE-005：fallback 全局关闭时打分超时返回 SCORING_ERROR
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `biz.config.fallback.enabled = False`；设置 `mock_scoring_client.score.side_effect = TimeoutError("timeout")`。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_timeout_disabled", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-score-005", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、`redis_store`、`mock_scoring_client`，并准备库存。
  2. 将 `biz.config.fallback.enabled` 显式设置为 `False`。
  3. 将 `mock_scoring_client.score.side_effect` 设置为 `TimeoutError("timeout")`。
  4. 调用输入中的 `biz.recommend_and_claim(...)`。
  5. 断言返回结果中的 `code/message/scene_id/results/coupon`。
- **预期结果**：返回 `{"code": 1012, "message": "打分服务异常", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

### TC-SCORE-006：fallback 全局关闭时打分不可用返回 SCORING_ERROR
- **关联**：L1/feature_scoring
- **优先级**：P1
- **类型**：异常
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `biz.config.fallback.enabled = False`；设置 `mock_scoring_client.score.side_effect = RuntimeError("unavailable")`。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_unavailable_disabled", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-score-006", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、`redis_store`、`mock_scoring_client`，并准备库存。
  2. 将 `biz.config.fallback.enabled` 显式设置为 `False`。
  3. 将 `mock_scoring_client.score.side_effect` 设置为 `RuntimeError("unavailable")`。
  4. 调用输入中的 `biz.recommend_and_claim(...)`。
  5. 断言返回结果中的 `code/message/scene_id/results/coupon`。
- **预期结果**：返回 `{"code": 1012, "message": "打分服务异常", "scene_id": 0, "experiment_info": {}, "results": [], "coupon": null}`。

## 四、分数基线

### TC-SCORE-007：内部 mock scorer 的基础分为 0.1
- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：从 `coupon_system.scoring_server.mock_server` 导入 `MockScorer`；使用 `patch("coupon_system.scoring_server.mock_server.random.uniform", return_value=0.0)` 固定噪声为 0；准备 `user_features={}` 与 `item_features={}`，确保没有任何加分项命中。
- **输入**：调用 `MockScorer()._calculate_score(user_features={}, item_features={})`
- **测试步骤**：
  1. 导入 `MockScorer` 并创建实例。
  2. 使用 `patch(...random.uniform, return_value=0.0)` 去掉随机噪声。
  3. 调用 `_calculate_score(user_features={}, item_features={})`。
  4. 断言返回值等于 `0.1`。
- **预期结果**：在无用户特征加分、无 item 特征加分、无随机噪声时，内部 mock scorer 返回基础分 `0.1`。

### TC-SCORE-008：外部 mock scorer 的基础分为 0.2
- **关联**：L2/0402
- **优先级**：P1
- **类型**：业务
- **前置条件**：从 `coupon_system.scoring_server.external_mock_server` 导入 `ExternalMockScorer`；使用 `patch("coupon_system.scoring_server.external_mock_server.random.uniform", return_value=0.0)` 固定噪声为 0；准备 `user_features={}`、`context_features={}` 与 `item_features={}`，确保没有任何加分项命中。
- **输入**：调用 `ExternalMockScorer()._calculate_score(user_features={}, context_features={}, item_features={})`
- **测试步骤**：
  1. 导入 `ExternalMockScorer` 并创建实例。
  2. 使用 `patch(...random.uniform, return_value=0.0)` 去掉随机噪声。
  3. 调用 `_calculate_score(user_features={}, context_features={}, item_features={})`。
  4. 断言返回值等于 `0.2`。
- **预期结果**：在无用户特征加分、无上下文加分、无 item 特征加分、无随机噪声时，外部 mock scorer 返回基础分 `0.2`。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/feature_scoring | 用户特征缺失静默省略、internal gRPC 路由、external HTTP 路由、外部请求 user_id SHA-256 加盐、内部请求 user_id 明文、fallback 全局关闭时 timeout/unavailable 返回 SCORING_ERROR | Redis 连接异常直接上抛、TSV 文件不存在/格式错误/JSON 错误的安全降级 |
| L2/0402 | internal/external 实际打分路由切换、外部 user_id 加密正确性、内部/外部 base_score 0.1/0.2、route 字段不下发给打分服务 | 无 |
