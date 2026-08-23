## MODIFIED Requirements

### Requirement: REQ-002: 解析案件信息

系统 MUST 满足以下现有合同：
系统从 data_case_info.json 自动提取以下字段：

| 字段 | 数据来源 | 映射到笔录 |
|------|---------|-----------|
| 案件名称 | contents[tp=案件名称] | 一(四) 案件简要情况 |
| 案件编号 | contents[tp=案件编号] | 文号 |
| 送检人 | contents[tp=送检人] | 一(二) 委托人 |
| 送检单位 | contents[tp=送检单位] | 一(一) 委托单位 |
| 采集人 | contents[tp=采集人] | —（备用） |
| 案件类型 | contents[tp=案件类型] | —（备用） |
| 报告时间 | contents[tp=报告时间] | 一(七) 检查结束时间 |

#### Scenario: 解析案件字段供当前笔录使用
- **WHEN** 解析受授权报告目录中的 `data_case_info.json`
- **THEN** 系统提取表中字段并填入当前 `InspectionReport`/`CaseDraft`，无法确认的字段保持为空，不伪造案件事实

#### Scenario: 清理案件名称末尾括号标记
- **WHEN** 报告案件名称识别结果为 `xx案（yy）` 或 `xx案(yy)` 形式
- **THEN** 系统 MUST 删除末尾括号及括号内内容，并将清理后的 `xx案` 用于 CaseDraft 案件名称和案件简要情况
- **AND** 清理仅针对案件名称末尾的括号标记，不删除名称中部内容

#### Scenario: 不自动补充案字
- **WHEN** 报告案件名称识别结果不以“案”结尾
- **THEN** 系统 MUST 保留清理后的案件名称原文作为案件简要情况
- **AND** 系统 MUST NOT 自动在末尾追加“案”

#### Scenario: 旧新报告格式归一化
- **WHEN** 用户提交受支持的旧格式、新格式或明确可归一化的混合格式报告目录
- **THEN** 系统先完成稳定格式检测，再输出同一套 `InspectionReport` Legacy DTO
- **AND** 不改变现有审核页面、公共模型或 Word 导出入口
