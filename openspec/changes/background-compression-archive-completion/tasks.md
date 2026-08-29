# Tasks: 后台压缩与归档完成统一导出

workflow_level: 3

> 规格：`openspec/changes/background-compression-archive-completion/specs/electronic-inspection-record/spec.md`
> 设计：`openspec/changes/background-compression-archive-completion/design.md`
> 范围：案件打开「立即/稍后」后台压缩触发（替换预览手动归档主路径）；压缩不阻塞审核；每 RAR 实时覆盖回填附件1/检查结果；盘号后填与顺序映射；归档完成态与导出路径提示；统一导出最新 Word + RAR（T050 起不再生成 HashMyFiles 截图，底层能力保留）；已导出标记与删除案件（复用 `case-workbench-delete`）。

## 共享类型/共享常量（Layer 0–1）

- [x] T001 统一导出与盘号映射契约。
  - 文件：`packages/shared/types/archiveCompletion.ts`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`
  - 内容：新增统一导出请求/结果（导出路径、part 集合、HashMyFiles 校验产物文件名）、盘号映射请求/结果、`ArchiveCompletionStatus` 派生状态投影（compressing/disc_pending/archive_complete/exported）、导出记录 DTO；产物最终由 T022 调整为 PNG 截图。
  - 设计细化（apply 阶段）：「待补盘号/归档完成」实现为派生状态投影（`archive_verified` + 盘号补齐标志），不新增 `CaseLifecycle` 枚举值，避免与 retention 包进行中的 v11 迁移冲突。
  - 验证：`pnpm --filter @biji/shared typecheck` 通过。

## 后端 Repository（Layer 20）

- [x] T002 持久化盘号映射与每 part 元数据。
  - 文件：`packages/backend/app/repository/workbench_schema.py`、`packages/backend/app/repository/archive_plan_repository.py`
  - 内容：`archive_plans` 表持久化 `mapping_revision`/`volume_slots_json`/`verified_slots_json`，`archive_plan_repository.update_mappings` 以 mapping_revision + 1 与 CAS 防并发持久化 part→盘号映射；每 part 文件名/大小/MD5 落在归档结果 parts 记录；导出记录经 `AuditEventRepository`（unified_export 事件）。遵守既有 revision/CAS 与迁移约束（含 v11 schema 同步）。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed（含持久化与过期 revision）+ 归档结果/导出审计相关测试回归。

## 后端 Service（Layer 21）

- [x] T003 允许无盘号执行压缩。
  - 文件：`packages/backend/app/services/archive/archive_execution_service.py`（现已合并原 archive gate policy 内部实现）
  - 内容：`pre_archive_gate` 对空盘号放行（非空仍校验）；`execute_archive` 空盘号传 `None` 给 plan（`plan_archive` 已支持 None，仅按体积计算 part）。导出 gate 仍要求盘号（归档完成前必须补齐）。
  - 验证：归档相关测试回归（`tests/test_archive_execution_service.py` 等）。

- [x] T004 盘号映射服务。
  - 文件：新增 `packages/backend/app/services/disc_mapping_service.py`
  - 内容：`build_disc_mappings` 按序生成全序列；`apply_disc_mapping` 加载最新 plan，经 `archive_plan_repository.update_mappings` 持久化（mapping_revision + 1、CAS 防并发）。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed（序列顺序/非法盘号/持久化/过期 revision）。

- [x] T005 复用指纹与盘号解耦。
  - 文件：`packages/backend/app/services/archive/archive_manifest_access_service.py`、`packages/backend/app/services/archive/archive_execution_service.py`
  - 内容：`archive_report_fingerprint` payload 剔除 `first_disc_number`，两处调用同步；盘号后填/修改不破坏 Manifest 复用。
  - 验证：更新 `test_manifest_reuse_rechecks_input_snapshot_and_tolerates_disc_change`（盘号变化容忍、输入变化仍失败）；`tests/test_archive_execution_service.py` 20 passed。

- [x] T006 检查结果/附件1 回填（接线确认 + 死代码清理）。
  - 文件：`packages/backend/app/services/archive/archive_attempt_completion_service.py`、`packages/backend/app/repository/archive_report_metadata_repository.py`
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

## 后端 Controller/Route（Layer 22–23）

- [x] T009 后台压缩触发与状态路由（既有能力确认）。
  - 文件：`packages/backend/app/services/archive/archive_task_api_service.py`
  - 内容：「立即压缩」触发经既有 `WORKBENCH_ARCHIVE_DECISION` + 后台任务创建路径（enqueue）已存在；「待补盘号/归档完成/已导出」为 `ArchiveCompletionStatus` 派生投影，由前端按 lifecycle + 盘号补齐标志呈现。
  - 验证：`tests/test_workbench_controller.py`、`tests/test_archive_task*.py` 回归。

- [x] T010 盘号映射端点。
  - 文件：`packages/backend/app/services/archive/archive_task_api_service.py`（map_disc_numbers）、`packages/backend/app/controllers/archive_task_controller.py`
  - 内容：`POST /workbench/cases/{id}/disc-mapping` 接收首个盘号，调用 `disc_mapping_service.apply_disc_mapping` 自动生成全序列并持久化；非法盘号/任务锁定映射返回稳定错误。
  - 验证：`tests/test_disc_mapping_service.py` 4 passed + `tests/test_workbench_controller.py` 回归。

- [x] T011 统一导出端点。
  - 文件：新增 `packages/backend/app/services/archive/archive_export_service.py`、`packages/backend/app/controllers/archive_task_controller.py`
  - 内容：`POST /workbench/cases/{id}/export-bundle` 解析 succeeded 任务 manifest/final_dir + 最新草稿报告 + 照片，调用 `unified_export_service` 写入导出路径；模板上下文由 Controller 解析传入（分层约束）；导出路径须绝对且存在。
  - 验证：`tests/test_unified_export_service.py` 3 passed + `tests/test_archive_task*.py`/`test_workbench_controller.py` 回归。

## 前端 Hook（Layer 10）

- [x] T012 归档完成/盘号映射/统一导出 hook 与状态投影。
  - 文件：新增 `packages/frontend/src/hooks/useArchiveCompletion.ts`、新增 `packages/shared/utils/archiveCompletionRules.ts`
  - 内容：`useArchiveCompletion` 提供盘号映射（POST disc-mapping）与统一导出（POST export-bundle）动作与错误投影；`resolveArchiveCompletionStatus`/`allPartsDiscMapped` 派生卡片完成状态。
  - 验证：`useArchiveCompletion.test.tsx` 3 passed + `archiveCompletionRules.test.ts` 7 passed。

## 前端组件/页面（Layer 11–12）

- [x] T013 案件卡片完成状态、统一导出入口与彻底删除。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、新增 `packages/frontend/src/hooks/useArchiveCompletionStatuses.ts`
  - 内容：卡片显示「待补盘号/归档完成/已导出」徽标；「归档完成/已导出」时主按钮为「统一导出」（native picker 选目录 → export-bundle，**替换原「查看结果」**，用户确认完全替换）；「已导出」时菜单出现「彻底删除」（复用 `case-workbench-delete` 删除确认）；工作台经 `useArchiveCompletionStatuses` 自动加载归档结果派生完成状态（无需先点查看结果）。
  - 验证：`CaseCard.test.tsx` 15 passed（统一导出断言，查看结果移除）+ `CaseWorkbenchPage.test.tsx` 14 passed（含卡片直达统一导出流程）+ 全量前端 269 passed。
  - 后续修订：T038 已将 `archive_complete` 的 UI 文案收敛为「待导出」，并将已导出阶段的推荐操作调整为「删除案件」；本任务保留为历史实现证据，不再代表当前入口权重。

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
  - 文件：`packages/backend/app/controllers/record_template_context_controller.py`、`packages/backend/app/controllers/archive_task_controller.py`、`packages/backend/app/services/archive/archive_export_service.py`、`tests/test_archive_export_service.py`（mock 更新）、`tests/test_archive_runtime_lifecycle.py`（新增端到端回归）。
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
  - 文件：`packages/shared/types/archiveTask.ts`、`archiveCompletion.ts`；`packages/backend/app/services/archive/archive_manifest_projection_service.py`、`disc_mapping_service.py`、`archive_task_api_service.py`、`archive_task_result_service.py`、`unified_export_service.py`、`packages/backend/app/controllers/archive_task_controller.py`、`record_controller.py`、`record_template_context_controller.py`；`packages/frontend/src/components/ExtractListEditor.tsx`、`ReviewAttachmentsSection.tsx`、`ArchiveCompletionPanel.tsx`、`RecordEditorForm.tsx`、`packages/frontend/src/hooks/useArchiveCompletion.ts`、`useCompletedArchiveResult.ts`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及对应测试。
  - 验证：附件投影、盘号映射、单独/统一导出后端定向测试通过（相关组合 12 passed、14 passed，最终复审修正组合 8 passed）；附件编辑器、盘号组件与页面前端测试通过（最终组合 2 files / 19 passed）；TypeScript 类型检查与 `git diff --check` 通过。独立 Code Review 两轮发现的 MUST FIX（plan revision CAS、展示兜底不写回、confirmed 约束、pending 客户端字段旁路、映射后结果刷新）均修复，最终复审 **PASS**、无 MUST FIX。`npm run verify:full -- --change background-compression-archive-completion` 的预检、架构、类型、治理、资产、全仓测试、构建与严格文档检查全部 PASS。

- [x] T026 修复压缩期间上传图片后统一导出 422（人工验收回归）。
  - 现象：启动“立即压缩”后上传两张图片，压缩完成再统一导出返回 422，界面只显示“工作台请求未完成，请稍后重试”。
  - 根因：图片二进制先持久化，但压缩中草稿编辑保护拒绝 `photo_ids/photo_groups` 保存，且上传后的草稿保存依赖 debounce；统一导出又扫描案件资产目录，把未绑定图片送入缺失映射的附件2计划，底层错误被统一包装为 `WORD_RENDER_FAILED` 且没有安全文案映射。
  - 内容：归档发布临界区允许审核草稿另行保存，完成事务以独立的最新草稿 CAS 合并 Manifest 结果；图片上传完成立即触发草稿保存并在内部离页前强制刷盘，审核页恢复仍在孤儿保留期内的未绑定上传；图片组在前后端按检材/图片顺序确定性生成；统一导出只消费最新草稿绑定图片，未绑定上传或附件2映射错误返回明确提示。
  - 文件：`case_workbench_repository.py`、`archive_attempt_completion_service.py`、`archive_attempt_recovery_repository.py`、`archive_export_service.py`、`case_asset_service.py`、`unified_export_service.py`、`workbench_error_messages_controller.py`；`useCaseRecordSession.ts`、`useCasePhotoAssets.ts`、`CaseRecordGeneratePage.tsx`、`main.tsx`、共享图片组工具及对应测试与变更包文档。
  - 验证：后端归档并发、图片资产、统一导出、附件2与错误文案定向组合 106 passed；前端图片上传/即时保存、确定性分组、单独导出与页面导航阻断组合 4 files / 38 passed；共享分组工具 1 passed；`lint:arch`、TypeScript 类型检查、`verify:quick` 与 `git diff --check` 通过。临时禁用“未绑定图片阻止导出”判断时对应回归明确失败，恢复后通过，断言有效。独立 Code Review 首轮发现 2 个 MUST FIX 与 2 个 SHOULD，已补 Data Router 导航阻断与失败态保护、孤儿保留期边界、`ATTACHMENT2_IMAGE_INVALID` 文案、真实草稿写竞争 CAS 测试；聚焦复审最终 **PASS**，无 remaining findings。
  - 最终门控：`npm run verify:full -- --change background-compression-archive-completion` 的预检、架构、类型、治理、资产检查、全仓测试、构建与严格文档检查全部 **PASS**。首轮全仓测试仅有一个无关的 1 秒动态导入用例在并发负载下超时，隔离重跑 4 passed；未修改该测试，原 scoped full gate 第二轮完整通过。
  - manual_acceptance: N/A（本轮以合成资产和自动化路由/导出回归覆盖该 422 链路，不涉及新增 Word 视觉版式或桌面交互）。

- [x] T027 彻底解耦后台压缩与审核编辑（人工验收回归）。
  - 现象：点击“立即压缩”后在审核编辑界面上传图片，草稿 PATCH 返回 409，归档任务在发布前因草稿内容变化中断。
  - 根因：发布前校验把开始执行时的报告与当前草稿做归档稳定指纹比较，图片引用变化被误判为归档绑定失效；归档完成回填又会推进草稿 revision，与同一时刻的图片引用保存形成一次合法竞争。
  - 内容：归档发布继续校验密封输入快照、来源、attempt/binding/fence 与当前绑定一致性，但不再要求审核报告内容保持不变；发布采用校验时刻的最新草稿元数据，RAR 仍只消费密封快照。草稿保存遇到仅由归档完成产生的单次 revision 推进时，在后端保留可信 RAR/MD5/附件1投影并自动重试一次，其他真实并发冲突仍返回 409。
  - 文件：`packages/backend/app/services/archive/archive_attempt_service.py`（现已合并原 validation 内部实现）、`packages/backend/app/repository/archive_context_binding_repository.py`、`packages/backend/app/repository/archive_report_metadata_repository.py`、`packages/backend/app/services/case_lifecycle_service.py`、对应后端回归测试及本变更包文档。
  - 验证：归档发布前任意审核编辑不再中断任务；归档完成与图片绑定保存竞争时保存成功且最终同时保留图片引用和可信归档字段；普通过期 revision 冲突仍被拒绝；执行后端定向 pytest、`npm run verify:quick`、当前变更 scoped strict docs 与 `git diff --check`。
  - code_review: [DEFERRED] 独立审查两次因模型容量/长时间无响应未能产出结论；按用户 2026-08-09 指示先提交并推送，后续可在新候选版本上补做独立审查。

- [x] T028 消除上传报告目录与统一导出选择器仍可能被浏览器覆盖的竞态（人工验收回归）。
  - 现象：T024 后两个入口的 Windows 原生目录选择器仍有概率在首次成功置顶后被浏览器重新覆盖。
  - 根因：后台提升线程在第一次 `SetWindowPos` 成功后立即退出；对话框初始化期间若句柄重建或浏览器点击/重绘重新改变 Z 序，后续没有持续校正。枚举逻辑还会选择同一 PowerShell 进程的任意可见窗口，存在命中非目录对话框的竞态。
  - 内容：优先选择隐藏 owner 直接拥有的窗口，再回退到标准 `#32770` 对话框；在 `ShowDialog` 整个存续期间每 100ms 以 `SWP_NOACTIVATE` 重申 TopMost，首次前台激活失败继续重试，候选句柄变化时重新激活，关闭时等待提升线程结束后再释放窗口，持续置顶但不循环抢焦点。
  - 文件：`packages/backend/app/services/local_directory_picker_service.py`、`tests/test_local_directory_picker_service.py`、本变更包 `design.md` 与 `tasks.md`。
  - 验证：`test_local_directory_picker_service` 11 passed；内嵌 C# `PickerWindow` 独立编译通过；结构性回归断言锁定提升循环不得提前退出、句柄变化重新激活、owner 优先、`SWP_NOACTIVATE` 与线程 Join；`npm run verify:quick`、`npx tsx scripts/check-docs.ts --strict --change background-compression-archive-completion`、前端生产构建和独立复审均 PASS。scoped full gate 的前端 288/288、后端 1009/1009（3 skipped）通过，门控仅被无关的长路径环境边界测试 `test_long_snapshot_paths_use_short_private_root_without_changing_source_tree` 在全仓并发下间歇性 `middle_length=14 < 16` 阻断；该用例隔离重跑 1 passed（此前与另一个无关性能用例组合隔离重跑 2 passed）。Windows 浏览器前台人工验收待用户执行。

