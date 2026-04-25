# AIAutoTest

AI 驱动的自动化测试工具，基于 Claude Code Skill 编排"文档 → 知识库 → 用例 → 执行"全流程。

## 项目结构

```
coupon_system/          # 待测系统：智能优惠券推荐策略服务（FastAPI + gRPC + Redis）
docs/                   # 开发文档输入目录（skill 的输入源）
test_workspace/         # AI 生成内容的工作目录
  knowledge/            #   测试知识库（L0/L1/L2 + TEST_SPEC）
  cases/                #   测试用例（Markdown，按模块分目录）
  plans/                #   方案文档
aitest_kit/             # Python 测试工具库（HTTP/gRPC 客户端、断言引擎）
.claude/skills/         # Claude Code Skill 定义
  doc-gen/              #   设计文档生成（从源码）
  doc-review/           #   设计文档审查
  knowledge-build/      #   测试知识库构建/更新
  test-design/          #   测试用例设计
  test-fix/             #   用例修正 + 经验沉淀
```

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev,server]"

# 启动待测系统
python -m coupon_system.main

# 运行单测
pytest tests/
```

## 技术栈

- Python 3.9+
- FastAPI + gRPC（待测系统）
- httpx + grpcio（测试客户端）
- Redis（数据层）

## 测试飞轮工作流

五个 skill 构成一条闭环流水线。按以下顺序协作：

```
docs/（开发文档）
  ↓
doc-review  ── 审查文档完整性，输出缺口清单
  ↓
doc-gen     ── 从源码补全缺失的设计文档（可选，文档不足时用）
  ↓
knowledge-build ── 从文档构建/更新测试知识库（L0/L1/L2）
  ↓
test-design ── 基于知识库 + TEST_SPEC 生成测试用例
  ↓
人工评审用例
  ↓
test-fix    ── 修正用例错误，沉淀经验到 TEST_SPEC 和相关 skill
  ↓
（需求变更时，从 knowledge-build 重新进入）
```

### 使用指引

- **首次接入新项目**：`/doc-review` → `/doc-gen`（按需）→ `/knowledge-build` → `/test-design`
- **需求迭代**：新文档放入 `docs/` → `/knowledge-build`（增量更新）→ `/test-design`（增量生成）
- **用例出错**：`/test-fix`（修用例 + 记 TEST_SPEC 陷阱 + 更新 skill）
- **只想看文档质量**：`/doc-review`

### 关键约定

- 测试知识库是用例设计的唯一输入源，不绕过知识库直接写用例
- Markdown 用例是唯一数据源，后续 codegen 生成 pytest 代码执行
- TEST_SPEC 是所有 skill 的行为准则，经验教训统一沉淀在此
- 用例存放在 `test_workspace/cases/{模块名}/` 下，未指定时先询问用户
