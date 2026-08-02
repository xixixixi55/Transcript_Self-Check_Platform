# 数据模型 Spec

> 本文档定义项目的数据模型，是类型定义的唯一真相源。
> 新增 type/interface 后 MUST 同步更新本文档。
> 一致性由 npx tsx scripts/check-docs.ts 自动检查。
>
> 本文件同时区分“类型已存在”和“生产已接线”：类型定义及单元测试只能证明基础实现存在，不能证明生产 Controller 已启用该管线。当前正式输出仍使用 `InspectionReport` legacy DTO；Shadow 已接入解析、归档/预览和 Legacy DOCX 成功后的导出输入旁路并只提供脱敏诊断，Canonical 正式输出未启用，`DocumentRenderPlan` 尚无生产类型、构造和消费。解析缓存、`ArchiveContext` metadata 快照和请求存活性治理属于已接入的运行时能力，但不改变正式归档的全量安全校验。Phase 1–4 最终集成人工验收已于 2026-07-31 通过；延期资源验收不阻塞 Canonical 类型、适配器、只读预览、编辑门控、候选输出隔离或回滚演练的开发/验证，但仍阻塞 Canonical 成为默认唯一正式输出以及 OpenSpec 归档，除非补测通过或发布负责人接受风险。真实浏览器小型纯合成输入仅产生单卷 RAR，多分卷边界由 Harness/自动化覆盖。

## 实体定义

<!-- 以下为初始模板，请在首次迭代时填充 -->

### 文书类型枚举（RecordType）

| 字段 | 类型 | 说明 |
|------|------|------|
| ELECTRONIC_INSPECTION | enum | 电子数据检查笔录（优先实现） |
| FORENSIC_REPORT | enum | 专业化勘查报告 |
| DIGITAL_FORENSIC | enum | 电子数据鉴定文书 |
| SCENE_TRIPLE_RECORD | enum | 传统现场三录 |
| SCENE_INSPECTION | enum | 传统现场检查笔录 |
| FORENSIC_MEDICAL | enum | 法医鉴定文书 |

### 检查笔录（InspectionRecord）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | 唯一标识 |
| record_type | RecordType | 文书类型 |
| case_number | string | 案件编号 |
| created_at | string (ISO 8601) | 生成时间 |
| updated_at | string (ISO 8601) | 最后修改时间 |
| source_report_path | string | 源 HTML 取证报告路径 |
| template_path | string | 使用的 Word 模板路径 |
| output_path | string | 生成的 .docx 输出路径 |
| status | RecordStatus | 状态（草稿/已完成/已归档） |

### 文书状态（RecordStatus）

| 字段 | 类型 | 说明 |
|------|------|------|
| DRAFT | enum | 草稿（可继续编辑） |
| COMPLETED | enum | 已完成（待归档） |
| ARCHIVED | enum | 已归档 |

### HTML 解析结果（ParsedReport）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | 唯一标识 |
| source_path | string | 源 HTML 文件路径 |
| parsed_at | string (ISO 8601) | 解析时间 |
| extracted_fields | object (JSON) | 提取的结构化字段（key-value） |
| raw_sections | object (JSON) | 按章节分组的原始内容 |

### 文书模板（RecordTemplate）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | 唯一标识 |
| name | string | 模板名称 |
| record_type | RecordType | 适用的文书类型 |
| file_path | string | .docx 模板文件路径 |
| placeholders | string[] | 模板中的 {{占位符}} 列表 |
| version | string | 模板版本号 |

### API 请求（GenerateRecordRequest）

| 字段 | 类型 | 说明 |
|------|------|------|
| report_path | string | 源 HTML 取证报告路径 |
| template_id | string | 使用的模板 ID |
| record_type | RecordType | 文书类型 |
| case_number | string | 案件编号 |

### API 请求（UpdateRecordRequest）

| 字段 | 类型 | 说明 |
|------|------|------|
| fields | Record<string, string> | 需要更新的字段键值对 |

### API 响应（RecordListResponse）

| 字段 | 类型 | 说明 |
|------|------|------|
| records | InspectionRecord[] | 笔录列表 |
| total | number | 总数 |

---

> **注意**：以上为初始数据模型骨架。
### 检材条目（EvidenceItem）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| device_type | string | 设备类型 |
| model | string（可选） | 具体型号 |
| imei1 | string（可选） | IMEI1 |
| imei2 | string（可选） | IMEI2 |
| serial_number | string（可选） | 序列号 |
| evidence_number | string | 检材编号 |

### 检查人员（Inspector）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 姓名 |
| unit | string | 单位 |
| badge_number | string | 警号 |

### 软件工具（SoftwareItem）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 名称 |
| version | string | 版本号 |

### 检查过程步骤（ProcessStep）

| 字段 | 类型 | 说明 |
|------|------|------|
| step_number | number | 步骤编号 |
| content | string | 步骤内容 |

### 检查结果（InspectionResult）

| 字段 | 类型 | 说明 |
|------|------|------|
| evidence_number | string | 检材编号 |
| software_name | string | 软件名称 |
| software_version | string | 软件版本 |
| data_summary | string | 数据分类摘要 |
| rar_filename | string | legacy 兼容字段；文件夹解析不生成最终归档文件名 |
| md5_hash | string | legacy 兼容字段；文件夹解析不生成最终归档 MD5 |
| file_size | string | legacy 兼容字段；文件夹解析当前仅保留空值/零值语义，不表达最终归档大小 |

### 表格数据（TableData）

| 字段 | 类型 | 说明 |
|------|------|------|
| columns | `{ key: string; title: string; width?: string }[]` | 列定义；附件1 默认五列：序号、电子数据、来源、提取方式、文件MD5哈希值 |
| rows | `Record<string, string>[]` | legacy 可编辑行数据；解析阶段的 `rar_info` 不驱动正式附件1，正式附件1由已验证 Manifest 派生的 AttachmentPlan 生成 |

### 检材照片组（MaterialPhotoGroup）

附件2使用显式的检材-照片映射。每个检材必须有且只有两张按审核顺序排列的图片；`ordered_image_ids` 不得跨检材复用或由渲染器按扁平位置推断。

| 字段 | 类型 | 说明 |
|------|------|------|
| material_id | string | 审核后检材的稳定标识 |
| material_number | string | 检材编号 |
| display_text | string | 对应图片组文字，当前模板为“检材{material_number}照片” |
| ordered_image_ids | `[string, string]` | 该检材的正面、反面两张图片 ID，保持组内顺序 |
| source_order | number | 审核后的检材组顺序，从1开始 |

