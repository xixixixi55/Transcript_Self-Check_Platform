# Spec Delta: 归档输入快照并行拷贝

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（归档输入快照拷贝改为受控并行执行，并放宽拷贝时刻逐文件落盘；元数据校验、目录/所有权 marker/文件清单持久化与崩溃重试契约保留）

## MODIFIED: REQ-ARCHIVE-IMMUTABLE-INPUT — 归档输入快照密封

### REQ-ARCHIVE-IMMUTABLE-INPUT: 输入快照并行拷贝与元数据密封

The archive execution input MUST be a task/attempt/deployment-bound sealed snapshot; mutable source bytes MUST NOT be used as the execution or publication authority. 快照拷贝使用受控并行线程拷贝；逐文件内容不再在拷贝时刻 fsync 落盘（改由 OS 写回，秒级），但快照目录重命名、所有权 marker 与文件清单元数据仍持久化落盘；密封与校验继续使用元数据级身份（相对路径 + 大小 + mtime），归档输出侧 RAR 校验与 MD5 保留。

#### Scenario: parallel sealed execution input

- WHEN a task begins archive execution
- THEN the service creates a task/attempt/deployment-bound snapshot under the controlled output root, copies the complete authorized inventory in parallel（默认 4 工作线程，`BIJI_ARCHIVE_COPY_WORKERS` 可配置覆盖）without following links or reparse points, verifies every relative path, size and modified-time metadata, and durably marks it `sealed`
- AND file content is flushed to the OS but not per-file fsynced at copy time; the snapshot directory rename (`os.replace` 后 `fsync_dir`)、owner marker 与文件清单元数据 remain durably persisted
- AND content not yet written back when power is lost immediately after copy can leave partial or zero-filled bytes; truncated content is caught by the size-based metadata gate, equal-size zero-filled content is not caught by the metadata gate and is covered by archive-output RAR validation and crash-retry rebuild from source
- AND the snapshot manifest records per-file relative path, size and modified-time metadata, not per-file content SHA-256
- AND WinRAR, inventory, RAR validation and Manifest generation read only the sealed snapshot, never the mutable source directory
- AND an unsealed, missing, owner-mismatched, incomplete or metadata-mismatched snapshot cannot enter WinRAR, publication, reuse or success
- AND source changes after sealing cannot change the bytes read by this attempt; failure, cancellation, crash and retry never reuse a prior attempt snapshot
