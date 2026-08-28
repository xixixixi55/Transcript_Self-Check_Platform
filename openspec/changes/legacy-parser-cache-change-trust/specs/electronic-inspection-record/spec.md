## MODIFIED Requirements

### Requirement: REQ-011：解析缓存

系统 SHALL 使用不透明键在 `output/parsed/` 中缓存完整 Legacy 解析结果（`InspectionReport` 加兼容 `rar_info`）。缓存记录 SHALL 包含来源内容指纹、`cache_version`、`input_trust_schema` 和 `last_accessed_at`，且 MUST NOT 包含用于前端展示的绝对路径。既有 Parser 语义 `cache_version` 保持为 `7`；独立 `input_trust_schema` 标识是否已应用来源变化信任合同。使用确定性 LRU 淘汰时，最多 SHALL 保留五条有效解析缓存记录。解析缓存清理 MUST 与归档输出清理保持分离。

#### Scenario: 首次解析创建带版本缓存记录

- **WHEN** 成功解析报告目录
- **THEN** 系统将完整 Legacy 解析结果保存为不透明 JSON 缓存记录
- **AND** 记录包含来源指纹、`cache_version`、`input_trust_schema` 和 `last_accessed_at`
- **AND** 记录不含用于前端展示的绝对来源路径
- **AND** 解析不执行 WinRAR，也不创建最终 `ArchiveManifest`

#### Scenario: 未变化报告复用受信任缓存

- **WHEN** 使用相同 Parser 缓存版本再次解析同一规范化报告目录
- **AND** 选定依赖成员关系未变化
- **AND** 每个依赖都经统一文件变化合同确认为 `trusted_unchanged`
- **THEN** 系统返回缓存的 Legacy `InspectionReport`，不重新读取全部依赖内容或再次运行解析
- **AND** 更新 `last_accessed_at`，不创建重复缓存记录
- **AND** 不执行或复用 WinRAR 结果

#### Scenario: 报告变化使缓存失效

- **WHEN** 依赖在原位置被覆盖、原子替换、删除后重建、新增、删除，或其内容/标识以其他方式变化
- **THEN** 缓存 MUST 失效或经过完整复验
- **AND** 新输入可读时，系统 MUST 重新构建 `InspectionReport`
- **AND** MUST NOT 返回旧 `InspectionReport`

#### Scenario: 不受信任来源不会产生错误缓存命中

- **WHEN** 来源不是 NTFS、由网络/移动/云支撑、受权限限制、Journal 被重建或无法验证、API 失败，或验证无法证明内容未变化
- **THEN** 系统在复用缓存记录前 MUST 完整读取必需依赖并计算摘要
- **AND** 读取失败或读取期间发生变化时，MUST 使解析失败，而不是返回旧缓存

#### Scenario: 安全升级旧缓存记录

- **WHEN** 有效旧缓存记录缺少 `input_trust_schema` 或使用更旧的输入信任模式
- **THEN** 系统在复用前 MUST 执行完整内容验证
- **AND** 验证成功后 MAY 使用当前输入信任模式重写记录
- **AND** 损坏、不完整或无效记录 MUST 视为缓存未命中

#### Scenario: LRU 淘汰保持隔离

- **WHEN** 创建第六条有效解析缓存
- **THEN** 删除具有最早确定性 `last_accessed_at` 的记录
- **AND** 淘汰 MUST 只删除 `output/parsed/` 下的解析缓存记录
- **AND** 淘汰 MUST NOT 删除 RAR、`ArchiveManifest`、归档下载、Word 导出、来源报告、默认值或其他输出

#### Scenario: 用户清理 Parser 缓存

- **WHEN** 用户确认第一阶段清理 Parser 缓存操作
- **THEN** Parser 缓存端点返回清理结果，下一次解析重新读取来源输入
- **AND** 已加载的前端报告数据不需要立即消失
- **AND** 清理 Parser 缓存 MUST NOT 删除 RAR、`ArchiveManifest`、归档下载、Word 导出、来源报告、默认值或其他输出
