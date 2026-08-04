# AGENTS.md — 笔录自检平台（文枢）

> Agent 项目级工作规则入口。工具专属命令、Skill、Harness 指南与本文件冲突时以本文件为准。

---

## 1. 项目目标

电子数据检查笔录自动生成平台（React 18 + TypeScript + FastAPI + officecli），面向民警使用。

---

## 1.1 仓库资产与合规

**本仓库经过敏感数据清理（历史重写完成于 2026-07-21）。**

- 仓库资产政策：`harness/repository-assets.md`
- 所有测试数据必须是明确合成数据（使用 SYNTHETIC/TEST/FIXTURE 标记）
- 禁止提交真实案件数据、人员信息、设备编号、生成输出
- 资产检查门控：`npx tsx scripts/check-repository-assets.ts`（已接入 `verify:quick`）
- **所有协作者必须从重写后的远端重新 clone**，禁止从旧 clone 推送

---

## 2. 规则优先级

**工作流程规则**（冲突时按此顺序）：
1. 安全与法律合规 — 不可覆盖
2. 根目录 AGENTS.md — Agent 工作流程最高规则来源
3. Harness 运营文档（`harness/`）— 架构约束、熵治理详情
4. 工具命令与 Skill（`.claude/`、`.agents/`）— 快捷入口，不得覆盖以上

**行为预期**：当前任务要求 + 有效 OpenSpec / 产品文档描述预期行为。
**实现事实**：代码、Git 状态、测试、构建和实际运行结果为当前实现状态的判断依据。

规格与实现冲突 → 报告差异，根据任务决定修改实现还是更新规格。不确定时暂停请求人类判定。

---

## 3. 任务开始前检查

按需读取，不得一次性加载所有 `harness/` 和 `openspec/`：

| 优先级 | 内容 | 何时读取 |
|:------:|------|---------|
| P0 | 直接相关源文件和测试 | 每个任务 |
| P1 | `harness/architecture.md` | 涉及新建文件或跨层引用 |
| P2 | 本文件的级别判断规则 | 不确定级别时 |
| P3 | 其他 `harness/` 详情 | 仅明确需要时 |

### 需求/功能任务的变更包关联检查

提出新需求或修改现有功能时，必须先扫描 `openspec/changes/` 下除 `archive/` 外的活跃变更包，并读取范围相近候选包的 `tasks.md` 及必要的 proposal/spec/design。完全属于已有变更目标时，必须继续在原变更包内补充任务和证据，不得重复创建；仅名称相似但范围不一致时不得强行挂靠；存在多个无法排除的重叠候选时暂停并请求人类选择。确认没有匹配的活跃变更包后，才按下述 Level 规则选择 Level 1 直接修改、Level 2 `tasks.md` + delta spec 或 Level 3 完整变更包。

### Bug/回归任务的变更包关联检查

修复 Bug 或回归问题时，必须先扫描 `openspec/changes/` 下除 `archive/` 外的活跃变更包，并读取候选包的 `tasks.md` 及必要的 proposal/spec/design，确认问题是否属于已有需求范围。已有匹配变更包时，必须在原变更包内修复、更新任务状态和测试证据，不得重复创建同目标变更包；仅名称相似但范围不一致时不得强行挂靠。存在多个无法排除的候选包时暂停并请求人类选择。确认没有匹配的活跃变更包后，才按下述 Level 规则判断是直接修复、创建 Level 2 `tasks.md` + delta spec，还是创建 Level 3 完整变更包；已归档变更不直接改写，通常新建修复变更包。

---

## 4. 任务级别判断

根据行为变化、影响范围、公共契约、调用范围和回滚风险判断，不得根据文件数量或代码行数机械判断。新增局部字段（即使改 3 个文件）可能仍是 Level 1；修改公共组件（影响多个页面）可能是 Level 2。

**无法明确判断时默认采用较轻级别。**

公共组件、公共接口、核心数据模型、共享类型、跨模块行为、鉴权和安全边界、持久化格式、模板公共语法只是**影响范围搜索信号**，不自动触发 Level 3。先搜索调用范围，只有确认属于重大架构、核心功能链路、大规模重构、重大迁移或高回滚风险时才升级。级别可在实施中调整，升级时只补充必要材料。

---

