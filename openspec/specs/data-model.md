# 数据模型 Spec

> 本文档定义项目的数据模型，是类型定义的唯一真相源。
> 新增 type/interface 后 MUST 同步更新本文档。
> 一致性由 npx tsx scripts/check-docs.ts 自动检查。
>
> 本文件同时区分“类型已存在”和“生产已接线”：类型定义及单元测试只能证明基础实现存在，不能证明生产 Controller 已启用该管线。当前正式输出仍使用 `InspectionReport` legacy DTO；Shadow 已接入解析、归档/预览和 Legacy DOCX 成功后的导出输入旁路并只提供脱敏诊断，Canonical 正式输出未启用，`DocumentRenderPlan` 尚无生产类型、构造和消费。报告解析不持久化完成结果，仅共享同一来源的在途任务；`ArchiveContext` metadata 快照和请求存活性治理属于已接入的运行时能力，但不改变正式归档的全量安全校验。Phase 1–4 最终集成人工验收已于 2026-07-31 通过；延期资源验收不阻塞 Canonical 类型、适配器、只读预览、编辑门控、候选输出隔离或回滚演练的开发/验证，但仍阻塞 Canonical 成为默认唯一正式输出以及 OpenSpec 归档，除非补测通过或发布负责人接受风险。真实浏览器小型纯合成输入仅产生单卷 RAR，多分卷边界由 Harness/自动化覆盖。

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
| extractable | boolean（可选） | 是否可提取；解析时由 IMEI1、IMEI2、序列号任一非空自动生成，存量缺失时同规则推导 |
| evidence_number | string | 检材编号 |

### 检查人员（Inspector）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 姓名 |
| unit | string | 单位 |
| position | string（历史数据可为空） | 职位 |
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

### 检查环境快照（InspectionEnvironmentSnapshot）

新案件在应用最终检查硬件默认值后采集一次本机环境快照，并持久化到可选字段 `inspection.environment_snapshot`。旧案件可缺少该字段；读取、轮询和普通保存不得因此自动重写其检查步骤。

| 字段 | 类型 | 说明 |
|------|------|------|
| operating_system.display_name | string | 本机 Windows 的稳定显示名称；无法识别时为空并由文本投影显示“待确认” |
| operating_system.status | `detected \| unavailable` | 操作系统信息识别状态 |
| security_software.name | string | 识别到的火绒安全软件名称；未识别时为空 |
| security_software.version | string | 识别到的版本；不可用时为空 |
| security_software.status | `detected \| version_unknown \| not_found \| unavailable` | 火绒安装与版本识别状态 |

### 检查环境识别状态（InspectionEnvironmentDetectionStatus）

取值为 `detected | version_unknown | not_found | unavailable`。

### 哈希算法（HashAlgorithm）

`HashAlgorithm` 是受控字符串联合类型 `md5 | sha1 | sha256`。共享默认值和新案件快照使用该类型；存量缺失值按 `md5` 兼容。

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
| hash_algorithm | `md5 \| sha1 \| sha256`（可选） | 案件业务哈希算法快照；存量缺失时按 `md5` 兼容 |

### 表格数据（TableData）

| 字段 | 类型 | 说明 |
|------|------|------|
| columns | `{ key: string; title: string; width?: string }[]` | 列定义；附件1默认五列，末列标题按案件算法显示文件 MD5、SHA-1 或 SHA-256 哈希值 |
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

顶层结构，包含 title、最终完整 `document_number`、可选 `document_number_template` 案件快照、可选 case_number、introduction（9字段）、inspection（4字段）和 attachments（含 `photo_ids`、可选 `photo_groups`、光盘字段）。其中 `photo_groups` 存在图片时必须明确每个检材的两张图片归属和顺序。`document_number_template` 只含 `prefix` 和 `suffix` 字符串；审核编辑可用该快照输入案件编号并生成完整 `document_number`，Word、预览和导出文件名仍只消费完整文号。

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
| company | string | 所属公司；旧持久化记录缺失时规范化为空字符串 |

---

具体字段和关系将在首次迭代 `/harness:propose` 中根据实际业务需求细化。

## 第一批迁移基础模型

以下类型属于报告适配与迁移边界的基础契约。它们不替换现有
`InspectionReport` 公共 DTO，也不承载 Word 排版或业务规划计算。

### CanonicalInspectionCase 及相关类型

`MaterialKind` 取 `phone`、`tablet` 或 `unconfirmed`；`IdentifierType` 取
`imei1`、`imei2` 或 `serial_number`。`MaterialIdentifier` 保存通用标识值及
`FieldProvenance`；`Material` 保存检材、标识、可提取状态和来源；`InspectorSnapshot` 保存
按报告选择顺序排列的检查人员快照；`SoftwareCategory` 表示
`main_forensic`、`winrar`、`python_hashlib`、`hashmyfiles` 或迁移期的 `unclassified`；
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
`unit`、`position`、`police_number` 以及创建和更新时间，不包含启用/停用状态；所有未删除记录均可选择。人员库记录与报告中的
`InspectorSnapshot` 分离；快照保存报告生成时的姓名、单位、职位、警号和顺序，不随人员库
后续修改而变化。旧 `introduction.inspectors` 仅作为由快照派生的 legacy 投影。

`DiscSequence` 保存介质编号解析结果的 `prefix`、真实日期、可选两位 `user_identifier`、首序号、输入位宽
和规范化首编号；正式标准分卷同时接受 `GPyyyyMMdd-序号` 与 `GPyyyyMMddXX-序号`，超大单卷同时接受 `YPyyyyMMdd-序号` 与 `YPyyyyMMddXX-序号`，其中可选的 `XX` 为两位数字用户标识。`generateDiscNumbers` 只根据该结构和最终卷数派生后续编号，不自动补写或删除用户标识，且只递增末尾序号，不能
根据目录位置或预估卷数伪造正式清单。

### 归档规划与最终清单

归档输入授权采用配置根目录与未来受控本机精确目录授权双轨模型。`report_dir` 仅是 deprecated 的一次性上下文创建参数；根目录外普通提交不得自动信任，后续接口只接受 `archive_context_id`。当前上下文只在进程内存中保存，服务重启后按 `ARCHIVE_CONTEXT_NOT_FOUND` 处理；过期/忙碌分别返回稳定错误，清理只删除系统元数据和系统临时产物。已验证的 ArchiveManifest/RAR 另有 `output/compressed/.archive-manifest-index.json` 登记，保存不透明目录键、输入/归档指纹和相对归档目录，不保存供前端展示的绝对路径；该登记属于归档生命周期，供后续独立归档清理策略识别未引用产物。

