## MODIFIED Requirements

### Requirement: EvidenceItem 可提取状态推导

`EvidenceItem.extractable` 缺失时，系统 MUST 仅按 `imei1` 或 `imei2` 是否至少存在一个非空值推导可提取状态；`serial_number` MUST 继续解析、保存和展示，但不得参与自动推导。用户显式保存的 `extractable` 布尔值 MUST 保持有效。

#### Scenario: 仅序列号不再自动判为可提取

- **WHEN** 检材的 IMEI1、IMEI2 均为空且序列号非空，并且没有显式 `extractable` 布尔值
- **THEN** 系统将该检材自动判为无法提取
- **AND** 序列号仍保留在检材数据和獬豸助手预览中

#### Scenario: 任一 IMEI 存在即可自动判为可提取

- **WHEN** 检材的 IMEI1 或 IMEI2 至少一个非空，并且没有显式 `extractable` 布尔值
- **THEN** 系统将该检材自动判为可提取

#### Scenario: 人工修正优先于自动推导

- **WHEN** 检材已经保存显式 `extractable` 布尔值
- **THEN** 系统使用该显式值，不因 IMEI 或序列号内容重新覆盖用户选择