- [x] T029 修复多分卷已生成但 WinRAR 仍在收尾时被固定 deadline 终止（用户实测回归）。
  - 现象：机械盘约 15 分钟已显示写出 3.9GB、检测到 2 个分卷，之后输出约 4 分钟无增长并最终报告归档超时。
  - 内容：执行超时在环境覆盖与最大上限约束下增加固定收尾余量；监控器区分硬上限与 RAR 输出无增长空闲超时，仅在输出总大小严格增长时刷新活动计时，首个非零 RAR 出现前不启动 idle timeout；前端明确“已生成 N 个分卷（仍在压缩）”是中间进度而非完成态。
  - 文件：`packages/backend/app/repository/winrar_timeout_policy.py`、`packages/backend/app/repository/winrar_process_monitor.py`、`packages/backend/app/repository/winrar_executor_repository.py`、`packages/frontend/src/components/ArchiveStatusPanel.tsx`、对应后端/前端测试与本变更包 `design.md`、delta spec。
  - 验证：后端超时/执行器/Worker 定向 pytest 96 passed、1 个既有配置 warning（含增长、缩小、停滞、首个输出前硬上限、`0→非零→停滞`、环境覆盖、hard/idle 同时及跨界、executor 终止成功/失败的 staging 语义）；前端状态组件 Vitest 12 passed；架构检查与 TypeScript 类型检查通过。临时把“严格增长”退回“任意变化”、把“相等时 hard 优先”退回 idle 优先后，对应边界测试均按预期失败；恢复实现后单测与定向组合重新通过。修复后 `npm run verify:quick` PASS、当前变更 scoped strict docs 13 checks/0 drift、`git diff --check` PASS。
  - code_review: [PASS] 首轮独立审查发现 3 项 MUST FIX：hard/idle 同时或一次跨过两个 deadline 时须按绝对 deadline 选择最早者且相等时 hard 优先；环境覆盖与 `0→非零→停滞` 边界需要区分性断言；idle timeout 终止失败时不得清理 staging。三项均已修复，独立复审确认全部 CLOSED、无新 MUST FIX。遗留 SHOULD：后续可为真实 `_rar_output_size` 增加多分卷文件系统测试，不阻塞本轮。T027 的历史 deferred 记录不作为 T029 审查证据。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、资产、全仓测试、前端构建与 scoped strict docs 全部通过。首次运行仅因系统临时盘可用空间 285 MB 低于 1024 MB 预检门槛而在测试前停止，切换到 D 盘短临时目录后原门控通过。
  - manual_acceptance: N/A（本轮修复不改变视觉布局或桌面交互；超时状态机由可注入时钟、输出探针及 executor 进程/清理测试覆盖。机械盘真实大数据回归可作为部署后观察，不作为自动化候选门控。）

