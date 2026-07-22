# Spec: 电子数据检查笔录自动生成

> 能力：CAP-001 ~ CAP-011
> 状态：MODIFIED（2026-07-22: 文档真相源与当前归档生产状态收口）

> 本文件是 living spec，只描述当前生产已经具备的能力。已批准但尚未生产启用的 Canonical/Shadow/`DocumentRenderPlan` 目标见 active change `openspec/changes/extensible-report-template-platform/spec.md`；当前实现与验收进度见其 `tasks.md`。代码和测试是实现证据，不自动覆盖已批准的业务合同。

当前生产输出仍由 `InspectionReport` legacy DTO 管线生成：生产 Controller 校验最终 `ArchiveManifest`，将其投影到兼容 DTO，并以 `ArchiveManifest` + `AttachmentPlan` + `current-template-v1` TemplateProfile 渲染唯一正式 DOCX。Canonical 模型、适配器、编排器和 Shadow 比较器已有基础实现，但未接入生产 Controller；`DocumentRenderPlan` 尚无生产构造和消费。

---

## CAP-001: HTML 报告上传与解析

### REQ-001: 提交受授权的本地报告目录

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

**Scenario: 输入本地报告目录路径并解析**
- WHEN 用户在当前页面输入受授权的本地报告目录路径
- THEN 前端以 `report_dir` 提交该路径，不使用 `webkitdirectory` 上传目录中的 JSON 文件
- AND 后端授权并直接读取该本地目录，解析 JSON 以提取案件信息、设备信息、工具版本和数据分类统计
- AND 解析成功后后端为该报告目录建立 `ArchiveContext` 并返回 `archive_context_id`
- AND 解析阶段不调用 WinRAR、不生成最终 `ArchiveManifest`
- AND 真实归档由导出时的独立归档入口执行，解析结果与最终归档结果分离

**Scenario: deprecated compress 参数不控制解析归档**
- WHEN 兼容请求传入任意 `compress` 值
- THEN 当前 UI 不暴露该参数，解析阶段无论其值为何均不调用 WinRAR
- AND `compress` 不决定解析成功后是否创建 `ArchiveContext`
- AND 该参数不能用来推断 `rar_info` 是否为 null 或归档是否完成

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
- THEN 生产 Controller 使用审核后的 `InspectionReport` legacy DTO 和已验证的最终 `ArchiveManifest` 构造 `AttachmentPlan`
- AND 系统使用 `word_templates/template.docx`（唯一正式运行模板）和 `current-template-v1` TemplateProfile 生成 .docx
- AND 带 Manifest 的正式渲染失败时必须明确失败，不得静默回退到无 Manifest 的 officecli batch 输出
- AND 当前导出不构造或消费 `CanonicalInspectionCase`/`DocumentRenderPlan`
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
- AND 路径中的 compress/nocompress 仅是 deprecated 参数留下的兼容命名空间，不代表执行过压缩
- AND 缓存载荷中的 `cache_version` 当前为 `6`

**Scenario: 重复解析时复用缓存**
- WHEN 再次请求解析相同的报告目录
- AND 缓存文件存在
- THEN 直接返回缓存中的解析结果，跳过 JSON 读取和解析
- AND 解析缓存与最终归档/Manifest 缓存彼此分离
- AND 缓存命中不会在解析阶段执行 WinRAR，也不会复用或伪造 WinRAR 结果

**Scenario: 缓存失效**
- WHEN 报告目录的源 JSON 文件修改时间晚于缓存文件时间
- THEN 重新解析并更新缓存

## REQ-012: 解析与最终归档分离

**Scenario: 解析阶段不执行真实压缩**
- WHEN 报告目录解析成功，无论 deprecated `compress` 参数为何值
- THEN 解析阶段只建立不透明 `archive_context_id`，不调用 WinRAR、不生成占位 Manifest
- AND 真实归档只由审核后的独立执行入口触发

