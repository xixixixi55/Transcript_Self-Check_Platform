# Spec Delta: 新案件可选择笔录哈希算法

> 基准 Spec: `openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（REQ-007、REQ-009、REQ-015、REQ-019）

## MODIFIED Requirements

### Requirement: REQ-007 任意字段可编辑

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

### Requirement: REQ-009 生成 Word 文档

系统 MUST 使用案件哈希算法快照生成检查结果、附件和 Word 内容，同时保留 legacy 模板字段兼容；三种算法必须消费同一份规范 Manifest 投影。

#### Scenario: Word 和附件使用案件选择的哈希

- **WHEN** 案件选择 SHA-1 或 SHA-256 且归档完成
- **THEN** 检查结果、附件1列标题、提取方式文案和 Word 正文使用对应算法名称
- **AND** 各分卷显示对应算法的完整大写摘要值
- **AND** 附件3“文件哈希”使用同一业务摘要
- **AND** legacy `md5_hash` 字段键可以承载所选摘要，但不得继续向用户展示错误的 MD5 标签

### Requirement: REQ-015 展示哈希和文件大小

系统 MUST 把案件选择的 MD5、SHA-1 或 SHA-256 作为最终 RAR 的唯一正式文件哈希，并让三种算法经过相同的归档和安全校验链路。

#### Scenario: Manifest 只保存并验证所选算法

- **WHEN** 系统完成一个新案件的 RAR 归档
- **THEN** 每个 part 保存案件 `hash_algorithm` 与对应 `hash_value`
- **AND** 系统只计算所选算法，不得为 SHA-1 或 SHA-256 案件额外计算固定 MD5
- **AND** MD5、SHA-1 与 SHA-256 摘要长度分别为 32、40 和 64 个十六进制字符
- **AND** Manifest 登记、物理文件复核、复用、恢复、下载和发布均根据同一 `hash_algorithm/hash_value` 执行

#### Scenario: 三种算法使用相同状态与错误链路

- **WHEN** 相同的 SYNTHETIC 报告案件分别选择 MD5、SHA-1 和 SHA-256 完成归档
- **THEN** 三次执行经历相同的 WinRAR、完整性、哈希、Manifest、发布和完成状态
- **AND** 除算法名称、摘要值、摘要长度与展示列宽外，Manifest 结构、错误处理和正式产物结构一致

#### Scenario: 所选算法检测同大小内容变化

- **WHEN** 已归档 RAR 被替换为同名、同字节数但内容不同的文件
- **THEN** 复用、恢复、下载或其他要求内容授权的入口使用该 part 的所选算法重新计算并拒绝不匹配内容
- **AND** 不得依赖文件大小、修改时间或固定 MD5 代替所选算法比较

#### Scenario: 兼容旧 Manifest

- **WHEN** 系统读取缺少 `hash_algorithm` 或 `hash_value` 的既有 Manifest
- **THEN** 将其业务算法和值解释为 MD5 与现有 `md5`
- **AND** 兼容投影后进入与新 MD5 Manifest 相同的动态算法安全门
- **AND** 新 Manifest 不再生成或要求额外 `md5`

### Requirement: HashMyFiles 截取案件所选算法列

统一导出 MUST 使用 Manifest 绑定的案件算法生成 HashMyFiles 校验截图，把待发布副本的结构化结果与 Manifest 逐项等值比较，并保持原子发布。

#### Scenario: 截取所选 HashMyFiles 算法列

- **WHEN** 用户统一导出选择 MD5、SHA-1 或 SHA-256 的案件
- **THEN** 系统只启用 HashMyFiles 中对应的算法
- **AND** 读取并校验 Filename、所选算法摘要、File Size
- **AND** 每个 HashMyFiles 摘要必须与同名 Manifest part 的 `hash_value` 完全一致
- **AND** 最终截图只显示这三列，算法列标题与案件选择一致
- **AND** 哈希列与截图窗口按摘要长度展开，完整摘要不得以省略号替代
- **AND** 结果列缺失、行缺失/重复、摘要长度不符、摘要不一致或截图失败时导出明确失败且保留上一版完整产物

#### Scenario: 统一导出避免固定 MD5 重复读取

- **WHEN** 统一导出已验证发布身份、路径边界、RAR 集合和精确大小，并把 RAR 复制到同卷 staging
- **THEN** 系统由 HashMyFiles 对 staging 副本计算案件所选算法并与 Manifest 比较
- **AND** 不在复制前为了统一导出额外对全部源 RAR 计算固定 MD5
- **AND** MD5、SHA-1、SHA-256 的统一导出编排和完整读取次数一致

#### Scenario: HashMyFiles 摘要与 Manifest 不一致

- **WHEN** HashMyFiles 返回格式及长度合法但与 Manifest `hash_value` 不同的摘要
- **THEN** 统一导出以稳定错误失败
- **AND** staging 中的 Word、RAR 和 PNG 不得发布
- **AND** 上一版完整导出和案件未导出状态保持不变