### 检查笔录全文（InspectionReport）

顶层结构，包含 title、document_number、可选 case_number、introduction（9字段）、inspection（4字段）和 attachments（含 `photo_ids`、可选 `photo_groups`、光盘字段）。其中 `photo_groups` 存在图片时必须明确每个检材的两张图片归属和顺序。

### RAR/压缩包文件信息（RarInfo）

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名 |
| md5 | string | MD5 哈希值（32位十六进制） |
| size_bytes | number | 文件大小（字节） |
| size_display | string | 格式化后的文件大小（如 "11.77 MB"） |

`rar_info` 是旧解析响应兼容字段，不是最终归档事实源。文件夹解析不生成最终归档信息，当前返回从 legacy 检查结果重建的空值/零值兼容数据；这些值不得视为归档完成。压缩包直接上传时，`rar_info` 保存原始上传压缩包的实际文件名、MD5、字节数和格式化大小。字段类型仍兼容 null，但 deprecated `compress=false` 不再能可靠决定 `rar_info` 是否为 null。最终归档文件名、实际大小和 MD5 只以已验证 `ArchiveManifest.parts[]` 为准。

### API 响应（ParseReportResponse）

| 字段 | 类型 | 说明 |
|------|------|------|
| report | InspectionReport | 解析生成的笔录全文 |
| parsed_files | string[] | 已解析的源文件列表 |
| rar_info | RarInfo \| null | 旧解析响应兼容字段；压缩包直传时含上传包实际信息，文件夹解析时仅可能为空/零兼容数据；不表达最终归档状态 |
| archive_context_id | string \| null | 后端生成的不可预测归档上下文标识；不包含本地路径 |
| archive_context | `ArchiveContextSummary` \| null | 仅含上下文标识、文件数、总字节数、状态、创建时间和过期时间；不含案件目录、允许根目录或安装路径 |
| archive_status | ArchiveExecutionStatus \| null | 归档执行阶段 |

### API 响应（ClearReportParsingCacheResponse）

| 字段 | 类型 | 说明 |
|------|------|------|
| cleared_count | number | 本次删除的持久化报告解析缓存条数；空缓存时为 0 |

### API 请求（ExportRecordRequest）

| 字段 | 类型 | 说明 |
|------|------|------|
| report | InspectionReport | 笔录全文 |
| photo_ids | string[] | 已上传图片ID列表 |

### API 响应（ExportRecordResponse）

| 字段 | 类型 | 说明 |
|------|------|------|
| download_url | string | 下载地址 |
| filename | string | 文件名 |
| document_number | string | 文号 |

### 硬件设备（HardwareDevice）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| name | string | 设备名称 |
| model | string | 型号 |
| description | string | 描述（可选） |

---

具体字段和关系将在首次迭代 `/harness:propose` 中根据实际业务需求细化。

## 第一批迁移基础模型

以下类型属于报告适配与迁移边界的基础契约。它们不替换现有
`InspectionReport` 公共 DTO，也不承载 Word 排版或业务规划计算。

### CanonicalInspectionCase 及相关类型

`MaterialKind` 取 `phone`、`tablet` 或 `unconfirmed`；`IdentifierType` 取
`imei1`、`imei2` 或 `serial_number`。`MaterialIdentifier` 保存通用标识值及
`FieldProvenance`；`Material` 保存检材、标识和来源；`InspectorSnapshot` 保存
按报告选择顺序排列的检查人员快照；`SoftwareCategory` 表示
`main_forensic`、`winrar`、`python_hashlib` 或迁移期的 `unclassified`；
`ConfirmationStatus` 表示 `confirmed` 或 `unconfirmed`。

`CanonicalCaseInfo`、`CanonicalInspectionPeriod`、`CanonicalInspectionResult`、
`CanonicalInspectionDetails`、`PhotoReference`、`ArchiveManifestSummary`、
`CanonicalAttachmentInputs` 共同组成 `CanonicalInspectionCase`。来源字段只
通过 `FieldProvenance` 表达来源文件、JSON 路径、适配器和置信度，不在来源对象
中保存原始敏感值。

### 运行模式、导出门控和 Shadow 比较

`PipelineMode` 取 `legacy`、`shadow` 或 `canonical`；`RuntimeVersions` 与
`PipelineSettings` 由后端集中读取；`PipelineRunStatus` 表示运行结果状态。
`ExportGateBlockerCode`、`ExportGateIssue` 和 `ExportGateResult` 表达纯校验
结果。`ShadowDifference` 与 `ShadowComparisonResult` 只表达字段路径、状态和
诊断代码，不表达真实案件、人员或设备标识值。

类型索引：`type MaterialKind`、`type IdentifierType`、`type SoftwareCategory`、
`type ConfirmationStatus`、`interface FieldProvenance`、`interface MaterialIdentifier`、
`interface Material`、`interface InspectorSnapshot`、`interface SoftwareTool`、
`interface PrimarySoftware`、`interface DiscSequence`、
`interface CanonicalCaseInfo`、`interface CanonicalInspectionPeriod`、
`interface CanonicalInspectionResult`、`interface CanonicalInspectionDetails`、
`interface PhotoReference`、`interface ArchiveManifestSummary`、
`interface CanonicalAttachmentInputs`、`interface CanonicalInspectionCase`、
`type ExportGateBlockerCode`、`interface ExportGateIssue`、`interface ExportGateResult`、
`type PipelineMode`、`interface RuntimeVersions`、`interface PipelineSettings`、
`type PipelineRunStatus`、`type ShadowPipelineStatus`、`interface ShadowDifference`、`interface ShadowComparisonResult`。

### 检材类型确认与检查人员库

`PrimarySoftware` 保存名称、版本、派生显示值、来源和确认状态；`primary_software`
是审核页唯一可编辑的主取证软件结构，兼容的 `software_name`、`software_version`
和 `software_tools` 从它派生。`MaterialClassificationStatus` 取 `confirmed_by_report`、`confirmed_by_user` 或
`unconfirmed`；`MaterialClassificationSource` 取 `report`、`user` 或 `none`。
`MaterialClassification` 保存检材类型确认状态、来源、规则版本和非敏感诊断码。
自动候选只读取报告明确的 `device_type` 字段，并使用受控词表归一化；未确认的
检材类型由导出门控阻止。

