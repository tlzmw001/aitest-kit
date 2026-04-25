# e2e 边界测试用例

> 生成方式：test-design skill
> 关联知识库：L0_system_architecture
> 生成日期：2026-04-25

---

## 一、校准与最新配置生效

### TC-E2E-004：远程 AB 命中 cal_on 且 game/mobile 请求在端到端链路中产生大于原分的校准分
- **关联**：L0_system_architecture
- **优先级**：P1
- **类型**：边界
- **前置条件**：在 4 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m ab_experiment_sdk.service`、`python -m coupon_system.scoring_server.mock_server`、`AB_SERVICE_URL=http://127.0.0.1:8100 python -m coupon_system.main`；执行 `curl http://127.0.0.1:8000/health` 和 `curl http://127.0.0.1:8100/health` 均返回 200；确认校准文件 [1.json](/Users/zmw/AIAutoTest/coupon_system/calibration/scene_game/linear/1.json) 存在且首条规则为 `{"conditions":{"device":"mobile"},"k":1.2,"b":0.1}`；执行 `curl -X PUT http://127.0.0.1:8100/api/v1/ab/whitelist/u_e2e_calibration_004 -H 'Content-Type: application/json' -d '{"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/user-features -H 'Content-Type: application/json' -d '{"user_id":"u_e2e_calibration_004","features":{"gender":"female","age":"28","total_spend":"12000","purchase_frequency":"9","register_days":"90","is_new_user":"True","is_member":"True"}}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_ACT_001","stock":3}'`。
- **输入**：`POST /api/v1/recommend`，body=`{"user_id":"u_e2e_calibration_004","scene_name":"game","device":"mobile","policy_id":"","external":0,"reqId":"req-e2e-004","score_threshold":0.2,"max_claim_per_request":1,"context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5}]}`。
- **测试步骤**：
  1. 按前置条件启动完整依赖，并固定 `u_e2e_calibration_004` 命中 `cr_v2_full` 和 `cal_on`。
  2. 发送输入中的 HTTP 推荐请求并保存响应为 `resp`。
  3. 断言 `resp.status_code == 200`、`resp.json()["code"] == 0`、`resp.json()["scene_id"] == 1001`。
  4. 断言 `resp.json()["experiment_info"] == {"coarse_rank_exp_game":"cr_v2_full","calibration_exp_game":"cal_on"}`。
  5. 断言 `resp.json()["results"][0]["item_id"] == "COUPON_ACT_001"`，且 `resp.json()["results"][0]["calibrated_score"] > resp.json()["results"][0]["score"]`。
  6. 断言 `resp.json()["coupon"]["item_id"] == "COUPON_ACT_001"`，并且查询库存后剩余 `2`。
- **预期结果**：当远程 AB 明确命中 `cal_on` 且请求为 `game/mobile` 时，端到端链路会加载最新版本的 mobile 线性校准规则，表现为返回结果中的 `calibrated_score` 严格大于原始 `score`，且发放流程继续成功。

## 二、跨服务故障边界

### TC-E2E-005：内部打分链路在 AB 服务不可用时直接返回 HTTP 500
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：边界
- **前置条件**：在 3 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m coupon_system.scoring_server.mock_server`、`AB_SERVICE_URL=http://127.0.0.1:8101 python -m coupon_system.main`；确认 `http://127.0.0.1:8101/health` 不可访问；执行 `curl http://127.0.0.1:8000/health` 返回 200；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/user-features -H 'Content-Type: application/json' -d '{"user_id":"u_e2e_ab_down_005","features":{"gender":"male","age":"30","total_spend":"5000","purchase_frequency":"3","register_days":"30","is_new_user":"False","is_member":"False"}}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_ACT_001","stock":3}'`。
- **输入**：`POST /api/v1/recommend`，body=`{"user_id":"u_e2e_ab_down_005","scene_name":"game","device":"mobile","policy_id":"","external":0,"reqId":"req-e2e-005","score_threshold":0.2,"max_claim_per_request":1,"context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5}]}`。
- **测试步骤**：
  1. 按前置条件以错误的 `AB_SERVICE_URL` 启动主服务，并保证 `8101` 端口没有任何 AB 服务进程。
  2. 发送输入中的 HTTP 推荐请求并保存响应为 `resp`。
  3. 断言 `resp.status_code == 500`。
  4. 执行 `curl http://127.0.0.1:8000/api/v1/coupons/u_e2e_ab_down_005`，断言 `total == 0`。
- **预期结果**：内部打分链路依赖远程 AB 服务，AB 服务不可用时请求不会降级为成功响应，而是直接在 HTTP 层暴露 500，且不会留下发放记录。