- [x] T030 修复上传图片后人工新增检材导致图片映射保持旧快照（人工验收回归）。
  - 现象：先上传四张图片、再人工新增第二个检材后，导出仍提示每个检材必须对应两张图片；只有删除全部图片并重新上传才能成功。
  - 根因：`photo_groups` 只在图片引用变化时按当时的检材列表生成；后续检材增删、改号或排序只更新 `evidence_list`，没有使用已持久化 `photo_ids` 重建映射。
  - 文件：`packages/shared/utils/softwareProjectionUtils.ts`、`packages/frontend/src/__tests__/softwareProjectionUtils.test.ts`、`packages/frontend/src/hooks/useCaseDraftAutosave.test.tsx`、本变更包 delta spec；人工检材到（三）/（四）的派生同步合同记录在 `audit-edit-enhancement` T020。
  - 内容：检材列表变化时以最新检材顺序和既有图片 ID 确定性重建 `photo_groups`，由现有草稿自动保存一并持久化；图片数量仍不匹配时保留现有明确导出门控。
  - 验证：定向 Vitest 覆盖“先四图、后一检材”、增删改排、失配状态与 autosave PATCH 载荷，2 files / 15 passed；后端数量失配门控定向 pytest 1 passed；临时禁用投影后回归用例 1 failed、恢复后通过；完整前端测试退出码 0；架构检查、TypeScript 类型检查与 `verify:quick` 通过。
  - code_review: [PASS] 首轮因增删改排、失配和持久化载荷覆盖不足驳回；补齐测试后第 2 轮独立复审确认 MUST FIX CLOSED，无新 MUST FIX。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、资产、完整测试、生产构建与 scoped strict docs 全部通过。
  - manual_acceptance: N/A（图片映射、草稿持久化载荷和导出失配门控由合成数据自动化覆盖；未改变 Word 视觉版式或桌面交互。）

- [x] T031 成功态以已验证 Manifest 覆盖最终分卷活动计数（浏览器实测反馈）。
  - 现象：4.10 GB 合成机械盘回归成功生成 2 个已验证分卷，但任务活动快照仍停留在 WinRAR 退出前观察到的 1 卷。
  - 根因：周期活动采样早于第二卷最终落盘；归档完成事务只写成功状态，没有用最终 Manifest 回填 `output_bytes`/`output_volume_count`。
  - 修复：`complete_verified_attempt` 在同一成功事务中从已验证 publish intent Manifest parts 计算并覆盖最终输出字节数、分卷数和最后变化时间；非法或空 parts 作为完成证据无效拒绝。
  - 验证：`tests/test_archive_runtime_lifecycle.py` 断言成功态最终计数来自 Manifest；定向后端测试、工程门控与浏览器回归通过。
  - code_review: [PASS] 独立首轮审查发现恢复不一致态与测试区分度 2 项 MUST FIX；修复为拒绝 attempt 未完成但 task 已成功的不一致恢复状态，并补“旧快照 1 卷 → 两卷 Manifest → 成功态 2 卷”事务级集成测试及非法 parts 边界。复审确认全部 CLOSED，无剩余 MUST FIX。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、资产、全仓测试、生产构建与 scoped strict docs 全部通过。
  - manual_acceptance: [PASS] 浏览器以 4.10 GB 明确合成机械盘报告执行真实 WinRAR 压缩，约 6 分 40 秒生成 4,000,000,000 与 107,749,764 字节两个已验证分卷且未超时；验收后应用案件、合成源目录及归档产物均已删除。

