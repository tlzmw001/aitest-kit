## 变更概述

新增 discount_system 作为迁移演练待测系统，首批接入 discount_policy 模块的 HTTP 公开 API 契约。

## 影响的 L1 模块

- discount_policy — 新增折扣策略评估、决策查询、决策删除和健康检查的测试知识。

## 新增/变更规则

1. 折扣策略评估接口为 `POST /api/v1/discount/policy`，请求体包含 7 个必填字段。
2. 折扣决策按优先级选择最高优先级命中规则。
3. 成功评估结果可按 `request_id` 查询，校验失败不创建记录。
4. 查询不存在决策返回 HTTP `404` 和 `DECISION_NOT_FOUND`。
5. 删除不存在决策仍返回成功，`deleted=false`。

## 影响分析

- 需要在测试飞轮中新增项目文档输入、L1/L2 知识、Markdown 用例、fixture/profile 和 generated pytest。
- 该模块为多端点 HTTP 生命周期测试，不适合复用默认 `/api/v1/recommend` 模板。
- 现有 coupon_system、ab_experiment_sdk 模块不应被修改或回归行为不应变化。

## 测试重点

- 覆盖五条业务规则和优先级冲突。
- 覆盖成功评估后的查询和删除生命周期。
- 覆盖公开字段边界：枚举非法、负数、缺少必填字段。
- 对文档未定义行为只记录缺口，不从实现推断。