### TC-E2E-006：外部打分链路在 AB 服务不可用时仍可成功完成推荐
- **关联**：L1/ab_experiment
- **优先级**：P1
- **类型**：边界
- **前置条件**：在 3 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m coupon_system.scoring_server.external_mock_server`、`AB_SERVICE_URL=http://127.0.0.1:8101 python -m coupon_system.main`；确认 `http://127.0.0.1:8101/health` 不可访问；执行 `curl http://127.0.0.1:8000/health` 返回 200；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/user-features -H 'Content-Type: application/json' -d '{"user_id":"u_e2e_external_skip_006","features":{"gender":"male","age":"35","total_spend":"9000","purchase_frequency":"6","register_days":"120","is_new_user":"False","is_member":"True"}}'`；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_SHIP_001","stock":3}'`。
- **输入**：`POST /api/v1/recommend`，body=`{"user_id":"u_e2e_external_skip_006","scene_name":"ad","device":"pc","policy_id":"","external":1,"reqId":"req-e2e-006","score_threshold":0.2,"max_claim_per_request":1,"context":{"channel":"ad"},"items":[{"item_id":"COUPON_SHIP_001","coupon_type":"free_shipping","value":0,"min_spend":2999,"expire_days":7}]}`。
- **测试步骤**：
  1. 按前置条件以错误的 `AB_SERVICE_URL` 启动主服务，但保证外部 HTTP scorer 可用。
  2. 发送输入中的 HTTP 推荐请求并保存响应为 `resp`。
  3. 断言 `resp.status_code == 200`、`resp.json()["code"] == 0`、`resp.json()["scene_id"] == 2002`。
  4. 断言 `resp.json()["experiment_info"] == {}`。
  5. 断言 `resp.json()["coupon"]["item_id"] == "COUPON_SHIP_001"`，且查询用户券后 `total == 1`。
- **预期结果**：即使远程 AB 服务不可用，只要请求走 `external=1` 路径，主服务也会跳过实验评估并继续完成外部打分、发放和查询闭环。

## 三、共享状态边界

### TC-E2E-007：gRPC 发放成功后可立即通过 HTTP 查询同一条领取记录
- **关联**：L0_system_architecture
- **优先级**：P1
- **类型**：边界
- **前置条件**：在 2 个终端分别启动 `redis-server --save '' --appendonly no --port 6379`、`python -m coupon_system.main`；执行 `curl http://127.0.0.1:8000/health` 返回 200；执行 `curl -X POST http://127.0.0.1:8000/api/v1/admin/stock -H 'Content-Type: application/json' -d '{"coupon_id":"COUPON_ACT_001","stock":1}'`；不写入任何 `coupon:fallback:score:*` Redis key。
- **输入**：gRPC 请求为 `coupon.CouponService/Recommend`，message=`{"user_id":"u_e2e_shared_state_007","scene_name":"game","device":"mobile","policy_id":"policy_fallback_001","context":{"channel":"game"},"items":[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":5,"is_prior":False}],"score_threshold":0.4,"max_claim_per_request":1,"external":0,"req_id":"req-e2e-007-grpc"}`；HTTP 请求为 `GET /api/v1/coupons/u_e2e_shared_state_007`。
- **测试步骤**：
  1. 按前置条件启动 Redis 和主服务，并把 `COUPON_ACT_001` 库存初始化为 `1`。
  2. 在 Python 中执行 `from coupon_system.protos import coupon_pb2, coupon_pb2_grpc; import grpc; channel = grpc.insecure_channel("127.0.0.1:50051"); stub = coupon_pb2_grpc.CouponServiceStub(channel); grpc_resp = stub.Recommend(coupon_pb2.RecommendRequest(user_id="u_e2e_shared_state_007", scene_name="game", device="mobile", policy_id="policy_fallback_001", context={"channel":"game"}, items=[coupon_pb2.CouponItem(item_id="COUPON_ACT_001", coupon_type="discount", value=80, min_spend=5000, expire_days=5, is_prior=False)], score_threshold=0.4, max_claim_per_request=1, external=0, req_id="req-e2e-007-grpc"))`。
  3. 断言 `grpc_resp.code == 0`、`grpc_resp.scene_id == 3001`、`grpc_resp.coupon.item_id == "COUPON_ACT_001"`。
  4. 执行 `curl http://127.0.0.1:8000/api/v1/coupons/u_e2e_shared_state_007` 并保存响应为 `http_resp`。
  5. 断言 `http_resp.status_code == 200`、`http_resp.json()["code"] == 0`、`http_resp.json()["total"] == 1`。
  6. 断言 `http_resp.json()["coupons"][0]["instance_id"] == grpc_resp.coupon.instance_id`，且 `http_resp.json()["coupons"][0]["item_id"] == "COUPON_ACT_001"`。
- **预期结果**：同一个主进程中通过 gRPC 成功发放的优惠券，会立刻出现在 HTTP 查询接口中；说明 HTTP 和 gRPC 两条入口共享同一套业务状态和持久化结果。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L0_system_architecture | 真实校准文件在端到端链路中生效、gRPC 发放后 HTTP 可查询同一条记录 | HTTP 与 gRPC 在非兜底随机打分场景下的数值级一致性 |
| L1/ab_experiment | AB 服务不可用时内部链路 500、外部链路跳过实验仍成功 | AB 服务恢复后的自动重试/自愈 |
| L1/calibration | `cal_on` + `game/mobile` 的最新线性校准文件实际生效 | 分段函数校准在端到端链路中的区间边界 |
