## MODIFIED Requirements

### Requirement: REQ-002: 解析案件信息

#### Scenario: 旧新报告格式归一化

- **WHEN** 用户提交受支持的旧格式、新格式或明确可归一化的混合格式报告目录
- **THEN** 系统先完成稳定格式检测，再输出同一套 `InspectionReport` Legacy DTO
- **AND** 不改变现有审核页面、公共模型或 Word 导出入口

### Requirement: REQ-003: 解析设备信息

#### Scenario: 设备字段来源和 IMEI 优先级稳定

- **WHEN** 报告同时包含 `tb2`、结构化设备表和普通候选文本
- **THEN** 合法非空 IMEI1/IMEI2 优先使用 `tb2` 值，仅在缺失时使用结构明确的设备表补充
- **AND** 解析不得依赖具体文件名、任意 15 位数字或跨检材拼接

#### Scenario: 不支持结构安全失败

- **WHEN** 报告缺少核心结构或格式无法识别
- **THEN** 返回稳定结构错误，不生成伪造的标准报告或部分成功结果