`InspectorLibraryRecord` 表示当前可选择的人员库记录，包含唯一 `id`、`name`、
`unit`、`police_number`、`enabled` 以及创建和更新时间。人员库记录与报告中的
`InspectorSnapshot` 分离；快照保存报告生成时的姓名、单位、警号和顺序，不随人员库
后续修改而变化。旧 `introduction.inspectors` 仅作为由快照派生的 legacy 投影。

`DiscSequence` 保存首个光盘编号解析结果的 `prefix`、真实日期、首序号、输入位宽
和规范化首编号；`generateDiscNumbers` 只根据该结构和最终卷数派生后续编号，不能
根据目录位置或预估卷数伪造正式清单。

### 归档规划与最终清单

归档输入授权采用配置根目录与未来受控本机精确目录授权双轨模型。`report_dir` 仅是 deprecated 的一次性上下文创建参数；根目录外普通提交不得自动信任，后续接口只接受 `archive_context_id`。当前上下文只在进程内存中保存，服务重启后按 `ARCHIVE_CONTEXT_NOT_FOUND` 处理；过期/忙碌分别返回稳定错误，清理只删除系统元数据和系统临时产物。已验证的 ArchiveManifest/RAR 另有 `output/compressed/.archive-manifest-index.json` 登记，保存不透明目录键、输入/归档指纹和相对归档目录，不保存供前端展示的绝对路径；该登记与解析缓存独立，供后续独立归档清理策略识别未引用产物。

解析阶段只建立 `archive_context_id` 和后端输入快照，不执行压缩。报告解析缓存保存在
`output/parsed/`，按规范化目录不透明键区分，记录源内容指纹和 `last_accessed_at`，有效记录最多 5 条并按 LRU 淘汰；其清理不触碰 `output/compressed/`。审核完成并通过执行前门禁后，`ArchivePlan` 记录案件展示名、安全归档基础名、相对输入文件清单、
十进制字节总量、固定分卷档位、预计与最大卷数、首个光盘编号、重规划上限和诊断。
生产档位为 4GB、22GB、45GB，容量单位为十进制 GB；计划模型不保存输入绝对路径。

预览来源与正式归档上下文使用明确的生命周期合同。`ArchivePreparationStatus` 取
`not_prepared`、`preparing`、`ready` 或 `failed`；其中 `not_prepared` 表示报告解析已完成但完整
inventory、Manifest 和 RAR 尚未准备，不能被当作正式归档证据。`ArchiveContextKind` 取
`preview_source` 或 `formal`，分别表示轻量预览来源记录和已通过正式归档准备门控的上下文。
`ArchiveLifecycleStatus` 是 `ArchiveExecutionStatus | ArchivePreparationStatus`，因此
`ArchiveContextSummary.status` 同时能够表达预览准备状态和正式归档执行状态；`idle` 不表示尚未建立预览来源记录。

档位合同为：4GB 与 22GB 档预计超过 2 卷时升级，45GB 档最多 3 卷，超过 135GB 在执行前阻止；初始执行后最多允许 2 次向上 replan。`volume_size_bytes` 表达档位每卷上限，`ArchivePart.size_bytes` 表达实际 part 文件大小，两者不得混用。

`ArchiveExecutionStatus` 表示 idle、planning、blocked、compressing、validating、
hashing、completed 或 failed。WinRAR 成功退出不直接产生清单；只有当前执行目录中的
分卷按数字连续、非零且满足 `0 < actual_size <= volume_size_bytes`，并且首卷通过
WinRAR 完整性测试后，才能使用 Python `hashlib` 流式计算 MD5 并构建 `ArchiveManifest`。
Manifest 的 parts 按实际文件系统结果排序，保存文件名、`size_bytes`、MD5、光盘编号、刻录日期、`volume_size_bytes` 和 `disc_capacity_bytes`，不保存绝对路径。每个 part 的 `disc_capacity_bytes` 只按其 `size_bytes` 独立选择最小可容纳的十进制 4GB/22GB/45GB 容量；不得直接继承 Manifest 档位。最终 Manifest 是 Word 正文、附件一和附件三归档字段的唯一事实源。归档成功后再调用文书导出；文书导出失败不撤销已验证的 Manifest。再次解析同一目录时，只有输入和归档指纹一致且 Manifest/RAR 重新通过存在性、精确大小和 MD5 校验，才可将已有 Manifest 登记绑定到新的 opaque context；输入变化或物理归档校验失败时旧登记失效并重新生成，旧 RAR 不由解析缓存清理逻辑删除。

当前生产 renderer 消费 `InspectionReport` 兼容数据、最终 `ArchiveManifest`、`AttachmentPlan` 和 `current-template-v1` TemplateProfile。`DocumentRenderPlan` 是未来统一渲染合同，不属于当前生产模型。

类型索引追加：`interface ArchiveContextSummary`、`type ArchiveVolumeTier`、`type ArchivePlanStatus`、
`type ArchiveValidationStatus`、`type ArchiveExecutionStatus`、`type ArchivePreparationStatus`、
`type ArchiveContextKind`、`type ArchiveLifecycleStatus`、
`interface ArchiveSourceEntry`、`interface ArchiveDiagnostic`、
`interface ArchiveCapability`、`interface ArchivePlan`、`interface ArchivePart`、
`interface ArchiveManifest`、`interface ArchiveExecutionResponse`。

类型索引追加：`type MaterialClassificationStatus`、
`type MaterialClassificationSource`、`interface MaterialClassification`、
`interface InspectorLibraryRecord`。

### Additional migration support types

`PrimarySoftwareCandidate` stores an explicit report candidate pair. `DiscSequenceErrorCode` identifies first-disc parsing failures, and `DiscSequenceParseResult` stores the validation result, parsed sequence, and diagnostic code.

Type index: `type PrimarySoftwareCandidate`, `type DiscSequenceErrorCode`, `interface DiscSequenceParseResult`.

### Persistent case workbench foundation

The persistent workbench uses `WorkbenchSchemaVersion` and `WorkbenchApiVersion` as
version contracts while keeping the Legacy `InspectionReport` as the only formal
report body. `CaseShell` is created before parsing and may represent a queued or
failed parse without being reviewable. `CaseDraft` is created only after successful
parsing and stores bounded business DTOs, `FieldState` values and opaque asset
references; it does not store images, Base64, complete HTML or raw JSON collections.

`CaseLifecycle` separates shell, parsing, review, archive and cleanup states.
`TaskKind`, `TaskStatus` and `TaskStage` describe durable task recovery, including
`interrupted` tasks after restart. `SourceRecord` binds a case and task to an opaque
source ID, an authorized root ID, metadata and fingerprint; internal locators are
never part of the public DTO. A source may carry a stable
`revalidation_error_code` while verification is pending or temporarily unavailable;
this diagnostic does not expose a locator. `OpaqueAssetRef` identifies controlled
large objects without embedding their content in SQLite.

