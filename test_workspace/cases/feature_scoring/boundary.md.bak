# feature_scoring 边界测试用例

> 生成方式：手动试跑（test-design 第二轮，读代码补充）
> 关联知识库：L1/feature_scoring
> 生成日期：2026-04-25

---

## 一、特征读取边界

### TC-FEAT-005：Redis 连接异常在用户特征读取阶段直接上抛
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.75)]`；使用 `patch.object(redis_store.client, "get", side_effect=redis.ConnectionError("redis down"))` 注入 Redis 连接异常。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_feat_redis_err", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-feat-005", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、`redis_store`、`mock_scoring_client` 并准备库存。
  2. 使用 `patch.object(redis_store.client, "get", side_effect=redis.ConnectionError("redis down"))`，让任意用户特征读取都抛出连接异常。
  3. 调用输入中的 `biz.recommend_and_claim(...)`。
  4. 断言调用过程抛出 `redis.ConnectionError("redis down")`，而不是返回业务错误码。
  5. 断言 `mock_scoring_client.score.assert_not_called()`，确认请求在特征抽取阶段已中断。
- **预期结果**：`redis.ConnectionError` 直接向上抛出；请求不会被转换为 `SCORING_ERROR` 或其他业务错误码；打分服务不被调用。

### TC-FEAT-006：item 特征文件不存在时记录 warning 且请求继续执行
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz` fixture 的构造方式初始化 `CouponBizService`；准备不存在的临时文件路径 `missing_path = tmp_path / "missing_item_features.tsv"`；将 `biz.feature_store` 替换为 `FeatureStore(redis_store=redis_store, user_feature_keys=load_config().user_feature_keys, item_feature_file=str(missing_path))`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.75)]`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_feat_missing_file", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-feat-006", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 创建一个不存在的 `missing_path`，不要实际写入文件。
  2. 使用该路径重新构造 `FeatureStore` 并替换 `biz.feature_store`。
  3. 打开 `caplog` 的 WARNING 日志采集。
  4. 调用输入中的 `biz.recommend_and_claim(...)`。
  5. 断言 `biz.feature_store.get_item_features("COUPON_ACT_001") == {}`。
  6. 断言结果 `result["code"] == 0`，且 `mock_scoring_client.score.assert_called_once()`。
  7. 在 `caplog.records` 中查找包含 `item 特征文件不存在` 的 warning 日志。
- **预期结果**：初始化 `FeatureStore` 时记录 warning；`get_item_features("COUPON_ACT_001")` 返回 `{}`；推荐请求仍能成功执行，不因 item 特征文件缺失而中断。

### TC-FEAT-007：TSV 行格式错误时跳过坏行并保留有效行
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：创建临时文件 `bad_line.tsv`，内容为两行：第一行 `BAD_LINE_WITHOUT_TAB`，第二行 `COUPON_OK_001\t{"popularity": 0.9, "stock": 100}`；使用 `FeatureStore(redis_store=redis_store, user_feature_keys=["gender"], item_feature_file=str(bad_line.tsv))` 初始化 `feature_store`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：依次调用 `feature_store.get_item_features("COUPON_OK_001")` 与 `feature_store.get_item_features("BAD_LINE_WITHOUT_TAB")`
- **测试步骤**：
  1. 创建 `bad_line.tsv`，其中第一行为不含 `\t` 的坏行，第二行为合法 TSV+JSON。
  2. 打开 `caplog` 的 WARNING 日志采集。
  3. 用该文件初始化 `feature_store`。
  4. 调用 `feature_store.get_item_features("COUPON_OK_001")`，保存结果为 `ok_features`。
  5. 调用 `feature_store.get_item_features("BAD_LINE_WITHOUT_TAB")`，保存结果为 `bad_features`。
  6. 断言 `ok_features == {"popularity": 0.9, "stock": 100}`。
  7. 断言 `bad_features == {}`，并在日志中存在 `item 特征文件第 1 行格式错误，跳过`。
- **预期结果**：格式错误的行被跳过并输出 warning；合法行仍正常加载到 `_item_features` 中；坏行不会污染缓存。

### TC-FEAT-008：TSV JSON 解析失败时跳过坏行并保留有效行
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：创建临时文件 `bad_json.tsv`，内容为两行：第一行 `COUPON_BAD_001\t{"popularity": }`，第二行 `COUPON_OK_002\t{"popularity": 0.6, "stock": 50}`；使用 `FeatureStore(redis_store=redis_store, user_feature_keys=["gender"], item_feature_file=str(bad_json.tsv))` 初始化 `feature_store`；使用 `caplog.set_level("WARNING")` 捕获日志。
- **输入**：依次调用 `feature_store.get_item_features("COUPON_BAD_001")` 与 `feature_store.get_item_features("COUPON_OK_002")`
- **测试步骤**：
  1. 创建 `bad_json.tsv`，让第一行 JSON 非法、第二行 JSON 合法。
  2. 打开 `caplog` 的 WARNING 日志采集。
  3. 用该文件初始化 `feature_store`。
  4. 调用 `feature_store.get_item_features("COUPON_BAD_001")`，保存结果为 `bad_features`。
  5. 调用 `feature_store.get_item_features("COUPON_OK_002")`，保存结果为 `ok_features`。
  6. 断言 `bad_features == {}`。
  7. 断言 `ok_features == {"popularity": 0.6, "stock": 50}`，并在日志中存在 `item 特征文件第 1 行 JSON 解析失败，跳过`。
- **预期结果**：JSON 非法的行被跳过并输出 warning；合法行仍正常加载；单行坏数据不会导致整个文件加载失败。

### TC-FEAT-009：reload_item_features 会清空旧缓存后再加载新文件
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：创建 `item_v1.tsv`，内容为 `COUPON_V1\t{"popularity": 0.3}`；创建 `item_v2.tsv`，内容为 `COUPON_V2\t{"popularity": 0.8}`；用 `item_v1.tsv` 初始化 `feature_store`。
- **输入**：先调用 `feature_store.get_item_features("COUPON_V1")`，再调用 `feature_store.reload_item_features(str(item_v2.tsv))`，最后分别调用 `feature_store.get_item_features("COUPON_V1")` 与 `feature_store.get_item_features("COUPON_V2")`
- **测试步骤**：
  1. 创建两个不同版本的 TSV 文件。
  2. 使用 `item_v1.tsv` 初始化 `feature_store`，确认 `feature_store.get_item_features("COUPON_V1") == {"popularity": 0.3}`。
  3. 调用 `feature_store.reload_item_features(str(item_v2.tsv))`。
  4. 再次调用 `feature_store.get_item_features("COUPON_V1")` 与 `feature_store.get_item_features("COUPON_V2")`。
  5. 断言旧 item `COUPON_V1` 返回 `{}`，新 item `COUPON_V2` 返回 `{"popularity": 0.8}`。
- **预期结果**：`reload_item_features` 先清空旧 `_item_features` 缓存，再加载新文件；旧缓存数据不会残留。

## 二、打分客户端边界

### TC-SCORE-009：external_path 未以斜杠开头时自动补成 /score
- **关联**：L2/0402
- **优先级**：P2
- **类型**：边界
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052, external_host="localhost", external_port=50053, external_path="score")`；构造 `fake_response`，其中 `raise_for_status()` 不抛异常，`json()` 返回 `{"code": 0, "message": "success", "scores": [{"item_id": "COUPON_ACT_001", "score": 0.61}]}`；使用 `patch("coupon_system.services.scoring_client.httpx.post", return_value=fake_response)` 捕获请求。
- **输入**：调用 `client.score(user_id="u_path_norm", scene_id=1001, user_features={}, context_features={}, items=[{"item_id": "COUPON_ACT_001", "features": {}}], external=1, request_id="req-score-009")`
- **测试步骤**：
  1. 初始化 `ScoringClient` 时将 `external_path` 设为不带前导斜杠的 `"score"`。
  2. 使用 `patch("coupon_system.services.scoring_client.httpx.post", ...)` 拦截请求。
  3. 调用输入中的 `client.score(...)`。
  4. 读取 `httpx.post.call_args.args[0]` 或 `httpx.post.call_args.kwargs` 中的 URL。
  5. 断言请求 URL 等于 `http://localhost:50053/score`。
