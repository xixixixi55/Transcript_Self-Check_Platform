# Spec Delta: 新案件可选择笔录哈希算法

> 基准 Spec: `openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（REQ-007、REQ-009、REQ-015、REQ-019）

## MODIFIED: CAP-003 — 全文在线编辑

### REQ-007: 任意字段可编辑

系统 MUST 在“笔录默认设置”中提供文件哈希算法设置，并将其作为新案件不可变的业务算法快照。

#### Scenario: 设置新案件哈希算法

- **WHEN** 用户在“笔录默认设置”选择 MD5、SHA-1 或 SHA-256 并成功保存
- **THEN** 系统持久化规范值 `md5`、`sha1` 或 `sha256`
- **AND** 随后创建的新案件在 `inspection.result.hash_algorithm` 保存该算法快照
- **AND** 已创建案件不因默认设置变化而改变
- **AND** 存量案件缺失算法字段时按 MD5 处理

#### Scenario: 拒绝无效哈希算法

- **WHEN** 默认值接口收到空值或候选集合以外的哈希算法
- **THEN** 系统整体拒绝请求并保持 revision 与已有默认值不变

## MODIFIED: CAP-004 — Word 文档生成

### REQ-009: 生成 Word 文档

系统 MUST 使用案件哈希算法快照生成检查结果、附件和 Word 内容，同时保留 legacy 模板字段兼容。

#### Scenario: Word 和附件使用案件选择的哈希

- **WHEN** 案件选择 SHA-1 或 SHA-256 且归档完成
- **THEN** 检查结果、附件1列标题、提取方式文案和 Word 正文使用对应算法名称
- **AND** 各分卷显示对应算法的完整大写摘要值
- **AND** 附件3“文件哈希”使用同一业务摘要
- **AND** legacy `md5_hash` 字段键可以承载所选摘要，但不得继续向用户展示错误的 MD5 标签

## MODIFIED: CAP-008 — 文件信息展示

### REQ-015: 展示哈希和文件大小

系统 MUST 区分归档内部完整性 MD5 与案件选择的业务哈希。

#### Scenario: Manifest 同时保存安全 MD5 与业务哈希

- **WHEN** 系统完成一个新案件的 RAR 归档
- **THEN** 每个 `ArchivePart.md5` 继续保存并验证内部完整性 MD5
- **AND** 每个 part 同时保存案件 `hash_algorithm` 与对应 `hash_value`
- **AND** MD5 案件直接复用 `md5`，不得为同一算法重复读取文件
- **AND** SHA-1 与 SHA-256 摘要长度分别为 40 和 64 个十六进制字符

#### Scenario: 兼容旧 Manifest

- **WHEN** 系统读取缺少 `hash_algorithm` 或 `hash_value` 的既有 Manifest
- **THEN** 将其业务算法和值解释为 MD5 与现有 `md5`
- **AND** 现有完整性校验、下载、复用和发布安全门保持不变

## MODIFIED: 统一导出完整产物包

### Requirement: HashMyFiles 截取案件所选算法列

统一导出 MUST 使用案件算法生成 HashMyFiles 校验截图，并保持原子发布。

#### Scenario: 截取所选 HashMyFiles 算法列

- **WHEN** 用户统一导出选择 MD5、SHA-1 或 SHA-256 的案件
- **THEN** 系统只启用 HashMyFiles 中对应的算法
- **AND** 读取并校验 Filename、所选算法摘要、File Size
- **AND** 最终截图只显示这三列，算法列标题与案件选择一致
- **AND** 哈希列与截图窗口按摘要长度展开，完整摘要不得以省略号替代
- **AND** 结果列缺失、摘要长度不符或截图失败时导出明确失败且保留上一版完整产物
