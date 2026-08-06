# Tasks: 后台压缩与归档完成统一导出

workflow_level: 3

> Spec: `openspec/changes/background-compression-archive-completion/specs/electronic-inspection-record/spec.md`
> Design: `openspec/changes/background-compression-archive-completion/design.md`
> 范围：案件打开「立即/稍后」后台压缩触发（替换预览手动归档主路径）；压缩不阻塞审核；每 RAR 实时覆盖回填附件1/检查结果；盘号后填与顺序映射；归档完成态与导出路径提示；统一导出最新 Word + RAR + HashMyFiles 校验 HTML；已导出标记与彻底删除（复用 `case-workbench-delete`）。

## SharedTypes / SharedConstants（Layer 0–1）

- [x] T001 统一导出与盘号映射契约。
  - 文件：`packages/shared/types/archiveCompletion.ts`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`
  - 内容：新增统一导出请求/结果（导出路径、part 集合、HashMyFiles HTML 文件名）、盘号映射请求/结果、`ArchiveCompletionStatus` 派生状态投影（compressing/disc_pending/archive_complete/exported）、导出记录 DTO。
  - 设计细化（apply 阶段）：「待补盘号/归档完成」实现为派生状态投影（`archive_verified` + 盘号补齐标志），不新增 `CaseLifecycle` 枚举值，避免与 retention 包进行中的 v11 迁移冲突。
  - 验证：`pnpm --filter @biji/shared typecheck` 通过。

## BE Repository（Layer 20）

- [ ] T002 持久化盘号映射与每 part 元数据。
  - 文件：`packages/backend/app/repository/workbench_schema.py`（如需迁移）、归档/案件 repository
  - 内容：持久化 part→盘号映射、每 part 的文件名/大小/MD5、导出记录与已导出标记；遵守既有 revision/CAS 与迁移约束。
  - 验证：repository 定向测试；`npm run verify:quick` 的 schema/迁移检查。

## BE Services（Layer 21）

- [x] T003 允许无盘号执行压缩。
  - 文件：`packages/backend/app/services/archive_gate_policy_service.py`、`packages/backend/app/services/archive_execution_service.py`
  - 内容：`pre_archive_gate` 对空盘号放行（非空仍校验）；`execute_archive` 空盘号传 `None` 给 plan（`plan_archive` 已支持 None，仅按体积计算 part）。导出 gate 仍要求盘号（归档完成前必须补齐）。
  - 验证：归档相关测试回归（`tests/test_archive_execution_service.py` 等）。

- [x] T004 盘号映射服务。
  - 文件：新增 `packages/backend/app/services/disc_mapping_service.py`
  - 内容：`build_disc_mappings` 按序生成全序列；`apply_disc_mapping` 加载最新 plan，经 `archive_plan_repository.update_mappings` 持久化（mapping_revision + 1、CAS 防并发）。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed（序列顺序/非法盘号/持久化/过期 revision）。

- [x] T005 复用指纹与盘号解耦。
  - 文件：`packages/backend/app/services/archive_manifest_access_service.py`、`packages/backend/app/services/archive_execution_service.py`
  - 内容：`archive_report_fingerprint` payload 剔除 `first_disc_number`，两处调用同步；盘号后填/修改不破坏 Manifest 复用。
  - 验证：更新 `test_manifest_reuse_rechecks_input_snapshot_and_tolerates_disc_change`（盘号变化容忍、输入变化仍失败）；`tests/test_archive_execution_service.py` 20 passed。

- [x] T006 检查结果/附件1 回填服务。
  - 文件：新增 `packages/backend/app/services/attachment_backfill_service.py`
  - 内容：`backfill_from_manifest` 以 manifest parts 覆盖填写检查结果 `result`（rar_filename/md5_hash/file_size）并尽力投影附件1；WinRAR 分卷为批量产出、无逐卷事件，回填点取 manifest 组装时（比导出更早）。
  - 验证：`tests/test_attachment_backfill_service.py` 2 passed（覆盖旧值、审核字段不完整不失败）。

- [x] T007 HashMyFiles 校验 HTML 生成（接口+预留）。
  - 文件：新增 `packages/backend/app/repository/hashmyfiles_repository.py`、新增 `packages/backend/app/services/hashmyfiles_service.py`
  - 内容：受控接口 + `BIJI_HASHMYFILES_PATH` 配置；真实 exe 参数为 TODO(probe)，参数未配置时明确失败（HASHMYFILES_ARGUMENTS_NOT_CONFIGURED）；缺失工具明确失败。
  - 验证：`tests/test_hashmyfiles_service.py` 5 passed（resolve/不可用/runner 调用/无 parts）。

- [x] T008 统一导出编排。
  - 文件：新增 `packages/backend/app/services/unified_export_service.py`
  - 内容：盘号补齐校验（DISC_MAPPING_INCOMPLETE）+ 最新 Word（`generate_docx`）+ 复制全部 RAR + HashMyFiles HTML 写入导出路径；导出审计经 `AuditEventRepository`（不含绝对路径，符合资产策略）。
  - 验证：`tests/test_unified_export_service.py` 3 passed（成功包/盘号未补齐失败/分卷缺失失败）。

## BE Controllers / Routes（Layer 22–23）

- [x] T009 后台压缩触发与状态路由（既有能力确认）。
  - 文件：`packages/backend/app/services/archive_task_api_service.py`
  - 内容：「立即压缩」触发经既有 `WORKBENCH_ARCHIVE_DECISION` + 后台任务创建路径（enqueue）已存在；「待补盘号/归档完成/已导出」为 `ArchiveCompletionStatus` 派生投影，由前端按 lifecycle + 盘号补齐标志呈现。
  - 验证：`tests/test_workbench_controller.py`、`tests/test_archive_task*.py` 回归。

- [x] T010 盘号映射端点。
  - 文件：`packages/backend/app/services/archive_task_api_service.py`（map_disc_numbers）、`packages/backend/app/controllers/archive_task_controller.py`
  - 内容：`POST /workbench/cases/{id}/disc-mapping` 接收首个盘号，调用 `disc_mapping_service.apply_disc_mapping` 自动生成全序列并持久化；非法盘号/任务锁定映射返回稳定错误。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed + `tests/test_workbench_controller.py` 回归。

- [x] T011 统一导出端点。
  - 文件：新增 `packages/backend/app/services/archive_export_service.py`、`packages/backend/app/controllers/archive_task_controller.py`
  - 内容：`POST /workbench/cases/{id}/export-bundle` 解析 succeeded 任务 manifest/final_dir + 最新草稿报告 + 照片，调用 `unified_export_service` 写入导出路径；模板上下文由 Controller 解析传入（分层约束）；导出路径须绝对且存在。
  - 验证：`tests/test_unified_export_service.py` 3 passed + `tests/test_archive_task*.py`/`test_workbench_controller.py` 回归。

## FE Hooks（Layer 10）

- [ ] T012 案件打开压缩时机与状态 hook。
  - 文件：`packages/frontend/src/hooks/useArchivePreparation.ts`、`packages/frontend/src/hooks/usePreviewArchive.ts`、新增案件完成/统一导出 hook
  - 内容：案件打开呈现「立即/稍后」选择（替换审核页手动 prepare 主路径）；「待补盘号/归档完成/已导出」状态投影；盘号后填与映射请求；导出路径选择（native picker）与导出请求。
  - 验证：hook 定向测试（立即/稍后、后填映射、导出触发、状态投影）。

## FE Components / Pages（Layer 11–12）

- [ ] T013 案件卡片状态与操作。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/ArchiveStatusCard.tsx`
  - 内容：卡片「立即压缩/稍后压缩」入口；「待补盘号」中间态与补填入口；「归档完成」提示导出路径；「已导出」标记与「彻底删除」按钮（复用 `case-workbench-delete` 删除能力）。
  - 验证：组件定向测试（各状态渲染、操作触发、删除确认）。

- [ ] T014 案件打开页与工作台页集成。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`
  - 内容：案件打开时引导立即/稍后选择；审核编辑页与后台压缩解耦（不再阻塞）；导出路径引导与已导出状态展示。
  - 验证：页面定向测试 + 相关回归测试。

## 综合验证

- [ ] T015 受影响测试与 Level 3 门控。
  - 内容：核对 delta 与实现，运行受影响前后端测试、`npm run verify:quick`、变更包 scoped strict docs、`git diff --check`；HashMyFiles 集成通过一次性实测证据与 mock 测试覆盖。
  - 验证：`npm run verify:quick`、受影响模块测试、`npx tsx scripts/check-docs.ts --strict --change background-compression-archive-completion`、`git diff --check`。
