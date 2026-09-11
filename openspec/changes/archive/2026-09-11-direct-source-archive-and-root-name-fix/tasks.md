# Tasks: 直接源报告归档与根目录修复

workflow_level: 3
lifecycle_status: ready-to-archive
spec_sync_status: reconciled
spec_sync_evidence: `openspec/specs/electronic-inspection-record/spec.md` 中的 REQ-012、REQ-ARCHIVE-IMMUTABLE-INPUT、REQ-ARCHIVE-PUBLICATION-GENERATION、REQ-ARCHIVE-MANIFEST-PROJECTION、REQ-ARCHIVE-ROOT-NAME、REQ-ARCHIVE-RUNTIME-OWNERSHIP 与 REQ-UNIFIED-EXPORT-TIMEOUT

> 规格：`openspec/changes/direct-source-archive-and-root-name-fix/specs/electronic-inspection-record/spec.md`
> 设计：`openspec/changes/direct-source-archive-and-root-name-fix/design.md`

## 前端组件（Layer 11）

- [x] T001 增加开始压缩确认与运行期源文件提示。
  - 文件：`packages/frontend/src/components/ArchiveDecisionPanel.tsx`、`packages/frontend/src/components/ArchiveDecisionPanel.test.tsx`
  - 内容：立即压缩前显示不修改/移动/删除/继续写入源目录的确认；`archive_queued`/`archiving` 持续显示警告，不提供“不再提示”。
  - 验证：Vitest + RTL 覆盖确认提交、取消不提交和运行期提示场景。

## 前端页面（Layer 12）

- [x] T002 将页面立即压缩动作接入确认交互。
  - 文件：`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`
  - 内容：仅在确认后调用 `decideArchive('immediate')`，取消保持原 lifecycle 且不发送请求。
  - 验证：页面定向测试覆盖首次、deferred 和 interrupted 重试入口。

## 后端 Repository（Layer 20）

- [x] T003 修复 WinRAR 输入根目录参数。
  - 文件：`packages/backend/app/repository/archive/winrar_executor_repository.py`、`tests/test_archive_executor_validator.py`、`tests/test_winrar_directory_structure_integration.py`
  - 内容：移除绝对快照路径分支；以源 parent 为 cwd、源 basename 为相对输入，真实 RAR listing/解压回归拒绝 `.i/s...` 和绝对路径泄漏。
  - 验证：执行器单元测试与本机真实 WinRAR 集成测试。

- [x] T011 解除工作台直出归档对全局 `output` Manifest 索引的依赖。
  - 文件：`packages/backend/app/repository/archive/archive_manifest_index_repository.py`、`archive_manifest_repository.py`、`archive_publish_intent_repository.py`、归档发布/恢复/结果服务及定向测试。
  - 内容：数据库参与的直出流程只读取 SQLite 持久发布事实，不读取、创建、锁定或重写 `output/compressed/.archive-manifest-index.json`；新直出的物理根写入既有 `publication_relative_dir` 内部字段并纳入 publication digest，结果/下载/统一导出不依赖位置 JSON 或 logical journal 目录；旧相对 intent 与无数据库流程保留兼容和失败关闭语义。
  - 验证：失败优先回归覆盖历史索引隔离；新增回归删除位置 JSON 与 logical journal 后重启仍可读取新直出，以及旧相对 intent 在 journal 已建、JSON 缺失时可由 SourceRecord 恢复。最终受影响后端 117 项、独立复审集合 214 项和 `npm run verify:quick` 均通过。

## 后端 Service（Layer 21）

- [x] T004 将归档编排改为单次直接源 inventory，并保留输出侧安全失败门控。
  - 文件：`packages/backend/app/services/archive/archive_execution_service.py`、`packages/backend/app/repository/archive/archive_input_repository.py`、`packages/backend/app/repository/archive/archive_attempt_recovery_repository.py`、`packages/backend/app/repository/archive/winrar_executor_repository.py`（执行模型现已收回唯一消费者）
  - 内容：新 attempt 不建立 sealed snapshot；WinRAR 直接使用 Worker 的唯一完整 inventory；已归档 `metadata-fingerprint-archive-path` 已覆盖早期“前后重复扫描”设计，当前不恢复第二次全目录枚举；WinRAR/输出校验观察到错误仍安全失败。
  - 验证：`tests/test_archive_execution_service.py` 明确锁定同一 attempt 不重复 inventory scan；`tests/test_archive_runtime_lifecycle.py`、attempt 安全/恢复相关定向 pytest 覆盖输出门控。

- [x] T005 保留历史 snapshot 恢复与清理兼容。
  - 文件：`packages/backend/app/services/archive/archive_attempt_recovery_reconciliation_service.py`（现已合并原 input snapshot recovery 内部实现）、案件删除相关测试
  - 内容：新 attempt 无 snapshot 时可完成/恢复；历史有 snapshot 记录仍仅由所有权验证路径清理，绝不删除外部源目录。
  - 验证：本轮不需修改历史快照清理代码；快照恢复、失败清理与案件删除定向 pytest 纳入 82 项后端定向回归并通过。

