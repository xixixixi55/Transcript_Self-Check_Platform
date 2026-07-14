# Spec: 电子数据检查笔录自动生成

> 能力：CAP-001 ~ CAP-005
> 状态：ADDED

---

## CAP-001: HTML 报告上传与解析

### REQ-001: 上传报告目录

**标准文件夹格式**（美亚手机大师 FL-901V5 生成）：

```
[案件名称]_[时间戳]_html/
├── [案件名称]_[时间戳]_html.html    ← 入口
├── data/
│   ├── data_case_info.json          ← 必须：案件信息
│   ├── data_device_lists.json       ← 必须：设备列表
│   ├── data_report_info.json        ← 必须：工具版本
│   ├── data_navigation.json         ← 必须：数据分类树
│   └── [检材编号]/Base/             ← 必须：设备详情（型号/IMEI）
├── assets/  md/  static/            ← 不解析，压缩 .rar 时原样打包
```

**Scenario: 选择文件夹上传**
- WHEN 用户通过文件夹选择器选择报告文件夹
- THEN 前端以 `webkitdirectory` 模式上传 data/ 目录下的所有 JSON 文件
- AND 后端解析各 JSON 提取案件信息、设备信息、工具版本、数据分类统计
- AND 返回结构化解析结果

**Scenario: 缺少必需文件**
- WHEN data/ 目录下缺少 data_case_info.json、data_device_lists.json、data_report_info.json、data_navigation.json 任一文件
- THEN 返回 422 错误，明确提示缺少哪个文件

**Scenario: RAR 压缩与 MD5 计算**
- WHEN 解析完成后
- THEN 后端将整个报告目录压缩为 `[案件名称].rar`
- AND 用 Python hashlib.md5() 计算 MD5 哈希值
- AND 记录 RAR 文件名、MD5、文件大小，用于自动填充检查结果

### REQ-002: 解析案件信息

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

### REQ-003: 解析设备信息

**Scenario: 提取检材详情**
- WHEN 解析 data_device_lists 和 data_navigation 中手机基本信息
- THEN 提取设备型号（如 iPhone 13 Pro）、IMEI/序列号、取证时间范围
- AND 返回结构化设备列表

### REQ-004: 解析取证工具信息

- WHEN 解析 data_report_info.json
- THEN 提取产品版本（如 FL-901V5 V3.2.12922）、平台版本、应用版本
- AND 返回版本信息供笔录填充

---

## CAP-002: 笔录 Web 预览

### REQ-005: 生成笔录预览

**Scenario: 解析完成后展示完整笔录预览**
- WHEN 解析完成
- THEN 系统将提取数据填入笔录模板，在页面上渲染完整笔录预览
- AND 预览包含所有章节：
  - 标题 + 文号
  - 一、绪论（一～九）
  - 二、检查（一～四）
  - 附件区域
  - 签名区

**Scenario: 缺失字段留空**
- WHEN 某个字段无法从 HTML 报告中提取（如检查人员、检查地点）
- THEN 该字段在预览中显示为空白输入框，等待民警填写

### REQ-006: 检查过程自动生成

**Scenario: 按模板生成检查过程**
- WHEN 系统生成检查过程章节
- THEN 按以下模板自动填充：
  - 步骤1: "将[设备型号]（IMEI1：[值]；IMEI2：[值]）编号为[检材编号]。"
  - 步骤2: "对检材[编号]进行拍照。"
  - 步骤3: "启动美亚FL-901手机取证塔，Windows 10 64位企业版操作系统启动正常，使用火绒安全软件（版本号为6.0.6.1）对取证塔进行杀毒，未发现病毒，完毕后退出火绒安全软件。"
  - 步骤4: "启动美亚手机大师-并行版V5软件（版本号为[版本号]）使用美亚手机大师-并行版V5软件对检材[编号]进行检查。"
- AND 设备型号/IMEI/编号/版本号从解析数据自动替换

---

## CAP-003: 全文在线编辑

### REQ-007: 任意字段可编辑

**Scenario: 点击字段进入编辑**
- WHEN 民警在预览页面上点击任意文本字段
- THEN 该字段切换为可编辑状态（输入框/文本域）
- AND 修改后自动保存到当前会话

**Scenario: 修改委托人**
- WHEN 民警修改委托人字段
- THEN 预览实时更新显示新值

