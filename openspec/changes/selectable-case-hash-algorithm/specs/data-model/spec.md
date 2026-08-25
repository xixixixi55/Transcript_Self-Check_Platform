# Spec Delta: 可选择哈希算法数据合同

> 基准 Spec: `openspec/specs/data-model.md`
> 变更类型：MODIFIED

## MODIFIED Requirements

### Requirement: 受控案件文件哈希算法合同

系统 MUST 使用受控枚举表达案件文件哈希算法，使 MD5、SHA-1、SHA-256 经过同一数据链路，并兼容现有 MD5 数据。

#### Scenario: 共享默认值和案件快照

- **WHEN** 系统创建或读取共享默认值
- **THEN** `SharedDefaults.hash_algorithm` 取 `md5`、`sha1` 或 `sha256`，缺失时为 `md5`
- **AND** 新案件把该值复制到 `InspectionReport.inspection.result.hash_algorithm`
- **AND** 案件字段缺失时兼容解释为 `md5`

#### Scenario: 新分卷只携带案件所选哈希

- **WHEN** 系统构建新的 `ArchiveManifest`
- **THEN** `ArchivePart.hash_algorithm` 必须等于案件快照中的 `md5`、`sha1` 或 `sha256`
- **AND** `ArchivePart.hash_value` 必须是所选算法的完整十六进制摘要
- **AND** 新分卷不得为了内部完整性额外计算或要求固定 `ArchivePart.md5`
- **AND** MD5、SHA-1、SHA-256 除算法参数、摘要长度和显示元数据外使用相同结构与校验流程

#### Scenario: 拒绝不完整或混用算法的新 Manifest

- **WHEN** 新 Manifest 的任一 part 缺少 `hash_algorithm/hash_value`、摘要长度与算法不符，或不同 part 使用不同算法
- **THEN** 系统拒绝登记、恢复、复用、下载和正式导出该 Manifest
- **AND** 不得回退到固定 MD5 绕过无效的新字段

#### Scenario: 兼容旧 MD5 Manifest

- **WHEN** 系统读取缺少 `hash_algorithm/hash_value` 但含合法 `ArchivePart.md5` 的旧分卷
- **THEN** 规范化读取层将其解释为 `hash_algorithm=md5` 且 `hash_value=ArchivePart.md5`
- **AND** 不批量改写存量 Manifest
- **AND** 后续复用、恢复、下载和导出进入与新 MD5 Manifest 相同的规范链路

#### Scenario: 拒绝无法兼容的旧 Manifest

- **WHEN** 旧分卷既没有完整新字段，也没有合法的 32 位 `md5`
- **THEN** 系统拒绝把该分卷视为已验证归档产物

#### Scenario: legacy 字段兼容

- **WHEN** 现有模板或兼容 DTO 仍读取 `md5_hash`
- **THEN** 该字段键保留
- **AND** 新案件可在该键中承载所选文件摘要
- **AND** 用户可见标签必须来自 `hash_algorithm`，不得依据 legacy 键名固定显示 MD5
