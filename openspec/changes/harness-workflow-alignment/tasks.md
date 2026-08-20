# Harness 工作流入口对齐

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: T023-T027 progressive context contract reconciled to openspec/specs/harness-workflow/spec.md; OpenSpec strict validation passed
manual_acceptance: N/A（仅治理文档与确定性检查脚本变化，无 UI、Word/PDF、桌面环境或真实业务流程）

## 目标

修正需求、Bug 和验证入口之间的流程分歧，保持轻量级别默认路径，同时避免活跃变更包重复、Level 2 门控遗漏和测试日志下钻过早。

## 任务

- [x] T001 在需求入口增加活跃变更包扫描、重叠范围处理和 Level 1/2/3 路由规则；验证：入口文档一致性检查。
- [x] T002 在 Bug 入口明确先关联已有活跃变更包，再按级别选择直接修复、tasks.md 或完整变更包；验证：入口文档一致性检查。
- [x] T003 对齐 Level 2 的 `verify:quick`、受影响模块测试和 scoped strict docs 门控，并保留纯样式/文案等低价值测试豁免；验证：治理测试和文档检查。
- [x] T004 将“先看汇总、失败再下钻”扩展到 pytest、Vitest、模块测试和完整门控子命令；验证：治理测试和文档检查。
- [x] T005 运行本变更的定向治理/文档验证，确认未修改业务代码且 Git 差异仅包含预期流程文件；验证：`npm run test:governance`、`npm run verify:docs:strict -- --change harness-workflow-alignment`、`git diff --check`。
- [x] T006 为活跃变更包持久化 `workflow_level`，并定义 Level 2 的 tasks + delta spec 固定工件；验证：scoped strict docs。
- [x] T007 在 `check-docs.ts` 增加范围化的 Level 2 delta、基本格式、历史 reconciled 例外和 `.agents`/`.claude` 镜像门控；验证：治理测试与 scoped strict docs。
- [x] T008 建立历史 Level 2 迁移台账，区分已完整同步、未同步和部分同步；明确 `case-shared-defaults` 与 `report-parsing-cache-management` 不重复造 Requirement；验证：台账核对。
- [x] T009 为历史未同步 Level 2 先写 delta，再按实际支持的 sync 流程合并 living spec；验证：living spec 检查与 delta 对照。
- [x] T010 保持 `.agents` 与 `.claude` 对应命令和 Skill 内容一致，并同步 Level 2 收尾规则；验证：镜像检查。
- [x] T011 定义候选冻结前的人工验收与反馈补丁节奏，避免在可预见的人工反馈前重复运行最终 Review/full gate；验证：delta spec 与 `harness/verification-strategy.md` 核对。
- [x] T012 新增完整门控环境预检，检查临时目录可写性、路径长度和可用空间，并在环境不满足时短路；子进程临时目录与 npm cache 统一指向预检根目录；验证：治理单元测试通过，系统临时盘低空间被预检正确拦截。
- [x] T013 将 `verify:full` 改为阶段摘要输出，失败时保留完整日志并只展示有限诊断尾部；验证：治理单元测试与 scoped dry-run 通过。
- [x] T014 保持 `AGENTS.md` 为精简规则入口，把候选冻结、预检和日志细则集中到 Harness 专用文档；验证：`AGENTS.md` 仅修改原有一行并增加文档引用。
- [x] T015 对照 delta 完成实现核对，运行 `test:governance`、scoped strict docs、typecheck 与 `git diff --check`，同步 living spec 后记录证据；验证：上述检查通过，scoped full gate 已验证预检、摘要输出及全量测试阶段，失败 build 按隔离复跑策略验证。
- [x] T016 Windows 未显式配置 `HARNESS_TEMP_ROOT` 时，默认使用项目所在卷根目录的短路径 `harness-temp-root`，按需创建目录，并保留显式覆盖优先级；同步验证策略和 living spec；验证：治理单元测试、预检实测、`verify:quick`、scoped strict docs 与 `git diff --check`。
  - 证据：未设置 `HARNESS_TEMP_ROOT` 时 `npm run verify:preflight` 输出 `temp="D:\\harness-temp-root"` 并通过；治理测试覆盖 Windows 项目盘默认值与显式覆盖优先级；typecheck、`verify:quick`、scoped strict docs 与 `git diff --check` 通过。
