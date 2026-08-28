# Tasks: 归档输入快照并行拷贝

workflow_level: 2

> 规格：`openspec/changes/archive-snapshot-copy-parallel/specs/electronic-inspection-record/spec.md`
> 范围：将归档输入快照拷贝从「顺序 + 每文件 fsync」改为「受控并行 + OS 写回」，降低 758MB 级报告清单阶段的耗时；保留元数据校验、目录/所有权 marker/文件清单持久化与崩溃重试契约。基准结论：去掉每文件 fsync 单线程 3.6×；SSD 并行峰值 8 线程、16 变慢；机械盘寻道竞争预计 2~4。默认并行度取折中 4，可配置覆盖。

## 后端 Service（Layer 21）

- [x] T001 copy_inventory 并行拷贝与目录遍历合并。
  - 文件：`packages/backend/app/services/archive_input_snapshot_copy_service.py`
  - 内容：先单遍创建所有目录（去除拷贝循环内逐文件 `parent.mkdir`），再用 `ThreadPoolExecutor` 并行拷贝文件，默认 4 工作线程、`BIJI_ARCHIVE_COPY_WORKERS` 可配置覆盖；worker 内完成拷贝与 mtime 恢复；任一失败记录日志并按原契约抛 `ArchiveInputError`。
  - 验证：受影响后端测试回归（归档输入快照相关）。

- [x] T002 copy_file 去掉每文件 fsync。
  - 文件：`packages/backend/app/services/archive_input_snapshot_copy_service.py`
  - 内容：`copy_file` 保留 `flush()` 与 `assert_regular`，移除每文件 `os.fsync`；快照目录 rename 后 `fsync_dir`、所有权 marker、文件清单元数据持久化均保留。
  - 验证：受影响后端测试回归。

## 综合验证

- [x] T003 运行受影响测试和 Level 2 门控。
  - 内容：核对 delta 与实现，运行架构、类型、后端测试与文档检查。
  - 验证：`npm run verify:quick`、受影响后端测试、scoped strict docs、`git diff --check`。
