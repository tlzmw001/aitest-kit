# logging 边界测试用例

> 生成方式：手动试跑（test-design 第二轮，读代码补充）
> 关联知识库：L1/logging
> 生成日期：2026-04-25

---

## 一、日志配置边界

### TC-LOG-007：未显式配置 root logger 时业务 INFO 日志默认不输出
- **关联**：L1/logging
- **优先级**：P2
- **类型**：边界
- **前置条件**：准备独立 Python 子进程脚本，不调用 `logging.basicConfig()`、不设置 root handler；脚本内容为 `from coupon_system.services.coupon_service import logger; logger.info("recommend request: reqId=req-log-007 user_id=u_log item_ids=A route=1 scene_id=1001")`。
- **输入**：执行 `python3 -c 'from coupon_system.services.coupon_service import logger; logger.info("recommend request: reqId=req-log-007 user_id=u_log item_ids=A route=1 scene_id=1001")'`
- **测试步骤**：
  1. 以子进程方式执行输入中的 Python 命令，捕获 `stdout` 和 `stderr`。
  2. 断言进程退出码为 `0`。
  3. 断言 `stdout` 不包含 `recommend request:`。
  4. 断言 `stderr` 不包含 `recommend request:`。
- **预期结果**：在未显式配置 root logger 且仅使用模块默认 `logger.info()` 的情况下，业务 INFO 日志不会输出到 `stdout/stderr`，体现知识库中标注的“INFO 日志不落地”风险。

## 二、日志故障隔离

### TC-LOG-008：日志 handler 写入失败时业务流程仍返回成功
- **关联**：L1/logging
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.8)]`；构造 `FailingStream`，其 `write()` 抛出 `OSError("log sink broken")`；创建 `logging.StreamHandler(FailingStream())` 并挂到 `coupon_system.services.coupon_service.logger`；设置 `logging.raiseExceptions = False` 模拟生产环境的吞错行为。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_log_sink_fail", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-log-008", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`。
  2. 为 `coupon_system.services.coupon_service.logger` 挂上写入必然失败的 `StreamHandler`。
  3. 将 `logging.raiseExceptions` 临时设置为 `False`。
  4. 调用输入中的 `biz.recommend_and_claim(...)`。
  5. 断言 `result["code"] == 0`，`result["coupon"] is not None`，且 `result["coupon"]["item_id"] == "COUPON_ACT_001"`。
- **预期结果**：即使日志写入失败，业务请求仍正常完成，返回成功响应；日志故障不会中断推荐与发放流程。

## 三、字段格式边界

### TC-LOG-009：多 item 请求的 item_ids 按原顺序以逗号拼接写入日志
- **关联**：L1/logging
- **优先级**：P2
- **类型**：边界
- **前置条件**：按 [tests/test_coupon_service.py](/Users/zmw/AIAutoTest/tests/test_coupon_service.py) 中 `biz`、`redis_store`、`mock_scoring_client` fixture 的构造方式初始化 `CouponBizService`；执行 `setup_stock(redis_store, "COUPON_ACT_001", 100)`、`setup_stock(redis_store, "COUPON_SHIP_001", 100)`、`setup_stock(redis_store, "COUPON_MEM_001", 100)`；设置 `mock_scoring_client.score.return_value=[ItemScore(item_id="COUPON_ACT_001", score=0.9), ItemScore(item_id="COUPON_SHIP_001", score=0.7), ItemScore(item_id="COUPON_MEM_001", score=0.6)]`；使用 `caplog.set_level("INFO")` 捕获日志。
- **输入**：调用 `biz.recommend_and_claim(user_id="u_log_multi", scene_name="game", device="mobile", policy_id="", external=0, req_id="req-log-009", score_threshold=0.5, max_claim_per_request=1, context={}, items=[{"item_id":"COUPON_ACT_001","coupon_type":"discount","value":80,"min_spend":5000,"expire_days":3},{"item_id":"COUPON_SHIP_001","coupon_type":"free_shipping","value":0,"min_spend":0,"expire_days":30},{"item_id":"COUPON_MEM_001","coupon_type":"fixed","value":5000,"min_spend":20000,"expire_days":1}])`
- **测试步骤**：
  1. 初始化 `biz`、库存与 `mock_scoring_client`，并打开 INFO 日志采集。
  2. 调用输入中的 `biz.recommend_and_claim(...)`。
  3. 在 `caplog.records` 中筛选包含 `recommend request:` 的日志行，并读取最新一条。
  4. 断言日志中包含 `item_ids=COUPON_ACT_001,COUPON_SHIP_001,COUPON_MEM_001`。
  5. 断言 `item_ids` 字段中不存在空格分隔形式 `COUPON_ACT_001, COUPON_SHIP_001`。
- **预期结果**：多 item 请求的 `item_ids` 会按输入顺序使用英文逗号直接拼接写入日志，中间不插入空格。

## 覆盖变更

| 知识库文档 | 新增覆盖 | 仍未覆盖 |
|-----------|---------|---------|
| L1/logging | root logger 未配置时 INFO 不落地风险、日志写入失败不影响业务、多 item 的 `item_ids` 拼接格式 | 无 |
| L2/0402 | 无新增覆盖（日志字段完整性和 `reqId` 规则已在业务用例覆盖） | 无 |