`WordDownloadName` is the Phase 2 T007 shared DTO for a browser-facing download
name only. It never contains a server physical artifact name. Its introduction
is used by the current Phase 2 download-name dialog and Legacy export flow:
each export asks for a validated client-facing name, cancellation creates no
download artifact, and the server physical artifact name remains unique and
independent. The current order, provenance and export interaction contract is
recorded in the living electronic-inspection-record spec; this DTO still never
contains a server locator or physical artifact name.

Phase 1D recovery keeps parse and source verification state durable across process
restart. Queued/running/cancelling parse tasks become retryable or interrupted
according to their persisted state, pending source verification remains pending for
later controlled rescheduling, and active edit leases from the previous deployment
instance are expired. A case in `archive_queued` or `archiving` without a verified
formal artifact becomes `archive_interrupted`; it remains viewable/editable and can
leave only through an explicit deferred decision or a newly accepted immediate
attempt. Recovery does not create a persistent archive worker, progress contract,
automatic retry, or automatic WinRAR continuation.

`ArchiveAttemptRecord` is the minimal public, path-free record around the existing
Legacy explicit archive entry. Its status is `accepted | running | succeeded |
failed | interrupted`, and its cleanup status is `not_required | pending | succeeded
| failed | unknown`. Public fields contain only opaque IDs, revisions, stable error
codes and timestamps; process IDs, command lines, staging locators and ownership
markers remain backend-only. A succeeded attempt and verified formal artifacts are
not rolled back by restart recovery. Workbench archive contexts are distinguished
from Legacy contexts by an internal, one-way context hash bound to exactly one
attempt and case; the executable context itself is not persisted or restored after
restart. An attempt may also persist internal Manifest identity evidence
(`manifest_source_key`, input fingerprint and archive fingerprint). The internal,
path-free Manifest index also records the opaque workbench attempt ID before the
database success transition, closing the crash window between index publication and
attempt completion. Recovery accepts either side of that durable evidence only when
the registered Manifest, case, attempt, source revision and physical RAR contents all
validate; it then completes the same attempt atomically instead of publishing a
second artifact. These internal binding and recovery fields are not exposed by the
public DTO or public Manifest.

The durable workbench database is schema version 10. This is an internal
persistence version, not a public API version. A deployment-scoped durable owner
claims the SQLite database before workbench services start; a second deployment
instance sharing that database is rejected. This owner is a local storage
boundary and does not claim authenticated multi-user isolation.

Before formal archive execution, each workbench task/attempt creates a bound
input snapshot in the `copying` state and can use it only after the snapshot is
sealed. The sealed snapshot is the execution input for inventory, WinRAR and
Manifest generation; source locators, snapshot locators and binding evidence
remain backend-only. A failed, cancelled or interrupted snapshot is not reused
by a later attempt.

An internal attempt binding stores `source_revision`, `draft_revision` and a
canonical `report_fingerprint`; the public attempt projection continues to omit
these internal evidence fields.
The active workbench context binding additionally stores the opaque `source_id`,
the same source/draft revisions and report fingerprint, `context_kind`, expiry
and consumption timestamps. A workbench archive execution must re-read the
server-side CaseDraft and SourceRecord and match all of these values before it
can use the draft as formal archive input. A client `report_json` is therefore
only a compatibility payload: for a workbench context it is rejected when its
content fingerprint differs and is never the authoritative report. A true
Legacy context continues to use the existing Legacy report contract.

Schema version 10 also persists one immutable `archive_publish_intents` record
per workbench attempt and binds it to a task-bound `publication_id` generation.
It contains the case/attempt/source identities, source and draft revisions,
report fingerprint, manifest/archive/input identities, safe relative
final-directory identity and the public Manifest snapshot. Its phase is
monotonic: `intent_persisted` → `published` → `indexed` → `verified`, with
`conflict` as a terminal safety state. This is a durable recovery record, not a
public worker queue, scheduler, progress record or automatic retry mechanism.

SQLite durable intent/publication records are the authoritative publication
facts. The path-free JSON Manifest index is a derived projection: it must match
the durable publication identity, digest and file set, may be rebuilt from
trusted durable evidence, and fails closed when that evidence is missing or
inconsistent. Public task/result projections expose only the approved opaque
artifact metadata and never expose the generation, owner, fence or filesystem
locator that binds the publication.

The intent's context binding is the persistent workbench context hash; its
relative final-directory identity is the formal runtime context plus the
Manifest ID, because the Legacy executor may create a separate in-memory
runtime context from the workbench context. Intent creation re-reads the
server-side shell, SourceRecord, CaseDraft and active workbench binding in one
database transaction. Before the filesystem move the service performs the same
binding revalidation again. Trusted completion then re-reads SourceRecord,
CaseShell and CaseDraft in its own write transaction and requires exactly one
attempt, shell and draft update; a zero-row update rolls the transaction back.
Normal execution and restart recovery call this same trusted completion service.

Formal archive recovery uses the intent, the internal Manifest index and the
physical final directory together:

| Durable evidence | Recovery result |
|---|---|
| No intent and no formal artifact | Mark an unfinished attempt `interrupted`; require explicit new preparation. |
| Intent persisted, final directory absent | Safely interrupt the unfinished attempt; retain the durable intent, do not publish or resume automatically, and require explicit new preparation. |
| Final directory exists while intent is still `intent_persisted` | Validate all bindings and Manifest/RAR, then advance only through `published` and `indexed`; never jump directly to `indexed` or republish. |
| Final directory exists and matches a persisted intent, but the index is absent | Validate Manifest/RAR and register the same artifact, then complete the same attempt. |
| Index and final directory both match the intent | Re-run the shared trusted completion validation and idempotently complete the same attempt; a crash before `verified` only finishes the phase marker and never rolls back success. |
| Missing final directory, tampered/incomplete files, missing intent, or any identity conflict | Do not mark success, overwrite, delete or republish; preserve unknown formal output and require a new explicit attempt. Confirmed evidence conflict may enter `conflict`; temporary database/index/I/O errors retain the current phase for later explicit verification. |

Only a validated completion evidence service may write `succeeded` and
`archive_verified`; a caller-provided Manifest ID alone is not evidence.

