## ADDED Requirements

### Requirement: 统一文件变化信任状态

Parser SHALL 通过同一内部文件变化信任合同评估每个依赖。合同 MUST 区分 `trusted_unchanged`、`changed` 和 `untrusted`；只有 `trusted_unchanged` 允许复用已存摘要。公共 API、用户可见错误和日志 MUST 只暴露不透明标识符和原因码，绝不暴露绝对路径。

#### Scenario: 受信任 NTFS 文件无需重读内容即可复用

- **WHEN** 来源为受支持的本地 NTFS 文件，当前卷和 Journal 标识有效，文件标识及逐文件 USN 令牌等于已存令牌，且目录成员关系未变化
- **THEN** 系统复用已存摘要而不重新读取该文件内容
- **AND** Parser 缓存可以复用对应 `InspectionReport`

#### Scenario: 检测到统计信息相同的内容替换

- **WHEN** 文件在原位置被不同内容覆盖，但路径、大小、stat 时间戳和文件标识保持不变
- **THEN** 当前逐文件变化令牌 MUST 不同，或者提供方 MUST 返回 `untrusted`
- **AND** MUST NOT 返回旧摘要和旧 `InspectionReport`

#### Scenario: 不受支持或不确定的来源使用安全回退

- **WHEN** 来源不是 NTFS、属于网络/移动/云来源、受权限限制、缺失，或 USN/API/Journal 状态无法证明内容未变化
- **THEN** 系统 MUST 对受影响依赖执行完整内容摘要验证
- **AND** 回退成功时 MUST 仍允许正常解析
- **AND** 回退失败时 MUST 使解析失败，而不是返回旧缓存

### Requirement: 目录成员关系信任

系统 SHALL 校验每个候选目录和选定依赖集按序排列的相对路径及条目类型成员关系。成员关系变化 MUST 使 Parser 缓存失效，而无需完整读取无关文件内容。

#### Scenario: 增加或删除依赖文件

- **WHEN** 选定依赖被增加、删除或变为不可读
- **THEN** 缓存输入 MUST 标为已变化或不受信任
- **AND** MUST NOT 返回旧解析结果

#### Scenario: 依赖文件被原子替换或重新创建

- **WHEN** 选定路径被另一个文件替换，或删除后重新创建
- **THEN** 系统 MUST 比较文件标识和变化令牌
- **AND** 解析前 MUST 使缓存失效或安全地重新验证缓存

### Requirement: 读取一致性和 TOCTOU 处理

系统 SHALL 在读取内容前后校验文件状态。如果读取前后文件标识、大小或变化令牌不同，MUST NOT 发布摘要、缓存记录或解析结果。

#### Scenario: 内容验证期间文件变化

- **WHEN** 读取依赖字节期间该依赖发生变化
- **THEN** 系统 MUST 丢弃候选摘要和缓存结果
- **AND** MUST 返回输入已变化或等价的可重试解析失败
- **AND** MUST NOT 使用休眠、随机重试或过时结果掩盖竞争

#### Scenario: 复用前无法确认验证状态

- **WHEN** 提供方无法在返回缓存命中前完成最终令牌确认
- **THEN** 系统 MUST 使用完整内容验证，而不是返回缓存结果

### Requirement: 进程和重启信任边界

系统 SHALL 区分进程本地摘要记忆与磁盘持久化解析结果。重启后 MUST NOT 假定进程本地令牌仍有效。缺少当前输入信任模式的磁盘缓存记录在复用前 MUST 要求完整内容验证。

#### Scenario: 缓存命中前服务重启

- **WHEN** 服务重启，且磁盘 Parser 缓存记录没有可验证的当前进程令牌
- **THEN** 首次复用尝试 MUST 执行完整内容验证
- **AND** 只有验证成功后才能建立新的进程本地信任

#### Scenario: 迁移 Legacy 缓存记录

- **WHEN** 语法有效的旧缓存记录缺少 `input_trust_schema`
- **THEN** 系统在复用前 MUST 验证全部必需输入内容
- **AND** 验证成功后 MAY 使用当前模式重写记录
- **AND** 格式错误或无效的记录 MUST 视为缓存未命中

### Requirement: 打包后的 Windows 行为

变化令牌适配器 SHALL 在后端延迟加载，且 SHALL 不要求客户安装额外系统组件。Win32 调用失败时，最终打包可执行文件 MUST 保留安全回退行为。

#### Scenario: 打包可执行文件无法访问 USN

- **WHEN** 打包可执行文件以受支持账户运行，但 USN 调用返回访问或 API 错误
- **THEN** Parser MUST 继续使用完整内容验证
- **AND** 诊断 MUST 使用不透明原因码，不暴露来源路径
