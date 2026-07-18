# 数据模型 Spec

> 本文档定义项目的数据模型，是类型定义的唯一真相源。
> 新增 type/interface 后 MUST 同步更新本文档。
> 一致性由 npx tsx scripts/check-docs.ts 自动检查。

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
| rar_filename | string | RAR文件名 |
| md5_hash | string | MD5哈希值 |
| file_size | string | 文件大小字符串；目录压缩时为字节数文本，压缩包直传时为带“字节”后缀的文本，具体展示由生成路径处理 |

### 表格数据（TableData）

| 字段 | 类型 | 说明 |
|------|------|------|
| columns | `{ key: string; title: string; width?: string }[]` | 列定义；附件1 默认五列：序号、电子数据、来源、提取方式、文件MD5哈希值 |
| rows | `Record<string, string>[]` | 行数据；目录解析启用压缩且生成归档文件时自动填充首行，未压缩或压缩包直传时当前实现不自动补附件1行，用户可编辑 |

### 检查笔录全文（InspectionReport）

顶层结构，包含 title、document_number、可选 case_number、introduction（9字段）、inspection（4字段）和 attachments（3个必需字段及可选 burning_date）。

### RAR/压缩包文件信息（RarInfo）

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名 |
| md5 | string | MD5 哈希值（32位十六进制） |
| size_bytes | number | 文件大小（字节） |
| size_display | string | 格式化后的文件大小（如 "11.77 MB"） |

目录解析和压缩包直传的来源不同：目录解析的 `rar_info` 从检查结果重建，当前 `size_bytes` 为 0、`size_display` 使用检查结果中的文件大小文本；压缩包直传返回原始上传文件的实际字节数和格式化大小。

### API 响应（ParseReportResponse）

| 字段 | 类型 | 说明 |
|------|------|------|
| report | InspectionReport | 解析生成的笔录全文 |
| parsed_files | string[] | 已解析的源文件列表 |
| rar_info | RarInfo \| null | RAR文件信息（MD5/大小），取消压缩时为 null |

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
`type PipelineRunStatus`、`interface ShadowDifference`、`interface ShadowComparisonResult`。

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

类型索引追加：`type MaterialClassificationStatus`、
`type MaterialClassificationSource`、`interface MaterialClassification`、
`interface InspectorLibraryRecord`。

### Additional migration support types

`PrimarySoftwareCandidate` stores an explicit report candidate pair. `DiscSequenceErrorCode` identifies first-disc parsing failures, and `DiscSequenceParseResult` stores the validation result, parsed sequence, and diagnostic code.

Type index: `type PrimarySoftwareCandidate`, `type DiscSequenceErrorCode`, `interface DiscSequenceParseResult`.