- [x] T032 统一机械盘基线下的完整性、HashMyFiles 与统一导出请求预算（用户环境反馈）。
  - 现象：大多数部署使用机械盘；`rar t` 仍按 50 MB/s 且无固定余量估算，HashMyFiles 内部允许长任务，但统一导出前端仍固定 30 分钟，可能在后端正常复制或校验时先报告超时。
  - 内容：完整性与 HashMyFiles 按全部 RAR 字节数使用机械盘保守吞吐和固定余量动态计算有界超时；SharedUtils 按机械盘复制预算 + HashMyFiles 最大有效内部预算计算统一导出请求上限，两个前端入口都把当前已验证 parts 交给 Hook 汇总；普通请求超时保持不变。
  - 文件：`packages/backend/app/repository/winrar_timeout_policy.py`、`packages/backend/app/services/hashmyfiles_service.py`、`packages/shared/constants/workbenchConstants.ts`、`packages/shared/utils/archiveCompletionRules.ts`、`packages/frontend/src/hooks/useArchiveCompletion.ts`、`packages/frontend/src/hooks/useArchiveCompletionStatuses.ts`、`packages/frontend/src/components/ArchiveCompletionPanel.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、对应后端/前端测试与本变更包 `design.md`、delta spec。
  - 验证：定向后端 pytest 89 passed，覆盖小体积、23 GB、135 GB、上限及 HashMyFiles 环境覆盖；前端 6 files / 54 tests passed，覆盖非法大小、最小值、机械盘动态增长、最大值、两个入口传递真实 parts、exported 自动加载与同案件 task 切换；架构检查、类型检查与 `git diff --check` 通过。临时把完整性吞吐退回 50 MB/s、HashMyFiles 吞吐退回 10 MiB/s、统一导出漏传 parts 后，对应回归用例均按预期失败，恢复后通过。
  - code_review: [PASS] 首轮独立审查发现外层预算未覆盖 HashMyFiles 环境上限、工作台事实源不准确、组件跨层依赖、设计参数漂移及非法大小边界 5 项 MUST FIX；二轮又发现同案件新 task 可能复用旧 parts。修复为按 `case_id + task_id` 绑定结果、导出前二次校验当前 task、组件经 Layer 10 派生状态并补 task 切换区分性测试；第三轮复审确认全部 CLOSED，无新 MUST FIX。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、资产、全仓测试、生产构建与 scoped strict docs 全部通过。首次运行仅有既有工作台删除测试在全仓并发下触发 5 秒超时（56/57 files、296/297 tests 已通过）；该文件隔离重跑 15/15（目标用例 2.42 秒），未修改实现或测试，原门控重跑通过。
  - manual_acceptance: N/A（超时预算及 task/parts 绑定由合成体积和可区分自动化测试覆盖，不改变视觉布局、Word/PDF 版式或桌面选择器交互；真实机械盘大数据可作为部署后观察。）

- [x] T033 调整统一导出产物目录规则（用户需求）。
  - 内容：用户选择导出文件夹后，Word 与 HashMyFiles 校验 PNG 导出到所选文件夹，RAR 分卷导出到其上级文件夹；所选文件夹为文件系统根时，RAR 回退到所选文件夹。跨两个目录发布仍保持整体回滚语义，并事务性清理旧规则遗留在所选文件夹中的同名 RAR。
  - 文件：`packages/backend/app/services/unified_export_service.py`、`tests/test_unified_export_service.py`、本变更包 `design.md`、delta spec 与 living spec。
  - 验证：统一导出定向 pytest 10 passed，覆盖常规父目录分流、根目录回退及跨目录发布失败回滚；`npm run verify:quick` PASS；当前变更 scoped strict docs 13 checks/0 drift；`git diff --check` PASS。
  - code_review: [PASS] 首轮独立审查发现旧规则遗留在所选目录的同名 RAR 未纳入迁移清理，可能与父目录新 RAR 形成混合布局；已将旧 RAR 与历史 HTML 纳入同一可回滚事务并补成功清理、失败恢复测试。复审确认 MUST FIX CLOSED、无 remaining MUST FIX；遗留 SHOULD 为后续增强回滚动作自身再次发生 I/O 错误时的全量恢复与专门诊断。
  - manual_acceptance: N/A（目录分流及根目录边界由合成路径自动化覆盖，不改变 Word/PNG 内容或目录选择器交互。）

- [x] T034 修复草稿 revision 冲突后图片绑定永久 409（用户实测回归）。
  - 现象：立即压缩后连续草稿保存先出现多次 200，随后首次 409；案件轮询 GET 与编辑租约 heartbeat 均保持 200，但草稿 PATCH 持续 409。图片二进制 `POST /assets` 成功后，图片引用仍因复用整草稿 PATCH 而 409，页面持续阻止离开。
  - 根因：图片二进制与草稿引用是两阶段写入，第二阶段复用整草稿 revision；首次冲突后本地存在未保存修改，后台 GET 不覆盖本地草稿，autosave 又持续携带旧 revision，形成永久冲突循环。T027 只覆盖归档完成恰好推进一次 revision，不能覆盖多次 revision 推进或冲突后继续编辑。
  - 内容：新增案件图片引用字段级绑定接口，以调用方最后观察到的图片 ID 列表作为图片域 CAS 基线；后端在最新草稿上原子合并 `asset_refs`、`photo_ids` 与确定性 `photo_groups`，非图片字段并发推进只触发有界重试，同一图片域被另一会话修改仍返回 409。前端图片上传/恢复改用该接口，并用返回的最新草稿 revision 重基已有本地未保存修改，终止旧 revision 重试循环。
  - 文件：`packages/shared/types/workbench.ts`、`packages/shared/constants/index.ts`、`packages/backend/app/services/case_lifecycle_service.py`、`packages/backend/app/controllers/case_asset_controller.py`、`packages/frontend/src/hooks/useCaseDraftAutosave.ts`、`useCaseRecordSession.ts`、相关前后端回归测试及本变更包文档。
  - 验证：后端图片资产定向 pytest 11 passed，覆盖非图片多次 revision 推进后绑定、真实图片域冲突及 HTTP 409 契约；前端 3 files / 37 tests passed，覆盖 autosave 重基、上传绑定失败后不重复上传的原地重试，以及页面离开保护；`npm run verify:quick` PASS，架构、类型、治理、quick docs 与仓库资产门控通过；`git diff --check` PASS。将图片域比较临时失效后，真实冲突用例按预期失败，恢复实现后通过。
  - code_review: [PASS] 对字段级 CAS、租约校验、最新草稿合并、并发重试、前端未保存编辑重放与失败重试基线完成实现自审；修正了首次绑定失败后错误采用未持久化图片列表作为下一次 CAS 基线的问题，复核无 remaining MUST FIX。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部通过。
  - manual_acceptance: [PASS] 首轮真实桌面验收观察到 `PATCH /assets/binding` 返回 405；实时 `openapi.json` 同样缺少该路径，而从当前工作区导入的 FastAPI 应用包含该 PATCH，证明请求命中的是新增路由前启动且未重载的旧应用，不是字段级 CAS 再次失败。进一步发现 30010 同时存在旧 reload 与当前应用两个监听者；清理后改为单一无 reload 当前工作区后端，连续 10 次 OpenAPI 检查均包含 PATCH，空体路由探针返回契约校验 422 而非 405。重启后同一案件 GET 200、draft revision=5，且 405 前上传的 4 个同指纹可用孤儿资产仍在登记表中。刷新审核页重新获取租约后，用户于 2026-08-12 按“报告解析完成 → 立即压缩 → 填盘号 → 上传两张图片 → 返回案件工作台”完成真实桌面复验并确认通过。

- [x] T035 审核编辑界面单独 Word 导出复用 Windows 原生目录选择器（用户需求）。
  - 目标：审核编辑界面「导出 Word」按“确认 Word 文件名 → Windows 原生目录选择器 → 写入所选目录”的顺序执行，与案件工作台统一导出的路径选择、目录记忆和一次性授权行为一致；取消选择不生成文件。
  - Layer 0–1：在 `packages/shared/types/wordDownload.ts` 补充单独 Word 路径导出的请求/响应契约，复用现有导出与目录选择端点常量而不新增重复入口；验证：shared typecheck。
  - Layer 10：修改 `packages/frontend/src/hooks/useRecordExport.ts`，复用 `useArchiveCompletion` 已使用的 native picker 契约，把所选路径、一次性 token 和文件名随导出请求提交；保留导出门控错误映射；验证：`packages/frontend/src/hooks/useRecordExport.test.tsx` 覆盖成功、取消、picker 失败和导出失败。
  - Layer 12：修改 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx`，保留现有文件名对话框，并在确认后先选择目录再生成 Word；成功后提示最终目录且页面不跳转；验证：`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx` 覆盖调用顺序、取消不请求导出、重复导出每次获取新 token。
  - Layer 22：修改 `packages/backend/app/controllers/record_controller.py` 及必要的同层辅助模块，复用现有报告规范化、模板、盘号、图片和导出门控，在一次性目录授权校验通过后将 `.docx` 原子写入 picker 所选目录；既有无路径 Legacy 请求继续返回浏览器下载；验证：`tests/test_record_controller.py` 覆盖授权成功、token 缺失/复用/路径不匹配、文件名清洗和生成失败不留下伪成功文件。
  - 文档与门控：实现完成后核对本变更 delta 与最终行为，更新 living spec，运行前后端定向测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change background-compression-archive-completion`；Windows 真实目录选择器及实际 `.docx` 落盘需人工验收。
  - 验证：前端 4 files / 48 tests passed，覆盖保存响应快照、准备阶段编辑锁、目录授权参数和不触发浏览器下载；后端定向 pytest 6 passed，覆盖一次性授权成功、路径不匹配、token 复用、生成失败保留旧文件及 Legacy 下载兼容；`npm run typecheck` 与 `npm run lint:arch` PASS；`git diff --check` PASS。
  - code_review: [PASS] 独立审查先后识别旧 revision 快照与保存后至 picker 前编辑竞态；修复为在首个异步等待前锁定编辑、flush 后只消费保存响应快照，最终复审无 MUST FIX。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部通过。
  - manual_acceptance: [PASS] 用户于 2026-08-13 完成真实 Windows 桌面人工验收并确认通过；审核编辑界面的 Word 文件名确认、原生目录选择、所选目录落盘及相关交互符合预期。

- [x] T036 隐藏审核编辑界面的单卷 RAR 下载按钮（用户需求）。
  - 内容：审核编辑界面的附件区域继续展示已验证 RAR 的文件名、大小、MD5、卷序和盘号，但不再显示「下载该 RAR」；统一导出、后端受控下载能力及非工作台兼容入口不变。
  - 文件：`packages/frontend/src/components/ArchiveStatusCard.tsx`、`RecordEditorForm.tsx`、`ArchiveStatusCard.test.tsx`、本变更包 delta spec 与 living spec。
  - 验证：前端组件定向测试 2 files / 16 tests passed，覆盖审核编辑器传入隐藏配置、归档信息保留且下载链接缺失，以及其他入口默认下载行为不变；`npm run verify:quick` PASS，架构、类型、治理、quick docs 与仓库资产门控通过；scoped strict docs 13 checks/0 drift；`git diff --check` PASS。
  - final_gate: [PASS] `HARNESS_TEMP_ROOT=D:\harness-temp` 下执行 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部通过；用户明确要求本轮不执行独立 code review。
  - manual_acceptance: N/A（仅隐藏指定页面按钮，组件自动化测试覆盖展示信息保留且下载链接缺失；不改变桌面选择器或真实文件内容。）

- [x] T037 修复可变长度光盘编号前缀导致归档发布失败（用户实测回归）。
  - 现象：首盘号前缀不是恰好 2 个字符时，两个 RAR 分卷及 MD5 已生成，但 Manifest `disc_date` 被固定下标截错；发布前复核返回 `ARCHIVE_PARTS_INVALID`，任务进入 `failed_retryable` 且 staging 被清理。
  - 内容：Manifest 组装统一使用 `parse_disc_sequence` 的结构化结果，并以同一个 sequence 提供日期及连续盘号；覆盖 1、2、3、20 字符中英文前缀、两分卷发布与非法盘号既有拒绝语义。
  - 文件：`packages/backend/app/services/archive/archive_manifest_service.py`、相关归档测试及本变更包文档。
  - 验证：盘号解析、Manifest、归档执行、计划投影、任务重试/生命周期、Worker 与发布 fence 定向 pytest 125 passed；架构检查、TypeScript 类型检查、仓库资产检查与 `git diff --check` 通过。临时恢复固定下标日期截取后，可变前缀单元/发布回归 4 failed，恢复实现后 5 passed，证明断言可区分旧缺陷。
  - code_review: [PASS] 首轮独立审查发现发布前最新非法盘号被静默降级、通用假 Worker 手工制造计划导致假阳性、缺少 21 字符拒绝边界 3 项 MUST FIX；修复为发布前对最新草稿重跑盘号门控，撤销假 Worker 计划注入，并分层覆盖生产投影接线、两槽位持久化、20 字符中英文合法上界及 21 字符/非法日期/非法序号稳定错误。独立复审确认全部 CLOSED，无新 MUST FIX。
  - final_gate: [PASS] 首次 scoped full gate 唯一失败为 `b4734ab` 中模板版本测试把 HEAD 当前 1.0.1 资产误作历史 1.0.0；该回归已在 `extensible-report-template-platform` 原任务内修复，模板定向 41 passed/1 skipped、独立复审 PASS，且两个 DOCX 资产无变化。随后在 `HARNESS_TEMP_ROOT=D:\harness-temp` 下重跑 `npm run verify:full -- --change background-compression-archive-completion`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部通过。
  - manual_acceptance: 自动化已覆盖三字符中文前缀两分卷的 Manifest 生成、发布复核、正式目录落地、重试新 attempt 和成功结果；原始本地报告的真实 WinRAR 验收需使用用户本机案件资料执行，不把真实案件数据写入仓库。

- [x] T038 收敛案件工作台卡片信息层级与阶段主操作。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/platformShell.css`、对应前端测试、本变更包 delta spec 与 living spec。
  - 内容：不新增 lifecycle，以明确正向分支仲裁最终状态和兼容活动任务；移除序号、重复案件名称与最终状态下的历史阶段，按解析中/解析失败/待处理/归档中/待补盘号/待导出/已导出显示唯一推荐操作；已导出删除确认说明目标目录文件不受影响，打开与再次导出保留为次要操作。
  - 边界：`CaseStatusBadge.tsx`、`ArchiveStatusPanel.tsx` 保持共享行为不变；上传报告目录组件和 `.case-workbench-directory-picker` 样式零视觉、零交互修改。
  - 验证：按实际可见推荐 CTA 名称覆盖状态矩阵、最终 lifecycle 优先、导出 loading 防重复与删除确认文案；运行定向前端测试、`npm run verify:quick`、三个关联变更的 scoped strict docs、独立代码审查、当前 Level 3 scoped full gate 与 `git diff --check`。
  - 自动化证据：候选版 5 files / 37 tests passed；审查修复后状态优先与再次导出页面级 deferred-promise 回归 2 files / 26 tests passed；TypeScript、架构与 `verify:quick` PASS；本地工作台浏览器核对标题、已导出卡片、更多菜单、删除确认和上传目录外观通过。
  - code_review: [PASS] 首轮独立审查发现 `archive_verified`/`exported` 仍可能泄漏历史任务详情/操作，以及再次导出缺少可见 loading 两项 MUST FIX；修复为最终阶段正向分支隔离任务动作，并以独立 `exportingCaseId` 覆盖完整异步周期。复审确认全部 CLOSED，无新 MUST FIX。
  - final_gate: [PASS] `npm run verify:full -- --change background-compression-archive-completion` 通过：预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部 PASS。
  - manual_acceptance: [PASS] 本地浏览器实际渲染确认上传报告目录虚线框、图标、文案和点击入口保持原状；仅打开并取消删除确认，未执行删除或导出。

