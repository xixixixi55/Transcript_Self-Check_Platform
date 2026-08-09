# Tasks: 后台压缩与归档完成统一导出

workflow_level: 3

> Spec: `openspec/changes/background-compression-archive-completion/specs/electronic-inspection-record/spec.md`
> Design: `openspec/changes/background-compression-archive-completion/design.md`
> 范围：案件打开「立即/稍后」后台压缩触发（替换预览手动归档主路径）；压缩不阻塞审核；每 RAR 实时覆盖回填附件1/检查结果；盘号后填与顺序映射；归档完成态与导出路径提示；统一导出最新 Word + RAR + HashMyFiles 校验截图；已导出标记与彻底删除（复用 `case-workbench-delete`）。

## SharedTypes / SharedConstants（Layer 0–1）

- [x] T001 统一导出与盘号映射契约。
  - 文件：`packages/shared/types/archiveCompletion.ts`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`
  - 内容：新增统一导出请求/结果（导出路径、part 集合、HashMyFiles 校验产物文件名）、盘号映射请求/结果、`ArchiveCompletionStatus` 派生状态投影（compressing/disc_pending/archive_complete/exported）、导出记录 DTO；产物最终由 T022 调整为 PNG 截图。
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

- [x] T007 HashMyFiles 校验结果生成（原 HTML 接口，发布产物由 T022 替换为 PNG）。
  - 文件：新增 `packages/backend/app/repository/hashmyfiles_repository.py`、新增 `packages/backend/app/services/hashmyfiles_service.py`
  - 内容：受控接口 + `BIJI_HASHMYFILES_PATH` 配置；缺失工具明确失败（HASHMYFILES_UNAVAILABLE）。
  - 实测（2026-08-06，本机 HashMyFiles v2.51）：`/files <多个路径>` + `/MD5 1 /SHA1 0 /CRC32 0 /SHA256 0 /SHA512 0 /SHA384 0` + `/shtml <输出路径>` 生成水平 HTML（UTF-16，含 Filename/MD5/Full Path 等列），保存后进程自动退出（returncode 0）；只开 MD5 时其余 hash 列头仍输出但值为空。`run_hashmyfiles` 据此实现，输出固定名 `hash-verification.html`（可重复导出覆盖），运行失败/输出缺失分别抛 HASHMYFILES_RUN_FAILED / HASHMYFILES_OUTPUT_MISSING（无路径泄漏）。
  - 验证：`tests/test_hashmyfiles_service.py` 8 passed（resolve/不可用/runner 调用/无 parts/参数构造/失败路径）+ 端到端真实 exe 生成验证。

- [x] T008 统一导出编排。
  - 文件：新增 `packages/backend/app/services/unified_export_service.py`
  - 内容：盘号补齐校验（DISC_MAPPING_INCOMPLETE）+ 最新 Word（`generate_docx`）+ 复制全部 RAR + HashMyFiles 校验产物写入导出路径；T022 将产物更新为 PNG 截图；导出审计经 `AuditEventRepository`（不含绝对路径，符合资产策略）。
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

- [x] T016 修复归档完成后统一导出 REVISION_CONFLICT（回归）。
  - 现象：案件工作台归档完成（`archive_verified`）卡片点「统一导出」恒报 409 `REVISION_CONFLICT`「案件已被其他会话修改，请重新读取后再导出。」。
  - 根因 1：`POST /workbench/cases/{id}/export-bundle` 把卡片持有的 **shell revision**（`expected_revision`）传给 `resolve_case_template_context`，后者按 **draft revision** 校验；shell 与 draft 是各自独立的乐观并发计数器，经归档生命周期合法分叉（`prepare` 置 `archive_queued` 时 shell +1 而 draft 不变，`complete_verified_attempt` 再各自 +1），实测归档完成后 shell=4、draft=2，故导出恒被拒。
  - 根因 2（被根因 1 掩盖的潜在 bug）：`archive_export_service.export_bundle` 与 `_resolve_photo_paths` 读 `draft["report_json"]`，但 `CaseDraftRepository.get` 返回投影 `report`（无 `report_json`），真实仓库下必然 KeyError；既有 `test_archive_export_service` 用 mock 遮蔽了该错位。
  - 修复：`resolve_case_template_context` 增 `require_current_revision: bool = True` 参数；`export-bundle` 端点传 `False`（导出并发守卫由 `export_bundle` 内 shell revision CAS 承担，模板上下文仍按最新草稿解析）；`archive_export_service` 两处改读 `draft["report"]` 并移除无用 `json` import。Legacy `/records/export` 仍传 draft revision，`require_current_revision` 默认保持原校验，行为不变。
  - 文件：`packages/backend/app/controllers/record_template_context_controller.py`、`packages/backend/app/controllers/archive_task_controller.py`、`packages/backend/app/services/archive_export_service.py`、`tests/test_archive_export_service.py`（mock 更新）、`tests/test_archive_runtime_lifecycle.py`（新增端到端回归）。
  - 测试：新增 `test_export_bundle_succeeds_after_archive_completion_when_revisions_differ` 走真实运行时链路（案件→归档完成→export-bundle 200 且 lifecycle=exported，并断言 `shell.revision != draft.revision`）。验证：后端全量 942 passed、前端相关 36 passed、`npm run verify:quick` ✅、`npx tsx scripts/check-docs.ts --strict --change background-compression-archive-completion` ✅（0 drift）。

- [x] T017 软件工具条目 python hashlib → HashMyFiles 2.51（人工验收反馈）。
  - 现象：审核编辑界面的「软件工具」仍显示 Python hashlib；MD5 校验实际已改用 HashMyFiles.exe。
  - 决策：新解析案件显示 "HashMyFiles 2.51"（带版本）；存量案件保留旧值，识别逻辑新旧兼容；只影响新案件。
  - 修复：`report_parser_service._build_software_tools` 注入条目改为 `category=hashmyfiles / name=HashMyFiles / version=2.51`（版本常量 `HASHMYFILES_DISPLAY_VERSION` 定义于 `hashmyfiles_repository.py`）；识别点全部新旧兼容：`software_policy_service`（`_RUNTIME_TOOL_NAMES` + category 映射）、`attachment_plan_service`（归档工具来源查询）、`canonical_models_service`（SoftwareCategory Literal 增 `hashmyfiles`）、`canonical_adapter_service`（投影过滤）、`canonical.ts`、`softwareProjectionUtils.ts`（前端运行时工具过滤）。`report_parser_service` 移除不再使用的 `sys` import。
  - 文件：`packages/backend/app/repository/hashmyfiles_repository.py`、`packages/backend/app/services/report_parser_service.py`、`software_policy_service.py`、`attachment_plan_service.py`、`canonical_models_service.py`、`canonical_adapter_service.py`、`packages/shared/types/canonical.ts`、`packages/shared/utils/softwareProjectionUtils.ts` + 对应测试与 living spec（`openspec/specs/electronic-inspection-record/spec.md`、`openspec/specs/data-model.md`）。
  - 测试：`test_report_parser_service`（HashMyFiles/2.51 断言）、`test_software_policy_service`（新增 HashMyFiles runtime tool 投影）、`test_attachment_plan_service`（HashMyFiles 满足归档工具来源）、前端 `softwareProjectionUtils.test`（HashMyFiles 保留为 runtime tool）。验证：后端相关 162 passed、前端相关通过。

- [x] T021 存量案件软件工具展示统一为 HashMyFiles 2.51（人工验收反馈）。
  - 现象：T017 仅修改新解析案件，已有草稿仍在审核编辑界面显示 `Python hashlib 3.11.0`，与当前实际校验工具不一致。
  - 决策：案件详情与正式导出均把旧条目投影为 `HashMyFiles 2.51`；底层迁移识别继续兼容 `python hashlib` / `python_hashlib`，无需批量改写数据库。
  - 文件：`packages/backend/app/services/software_policy_service.py`、`case_lifecycle_service.py`、`archive_export_service.py`、`tests/test_software_policy_service.py`、`tests/test_workbench_controller.py`、`tests/test_archive_export_service.py`、delta spec 与 living spec。
  - 测试：`test_legacy_hashlib_runtime_tool_is_projected_as_hashmyfiles` 锁定规范化规则；`test_case_detail_projects_legacy_hashlib_as_hashmyfiles` 锁定存量案件详情展示接线；`test_export_bundle_marks_shell_exported_after_success` 锁定正式导出投影。

- [x] T018 统一导出先填 Word 文件名再选导出目录（人工验收反馈）。
  - 现象：工作台卡片点「统一导出」直接弹目录选择器，无 Word 文件名输入框；仅在审核编辑界面的「导出 Word」有文件名框。
  - 决策：点「统一导出」→ 先弹 Word 文件名输入框（默认案件名称，每次导出都询问）→ 再选导出目录 → 导出用该文件名；审核页 `ArchiveCompletionPanel` 的「开始导出/再次导出」同步走文件名→目录流程（默认文号）。
  - 修复（后端）：`UnifiedExportRequest`（shared + Pydantic）增必填 `word_filename`；`export_bundle`/`unified_export`/`_export_word` 透传；`record_generator_service.generate_docx` 增可选 `output_filename`（`_sanitize_docx_filename` 剥离路径前缀/非法字符、补 `.docx`），未传时保持原有文号+时间戳自动命名（Legacy `/records/export` 不变）。
  - 修复（前端）：`CaseWorkbenchPage` 点「统一导出」先开 `WordDownloadNameDialog`（默认案件名称），确认后走目录选择器→exportBundle；`useArchiveCompletion.exportBundle` 增 `word_filename` 参数；`ArchiveCompletionPanel` 增 `defaultWordName` 并让导出先问文件名（未选目录时自动补选）。
  - 文件：`packages/shared/types/archiveCompletion.ts`、`packages/backend/app/controllers/archive_task_controller.py`、`services/archive_task_api_service.py`、`archive_export_service.py`、`unified_export_service.py`、`record_generator_service.py`、`packages/frontend/src/hooks/useArchiveCompletion.ts`、`pages/CaseWorkbenchPage.tsx`、`pages/CaseRecordGeneratePage.tsx`、`components/ArchiveCompletionPanel.tsx` + 对应测试。
  - 测试：`test_unified_export_service`（word_filename 透传 + 落盘）、`test_archive_export_service`（export_bundle 传 word_filename）、`test_record_generator_service`（output_filename 生效/清洗）、`test_archive_runtime_lifecycle` 端到端（export-bundle 带 word_filename 200 且输出文件名正确）、前端 `CaseWorkbenchPage`/`CaseRecordGeneratePage`/`useArchiveCompletion` 均按新流程断言。验证：后端相关 23 passed、前端相关 31 passed、typecheck ✅。

- [x] T019 修复已导出案件再次导出 422 EXPORT_PATH_NOT_AUTHORIZED（回归）。
  - 现象：已导出成功的案件再次点「导出/再次导出」，`export-bundle` 返回 422。
  - 根因：`ArchiveCompletionPanel` 缓存了首次导出的 `exportPath/directoryToken`；目录授权 token 是一次性（`consume_exact_directory_grant` 消费后标记 used），二次导出复用已消费 token → `EXPORT_PATH_NOT_AUTHORIZED` → 422。工作台卡片路径每次 `chooseDirectory()` 新开选择器，不受影响；复现：同一 token 二次 export-bundle 返回 422 EXPORT_PATH_NOT_AUTHORIZED。
  - 修复：`ArchiveCompletionPanel` 移除缓存的 `exportPath/directoryToken` 状态与「选择导出目录」按钮，`confirmExportName` 每次导出都重新 `chooseDirectory()` 获取新 token（先填文件名→再选目录→导出），与工作台卡片行为一致。
  - 文件：`packages/frontend/src/components/ArchiveCompletionPanel.tsx`、`tests`（`CaseRecordGeneratePage.test.tsx` 更新：删除选择目录按钮依赖，新增「fresh grant on every export」断言）。
  - 测试：前端 `CaseRecordGeneratePage`/`CaseWorkbenchPage`/`useArchiveCompletion` 28 passed；`verify:quick` ✅、`lint:arch` ✅。

- [x] T020 修复原生目录选择器窗口概率性被浏览器遮挡（人工验收反馈）。
  - 现象：「上传报告目录」「统一导出」的 Windows 原生目录选择器（PowerShell `FolderBrowserDialog`）概率性出现在浏览器窗口后面而不可见。
  - 根因：对话框由后台服务进程弹出，未获得前台焦点/置顶，Windows 前台锁使对话框 Z 序可能落在浏览器之下。
  - 修复：`local_directory_picker_service._folder_picker_script` 为 `FolderBrowserDialog` 挂一个隐藏的 TopMost 所有者窗体（`$owner.TopMost = $true; ShowInTaskbar=$false; Opacity=0`），以 `ShowDialog($owner)` 展示——TopMost 使对话框 Z 序恒高于浏览器等非 TopMost 窗口，保证可见可点。
  - 文件：`packages/backend/app/services/local_directory_picker_service.py`、`tests/test_local_directory_picker_service.py`（断言含 TopMost owner + ShowDialog($owner)）。
  - 验证：本机 PowerShell 冒烟（对话框成功打开阻塞、无语法错误）；`test_local_directory_picker_service` 5 passed；后端全量 946 passed；`verify:quick` ✅。

- [x] T022 HashMyFiles 校验 HTML 替换为三列 PNG 界面截图（人工验收反馈）。
  - 需求：统一导出不再发布 HTML，改为 HashMyFiles 风格 PNG 截图；每个 RAR 一行，只显示 Filename、MD5、File Size (Bytes)。
  - 决策：HashMyFiles.exe 仍是 MD5 事实来源；调用其 `/shtml` 生成仅供进程内解析的临时结果，校验文件名/MD5/字节大小完整性后，用受控 PowerShell `System.Drawing` 离屏渲染 PNG。临时 HTML、JSON、脚本均不进入导出包并在结束时清理，避免依赖交互式桌面会话截图。
  - 文件：`packages/backend/app/repository/hashmyfiles_repository.py`、`services/hashmyfiles_service.py`、`unified_export_service.py`、`archive_export_service.py`、`controllers/archive_task_controller.py`、`packages/shared/types/archiveCompletion.ts`、`packages/frontend/src/components/ArchiveCompletionPanel.tsx`、相关测试与 OpenSpec 文档。
  - 验证：后端受影响测试 48 passed，前端受影响测试 34 passed；导出端点覆盖结果缺失、结果不完整与截图失败的具体错误提示且均不进入 exported；失败发布保留旧截图并清理临时文件；关键数据转换突变验证有效；`verify:quick` 通过。本机真实 HashMyFiles 对中文文件名、多分卷及带千位分隔的字节大小生成 PNG 成功，视觉确认仅含 Filename、MD5、File Size (Bytes)，导出目录无 HTML/JSON/脚本残留。

- [x] T023 校验 PNG 改为真实 HashMyFiles.exe 窗口截图（人工验收反馈）。
  - 现象：T022 的离屏仿制界面使用替代图标，标题栏、工具栏颜色和控件样式与用户实际打开的 HashMyFiles 不一致。
  - 决策：移除仿制窗口绘制；用独立临时 `/cfg` 启动真实 HashMyFiles，读取原生 ListView 并核对待发布 RAR 的文件名、完整 32 位 MD5 与字节大小，通过 Windows 消息只保留 Filename、MD5、File Size 三个可见列并清除选中高亮，再用 `PrintWindow` 捕获真实窗口。进程纳入 KILL_ON_JOB_CLOSE Job Object，临时配置不修改用户个人设置，超时或完成后均清理。完整导出改为同卷暂存并带回滚发布，截图失败保留上一版完整包。
  - 文件：`packages/backend/app/repository/hashmyfiles_repository.py`、`packages/backend/app/services/unified_export_service.py`、`tests/test_hashmyfiles_service.py`、`tests/test_unified_export_service.py`、变更包 design/delta spec 与 living spec。
  - 验证：真实 HashMyFiles v2.51 对两个中文合成 RAR 截图成功，原生彩色工具栏、完整 32 位 MD5、字节大小和三列布局均经视觉确认，截图后 HashMyFiles 进程残留为 0；受影响目标测试 42 passed，独立 Code Review PASS，`verify:quick` 与 `git diff --check` 通过。

- [x] T024 修复目录选择器置顶误判 422，并让上传报告与统一导出分别记忆目录（人工验收回归）。
  - 现象：T020 的隐藏 TopMost owner 仍可能被浏览器覆盖；首轮 T024 使用 PowerShell WinForms Timer + `GetLastActivePopup` 检测置顶，但真实环境在用户成功选择后仍因状态未回写而退出 21，前端收到 422「本机文件夹选择未完成」。上传报告目录也未记忆上次选择。
  - 内容：把窗口枚举与 TopMost 重试移入独立 C# 后台线程，避免依赖 PowerShell 模态调用期间的 Timer 回调；不再把合法选择事后降级为 422。上传报告与统一导出使用独立历史键，分别默认定位到各自上次成功选择的有效目录；取消、失效和损坏安全回退。
  - 文件：`packages/backend/app/repository/local_directory_history_repository.py`、`packages/backend/app/services/local_directory_picker_service.py`、`packages/backend/app/services/workbench_factory_service.py`、`packages/backend/app/controllers/workbench_controller.py`、对应后端测试与本变更包文档。
  - 验证：目录历史与 picker/controller 定向 pytest、PowerShell 脚本解析及内嵌 C# 编译、架构检查、类型检查、独立 Code Review 与当前变更 scoped full gate；真实浏览器前台下分别验收上传报告和统一导出的窗口 Z 序及再次打开默认目录。
  - 证据：窗口提升改由嵌入 C# 后台线程按独立 PowerShell PID 枚举可见窗口并持续重试 TopMost；未确认置顶只记录安全 warning，不再把合法选择降级为 422。report/export 双历史使用进程级写锁、同目录临时文件与原子替换，兼容首轮 T024 的旧 export 偏好。定向 pytest 51 passed，PowerShell 脚本解析与内嵌 C# 编译、架构及类型检查通过；独立 Code Review 与复审均 PASS（无 MUST FIX）；`npm run verify:full -- --change background-compression-archive-completion` 的预检、架构、类型、治理、资产、全仓库测试、构建与严格文档检查全部 PASS。用户已完成人工验收，确认上传报告目录与统一导出的 Windows 选择器位于浏览器前方、操作正常，且两个入口能够分别记忆上次成功选择的目录。

- [x] T025 修复附件1提取方式展示、盘号持续可编辑与单独 Word 导出盘号误判（人工验收回归）。
  - 现象：审核编辑附件1的提取方式为空但 Word 有值；归档完成后首盘号输入消失；分卷映射已存在时单独导出 Word 仍报 `FIRST_DISC_NUMBER_MISSING`。
  - 内容：附件投影兜底路径与前端历史空值展示按 Word 的硬件语义补齐提取方式，展示兜底不因其他列编辑而写回；归档完成/已导出状态保留首盘号编辑并用 plan 行 revision 做 CAS 后整体重映射，成功后显式重读归档结果刷新完成态与分卷；`/records/export` 携带 `case_id` 时以当前 plan 为事实源，只有全部 active slot 均 confirmed 才叠加首盘号，存在 pending/部分映射时清空客户端兼容字段并由门控拒绝。
  - 文件：`packages/shared/types/archiveTask.ts`、`archiveCompletion.ts`；`packages/backend/app/services/archive_manifest_projection_service.py`、`disc_mapping_service.py`、`archive_task_api_service.py`、`archive_task_result_service.py`、`unified_export_service.py`、`packages/backend/app/controllers/archive_task_controller.py`、`record_controller.py`、`record_template_context_controller.py`；`packages/frontend/src/components/ExtractListEditor.tsx`、`ReviewAttachmentsSection.tsx`、`ArchiveCompletionPanel.tsx`、`RecordEditorForm.tsx`、`packages/frontend/src/hooks/useArchiveCompletion.ts`、`useCompletedArchiveResult.ts`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及对应测试。
  - 验证：附件投影、盘号映射、单独/统一导出后端定向测试通过（相关组合 12 passed、14 passed，最终复审修正组合 8 passed）；附件编辑器、盘号组件与页面前端测试通过（最终组合 2 files / 19 passed）；TypeScript 类型检查与 `git diff --check` 通过。独立 Code Review 两轮发现的 MUST FIX（plan revision CAS、展示兜底不写回、confirmed 约束、pending 客户端字段旁路、映射后结果刷新）均修复，最终复审 **PASS**、无 MUST FIX。`npm run verify:full -- --change background-compression-archive-completion` 的预检、架构、类型、治理、资产、全仓测试、构建与严格文档检查全部 PASS。
