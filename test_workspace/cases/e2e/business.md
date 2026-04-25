# e2e 业务测试用例

> 生成方式：test-design skill
> 关联知识库：L0_system_architecture
> 生成日期：2026-04-25

---

## 一、HTTP 全链路

### TC-E2E-001：通过 HTTP 走内部打分时完成主服务到 AB 服务再到发放的全链路
- **关联**：L0_system_architecture
- **优先级**：P0
- **类型**：业务
- **前置条件**：在 4 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m ab_experiment_sdk.service`、`python -m coupon_system.scoring_server.mock_server`、`AB_SERVICE_URL=http://127.0.0.1:8100 python -m coupon_system.main`；执行 `curl http://127.0.0.1:8000/health` 和 `curl http://127.0.0.1:8100/health` 均返回 200；执行 `curl -X PUT http://127.0.0.1:8100/api/v1/ab/whitelist/u_e2e_http_internal_001 -H 'Content-Type: application/json' -d '{"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}'` 固定命中策略；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/user-features -H 'Content-Type: application/json' -d '{"user_id":"u_e2e_http_internal_001","features":{"gender":"female","age":"24","total_spend":"12000","purchase_frequency":"8","register_days":"60","is_new_user":"True","is_member":"True"}}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_ACT_001","stock":5}'`。
- **输入**：`POST /api/v1/recommend`，body=`{"user_id":"u_e2e_http_internal_001","scene_name":"game","device":"mobile","policy_id":"","external":0,"reqId":"req-e2e-001","score_threshold":0.2,"max_claim_per_request":1,"context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5}]}`。
- **测试步骤**：
  1. 按前置条件启动 Redis、AB 服务、内部 mock scorer 和主服务，并固定 `u_e2e_http_internal_001` 的 AB 白名单。
  2. 发送输入中的 `POST /api/v1/recommend` 请求并保存响应为 `resp`。
  3. 断言 `resp.status_code == 200`、`resp.json()["code"] == 0`、`resp.json()["scene_id"] == 1001`。
  4. 断言 `resp.json()["experiment_info"] == {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`。
  5. 断言 `resp.json()["results"]` 长度为 `1`，且 `results[0]["item_id"] == "COUPON_ACT_001"`、`results[0]["recommended"] == True`。
  6. 断言 `resp.json()["coupon"]["item_id"] == "COUPON_ACT_001"`、`resp.json()["coupon"]["user_id"] == "u_e2e_http_internal_001"`、`resp.json()["coupon"]["status"] == "claimed"`。
  7. 执行 `curl http://127.0.0.1:8000/api/v1/admin/stock/COUPON_ACT_001`，断言返回 `{"code":0,"stock":4}`。
  8. 执行 `curl http://127.0.0.1:8000/api/v1/coupons/u_e2e_http_internal_001`，断言 `code == 0`、`total == 1`，且 `coupons[0]["instance_id"] == resp.json()["coupon"]["instance_id"]`。
- **预期结果**：HTTP 内部打分请求可以贯穿参数校验、场景路由、远程 AB 实验、粗排、特征抽取、内部打分、校准、库存扣减和发放记录持久化；最终返回 `scene_id=1001`、命中的实验信息、1 条推荐结果和 1 张已发放优惠券。

### TC-E2E-002：通过 HTTP 走外部打分时跳过实验但仍完成推荐与发放
- **关联**：L0_system_architecture
- **优先级**：P0
- **类型**：业务
- **前置条件**：在 4 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m ab_experiment_sdk.service`、`python -m coupon_system.scoring_server.external_mock_server`、`AB_SERVICE_URL=http://127.0.0.1:8100 python -m coupon_system.main`；执行 `curl http://127.0.0.1:8000/health` 和 `curl http://127.0.0.1:8100/health` 均返回 200；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/user-features -H 'Content-Type: application/json' -d '{"user_id":"u_e2e_http_external_002","features":{"gender":"male","age":"31","total_spend":"8000","purchase_frequency":"5","register_days":"120","is_new_user":"False","is_member":"True"}}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_SHIP_001","stock":5}'`。
- **输入**：`POST /api/v1/recommend`，body=`{"user_id":"u_e2e_http_external_002","scene_name":"ad","device":"pc","policy_id":"","external":1,"reqId":"req-e2e-002","score_threshold":0.2,"max_claim_per_request":1,"context":{"channel":"ad"},"items":[{"item_id":"COUPON_SHIP_001","coupon_type":"free_shipping","value":0,"min_spend":2999,"expire_days":7}]}`。
- **测试步骤**：
  1. 按前置条件启动 Redis、AB 服务、外部 mock scorer 和主服务，并初始化用户特征与库存。
  2. 发送输入中的 `POST /api/v1/recommend` 请求并保存响应为 `resp`。
  3. 断言 `resp.status_code == 200`、`resp.json()["code"] == 0`、`resp.json()["scene_id"] == 2002`。
  4. 断言 `resp.json()["experiment_info"] == {}`。
  5. 断言 `resp.json()["results"]` 长度为 `1`，且 `results[0]["item_id"] == "COUPON_SHIP_001"`、`results[0]["recommended"] == True`。
  6. 断言 `resp.json()["coupon"]["item_id"] == "COUPON_SHIP_001"`、`resp.json()["coupon"]["user_id"] == "u_e2e_http_external_002"`。
  7. 执行 `curl http://127.0.0.1:8000/api/v1/coupons/u_e2e_http_external_002`，断言 `code == 0`、`total == 1`，且返回的 `item_id` 为 `"COUPON_SHIP_001"`。