- [x] T039 将已导出状态 Tag 调整为成功语义绿色。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCardCompletion.test.tsx`、本变更包 delta spec 与 living spec。
  - 内容：仅为 `exported` 阶段使用 Ant Design 现有 `success` Tag 语义 token；其他阶段保持当前默认 Tag，不增加 hex/RGB 或第二套状态颜色映射。
  - 验证：组件测试断言已导出 Tag 使用设计系统成功语义类；运行定向测试、类型/架构检查、scoped strict docs 与当前 Level 3 full gate。用户明确要求本次不执行独立复审。
  - 自动化证据：修改前定向测试 1 failed / 8 passed，证明断言可区分默认 Tag；实现后 1 file / 9 tests passed，TypeScript 与架构检查 PASS。
  - final_gate: [PASS] `npm run verify:full -- --change background-compression-archive-completion` 通过：预检、架构、类型、治理、仓库资产、全仓测试、生产构建与 scoped strict docs 全部 PASS。
  - manual_acceptance: [PASS] 本地浏览器确认 `ant-tag-success` 生效，实际文字色、边框色和浅色背景均来自 Ant Design 成功语义 token，未新增硬编码颜色。

- [x] T040 为待导出阶段补充打开案件入口。
  - 目标：案件卡片处于「待导出」时，继续以「统一导出」作为唯一推荐主操作，并在更多菜单同时提供「打开案件」与「删除案件」；打开案件复用既有审核编辑路由，不触发导出或状态变化。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCardCompletion.test.tsx`、本变更包 delta spec；实现完成后再按同步流程更新 living spec。
  - 验证：组件定向测试断言待导出阶段主按钮仍为「统一导出」、更多菜单顺序包含「打开案件」「删除案件」，且「打开案件」链接指向当前案件审核编辑路由；运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change background-compression-archive-completion` 与 `git diff --check`。
  - 自动化证据：Layer 11 组件实现复用既有审核编辑路由；定向 Vitest 1 file / 10 tests PASS，真实点击「打开案件」后断言路由切换、统一导出主按钮保留且导出/删除回调均未触发；`lint:arch` 与 TypeScript 类型检查 PASS。`verify:quick` 的架构、类型、治理测试通过，但 quick docs 因工作区既有 `.agents/.claude` 工具镜像漂移 39 项而失败，与本任务代码及规格无关。
  - code_review: [PASS] 独立首轮审查要求补充真实点击、路由切换与副作用隔离断言；修复测试后复审确认 MUST FIX 全部关闭，无剩余 MUST FIX。遗留 SHOULD：Ant Design Dropdown 测试可在后续引入异步用户交互工具以消除既有 `act(...)` warning，不阻塞本轮。
  - final_gate: [N/A] 用户明确本次不需要完整门控；已停止正在运行的 `verify:full -- --change background-compression-archive-completion`。停止前环境预检、架构、类型、治理测试与仓库资产检查均通过。
  - manual_acceptance: [BLOCKED] 内置浏览器当前无可接管标签页，新建 localhost 页面未能附着，未执行导出或删除；菜单结构、可点击路由与主操作保持由合成数据组件测试覆盖。

- [x] T041 修复二进制容量、45GB 五卷与超大单卷机制（用户实测回归）。
  - 现象：生产计划器仍生成十进制 `4000000000` 字节的 4GB 分卷，45GB 仍限制 3 卷，并在 135GB 后报 `ARCHIVE_TOO_LARGE`。
  - 内容：容量统一为 `1024³`；标准档位保持 4GB/22GB/45GB，卷数为 2/2/5，最多覆盖 225GB；超过阈值切换为显式 `oversized_single_volume`，WinRAR 不传 `-v`，Manifest 与物理校验只接受单一 `<案件名>.rar`。历史无模式 Manifest 继续按旧十进制规则复核。
  - 文件：归档计划、WinRAR 执行、产物校验、Manifest、共享常量/类型、相关测试、本变更包 delta/design/proposal 与 living specs。
  - 验证：planner/validator/executor/Manifest 定向 pytest，`npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。
  - 收尾补漏：默认资源准入由旧 135GB 上限改为安全整数边界（保留 `BIJI_ARCHIVE_MAX_INPUT_BYTES` 部署覆盖）；附件与 Word 计划接受超大单卷 Manifest 的空容量字段，标准分卷仍拒绝缺失容量；前后端旧 135GB 错误文案改为策略容量描述。
  - 自动化证据：受影响后端 247 passed；前端 `useRecordExport` 10 passed；架构检查与 TypeScript 类型检查通过；`verify:quick`、scoped strict docs 与 `git diff --check` 通过。
  - code_review: [PASS] 独立首轮审查发现历史无模式 Manifest 在导出访问层错误使用二进制容量补值；修复为统一模式感知容量策略，并加入 4.1GB 边界回归。复审 `CONDITIONAL PASS`，原 MUST FIX 关闭且无新 MUST FIX；遗留 SHOULD 为补对称归一化测试、共享类型表达历史可选模式及执行前更早拒绝非法模式，不阻塞本轮。
  - final_gate: [PASS] `npm run verify:full -- --change background-compression-archive-completion` 在隔离的可写临时目录与合成工作台数据目录下通过：preflight、架构、类型、治理测试、仓库资产、全量测试、构建和 scoped strict docs 全部 PASS。首次默认数据目录运行因沙箱对 `%LOCALAPPDATA%/文枢` 仅只读而失败；第二次仅命中既有并发 retry flaky（后端 1156 passed、1 failed，失败用例隔离重跑通过）；第三次完整门控取得 exit 0，期间未修改实现。

- [ ] T042 归档失败状态刚出现时立即重试可能误报 REVISION_CONFLICT。[DEFERRED]
  - 类型：低概率时序边界 Bug；不影响正常压缩、容量规划、归档产物或失败后的数据安全。
  - 用户复现：启动归档并使其进入可重试失败；在界面刚显示“压缩失败，可重试”时立即点击“重试”。若后台仍在把案件生命周期收敛为 `archive_interrupted` 并递增 case revision，前端携带的旧 revision 会收到 409 `REVISION_CONFLICT`。
  - 临时规避：刷新或重新进入案件后再次点击重试；读取到最新案件 revision 后通常可成功。

  - 根因：retry 对 task revision 与 case revision 分阶段校验，案件读取与新 attempt/task 创建不在同一原子事务；后台失败收尾可在检查与使用之间推进 case revision。
  - 后续验收：内部失败收尾仅推进生命周期且 source/draft/report fingerprint 未变化时，重试应受控重基并成功；真实用户编辑、来源变化或新活动任务仍必须返回 409；增加确定性并发测试，不以盲目重跑掩盖竞态。

- [x] T043 将统一导出压缩包归位到所选文件夹（用户需求）。
  - 内容：统一导出时 Word、HashMyFiles 校验 PNG 与全部 RAR 分卷均写入用户选择的文件夹；发布阶段不访问所选文件夹上级目录，保留目录授权边界。
  - 文件：`packages/backend/app/services/unified_export_service.py`、`tests/test_unified_export_service.py`、本变更包 `design.md`、delta spec 与 living spec。
  - 验证：统一导出与调用链后端定向 pytest 52 passed、2 个既有 `ARCHIVE_CONFIGURED_ROOT_INVALID` warnings；架构检查、TypeScript 类型检查、`npm run verify:quick` 与 `git diff --check` 通过；当前变更 scoped strict docs 13 checks/0 drift。
  - final_gate: [ENVIRONMENT-BLOCKED] scoped full gate 的全量测试在默认数据根因只读数据库失败；切换可写数据根后相关失败用例 10 passed，但全量运行又命中既有 `TEMPLATE_VERSION_IMMUTABLE` 测试隔离冲突（1205 passed、3 failed、7 errors）。
  - code_review: [N/A] 用户明确要求本轮不执行独立审查。