解析阶段只建立 `archive_context_id` 和后端输入快照，不执行压缩。每个顺序解析请求重新读取当前来源并运行 Parser，不保存可供后续请求复用的解析结果；同一规范化来源同时进行的请求可以共享在途任务。审核完成并通过执行前门禁后，`ArchivePlan` 记录案件展示名、安全归档基础名、相对输入文件清单、
二进制字节总量、归档模式、固定分卷档位、预计与最大卷数、首个光盘编号、重规划上限和诊断。
生产档位为 4GB、22GB、45GB，容量单位满足 `1GB = 1024³` 字节；计划模型不保存输入绝对路径。

预览来源与正式归档上下文使用明确的生命周期合同。`ArchivePreparationStatus` 取
`not_prepared`、`preparing`、`ready` 或 `failed`；其中 `not_prepared` 表示报告解析已完成但完整
inventory、Manifest 和 RAR 尚未准备，不能被当作正式归档证据。`ArchiveContextKind` 取
`preview_source` 或 `formal`，分别表示轻量预览来源记录和已通过正式归档准备门控的上下文。
`ArchiveLifecycleStatus` 是 `ArchiveExecutionStatus | ArchivePreparationStatus`，因此
`ArchiveContextSummary.status` 同时能够表达预览准备状态和正式归档执行状态；`idle` 不表示尚未建立预览来源记录。

type ArchiveMode 取 `standard_split` 或 `oversized_single_volume`，type ArchiveMedium 取 `optical_disc` 或 `hard_drive`，两者固定一一对应。档位合同为：4GB 与 22GB 档预计超过 2 卷时升级，45GB 档最多 5 卷；不超过 225GB 使用 `standard_split` 和光盘，超过 225GB 使用 `oversized_single_volume` 和硬盘并生成单一 `<案件名>.rar`。模式只看压缩前输入总量，压缩后的实际大小不重新分类。默认资源准入不再以旧 135GB 上限阻断，但部署人员可显式配置本机输入安全上限。标准分卷初始执行后最多允许 2 次向上 replan。`volume_size_bytes` 表达标准档位每卷上限，`ArchivePart.size_bytes` 表达实际文件大小；超大单卷的 `volume_size_bytes` 与 `volume_tier_gb` 为空，附件与 Word 计划继续保留这些空值而不伪造光盘容量档位。

`ArchiveExecutionStatus` 表示 idle、planning、blocked、compressing、validating、
hashing、completed 或 failed。WinRAR 成功退出不直接产生清单；只有当前执行目录中的
标准分卷按数字连续、非零且满足 `0 < actual_size <= volume_size_bytes`；超大单卷只接受一个非空的 `<案件名>.rar`。首个 RAR 通过
WinRAR 完整性测试后，才能使用 Python `hashlib` 流式计算 MD5 并构建 `ArchiveManifest`。
Manifest 的 parts 按实际文件系统结果排序，保存模式、文件名、`size_bytes`、内部完整性 `md5`、案件业务 `hash_algorithm` 与 `hash_value`、历史字段名 `disc_number` 所承载的介质编号与日期，不保存绝对路径。`hash_algorithm` 取 `md5 | sha1 | sha256`；选择 MD5 时 `hash_value` 复用 `md5`，选择 SHA-1/SHA-256 时保存对应完整十六进制摘要；旧 part 缺少新增字段时以 `md5` 和现有 `md5` 兼容投影。标准分卷额外保存 `volume_size_bytes` 和按实际大小选择的最小二进制 4GB/22GB/45GB `disc_capacity_bytes`；超大单卷这两个容量字段为空。`ArchiveTaskResult` 与 `DiscMappingResult` 对外同时投影 `archive_medium`，供审核界面和 Word 选择光盘或硬盘语义。未带模式的历史 Manifest 按旧十进制规则复核。最终 Manifest 是 Word 正文、附件一和附件三归档字段的唯一事实源。归档成功后再调用文书导出；文书导出失败不撤销已验证的 Manifest。再次解析同一目录时，只有输入和归档指纹一致且 Manifest/RAR 重新通过存在性、精确大小和 MD5 校验，才可将已有 Manifest 登记绑定到新的 opaque context；输入变化或物理归档校验失败时旧登记失效并重新生成，旧 RAR 不由解析缓存清理逻辑删除。

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

类型索引追加：`interface ArchivePartDiscMapping`、`interface DiscMappingRequest`、
`interface DiscMappingResult`、`interface UnifiedExportRequest`、
`interface UnifiedExportOutput`、`interface UnifiedExportResult`、
`interface ExportRecord`、`type ExportDirectoryResult`、
`interface OpenExportDirectoryResult`、`type ArchiveCompletionStatus`。
（盘号映射与统一导出契约：压缩允许先无盘号执行，压缩后输入首个盘号自动生成全序列并映射到 plan 槽位；统一导出把最新 Word + 全部 RAR 写入用户选择路径，导出路径由后端 native picker（`LocalDirectoryPickerService`）选择并返回，导出审计不保存绝对路径。`ExportDirectoryResult` 是 picker 的选择结果契约：`{ path, token }` 或 `{ cancelled }`。案件最后成功导出路径只由专用本地 Repository 按 `case_id` 保存；`OpenExportDirectoryResult` 只返回案件标识、打开成功标记和导出时间，不向前端回传路径。）

### 其他迁移支持类型

`PrimarySoftwareCandidate` 保存显式报告候选对。`DiscSequenceErrorCode` 标识首盘编号解析失败，`DiscSequenceParseResult` 保存校验结果、解析后的序列和诊断码。

类型索引：`type PrimarySoftwareCandidate`、`type DiscSequenceErrorCode`、`interface DiscSequenceParseResult`。

### 持久化案件工作台基础

持久化工作台以 `WorkbenchSchemaVersion` 和 `WorkbenchApiVersion` 作为版本合同，同时保留 Legacy `InspectionReport` 作为唯一正式报告正文。`CaseShell` 在解析前创建，可表示排队或失败且不可审核的解析。`CaseDraft` 仅在解析成功后创建，保存有界业务 DTO、`FieldState` 值和不透明资产引用；不保存图片、Base64、完整 HTML 或原始 JSON 集合。

