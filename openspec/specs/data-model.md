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
| model | string | 具体型号 |
| imei1 | string | IMEI1 |
| imei2 | string | IMEI2 |
| serial_number | string | 序列号 |
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
| file_size | string | 文件大小 |

### 表格数据（TableData）

| 字段 | 类型 | 说明 |
|------|------|------|
| columns | ColumnDef[] | 列定义 |
| rows | RowData[] | 行数据 |

### 检查笔录全文（InspectionReport）

顶层结构，包含 title + document_number + introduction(9字段) + inspection(4字段) + attachments(3字段)。

### RAR/压缩包文件信息（RarInfo）

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名 |
| md5 | string | MD5 哈希值（32位十六进制） |
| size_bytes | number | 文件大小（字节） |
| size_display | string | 格式化后的文件大小（如 "11.77 MB"） |

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