- **预期结果**：外部打分 HTTP 链路会正常计算场景 `ad/pc -> scene_id=2002`，并因为 `external=1` 跳过实验评估返回空 `experiment_info`；请求仍可完成外部打分、发放与查询闭环。

## 二、双协议对齐

### TC-E2E-003：同一兜底请求通过 HTTP 和 gRPC 返回一致的业务结果
- **关联**：L0_system_architecture
- **优先级**：P0
- **类型**：业务
- **前置条件**：在 2 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m coupon_system.main`；执行 `curl http://127.0.0.1:8000/health` 返回 200；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_ACT_001","stock":2}'`；不写入任何 `coupon:fallback:score:*` Redis key，使兜底分使用配置默认值 `0.5`。
- **输入**：HTTP 请求为 `POST /api/v1/recommend`，body=`{"user_id":"u_e2e_dual_proto_003","scene_name":"game","device":"mobile","policy_id":"policy_fallback_001","external":0,"reqId":"req-e2e-003-http","score_threshold":0.4,"max_claim_per_request":1,"context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5}]}`；gRPC 请求为 `coupon.CouponService/Recommend`，message=`{"user_id":"u_e2e_dual_proto_003","scene_name":"game","device":"mobile","policy_id":"policy_fallback_001","context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5,"is_prior":False}],"score_threshold":0.4,"max_claim_per_request":1,"external":0,"req_id":"req-e2e-003-grpc"}`。
- **测试步骤**：
  1. 按前置条件启动 Redis 和主服务，并把 `COUPON_ACT_001` 库存初始化为 `2`。
  2. 发送输入中的 HTTP 请求并保存响应为 `http_resp`。
  3. 在 Python 中执行 `from coupon_system.protos import coupon_pb2, coupon_pb2_grpc; import grpc; channel = grpc.insecure_channel("127.0.0.1:50051"); stub = coupon_pb2_grpc.CouponServiceStub(channel); grpc_resp = stub.Recommend(coupon_pb2.RecommendRequest(user_id="u_e2e_dual_proto_003", scene_name="game", device="mobile", policy_id="policy_fallback_001", context={"channel":"game"}, items=[coupon_pb2.CouponItem(item_id="COUPON_ACT_001", coupon_type="discount", value=80, min_spend=5000, expire_days=5, is_prior=False)], score_threshold=0.4, max_claim_per_request=1, external=0, req_id="req-e2e-003-grpc"))`。
  4. 断言 `http_resp.status_code == 200`、`http_resp.json()["code"] == 0`，且 `grpc_resp.code == 0`。
  5. 断言两侧 `scene_id` 都为 `3001`，`experiment_info` 都为空对象。
  6. 断言两侧首个结果都满足 `item_id == "COUPON_ACT_001"`、`score == 0.5`、`calibrated_score == 0.5`、`recommended == True`。
  7. 断言两侧 `coupon.item_id` 都为 `"COUPON_ACT_001"`，且主服务库存最终从 `2` 变为 `0`。
- **预期结果**：当请求命中同一个兜底策略时，HTTP 和 gRPC 两条入口会返回一致的业务结果，包括 `scene_id=3001`、兜底分 `0.5`、空 `experiment_info`、相同的推荐 item 和成功发放结果。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L0_system_architecture | HTTP 内部全链路、HTTP 外部全链路、HTTP/gRPC 双协议一致性 | 主服务与外部打分服务的异常恢复、跨进程并发压测 |
| L1/ab_experiment | 远程 AB 服务参与主链路、`external=1` 跳过实验评估 | AB 服务不可用时的端到端错误传播 |
| L1/issuance | 发放后库存扣减和查询闭环 | 并发库存竞争 |
