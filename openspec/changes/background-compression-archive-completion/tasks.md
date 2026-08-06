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

- [x] T002 持久化盘号映射与每 part 元数据。
  - 文件：`packages/backend/app/repository/workbench_schema.py`、`packages/backend/app/repository/archive_plan_repository.py`
  - 内容：`archive_plans` 表持久化 `mapping_revision`/`volume_slots_json`/`verified_slots_json`，`archive_plan_repository.update_mappings` 以 mapping_revision + 1 与 CAS 防并发持久化 part→盘号映射；每 part 文件名/大小/MD5 落在归档结果 parts 记录；导出记录经 `AuditEventRepository`（unified_export 事件）。遵守既有 revision/CAS 与迁移约束（含 v11 schema 同步）。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed（含持久化与过期 revision）+ 归档结果/导出审计相关测试回归。

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

- [x] T006 检查结果/附件1 回填（接线确认 + 死代码清理）。
  - 文件：`packages/backend/app/services/archive_attempt_completion_service.py`、`packages/backend/app/repository/archive_report_metadata_repository.py`
  - 内容：回填在归档 attempt 完成时经 `complete_verified` → `update_verified_draft` 接线：`verified_archive_result_fields` 以 manifest parts 覆盖填写检查结果 `result`（rar_filename/md5_hash/file_size），`attachment_projection` 投影附件1 extract_list，并更新草稿 lifecycle 为 `archive_verified`（revision CAS 保护）。WinRAR 分卷为批量产出、无逐卷事件，回填点在 attempt 完成（早于导出）。Review（T015）发现独立 `attachment_backfill_service.backfill_from_manifest` 是重复死代码，已删除。
  - 验证：`tests/test_archive_runtime_lifecycle.py` 断言草稿 inspection.result 与 extract_list 已回填（rar_filename/md5/file_size）。

- [x] T007 HashMyFiles 校验 HTML 生成（接口+实测固化）。
  - 文件：新增 `packages/backend/app/repository/hashmyfiles_repository.py`、新增 `packages/backend/app/services/hashmyfiles_service.py`
  - 内容：受控接口 + `BIJI_HASHMYFILES_PATH` 配置；缺失工具明确失败（HASHMYFILES_UNAVAILABLE）。
  - 实测（2026-08-06，本机 HashMyFiles v2.51）：`/files <多个路径>` + `/MD5 1 /SHA1 0 /CRC32 0 /SHA256 0 /SHA512 0 /SHA384 0` + `/shtml <输出路径>` 生成水平 HTML（UTF-16，含 Filename/MD5/Full Path 等列），保存后进程自动退出（returncode 0）；只开 MD5 时其余 hash 列头仍输出但值为空。`run_hashmyfiles` 据此实现，输出固定名 `hash-verification.html`（可重复导出覆盖），运行失败/输出缺失分别抛 HASHMYFILES_RUN_FAILED / HASHMYFILES_OUTPUT_MISSING（无路径泄漏）。
  - 验证：`tests/test_hashmyfiles_service.py` 8 passed（resolve/不可用/runner 调用/无 parts/参数构造/失败路径）+ 端到端真实 exe 生成验证。

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

- [x] T012 归档完成/盘号映射/统一导出 hook 与状态投影。
  - 文件：新增 `packages/frontend/src/hooks/useArchiveCompletion.ts`、新增 `packages/shared/utils/archiveCompletionRules.ts`
  - 内容：`useArchiveCompletion` 提供盘号映射（POST disc-mapping）与统一导出（POST export-bundle）动作与错误投影；`resolveArchiveCompletionStatus`/`allPartsDiscMapped` 派生卡片完成状态。
  - 验证：`useArchiveCompletion.test.tsx` 3 passed + `archiveCompletionRules.test.ts` 7 passed。

## FE Components / Pages（Layer 11–12）

- [x] T013 案件卡片完成状态、统一导出入口与彻底删除。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、新增 `packages/frontend/src/hooks/useArchiveCompletionStatuses.ts`
  - 内容：卡片显示「待补盘号/归档完成/已导出」徽标；「归档完成/已导出」时主按钮为「统一导出」（native picker 选目录 → export-bundle，**替换原「查看结果」**，用户确认完全替换）；「已导出」时菜单出现「彻底删除」（复用 `case-workbench-delete` 删除确认）；工作台经 `useArchiveCompletionStatuses` 自动加载归档结果派生完成状态（无需先点查看结果）。
  - 验证：`CaseCard.test.tsx` 15 passed（统一导出断言，查看结果移除）+ `CaseWorkbenchPage.test.tsx` 14 passed（含卡片直达统一导出流程）+ 全量前端 269 passed。