**Scenario: 修改案件简要情况**
- WHEN 民警编辑案件简要情况（自由文本）
- THEN 预览实时更新

**Scenario: 修改检查设备硬件**
- WHEN 民警从硬件下拉框选择不同设备
- THEN 检查设备章节自动更新

**Scenario: 修改软件版本号**
- WHEN 民警修改软件版本号
- THEN 检查过程和检查设备章节中的版本号同步更新

### REQ-008: 附件图片上传

**Scenario: 上传检材照片**
- WHEN 民警在附件区域点击"添加照片"按钮
- THEN 弹出文件选择器，支持选择本地 .jpg/.png 图片文件
- AND 支持一次选择多张图片

**Scenario: 预览和管理已上传照片**
- WHEN 图片上传完成
- THEN 预览区展示已上传的缩略图列表
- AND 每张图片支持删除和拖拽排序

**Scenario: 导出时图片嵌入 .docx**
- WHEN 导出 .docx 时
- THEN 附件2区域自动嵌入所有已上传的检材照片
- AND 每张照片下方附带"检材[编号]照片"标签

---

## CAP-004: 导出 .docx

### REQ-009: 导出标准格式笔录

**Scenario: 确认无误后导出**
- WHEN 民警点击"导出 Word"按钮
- THEN 系统将当前预览内容（含所有文本修改 + 附件图片）通过 officecli 生成 .docx
- AND 附件2区域嵌入所有已上传的检材照片（原图嵌入）
- AND 文件文号格式为 "xx电检〔YYYY〕xx号"
- AND 自动触发浏览器下载

**Scenario: 导出后仍可修改**
- WHEN 导出完成后
- THEN 预览页面不关闭，民警可继续修改并再次导出

---

## CAP-005: 硬件设备管理

### REQ-010: 硬件设备 CRUD

**Scenario: 查看设备列表**
- WHEN 民警进入设备管理页面
- THEN 展示所有已配置的取证硬件设备（名称、型号、描述）

**Scenario: 添加新设备**
- WHEN 民警填写设备名称、型号并保存
- THEN 该设备出现在生成笔录的硬件下拉框中

**Scenario: 删除设备**
- WHEN 民警删除某个设备
- THEN 该设备从列表中移除，但不影响已生成的笔录

---

## REQ-011: 解析缓存

**Scenario: 首次解析后缓存**
- WHEN 首次解析某个报告目录成功
- THEN 将完整解析结果（InspectionReport + rar_info）保存为 JSON 缓存文件
- AND 缓存路径为 `output/parsed/[报告目录名].json`

**Scenario: 重复解析时复用缓存**
- WHEN 再次请求解析相同的报告目录
- AND 缓存文件存在
- THEN 直接返回缓存中的解析结果，跳过 JSON 读取和解析
- AND RAR 压缩步骤单独判断（见 REQ-012）

**Scenario: 缓存失效**
- WHEN 报告目录的源 JSON 文件修改时间晚于缓存文件时间
- THEN 重新解析并更新缓存

## REQ-012: 避免重复压缩

**Scenario: RAR 已存在时跳过**
- WHEN 解析报告后需要生成 RAR
- AND `output/compressed/[案件名称].rar` 已存在且大小 > 0
- THEN 跳过压缩步骤，直接使用现有 RAR 文件
- AND 仅重新计算 MD5（或连 MD5 也缓存到 JSON 中）

**Scenario: RAR 不存在时正常压缩**
- WHEN RAR 文件不存在
- THEN 正常执行压缩 + MD5 计算

## 存储路径

| 用途 | 路径 |
|------|------|
| 解析缓存 | `output/parsed/[报告目录名].json` |
| RAR 压缩包 | `output/compressed/[案件名称].rar` |
| 导出 .docx | `output/exports/[文号].docx` |
| 硬件设备配置 | `packages/backend/app/data/hardware_devices.json` |

## 跨功能约束

- **MUST**: API 响应字段名用 camelCase，Python 内部用 snake_case，Controller 层做转换
- **MUST**: officecli 调用仅存在于 BE_Services 层
- **MUST**: 生成的 .docx 遵循标准检查笔录格式（参照 templates/ 中的样例文档）
- **MUST**: 不能跳过 spec 直接修改代码——任何代码变更必须先更新 spec 再实现
