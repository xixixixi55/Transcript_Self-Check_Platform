---
name: "Harness: Propose"
description: "创建需求变更包（需求定义 + 影响分析 + 任务拆解），按 Harness 架构约束编排"
argument-hint: "<功能描述>"
---

按 Harness Engineering 迭代闭环的 ① ② ③ 步骤创建需求变更包（Level 3 完整流程入口）。
内部调用 OpenSpec propose 完成变更包创建，并在其上注入 Harness 架构约束。
**不覆盖根目录 AGENTS.md 的级别规则。**

**前置读取**（MUST 在开始前阅读）：
- `AGENTS.md` — 项目上下文、架构分层、命名约定
- `harness/iteration-guide.md` — ① ② ③ 步骤详细流程
- `harness/architecture.md` — 分层定义、依赖规则矩阵

**Input**：功能描述（如 `/harness:propose "舆情仪表盘"`）。无输入时询问用户。

---

**步骤**

1. **调用 OpenSpec 创建变更包**

   执行 `/opsx:propose` 命令完成变更包创建（proposal + specs + design + tasks）。
   `/opsx:propose` 内部会：
   - 读取 `openspec/config.yaml` 中的 rules 约束变更包质量
   - 按 schema 定义的 artifact 依赖顺序生成文件
   - 使用 OpenSpec CLI（如可用）提供结构化支撑

   如果 `/opsx:propose` 命令不可用，降级为手动创建：
   - 创建 `openspec/changes/<功能名>/` 目录
   - MUST 遵循 `openspec/config.yaml` 中 `rules` 定义的质量标准
   - 按顺序生成 proposal.md → specs/ → design.md → tasks.md

2. **Harness 约束注入（在 OpenSpec 产出物上补充）**

   OpenSpec 完成变更包创建后，MUST 检查并补充以下 Harness 约束：

   a. **proposal.md 的 Impact 部分**
      - MUST 按 `harness/architecture.md` 的分层矩阵分析影响范围
      - 列出每个受影响层级的新增/修改

   b. **design.md**
      - 技术设计 MUST 遵循 `harness/architecture.md` 的分层约束
      - 跨层引用 MUST 符合依赖规则矩阵

   c. **tasks.md**
      - MUST 按架构层级从低到高排序（Layer 0 → Layer N）
      - 每个代码 Task 后跟测试 Task
      - 每个 Task 指向具体文件路径，附带验证方式

3. **展示摘要，等待确认**
   - 列出影响的层级、新增/修改的文件数
   - 提示：确认后运行 `/harness:apply` 开始开发

**Guardrails**
- 不确定时追问用户，不猜测
- 与 `openspec/specs/` 中现有 spec 不能冲突
- 如果同名变更包已存在，询问是续建还是新建