`CaseLifecycle` 区分外壳、解析、审核、归档和清理状态。`TaskKind`、`TaskStatus` 和 `TaskStage` 描述持久任务恢复，包括重启后的 `interrupted` 任务。`SourceRecord` 将案件和任务绑定到不透明来源 ID、授权根目录 ID、元数据和指纹；内部定位符绝不属于公共 DTO。验证待处理或暂时不可用时，来源可携带稳定的 `revalidation_error_code`，该诊断不暴露定位符。`OpaqueAssetRef` 标识受控大对象，而不在 SQLite 中嵌入其内容。

`CasePhotoBindingRequest` 是字段级图片绑定命令，携带期望的不透明图片引用、调用方最后观察到的有序图片 ID 列表（作为图片域比较并设置基线）及有效编辑租约凭据。`CasePhotoBindingResult` 返回合并后的完整最新 `CaseDraft`，使客户端能将待处理的非图片编辑重新基于新修订应用。两项合同均不含图片二进制内容或文件系统定位符。

`WordDownloadName` 是第二阶段 T007 的共享 DTO，只承载面向浏览器的下载名称，绝不包含服务器物理产物名称。当前第二阶段下载名称对话框和 Legacy 导出流程使用该类型：每次导出都询问并校验面向客户端的名称；取消时不创建下载产物；服务器物理产物名称保持唯一且相互独立。当前顺序、来源和导出交互合同记录在现行 electronic-inspection-record 规格中；该 DTO 仍绝不包含服务器定位符或物理产物名称。

`WordDirectoryExportTarget` 将 Windows 选择器选定的目录及其一次性精确目录授权令牌从前端传给独立 Word 导出请求。文档原子发布到该位置后，`WordDirectoryExportResult` 只返回最终导出目录和净化后的 Word 文件名。两项 DTO 均不授予可复用文件系统访问权限；不含目标的 Legacy 请求继续返回浏览器下载响应。

`WordExportWarning` 为安全省略可选章节但成功完成的独立 Word 导出携带稳定警告码和用户可见消息。当前生成方在图片无效或不完整而省略附件 2 时使用该类型；警告不会将成功的 Word 结果变为导出失败。

### 来源授权请求类型

`SourceAuthorizationRequest` 是普通前端来源目录开关的共享请求片段。`source_authorization_enabled` 为显式字段：持久化的首页偏好控制工作台和 legacy 目录解析请求，而直接 API 调用方默认仍接受严格授权。`CaseSubmissionRequest` 携带初始工作台来源路径和可选案件元数据；`SourceReplacementRequest` 携带替换路径和预期来源修订；`ParseReportDirectoryRequest` 是 legacy 目录解析合同。三类请求均可携带可选的 `directory_grant_token`，但关闭授权绝不会移除后端基本的本地路径和输出隔离安全检查。

`CaseDirectorySubmissionRequest` 是受信任的本地 Windows 文件夹选择器桥接所使用的无路径工作台请求。它携带可选案件元数据和持久化授权偏好；浏览器绝不提供选定的绝对路径。后端选择目录后，立即将该路径送入同一来源登记和解析提交链路。

类型索引：`interface SourceAuthorizationRequest`、
`interface CaseSubmissionRequest`, `interface SourceReplacementRequest`,
`interface ParseReportDirectoryRequest`、`interface CaseDirectorySubmissionRequest`。

第 1D 阶段恢复使解析和来源验证状态跨进程重启保持持久。排队/运行/取消中的解析任务依其持久状态变为可重试或已中断；待定来源验证继续保持待定，以便后续受控重新调度；上一部署实例的有效编辑租约到期。没有已验证正式产物且处于 `archive_queued` 或 `archiving` 的案件变为 `archive_interrupted`；它仍可查看/编辑，只能通过显式延期决定或新接受的立即尝试离开该状态。恢复不会创建持久归档 Worker、进度合同、自动重试或自动继续 WinRAR。

`ArchiveAttemptRecord` 是围绕既有 Legacy 显式归档入口的最小无路径公共记录。状态为 `accepted | running | succeeded | failed | interrupted`，清理状态为 `not_required | pending | succeeded | failed | unknown`。公共字段只包含不透明 ID、修订、稳定错误码和时间戳；进程 ID、命令行、暂存定位符和所有权标记仅限后端。重启恢复不会回滚成功尝试和已验证正式产物。内部单向上下文哈希将恰好一次尝试和一个案件绑定，用于区分工作台归档上下文与 Legacy 上下文；可执行上下文本身不持久化，也不在重启后恢复。尝试还可持久化内部 Manifest 标识证据（`manifest_source_key`、输入指纹和归档指纹）。内部无路径 Manifest 索引在数据库成功转换前记录不透明工作台尝试 ID，以封闭索引发布与尝试完成之间的崩溃窗口。只有已登记 Manifest、案件、尝试、来源修订和物理 RAR 内容全部通过校验时，恢复才接受任一侧持久证据，并原子完成同一尝试而非发布第二份产物。这些内部绑定和恢复字段不向公共 DTO 或公共 Manifest 暴露。

持久工作台数据库的模式版本为 10。这是内部持久化版本，不是公共 API 版本。工作台服务启动前，由部署范围内的持久所有者认领 SQLite 数据库；共享该数据库的第二个部署实例会被拒绝。该所有者是本地存储边界，并不宣称提供已认证多用户隔离。

正式归档执行前，每个工作台任务/尝试都创建处于 `copying` 状态的绑定输入快照，并且只能在快照封存后使用。封存快照是清单、WinRAR 和 Manifest 生成的执行输入；来源定位符、快照定位符和绑定证据仅限后端。失败、取消或中断的快照不得被后续尝试复用。

内部尝试绑定保存 `source_revision`、`draft_revision` 和规范 `report_fingerprint`；公共尝试投影继续省略这些内部证据字段。有效工作台上下文绑定还保存不透明 `source_id`、相同的来源/草稿修订与报告指纹、`context_kind`、到期时间和消费时间。工作台归档执行必须重新读取服务端 CaseDraft 和 SourceRecord 并匹配全部值，才能将草稿用作正式归档输入。因此客户端 `report_json` 只是兼容载荷：工作台上下文中其内容指纹不同时会被拒绝，且绝不是权威报告。真正的 Legacy 上下文继续使用既有 Legacy 报告合同。

