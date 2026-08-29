# Tasks: 归档路径元数据级指纹

workflow_level: 2

> 规格：`openspec/changes/metadata-fingerprint-archive-path/specs/electronic-inspection-record/spec.md`
> 范围：将来源复核与归档输入路径的全量内容指纹替换为元数据级指纹，修复归档决策请求阻塞并降低解析后复核与压缩任务负载；归档输出侧完整性校验保留。产品决策：放弃来源复核与归档输入快照的逐文件内容哈希，归档输出侧 RAR 校验与 MD5 仍保留。

## 后端 Service（Layer 21）

- [x] T001 来源复核指纹改为元数据级。
  - 文件：`packages/backend/app/services/source_record_fingerprint_service.py`、`tests/test_phase1d_fourth_review.py`
  - 内容：`fingerprint()` 以 path+type+size+mtime 计算，不读取文件内容；保留前后快照对比与符号链接/OSError 语义；删除 `_file_digest`/`_read_file_digest`。
  - 验证：来源指纹定向测试覆盖元数据变更检测与快照期间变更的瞬态失败。

- [x] T002 归档输入快照去掉逐文件内容 SHA-256。
  - 文件：`packages/backend/app/services/archive/archive_input_snapshot_copy_service.py`、`packages/backend/app/services/archive/archive_input_snapshot_files_service.py`
  - 内容：`source_evidence`/`copy_inventory`/`copy_file`/`assert_source_matches`/`assert_matches` 改为元数据校验；快照清单不再记录逐文件 sha256。
  - 验证：归档输入/执行相关后端测试回归。

- [x] T005 修复大目录来源复核重复扫描与 pending 无重试闭环。
  - 文件：`packages/backend/app/repository/source_record_repository.py`、`packages/backend/app/services/source_record_fingerprint_service.py`、`source_record_service.py`、`case_parse_dispatcher_service.py`、`workbench_factory_service.py`、`packages/backend/app/main.py`、`tests/test_phase1d_fourth_review.py`、`tests/test_phase1d_recovery.py`
  - 内容：从同一稳定快照派生初次复核 metadata/fingerprint，来源复核使用独立有界执行池；瞬态失败后有限退避重试，耗尽时持久化稳定诊断码，归档安全门保持不变。
  - 验证：定向测试覆盖两次而非三次目录扫描、解析与来源复核资源隔离、瞬态失败后自动恢复、重试耗尽和异常 Future 收敛。

## 前端（Layer 10/12）

