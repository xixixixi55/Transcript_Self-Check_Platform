# Spec Delta：预览字段映射与 Word 导出修复

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`

## ADDED: CAP-013 — 设备与检材字段映射

### REQ-029：预览显示完整检材信息

**Scenario: 从设备报告填充检材**

- WHEN 报告包含设备列表和对应 `data/<检材编号>/Base/` 数据
- THEN `introduction.evidence_list` 至少包含一条记录
- AND 设备名称、IMEI1、IMEI2、序列号和检材编号分别填入对应字段
- AND 检材编号等于报告设备列表中的检材名称（例如 `SYN-JC00000001`）

**Scenario: 缺少可选 Base 字段**

- WHEN Base 数据缺少某个可选字段
- THEN 其他已识别字段仍保留
- AND 缺失字段为空字符串，不得导致整条检材记录丢失

### REQ-030：预览设备字段语义一致

**Scenario: 显示设备名称**

- WHEN 预览渲染检材情况
- THEN 第一字段标签为“设备名称”
- AND 优先显示解析出的设备名称，旧缓存没有设备名称时才回退到型号字段

## ADDED: CAP-014 — 默认工具与附件清单

### REQ-031：默认包含 Python hash 工具

**Scenario: 生成软件工具列表**

- WHEN 目录、ZIP 或 RAR 报告解析完成
- THEN `inspection.software_tools` 包含用于计算 hash 的 Python 标准库工具
- AND 工具可在预览中编辑

### REQ-032：附件 1 使用标准五列表头

**Scenario: 预览空附件清单**

- WHEN `attachments.extract_list` 没有自定义列
- THEN 显示“序号、电子数据、来源、提取方式、文件MD5哈希值”五列
- AND 至少显示一行可编辑空记录

## ADDED: CAP-015 — Word 导出完整性

### REQ-033：导出包含预览内容

**Scenario: 导出当前笔录**

- WHEN 用户点击“导出 Word”且报告数据有效
- THEN 返回的 `.docx` 文件存在且大小大于零
- AND `word/document.xml` 包含标题、检材字段和附件 1 表头/数据

**Scenario: 文档构建失败**

- WHEN officecli 创建或写入文档失败，或生成文件为空
- THEN API 返回明确的 5xx 错误
- AND 不返回伪成功的空文件
