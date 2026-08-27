# AGENTS.md — 笔录自检平台（文枢）

> Agent 项目级规则入口；安全与法律要求不可覆盖。Harness、工具命令和 Skill 与本文件冲突时，以本文件为准。

## 1. 项目与资产安全

电子数据检查笔录自动生成平台（React 18 + TypeScript + FastAPI + officecli），面向用户使用。

- 仓库资产政策见 `harness/repository-assets.md`。
- 测试数据必须明确标记为 SYNTHETIC/TEST/FIXTURE。
- 禁止提交真实案件数据、人员信息、设备编号、生成输出。
- 资产检查使用 `npx tsx scripts/check-repository-assets.ts`，已接入 `npm run verify:quick`。

## 2. 事实源与读取范围

工作流程规则优先级：本文件 → `harness/` → `.agents/`、`.claude/` 工具入口。行为预期来自当前任务与有效 OpenSpec/产品文档；实现事实来自代码、Git 状态、测试、构建和实际运行。二者冲突时报告差异，不假设任一方天然正确。

按需读取，不批量加载全部 Harness 或 OpenSpec：

| 优先级 | 内容 | 何时读取 |
|:--:|---|---|
| P0 | 直接相关源码与现有测试 | 每个任务 |
| P1 | `harness/architecture.md` | 新建文件、跨层引用或架构影响 |
| P2 | 本文件的关联、Level、验证规则 | 修改需求、功能、Bug 或回归 |
| P3 | 其他 Harness/OpenSpec 正文 | 候选确认或专用流程明确需要时 |

工具入口采用渐进式上下文：已在当前上下文中的本文件不重复读取；Level 1 只读取直接相关源码/测试，Level 2 再读取匹配包的 tasks 与相关 delta，Level 3 只读取当前阶段所需的指南章节和工件。`harness/architecture.md` 仅在新建文件、跨层引用、公共契约或架构风险出现时加载；验证、Review、归档细则到对应阶段再加载，不得在需求入口无条件预读全部 Harness 文档。

## 3. 未归档变更关联

在判断 Level 前扫描 `openspec/changes/`（排除 `archive/`）。先搜索变更名、`tasks.md` 和少量命中内容；候选不足时扩大到 delta spec，必要时再读 proposal/design，不得为找候选批量载入全部正文。

以下任一项是强关联信号：同一正式能力或 Requirement/Scenario、同一用户结果或验收场景、同一核心调用链/设计决策、原实现引入的回归、候选冻结前反馈。文件、关键词和 capability 相同只用于发现候选，不单独决定归属。

- `in-progress`：同目标任务继续原包并补充任务、delta 和证据。
- `complete` 但未归档：归档前反馈或原验收范围回归可重开原包；其他任务独立判断 Level。
- 已归档：不改写；后续任务重新判断 Level，只有新的 Level 2/3 才创建包。
- 多个候选按需读取后仍重叠不清时，请求用户选择。
- 创建新 Level 2/3 包前，在结果中列出主要候选及排除理由；无关键词命中不等于无关联。

任务归属只决定需求记录位置，不决定本次增量验证强度。

## 4. Level 判断

按正式合同、影响范围、调用范围、回滚风险判断，不按文件数或代码行数机械升级；无法明确判断时采用较轻级别。公共组件、接口、模型、共享类型、持久化和安全边界是影响搜索信号，不自动等于 Level 3。

| 级别 | 适用范围 | 工件与流程 |
|:--:|---|---|
| Level 1 | 文案/样式/展示、内部重构、测试调整、恢复既有预期的 Bug，以及单一能力内部低风险调整；可有局部可观察变化，但不新增公共合同、持久化格式或安全边界 | 直接修改和定向验证；不创建 change、proposal/spec/design，不归档 |
| Level 2 | 需要新增/修改正式 Requirement/Scenario，或引入中等范围能力；保持总体架构 | 复用匹配包；否则创建 `tasks.md` + 至少一个 delta spec，记录 `workflow_level: 2`；不自动增加 proposal/design/Review |
| Level 3 | 重大架构或核心链路变化、大规模重构、框架/引擎/部署/安全模型重大迁移或高回滚风险 | proposal → spec → design → tasks → implementation → verify → review → archive |

Level 2 delta 使用 ADDED/MODIFIED/REMOVED/RENAMED，只写最终行为和关键场景；不得以 `Spec impact: N/A` 绕过。收尾按 delta → 实现核对 → sync → living spec 检查，未同步不得正式归档。

## 5. 验证与测试

验证强度由本次修改风险决定，不继承所在变更包 Level。行为变化必须提供足够证据；新增测试前先搜索现有覆盖，优先复用、修改或合并已有测试，仅在现有证据无法区分新增风险时新增用例。