- [x] T003 修复删除门并给归档/删除请求加超时。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/hooks/useCaseWorkbench.ts`、`packages/frontend/src/hooks/useCaseRecordSession.ts`、`packages/shared/constants/workbenchConstants.ts`
  - 内容：`confirmDelete` 门放宽为 `actionCaseId === deleteCaseId`（只拦截删除正在归档的同一案件）；归档决策与归档/删除请求增加 30s 超时。
  - 验证：受影响前端测试覆盖删除门与超时参数。

## 综合验证

- [x] T004 运行受影响测试和 Level 2 门控。
  - 内容：核对 delta 与实现，运行架构、类型、前后端测试和文档检查。
  - 验证：`npm run verify:quick`、受影响前后端测试、`npx tsx scripts/check-docs.ts --strict --change metadata-fingerprint-archive-path`、`git diff --check`。

- [x] T006 回归修复后的 Level 2 收尾。
  - 内容：核对新增 delta 与实现，运行架构、类型、受影响后端测试、`verify:quick` 和 scoped strict docs；同步 living spec。
  - 验证：`npm run verify:quick`、受影响后端测试、`npx tsx scripts/check-docs.ts --strict --change metadata-fingerprint-archive-path`、`git diff --check`。

- [x] T007 修复大目录复核导致 Uvicorn 重载/退出不收敛。
  - 文件：`packages/backend/app/services/source_record_fingerprint_service.py`、`source_record_service.py`、`case_parse_dispatcher_service.py`、`packages/backend/app/main.py`、`tests/test_phase1d_fourth_review.py`、`tests/test_phase1d_recovery.py`、`tests/test_archive_runtime_lifecycle.py`
  - 内容：将 dispatcher shutdown 信号传入目录快照遍历；取消时保持现有来源状态且不重试，使生命周期关闭能够终止已运行复核任务并释放后端端口。
  - 验证：定向测试覆盖遍历取消、来源状态不误写、dispatcher shutdown 收敛和 FastAPI lifespan 关闭。

- [x] T008 重启回归后的 Level 2 收尾。
  - 内容：重新运行受影响后端测试、`verify:quick`、scoped strict docs，并同步 living spec。
  - 验证：`npm run verify:quick`、受影响后端测试、`npx tsx scripts/check-docs.ts --strict --change metadata-fingerprint-archive-path`、`git diff --check`。

- [x] T009 消除大目录审核入口与归档执行的重复全量扫描。
  - 文件：`packages/backend/app/services/source_record_fingerprint_service.py`、`packages/backend/app/services/source_record_service.py`、`packages/backend/app/services/archive/archive_task_api_service.py`、`packages/backend/app/services/archive/archive_runtime_service.py`、`packages/backend/app/services/archive/archive_execution_service.py`、`packages/backend/app/services/archive/archive_manifest_access_service.py`、`packages/backend/app/repository/archive/archive_input_repository.py`、`packages/backend/app/controllers/workbench_controller.py` 及对应测试。
  - 内容：按产品确认的短生命周期案件边界，将来源复核收敛为授权路径、报告结构与核心报告文件身份检查；解析完成后不再递归扫描全部媒体文件。归档提交快速进入后台，直接源归档只构建一次完整输入 inventory，随后依赖 WinRAR 完整性、RAR MD5 与 Manifest 校验，不再执行独立来源复核和压缩前后重复 inventory。
  - 验证：SYNTHETIC 回归覆盖核心报告变化、深层媒体不触发审核入口递归扫描、归档提交仅复核一次、归档执行不重复扫描、工作台请求并发可用和输出完整性门；定向后端 79 passed，前端 20 passed，inventory/历史快照兼容 23 passed/2 skipped。用户指定目录只读基准确认来源复核收敛为毫秒级、后台唯一 inventory 较旧实现明显缩短；真实样本路径、名称、内容和统计未写入仓库。

- [x] T010 完成本轮 Level 2 回归收尾。
  - 内容：核对 delta 与最终实现，sync living spec，运行定向前后端测试、`verify:quick`、scoped strict docs 与 diff 检查。
  - 验证：后端全量 989 passed/3 skipped，受影响前端 20 passed，`npm run verify:quick` PASS；delta 已同步到 living spec，scoped strict docs 与 `git diff --check` PASS。

- [x] T011 消除归档发布重复 MD5 并恢复结果读取可用性。
  - 文件：`packages/backend/app/services/archive/archive_manifest_service.py`、`archive_publish_service.py`、`archive_execution_service.py`、`archive_attempt_completion_service.py`（现已合并原 completion record 内部实现）、`archive_task_result_service.py`、`packages/backend/app/controllers/archive_task_controller.py` 及对应后端测试。
  - 内容：每个新生成 RAR 在 Manifest 组装阶段只做一次完整 MD5；同一 attempt 的密封、原子发布、索引和完成提交复用该可信摘要并继续核对物理文件集合、类型和字节数。普通结果展示只验证 durable publication 身份和物理元数据，不重新读取 RAR 内容；正式导出、下载、恢复和复用仍保留完整内容校验。所有可能执行大文件 I/O 的结果下载与统一导出 HTTP 入口移入 FastAPI 同步线程池，避免阻塞事件循环。WinRAR 默认压缩级别保持不变。
  - 验证：SYNTHETIC 后端测试断言同次新归档每卷只计算一次 MD5、发布切点篡改仍安全失败、结果读取不调用内容哈希、下载/正式导出仍执行完整哈希，并发结果请求不阻塞工作台列表。

- [x] T012 完成输出校验性能回归的 Level 2 收尾。
  - 内容：核对 delta 与实现，运行受影响后端测试、架构与类型检查、`verify:quick`、scoped strict docs，sync living spec 并检查差异；浏览器人工验收由用户执行。
  - 验证：受影响后端核心回归 119 passed；`npm run verify:quick` PASS；delta 已同步到 living spec；scoped strict docs 与 `git diff --check` PASS。浏览器人工验收按用户要求未执行。