- [x] T008 修复压缩期间盘号自动保存导致阶段 8 发布失败。
  - 文件：草稿持久化、attempt 发布校验、归档执行服务及对应后端测试。
  - 内容：仅允许盘号派生字段热更新，并以最新有效盘号生成 Manifest；其他草稿变化继续安全失败，真实错误不得伪装为分卷损坏。
  - 验证：发布边界、草稿保存及执行服务定向测试覆盖 revision/fingerprint 同步、最新盘号 Manifest 和错误码保真。

- [x] T009 防止无进程 context 的 coordinator 抢占 queued task。
  - 文件：归档 coordinator/scheduler、`archive_runtime_context_lease_repository.py` 与运行时测试。
  - 内容：scheduler 支持 eligible task 集合，coordinator 仅领取本进程已注册 context 的任务；内部 context binding 短租约不改变公开 task revision，正常停止、初始注册失败、从未租约和过期租约均收敛为 interrupted。
  - 验证：scheduler 回归证明无本地 context 的首个任务保持 queued、后续 eligible 任务仍可领取；运行时测试覆盖续租后旧 revision 仍可取消、claim 清租约、双 coordinator 过期回收、初始租约失败、无租约崩溃和正常 stop。

- [x] T010 为统一导出配置专用长超时和明确错误提示。
  - 文件：shared constants、前端归档完成 hook、工作台错误文案及对应测试。
  - 验证：Hook/Page 测试断言仅统一导出使用 30 分钟超时；后端错误文案覆盖目录授权、路径、归档结果与生命周期失败。

- [x] T012 修复完整门控隔离缺口与归档任务详情撕裂快照。
  - 文件：`scripts/verify-full.ts`、`scripts/verify-full-utils.ts`、`scripts/check-docs-utils.test.ts`、`harness/verification-strategy.md`、`packages/backend/app/services/archive/archive_task_api_service.py`、`tests/test_archive_runtime_lifecycle.py`。
  - 内容：每次完整门控使用独立的临时应用数据根和工作台数据库根，不再读写真实用户数据或复用旧门控状态；归档任务详情从同一任务快照生成状态摘要与 revision，避免并发终态转换返回“新状态 + 旧 revision”。
  - 验证：隔离前相关诊断组出现路径安全拒绝和只读数据库错误，隔离后 15 项全部通过；撕裂快照测试修复前压力运行第 2 轮复现 `REVISION_CONFLICT`，修复后连续 20/20 轮通过；相关归档运行时、任务持久化、安全与执行测试 84 项通过，治理测试、TypeScript 类型检查和 scoped strict docs 通过。

## 候选审查与验证

- [x] T006 冻结候选版本并执行独立 Code Review。
  - 文件：本变更全部实现与测试差异。
  - 验证：按 `harness/code-review-agent.md` 保留独立审查证据；若修改被审查源码、测试断言或行为，必须复审。
  - 证据：T011 后统一复审首轮发现旧增量与现行单次 inventory 合同的 supersession 未显式记录、以及物理位置仍依赖 JSON；第一轮 remediation 后进一步发现 logical journal 目录依赖与旧相对 intent 恢复缺口；第二轮修复后独立复审 PASS、定向回归 214 项通过。T012 修改公开详情核心投影与验证 Harness 后重新复审，发现并修复 Windows 环境变量大小写绕过隔离的问题；最终独立复审 PASS，治理测试和类型检查均通过，无验收阻断。

- [x] T007 运行 Level 3 完整验证并记录人工验收。
  - 文件：`openspec/changes/direct-source-archive-and-root-name-fix/tasks.md`、`harness/archive/iterations/`中本轮迭代记录。
  - 验证：`npm run verify:full -- --change direct-source-archive-and-root-name-fix`、`git diff --check`；本机真实 WinRAR 测试验证原始根名，UI 人工验收根据自动化覆盖结果记录为通过或 N/A。
  - 证据：首次 scoped gate 因将 `HARNESS_TEMP_ROOT` 置于仓库内部触发导出路径安全拒绝；切换系统临时目录后又暴露完整门控未隔离真实工作台数据库的 Harness 缺口。T012 修复隔离和详情撕裂竞态后，最终 scoped gate 的 preflight、架构、类型、治理、资产、完整测试、构建与严格文档检查全部 PASS；候选最终独立复审 PASS，无验收阻断。真实 WinRAR listing/解压自动化继续覆盖原始根名；确认交互、取消与运行期提示由 RTL 覆盖，UI 人工验收记为 N/A。增量规格已同步至 living spec，OpenSpec 严格校验、全量 spec 校验和同步后 scoped strict docs 均通过。
