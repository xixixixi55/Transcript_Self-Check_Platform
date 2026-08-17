## MODIFIED Requirements

### Requirement: Archive planning and WinRAR execution are separate

系统 MUST 先生成可审计的 `ArchivePlan`，再由独立执行器调用 WinRAR。4GB、22GB、45GB 档 MUST 统一按 `1GB = 1024³` 字节计算，最大卷数分别为2、2、5，不得新增75GB档。输入不超过225GB时 MUST 使用 `standard_volume` 标准分卷模式；输入超过225GB时 MUST 使用 `oversized_single` 超大单卷模式，生成且只生成一个 `案件名.rar`，225GB不得作为系统禁止压缩的总上限。

`ArchivePlan` 和 `ArchiveManifest` MUST 显式记录归档模式。标准分卷适用的 `volume_size_bytes`、`volume_tier_gb` 和 `disc_capacity_bytes` 在超大单卷模式中 MUST 明确表示不适用，不得用0、45GB或任意超大容量哨兵代替模式。两种模式均 MUST 保留实际文件名、实际大小、MD5、part顺序、盘号、刻录日期、完整性和文件安全证据。

#### Scenario: 二进制标准档位边界

- WHEN 输入总大小不超过8GB、超过8GB且不超过44GB、超过44GB且不超过225GB（均按 `1024³` 字节换算）
- THEN 规划模式为 `standard_volume`
- AND 分别选择4GB、22GB、45GB档
- AND 三档最大卷数分别为2、2、5

#### Scenario: 超过225GB切换超大单卷

- WHEN 输入总大小超过 `225 × 1024³` 字节
- THEN `ArchivePlan` 状态为 `planned` 且模式为 `oversized_single`
- AND WinRAR命令不包含 `-v` 参数
- AND 预期产物为单个 `案件名.rar`
- AND 系统不返回 `ARCHIVE_TOO_LARGE` 或 `ARCHIVE_INPUT_LIMIT`

#### Scenario: 标准分卷保持严格校验

- WHEN `standard_volume` 模式的WinRAR执行完成
- THEN 系统对单卷校验 `案件名.rar`，对多卷校验 `.partN.rar` 命名和卷号连续性，并校验每卷档位上限、最大卷数、文件安全、非空、完整性和MD5
- AND 任一条件不满足时不得发布Manifest或进入正式导出

#### Scenario: 超大单卷按模式校验

- WHEN `oversized_single` 模式的WinRAR执行完成
- THEN 系统只接受一个安全、非空且文件名精确为 `案件名.rar` 的RAR
- AND 系统校验实际大小、完整性和MD5
- AND 即使实际RAR大于45GB，也不得因标准分卷或标准光盘容量上限而拒绝
- BUT 出现 `.partN.rar`、多个RAR、空文件或文件名不匹配时必须拒绝发布

#### Scenario: 资源安全门控继续生效

- WHEN 超过225GB的输入进入归档准入
- THEN 系统不得仅因输入总大小超过135GB或225GB拒绝
- AND 磁盘空间、CPU/IO、WinRAR并发、路径和输入安全门控仍按现有规则执行

#### Scenario: 旧Manifest与标准分卷兼容

- WHEN 系统读取本变更前生成的、没有显式归档模式的合法Manifest
- THEN 系统按 `standard_volume` 兼容解释并执行原有严格校验
- AND 不得把旧Manifest误判为超大单卷或放宽其每卷容量规则
