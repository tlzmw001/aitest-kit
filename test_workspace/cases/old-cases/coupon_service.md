# 优惠券策略系统测试用例

> 来源：tests/test_coupon_service.py
> 待测模块：coupon_system（推荐 pipeline 全链路）

---

## 一、参数校验

### TC-VAL-001：user_id 为空时返回参数错误
- **关联**：L1/validation_ratelimit
- **前置条件**：无
- **输入**：user_id=""，scene_name="game"，device="mobile"，items=有效候选券
- **预期结果**：返回 code=INVALID_PARAM

### TC-VAL-002：scene_name 为空时返回参数错误
- **关联**：L1/validation_ratelimit
- **前置条件**：无
- **输入**：user_id="u001"，scene_name=""，device="mobile"，items=有效候选券
- **预期结果**：返回 code=INVALID_PARAM

### TC-VAL-003：device 为空时返回参数错误
- **关联**：L1/validation_ratelimit
- **前置条件**：无
- **输入**：user_id="u001"，scene_name="game"，device=""，items=有效候选券
- **预期结果**：返回 code=INVALID_PARAM

### TC-VAL-004：items 为空列表时返回参数错误
- **关联**：L1/validation_ratelimit
- **前置条件**：无
- **输入**：user_id="u001"，scene_name="game"，device="mobile"，items=[]
- **预期结果**：返回 code=INVALID_PARAM

### TC-VAL-005：缺少必填请求字段时返回参数错误
- **关联**：L2/0402
- **前置条件**：无
- **输入**：调用 recommend_and_claim，不传 external/score_threshold/max_claim_per_request
- **预期结果**：返回 code=INVALID_PARAM

---

## 二、HTTP 请求 Schema 校验

### TC-SCHEMA-001：HTTP 请求缺少 external 字段
- **关联**：L2/0402
- **前置条件**：构造完整请求 payload
- **输入**：删除 external 字段，构造 RecommendRequest
- **预期结果**：抛出 ValidationError

### TC-SCHEMA-002：HTTP 请求缺少 score_threshold 字段
- **关联**：L2/0402
- **前置条件**：构造完整请求 payload
- **输入**：删除 score_threshold 字段，构造 RecommendRequest
- **预期结果**：抛出 ValidationError

### TC-SCHEMA-003：HTTP 请求缺少 max_claim_per_request 字段
- **关联**：L2/0402
- **前置条件**：构造完整请求 payload
- **输入**：删除 max_claim_per_request 字段，构造 RecommendRequest
- **预期结果**：抛出 ValidationError

---

## 三、gRPC 必填字段校验

### TC-GRPC-001：gRPC 请求缺少 external 字段返回 INVALID_PARAM
- **关联**：L2/0402
- **前置条件**：构造 gRPC RecommendRequest，包含其他必填字段
- **输入**：不设置 external
- **预期结果**：response.code == INVALID_PARAM

### TC-GRPC-002：gRPC 请求缺少 score_threshold 字段返回 INVALID_PARAM
- **关联**：L2/0402
- **前置条件**：构造 gRPC RecommendRequest，设置 external=0
- **输入**：不设置 score_threshold
- **预期结果**：response.code == INVALID_PARAM

### TC-GRPC-003：gRPC 请求缺少 max_claim_per_request 字段返回 INVALID_PARAM
- **关联**：L2/0402
- **前置条件**：构造 gRPC RecommendRequest，设置 external=0，score_threshold=0.5
- **输入**：不设置 max_claim_per_request
- **预期结果**：response.code == INVALID_PARAM

### TC-GRPC-004：gRPC 请求包含所有必填字段可通过校验
- **关联**：L1/validation_ratelimit
- **前置条件**：构造完整 gRPC RecommendRequest
- **输入**：所有必填字段均设置
- **预期结果**：response.code == OK