## 5. Level 1 — 轻量修改

**适用**：纯样式、文案、小修复、内部重构、测试调整，以及其他不新增或改变正式行为的修改。

**流程**：检查 Git → 读相关代码和测试 → 搜索调用范围 → 最小修改 → 针对性验证（相关测试或 `lint:arch` + `typecheck`）→ 检查 diff → 汇报。不创建 OpenSpec change、proposal/spec/design、迭代记录。不要求读取 `iteration-guide.md`、独立 Code Review Agent、归档。

---

## 6. Level 2 — 普通功能或中等影响修改

**适用**：引入新的可观察行为或扩大现有能力，影响范围中等，但仍保持现有公共契约和总体架构。模块数和文件数仅作参考。

**固定产物**：`openspec/changes/<name>/tasks.md` 与至少一个 `openspec/changes/<name>/specs/<capability>/spec.md`。在 tasks.md 持久化 `workflow_level: 2`；delta spec 只记录最终行为要求和关键场景，必须使用 ADDED/MODIFIED/REMOVED/RENAMED 结构。不得使用 `Spec impact: N/A` 绕过；没有行为 delta 时重新归为 Level 1。不因此新增 proposal.md、design.md、verify 或 review 要求。

**收尾**：实现完成后核对 delta 与最终行为，按 `delta spec → 实现核对 → sync → 检查 living spec` 同步到 `openspec/specs`；主规格未同步不得正式归档。

---

## 7. Level 3 — 重大变更

**适用**：重大架构变化、核心功能链路变化、跨模块大规模重构、框架/引擎更换、数据库/队列引入、重大部署变化、重大安全模型变化或高回滚风险迁移。小范围新增接口、局部持久化字段或受控上传实现，按影响范围判断，默认不直接升级。

**完整流程**：proposal → spec → design → tasks → implementation → verify → review → archive。默认读取完整 Harness 迭代、评审和熵治理文档。

---

## 8. 自动化测试与人工验收

- 纯样式、文案、图标或不改变交互的展示调整，不强制新增自动化测试。
- 改变交互、导航、可访问性、数据处理或业务行为时，必须有受影响层的定向测试；前后端都变更时两侧都测。
- 核心业务逻辑、权限、安全、关键数据转换必须有可区分的有效断言；不要求对纯展示代码做突变验证。
- 人工验收是独立维度，不由 Level 1/2/3 自动推导。只有 UI 视觉、真实 Word/PDF、桌面环境、真实业务流程或用户明确要求无法由自动化可靠覆盖时才触发；不适用时记录 `N/A`。

所有自动化验证命令（pytest、Vitest、模块测试、完整门控及其子命令）的输出处理都先给通过/失败汇总和按类型计数；失败默认不展开逐条日志，只有需要定位失败时才下钻具体日志。命令没有提供对应参数时，不得虚构通用的 `--details` 参数。
运行 pytest 默认使用安静模式和短 traceback（`-q --tb=short`），前端 Vitest 优先使用非 verbose 模式：先只读取退出码、最终统计和失败数量；通过时不逐条读取通过用例，失败时只下钻失败用例及其 traceback。修复后先重跑失败用例，再按需运行受影响模块；除非明确需要，不使用 `-v` 或逐条输出。

---

## 9. Code Review Agent

| 级别 | 要求 |
|:----:|------|
| Level 1 | 默认不启用 |
| Level 2 | 按需启用；仅在审查有明确价值时使用 |
| Level 3 | 候选版本统一审查一次，不按 Task 启动；必须保留独立审查或人工审查证据 |

Review 驳回后，修改了被审查源码、接口、数据模型或行为时必须复审；只改文档、格式、命名或注释等测试元数据时可不复审；修改测试断言、fixture、mock、覆盖范围或预期结果时必须复审。最终验证失败导致实现修改时，原 Review 结论失效。详见 `harness/code-review-agent.md`。

---

## 10. 验证与治理范围

| 级别 | 验证命令 | OpenSpec | 归档 |
|:----:|------|---------|:----:|
| Level 1 | 按变化执行定向测试，或 `npm run verify:quick` | 不创建 | 不归档 |
| Level 2 | `npm run verify:quick` + 受影响模块原始测试；收尾执行 scoped strict docs | tasks.md + delta specs | sync 后方可正式归档 |
| Level 3 | 执行全仓库自动化工程检查；严格任务状态仅检查 `npm run verify:full -- --change <name>` 指定的变更包；全局发布/集中归档执行 `npm run verify:full:all` | 完整变更包 | 完整归档协议 |

