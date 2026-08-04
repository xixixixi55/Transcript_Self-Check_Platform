## MODIFIED Requirements

### Requirement: REQ-009: 导出标准格式笔录

#### Scenario: 使用当前正式模板填充报告

- **WHEN** 用户导出有效审核报告且 `word_templates/template.docx` 存在
- **THEN** 系统使用带占位符和列表块的正式模板填充报告
- **AND** 委托人数组、检材、检查人员、检查过程和提取清单按模板约定展开
- **AND** 模板填充失败时不返回伪成功空文件

#### Scenario: 模板缺失时保持兼容回退

- **WHEN** 正式模板不可用
- **THEN** 系统按既有兼容路径处理并明确报告结果
- **AND** 不改变现有 Legacy DTO、Word 字段映射和附件安全门控
