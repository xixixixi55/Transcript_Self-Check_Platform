## MODIFIED Requirements

### Requirement: REQ-009: 导出标准格式笔录

#### Scenario: VML 宿主段落和占位符保持完整

- **WHEN** 系统使用正式模板填充 Word 文档
- **THEN** 正文中的 `w:pict`、`v:shape`、`v:textbox` 和 `w:txbxContent` 宿主结构保持存在
- **AND** 占位符只在 VML 文本框子树内替换，不删除宿主段落

#### Scenario: 数据摘要和附件分页保持确定性

- **WHEN** 数据摘要为空、为 null 或仅包含空白，或附件区域包含 0、1、2 张图片
- **THEN** 数据摘要使用“即时通讯、手机信息”作为固定默认值
- **AND** 附件摘要、附件 1、附件 2、附件 3 按既定分页规则生成且不产生无意义空白页
