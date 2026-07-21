# Spec: 电子数据检查笔录自动生成

> 能力：CAP-001 ~ CAP-009
> 状态：MODIFIED（2026-07-13: 新增 CAP-006~009 上传流程优化）

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
│   └── [检材编号]/                  ← 设备详情（型号/IMEI/序列号）
│       ├── Base/                     ← 传统格式（JSON 键值对）
│       └── Phone/                    ← 表格格式（信息/内容 列）
├── assets/  md/  static/            ← 不解析，生成归档时原样打包
```

**Scenario: 选择文件夹上传（压缩默认勾选）**
- WHEN 用户通过文件夹选择器选择报告文件夹
- AND "压缩为 .rar"复选框保持默认勾选
- THEN 前端以 `webkitdirectory` 模式上传 data/ 目录下的所有 JSON 文件
- AND 后端解析各 JSON 提取案件信息、设备信息、工具版本、数据分类统计
- AND 后端将整个报告目录建立 `ArchiveContext`（不在此阶段执行真实压缩）
- AND 返回结构化解析结果（含 archive_context_id）
- AND 后续归档执行由单独导出流程触发，解析与归档结果分离

**Scenario: 选择文件夹上传（取消压缩）**
- WHEN 用户取消勾选"压缩为 .rar"复选框
- AND 选择报告文件夹上传
- THEN 后端跳过 RAR 压缩步骤
- AND 不计算 MD5
- AND 返回的 `rar_info` 为 null

**Scenario: 上传 .rar/.zip 压缩包（CAP-007）**
- WHEN 用户通过文件选择器选择 .rar 或 .zip 文件上传
- THEN 后端解压到临时目录，解析内部 JSON 数据
- AND 直接计算上传文件的 MD5 和文件大小
- AND 跳过压缩步骤

**Scenario: 缺少必需文件**
- WHEN data/ 目录下缺少必需 JSON 文件
- THEN 返回 422 错误，明确提示缺少哪个文件

**Scenario: 文件类型不支持**
- WHEN 用户选择非 .rar/.zip 格式的文件
- THEN 前端阻止上传，提示"仅支持 .rar 和 .zip 格式"

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

**Scenario: 从检材子目录提取设备详情**
- WHEN 解析 `data/[检材编号]/` 下各直接子目录中的 JSON 文件（不限于 Base/，也包含 Phone/ 等）
- THEN 优先从结构化 JSON 中提取设备字段
- AND 支持多种 JSON 格式：
  - `{"name": "设备名称", "value": "iPhone 13 Pro"}` 键值对格式
  - `{"信息": "设备名称", "内容": "iPhone 13 Pro"}` 表格行格式
  - `{"c1": "设备名称", "c2": "iPhone 13 Pro"}` 列标识格式
- AND 识别以下字段别名：
  - 设备名称：设备名称、手机名称、Device Name、productname
  - 型号：型号、设备型号、手机型号、model
  - 序列号：序列号、Serial、SN
  - IMEI1/IMEI2
- AND 结构化解析失败时回退到正则匹配
- AND 返回结构化设备列表（含 device_type / model / imei1 / imei2 / serial_number / evidence_number）

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
- AND 网页预览是可编辑的结构化内容展示，不承诺等同于最终 Word 的分页和版式渲染

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
- THEN 附件2使用显式 `MaterialPhotoGroup`，每组绑定一个检材及其两张图片
- AND Renderer 不得根据文件名或数组位置猜测检材归属
- AND 当前排版规则：一个检材组左右两张图片居中，两个检材组上下两组

---

## CAP-004: 导出 .docx

### REQ-009: 导出标准格式笔录

**Scenario: 确认无误后导出**
- WHEN 民警点击"导出 Word"按钮
- THEN 系统使用 `word_templates/template.docx`（唯一正式运行模板）和 `current-template-v1` TemplateProfile 生成 .docx
- AND 渲染失败时必须明确失败，不得静默回退到旧输出路径
- AND 附件2区域按 `MaterialPhotoGroup` 显式绑定检材和图片，不根据文件名或数组位置猜测归属
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
- AND 缓存路径按压缩模式区分为 `output/parsed/[报告目录名].compress.json` 或 `output/parsed/[报告目录名].nocompress.json`
- AND 缓存载荷中的 `cache_version` 当前为 `4`

**Scenario: 重复解析时复用缓存**
- WHEN 再次请求解析相同的报告目录
- AND 缓存文件存在
- THEN 直接返回缓存中的解析结果，跳过 JSON 读取和解析
- AND RAR 压缩步骤单独判断（见 REQ-012）

**Scenario: 缓存失效**
- WHEN 报告目录的源 JSON 文件修改时间晚于缓存文件时间
- THEN 重新解析并更新缓存

## REQ-012: 避免重复压缩

**Scenario: 压缩开关关闭时跳过**
- WHEN `compress=false`
- THEN 无论 RAR 是否存在，均跳过压缩步骤
- AND `rar_info` 返回 null

**Scenario: RAR 已存在且 compress=true 时跳过**
- WHEN `compress=true`
- AND `output/compressed/[案件名称].rar` 或 `.zip` 已存在且大小 > 0
- THEN 跳过压缩步骤，直接使用现有归档文件并重新计算其 MD5 和大小

**Scenario: RAR 不存在时正常压缩**
- WHEN 可复用的归档文件不存在
- THEN 正常执行归档生成 + MD5 计算

---

## CAP-006: 压缩选项控制

### REQ-013: 压缩复选框

**Scenario: 默认勾选压缩**
- WHEN 用户进入上传页面
- THEN "压缩为 .rar"复选框默认勾选

**Scenario: 压缩复选框仅在文件夹模式下可用**
- WHEN 用户选择"上传压缩包"模式
- THEN "压缩为 .rar"复选框禁用或隐藏

**Scenario: 取消压缩后检查结果留空**
- WHEN 用户取消压缩并完成解析
- THEN 检查结果中的 RAR 文件名、MD5 哈希、文件大小字段留空
- AND 导出的 Word 笔录中对应字段显示为空

---

## CAP-007: 压缩包直接上传

### REQ-014: 上传 .rar/.zip 压缩包

**Scenario: 上传 .rar 文件并解析**
- WHEN 用户通过文件选择器选择 .rar 文件上传
- THEN 后端接收文件，调用 WinRAR CLI 解压到临时目录
- AND 解析 JSON 数据，构建 InspectionReport
- AND 直接计算上传的 .rar 文件的 MD5 和文件大小
- AND 跳过压缩步骤

**Scenario: 上传 .zip 文件并解析**
- WHEN 用户选择 .zip 文件上传
- THEN 使用 Python zipfile 标准库解压

**Scenario: 压缩包内缺少必需文件**
- WHEN 解压后的 data/ 目录下缺少必需 JSON 文件
- THEN 返回 422 错误，明确提示缺少哪个文件

---

## CAP-008: 文件信息展示

### REQ-015: 展示 MD5 和文件大小

**Scenario: 上传后展示文件信息**
- WHEN 报告解析成功
- AND rar_info 不为 null
- THEN 前端展示文件 MD5（32 位十六进制）和文件大小（MB 格式）
- AND 信息位于上传区域下方的 FileInfoCard 组件中

**Scenario: 未压缩时不展示文件信息**
- WHEN rar_info 为 null
- THEN 显示"未生成压缩文件"

---

## CAP-009: 软件工具列表动态生成

### REQ-016: 按实际操作生成 software_tools

系统 MUST 根据实际运行环境生成 software_tools 列表；列表数量取决于产品版本是否成功解析。

产品版本非空时包含三项；产品版本为空时省略美亚手机大师，保留 WinRAR 和 Python hashlib 两项：

| 条件 | 名称 | 版本来源 |
|:---:|------|---------|
| product_version 非空 | 美亚手机大师-并行版V5 | `data_report_info.json` 的 product_version |
| 始终 | WinRAR压缩管理软件 | `detect_winrar_version()`，未检测到则默认 "6.24"（用户可修改） |
| 始终 | Python hashlib | `sys.version_info`（如 "3.11.0"） |

**Scenario: WinRAR 始终显示**
- WHEN 生成 software_tools
- THEN 始终包含"WinRAR压缩管理软件"
- AND 版本号为实际检测值或默认 "6.24"
- AND 用户可在预览中修改版本号

**Scenario: Python hashlib 显示实际 Python 版本**
- WHEN 生成 software_tools
- THEN 包含"Python hashlib"，版本号为当前运行 Python 解释器的实际版本（如 "3.11.0"）

**Scenario: 产品版本为空时省略美亚工具**
- WHEN `data_report_info.json` 未提供产品版本
- THEN `software_tools` 不包含"美亚手机大师-并行版V5"
- AND 仍包含 WinRAR 和 Python hashlib

---

## CAP-010: 附件1 电子数据提取固定清单自动填充

### REQ-017: 从 rar_info 自动填充提取清单

**Scenario: 压缩后自动填充附件1**
- WHEN 目录解析启用压缩且生成了归档文件
- THEN `attachments.extract_list` 自动填充一行数据：
  - 列结构固定为：序号、电子数据、来源、提取方式、文件MD5哈希值
  - 电子数据 = 归档文件名
  - 来源 = `[检材编号]检材内提取`（检材编号为空时为空）
  - 提取方式 = "使用美亚手机取证塔对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值"
  - 文件MD5哈希值 = 归档文件的 MD5 哈希值
- AND 用户可继续编辑或添加行

**Scenario: 未压缩时附件1留空**
- WHEN 压缩开关关闭、未生成 RAR 文件
- THEN `attachments.extract_list` 仍有标准 5 列表头但无数据行
- AND 用户可手动填写
- AND 直接上传 `.rar/.zip` 时，归档文件信息写入检查结果和 `rar_info`，当前实现不自动补附件1数据行

---

## 存储路径

| 用途 | 路径 |
|------|------|
| 解析缓存 | `output/parsed/`（本地，不得进入 Git） |
| 归档文件 | `output/compressed/`（本地，不得进入 Git） |
| 导出 .docx | `output/exports/`（本地，不得进入 Git） |
| 硬件设备配置 | `packages/backend/app/data/hardware_devices.json` |

## 跨功能约束

- **MUST**: API 响应字段名用 camelCase，Python 内部用 snake_case，Controller 层做转换
- **MUST**: officecli 作为旧版回退路径存在于 `record_generator_service.py`，当前正式渲染主路径为 `template_filler_service.py`
- **MUST**: 生成的 .docx 使用唯一正式模板 `word_templates/template.docx`（`current-template-v1` TemplateProfile）；渲染失败时必须明确报错，不得静默回退
- **MUST**: 基于 AGENTS.md 治理规则，Level 1 小修改无需 OpenSpec change；架构或公共合同变更仍需完整流程
- **MUST**: `rar_info` 在 ParseReportResponse 中为可选字段（`RarInfo | null`）
- **MUST**: 解压操作仅存在于 BE_Repository 层（`file_storage.py`）
- **MUST**: 软件工具列表由后端根据实际运行环境生成；WinRAR 和 Python hashlib 始终显示，产品版本为空时省略美亚手机大师
- **MUST**: `entrust_time`（委托时间）使用中文格式（如 `2026年6月30日`），由 `format_time_chinese()` 转换
- **MUST**: `file_size` 保持后端当前字符串语义；目录压缩为字节数文本，压缩包直传为带“字节”后缀的文本
- **MUST**: 设备解析时优先结构化 JSON，再正则回退；扫描检材目录下各直接子目录（不限于 Base/），支持 `设备型号`、`信息/内容` 和 `c1/c2`
- **MUST**: DOCX 生成格式遵循项目模板/构建器定义的标准结构；自动化验证不替代人工视觉验收