- 安全、权限、持久化、公共契约、核心业务逻辑和关键数据转换必须有可区分的自动化回归。
- 纯文档、文案、样式、图标及非交互展示不要求新增测试；按需执行类型、构建或视觉检查。
- 前后端同时修改不自动要求两侧新增测试；验证实际改变的逻辑和合同边界。
- Spec Scenario 不要求与测试用例一一对应；避免在多个层重复验证同一实现细节，替换行为时合并或删除失效/重复测试。
- 人工验收独立于 Level，仅用于自动化不能可靠覆盖的 UI 视觉、真实 Word/PDF、桌面环境或真实业务流程；不适用时记录 `N/A`。

增量任务先运行失败用例或最小定向检查。Level 3 开发和反馈阶段不因包级别立即运行最终 Review/full gate；待必选任务、适用人工验收和反馈全部收敛后冻结候选，统一 Review 并运行一次 `npm run verify:full -- --change <name>`。冻结后修改先解冻并做受影响验证，再于下一次收敛时统一冻结。细则见 `harness/verification-strategy.md`。

| 级别 | 收尾自动化 |
|:--:|---|
| Level 1 | 最小定向测试，或适用的 `lint:arch` + `typecheck` |
| Level 2 | `npm run verify:quick` + 受影响模块测试 + `npm run verify:docs:strict -- --change <name>` |
| Level 3 | 冻结候选后的 Review + `npm run verify:full -- --change <name>` |

全局发布/集中归档才运行 `npm run verify:full:all`。`package.json` 是命令唯一来源；输出、环境预检和失败下钻见 `harness/verification-strategy.md`。

## 6. Code Review

- Level 1 默认不启用；Level 2 仅在公共合同、核心数据、安全或高风险跨模块行为有明确审查价值时启用。
- Level 3 在冻结候选后统一审查一次，不按 Task 启动。
- 修改被审查的核心逻辑、接口、模型、正式行为或测试预期会使相关结论失效；纯文案、样式、格式、命名或注释只做受影响 diff 检查，除非它们本身属于正式合同。
- 复审范围和独立审查要求见 `harness/code-review-agent.md`。

## 7. 架构与工具约束

分层方向：SharedTypes(0)→Constants(1)→Utils(2)；FE Hooks(10)→Components(11)→Pages(12)；BE Repo(20)→Services(21)→Controllers(22)→Routes(23)。编号只表示允许的依赖方向，不要求每项业务机械经过 Repo→Service→Controller→Route 全部层级；前后端仅通过 SharedTypes API 契约通信。

- 源码文件 ≤400 行是推荐目标；400–600 行的高内聚模块允许保留；600–800 行必须评估自然职责边界并提供说明；>800 行原则上禁止，需按自然边界拆分或登记明确豁免理由。高内聚模块可合理超过 400 行，禁止仅为 LOC 拆分文件。
- 模块拆分必须由领域职责、变化原因或可独立测试的行为边界驱动；新增 Service/Repository 必须具有可独立描述的领域职责，禁止创建仅承担行数拆分作用的 support/helper/pass-through Service 或 Repository。
- TS 使用 camelCase/PascalCase 和命名导出，Python 使用 snake_case。新增目录更新 `harness/directory.md`。
- 详细依赖矩阵、文件和测试组织见 `harness/architecture.md`。
- `.agents/` 与 `.claude/` 中 Git 管理的对应命令/Skill 必须镜像一致；工具入口只转发本文件和 Harness 细则，不复制独立流程规则。
- `AGENTS.md` 必须不超过 250 行；详细执行说明下沉到已有 Harness 专用文档。

## 8. 完成标准

- 适用的架构、类型检查和受影响验证通过；`git diff` 仅含预期变更。
- Level 2：必选任务完成、delta 与实现核对并同步 living spec、scoped strict docs 通过。
- Level 3：冻结候选的 Review 与 scoped full gate 通过；全局发布/集中归档另跑 global full gate。
- 普通 checklist 默认必选；只有行末明确 `[OPTIONAL]`、`[DEFERRED]` 或 `[N/A]` 可不勾选。

## 9. 禁止事项

- ❌ 以文件数/行数升级风险，或不确定时自动扩大流程。
- ❌ 因行为变化机械新增测试，或在多个层重复同一断言。
- ❌ 将 change 归属直接等同于本次 Task 的验证强度。
- ❌ 多处复制同一规则、硬编码会变化的数字、批量跳过适用验证。
- ❌ 常规使用 `git commit --no-verify`。

## 10. 文档索引

| 路径 | 用途 |
|---|---|
| `harness/iteration-guide.md` | Level 3 闭环与候选节奏 |
| `harness/verification-strategy.md` | 验证选择、人工验收、预检和日志 |
| `harness/architecture.md` | 分层、依赖、文件与测试组织 |
| `harness/code-review-agent.md` | Review 范围和复审 |
| `harness/entropy-rules.md` | 归档与熵治理 |
| `openspec/specs/` | living specs |
