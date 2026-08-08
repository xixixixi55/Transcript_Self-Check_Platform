# Harness 工作流入口对齐

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: T011-T014 implemented; delta synchronized to openspec/specs/harness-workflow/spec.md

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