Schema version 10 adds the internal `archive_publish_fences` table. A fence binds
one case and attempt to the source ID/revision, draft revision, report
fingerprint, one-way context hash and shell revision. At most one fence for a
case and one for an attempt may be `active`. The controlled publish-intent
transaction creates the fence and intent together after re-reading the server
facts. Active fences reject ordinary writes that could change those facts.
After restart, an active fence becomes `pending_verification` only after the
old runtime state and context binding have been invalidated. Pending evidence
does not permanently block editing: a draft/source/shell edit atomically marks
the old fence `invalidated`, so its formal artifact remains unknown and cannot
be completed or reused. Successful trusted completion consumes the fence;
release, invalidation and consumption are idempotent internal transitions.

Reconciliation is driven by every non-terminal publish intent, including an
attempt that was left `failed` after a publish-side infrastructure error. It
first converts stale runtime states to `interrupted`, then validates the intent,
fence, Manifest index and physical RAR. Temporary infrastructure failures keep
the interrupted attempt, pending evidence and formal files without republish;
only confirmed identity, target or integrity conflicts become `conflict`.

Source trust is an archive-safety gate, not a Word-export prohibition. An
`available` source exports normally; `pending` and `requires_reselection` remain
viewable, editable, previewable and exportable after an explicit client-side risk
confirmation based on the current server-returned source state. Cancelling that
confirmation cancels only that export action. Archive preparation continues to
require a trusted, current source revision.

For workbench images, the opaque reference is bound to `case_id` by the backend
asset registry. The binary lives in the controlled application asset workspace;
the public record contains only the asset ID, kind, SHA-256 fingerprint and safe
metadata. Uploads are validated and atomically finalized before a reference can
enter a case draft. Missing or corrupt content is a recoverable error, and
unreferenced temporary assets are removed after a grace period.

`SharedDefaults` is backend-persisted and deployment-scoped for the current local
operator; this scope does not provide or claim multi-user isolation. It is limited
to document number, inspection place, inspection method, hardware device, ordered
inspector snapshots and disc-number prefix. A successful draft save may send a
sparse patch containing only non-empty values that the user explicitly changed.
Case fields follow user edit > non-empty Parser report value > non-empty shared
default > system default or empty. Later cases use shared values only when the
Parser value is missing, blank, whitespace or an empty array; existing cases are
never rewritten, and Parser-derived values never create a shared-default patch. `localStorage`
is not a workbench case or shared-default source of truth. `FieldSource`
distinguishes `report`, `user` and `system_default`, while `FieldConfirmation`
separately represents pending human confirmation. `ClientIdentity` is a local
session identity, not an authenticated person. `EditLease` provides one active case
lease with expiry and takeover metadata.
`SaveStatus`, `SharedDefaultsSaveStatus` and `DualSaveResult` report draft and
shared-default persistence independently. Shared-default writes use a sparse
six-field `shared_defaults_patch`; `updated`, `unchanged`, `failed` and
`revision_conflict` are distinct statuses, and blank values do not clear stored
defaults. `RevisionConflictDto` describes optimistic concurrency failures.
`WorkbenchApiEnvelope`, `CaseShellResponse`, `CaseDraftResponse`,
`SourceRecordResponse`, `SharedDefaultsResponse` and `TaskRecordResponse` are the
versioned API DTO envelopes and contain no absolute paths.

`CaseListPage` carries opaque case-shell cards with offset/limit metadata;
`CaseDetail` joins one shell with its optional draft, source summary and parse
task; `CaseSubmission` is the immediate response after an authorized report
directory is accepted and persisted. `ArchiveDecision` is `immediate` or
`deferred`; `ArchiveDecisionResult` reports the persisted lifecycle and, for
immediate decisions, the safe public summary of the newly queued archive task.
It does not expose the internal Legacy context or archive-attempt binding.
Deferred decisions remain visible after refresh as
`archive_deferred`. `DeletePreflight` reports stable blockers without
deleting case records or formal artifacts. `CaseListResponse`,
`CaseDetailResponse` and `CaseSubmissionResponse` are the corresponding
versioned envelopes. `CaseSubmission` also exposes the current server-read
shared defaults so a newly created case can show its prefill before parsing;
the deployment instance remains server-authoritative.

`DemoReadiness` is a read-only Demo capability snapshot containing four fixed
`DemoReadinessItem` entries: backend service, source authorization, WinRAR and
archive output. `DemoReadinessKey` fixes those identities and
`DemoReadinessState` is limited to `ready`, `not_configured`, `unavailable` and
`unknown`. Items expose only a safe label, stable error code and fixed guidance;
they never contain configured roots, absolute paths, executable details,
process data, environment values or exception text.

### Phase 3 archive task shared contract

T011 adds shared types and pure rules only; it does not yet wire a database,
Worker, case-list API or card UI. `TaskRecord` keeps its existing `percent`,
`finished_at`, `error_summary`, status and cancellation fields. Archive records
may additionally carry `ArchiveProgressKind=workflow_milestone`, safe stage
metadata, `updated_at`, heartbeat/output activity, `ArchiveWorkerState` and
backend-authoritative `ArchiveTaskAction` values. Old task records may omit
these optional fields.

`ArchiveWorkflowStage` and `ArchiveWorkflowMilestonePercent` define the fixed
`0/10/20/30/75/85/90/95/100` workflow milestones. WinRAR remains at 30 while
running; output bytes and volume count are activity evidence only and never a
compression ratio. `ProgressSnapshot` is the complete shared milestone/activity
snapshot. `ArchiveTaskCardSummary` is an explicit safe projection and cannot
carry Worker IDs, leases, local paths, stacks, raw logs or internal diagnostics.

`VolumeSlot` has stable identity, plan revision, lineage, ordinal, planned bytes,
status and optional `DiscMapping`; `PlannedVolumeSlot` is a replan input.
`ArchivePlanSnapshot` stores the versioned slot plan. `ReconciledVolumeSlots`
separates active and removed slots, while `VerifiedVolumeSlot` is the bounded
Manifest convergence input. `LegacyArchiveCompatibilityStatus`,
`ResourceAdmissionStatus`, `ArchiveResourceAdmission`,
`ArchiveTaskCommandRequest` and `ArchiveTaskCommandResult` were introduced as
shared contracts; T013–T015 now persist and expose them through the single
archive-task lifecycle.

T015 adds public, path-free task projections on top of the same persistent
record. `ArchiveTaskPublicDetail` extends the card summary with task revision,
attempt ordinal, cancellation flag, safe error code and the current bounded
archive-plan snapshot. `ArchiveTaskHistory` returns those public details in
case history order without replacing prior attempts. `ArchiveTaskResult` is
available only after both the task and its bound attempt succeeded and the
persisted Manifest and physical parts revalidate; it exposes verified slot
metadata, published asset metadata and path-free part download identities, but
never locators, process ownership, commands, logs or raw diagnostics.

