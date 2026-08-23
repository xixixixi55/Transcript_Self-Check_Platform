# Spec Delta: 可选择哈希算法数据合同

> 基准 Spec: `openspec/specs/data-model.md`
> 变更类型：MODIFIED

## MODIFIED: SharedDefaults、InspectionReport 与 ArchiveManifest

### Requirement: 受控业务哈希算法合同

系统 MUST 使用受控枚举表达业务哈希算法，并兼容现有 MD5 数据。

#### Scenario: 共享默认值和案件快照

- **WHEN** 系统创建或读取共享默认值
- **THEN** `SharedDefaults.hash_algorithm` 取 `md5`、`sha1` 或 `sha256`，缺失时为 `md5`
- **AND** 新案件把该值复制到 `InspectionReport.inspection.result.hash_algorithm`
- **AND** 案件字段缺失时兼容解释为 `md5`

#### Scenario: 分卷同时携带两类摘要

- **WHEN** 系统构建新的 `ArchiveManifest`
- **THEN** `ArchivePart.md5` 继续表示内部完整性 MD5
- **AND** `ArchivePart.hash_algorithm` 表示案件业务算法
- **AND** `ArchivePart.hash_value` 表示该算法的完整十六进制摘要
- **AND** 旧分卷缺少新增字段时以 `md5` 和 `ArchivePart.md5` 兼容投影

#### Scenario: legacy 字段兼容

- **WHEN** 现有模板或兼容 DTO 仍读取 `md5_hash`
- **THEN** 该字段键保留
- **AND** 新案件可在该键中承载所选业务摘要
- **AND** 用户可见标签必须来自 `hash_algorithm`，不得依据 legacy 键名固定显示 MD5