模式版本 10 还为每次工作台尝试持久化一条不可变 `archive_publish_intents` 记录，并绑定到任务所属的 `publication_id` 代次。它包含案件/尝试/来源标识、来源和草稿修订、报告指纹、Manifest/归档/输入标识、安全相对最终目录标识和公共 Manifest 快照。阶段单调推进：`intent_persisted` → `published` → `indexed` → `verified`，`conflict` 为终止安全状态。这是持久恢复记录，不是公共工作队列、调度器、进度记录或自动重试机制。

SQLite 持久意图/发布记录是权威发布事实。无路径 JSON Manifest 索引是派生投影：必须匹配持久发布标识、摘要和文件集，可从受信任持久证据重建；证据缺失或不一致时安全失败。公共任务/结果投影只暴露获准的不透明产物元数据，绝不暴露绑定发布的代次、所有者、栅栏或文件系统定位符。

意图的上下文绑定是持久工作台上下文哈希；其相对最终目录标识由正式运行时上下文和 Manifest ID 组成，因为 Legacy 执行器可能从工作台上下文创建独立的内存运行时上下文。创建意图时在同一数据库事务内重新读取服务端外壳、SourceRecord、CaseDraft 和有效工作台绑定；文件系统移动前再次执行相同绑定复验。受信任完成流程随后在自身写事务中重新读取 SourceRecord、CaseShell 和 CaseDraft，要求尝试、外壳和草稿各恰好更新一行；零行更新将回滚事务。正常执行和重启恢复调用同一受信任完成服务。

正式归档恢复会同时使用意图、内部 Manifest 索引和物理最终目录：

| 持久证据 | 恢复结果 |
|---|---|
| 无意图且无正式产物 | 将未完成尝试标为 `interrupted`；要求显式重新准备。 |
| 意图已持久化但最终目录不存在 | 安全中断未完成尝试；保留持久意图，不自动发布或恢复，并要求显式重新准备。 |
| 最终目录存在但意图仍为 `intent_persisted` | 校验全部绑定和 Manifest/RAR，然后只能依次推进到 `published` 和 `indexed`；绝不直接跳到 `indexed` 或重新发布。 |
| 最终目录存在且匹配持久意图，但索引不存在 | 校验 Manifest/RAR 并登记同一产物，然后完成同一尝试。 |
| 索引和最终目录均匹配意图 | 重新运行共享受信任完成校验并幂等完成同一尝试；`verified` 前崩溃只补齐阶段标记，绝不回滚成功。 |
| 最终目录缺失、文件被篡改/不完整、意图缺失或任何标识冲突 | 不标记成功、不覆盖、不删除、不重新发布；保留未知正式输出并要求新的显式尝试。确认的证据冲突可进入 `conflict`；临时数据库/索引/I/O 错误保留当前阶段以便后续显式验证。 |

只有经过验证的完成证据服务可以写入 `succeeded` 和 `archive_verified`；调用方提供的 Manifest ID 本身不是证据。

模式版本 10 增加内部 `archive_publish_fences` 表。栅栏将一个案件和尝试绑定到来源 ID/修订、草稿修订、报告指纹、单向上下文哈希和外壳修订。每个案件和每次尝试最多各有一个 `active` 栅栏。受控发布意图事务重新读取服务端事实后，同时创建栅栏和意图。有效栅栏会拒绝可能改变这些事实的普通写入。重启后，只有旧运行时状态和上下文绑定失效，有效栅栏才变为 `pending_verification`。待定证据不会永久阻止编辑：草稿/来源/外壳编辑会原子地将旧栅栏标为 `invalidated`，使其正式产物保持未知且无法完成或复用。成功的受信任完成流程消费栅栏；释放、失效和消费都是幂等内部转换。

每个非终止发布意图都会驱动核对，包括因发布侧基础设施错误而遗留为 `failed` 的尝试。流程先将过时运行时状态转为 `interrupted`，再校验意图、栅栏、Manifest 索引和物理 RAR。临时基础设施故障会保留已中断尝试、待定证据和正式文件而不重新发布；只有确认的标识、目标或完整性冲突才进入 `conflict`。

来源信任是归档安全门控，不是 Word 导出禁令。`available` 来源正常导出；基于服务端当前返回的来源状态进行显式客户端风险确认后，`pending` 和 `requires_reselection` 来源仍可查看、编辑、预览和导出。取消确认只取消本次导出操作。归档准备继续要求受信任且当前有效的来源修订。

对于工作台图片，后端资产注册表将不透明引用绑定到 `case_id`。二进制内容位于受控应用资产工作区；公共记录只包含资产 ID、种类、SHA-256 指纹和安全元数据。上传内容须先经过校验并原子完成，引用才能进入案件草稿。内容缺失或损坏属于可恢复错误；未引用临时资产会在宽限期后删除。

`SharedDefaults` 由后端持久化，并以当前本地操作员所在部署为范围；该范围不提供也不宣称多用户隔离。可编辑业务值仅限委托单位前缀、文号模板、检查地点、检查方法、硬件设备、数据摘要、检查要求、有序检查人员快照及 `md5 | sha1 | sha256` 哈希算法。为兼容持久部署，Legacy 附件一提取方法值仍可读取，但集中设置页不显示或提交，新案件初始化也不使用。旧的完整文号和盘号前缀继续作为 API 兼容持久值，但集中设置页不编辑它们。

算法默认为 MD5，并快照到之后每个新案件，绝不改写已有案件。当 Parser 值缺失、空白或等于固定系统摘要时，后续新案件还会快照非空共享数据摘要；真实 Parser 摘要保持权威。成功保存草稿时可发送稀疏补丁，只包含用户显式修改的非空值。案件字段优先级为：用户编辑 > 非空 Parser 报告值 > 非空共享默认值 > 系统默认值或空值。只有 Parser 值缺失、空白、仅含空格或为空数组时，后续案件才使用共享值；不改写已有案件，Parser 派生值也不创建共享默认值补丁。`localStorage` 不是工作台案件或共享默认值的事实源。`FieldSource` 区分 `report`、`user` 和 `system_default`，`FieldConfirmation` 单独表示待人工确认。`ClientIdentity` 是本地会话标识，不是已认证人员。`EditLease` 提供一份带到期和接管元数据的有效案件租约。