### TC-GRPC-005：gRPC 请求中 is_prior 字段正确映射为内部 isPrior
- **关联**：L2/0404
- **前置条件**：初始化库存，白名单用户命中粗排策略
- **输入**：gRPC CouponItem 设置 is_prior=True
- **预期结果**：response.code == OK，coarse_ranker.rank 收到的 item 中 isPrior==True

---

## 四、场景路由

### TC-ROUTE-001：game/mobile 路由到 scene_id=1001
- **关联**：L1/scene_routing
- **前置条件**：初始化库存
- **输入**：scene_name="game"，device="mobile"
- **预期结果**：result["scene_id"] == 1001

### TC-ROUTE-002：ad/pc 路由到 scene_id=2002
- **关联**：L1/scene_routing
- **前置条件**：初始化库存
- **输入**：scene_name="ad"，device="pc"
- **预期结果**：result["scene_id"] == 2002

### TC-ROUTE-003：兜底 policyId 跳过打分直接发放
- **关联**：L1/scene_routing
- **前置条件**：初始化库存
- **输入**：policy_id="policy_fallback_001"
- **预期结果**：scene_id=3001，message="兜底策略"，experiment_info={}，打分服务未被调用

### TC-ROUTE-004：兜底发放时 user_id 正确传递
- **关联**：L1/scene_routing
- **前置条件**：初始化库存
- **输入**：user_id="u_fallback"，policy_id="policy_fallback_001"
- **预期结果**：coupon 不为空，coupon["user_id"]=="u_fallback"

### TC-ROUTE-005：未知场景组合走兜底
- **关联**：L1/scene_routing
- **前置条件**：初始化库存
- **输入**：scene_name="unknown"，device="vr"
- **预期结果**：scene_id=3001，experiment_info=={}

### TC-ROUTE-006：兜底场景跳过实验评估
- **关联**：L1/scene_routing, L2/0404
- **前置条件**：初始化库存
- **输入**：policy_id="policy_fallback_001"
- **预期结果**：code=OK，scene_id=3001，experiment_sdk.evaluate 未被调用

---

## 五、AB 实验

### TC-EXP-001：正常请求返回实验信息
- **关联**：L1/ab_experiment
- **前置条件**：初始化库存
- **输入**：scene_name="game"，device="mobile"
- **预期结果**：experiment_info 包含 coarse_rank_exp_game 和 calibration_exp_game

### TC-EXP-002：白名单用户可强制指定策略
- **关联**：L1/ab_experiment
- **前置条件**：初始化库存，设置用户白名单 {coarse_rank_exp_game: "cr_off", calibration_exp_game: "cal_on"}
- **输入**：user_id="u_whitelist_001"
- **预期结果**：code=OK，experiment_info 中策略与白名单设置一致

### TC-EXP-003：只评估当前场景映射的实验
- **关联**：L1/ab_experiment, L2/0404
- **前置条件**：初始化库存
- **输入**：scene_name="ad"，device="pc"
- **预期结果**：experiment_info 包含 ad 相关实验，不包含 game 相关实验

---

## 六、粗排

### TC-CR-001：保送券按 top_value 规则排序
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：3 个 item（2 个 isPrior=True），prior_rule="top_value"，prior_count=2
- **预期结果**：结果为 [P_high, P_low]，按 value 降序

### TC-CR-002：截断规则按 top_value 保留前 N 个
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：4 个 item，truncate_count=2，truncate_rule="top_value"
- **预期结果**：返回 2 个，value 最高的在前

### TC-CR-003：截断数量超过候选数时不截断
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：1 个 item，truncate_count=10
- **预期结果**：返回 1 个

### TC-CR-004：多重过滤条件取交集
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：3 个 item，filters=[expire_days>=3, value>=5, coupon_type in (discount,cash)]
- **预期结果**：只有同时满足三个条件的 item 保留

### TC-CR-005：多样性控制 + backfill 补位
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：3 个相同 coupon_type 的 item，diversity max_per_group=1，truncate_count=2
- **预期结果**：先选 1 个多样性名额，再从 backfill 补 1 个

