# Tasks: 归档路径元数据级指纹

workflow_level: 2

> Spec: `openspec/changes/metadata-fingerprint-archive-path/specs/electronic-inspection-record/spec.md`
> 范围：将来源复核与归档输入路径的全量内容指纹替换为元数据级指纹，修复归档决策请求阻塞并降低解析后复核与压缩任务负载；归档输出侧完整性校验保留。产品决策：放弃来源复核与归档输入快照的逐文件内容哈希，归档输出侧 RAR 校验与 MD5 仍保留。

## Backend Services（Layer 21）

- [x] T001 来源复核指纹改为元数据级。
  - 文件：`packages/backend/app/services/source_record_fingerprint_service.py`、`tests/test_phase1d_fourth_review.py`
  - 内容：`fingerprint()` 以 path+type+size+mtime 计算，不读取文件内容；保留前后快照对比与符号链接/OSError 语义；删除 `_file_digest`/`_read_file_digest`。
  - 验证：来源指纹定向测试覆盖元数据变更检测与快照期间变更的瞬态失败。

- [x] T002 归档输入快照去掉逐文件内容 SHA-256。
  - 文件：`packages/backend/app/services/archive_input_snapshot_copy_service.py`、`packages/backend/app/services/archive_input_snapshot_files_service.py`
  - 内容：`source_evidence`/`copy_inventory`/`copy_file`/`assert_source_matches`/`assert_matches` 改为元数据校验；快照清单不再记录逐文件 sha256。
  - 验证：归档输入/执行相关后端测试回归。

- [x] T005 修复大目录来源复核重复扫描与 pending 无重试闭环。
  - 文件：`packages/backend/app/repository/source_record_repository.py`、`packages/backend/app/services/source_record_fingerprint_service.py`、`source_record_service.py`、`case_parse_dispatcher_service.py`、`workbench_factory_service.py`、`packages/backend/app/main.py`、`tests/test_phase1d_fourth_review.py`、`tests/test_phase1d_recovery.py`
  - 内容：从同一稳定快照派生初次复核 metadata/fingerprint，来源复核使用独立有界执行池；瞬态失败后有限退避重试，耗尽时持久化稳定诊断码，归档安全门保持不变。
  - 验证：定向测试覆盖两次而非三次目录扫描、解析与来源复核资源隔离、瞬态失败后自动恢复、重试耗尽和异常 Future 收敛。

## Frontend（Layer 10/12）

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