**Scenario: 已验证 Manifest 的安全复用**
- WHEN 同一归档上下文、输入指纹、首光盘编号和审核数据均未变化，且已有已验证 Manifest
- THEN 文书失败后的同次安全重试可以复用该归档结果而不重复执行 WinRAR
- AND 新的导出请求仍重新验证实际 part 的存在性、大小和完整 MD5

---

## CAP-006: 废弃兼容参数边界

### REQ-013: deprecated compress 请求参数

**Scenario: 当前 UI 不提供压缩开关**
- WHEN 用户通过当前页面提交本地报告目录
- THEN 页面不展示“压缩为 .rar”复选框，也不提供默认勾选或取消勾选操作
- AND 后端仅为旧请求兼容保留 `compress` 参数
- AND 任意参数值都不触发解析阶段压缩、不决定 `ArchiveContext` 创建，也不构成最终归档状态证据

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

`rar_info` 是旧解析响应兼容字段，不是最终归档事实源，也不能驱动正式附件或最终导出。

**Scenario: 压缩包直接上传返回兼容文件信息**
- WHEN 用户直接上传 `.rar` 或 `.zip` 压缩包并解析成功
- THEN `rar_info` 包含该上传压缩包的实际文件名、MD5、`size_bytes` 和格式化大小

**Scenario: 文件夹解析不产生最终归档信息**
- WHEN 后端直接读取 `report_dir` 完成文件夹解析
- THEN `rar_info` 中的空值或零值仅为 legacy 兼容数据，不表示最终归档已完成
- AND `compress=false` 不能作为 `rar_info=null` 的可靠语义
- AND 最终归档文件名、大小和 MD5 只来自已验证的 `ArchiveManifest`

---

## CAP-009: 软件工具列表动态生成

### REQ-016: 按实际操作生成 software_tools

系统 MUST 根据报告来源和实际运行环境生成 `software_tools`。主软件名称和版本均为可靠候选时，列表包含主软件、WinRAR 和 Python hashlib；主软件名称或版本不完整时，不加入主软件工具，只保留 WinRAR 和 Python hashlib。主软件确认状态由 `inspection.primary_software` 和统一导出门控管理，不写死具体厂商或产品名称。

| 条件 | 名称 | 版本来源 |
|:---:|------|---------|
| 主软件名称和版本均为可靠候选 | 报告提供的主取证软件 | 报告来源字段及 provenance |
| 始终 | WinRAR压缩管理软件 | `detect_winrar_version()`；未检测到时版本为空并标记未确认 |
| 始终 | Python hashlib | `sys.version_info`（如 "3.11.0"） |

**Scenario: WinRAR 始终显示**
- WHEN 生成 software_tools
- THEN 始终包含"WinRAR压缩管理软件"
- AND 版本号为实际检测值；未检测到时不伪造默认版本
- AND 用户可在预览中修改版本号

**Scenario: Python hashlib 显示实际 Python 版本**
- WHEN 生成 software_tools
- THEN 包含"Python hashlib"，版本号为当前运行 Python 解释器的实际版本（如 "3.11.0"）

**Scenario: 主软件候选不完整时不加入主软件工具**
- WHEN 主软件名称或版本缺失，或尚未形成可靠候选
- THEN `software_tools` 不加入主软件工具
- AND 仍包含 WinRAR 和 Python hashlib
- AND `inspection.primary_software` 保留确认状态，由导出门控决定是否允许正式导出

---

## CAP-010: 附件1 电子数据提取固定清单自动填充

### REQ-017: 从最终 ArchiveManifest 生成提取清单