`SaveStatus`、`SharedDefaultsSaveStatus` 和 `DualSaveResult` 分别报告草稿与共享默认值的持久化结果。共享默认值写入使用受支持字段补丁；显式集中设置请求可以清空值，而 legacy 稀疏草稿补丁保留非空语义。`updated`、`unchanged`、`failed` 和 `revision_conflict` 是不同状态；`RevisionConflictDto` 描述乐观并发失败。`WorkbenchApiEnvelope`、`CaseShellResponse`、`CaseDraftResponse`、`SourceRecordResponse`、`SharedDefaultsResponse` 和 `TaskRecordResponse` 是带版本的 API DTO 信封，均不含绝对路径。

`CaseListPage` 携带带 offset/limit 元数据的不透明案件外壳卡片；`CaseDetail` 组合外壳、可选草稿、来源摘要和解析任务；`CaseSubmission` 是授权报告目录被接受并持久化后的即时响应。`ArchiveDecision` 为 `immediate` 或 `deferred`；`ArchiveDecisionResult` 报告持久生命周期，并在立即决定时返回新排队归档任务的安全公共摘要，但不暴露内部 Legacy 上下文或归档尝试绑定。延期决定刷新后仍以 `archive_deferred` 可见。`DeletePreflight` 是向后兼容的只读确认预览：案件存在时返回无阻塞项的 `allowed: true`，但不删除记录或产物。`CaseListResponse`、`CaseDetailResponse` 和 `CaseSubmissionResponse` 是对应的带版本信封。`CaseSubmission` 还暴露服务端当前读取的共享默认值，使新案件在解析前显示预填内容；部署实例仍是权威来源。

`DirectorySelectionCancelled` 是取消原生文件夹对话框时返回的无路径 `{ cancelled: true }` 结果。`CaseDirectorySubmissionResult` 是该取消结果与 `CaseSubmission` 的联合类型，`CaseDirectorySubmissionResponse` 是其带版本信封；这些类型均不暴露选定绝对路径。`CaseDeletionResult` 是确认删除案件后的最小成功响应，只包含不透明案件 ID 和 `deleted: true`。对应服务端操作删除案件工作台记录及平台所有的归档、Word 和图片文件；用户提供的来源目录不属于删除边界。

`DemoReadiness` 是只读 Demo 能力快照，包含后端服务、WinRAR 和归档输出三项固定 `DemoReadinessItem`。首页来源授权开关是独立持久化的前端偏好，不是就绪项。`DemoReadinessKey` 固定这些标识，`DemoReadinessState` 仅限 `ready`、`not_configured`、`unavailable` 和 `unknown`。各项只暴露安全标签、稳定错误码和固定指引；绝不包含配置根目录、绝对路径、可执行文件详情、进程数据、环境值或异常文本。

### 第三阶段归档任务共享合同

T011 只增加共享类型和纯规则；尚未接入数据库、Worker、案件列表 API 或卡片 UI。`TaskRecord` 保留既有 `percent`、`finished_at`、`error_summary`、状态和取消字段。归档记录还可携带 `ArchiveProgressKind=workflow_milestone`、安全阶段元数据、`updated_at`、心跳/输出活动、`ArchiveWorkerState` 和以后端为权威的 `ArchiveTaskAction` 值。旧任务记录可以省略这些可选字段。

`ArchiveWorkflowStage` 和 `ArchiveWorkflowMilestonePercent` 定义固定的 `0/10/20/30/75/85/90/95/100` 工作流里程碑。WinRAR 运行时保持在 30；输出字节数和分卷数只是活动证据，绝不代表压缩比例。`ProgressSnapshot` 是完整共享里程碑/活动快照。`ArchiveTaskCardSummary` 是显式安全投影，不得携带 Worker ID、租约、本地路径、堆栈、原始日志或内部诊断。

`VolumeSlot` 包含稳定标识、计划修订、谱系、序号、计划字节数、状态和可选 `DiscMapping`；`PlannedVolumeSlot` 是重新规划输入。`ArchivePlanSnapshot` 保存带版本的槽位计划。`ReconciledVolumeSlots` 区分有效与已移除槽位，`VerifiedVolumeSlot` 是有界 Manifest 收敛输入。`LegacyArchiveCompatibilityStatus`、`ResourceAdmissionStatus`、`ArchiveResourceAdmission`、`ArchiveTaskCommandRequest` 和 `ArchiveTaskCommandResult` 作为共享合同引入；T013–T015 现已通过单一归档任务生命周期持久化并暴露它们。

T015 在同一持久记录之上增加无路径公共任务投影。`ArchiveTaskPublicDetail` 在卡片摘要基础上增加任务修订、尝试序号、取消标记、安全错误码和当前有界归档计划快照。`ArchiveTaskHistory` 按案件历史顺序返回这些公共详情，不替换先前尝试。只有任务及其绑定尝试均成功，且持久 Manifest 与物理分卷通过复验后，`ArchiveTaskResult` 才可用；它暴露已验证槽位元数据、已发布资产元数据和无路径分卷下载标识，但绝不暴露定位符、进程所有权、命令、日志或原始诊断。

### 第四阶段已批准模板共享合同

T016 引入无路径共享合同。`TemplateVersionRef` 在 `CaseDraft` 中只保存 `TemplateId` 和语义版本。对应 `TemplateVersion` 将该引用绑定到不透明资产 ID、指纹、带版本的校验规则引用和 `TemplateApprovalRecord`；绝不包含模板路径或 DOCX 内容。

`TemplateValidationResult` 区分已验证版本与稳定的未知、未批准、资产缺失、指纹不匹配和规则校验失败。`WordArtifactValidity` 记录 Word 产物是否仍有效或因模板变化失效。`TemplateSelectionImpact` 固定第四阶段边界：模板变化使 Word 失效，但不改变归档规划、归档任务创建、已验证 Manifest 和盘号映射。

`TemplateManagementRecord` 是 `TemplateVersion` 的无路径管理页投影，增加 `is_default`、`can_delete`、`can_customize` 和当前从 DOCX 读取的白名单 `TemplateCustomization`。对应 `TemplateManagementResponse` 返回可用记录、可空 `default_template_ref` 及默认模板更新所用的单调 `defaults_revision`。

`RenameTemplateRequest` 只携带去除首尾空格的 `display_name`。重命名更新已批准模板的展示元数据，同时保留其 ID、版本、资产、指纹、校验规则、批准历史、默认状态和案件引用。

受控前端定制合同使用 `TemplateBodyFont` 和 `TemplateBodyFontSize` 白名单。`TemplateCustomization` 只包含固定文档标题、正文字体和字号。`DeriveTemplateRequest` 标识已批准来源版本和新的不可变目标版本；绝不携带文件系统路径、DOCX 字节、任意 OOXML 或布局规则。

