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
- [x] T033 审计第二批高数量、高耗时和高噪音测试，确认仅合并已有风险覆盖而不压缩安全矩阵。文件：`tests/test_template_filler_service.py`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx` 及其组件/Hook 测试；验证：定向基线与职责映射。
  - 证据：检材渲染基线为 5 次 DOCX 生成/约 3.05 秒 call；工作台页面为 17 条/11.62 秒 call，并反复输出 Modal 废弃属性警告。安全、恢复、持久化、归档执行和文件校验矩阵未纳入删减候选。
- [x] T034 将 5 次检材渲染 DOCX 的测试合并为两次多检材渲染，保留已确认手机/平板标识符、类型后缀、未确认名称优先级和不可提取脱敏断言。文件：`tests/test_template_filler_service.py`；验证：定向 pytest 与耗时对比。
  - 证据：首次尝试单次渲染时，第 6 个检材被模板容量边界截断并导致断言失败；据此保留两次真实渲染。最终 2 条通过，call 合计约 1.23 秒，所有原有正向与脱敏反向断言仍在。
- [x] T035 删除工作台页面层重复验证的取消删除和重复导出 loading 场景，保留删除成功接线、导出成功接线、CaseCard 禁用/loading 合同与 Hook 请求合同；同时迁移 AntD Modal 的废弃属性以清除重复日志噪音。文件：`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`、`packages/frontend/src/components/CaseCardCompletion.test.tsx`、`packages/frontend/src/hooks/useArchiveCompletion.test.tsx`、`packages/frontend/src/components/ReviewPreviewDrawer.tsx`、`packages/frontend/src/components/WordDownloadNameDialog.tsx`；验证：相关前端测试与 typecheck。
  - 证据：工作台页面 17 条降至 15 条，call 约 11.62 秒降至 9.73 秒；相关页面、组件、Hook 与文件名对话框 32 条通过，typecheck 通过，`destroyOnClose` 警告清零。
- [x] T036 运行第二批定向、前后端全量和 scoped Harness 门控，记录累计测试数量与剩余候选。文件：`openspec/changes/harness-workflow-alignment/tasks.md`；验证：受影响测试、`npm run verify:quick`、前后端全量、scoped strict docs 与 `git diff --check`。
  - 证据：前端全量 60 个文件/381 条通过；后端全量 1216 通过/3 跳过。Vitest+pytest 收集项累计由最初 1613 降至 1600（两批净减 13）；第二批净减 5，且减少 3 次 DOCX 生成。剩余高价值候选为 autosave 的异步警告与等待、管理组件 mock 属性噪音、jsdom `getComputedStyle` 噪音及慢 portable/Word 集成进程，需逐组验证而不按数量批量删除。
- [x] T037 暂停 warning 治理，完成测试源文件、收集项、fixture/helper、模板二进制、动态生成资产、门控范围和维护热点盘点。文件：`openspec/changes/harness-workflow-alignment/test-assets-inventory.md`；验证：静态文件统计、pytest collect-only、Shared 显式 Vitest 与现有前后端全量结果交叉核对。
  - 证据：确认 168 个测试源文件/约 35,944 行；标准门控收集 1,600 条，另有 4 个 Shared 文件/12 条可通过但未纳入门控；识别 4 个产品/测试共用 DOCX、10 个 cross-test import consumer、19 个超 400 行测试文件以及无 E2E 资产的覆盖层级缺口。
- [x] T038 核对 Shared 4 个孤儿测试的生产调用和门控内重复覆盖，区分应迁移的风险断言与可删除的实现细节断言。文件：`packages/shared/utils/*.test.ts` 及受影响前端测试；验证：调用范围和现有测试映射。
  - 证据：下载命名、检材分组、数字文件名识别与位置错误已有 gated direct/UI/Hook 覆盖；来源标签、复杂排序和前导零位置解析需要迁移；`naturalEvidenceOrder` 与 `markFieldStateUserEdited` 无生产调用。
- [x] T039 将仍有价值的来源标签、自然排序和位置解析断言并入现有门控测试，删除无生产调用的工具及 4 个孤儿测试文件，不新增测试条目。文件：`packages/shared/utils/`、`packages/frontend/src/components/InspectorEditor.test.tsx`、`packages/frontend/src/components/ImageUploader.test.tsx`；验证：受影响前端测试与 typecheck。
  - 证据：7 个受影响前端文件/73 条定向测试通过，Frontend 全量 60 文件/381 条通过；Shared typecheck、Frontend typecheck 通过；`packages/shared` 测试文件清零。
- [x] T040 更新测试资产盘点并运行 Level 2 收尾门控，确认 Shared 孤儿测试清零、标准门控测试数不增加。文件：`openspec/changes/harness-workflow-alignment/test-assets-inventory.md`、`openspec/changes/harness-workflow-alignment/tasks.md`；验证：`verify:quick`、受影响前端测试、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：测试源文件 168→164、测试代码约 35,944→35,765 行、门控外测试 12→0；标准 Frontend 仍为 381 条，Backend 本轮未改。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在任务完成前准确拦截 T040，更新状态后复跑通过。
- [x] T041 建立 cross-test import consumer/provider 依赖表，并核对 Workbench、Record、Template Controller 大套件与 Service/Repository 层的重复职责；每个删除候选必须记录删除原因和替代覆盖。文件：`tests/`、`openspec/changes/harness-workflow-alignment/test-assets-inventory.md`；验证：静态依赖与测试职责映射。
  - 证据：确认 10 个 consumer、7 个 provider、13 条导入边；本批不改 provider。三个 Controller 基线 94 条中识别出 7 个可合并的重复 setup/映射收集项，逐项删除原因和替代覆盖已记录在测试资产盘点第 10 节。
- [x] T042 仅合并已证明由其他层或同套件等价覆盖的低风险测试，保留安全、权限、持久化、并发、恢复、归档生命周期和关键转换矩阵。文件：经 T041 确认的测试文件；验证：删除映射、定向 pytest 和收集项变化。
  - 证据：Record Controller 合并 5 个、Workbench Controller 合并 2 个收集项；8 条定向 Controller/Service/Repository 证据通过。Backend 全量 1,209 passed/3 skipped，收集项 1,219→1,212；删除原因和替代覆盖逐项记录在盘点第 10 节。
- [x] T043 运行受影响 Backend 全量与 Level 2 收尾门控，记录删减原因、测试数、耗时和剩余高风险候选。文件：`openspec/changes/harness-workflow-alignment/tasks.md`、`test-assets-inventory.md`；验证：Backend 全量、`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：Backend 全量 1,209 passed/3 skipped/37 warnings，183.10 秒；标准总收集项 1,600→1,593，本批测试代码约 35,765→35,723 行。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在本任务完成后复跑通过。剩余并发、归档、恢复和模板迁移高风险测试未删。
- [x] T044 建立 Word/DOCX 相关 Renderer、Generator、Profile、Customization 与 Filler 套件的生成调用、耗时和跨层职责基线；识别可合并候选但不触碰模板合法性、不可变性、脱敏、损坏和导出安全矩阵。文件：`tests/test_attachment_docx_renderer.py`、`tests/test_record_generator_service.py`、`tests/test_template_profile_service.py`、`tests/test_template_customization_service.py`、`tests/test_template_filler_service.py`；验证：定向 pytest durations 与调用映射。
  - 证据：5 个套件基线 84 passed/48.82 秒；附件一签名分页 7 个参数约 6.7 秒、Filler 图片回归 7 个参数约 6.8 秒、附件二固定网格 4 个参数约 3.7 秒。确认 5 个附件一数量已有同输入的更强专项渲染、两个三检材续页测试重复 6 图渲染、4 个图片几何组合已被纯几何与 Renderer 边界覆盖。
- [x] T045 仅合并已证明重复的 DOCX 生成过程或跨层实现断言；每个删除项记录原测试、删除原因、替代覆盖和保留风险。文件：经 T044 确认的测试文件、`test-assets-inventory.md`；验证：定向 pytest 与收集项/生成次数变化。
  - 证据：附件一重复数量渲染合并 5 项、三检材续页重复渲染合并 1 项、Filler 重复图片几何组合合并 4 项；定向套件 84→74 条、48.82→34.32 秒，减少 10 次真实 DOCX 生成。逐项删除原因和替代覆盖见盘点第 11 节。
- [x] T046 运行 Backend 全量与 Level 2 收尾门控，记录测试数、耗时和未删高风险套件。文件：`tasks.md`、`test-assets-inventory.md`；验证：Backend 全量、`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：Backend 全量 1,199 passed/3 skipped/37 warnings，162.52 秒；标准总收集项 1,593→1,583，定向 Word/DOCX 套件减少 10 次真实生成和约 14.5 秒。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在任务完成后复跑通过。奇数/损坏图片、模板 profile、不可变性、脱敏和正式导出门控保留。
- [x] T047 盘点 9 个子进程测试文件的启动次数、耗时和进程边界职责，排除 WinRAR 超时、Portable 完整性、安全资产检查和失败清理矩阵。文件：`tests/`；验证：静态 subprocess/runpy 映射与定向 pytest durations。
  - 证据：纠正静态口径为 15 个引用进程类型/API 的文件，其中 7 个实际启动外部进程；合同、模板脚本、Portable、Job Object、Phase1D 与真实 WinRAR 边界必须保留。可合并候选仅为 Python 架构提取器 9 次重复 CLI 启动。
- [x] T048 仅合并内部逻辑已有直接测试或同一进程可覆盖多个诊断的重复启动；每个删除项记录原测试、删除原因、替代覆盖和减少的进程次数。文件：经 T047 确认的测试文件、`test-assets-inventory.md`；验证：定向 pytest 与启动次数/收集项变化。
  - 证据：`_python_imports.py` 提取 CLI 与直接调用共用 `extract_files`；测试 9→4、进程启动 9→1。合同检查与模板脚本组合定向结果 18→13 passed、8.74→7.24 秒；5 个合并项的原因和替代覆盖见盘点第 12 节。
- [x] T049 运行 Backend 全量与 Level 2 收尾门控，记录测试数、耗时和保留的进程边界。文件：`tasks.md`、`test-assets-inventory.md`；验证：Backend 全量、`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：Backend 全量 1,194 passed/3 skipped/37 warnings，161.09 秒；标准总收集项 1,583→1,578，Python 架构测试减少 5 条并减少 8 次真实进程启动。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在任务完成后复跑通过。合同、模板确定性、Portable、进程所有权和真实 WinRAR 边界保留。
- [x] T050 盘点报告 Projection、Record Generator、Template Profile/Customization/Filler 的 cross-test helper 依赖、职责和耗时，确认 provider 删除风险与可合并候选。文件：相关 `tests/test_*.py`；验证：静态导入、调用和定向 pytest durations。
  - 证据：确认 report/template 链有 5 条 cross-test 导入边，来自 Legacy Projection report builder 与 Template Filler manifest builder；6 个相关套件原收集 60 条。Projection 单元、真实 DOCX、Profile 漂移、Customization allowlist 和 Controller 持久化/并发职责均不重复，唯一可合并项是 Generator 对同一 renderer handoff 的排序/脱敏与旧步骤迁移测试。
- [x] T051 将本批实际触及的共享 report/manifest builder 与 provider 测试解耦，并仅合并已证明跨层重复的测试；每个删除项记录原因和替代覆盖。文件：经 T050 确认的测试支持与套件、`test-assets-inventory.md`；验证：无相关 cross-test import、定向 pytest 与收集项变化。
  - 证据：共享 builder 迁入 `tests/synthetic_report_builders.py`，report/template 链 5 条 `test_*.py` 导入边清零；Generator 两个相同 handoff 测试合并为一个，排序、人员快照、UI 元数据清理和旧步骤精确迁移断言全部保留。相关套件 60→59 条，定向 59 passed/16 warnings/33.90 秒；删除原因与保留风险见盘点第 13 节。
- [x] T052 运行 Backend 全量与 Level 2 收尾门控，记录测试数、耗时和保留风险。文件：`tasks.md`、`test-assets-inventory.md`；验证：Backend 全量、`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：正常权限下 Backend 全量 1,193 passed/3 skipped/37 warnings，196.29 秒，收集项 1,197→1,196；标准总收集项 1,578→1,577。首次沙箱运行因默认 LocalAppData SQLite 仅有读取权限统一失败，未作为代码结果；同命令在正常权限下全绿。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在任务完成后复跑通过。
- [x] T053 盘点 parse-cache 与 case cleanup provider/consumer 的 cross-test helper、测试职责和耗时，排除缓存并发、安全路径、formal authority 与 fail-closed 矩阵。文件：相关 `tests/test_*.py`；验证：静态导入、调用映射、定向 pytest durations。
  - 证据：4 个套件基线 25 passed/5.93 秒；确认 2 条 cross-test 导入边。Parse-cache 13 条分别覆盖元数据命中、内容/候选变化、删除、旧缓存、并发代际与路径安全，全部保留；cleanup 仅发现两个同状态重复完整 setup 的可合并项。
- [x] T054 将共享 parse-cache/cleanup setup 迁入非测试支持模块，并仅合并同一状态下重复 setup 的测试；逐项记录删除原因和替代覆盖。文件：经 T053 确认的测试支持与套件、`test-assets-inventory.md`；验证：相关 cross-test import 清零、定向 pytest 与收集项变化。
  - 证据：parse-cache tree builder 与 tombstone setup 已迁入非测试支持模块，本批 2 条 cross-test 导入清零，全仓剩余 6 条均属于暂不触碰的 Phase1D 链。成功 tombstone 后的编辑拒绝与重启证据合并、deployment scope 与异 deployment lease 证据合并；全部异常码、formal fact、重启和隔离断言保留。相关套件 25→23 条，定向 23 passed/8.33 秒；耗时受环境波动未宣称下降，明确减少 2 次完整 setup。逐项原因见盘点第 14 节。
- [x] T055 运行 Backend 全量与 Level 2 收尾门控，记录测试数、耗时和保留风险。文件：`tasks.md`、`test-assets-inventory.md`；验证：Backend 全量、`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check`。
  - 证据：Backend 全量复跑 1,191 passed/3 skipped/37 warnings，168.35 秒，收集项 1,196→1,194；标准总收集项 1,577→1,575。首次全量仅既有 archive runtime revision 时序用例失败，单独复跑通过且第二次全量未复现，未修改该链。`verify:quick`、OpenSpec strict 与 `git diff --check` 通过；scoped strict docs 在任务完成后复跑通过。
