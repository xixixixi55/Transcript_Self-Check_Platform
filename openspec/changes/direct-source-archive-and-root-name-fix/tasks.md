# Tasks: 直接源报告归档与根目录修复

workflow_level: 3

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
  - 文件：`packages/backend/app/repository/winrar_executor_repository.py`、`tests/test_archive_executor_validator.py`、`tests/test_winrar_directory_structure_integration.py`
  - 内容：移除绝对快照路径分支；以源 parent 为 cwd、源 basename 为相对输入，真实 RAR listing/解压回归拒绝 `.i/s...` 和绝对路径泄漏。
  - 验证：执行器单元测试与本机真实 WinRAR 集成测试。

## 后端 Service（Layer 21）

- [x] T004 将归档编排改为直接源 inventory 与 WinRAR 前后变化门控。
  - 文件：`packages/backend/app/services/archive/archive_execution_service.py`、`packages/backend/app/repository/archive_input_repository.py`、`packages/backend/app/repository/archive_attempt_recovery_repository.py`、`packages/backend/app/repository/winrar_executor_repository.py`（执行模型现已收回唯一消费者）
  - 内容：新 attempt 不建立 sealed snapshot；WinRAR 直接使用 context inventory；成功返回后再校验 inventory，变化时清理 staging 并中止完整性/MD5/Manifest/发布。
  - 验证：`tests/test_archive_execution_service.py`、`tests/test_archive_runtime_lifecycle.py`、attempt 安全/恢复相关定向 pytest；核心分支执行断言有效性验证。

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

## 候选审查与验证

- [x] T006 冻结候选版本并执行独立 Code Review。
  - 文件：本变更全部实现与测试差异。
  - 验证：按 `harness/code-review-agent.md` 保留独立审查证据；若修改被审查源码、测试断言或行为，必须复审。
  - 证据：原直接源候选经修复后 PASS。人工验收补丁第 1/2 轮复审分别发现发布 TOCTOU、orphan queued 饥饿、task revision 污染和 never-leased 缺口；用户确认继续后第 3 轮复审 PASS，确认 publication snapshot + intent CAS、内部 context-binding lease、claim 清租约及各收敛路径闭合，无 MUST FIX。

- [x] T007 运行 Level 3 完整验证并记录人工验收。
  - 文件：`openspec/changes/direct-source-archive-and-root-name-fix/tasks.md`、`harness/archive/iterations/`中本轮迭代记录。
  - 验证：`npm run verify:full -- --change direct-source-archive-and-root-name-fix`、`git diff --check`；本机真实 WinRAR 测试验证原始根名，UI 人工验收根据自动化覆盖结果记录为通过或 N/A。
  - 证据：首次最终 scoped gate 的前端 279/279 通过，后端 969 通过、3 跳过、1 个长路径夹具环境边界失败；确定性修正经独立复审 PASS。最终 scoped gate 重跑的 preflight、lint:arch、typecheck、test:governance、check:repository-assets、test、build、verify:docs:strict 全部 PASS。真实 WinRAR listing/解压自动化已覆盖原始根名；人工验收已验证归档第 3 次成功，统一导出需在单实例重启后复测。