- [x] T044 新增批量导入图片按钮，按文件名数字排序配对，且图片异常不阻止单独 Word 导出（用户需求）。
  - 目标：审核编辑界面的附件图片区域新增独立「批量导入图片」按钮，原有逐张添加入口保留；按钮允许一次全选图片。普通数字文件名允许跳号，按自然升序排列后每两张依次对应当前检材；同时支持 `1-1、1-2、2-1、2-2` 位置分组命名，第一个数字表示当前检材顺序而非检材编号。批量图片数不等于检材数两倍时整批不填入、既有图片不变；一次 200 多张图片仍以有界并发正常上传和导出读取；任何图片缺失、数量、映射、绑定或读取问题均不得阻止审核页单独 Word 导出。
  - Layer 0：修改 `packages/shared/types/wordDownload.ts` 与 `openspec/specs/data-model.md`，为目录落盘成功但省略可选附件2的结果增加结构化非阻断 warning 契约。
  - Layer 2：修改 `packages/shared/utils/materialPhotoGroups.ts` 及同目录测试，新增稳定的文件名数字自然排序和 `<检材顺序>-<图片顺序>` 位置解析纯函数，覆盖 `pic1003.png`/`pic1005.png` 跳号、不同数字位数、扩展名差异、同序稳定性及 `1-1`/`1-2` 位置语义。
  - Layer 10：新增 `packages/frontend/src/hooks/useBatchImageImport.ts`，修改 `useCasePhotoAssets.ts`、`useRecordExport.ts` 及测试；在 Hook 层完成总数优先的批量原子校验和自然排序，使批量图片上传与导出读取最多 4 并发、保序且仅保存一次图片绑定，局部上传失败重试只重传失败项；单独 Word 请求仅在图片完整有效时携带附件2，零图片及后端图片异常均展示非阻断提示，不再把任何图片错误映射为 Word 导出失败。
  - Layer 11：修改 `packages/frontend/src/components/ImageUploader.tsx`、`packages/frontend/src/reviewWorkspace.css` 及测试，在附件说明行新增带上传图标的次要按钮「批量导入图片」，通过隐藏/受控多选文件入口接收整批图片，同时保留逐张槽位；先统一校验格式、大小、文件名数字和 `图片数 = 检材数 × 2`，全部通过才按自然排序结果一次调用 `onChange`，否则整批拒绝并提示当前检材数、应选数、实际数和未导入结果；窄屏下说明与按钮纵向排列且按钮保持完整可点击标签。
  - Layer 12：修改 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及测试，使图片仍在上传时最多等待 5 秒，等待超时或持久化图片读取失败时，单独 Word 导出继续以无附件2模式执行。
  - Layer 22：修改 `packages/backend/app/controllers/record_controller.py` 及 `tests/test_record_controller.py`，把图片门控从审核页单独 Word 导出失败条件中移除；有效图片正常渲染附件2，无效或不完整图片安全省略附件2并返回非阻断提示，其他 Word 门控保持不变。
  - 验证：运行共享工具、`ImageUploader`、`useCasePhotoAssets`、`useRecordExport`、页面与 `record_controller` 定向测试；覆盖独立按钮可访问名称、多选、逐张入口仍存在、批量成功配对、数量不足/超出均零写入、原列表保留、跳号排序、202 张图片上传/读取并发上限与单次绑定、前端直接请求与旧客户端请求均无法用图片问题阻断 Word；再运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change background-compression-archive-completion` 与 `git diff --check`。真实 `.docx` 需人工确认完整图片生成附件2、异常图片仍成功导出且附件2省略。
  - 自动化证据：前端 4 files / 60 tests、共享排序与位置解析 6 tests、后端图片及 revision 定向 9 tests 全部通过；202 张合成图片上传与读取峰值并发均为 4，原顺序和单次绑定断言通过；三检材 `1-1` 至 `3-2` 乱序选择按位置正确配对，重复、越界、非法槽位和两种命名混用整批拒绝；页面回归真实等待 5 秒并覆盖目录选择期间图片绑定推进 revision；后端正向只容忍迟到图片绑定，非图片变化、未来 revision 及缺失/空图片等价均保持 409。临时反转位置排序后核心回归按预期失败，恢复实现后通过；`npm run verify:quick`、`lint:arch`、TypeScript 与 `git diff --check` PASS。
  - code_review: [PASS] 用户补充位置分组命名后重新冻结候选；独立复审继续识别并关闭目录选择期间 revision 竞态、未来 revision 误放行及空图片表示误判，最终确认先前跨层引用、图片读取容错、零图片提示、数量提示优先级和非图片写入失败合同均已修复，无剩余 MUST/SHOULD。最终门控仅更新一处旧帮助文案测试断言后再次复审 PASS。
  - final_gate: [ENVIRONMENT-BLOCKED] 两次使用独立可写合成数据根执行 scoped full gate：预检、架构、类型、治理、仓库资产及前端 60 files / 387 tests 均 PASS；后端两次均为 1213 passed、3 skipped、3 failed、7 errors，全部归因既有共享模板状态 `TEMPLATE_VERSION_IMMUTABLE`。对应 10 个失败/错误用例换全新数据根隔离重跑 10/10 PASS，T044 后端图片与 revision 定向 9/9 PASS；按重复失败终止规则未继续重跑，生产构建阶段因前置全量测试失败未执行。
  - manual_acceptance: [PENDING] 真实 Windows 桌面 `.docx` 尚需确认：完整图片生成附件2、异常图片仍成功导出且附件2省略。

- [x] T045 超大单卷使用用户填写的硬盘编号并生成硬盘文书（用户需求反馈，补充压缩前编号体验优化）。
  - 规则：继续按压缩前归档输入总量选择现有模式；不超过 `225 × 1024³` 字节保持标准光盘分卷，超过阈值保持一个不分卷的大 RAR。`standard_split` 对应光盘，`oversized_single_volume` 对应硬盘；恰好 225GB 仍属于光盘。
  - 编号：编号由用户在审核编辑界面填写。该任务实施时标准分卷使用 `GPyyyyMMdd-序号`、超大单卷使用 `YPyyyyMMdd-序号`；后续 T049 在日期后增加两位用户标识并保留历史格式兼容。压缩可在编号为空时继续，错误介质前缀不得成为已完成映射。
  - Word：光盘正文、附件摘要和附件3保持“封盘/刻录/光盘”语义并在摘要列出全部编号；硬盘正文改为“结果以拷贝的方式保存在编号为……的硬盘中”，附件摘要改为“本鉴定中心拷贝的编号为……的硬盘1块，共1页”，附件3显示“硬盘编号”及“本鉴定中心拷贝的……号硬盘”。
  - 文件：`packages/shared/types/archive.ts`、`archiveCompletion.ts`、`archiveTask.ts`；`packages/backend/app/services/disc_sequence_service.py`、`archive_execution_service.py`、`archive_task_api_service.py`、`archive_task_result_service.py`、`disc_mapping_service.py`、`attachment_plan_models_service.py`、`attachment_plan_service.py`、`attachment_docx_renderer_service.py`、`template_filler_service.py`；`packages/frontend/src/components/ArchiveCompletionPanel.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`；相关现有测试、delta/design 与 living spec。
  - 验证：盘号/硬盘号解析映射、归档结果投影、AttachmentPlan 和真实 DOCX XML 定向 pytest；`ArchiveCompletionPanel` 定向 Vitest；`npm run lint:arch`、`npm run typecheck`、scoped strict docs 与 `git diff --check`。核心介质映射与 Word 文案断言需验证区分度。
  - 自动化证据：后端归档规划、介质映射、AttachmentPlan、DOCX renderer 与统一导出定向 pytest 121 passed；归档结果 HTTP 投影 1 passed；前端介质输入、状态卡、审核附件、待办校验与页面接线 54 tests passed；officecli 硬盘版合成 DOCX validate PASS，document builder 14 passed；`npm run pre-commit`、架构、类型、治理、quick docs、仓库资产与 `git diff --check` PASS。
  - 区分度证据：临时把超大单卷前缀由 `YP` 错设为 `GP` 后，硬盘映射回归 3 failed；恢复后映射套件 9 passed。临时把硬盘附件摘要“拷贝”改回“刻制”后，硬盘 Word 精确文案用例按预期失败；恢复后 DOCX renderer 32 passed。
  - final_gate/code_review: [DEFERRED] 当前 Level 3 变更包仍有 T044 真实 Word 人工验收待完成，候选尚未冻结；按 Harness 节奏不在单项反馈收敛时重复运行 scoped full gate 或最终 Review。
  - manual_acceptance: N/A（本任务不改变模板样式、分页或图形结构；合成硬盘版 DOCX 已通过精确文本/页计划断言和 officecli 文件结构校验。真实案件数据与 225GB 以上实际 WinRAR 执行不进入仓库测试。）
  - 追加反馈：归档模式尚未确定时，审核页使用中性的“介质编号”标签，同时接受 GP/YP 两种合法格式并明确说明最终介质由压缩前归档总量决定；模式确定后再切换为光盘或硬盘精确校验。补充前端 4 files / 49 tests PASS，覆盖压缩前填写并自动保存 YP、GP/YP 双格式及非法前缀校验；Impeccable 界面规范扫描 0 findings。

- [x] T046 允许用户在平台设置中选择 RAR 工作与存储目录（部署空间反馈）。
  - 现象：便携 EXE 默认把 staging 与已验证 RAR 都写入 `%LOCALAPPDATA%\文枢`；系统盘仅剩约 1.36GB 时，两次任务均在首卷增长到约 1.4GB 后由 WinRAR 非零退出，批量导入图片进一步竞争系统盘空间。
  - Layer 0–1：新增归档存储设置的读取、选择与恢复默认 API 契约及稳定错误码。
  - Layer 20–23：以用户数据根内的原子 JSON 保存选择；启动时将所选目录下的专用 `文枢归档工作区` 解析为归档 output root，使 staging、已验证 RAR、Manifest 索引和恢复/删除继续位于同一受控文件系统；目录不存在、不可写或与程序资源根重叠时不静默启用。原生选择器复用既有窗口归属和独立历史记录，设置在文枢重启后生效。
  - Layer 10–11：侧栏底部新增与现有按钮同尺寸、同圆角和同阴影的设置按钮；弹窗展示当前生效目录、待生效目录、空间提示、选择目录与恢复默认操作，明确正在运行的归档不会迁移。
  - 验证：设置仓库/路径解析/控制器 pytest，侧栏与设置弹窗 Vitest，`lint:arch`、`typecheck`、`verify:quick`、scoped strict docs、生产构建、Impeccable detector 与桌面视觉检查。
  - 自动化证据：归档设置、案件产物删除、Workbench HTTP 与归档生命周期后端定向 61 passed；历史默认根归档在切换根后仍可读取的区分用例 PASS；侧栏/弹窗前端 25 passed；TypeScript、生产构建、架构检查与 `git diff --check` PASS。
  - 视觉与审查：3440×1440 桌面实测确认折叠侧栏按钮为既有 40×40、10px 圆角、阴影和紫色反馈；Impeccable detector 仅命中既有侧栏 margin 动画。独立 finish review 关闭 portal 变量、恢复默认确认、加载失败重试和 mutation 失败反馈问题后最终 PASS。
  - final_gate: [DEFERRED] 当前 Level 3 变更包仍有 T044 真实 Word 人工验收待完成，候选尚未冻结；本反馈只运行增量门控，不重复 scoped full gate。

- [x] T047 阻止统一导出污染便携版程序目录（用户实测回归）。
  - 现象：统一导出允许选择文枢便携包程序目录，Word、RAR 和 HashMyFiles PNG 会成为完整性清单之外的未知文件；下次启动时启动器提示“程序文件不完整或包含未知文件”。取消另一个归档任务后立即删除只产生已安全忽略的 stale-owner 收敛日志，不是该启动提示的来源。
  - 修复：导出目录选择器在记忆偏好前校验目录；控制器在签发一次性授权前复核；统一导出与审核页单独 Word 落盘前再次复核。程序资源根、用户数据根及其子目录统一返回稳定 `EXPORT_DIRECTORY_UNSAFE`，不消费授权、不写文件、不覆盖上次有效目录偏好。
  - 文件：`packages/backend/app/services/archive/archive_export_service.py`、`local_directory_picker_service.py`、`packages/backend/app/controllers/workbench_controller.py`、`record_controller.py`、`workbench_error_messages_controller.py`、对应后端测试、delta spec 与 living spec。
  - 验证：导出服务、目录选择器、统一/单独 Word 控制器定向 pytest；`npm run verify:quick`、scoped strict docs 与 `git diff --check`。本反馈不冻结仍含人工验收待办的 Level 3 候选，不重复最终 Review/full gate。
  - 自动化证据：统一导出服务、授权服务、目录选择器与统一/单独 Word 控制器定向 39 passed；`npm run verify:quick` PASS（架构、类型、治理、quick docs、仓库资产）；程序目录与用户数据目录拒绝、拒绝时不消费 grant、不覆盖有效目录历史及正常目录导出均有区分断言。首次扩大运行 `test_record_controller.py` 的 2 个无关 archive endpoint 用例因默认 SQLite 只读失败，受影响用例隔离重跑全部通过。
  - 追加修复：2026-08-23 审计发现选择器返回路径在控制器复核后仍以原始表示签发授权，而统一导出按规范路径消费授权；控制器现统一用校验返回的规范路径响应并签发授权，避免 junction、别名或含 `..` 的等价路径产生授权不匹配。补充统一导出拒绝程序根时不消费 grant、不中转到 renderer，以及控制器只为规范路径签发授权的回归断言。受影响回归 32 passed，扩大后端套件 100 passed；2 个既有 archive endpoint 用例仍因默认 SQLite 只读失败，换全新合成数据根隔离重跑 2/2 passed；架构与类型检查 PASS。

- [x] T048 修复繁忙机械盘上 HashMyFiles 99% 后误报截图失败（用户稳定复现回归）。
  - 现象：统一导出到正在进行电子取证的 F 盘时，HashMyFiles 在 120 秒内运行到 99% 后退出，前端提示截图生成失败；导出到空闲 G 盘正常。
  - 根因：真实窗口捕获脚本开启 `LiveHashes` 并每 100ms 读取全部列表行，任一 `SendMessageTimeout` 超过 2 秒就终止进程；外层又把所有 PowerShell 非零退出统一包装成截图失败，丢失校验超时、窗口无响应、结果不完整与真实截图失败的差异。
  - 内容：关闭实时摘要；单次窗口消息容忍调整为 5 秒，计算阶段短暂无响应按 500ms 低频重试并受既有动态总期限约束；摘要完整后再读取最终行和执行带独立宽限的窗口整理/截图；PowerShell 通过无路径结构化结果返回启动、校验总超时、窗口持续无响应、结果无效与截图失败，后端和前端安全文案保持区分。
  - 文件：`packages/backend/app/repository/hashmyfiles_repository.py`、新增同层捕获脚本模块、`packages/backend/app/controllers/workbench_error_messages_controller.py`、`packages/shared/constants/workbenchConstants.ts`、相关后端测试、本变更包 delta/design 与 living spec。
  - 验证：HashMyFiles Repository、统一导出错误传播与 Controller 文案定向 pytest；`npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。使用 SYNTHETIC RAR 在繁忙机械盘上的真实窗口复验作为人工验收。
  - 自动化证据：Repository、统一导出原子回滚、API 错误传播与公共文案定向 pytest 45 passed；内嵌 PowerShell 解析、C# 编译及真实 PowerShell 启动失败结构化结果通过；随包 HashMyFiles 对临时 SYNTHETIC 小文件的真实窗口 PNG 冒烟验证 PASS；`npm run verify:quick`、架构、类型与 `git diff --check` PASS。临时恢复 `LiveHashes=1` 和 2 秒窗口阈值后核心回归按预期失败，恢复正式实现后通过。
  - final_gate/code_review: [DEFERRED] 当前 Level 3 变更包仍有既有 T044 真实 Word 人工验收待完成，候选尚未冻结；本反馈只运行增量门控，不重复最终 Review/full gate。
  - manual_acceptance: [N/A] T050 已将 HashMyFiles 截图从检查笔录统一导出调用链移除，本任务原定的繁忙盘统一导出截图验收不再适用；底层截图能力及其自动化验证保留，后续由鉴定文书接入任务另行验收。