T017 增加前端注册表客户端和审核页选择器。客户端筛选完整已批准版本，只显示模板 ID、版本和安全验收摘要，并且只提交 `TemplateVersionRef`、草稿修订和编辑租约证明。仅当返回的影响保留归档、Manifest 和盘号映射事实时才接受选择结果。

T018 增加持久后端注册表、不可变批准历史和案件模板引用更新。已登记版本将受控内部资产定位符绑定到不可变 ID、版本、包指纹和校验规则；公共投影保持无路径。列表和正式生成都要求当前批准状态，并在使用前复验资产指纹和 Word 结构。切换案件引用只使 Word 产物失效，不改变归档规划、任务、Manifest 或盘号映射。没有引用的已有案件继续使用 `current-template-v1`。

T019 在既有工作台 API 下暴露已批准且通过复验的注册表和案件选择操作。选择沿用既有编辑租约和草稿修订合同，只持久化模板 ID/版本。正式 Word 生成只发送不透明案件标识和修订；后端解析持久引用，并通过 T018 注册表复验当前批准、指纹、规则和结构，然后才运行既有 Legacy 生成器。

### 第 5A 阶段保留策略共享合同与 v11 基础

切片 5A-1 只增加公共保留策略合同基础和 SQLite 持久化基础。这些类型和表不代表清理执行、Coordinator 调度、发布复验、正式 Word 文件持久化、已清理案件下载路由、API/UI 接线、E2E 或人工验收已经实现。

#### 保留策略公共类型

下列公共类型从 `packages/shared/types/retention.ts` 导出，并由共享导出索引重新导出。它们是安全合同：携带不透明案件/发布/产物标识、状态、有界摘要、修订/摘要事实和时间戳，但绝不携带绝对路径、数据库表名、所有者/认领令牌、租约、栅栏、内部尝试/上下文标识或客户端控制的删除文件列表。

`RetentionPolicyMode` 取 `disabled | preview_only | enforce`。`RetentionEligibility` 取 `eligible | ineligible | unknown`。`RetentionStatus` 取 `unknown | not_expired | eligible | blocked | planned | processing | completed | failed`。`CleanupRunPhase` 取 `planned | claimed | preflighted | work_files_cleaned | records_cleaned | verified | succeeded | blocked | stale | cancel_requested | cancelled | interrupted | partial_failure | failed_retryable | failed_terminal`。`CleanupRunStatus` 取 `active | succeeded | cancelled | failed | blocked`。

`RetentionBlockerCode` 是下列稳定联合类型：
`RETENTION_CASE_MUTATION_TIME_MISSING`, `RETENTION_PUBLICATION_MISSING`,
`RETENTION_PUBLICATION_UNVERIFIED`, `RETENTION_PUBLICATION_TIME_MISSING`,
`RETENTION_WORD_ARTIFACT_MISSING`, `RETENTION_WORD_ARTIFACT_UNVERIFIED`,
`RETENTION_TIME_INVALID`, `RETENTION_TIME_IN_FUTURE`,
`RETENTION_NOT_EXPIRED`, `RETENTION_ACTIVE_TASK`, `RETENTION_ACTIVE_LEASE`,
`RETENTION_RECOVERY_IN_PROGRESS`, `RETENTION_OWNERSHIP_UNKNOWN`,
`RETENTION_AUTHORITY_INCONSISTENT`, `RETENTION_SNAPSHOT_ACTIVE`,
`RETENTION_SNAPSHOT_RECOVERY_REFERENCED` 和
`RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN`。

`CleanupErrorCode` 是下列稳定联合类型：
`CLEANUP_PATH_OUTSIDE_ALLOWED_ROOT`, `CLEANUP_OWNERSHIP_UNKNOWN`,
`CLEANUP_SYMLINK_OR_JUNCTION_REJECTED`, `CLEANUP_FILE_IN_USE`,
`CLEANUP_ACCESS_DENIED`, `CLEANUP_FILE_CHANGED`,
`CLEANUP_FILE_DELETE_FAILED`, `CLEANUP_SNAPSHOT_DELETE_FAILED`,
`CLEANUP_STALE_REQUEST` 和 `CLEANUP_CONFLICT`。

`RetentionPolicyDto` 包含 `mode`、`retention_days`、`scan_interval_seconds`、`batch_size`、`policy_revision`、可空 `activated_at` 和 `updated_at`。

`RetentionStatusDto` 包含 `case_id`、`status`、`eligibility`、可空 `retention_anchor_utc`、可空 `expires_at_utc`、可空 `blocker_code`、`policy_revision`、`case_revision` 和 `updated_at`。

`CleanupPreviewItemDto` 包含 `case_id`、`eligibility`、可空 `blocker_code`、`planned_data_categories` 中的公共类别名、`preserved_formal_artifact_categories` 中的公共类别名、可空锚点与到期时间，以及 `has_running_task`、`has_edit_lease`、`has_recovery` 和 `has_conflict` 布尔摘要。`CleanupPreviewDto` 包含一个 `RetentionPolicyDto`、`items` 数组和 `generated_at`。仅限后端的 `CaseRetentionPreviewService` 现根据当前部署的持久案件外壳和共享 `CaseRetentionService` 资格谓词构建该投影。它按案件 ID 升序排列，返回 `candidate`、`skipped` 或 `blocked` 状态，以及稳定阻塞原因、计划/保留类别、锚点/到期时间、策略/案件修订和任务/租约/恢复布尔摘要。每项和完整结果都携带规范 SHA-256 摘要。该服务无路径，不创建清理运行，也不删除或改变案件记录；公共路由/API/UI 接线和 Coordinator 执行属于后续能力。

`CleanupRunStatusDto` 包含不透明 `run_id`、`case_id`、`phase`、`status`、可空 `result_code`、可空 `error_code`、`updated_at` 和可空 `completed_at`。内部认领、租约和栅栏字段不属于该投影。

`FormalWordArtifactSafeProjection` 包含 `word_artifact_id`、`case_id`、
`publication_id`, `file_digest`, `file_size`, `source_manifest_digest`,
`template_identity`、`template_version`、`generated_at`、可空
`verified_at` 和 `status`（`pending | verified | invalid`）。该公共投影特意省略内部相对路径。