### Phase 4 approved template shared contract

T016 introduced the path-free shared contract. `TemplateVersionRef` stores only a `TemplateId` and semantic
version in `CaseDraft`. The corresponding `TemplateVersion` binds that reference
to an opaque asset ID, fingerprint, versioned validation-rule references and a
`TemplateApprovalRecord`; it never contains a template path or DOCX content.

`TemplateValidationResult` distinguishes a validated version from stable unknown,
unapproved, missing-asset, fingerprint-mismatch and rule-validation failures.
`WordArtifactValidity` records whether a Word artifact remains valid or was
invalidated by a template change. `TemplateSelectionImpact` fixes the Phase 4
boundary: a template change invalidates Word while leaving archive planning,
archive-task creation, the verified Manifest and disc mapping unchanged.

T017 adds the frontend registry client and review-page selector. The client
filters for complete approved versions, displays only the template ID, version
and safe acceptance summary, and submits only `TemplateVersionRef`, draft
revision and edit-lease proof. It accepts a selection result only when the
returned impact preserves archive, Manifest and disc-mapping facts.

T018 adds the persistent backend registry, immutable approval history and
case-template reference update. Registered versions bind a controlled internal
asset locator to their immutable ID, version, package fingerprint and validation
rules; public projections remain path-free. Listing and formal generation both
require the current approved status and revalidate the asset fingerprint and
Word structure before use. Switching a case reference invalidates only the Word
artifact and does not mutate archive planning, tasks, Manifest or disc mapping.
Existing cases without a reference continue to use `current-template-v1`.

T019 exposes the approved, revalidated registry and case-selection operations
under the existing workbench API. Selection uses the existing edit lease and
draft revision contracts and persists only the template ID/version. Formal Word
generation sends only opaque case identity and revision; the backend resolves
the persisted reference and revalidates current approval, fingerprint, rules and
structure through the T018 registry before the existing Legacy generator runs.

### Phase 5A retention shared contract and v11 foundation

Slice 5A-1 adds the public retention contract foundation and the SQLite persistence
foundation only. These types and tables do not mean that cleanup execution,
Coordinator scheduling, publication revalidation, formal Word file persistence,
cleaned-case download routes, API/UI wiring, E2E or manual acceptance are
implemented.

#### Retention public types

The following public types are exported from `packages/shared/types/retention.ts`
and re-exported from the shared export index. They are safe contracts: they carry
opaque case/publication/artifact identities, status, bounded summaries,
revision/digest facts and timestamps, but never absolute paths, database table
names, owner/claim tokens, leases, fences, internal attempt/context identities
or client-controlled deletion file lists.

`RetentionPolicyMode` is `disabled | preview_only | enforce`.
`RetentionEligibility` is `eligible | ineligible | unknown`.
`RetentionStatus` is `unknown | not_expired | eligible | blocked | planned |
processing | completed | failed`.
`CleanupRunPhase` is `planned | claimed | preflighted | work_files_cleaned |
records_cleaned | verified | succeeded | blocked | stale | cancel_requested |
cancelled | interrupted | partial_failure | failed_retryable | failed_terminal`.
`CleanupRunStatus` is `active | succeeded | cancelled | failed | blocked`.

`RetentionBlockerCode` is the stable union:
`RETENTION_CASE_MUTATION_TIME_MISSING`, `RETENTION_PUBLICATION_MISSING`,
`RETENTION_PUBLICATION_UNVERIFIED`, `RETENTION_PUBLICATION_TIME_MISSING`,
`RETENTION_WORD_ARTIFACT_MISSING`, `RETENTION_WORD_ARTIFACT_UNVERIFIED`,
`RETENTION_TIME_INVALID`, `RETENTION_TIME_IN_FUTURE`,
`RETENTION_NOT_EXPIRED`, `RETENTION_ACTIVE_TASK`, `RETENTION_ACTIVE_LEASE`,
`RETENTION_RECOVERY_IN_PROGRESS`, `RETENTION_OWNERSHIP_UNKNOWN`,
`RETENTION_AUTHORITY_INCONSISTENT`, `RETENTION_SNAPSHOT_ACTIVE`,
`RETENTION_SNAPSHOT_RECOVERY_REFERENCED` and
`RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN`.

`CleanupErrorCode` is the stable union:
`CLEANUP_PATH_OUTSIDE_ALLOWED_ROOT`, `CLEANUP_OWNERSHIP_UNKNOWN`,
`CLEANUP_SYMLINK_OR_JUNCTION_REJECTED`, `CLEANUP_FILE_IN_USE`,
`CLEANUP_ACCESS_DENIED`, `CLEANUP_FILE_CHANGED`,
`CLEANUP_FILE_DELETE_FAILED`, `CLEANUP_SNAPSHOT_DELETE_FAILED`,
`CLEANUP_STALE_REQUEST` and `CLEANUP_CONFLICT`.

`RetentionPolicyDto` contains `mode`, `retention_days`,
`scan_interval_seconds`, `batch_size`, `policy_revision`, nullable
`activated_at` and `updated_at`.

`RetentionStatusDto` contains `case_id`, `status`, `eligibility`, nullable
`retention_anchor_utc`, nullable `expires_at_utc`, nullable
`blocker_code`, `policy_revision`, `case_revision` and `updated_at`.

`CleanupPreviewItemDto` contains `case_id`, `eligibility`, nullable
`blocker_code`, public category names in `planned_data_categories`, public
category names in `preserved_formal_artifact_categories`, nullable anchor and
expiry timestamps, and the boolean summaries `has_running_task`,
`has_edit_lease`, `has_recovery` and `has_conflict`.
`CleanupPreviewDto` contains a `RetentionPolicyDto`, an `items` array and
`generated_at`. These are type-level safe preview contracts; no preview scan or
cleanup execution is enabled by this foundation.

`CleanupRunStatusDto` contains opaque `run_id`, `case_id`, `phase`, `status`,
nullable `result_code`, nullable `error_code`, `updated_at` and nullable
`completed_at`. Internal claim, lease and fence fields are not part of this
projection.

`FormalWordArtifactSafeProjection` contains `word_artifact_id`, `case_id`,
`publication_id`, `file_digest`, `file_size`, `source_manifest_digest`,
`template_identity`, `template_version`, `generated_at`, nullable
`verified_at` and `status` (`pending | verified | invalid`). The internal
relative path is deliberately absent from this public projection.

