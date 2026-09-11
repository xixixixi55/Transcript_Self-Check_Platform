## MODIFIED Requirements

### Requirement: REQ-002: 解析案件信息

系统 MUST 从受支持报告中解析可确认的案件事实，但委托时间 MUST 作为新案件草稿的人工维护字段保持为空，不得从报告“创建时间”或系统日期推导。

#### Scenario: 新案件委托时间默认留空并提示选择

- **WHEN** 系统完成报告解析并首次初始化新案件草稿
- **THEN** `introduction.entrust_time` 保持为空且字段处于待确认状态
- **AND** 审核页面在日期控件附近提示用户选择委托日期

#### Scenario: 报告创建时间不作为委托时间

- **WHEN** 报告 `data_case_info.json` 包含“创建时间”或旧委托时间种子
- **THEN** 系统 MUST NOT 将报告“创建时间”或旧种子写入 `introduction.entrust_time`
- **AND** “创建时间”仍可按现有合同参与检查起止时间计算

#### Scenario: 用户人工维护委托时间

- **WHEN** 用户在审核页面选择委托时间并保存草稿
- **THEN** 系统保留用户选择的日期供预览和 Word 导出使用
- **AND** 日期使用既有中文纯日期格式，后续加载已保存案件时不得清空或覆盖用户值