仅限后端的 `RetentionPolicyConfig` 解析结果不是 SharedTypes 公共模型，特意不列入公共导出列表。其部署输入为 `BIJI_CASE_RETENTION_MODE`、
`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和
`BIJI_CASE_RETENTION_BATCH_SIZE`，默认值依次为 `disabled`、30、86400 和 20；legacy 天数键只是迁移兼容输入，不能启用保留策略工作。

#### v11 持久化基础

SQLite 持久化模式现为 `WORKBENCH_DATABASE_SCHEMA_VERSION = 11`；既有 API 信封版本仍为 v1。v10→v11 迁移在事务内执行，保持 `foreign_keys=ON`，校验 `foreign_key_check`，保留既有来源/尝试/快照标识，并拒绝不受支持的未来版本。迁移不删除记录或文件、不回填历史发布验证时间、不创建清理运行，也不启用 `enforce`。新安装和升级均以 `disabled` 模式初始化持久策略。

v11 基础包含下列新表：

| 表 | 已实现的持久字段和约束 |
|---|---|
| `case_retention_policies` | 部署主标识、`mode`、`retention_days`（1–3650）、`scan_interval_seconds`（至少 3600）、`batch_size`（1–1000）、`policy_revision`、可空 `activated_at`、`created_at` 和 `updated_at`；部署标识唯一。 |
| `case_retention_records` | `retention_record_id`、部署/案件标识、`eligibility`、`status`、可空 `last_meaningful_mutation_at`、`latest_verified_formal_publication_at`、`latest_successful_word_export_at`、`retention_anchor_utc`、`expires_at_utc`、`last_blocker_code`、策略/案件/清理修订和时间戳；`(deployment_instance_id, case_id)` 唯一。 |
| `case_cleanup_runs` | 运行/案件/部署标识、策略和案件修订、所有者/认领/租约/栅栏字段、当前阶段、重试/文件/结果/错误字段和时间戳；部分唯一索引确保每个部署/案件最多一个有效运行，并提供恢复、租约和部署扫描索引。这些内部认领字段不是公共 DTO 字段。 |
| `formal_word_artifacts` | Word 产物/部署/案件/发布标识、受控内部相对路径、摘要、大小、来源 Manifest 摘要、模板标识/版本、生成/验证时间戳和状态；包含 Word 标识及案件/发布查询索引。本切片创建持久行基础，但不持久化真实 Word 文件。 |

清理运行 Repository 基础现持久化计划运行，并针对计划的策略/案件修订执行部署范围认领 CAS。成功认领会分配所有者、不透明认领令牌、租约到期时间和单调栅栏纪元；有效认领会冲突，已到期且有所有者的认领可用新栅栏接管。归属方的阶段/结果/重试/租约更新继续受 CAS 保护，恢复列表持久且重启安全。下述已清理案件记录边界也仅限内部：只能从部署范围内有效的 `work_files_cleaned` 认领进入，而公共运行投影排除所有者、令牌、租约和栅栏字段。候选调度、物理文件删除、来源/快照清理及公共执行/API 边界属于后续能力。

正式 Word 产物 Repository 只持久化产物元数据，不保存完整 `report_json`。它校验小写 SHA-256 文件/Manifest 摘要、非负且 JavaScript 安全的文件大小、受控相对路径、UTC-Z 时间戳，以及 `status` 与 `verified_at` 的一致性。创建和读取要求存在绑定到同一部署和案件的当前发布行；读取已验证产物时还会复验既有发布的已验证阶段/状态及非空 `publication_verified_at`。安全投影省略内部相对路径。这只是持久元数据基础；物理 Word 生成、文件内容验证和已清理案件下载属于后续能力。

已清理案件墓碑 Repository 只有在重新核对已认领清理运行、当前策略修订、案件修订、持久保留锚点、已验证发布集、已验证正式 Word 产物，并确认没有有效任务、编辑租约或发布恢复后，才执行记录边界。在同一 SQLite 事务内，它消费无路径文件步骤收据，其快照和临时资产 ID 必须精确匹配已标为 `cleaned` 的持久行；随后删除快照行、压缩正式尝试/任务载荷，删除无效工作上下文、孤立尝试/任务、自有临时资产、计划、草稿和工作资产引用，并删除未引用来源行。仍被正式尝试/意图/栅栏引用的来源变为最小墓碑，使既有发布权威保留来源外键。保留正式意图/栅栏/尝试、发布、Word 和已发布资产事实；外围事务提交前必须执行 `PRAGMA foreign_key_check`。随后外壳保留部署/案件标识和安全摘要，清除案件编号/来源/任务工作引用，标记 `record_cleaned`，增加墓碑/清理/案件修订，将清理运行推进到 `records_cleaned`，并把匹配保留记录更新为 `completed`。已清理外壳仍可查询，但草稿保存/生命周期转换以 `CASE_RECORD_CLEANED` 拒绝；正式 Word/发布行保持不变，仍可按持久标识读取。物理路径验证、文件删除和公共产物列表/下载属于后续能力。

3.1 保留策略服务现根据这些持久事实评估单个案件。它使用保留记录的有效变更时间、每个当前发布意图的最大验证时间及正式 Word 产物行的最大验证时间；不得以外壳 `updated_at`、文件 mtime、下载时间或派生 Manifest 索引时间替代。所得锚点和连续 24 小时到期时间通过部署/案件保留投影 upsert 持久化，并携带 `Z` 时间戳和当前持久策略/案件修订。

`publication_verified_at` 为空的历史发布意图保持未验证，直到受控内部复验器证明精确持久发布标识、文件清单、RAR/Manifest/MD5 检查、栅栏、所有权、部署和案件绑定。只有此后，既有仅限 NULL 的发布 CAS 才写入所提供的受信任 UTC 验证时间。缺少复验或复验失败时字段保持为空；不推断时间戳，也不创建新发布标识。同一服务对格式错误或未来时间戳、不完整发布/Word 权威、有效任务或编辑租约、发布/恢复/快照/上下文冲突、有效清理运行及非终止案件状态安全失败。只有持久策略模式为 `enforce` 时才返回内部 `enforce_allowed` 门控；本切片不增加调度器、预览路由或公共清理执行 API。Word 验证器边界要求持久产物摘要、大小、Manifest 摘要和所有权匹配；物理文件解析留给后续清理/访问工作。

#### v11 备份、恢复与应用回滚边界

第五阶段定义受控运维备份/恢复边界，但不增加公共备份或撤销删除 API。可恢复代次是经过静默和交叉核对的集合，包含 v11 SQLite 数据库、正式 RAR/Manifest/MD5 发布文件及持久权威、正式 Word 行/文件、已批准模板标识/版本和文件、自有工作资产、保留策略及审计事实。代次记录部署/模式标识、UTC-Z 时间、相对定位符、大小和摘要；恢复前必须执行 SQLite 完整性/外键/模式校验及发布/Word 权威检查。

恢复首先在策略为 `disabled` 的隔离合成部署中执行；正式文件按持久 `publication_id` 和 `word_artifact_id` 读取，派生 Manifest 索引只根据 SQLite 发布事实重建。分组缺失或不匹配、所有权不确定、外键错误或可能覆盖正式文件/来源时安全失败。Git/应用回滚不是数据回滚：v10 应用必须拒绝 v11 数据库；迁移后的应用回滚要求匹配的 v10 或 v11 分组备份，而不是反向 SQL 或人工删除。受控演练清单维护于
`[harness/retention-backup-recovery.md](../../harness/retention-backup-recovery.md)`.

现有 v11 基础字段如下：

- `case_shells`: `deployment_instance_id`, `record_cleaned`,
  `tombstone_revision`、`retention_state`、`cleanup_state`、可空
  `cleaned_at`, `last_meaningful_mutation_at`, `retention_anchor_utc`,
  `safe_display_summary` 和 `cleanup_revision`；清理压缩会清除
  `case_number`、`source_id`、`parse_task_id` 和 `report_available`，同时保留安全标题/摘要和持久正式行。
- `source_records`：`deployment_instance_id`、`tombstone_state`、可空 `tombstoned_at` 和 `tombstone_revision`。清理删除没有正式引用的行，并将被正式引用的行压缩为最小墓碑，同时保留发布外键所需来源标识。
- `task_records`：`deployment_instance_id`、可空 `publication_id`、可空 `word_artifact_id` 和可空 `formal_verified_at`。
- `archive_publish_intents`：可空 `publication_verified_at`，它仍属于既有持久发布事实，而不是第二个发布权威。

新的关键索引包括 `source_deployment_state`、
`archive_publication_verified`, `case_retention_case`,
`cleanup_run_active_case`, `cleanup_run_recoverable`, `cleanup_run_lease`,
`cleanup_run_deployment_scan`、`formal_word_case` 和
`formal_word_publication`。任何新表都不使用 `CURRENT_TIMESTAMP`、`datetime('now')` 或其他 SQLite 本地时间表达式。

#### 第五阶段持久时间合同

第五阶段新增持久时间戳以带时区的 UTC ISO 8601 写入，并使用规范 `Z` 后缀。带其他偏移的感知时间戳在写入前转换为 UTC；拒绝无时区时间戳。这适用于新策略、保留记录、清理运行、Word 产物和 `publication_verified_at` 写入。既有 v10 时间戳仍可读取，不会仅为改变文本偏移而重写。API 时间戳字段保留时区信息；`Asia/Shanghai` 只用于显示，绝不改变 UTC 比较、保留计算或 CAS 事实。

#### 尚未成为现行能力

有效的第五阶段 delta 仍定义当前基础和 3.1/3.2 服务尚未交付的未来行为：公共预览路由/API/UI 接线、Coordinator 与 enforce 执行、工作记录/文件清理、物理发布/Word 文件复验集成、正式 Word 文件生成与下载、已清理案件路由、API/UI 行为、Windows 删除、E2E 和人工验收。在实现与验证任务完成前，这些行为继续保留在活跃变更中。

类型索引：type WorkbenchSchemaVersion、type WorkbenchApiVersion、type CaseLifecycle、
type TaskKind, type TaskStatus, type TaskStage, type ArchiveProgressKind,
type ArchiveWorkerState, type ArchiveTaskAction, type ArchiveWorkflowStage,
type ArchiveWorkflowMilestonePercent, type VolumeSlotStatus, type DiscMappingSource,
type DiscMappingConfirmation, type FieldSource, type FieldConfirmation,
type LeaseStatus, type SourceAccessStatus, type CaseAssetContentStatus, interface OpaqueAssetRef, interface CaseAssetRecord,
interface CaseAssetList, interface CasePhotoBindingRequest, interface CasePhotoBindingResult,
interface FieldState,
interface WordDownloadName, interface WordDirectoryExportResult, interface WordExportWarning,
interface WordDirectoryExportTarget,
interface DocumentNumberTemplate, interface CaseShell, interface CaseDraft,
interface SharedDefaults, interface ClientIdentity,
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
interface CaseDetail, interface CaseSubmission, interface DirectorySelectionCancelled,
type CaseDirectorySubmissionResult, type ArchiveDecision,
type ArchiveDecisionStatus, interface ArchiveDecisionResult, interface DeletePreflight,
interface CaseDeletionResult,
interface ArchiveAttemptRecord, type ArchiveAttemptStatus, type ArchiveCleanupStatus,
interface CaseListResponse, interface CaseDetailResponse, interface CaseSubmissionResponse,
interface CaseDirectorySubmissionResponse,
type DemoReadinessState, type DemoReadinessKey, interface DemoReadinessItem,
interface DemoReadiness,
type TemplateId, type TemplateApprovalStatus, type TemplateErrorCode,
type WordArtifactValidity, interface TemplateVersionRef,
interface TemplateApprovalRecord, interface TemplateValidationRuleRef,
interface TemplateVersion, interface TemplateManagementRecord,
interface TemplateManagementResponse, interface TemplateValidationSuccess,
interface TemplateValidationFailure, type TemplateValidationResult,
interface TemplateSelectionImpact,
type TemplateBodyFont, type TemplateBodyFontSize,
interface TemplateCustomization, interface DeriveTemplateRequest,
interface RenameTemplateRequest,
type RetentionPolicyMode, type RetentionEligibility, type RetentionStatus,
type CleanupRunPhase, type CleanupRunStatus, type RetentionBlockerCode,
type CleanupErrorCode, interface RetentionPolicyDto,
interface RetentionStatusDto, interface CleanupPreviewItemDto,
interface CleanupPreviewDto, interface CleanupRunStatusDto,
interface FormalWordArtifactSafeProjection,
interface ArchiveStorageSettings.

`ArchiveStorageSettings` 是部署本机的归档目录设置投影，包含当前生效目录、待生效目录、默认目录、自定义/有效状态、是否需要重启及稳定错误码。它不保存案件内容，也不把本机绝对路径写入案件数据库或归档 Manifest。
