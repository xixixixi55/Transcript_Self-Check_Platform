## MODIFIED Requirements

### Requirement: REQ-029: 案件工作台承接完整生成笔录能力

#### Scenario: 案件前端不展示 Demo 就绪状态

- **WHEN** 用户进入电子数据检查入口或案件工作台
- **THEN** 页面不展示“Demo 环境就绪状态”区域
- **AND** 页面不展示后端、WinRAR、归档输出根三项就绪状态
- **AND** 页面不因该展示发起 Demo 就绪接口请求

#### Scenario: 删除操作只执行预检

- **WHEN** 用户点击案件卡片的检查删除条件按钮
- **THEN** 系统只调用既有删除预检并展示稳定结果
- **AND** 不删除案件、草稿、来源、归档或正式产物
