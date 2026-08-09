# Spec Delta: 归档路径元数据级指纹

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（来源复核与归档输入使用元数据级指纹，归档输出侧完整性校验保留）

## MODIFIED: CAP-021 — 来源复核指纹

### REQ-021: 来源复核与归档决策可用性检查使用元数据级指纹

来源复核与归档决策前的来源可用性检查 MUST 使用元数据级指纹（相对路径 + 类型 + 大小 + mtime），不得在复核或请求路径读取源文件内容；全量内容指纹保留在归档执行侧。来源失效时必须要求重新选择目录。

#### Scenario: 来源复核使用元数据指纹

- WHEN 系统复核 SourceRecord 或执行归档决策前的来源可用性检查
- THEN 后端递归采集路径、类型、大小和 mtime 计算元数据指纹，不读取文件内容
- AND 路径、允许根、链接安全性、报告结构、大小、mtime 或元数据指纹发生变化，或来源被替换/不可用时，标记 `requires_reselection` 并阻止归档
- AND 同尺寸且时间戳保持不变的原地内容改写不在元数据指纹门的检测范围内；归档执行仍对实际归档内容做完整性校验

#### Scenario: 大目录初次复核避免重复扫描并可从瞬态失败恢复

- WHEN 初次来源复核递归采集目录统计和元数据指纹
- THEN 后端从同一份稳定快照派生文件数、目录数和 fingerprint，不为目录统计额外执行一次全目录遍历
- AND 来源复核使用独立的有界执行资源，不得占用报告解析工作线程
- AND 扫描期间来源仍在写入或发生暂时 I/O/权限错误时，来源保持 `pending`，后台按有限退避自动重试，无需重启应用
- AND 有限重试耗尽后记录稳定诊断状态，继续阻止归档，不得静默永久挂起或将来源误标为可用
- AND 应用重载或关闭时取消仍在运行的目录遍历，来源保持 `pending`，旧后端进程不得因来源复核线程长期阻塞退出或占用服务端口

## MODIFIED: REQ-ARCHIVE-IMMUTABLE-INPUT — 归档输入快照密封

### REQ-ARCHIVE-IMMUTABLE-INPUT: 输入快照密封与校验使用元数据级身份

The archive execution input MUST be a task/attempt/deployment-bound sealed snapshot; mutable source bytes MUST NOT be used as the execution or publication authority. 快照密封与校验使用元数据级身份（相对路径 + 大小 + mtime），不再计算逐文件内容 SHA-256；归档输出侧的 RAR 校验与 MD5 保留。

#### Scenario: sealed execution input

- WHEN a task begins archive execution
- THEN the service creates a task/attempt/deployment-bound snapshot under the controlled output root, copies the complete authorized inventory without following links or reparse points, verifies every relative path, size and modified-time metadata, flushes the copy, and durably marks it `sealed`
- AND the snapshot manifest records per-file relative path, size and modified-time metadata, not per-file content SHA-256
- AND WinRAR, inventory, RAR validation and Manifest generation read only the sealed snapshot, never the mutable source directory
- AND an unsealed, missing, owner-mismatched, incomplete or metadata-mismatched snapshot cannot enter WinRAR, publication, reuse or success
- AND source changes after sealing cannot change the bytes read by this attempt; failure, cancellation, crash and retry never reuse a prior attempt snapshot