- **预期结果**：`external_path="score"` 会被规范化为 `/score`；外部请求 URL 为 `http://localhost:50053/score`，不会变成 `http://localhost:50053score`。

### TC-SCORE-010：外部 HTTP 返回非 JSON 时抛出 RuntimeError
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052, external_host="localhost", external_port=50053)`；构造 `fake_response`，其中 `raise_for_status()` 不抛异常、`text="not-json"`、`json.side_effect=ValueError("invalid json")`；使用 `patch("coupon_system.services.scoring_client.httpx.post", return_value=fake_response)` 捕获请求。
- **输入**：调用 `client.score(user_id="u_bad_json", scene_id=1001, user_features={}, context_features={}, items=[{"item_id": "COUPON_ACT_001", "features": {}}], external=1, request_id="req-score-010")`
- **测试步骤**：
  1. 初始化 `ScoringClient`。
  2. 将 `httpx.post` 打桩为返回非 JSON 的 `fake_response`。
  3. 调用输入中的 `client.score(...)`。
  4. 断言调用抛出 `RuntimeError("External scoring service returned invalid JSON")`。
- **预期结果**：当外部服务响应体无法被 `response.json()` 解析时，`ScoringClient` 抛出 `RuntimeError("External scoring service returned invalid JSON")`。

### TC-SCORE-011：内部 gRPC 返回非零业务码时抛出 RuntimeError
- **关联**：L1/feature_scoring
- **优先级**：P2
- **类型**：边界
- **前置条件**：初始化 `ScoringClient(host="localhost", port=50052)`；从 `coupon_system.protos` 导入 `scoring_pb2`；构造 `FakeStub`，其 `Score(request, timeout)` 返回 `scoring_pb2.ScoreResponse(code=5001, message="downstream unavailable", scores=[])`；使用 `patch.object(client, "_get_stub", return_value=FakeStub())` 注入假 stub。
- **输入**：调用 `client.score(user_id="u_grpc_fail", scene_id=1001, user_features={}, context_features={}, items=[{"item_id": "COUPON_ACT_001", "features": {}}], external=0, request_id="req-score-011")`
- **测试步骤**：
  1. 初始化 `ScoringClient` 并准备返回业务错误码的 `FakeStub`。
  2. 使用 `patch.object(client, "_get_stub", return_value=FakeStub())` 注入假 stub。
  3. 调用输入中的 `client.score(...)`。
  4. 断言调用抛出 `RuntimeError("Scoring service error: downstream unavailable")`。
- **预期结果**：当内部 gRPC 服务返回 `code != 0` 时，`ScoringClient` 不返回空列表，而是抛出 `RuntimeError("Scoring service error: downstream unavailable")`。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/feature_scoring | Redis 连接异常直接上抛、TSV 文件不存在/格式错误/JSON 错误的安全降级、reload_item_features 缓存刷新、外部非 JSON 响应、内部非零业务码错误处理 | fallback 启用且 `on_scoring_unavailable.action="deny"` 的分支 |
| L2/0402 | external_path 自动补 `/` 的请求路径规范化 | 无 |