- [x] T049 在 GP/YP 介质编号日期后增加两位用户标识（用户需求）。
  - 规则：界面继续使用单个完整字符串输入；光盘编号新增支持 `GPyyyyMMddXX-序号`，硬盘编号新增支持 `YPyyyyMMddXX-序号`，其中 `XX` 为两位数字用户标识。连续分卷只递增末尾序号并保留用户标识。
  - 兼容：原有 `GPyyyyMMdd-序号` / `YPyyyyMMdd-序号` 与新增格式都可用于提前规划、后填映射、修改、展示和导出，系统不自动补写或删除用户标识。
  - 文件：共享与后端 `DiscSequence` 类型/解析生成事实源、Canonical 投影、审核页介质编号提示、现有盘号/规划/映射测试、本变更 delta 与 living spec。
  - 验证：共享 Vitest、后端盘号/规划/映射 pytest、`ArchiveCompletionPanel` 与审核提示定向 Vitest；再运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change background-compression-archive-completion` 与 `git diff --check`。纯编号与文案变化无需真实 Word 或桌面人工验收。
  - 自动化证据：后端编号解析、规划、映射与 Canonical 投影 63 passed；共享解析生成、审核输入与提示 49 passed；页面自动保存和归档映射流程 17 passed；`npm run verify:quick`、scoped strict docs 与 `git diff --check` PASS。新旧 GP/YP 格式均覆盖提前规划、后填映射和连续生成，新格式额外断言两位用户标识保持不变。后续回归修复将归档执行测试遗留的中文介质前缀改为受支持的 `GPyyyyMMddXX-序号`，继续区分两分卷序列、日期解析、Manifest 与计划投影；Runtime/Execution 核心测试 46 passed。
  - manual_acceptance: [N/A] 该任务仅改变结构化编号解析、校验提示与字符串投影，无真实 Word 版式或桌面外部工具行为变化。
  - final_gate/code_review: [DEFERRED] 当前 Level 3 变更包仍有既有 T044/T048 人工验收开放项，候选尚未冻结；本反馈按增量风险运行 quick/scoped docs，不重复最终 Review/full gate。

- [x] T050 检查笔录统一导出停用 HashMyFiles 截图并保留底层能力（用户需求）。
  - 决策：统一导出只发布最新 Word 与全部已验证 RAR，不启动 HashMyFiles、不生成截图；`hashmyfiles_repository`、`hashmyfiles_service` 与截图脚本保持可用，供后续鉴定文书流程复用。
  - 兼容：统一导出结果与新审计记录不再声明 `hash_verification_image`；历史导出记录的 PNG/HTML 字段继续兼容读取。再次导出到同一目录成功时移除旧固定名截图/HTML，发布失败时与旧 Word/RAR 一并回滚恢复。
  - 文件：`packages/backend/app/services/unified_export_service.py`、`packages/backend/app/controllers/archive_task_controller.py`、`packages/shared/types/archiveCompletion.ts`、统一导出超时规则、现有后端/前端测试、本变更 delta/design 与 living spec。
  - 验证：统一导出定向 pytest、Shared/前端相关 Vitest、`npm run lint:arch`、`npm run typecheck`、scoped strict docs 与 `git diff --check`；核心“不调用截图机制”断言需验证区分度。
  - 自动化证据：统一导出与导出编排后端 22 passed；Shared 超时、导出 Hook 与两个入口页面 4 files / 49 tests passed；`npm run verify:quick`、scoped strict docs、架构、类型、治理、仓库资产与 `git diff --check` PASS。临时恢复统一导出截图调用后核心“不调用 HashMyFiles”回归按预期失败，恢复正式实现后定向套件通过。后续回归修复移除生命周期测试中已失效的截图错误 mock，恢复“revision 分离时仍可导出”的单一职责，并断言不生成 PNG/HTML；统一导出、归档导出、生命周期与保留的 HashMyFiles 能力相关测试 71 passed。
  - final_gate/code_review: [DEFERRED] 当前 Level 3 变更包仍有既有 T044 人工验收开放项，候选尚未冻结；本反馈只运行增量门控，不重复最终 Review/full gate。
  - manual_acceptance: [N/A] 当前任务移除外部截图调用与 PNG 产物，不改变 Word 布局；自动化断言覆盖导出目录内容、审计结果与旧产物清理/回滚。

- [x] T051 适配繁忙机械盘 0.3 MB/s 单任务吞吐的超时治理（部署反馈）。
  - 现象：同事电脑使用机械盘并同时运行大量磁盘密集型任务时，单任务有效吞吐约为 0.3 MB/s；现有 5 MB/s 预算、WinRAR/完整性/HashMyFiles 10 小时上限及统一导出 24 小时上限会提前终止仍在正常工作的任务。
  - 决策：磁盘密集型体积预算统一按 0.1 MB/s 计算，为实测 0.3 MB/s 提供三倍耗时预算；WinRAR 执行、`rar t` 完整性、保留的 HashMyFiles 能力和统一导出客户端最大上限统一为 30 天。WinRAR 输出无增长阈值默认由 600 秒提高到 1800 秒并提供受边界约束的独立环境配置。普通工作台 30 秒请求、目录选择器、编辑租约、SQLite 锁等待及报告解析等待不变。
  - Layer 1–2：修改 `packages/shared/constants/workbenchConstants.ts`、`packages/shared/utils/archiveCompletionRules.ts`，把统一导出的复制吞吐基线和最大请求上限改为新合同；复用 `archiveCompletionRules.test.ts` 覆盖 0.3 MB/s 场景、最小值、非法大小、30 天上限和超上限钳制。
  - Layer 20：修改 `packages/backend/app/repository/winrar_timeout_policy.py`、`winrar_process_monitor.py`，统一 WinRAR 执行与完整性预算，新增受控 idle timeout 配置解析；扩展 `tests/test_winrar_timeout.py`，覆盖低吞吐大体积、增长不误杀、1800 秒停滞、环境覆盖、非法配置回退、30 天上限及稳定错误码。
  - Layer 21：修改 `packages/backend/app/services/hashmyfiles_service.py`，同步保留能力的体积预算和环境覆盖边界；复用 `tests/test_hashmyfiles_service.py` 覆盖 0.3 MB/s 体积、30 天上限与非法覆盖回退。检查笔录统一导出仍不得启动 HashMyFiles。
  - 一致性与验证：核对 delta/design 与实现后同步 living spec；先运行 WinRAR、HashMyFiles、统一导出超时的定向失败用例，再运行受影响测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change background-compression-archive-completion` 与 `git diff --check`。使用 SYNTHETIC 体积和可注入时钟验证，不创建大体积仓库资产。
  - code_review/final_gate：该任务修改核心归档执行与外部进程终止边界，有独立审查价值；与本 Level 3 包其余开放项收敛后统一冻结、Review 并运行一次 scoped full gate，不在本任务实施后提前重复最终门控。
  - implementation: [x] 统一导出复制、WinRAR 执行、`rar t` 完整性与 HashMyFiles 保留能力均已改为 0.1 MB/s 预算及 30 天上限；WinRAR idle 默认值已改为 1800 秒，并新增 `BIJI_ARCHIVE_IDLE_TIMEOUT_SECONDS` 的正整数/30 天边界解析与非法值安全回退。delta、design 与 living spec 已同步最终数值。
  - automated_evidence: [x] 失败先行时，旧常量使前端 2 项、后端 16 项新增断言失败；正式实现下前端统一导出相关 3 个文件 19 项通过，后端 WinRAR/HashMyFiles 101 项通过；`npm run lint:arch`、`npm run typecheck`、`npm run verify:quick` 均通过。`test_archive_worker_service.py` 在本机 pytest collection 阶段持续占用 CPU 未完成，本任务改由同层 `test_winrar_timeout.py` 的可注入进程监控集成断言提供定向证据，未宣称该整文件通过。
  - manual_acceptance: [x] 按本任务允许的替代路径，使用本机真实 `Rar.exe` 对明确标记为 `SYNTHETIC/TEST` 的小样本完成创建与 `rar t` 实跑（两阶段退出码均为 0，临时产物已清理）；低速体积、30 天钳制、1800 秒停滞及配置边界由可注入时钟/体积自动化断言覆盖。目标机械盘代表性并行负载的长时间观察可作为部署复核继续执行，但不再阻塞本任务自动化收敛。