The backend-only `RetentionPolicyConfig` parser result is not a SharedTypes
public model and is intentionally not included in the public export list. Its
deployment inputs are `BIJI_CASE_RETENTION_MODE`,
`BIJI_CASE_RETENTION_DAYS`, `BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` and
`BIJI_CASE_RETENTION_BATCH_SIZE`, with defaults `disabled`, 30, 86400 and 20;
the legacy days key is migration-only compatibility input and cannot enable
retention work.

#### v11 persistence foundation

The SQLite persistence schema is now `WORKBENCH_DATABASE_SCHEMA_VERSION = 11`;
the existing API envelope version remains v1. The v10→v11 migration is
transactional, keeps `foreign_keys=ON`, validates `foreign_key_check`, preserves
existing source/attempt/snapshot identities and rejects unsupported future
versions. It does not delete records or files, backfill historical publication
verification times, create cleanup runs, or enable `enforce`. New installations
and upgrades initialize the durable policy in `disabled` mode.

The v11 foundation contains these new tables:

| Table | Implemented durable fields and constraints |
|---|---|
| `case_retention_policies` | deployment primary identity, `mode`, `retention_days` (1–3650), `scan_interval_seconds` (at least 3600), `batch_size` (1–1000), `policy_revision`, nullable `activated_at`, `created_at` and `updated_at`; deployment identity is unique. |
| `case_retention_records` | `retention_record_id`, deployment/case identity, `eligibility`, `status`, nullable `last_meaningful_mutation_at`, `latest_verified_formal_publication_at`, `latest_successful_word_export_at`, `retention_anchor_utc`, `expires_at_utc`, `last_blocker_code`, policy/case/cleanup revisions and timestamps; `(deployment_instance_id, case_id)` is unique. |
| `case_cleanup_runs` | run/case/deployment identity, policy and case revisions, owner/claim/lease/fence fields, current phase, retry/file/result/error fields and timestamps; a partial unique index permits at most one active run per deployment/case, with recovery, lease and deployment scan indexes. These internal claim fields are not public DTO fields. |
| `formal_word_artifacts` | Word artifact/deployment/case/publication identity, controlled internal relative path, digest, size, source Manifest digest, template identity/version, generated/verified timestamps and status; Word identity and case/publication query indexes are present. This slice creates the durable row foundation but does not persist real Word files. |

The cleanup-run repository foundation now persists planned runs and performs
deployment-scoped claim CAS against the planned policy/case revisions. A
successful claim assigns an owner, opaque claim token, lease expiry and a
monotonic fence epoch; a live claim conflicts, while an expired owned claim
can be taken over with a new fence. Owned phase/result/retry/lease updates
remain CAS-protected, and recovery listing is durable and restart-safe. The
cleaned-case records boundary below is also internal: it can only be entered
from a live deployment-scoped `work_files_cleaned` claim, while the public run
projection excludes owner, token, lease and fence fields. Candidate scheduling,
physical file deletion, source/snapshot cleanup and the public execution/API
boundary remain later capabilities.

The formal Word artifact repository persists only durable artifact metadata and
does not store the complete `report_json`. It validates lower-case SHA-256
file/Manifest digests, a non-negative JavaScript-safe file size, controlled
relative paths, UTC-Z timestamps and the consistency of `status` with
`verified_at`. Creation and reads require a current publication row bound to
the same deployment and case; reads of a verified artifact additionally
revalidate the existing publication's verified phase/status and non-null
`publication_verified_at`. The safe projection omits the internal relative
path. This is a durable metadata foundation: physical Word generation,
file-content verification and cleaned-case download remain later capabilities.

The cleaned-case tombstone repository now performs the records boundary only
after rechecking the claimed cleanup run, current policy revision, case
revision, durable retention anchor, verified publication set, verified formal
Word artifact and absence of active task, edit lease or publication recovery.
Within one SQLite transaction it consumes a path-free file-step receipt whose
snapshot and temporary-asset IDs exactly match the durable rows already marked
`cleaned`, then deletes snapshot rows, compacts formal attempt/task payloads,
deletes inactive work contexts, orphan attempts/tasks, owned temporary assets,
plans, drafts and work asset references, and deletes unreferenced source rows.
Sources still referenced by formal attempts/intents/fences become minimum
tombstones so the existing publication authority keeps its source FK. Formal
intent/fence/attempt, publication, Word and published asset facts are retained;
`PRAGMA foreign_key_check` is required before the surrounding transaction can
commit. The shell then retains its deployment/case identity and safe summary,
clears case number/source/task work references, marks `record_cleaned`,
increments the tombstone/cleanup/case revisions, advances the cleanup run to
`records_cleaned`, and updates the matching retention record to `completed`.
The cleaned shell remains queryable, while draft save/lifecycle transitions
are rejected with `CASE_RECORD_CLEANED`; formal Word/publication rows remain
untouched and can still be read by durable identity. Physical path validation,
file deletion, and public artifact listing/download remain later capabilities.

The 3.1 retention service now evaluates one case from those durable facts. It
uses the retention record's meaningful-mutation time, the maximum verified time
from every current publication intent, and the maximum verified time from the
formal Word artifact rows; no shell `updated_at`, file mtime, download time or
derived Manifest index time is substituted. The resulting anchor and continuous
24-hour expiry are persisted through the deployment/case retention projection
upsert, with `Z` timestamps and the current durable policy/case revisions.

Historical publication intents with a null `publication_verified_at` remain
unverified until a controlled internal revalidator proves the exact durable
publication identity, file inventory, RAR/Manifest/MD5 checks, fence, ownership,
deployment and case binding. Only then does the existing NULL-only publication
CAS write the supplied trusted UTC verification time. Missing or failed
revalidation leaves the field null; no timestamp is inferred and no new
publication identity is created. The same service fails closed for malformed or
future timestamps, incomplete publication/Word authority, active tasks or edit
leases, publication/recovery/snapshot/context conflicts, active cleanup runs and
non-terminal case state. It returns an internal `enforce_allowed` gate only when
the durable policy mode is `enforce`; this slice does not add a scheduler,
preview route or public cleanup execution API. The Word verifier boundary
requires the durable artifact digest, size, Manifest digest and ownership to
match; physical file resolution remains with the later cleanup/access work.

#### v11 backup, recovery, and application rollback boundary