Level 2 的严格任务状态和 delta 结构只检查 `<name>` 当前变更包；Level 3 当前变更收尾也只检查显式传入的 `<name>`，全局发布/集中归档才检查所有活跃变更包。普通 checklist 任务默认必选；只有任务行末尾明确写成 `[OPTIONAL]`、`[DEFERRED]` 或 `[N/A]` 时可不勾选。脚本只读取显式状态和 `workflow_level`，不根据 proposal/design 是否存在反向猜测级别，也不宣称能自动判断代码与规格的完整语义一致性。

`npm run verify:full -- --change <name>` 执行全仓库自动化工程检查，但严格任务状态只检查指定变更包；`npm run verify:full:all` 才检查全部活跃变更包。两者都不等同于完整系统验收；当前不包含 Playwright E2E、mypy、真实桌面环境和 Word/PDF 人工验收。未提供 scope 时，`verify:full` 不猜测当前变更，直接提示使用 `--change` 或 `--all`。

`package.json` 是命令唯一来源；`scripts/verify.sh` 和 `harness.config.yaml` 只做转发。保留的 `verify:frontend`/`verify:backend` 仅是模块便利入口；`verify` 是显式的全局完整门控别名，不与 `verify:quick`、当前变更 `verify:full` 叠加作为额外门控。全局文档任务检查使用 `npm run verify:docs:strict:all`。

不推荐常规使用 `git commit --no-verify`（仅限人工确认后的异常处理）。

---

## 11. 工具兼容 + 旧变更包迁移

- `.claude/`、`.agents/` 下命令和 Skill 是工具快捷入口，不得维护与本文件冲突的流程规则。
- `.agents/` 与 `.claude/` 的对应文件必须保持内容一致（忽略 CRLF/LF 行尾差异）；默认和 strict docs 都执行镜像检查。
- `/harness:fix` 支持 Level 1（不创建 OpenSpec change）。
- **现有活跃变更包**不自动删除或降级，继续按原约定处理或后续逐个评估迁移。新三级规则默认适用于新任务。

---

## 12. 架构约束（摘要）

详见 `harness/architecture.md`。

**分层方向**：SharedTypes(0)→Constants(1)→Utils(2)；FE Hooks(10)→Components(11)→Pages(12)；BE Repo(20)→Services(21)→Controllers(22)→Routes(23)。前后端仅通过 SharedTypes API 契约通信。

**文件**：≤250 行、命名导出、TS camelCase/PascalCase、Python snake_case。新增目录后更新 `harness/directory.md`。

**测试**：Utils/Repo/Services → 单元测试；Hooks/Components → Vitest+RTL；Pages/Routes → E2E；Controllers → 集成测试。

---

## 13. 任务完成标准

- lint:arch + typecheck 通过 / 针对本次修改的测试通过 / `git diff` 仅含预期变更
- Level 2：当前变更包的必选任务标记完成、受影响验证和 scoped strict docs 通过；Level 3：当前变更的 scoped full gate 和 Review 证据通过；全局发布/集中归档再增加 global full gate

---

## 14. 禁止事项

- ❌ 以文件数量或代码行数作为风险判断标准
- ❌ 不确定时自动扩大流程 / 在工具命令中独立定义流程规则
- ❌ 多个文件复制同一信息（用"详见 xxx"）/ 硬编码会变的数字
- ❌ 假设代码或 Spec 任一方天然正确 / 批量跳过测试

---

## 15. 文档索引

| 路径 | 用途 |
|------|------|
| `harness/iteration-guide.md` | 六步闭环详情（Level 3） |
| `harness/architecture.md` | 分层规则、依赖矩阵 |
| `harness/entropy-rules.md` | 归档门控、教训反哺（Level 3） |
| `harness/code-review-agent.md` | 审查维度和流程 |
| `harness/directory.md` | 目录结构 |
| `openspec/specs/` | 能力 spec |
| `openspec/specs/data-model.md` | 实体定义 |