- [x] T014 案件打开页「立即/稍后」选择与补盘号入口。
  - 文件：`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、新增 `packages/frontend/src/components/ArchiveCompletionPanel.tsx`、`packages/backend/app/controllers/workbench_controller.py`（新增 `POST /workbench/select-export-directory`）、`packages/backend/app/services/local_directory_picker_service.py`（select 支持描述）、`packages/frontend/src/hooks/useArchiveCompletion.ts`（chooseDirectory）、`packages/shared/types/archiveCompletion.ts`（ExportDirectoryResult）、`packages/shared/constants/index.ts`
  - 内容：案件打开呈现「立即/稍后」选择（替换审核页手动 prepare 主路径）；「待补盘号」补填入口（输入首个盘号 → disc-mapping）。统一导出触发已移至工作台卡片（T013）；打开页保留补盘号与立即/稍后主路径。
  - 验证：`CaseRecordGeneratePage.test.tsx` 9 passed（含补填映射、导出触发、exported 再次导出）+ `useArchiveCompletion.test.tsx` 5 passed + `test_workbench_controller.py` 34 passed（含 select-export-directory 3 个新用例）。

## 综合验证

- [x] T015 受影响测试与 Level 3 门控。
  - 独立 Code Review（生成者/评估者分离）判定 FAIL，9 项 MUST FIX 全部验证属实并修复：
    - MF-1 空盘号压缩：`assemble_archive_manifest` 空盘号产出空 disc 元数据，`validate_manifest_files` 容忍双空。
    - MF-2 plan 落库：`archive_mapping_service.persist_archive_plan_for_attempt` 在 execute_archive 成功后按 manifest parts 投影 `archive_plans`（先填盘号带 confirmed mapping）。
    - MF-3 事实源统一：`archive_task_result_service.result()` 与导出 gate 从持久化 plan slots 派生 disc（plan 缺失回退 manifest），前端从「待补盘号」进入「归档完成」。
    - MF-4 exported 持久化：`CASE_TRANSITIONS` 增 `archive_verified→exported`；`export_bundle` 成功后 `update_lifecycle(exported)`。
    - MF-5 picker 超时：`EXPORT_DIRECTORY_PICKER_TIMEOUT_MS=620s`（后端 600s 上限）。
    - MF-6 回填接线：确认回填已由 `complete_verified→update_verified_draft` 接线，删除重复死代码 `attachment_backfill_service`，修正 design D3。
    - MF-7 伪造值：`apply_disc_mapping` 返回真实 lifecycle `archive_verified`，移除 `archive_disc_pending`。
    - MF-8 CAS 对齐：`map_disc_numbers` 校验 case revision，plan 写用 plan 自身 revision。
    - MF-9 路径受控：`select-export-directory` 签发一次性 grant token（复用 `issue_exact_directory_grant`），`export_bundle` 消费校验，未授权拒绝 `EXPORT_PATH_NOT_AUTHORIZED`。
  - 补端到端测试：`test_archive_execution_service`（空盘号压缩）、`test_archive_plan_persistence`（persist_archive_plan）、`test_workbench_persistence`（archive_verified→exported）、新增 `test_archive_export_service`（token 门控/exported 标记/DISC_MAPPING_INCOMPLETE）；HashMyFiles 默认随包位置回退（design D4）。
  - 复审（二轮）发现并修复 2 个回归：MUST-1 可重复导出被 MF-4 破坏（`CASE_TRANSITIONS["exported"]` 增自环，补二次迁移断言）；MUST-2 后填路径 Word 导出仍读原始空 disc manifest（`unified_export._with_disc_mapping` 把 plan slots 盘号叠加到 manifest 深拷贝供 `generate_docx`，补叠加测试）。复审最终 **CONDITIONAL PASS**（9 项 MUST FIX + 2 回归全部解决，无阻塞项）。
  - 实施后补充（用户实测反馈）：统一导出主按钮移至案件工作台卡片（替换「查看结果」，T013）；`useArchiveCompletionStatuses` 自动加载归档结果，卡片恒定派生完成态（移除"完成态需先点查看"的遗留限制）。归档 inventory 性能优化：`verify_input_inventory` 改 `check_readability=False`（可读性由 seal 复制兜底）并移除第二轮重复 stat，`build_input_inventory` 文件 stat/open 用 `ThreadPoolExecutor` 并行（新增 `archive_input_inventory_worker.py`）；基准 3000 文件 verify 5.3s→0.87s、build 4.5s→1.7s。
  - 遗留 SHOULD（不阻塞，已注明）：`execute_archive` 复用路径不重复落库 plan（首次成功已落库，复用时有 plan）；导出审计身份为 `system`（REQ-028 建议后续传真实会话）；重复导出 Word 因时间戳文件名累积；PATCH `/archive-plan` 的 `update_mappings` 用 plan revision 做 CAS（既有接口语义，与 POST `/disc-mapping` 的 case revision 校验不同，为既有设计非本包引入）。
  - 验证：`npm run verify:quick` ✅、后端全量 941 passed（1 个并发 flaky 测试确认非本改动，文件级/单测通过）、前端 269 passed、`npx tsx scripts/check-docs.ts --strict --change background-compression-archive-completion` ✅（0 drift）、`git diff --check`。