Phase 5 defines a controlled operational backup/recovery boundary but does not
add a public backup or undelete API. A recoverable generation is a quiesced,
cross-checked set containing the v11 SQLite database, formal RAR/Manifest/MD5
publication files and durable authority, formal Word rows/files, approved
template identity/version and files, owned work assets, retention policy and
audit facts. The generation records deployment/schema identity, UTC-Z time,
relative locators, sizes and digests; SQLite integrity/FK/schema validation and
publication/Word authority checks are required before restore.

Restore is first performed in an isolated synthetic deployment with policy
`disabled`; formal files are read by durable `publication_id` and
`word_artifact_id`, and the derived Manifest index is rebuilt only from SQLite
publication facts. Missing or mismatched groups, ownership uncertainty, FK
errors, or a possible formal/source overwrite fail closed. Git/application
rollback is not data rollback: a v10 application must reject a v11 database,
and post-migration application rollback requires a matching v10 or v11 grouped
backup rather than reverse SQL or manual deletion. The controlled rehearsal
checklist is maintained in
`[harness/retention-backup-recovery.md](../../harness/retention-backup-recovery.md)`.

Existing v11 foundation fields are:

- `case_shells`: `deployment_instance_id`, `record_cleaned`,
  `tombstone_revision`, `retention_state`, `cleanup_state`, nullable
  `cleaned_at`, `last_meaningful_mutation_at`, `retention_anchor_utc`,
  `safe_display_summary` and `cleanup_revision`; cleaned compaction clears
  `case_number`, `source_id`, `parse_task_id` and `report_available` while
  preserving the safe title/summary and durable formal rows.
- `source_records`: `deployment_instance_id`, `tombstone_state`, nullable
  `tombstoned_at` and `tombstone_revision`. Cleanup deletes rows without
  formal references and compacts formally referenced rows to a minimum
  tombstone while preserving the source identity required by publication FKs.
- `task_records`: `deployment_instance_id`, nullable `publication_id`,
  nullable `word_artifact_id` and nullable `formal_verified_at`.
- `archive_publish_intents`: nullable `publication_verified_at`, which remains
  part of the existing publication durable facts rather than a second
  publication authority.

The new critical indexes include `source_deployment_state`,
`archive_publication_verified`, `case_retention_case`,
`cleanup_run_active_case`, `cleanup_run_recoverable`, `cleanup_run_lease`,
`cleanup_run_deployment_scan`, `formal_word_case` and
`formal_word_publication`. No new table uses `CURRENT_TIMESTAMP`,
`datetime('now')` or another SQLite-local time expression.

#### Phase 5 durable time contract

New Phase 5 durable timestamps are written as timezone-aware UTC ISO 8601 with
the canonical `Z` suffix. Aware timestamps with another offset are converted to
UTC before writing; naive timestamps are rejected. This applies to new policy,
retention record, cleanup run, Word artifact and `publication_verified_at`
writes. Existing v10 timestamps remain readable and are not rewritten merely
to change their textual offset. API timestamp fields retain timezone information
and `Asia/Shanghai` is display-only; it never changes UTC comparison,
retention calculation or CAS facts.

#### Not yet a living capability

The active Phase 5 delta still defines future behavior that is not delivered by
the current foundation and 3.1 service: deterministic preview scanning,
Coordinator and enforce execution, work-record/file cleanup, physical
publication/Word file revalidation integration, formal Word file generation and
download, cleaned-case routes, API/UI behavior, Windows deletion, E2E and
manual acceptance. Those behaviors remain in the active change until their
implementation and verification tasks complete.

Type index: type WorkbenchSchemaVersion, type WorkbenchApiVersion, type CaseLifecycle,
type TaskKind, type TaskStatus, type TaskStage, type ArchiveProgressKind,
type ArchiveWorkerState, type ArchiveTaskAction, type ArchiveWorkflowStage,
type ArchiveWorkflowMilestonePercent, type VolumeSlotStatus, type DiscMappingSource,
type DiscMappingConfirmation, type FieldSource, type FieldConfirmation,
type LeaseStatus, type SourceAccessStatus, type CaseAssetContentStatus, interface OpaqueAssetRef, interface CaseAssetRecord,
interface CaseAssetList, interface FieldState,
interface WordDownloadName,
interface CaseShell, interface CaseDraft, interface SharedDefaults, interface ClientIdentity,
interface EditLease, interface TaskRecord, interface SourceRecord, interface SaveStatus,
interface DiscMapping, interface VolumeSlot, interface PlannedVolumeSlot,
interface ArchivePlanSnapshot, interface ProgressSnapshot, interface ArchiveTaskCardSummary,
type LegacyArchiveCompatibilityStatus, type ResourceAdmissionStatus,
interface ArchiveResourceAdmission, interface ArchiveTaskCommandRequest,
interface ArchiveTaskCommandResult, interface ArchiveTaskPublicDetail,
interface ArchiveTaskHistory, interface ArchiveTaskResult,
interface ReconciledVolumeSlots, interface VerifiedVolumeSlot,
interface SharedDefaultsSaveStatus,
interface DualSaveResult, interface RevisionConflictDto, interface WorkbenchApiEnvelope,
interface CaseShellResponse, interface CaseDraftResponse, interface SourceRecordResponse,
interface SharedDefaultsResponse, interface TaskRecordResponse, interface CaseListPage,
interface CaseDetail, interface CaseSubmission, type ArchiveDecision,
type ArchiveDecisionStatus, interface ArchiveDecisionResult, interface DeletePreflight,
interface ArchiveAttemptRecord, type ArchiveAttemptStatus, type ArchiveCleanupStatus,
interface CaseListResponse, interface CaseDetailResponse, interface CaseSubmissionResponse,
type DemoReadinessState, type DemoReadinessKey, interface DemoReadinessItem,
interface DemoReadiness,
type TemplateId, type TemplateApprovalStatus, type TemplateErrorCode,
type WordArtifactValidity, interface TemplateVersionRef,
interface TemplateApprovalRecord, interface TemplateValidationRuleRef,
interface TemplateVersion, interface TemplateValidationSuccess,
interface TemplateValidationFailure, type TemplateValidationResult,
interface TemplateSelectionImpact,
type RetentionPolicyMode, type RetentionEligibility, type RetentionStatus,
type CleanupRunPhase, type CleanupRunStatus, type RetentionBlockerCode,
type CleanupErrorCode, interface RetentionPolicyDto,
interface RetentionStatusDto, interface CleanupPreviewItemDto,
interface CleanupPreviewDto, interface CleanupRunStatusDto,
interface FormalWordArtifactSafeProjection.