### TC-CR-006：完整粗排 pipeline（保送+过滤+排序+多样性）
- **关联**：L1/rough_ranking
- **前置条件**：无
- **输入**：8 个 item（含 3 个保送），过滤 expire_days<3，带加权排序和多样性
- **预期结果**：[P1, P2, A, C, E]，保送 2 个在前，目标位按多样性从不同 type 各取 1 个

---

## 七、打分与发放

### TC-CLAIM-001：正常打分后成功发放
- **关联**：L1/issuance
- **前置条件**：初始化库存 100，打分返回 score=0.6
- **输入**：正常推荐请求
- **预期结果**：code=OK，results 长度 1，coupon 不为空，status="claimed"

### TC-CLAIM-002：发放后库存减少
- **关联**：L1/issuance
- **前置条件**：初始化库存 100，打分返回 score=0.6
- **输入**：正常推荐请求
- **预期结果**：库存从 100 降为 99

### TC-CLAIM-003：分数低于阈值不发放
- **关联**：L1/issuance
- **前置条件**：初始化库存 100，打分返回 score=0.3（阈值 0.5）
- **输入**：正常推荐请求
- **预期结果**：code=OK，coupon=None，recommended=False，库存不变

### TC-CLAIM-004：库存为零时跳过发放
- **关联**：L1/issuance
- **前置条件**：初始化库存 0，打分返回 score=0.8
- **输入**：正常推荐请求
- **预期结果**：code=OK，coupon=None

### TC-CLAIM-005：多候选券发放分数最高的
- **关联**：L1/issuance
- **前置条件**：3 个候选券各 100 库存，打分分别 0.6/0.9/0.4
- **输入**：传入 3 个候选券
- **预期结果**：发放分数最高的 COUPON_SHIP_001

### TC-CLAIM-006：请求级 score_threshold 覆盖配置
- **关联**：L2/0402
- **前置条件**：初始化库存 100，打分返回 score=0.6
- **输入**：score_threshold=0.95
- **预期结果**：code=OK，coupon=None，recommended=False

### TC-CLAIM-007：max_claim_per_request 控制尝试发放数量
- **关联**：L2/0402
- **前置条件**：A 库存 0，B 库存 100，打分 A=0.9 B=0.8
- **输入**：max_claim_per_request=1 vs max_claim_per_request=2
- **预期结果**：=1 时 coupon=None（只尝试 A），=2 时发放 B

### TC-CLAIM-008：请求级参数非法返回错误
- **关联**：L2/0402
- **前置条件**：无
- **输入**：score_threshold=1.5 或 max_claim_per_request=0
- **预期结果**：code=INVALID_PARAM

---

## 八、打分服务异常

### TC-FAIL-001：打分超时走兜底（default_score=0.5）
- **关联**：L1/feature_scoring
- **前置条件**：初始化库存 100，打分抛出 TimeoutError
- **输入**：正常推荐请求
- **预期结果**：code=OK，使用 default_score=0.5（>=阈值 0.5），发放成功

### TC-FAIL-002：打分不可用走兜底（default_score=0.3）
- **关联**：L1/feature_scoring
- **前置条件**：初始化库存 100，打分抛出 RuntimeError
- **输入**：正常推荐请求
- **预期结果**：code=OK，使用 default_score=0.3（<阈值 0.5），不发放

### TC-FAIL-003：打分超时 action=deny 时返回错误
- **关联**：L1/feature_scoring
- **前置条件**：配置 on_scoring_timeout.action="deny"，打分抛出 TimeoutError
- **输入**：正常推荐请求
- **预期结果**：code=SCORING_ERROR

### TC-FAIL-004：兜底分优先读 Redis
- **关��**：L2/0402
- **前置条件**：初始化库存 100，Redis 设置 scene_id=1001 的兜底分 0.9，打分抛出 RuntimeError
- **输入**：正常推荐请求
- **预期结果**：code=OK，score=0.9，发放成功

---

## 九、外部打分路由与日志