**Scenario: 归档完成后生成附件1**
- WHEN 独立归档执行完成且最终 `ArchiveManifest` 验证通过
- THEN `AttachmentPlan` 按 Manifest 中每个实际 part 生成一行数据：
  - 列结构固定为：序号、电子数据、来源、提取方式、文件MD5哈希值
  - 电子数据 = 实际 part 文件名
  - 来源 = 审核后的 `evidence_number` 去重并按顺序使用“、”拼接，最后追加“内提取”；同一来源文本供各 part 行使用，不声称每个 part 独立对应一个检材编号
  - 提取方式 = 使用 `inspection.hardware_device`；缺失时使用“取证设备”；生成当前固定的检查、报告、压缩和 MD5 描述
  - 文件MD5哈希值 = 该实际 part 的 MD5 哈希值
- AND Word 和附件3使用同一 Manifest，不从 `rar_info`、ArchivePlan 或目录扫描重新生成卷列表

**Scenario: 解析响应兼容字段不驱动附件1**
- WHEN 文件夹解析仅返回空值/零值 `rar_info`，或压缩包直传返回上传文件的兼容 `rar_info`
- THEN 这些解析响应字段均不作为正式附件1或最终导出的归档事实源
- AND 正式附件1只按已验证 `ArchiveManifest` 派生的 `AttachmentPlan` 生成

---

## CAP-011: 受控分卷归档与最终 Manifest

### REQ-018: 当前生产归档合同

- WinRAR 分卷档位固定为十进制 4GB、22GB、45GB；4GB 和 22GB 档预计超过 2 卷时升级，45GB 档最多 3 卷，输入超过 135GB 在执行前阻止。
- 初始执行后最多允许 2 次向上 replan。`volume_size_bytes` 是档位每卷上限，`size_bytes` 是 WinRAR 实际 part 文件大小。
- 每个 part 的 `disc_capacity_bytes` 必须只根据该 part 的 `size_bytes` 独立选择最小可容纳容量；不得继承 Manifest 档位值。
- 最终 `ArchiveManifest` 是 Word 正文、附件1和附件3归档字段的唯一事实源。

**Scenario: 真实验收边界**
- WHEN 判断当前归档生产验收状态
- THEN 4GB 双卷和 22GB 单卷真实执行已通过
- AND 22GB 双卷、45GB 真实执行和真实 replan 为延期，不是失败、取消或已完成
- AND 正式模板当前没有独立展示 `disc_capacity_bytes` 的位置，living spec 更新不改变 Word 布局

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
- **MUST**: 当前正式输出是 legacy DTO 管线；`template_filler_service.py` 是带最终 Manifest 的正式渲染路径，失败时不回退；officecli batch 只保留为无 Manifest 兼容回退
- **MUST**: 生成的 .docx 使用唯一正式模板 `word_templates/template.docx`（`current-template-v1` TemplateProfile）；渲染失败时必须明确报错，不得静默回退
- **MUST**: 基于 AGENTS.md 治理规则，Level 1 小修改无需 OpenSpec change；架构或公共合同变更仍需完整流程
- **MUST**: `rar_info` 是 ParseReportResponse 的旧兼容字段（`RarInfo | null`）；其 null/空值/零值不由 deprecated `compress` 参数可靠决定，也不代表最终归档状态
- **MUST**: 解压操作仅存在于 BE_Repository 层（`file_storage.py`）
- **MUST**: 软件工具列表由报告来源与运行环境共同生成；WinRAR 和 Python hashlib 始终显示，WinRAR 未检测到时不伪造默认版本，主软件候选不完整时保持未确认
- **MUST**: `entrust_time`（委托时间）使用中文格式（如 `2026年6月30日`），由 `format_time_chinese()` 转换
- **MUST**: legacy `InspectionResult.file_size` 在文件夹解析中只保留空值/零值兼容语义；压缩包直传的实际大小位于 `rar_info.size_bytes`，最终归档大小只以已验证 `ArchiveManifest.parts[].size_bytes` 为准
- **MUST**: 设备解析时优先结构化 JSON，再正则回退；扫描检材目录下各直接子目录（不限于 Base/），支持 `设备型号`、`信息/内容` 和 `c1/c2`
- **MUST**: DOCX 生成格式遵循项目模板/构建器定义的标准结构；自动化验证不替代人工视觉验收
