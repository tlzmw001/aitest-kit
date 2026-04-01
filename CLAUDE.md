# AIAutoTest

AI 驱动的自动化测试工具，基于 Claude Code Skill 编排全流程。

## 项目结构

- `aitest_kit/` — Python 测试工具库（HTTP/gRPC 客户端、断言引擎、用例执行、报告生成）
- `coupon_system/` — 待测系统：智能优惠券/权益发放服务（FastAPI + gRPC + Redis）
- `.claude/skills/autotest/` — Claude Code Skill 定义
- `docs/` — 开发文档输入目录（plan 阶段的输入源）
- `test_workspace/` — AI 生成内容的工作目录（方案/用例/结果/报告）
- `config/autotest.yaml` — 项目配置

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev,server]"

# 启动待测系统
python -m coupon_system.main

# 校验 YAML 用例
python -m aitest_kit validate test_workspace/suites/<suite>.yaml

# 执行测试
python -m aitest_kit run test_workspace/suites/<suite>.yaml --config config/autotest.yaml

# 运行工具库自身的单测
pytest tests/
```

## 技术栈

- Python 3.10+
- FastAPI + gRPC (待测系统)
- httpx + grpcio (测试客户端)
- Redis (数据层)
- PyYAML + jsonschema (用例格式)
