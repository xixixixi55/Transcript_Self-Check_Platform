# 规格增量：新案件可选择笔录哈希算法

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

### Requirement: 检查笔录统一导出保持无截图合同

检查笔录统一导出 MUST 继续只发布 Word 与已验证 RAR，不得接入为鉴定文书预留的 HashMyFiles 截图能力。

#### Scenario: 统一导出不运行 HashMyFiles

- **WHEN** 用户统一导出选择 MD5、SHA-1 或 SHA-256 的检查笔录案件
- **THEN** 系统在进入统一导出前按 Manifest 所选算法完成内容授权
- **AND** 导出编排只暂存并原子发布 Word 与全部 RAR，不启动 HashMyFiles、不生成 PNG
- **AND** 再次成功导出移除目标目录中的历史 `hash-verification.png` 或 `hash-verification.html`
- **AND** HashMyFiles 三算法与三列截图能力保留为内部未接线能力，等待鉴定文书模块定义使用合同
