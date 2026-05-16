# Lesson 9：skills 工作流和 AI 协作边界

> 学习目标：理解 skill 不是替代 CLI 的代码，而是约束 AI 如何沿着测试飞轮工作的协议。

## skills 工作流总图

```mermaid
flowchart TD
    A["docs/ 公开文档"] --> B["doc-review: 检查文档缺口"]
    B --> C{"文档足够?"}
    C -->|否| D["doc-gen: 从源码/现有文档补测试设计输入"]
    C -->|是| E["knowledge-build"]
    D --> E

    E --> F["knowledge L0/L1/L2"]
    F --> G["test-design"]
    G --> H["Markdown cases"]

    H --> I["人工 review"]
    I --> J["test-codegen"]
    J --> K["aitest codegen: parser/profile/IR/renderer"]
    K --> L["generated pytest"]

    L --> M["aitest run/report"]
    M --> N{"失败类型?"}

    N -->|用例问题| O["test-fix: 修 Markdown + TEST_SPEC"]
    N -->|fixture/profile/codegen| P["修 fixture/profile/emitter"]
    N -->|待测系统 bug| Q["记录 test_workspace/results"]
    N -->|通过| R["emitter-build: 沉淀辅助"]

    O --> J
    P --> J
    R --> S["规则 / profile / helper / 文档沉淀"]
```

## 本节关键结论

skill 的本质不是自动化脚本，而是：

```text
AI 工作流协议。
```

它规定 AI 在每个阶段：

```text
读什么
不能读什么
输出什么
遇到不确定怎么标
什么时候停
什么时候进入下一阶段
什么时候沉淀经验
```

CLI 的本质是：

```text
确定性执行引擎。
```

两者合起来，才是完整项目：

```text
skills 负责让 AI 做正确的判断；
CLI 负责让稳定规则可重复执行。
```

这仍然符合项目核心哲学：

```text
AI 负责探索未知，代码负责稳定重复。
```