- [x] T017 将 Agent 工具镜像门控限定为 Git 管理且未忽略的命令/Skill 源，忽略本机 settings 与 provider 专用安装目录；保留对仓库单侧缺失或内容不一致的检测。文件：`.gitignore`、`scripts/check-docs.ts`、`scripts/check-docs-utils.ts`、治理测试及本变更 delta/living spec；验证：治理测试、`verify:quick`、scoped strict docs 与 `git diff --check`。
  - 证据：39 项本机/provider 漂移清零，`verify:quick` 全部通过；临时添加未忽略的单侧合成 Skill 时门控准确报告 1 项 `agent-tooling-mirror-drift`，移除后恢复 0 drift；delta 已同步到 living spec。
- [x] T018 扩大活跃变更包关联口径，并将局部低风险行为修复纳入 Level 1；变更归属不再自动决定增量验证强度。文件：`AGENTS.md`、`harness/iteration-guide.md`；验证：治理测试、文档检查与规则场景核对。
- [x] T019 将测试规则改为风险相称的验证证据，优先复用、修改或合并已有测试；Level 3 的完整 Review/full gate 仅在反馈收敛、候选冻结后统一执行。文件：`AGENTS.md`、`harness/verification-strategy.md`、`harness/architecture.md`、`harness/code-review-agent.md`；验证：规则一致性检查。
- [x] T020 对齐 Harness propose/apply/fix/verify 命令与 Skill 镜像，使工具入口只转发根规则和细则，不恢复“行为变化必加测试”或“Task 继承整包门控”的旧语义。文件：`.agents/commands/harness/`、`.claude/commands/harness/`、`.agents/skills/`、`.claude/skills/`；验证：Agent 工具镜像检查。
- [x] T021 将 `AGENTS.md` 控制在 250 行以内，并把超限从默认警告改为所有文档检查均阻断；补充 250/251 行边界治理测试。文件：`scripts/check-docs.ts`、`scripts/check-docs-utils.ts`、`scripts/check-docs-utils.test.ts`；验证：`npm run test:governance`。
- [x] T022 核对 delta 与最终规则，使用同步后的 living spec 记录关联、分级、验证和行数预算合同；运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change harness-workflow-alignment`、`git diff --check`。文件：`openspec/changes/harness-workflow-alignment/specs/harness-workflow/spec.md`、`openspec/specs/harness-workflow/spec.md`。
  - 证据：`AGENTS.md` 为 113 个物理行（逻辑计数含结尾换行 114，低于 250）；`npm run verify:quick` 与 `openspec validate harness-workflow-alignment --type change --strict --no-interactive` 通过；scoped strict docs 与 diff 检查见最终验证。
- [x] T023 将高频 Harness 入口改为渐进式上下文路由：普通 Level 1/2 不再预读完整迭代/架构文档，Level 3 按阶段加载。文件：`AGENTS.md`、`harness/iteration-guide.md`、`.agents/commands/harness/propose.md`、`.agents/commands/harness/apply.md`、`.agents/commands/harness/fix.md`、`.agents/commands/harness/verify.md` 及 `.claude` 镜像；验证：入口场景核对与镜像检查。
  - 证据：propose 常驻规则从修改前约 700 行降至 147 行，apply 从约 707 行降至 156 行（均不含任务源码/工件）；`verify:quick` 的镜像检查为 0 drift。
- [x] T024 增加默认治理门控，阻止高频入口恢复无条件全量预读，并覆盖合格、缺标记和旧式 MUST 预读边界。文件：`scripts/check-docs-utils.ts`、`scripts/check-docs-utils.test.ts`、`scripts/check-docs.ts`；验证：`npm run test:governance`。
  - 证据：治理单测与默认 `harness-context-loading` 检查通过；默认 docs 共 7 项检查、0 drift。
- [x] T025 以本次需求执行端到端流程审计，并静态核对 Level 1/2/3 三条路由实际会读取的资料和触发的门控。文件：`openspec/changes/harness-workflow-alignment/tasks.md`；验证：上下文行数对比、路由矩阵和实际命令记录。
  - 证据：窄化搜索命中本包 T018/T019/T023/T026，仅另有一个通用标题候选且业务范围不相关；本需求复用 `harness-workflow-alignment`、判定 Level 2，实际完成 tasks/delta、实现、治理定向测试、quick、sync 和 OpenSpec strict 路径。Level 1/2/3 读取与门控矩阵由四个高频入口及治理测试覆盖。
- [x] T026 核对最终行为并将渐进式上下文合同同步到 living spec。文件：`openspec/changes/harness-workflow-alignment/specs/harness-workflow/spec.md`、`openspec/specs/harness-workflow/spec.md`；验证：OpenSpec strict validation。
  - 证据：delta 与 living spec 已包含 Progressive Harness context routing 和 preserves quality gates；`openspec validate harness-workflow-alignment --type change --strict --no-interactive` 通过。
- [x] T027 运行 Level 2 正常收尾门控，并按用户要求额外执行一次 scoped full gate 质量审计；该额外全量审计不成为普通 Level 2 默认门控。文件：`package.json`、`openspec/changes/harness-workflow-alignment/tasks.md`；验证：`npm run verify:quick`、`npm run verify:docs:strict -- --change harness-workflow-alignment`、`npm run verify:full -- --change harness-workflow-alignment`、`git diff --check`。
  - 证据：`verify:quick` 通过；scoped strict docs 为 14 checks / 0 drifts；额外 scoped full gate 的 preflight、lint:arch、typecheck、governance、assets、全仓 test、build、scoped strict docs 全部 PASS（test 265.3s，build 22.9s）。沙箱内首次 preflight 因 `D:\harness-temp-root` 不可写而正确短路，在可写授权环境重跑通过；最终 OpenSpec 和 diff 检查见收尾命令。
- [x] T028 建立现有测试基线并按重复覆盖、执行耗时和日志噪音筛选第一批治理候选。文件：`tests/`、`packages/frontend/src/`、`packages/shared/`；验证：前后端全量收集与耗时报告。
  - 证据：基线为前端 60 个文件/387 条（94.37 秒）、后端 1226 条收集项（1213 通过、3 跳过；默认沙箱环境另有 10 项 SQLite 只读故障）；按重复职责和进程成本选取 3 组低风险候选，未删除 WinRAR 超时、恢复、安全、持久化或 Word/PDF 风险用例。
- [x] T029 将 `getCompletedTaskFileReferences` 回归迁回原生治理测试，删除启动 Node 子进程的重复 Python 包装测试。文件：`scripts/check-docs-utils.test.ts`；验证：`npm run test:governance`。
  - 证据：同一组未完成/已完成/代码块引用断言已在 TypeScript 原生调用中通过，不再由 pytest 为一个纯函数启动 Node 子进程。
- [x] T030 将四类合同漂移注入合并为一次检查器集成调用，同时保留无漂移通过路径。文件：`tests/test_check_contracts.py`；验证：定向 pytest 与诊断维度断言。
  - 证据：2 条定向测试通过；单次漂移运行同时断言 field-name、optionality、enum-values、error-code-set 及代表性详情，干净合同仍由独立运行验证。
- [x] T031 删除页面层重复覆盖的归档状态、进度导航和生命周期展示测试，保留对应组件合同与页面接线回归。文件：`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`、`packages/frontend/src/components/ArchiveDecisionPanel.test.tsx`、`packages/frontend/src/components/ArchiveStatusCard.test.tsx`、`packages/frontend/src/components/reviewWorkspaceComponents.test.tsx`；验证：相关前端测试。
  - 证据：相关 4 个前端文件 36 条全部通过；页面套件由 18 条/58.44 秒降至 14 条/37.89 秒，组件层仍覆盖决策状态、进度与归档结果展示，页面层保留保存、冲突、并发、导航、导出和盘号映射接线。
- [x] T032 运行治理、受影响前后端测试和工程门控，记录测试数量、耗时变化与未处理的高风险套件。文件：`openspec/changes/harness-workflow-alignment/tasks.md`；验证：定向测试、`npm run verify:quick`、前后端全量测试和 `git diff --check`。
  - 证据：前端全量 60 个文件/383 条通过，后端全量 1219 通过/3 跳过；Vitest+pytest 收集项由 1613 降至 1605（净减 8）。并发全量墙钟受资源竞争影响不作前后对比；剩余优先审计候选为页面/管理组件警告噪音、autosave 慢测试、portable/checker/Word 集成进程成本，当前批次不以合并安全矩阵来换取数量下降。
  - 收尾：`verify:quick`、OpenSpec strict、scoped strict docs、scoped full gate 与 `git diff --check` 全部通过；full gate 中全仓 test 282.1 秒、build 27.8 秒。
