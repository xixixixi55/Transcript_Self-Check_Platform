## MODIFIED Requirements

### Requirement: REQ-029: 案件工作台承接完整生成笔录能力

#### Scenario: 统一平台外壳和父子导航

- **WHEN** 用户进入首页、电子数据检查模块、生成笔录或设备管理页面
- **THEN** 页面使用同一个 `PlatformShell`
- **AND** 电子数据检查笔录是一级入口，生成笔录和设备管理是其二级入口
- **AND** 旧 `/generate` 和 `/devices` 地址通过路由重定向并保留可用查询参数和 hash

#### Scenario: 审核编辑页保留真实交互语义

- **WHEN** 用户进入审核编辑页
- **THEN** 页面显示真实案件摘要、当前步骤、待核对提示、保存状态和结构摘要 Drawer
- **AND** `Esc`、`Ctrl+S`、底部操作栏和重复操作保护只触发已实现的当前页面行为，不伪造服务器保存或 Word 最终版式
