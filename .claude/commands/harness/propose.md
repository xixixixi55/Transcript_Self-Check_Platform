---
name: "Harness: Propose"
description: "创建需求变更包（需求定义 + 影响分析 + 任务拆解），按 Harness 架构约束编排"
argument-hint: "<功能描述>"
---

按 Harness Engineering 的需求入口处理新功能或现有行为修改。
先按根目录 `AGENTS.md` 关联活跃变更包并判断级别，再选择轻量任务清单或完整 OpenSpec 变更包；只有 Level 3 才执行完整的 ① ② ③ 步骤。
**不覆盖根目录 AGENTS.md 的级别规则。**

**前置读取**（MUST 在开始前阅读）：
- `AGENTS.md` — 项目上下文、架构分层、命名约定
- `harness/iteration-guide.md` — ① ② ③ 步骤详细流程
- `harness/architecture.md` — 分层定义、依赖规则矩阵

**Input**：功能描述（如 `/harness:propose "舆情仪表盘"`）。无输入时询问用户。

---

**步骤**

1. **关联活跃变更包并判断级别（创建前 MUST 执行）**

   - 扫描 `openspec/changes/` 下除 `archive/` 外的活跃变更包。
   - 读取范围相近候选包的 `tasks.md` 及必要的 proposal/spec/design。
   - 完全属于已有变更目标时，继续使用原变更包并补充任务，不创建重复包。
   - 仅名称相似但范围不一致时不得强行挂靠；存在多个无法排除的重叠候选时暂停并请求用户选择。
   - 确认没有匹配包后，按行为影响、调用范围和回滚风险判断 Level；不确定时默认较轻级别。

2. **按级别创建或选择变更工件**

   - Level 1：直接按 `AGENTS.md` 的轻量流程修改，不创建 OpenSpec change。
   - Level 2：固定创建 `openspec/changes/<功能名>/tasks.md` 与至少一个 `specs/<能力>/spec.md` 精简 delta；在 tasks.md 写入 `workflow_level: 2`、目标、验收标准、任务列表、影响范围和验证方式。不得使用 `Spec impact: N/A`；没有行为 delta 时重新归为 Level 1。不自动创建 proposal.md、design.md，也不增加 Level 3 的 verify/review 要求。
   - Level 3：调用 OpenSpec 创建完整变更包。

3. **Level 3 调用 OpenSpec 创建变更包**

   仅 Level 3 执行 `/opsx:propose`，完成 proposal + specs + design + tasks。

   `/opsx:propose` 内部会：
   - 读取 `openspec/config.yaml` 中的 rules 约束变更包质量
   - 按 schema 定义的 artifact 依赖顺序生成文件
   - 使用 OpenSpec CLI（如可用）提供结构化支撑

   如果 `/opsx:propose` 命令不可用，降级为手动创建：
   - 创建 `openspec/changes/<功能名>/` 目录
   - MUST 遵循 `openspec/config.yaml` 中 `rules` 定义的质量标准
   - 按顺序生成 proposal.md → specs/ → design.md → tasks.md

4. **Harness 约束注入（在变更工件上补充）**

   Level 3 的 OpenSpec 完成后，MUST 检查并补充以下 Harness 约束；Level 2 将任务信息写入 tasks.md，并将最终行为要求和关键场景写入精简 delta spec：

   a. **proposal.md 的 Impact 部分（仅 Level 3）**
      - MUST 按 `harness/architecture.md` 的分层矩阵分析影响范围
      - 列出每个受影响层级的新增/修改

   b. **design.md（仅 Level 3）**
      - 技术设计 MUST 遵循 `harness/architecture.md` 的分层约束
      - 跨层引用 MUST 符合依赖规则矩阵

   c. **tasks.md**
      - MUST 按架构层级从低到高排序（Layer 0 → Layer N）
      - 改变交互、业务行为或数据处理的 Task 必须说明对应测试；纯样式、文案、图标和不改变交互的展示调整不强制新增测试 Task
      - 每个 Task 指向具体文件路径，附带验证方式
      - Level 2 必须保留 `workflow_level: 2`，不以是否存在 proposal/design 反向猜测级别

5. **展示摘要，等待确认**
   - 列出影响的层级、新增/修改的文件数
   - Level 2 提示确认后按 tasks.md 对照 delta spec 开始开发；Level 3 提示确认后运行 `/harness:apply` 开始开发

**Guardrails**
- 需求范围或行为定义有歧义时追问用户，不猜测；仅级别不确定时按 `AGENTS.md` 默认采用较轻级别
- 与 `openspec/specs/` 中现有 spec 不能冲突
- 不得只用变更包名称判断是否重复，必须按目标和范围关联