- [x] T052 修复不可写归档目录导致启动/pytest 收集高 CPU 卡住（T046 部署回归）。
  - 根因：`config.py` 导入时会解析自定义归档目录，Repository 的可写性探针使用 Python 3.11 `NamedTemporaryFile`；Windows 上底层创建返回 `PermissionError` 且目录表面仍可访问时，`tempfile._mkstemp_inner` 会不断更换随机名称重试，无法及时投影 `ARCHIVE_STORAGE_DIRECTORY_UNAVAILABLE`。
  - 修复：Repository 改用自有随机文件名和有限次独占创建；名称碰撞只做小次数重试，权限、只读、离线盘及其他 I/O 错误立即返回不可写，成功探针仍 flush/fsync 并清理自身临时文件。
  - 验证：在现有 `test_archive_storage_settings.py` 增加权限拒绝立即失败及名称碰撞有界回归；运行该文件、`test_archive_worker_service.py --collect-only`、架构检查、scoped strict docs 与 `git diff --check`。该低风险 Repository 回归不改变公共合同，不单独冻结 Level 3 候选或运行 full gate。
  - 自动化证据：失败先行时存储设置既有 3 项通过、新增权限拒绝与碰撞上限 2 项失败；正式实现后 5/5 通过。此前在沙箱内超过 30 秒不返回的 `test_archive_worker_service.py` 现于 0.94 秒收集 23 项，完整执行 23/23 通过；`npm run lint:arch` 通过。
  - manual_acceptance: [N/A] 本任务修复 Repository 错误收敛与测试/启动阻塞，无界面、真实文书或外部工具交互；真实沙箱权限拒绝已复现旧挂起并验证新实现快速返回。

- [x] T053 统一导出完成后按案件打开最后导出文件夹（用户需求）。
  - 行为：统一导出成功后，案件卡片显示带“打开导出文件夹”悬浮提示和无障碍名称的文件夹图标按钮；点击后由后端从该案件最后一条成功统一导出记录解析目录并打开 Windows 文件资源管理器，前端不提交任意本机路径。
  - 安全与恢复：专用本地 Repository 按案件持久化规范绝对路径，不绕过通用审计 JSON 的绝对路径禁令；无成功记录、目录已移动/删除或系统无法打开时返回稳定可操作错误，不启动 shell 命令解析，不泄露其他案件路径。
  - 并发：案件 A 的统一导出未完成时可启动案件 B 导出；无论 A/B 完成顺序如何，每张卡片的 loading、成功标记和打开目录动作只绑定自身 `case_id`，不得被全局“最后完成”路径覆盖。
  - 文件：`packages/shared/types/workbench.ts`、`packages/shared/types/archiveCompletion.ts`、`packages/shared/constants/index.ts`、新增 `packages/backend/app/repository/local_case_export_directory_repository.py`、`packages/backend/app/services/archive/archive_export_service.py`、`archive_task_api_service.py`、`case_lifecycle_service.py`、`packages/backend/app/controllers/archive_task_controller.py`、`packages/frontend/src/hooks/useArchiveCompletion.ts`、`components/CaseCard.tsx`、`pages/CaseWorkbenchPage.tsx` 及现有测试。
  - 验证：复用统一导出审计、导出编排和工作台页面测试，覆盖路径持久化、按案件查询最新成功记录、目录不存在、无 shell 解析启动，以及 A/B 导出反序完成后两个图标分别请求自身案件端点；运行 `npm run verify:quick`、scoped strict docs、Impeccable detector 与 `git diff --check`。
  - 自动化证据：后端导出目录 Repository、统一导出、导出编排及工作台持久化 52/52 通过；案件卡片 10/10、归档完成 Hook 7/7，通过案件页 A/B 反序完成定向回归 1/1；前端生产构建、`npm run verify:quick`、scoped strict docs（14 checks / 0 drift）与 `git diff --check` 通过。Impeccable detector 仅报告 `platformShell.css:67` 既有 `margin-left` 布局动画，本任务新增样式无新告警。
  - code_review: [DEFERRED] 本任务复用当前未冻结 Level 3 变更包，按包级节奏待全部反馈收敛后统一独立审查，不为单项反馈提前冻结候选。
  - manual_acceptance: [PENDING] 自动化已验证按案件端点和 Windows Explorer 参数列表；仍需在真实打包 Windows 客户端中点击图标，确认文件资源管理器聚焦到实际导出目录。