### TC-LOG-001：external=1 路由正确且日志包含关键字段
- **关联**：L2/0402
- **前置条件**：初始化库存 100
- **输入**：external=1，req_id="req-abc-001"
- **预期结果**：code=OK，experiment_info={}，打分服务收到 external=1 和 request_id，日志包含 reqId/user_id/item_ids/route=2/scene_id

### TC-LOG-002：external=1 跳过实验评估
- **关联**：L2/0402, L2/0404
- **前置条件**：初始化库存 100
- **输入**：external=1
- **预期结果**：code=OK，experiment_info={}，experiment_sdk.evaluate 未被调用

### TC-LOG-003：external=1 时场景路由仍正常工作
- **关联**：L2/0402
- **前置条件**：初始化库存 100
- **输入**：external=1，scene_name="ad"，device="pc"
- **预期结果**：scene_id=2002（场景与 route 隔离）

---

## 十、校准

### TC-CAL-001：线性校准 y=kx+b 并 clamp 到 [0,1]
- **关联**：L1/calibration
- **前置条件**：创建线性校准文件，conditions={device:"ios"}，k=1.2，b=0.1
- **输入**：score=0.9，device="ios"
- **预期结果**：calibrated_score=1.0（1.2*0.9+0.1=1.18，clamp 后=1.0）

### TC-CAL-002：分段+线性串联校准
- **关联**：L1/calibration
- **前置条件**：创建分段和线性校准文件
- **输入**：score=0.5，device="ios"
- **预期结果**：先分段（中间段保持 0.5），再线性（1.2*0.5+0.05=0.65）

### TC-CAL-003：加载最新版本校准文件
- **关联**：L1/calibration
- **前置条件**：目录中有 1.json 和 3.json
- **输入**：score=0.5
- **预期结果**：使用 3.json 的参数（k=1.3），calibrated_score=0.65

### TC-CAL-004：无效 condition 字段不匹配
- **���联**：L1/calibration
- **前置条件**：校准规则包含未知字段 "unknown":"x"
- **输入**：score=0.4，device="ios"
- **预期结果**：规则不命中，calibrated_score=0.4（原值不变）

---

## 十一、特征抽取

### TC-FEAT-001：获取用户特征
- **关联**：L1/feature_scoring
- **前置条件**：Redis 中写入用户特征 {gender:"male", total_spend:"15000", is_new_user:"true"}
- **输入**：user_id="u001"
- **预期结果**：返回包含 gender、total_spend 的 dict

### TC-FEAT-002：获取 Item 特征
- **关联**：L1/feature_scoring
- **前置条件**：item_features.tsv 文件包含 COUPON_ACT_001 数据
- **输入**：item_id="COUPON_ACT_001"
- **预期结果**：返回包含 popularity、stock 字段的 dict

### TC-FEAT-003：不存在的 Item 返回空 dict
- **关联**：L1/feature_scoring
- **前置条件**：无
- **输入**：item_id="NONEXISTENT"
- **预期结果**：返回 {}

---

## 十二、查询接口

### TC-QUERY-001：未领券用户查询返回空
- **关联**：L1/issuance
- **前置条件**：无
- **输入**：user_id="user_no_coupons"
- **预期结果**：code=OK，coupons=[]，total=0

### TC-QUERY-002：领券后可查询到
- **关联**：L1/issuance
- **前置条件**：用户 u001 成功领取 COUPON_ACT_001
- **输入**：query_user_coupons("u001")
- **预期结果**：code=OK，total=1，coupons[0]["item_id"]=="COUPON_ACT_001"

### TC-QUERY-003：user_id 为空返回参数错误
- **关联**：L1/issuance
- **前置条件**：无
- **输入**：user_id=""
- **预期结果**：code=INVALID_PARAM

---

## 十三、限流

### TC-RATE-001：用户级限流（per_user_qps=2）
- **关联**：L1/validation_ratelimit
- **前置条件**：启用限流，per_user_qps=2，max_qps=100
- **输入**：同一用户连续 3 次请求
- **预期结果**：第 3 次返回 RATE_LIMITED，或前 2 次均为 OK
