## MODIFIED Requirements

### Requirement: REQ-002: 解析案件信息

系统 MUST 从受支持报告中解析可确认的案件事实，但委托时间 MUST 作为新案件草稿的人工维护字段初始化，不得从报告“创建时间”推导。

#### Scenario: 新案件委托时间默认当天日期

- **WHEN** 系统完成报告解析并首次初始化新案件草稿
- **THEN** `introduction.entrust_time` 使用 `Asia/Shanghai` 时区的当天日期
- **AND** 值使用 `YYYY年M月D日` 的纯日期格式，不包含时分秒

#### Scenario: 报告创建时间不作为委托时间

- **WHEN** 报告 `data_case_info.json` 包含“创建时间”，且该日期与草稿初始化当天不同
- **THEN** 系统 MUST NOT 将报告“创建时间”写入 `introduction.entrust_time`
- **AND** “创建时间”仍可按现有合同参与检查起止时间计算

#### Scenario: 用户人工维护委托时间

- **WHEN** 用户在审核页面修改新案件预填的委托时间并保存草稿
- **THEN** 系统保留用户选择的日期供预览和 Word 导出使用
- **AND** 后续加载已保存案件时不得用新的当天日期覆盖用户值
