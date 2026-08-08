# Spec: 电子数据检查笔录自动生成

> 能力：CAP-001 ~ CAP-011
> 状态：MODIFIED（2026-08-01: Phase 1–4 workbench/archive contracts and archive-readiness reconciliation）

## Purpose

> 本文件是 living spec，只描述当前生产已经具备的能力。已批准但尚未正式输出启用的 Canonical/`DocumentRenderPlan` 目标见 active change `openspec/changes/extensible-report-template-platform/spec.md`；Shadow 已作为不改变Legacy响应的脱敏旁路接线，当前实现与验收进度见其 `tasks.md`。代码和测试是实现证据，不自动覆盖已批准的业务合同。

当前生产输出仍由 `InspectionReport` legacy DTO 管线生成：生产 Controller 校验最终 `ArchiveManifest`，将其投影到兼容 DTO，并以 `ArchiveManifest` + `AttachmentPlan` + 案件明确引用且当前重新校验通过的 approved TemplateProfile 渲染唯一正式 DOCX；没有模板引用的兼容案件继续使用 `current-template-v1`。Shadow 已接入解析、归档/预览和 Legacy DOCX 成功后的导出输入旁路，结果只通过受限脱敏诊断查询查看；Canonical 正式输出未启用，`DocumentRenderPlan` 尚无生产构造和消费。

当前生产事实：旧版报告与同厂商新版报告均识别后继续输出 Legacy DTO；解析和清缓存请求均有存活性治理；解析缓存只覆盖解析器实际依赖的数据；`ArchiveContext` metadata 使用有 TTL 和容量限制的快照。正式归档仍在生产路径执行完整 inventory、全量内容指纹、可读性、符号链接、路径越界及 Manifest/RAR 校验，缓存和快照不会降低这些安全边界。Shadow 的生产接线已完成，但真实样本差异治理尚未完成；Phase 1–4 最终集成人工验收已于 2026-07-31 通过，Canonical 正式生产切换未启用，OpenSpec archive 尚未执行。延期资源验收不阻塞 Shadow 差异治理或 Canonical 预切换开发与验证；它仍限制 Canonical 成为默认唯一正式输出和未声明的大规模能力。本变更的 Production Review 已记录当前 Legacy-only 单 Windows 支持模型下的发布负责人风险接受，因此当前只进入 archive-readiness reconciliation，不把延期资源验收写成已完成能力。

当前有两个必须区分的入口边界：持久化案件工作台是前端主生产入口，先持久化
CaseShell、SourceRecord 和解析任务，解析成功后保存 CaseDraft；用户审核和保存草稿后，
显式选择立即压缩或稍后压缩，工作台预览不会自动启动归档。后端 `/records/*` 继续作为
Legacy 兼容入口和唯一正式输出管线保留；兼容客户端可以继续使用其既有请求/响应合同，
但这不构成第二个工作台流程。

---

## Requirements

**CAP-001: HTML 报告上传与解析**

### Requirement: REQ-001: 提交受授权的本地报告目录

系统 MUST 满足以下现有合同：
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

#### Scenario: 工作台通过本机目录卡片登记并解析
- WHEN 用户在持久化案件工作台点击“上传报告目录”卡片
- THEN 后端在本地 Windows 交互桌面弹出原生文件夹选择窗口，取得用户选择的真实绝对路径
- AND 该路径只在后端传给既有来源登记和安全校验链路；前端不使用 `webkitdirectory` 上传或复制报告目录，也不要求路径位于桌面
- AND 后端先授权并持久化 CaseShell、SourceRecord 和解析任务，再异步解析目录以提取案件信息、设备信息、工具版本和数据分类统计
- AND 成功响应只返回案件/来源/任务摘要，不返回完整绝对路径
- AND 用户取消选择时不创建案件、来源或解析任务
- AND 解析成功后在同一案件上保存 CaseDraft，解析阶段不调用 WinRAR、不生成最终 `ArchiveManifest`
- AND 用户审核和保存草稿后显式选择立即压缩或稍后压缩；进入预览本身不启动归档

#### Scenario: Legacy 兼容入口解析本地报告目录
- WHEN 兼容客户端调用 `/records/*` 解析入口并以 `report_dir` 提交受授权目录
- THEN 后端继续按 Legacy 请求/响应合同读取和解析目录，并可返回 opaque `archive_context_id`
- AND 解析阶段不调用 WinRAR、不生成最终 `ArchiveManifest`
- AND 该兼容合同不改变工作台先持久化案件壳、再由用户显式决定压缩时机的流程

#### Scenario: deprecated compress 参数不控制解析归档
- WHEN 兼容请求传入任意 `compress` 值
- THEN 当前 UI 不暴露该参数，解析阶段无论其值为何均不调用 WinRAR
- AND `compress` 不决定解析成功后是否创建 `ArchiveContext`
- AND 该参数不能用来推断 `rar_info` 是否为 null 或归档是否完成

#### Scenario: 上传 .rar/.zip 压缩包（CAP-007）
- WHEN 用户通过文件选择器选择 .rar 或 .zip 文件上传
- THEN 后端解压到临时目录，解析内部 JSON 数据
- AND 直接计算上传文件的 MD5 和文件大小
- AND 跳过压缩步骤

#### Scenario: 缺少必需文件
- WHEN data/ 目录下缺少必需 JSON 文件
- THEN 返回 422 错误，明确提示缺少哪个文件

#### Scenario: 文件类型不支持
- WHEN 用户选择非 .rar/.zip 格式的文件
- THEN 前端阻止上传，提示"仅支持 .rar 和 .zip 格式"

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

#### Scenario: 旧新报告格式归一化
- **WHEN** 用户提交受支持的旧格式、新格式或明确可归一化的混合格式报告目录
- **THEN** 系统先完成稳定格式检测，再输出同一套 `InspectionReport` Legacy DTO
- **AND** 不改变现有审核页面、公共模型或 Word 导出入口

### Requirement: REQ-003: 解析设备信息

系统 MUST 满足以下现有合同：
#### Scenario: 从检材子目录提取设备详情
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

#### Scenario: 设备字段来源和 IMEI 优先级稳定
- **WHEN** 报告同时包含 `tb2`、结构化设备表和普通候选文本
- **THEN** 合法非空 IMEI1/IMEI2 优先使用 `tb2` 值，仅在缺失时使用结构明确的设备表补充
- **AND** 解析不得依赖具体文件名、任意 15 位数字或跨检材拼接

#### Scenario: 不支持结构安全失败
- **WHEN** 报告缺少核心结构或格式无法识别
- **THEN** 返回稳定结构错误，不生成伪造的标准报告或部分成功结果

### Requirement: REQ-004: 解析取证工具信息

系统 MUST 满足以下现有合同：
- WHEN 解析 data_report_info.json
- THEN 提取产品版本（如 FL-901V5 V3.2.12922）、平台版本、应用版本
- AND 返回版本信息供笔录填充

#### Scenario: 解析取证工具版本
- **WHEN** 解析受授权报告目录中的 `data_report_info.json`
- **THEN** 系统提取可确认的产品、平台和应用版本供当前笔录填充，无法确认的值保持未确认

---

**CAP-002: 笔录 Web 预览**

### Requirement: REQ-005: 生成笔录预览

系统 MUST 满足以下现有合同：
#### Scenario: 解析完成后展示完整笔录预览
- WHEN 解析完成
- THEN 系统将提取数据填入笔录模板，在页面上渲染完整笔录预览
- AND 预览包含所有章节：
  - 标题 + 文号
  - 一、绪论（一～九）
  - 二、检查（一～四）
  - 附件区域
  - 签名区
- AND 网页预览是可编辑的结构化内容展示，不承诺等同于最终 Word 的分页和版式渲染

#### Scenario: 缺失字段留空
- WHEN 某个字段无法从 HTML 报告中提取（如检查人员、检查地点）
- THEN 该字段在预览中显示为空白输入框，等待民警填写

#### Scenario: 按已确认检材类型显示设备标识
- WHEN 检材类型已由报告或用户确认为手机
- THEN 审核预览、检查过程和正式 Word 只显示该检材存在且合法的 IMEI1/IMEI2，不显示序列号
- WHEN 检材类型已由报告或用户确认为平板
- THEN 审核预览、检查过程和正式 Word 只显示该检材序列号，不显示 IMEI
- AND 原始解析字段继续保留，显示策略不得通过删除原始标识实现

#### Scenario: 工作台预览不自动启动归档
- WHEN 工作台案件已解析并进入审核或 Word 预览
- THEN 预览只使用当前 CaseDraft，不自动启动 WinRAR
- AND 用户选择“立即开始压缩”后才进入受控 Legacy 显式归档入口，选择“稍后压缩”时保持 `archive_deferred`

#### Scenario: Legacy 兼容入口生成并核对真实归档
- WHEN Legacy 兼容客户端的解析结果已建立 `ArchiveContext`、首个光盘编号有效且显式调用独立归档入口
- THEN 系统异步启动真实 WinRAR 归档，不阻塞其他报告字段的审核和编辑
- AND 归档区域按真实执行阶段显示等待开始、压缩中、完整性校验中、MD5计算中、已完成或失败
- AND 已完成时只展示 validated `ArchiveManifest.parts` 中每个实际 RAR 的文件名、精确字节数、可读大小、MD5、分卷序号、光盘容量、状态和独立下载入口
- AND 后端使用与 Word 相同的 Manifest→legacy附件投影生成附件1预览表格，前端显示每个 part 的文件名、审核后检材来源、当前固定提取方式和MD5；不得继续显示解析期空表或旧 `rar_info`
- AND WinRAR 不可用或归档失败时仍允许继续审核和编辑，但正式 Word 导出保持阻止

### Requirement: REQ-006: 检查过程自动生成

系统 MUST 满足以下现有合同：
#### Scenario: 按模板生成检查过程
- WHEN 系统生成检查过程章节
- THEN 按以下模板自动填充：
  - 步骤1: "将[设备型号]（IMEI1：[值]；IMEI2：[值]）编号为[检材编号]。"
  - 步骤2: "对检材[编号]进行拍照。"
  - 步骤3: "启动美亚FL-901手机取证塔，Windows 10 64位企业版操作系统启动正常，使用火绒安全软件（版本号为6.0.6.1）对取证塔进行杀毒，未发现病毒，完毕后退出火绒安全软件。"
  - 步骤4: "启动美亚手机大师-并行版V5软件（版本号为[版本号]）使用美亚手机大师-并行版V5软件对检材[编号]进行检查。"
- AND 设备型号/IMEI/编号/版本号从解析数据自动替换

---

**CAP-003: 全文在线编辑**

### Requirement: REQ-007: 任意字段可编辑

系统 MUST 满足以下现有合同。工作台编辑通过后端自动保存并携带草稿 revision；编辑会话使用心跳租约，连续无心跳达到既定超时后才允许用户确认接管。版本冲突、租约冲突和保存失败不得静默覆盖后端草稿。
#### Scenario: 工作台共享六项默认值
- WHEN 用户在工作台明确修改文号、检查地点、检查方法、检查硬件设备、有序检查人员快照或光盘编号前缀，并且当前草稿成功保存
- THEN 系统通过后端部署实例/本地操作者作用域的共享默认值事实源，稀疏更新本次明确修改的非空字段
- AND 六项范围不得扩大，未修改字段不进入共享 patch，空值不清除已保存的共享默认值
- AND 案件字段优先级为“当前案件用户手工修改 > Parser 非空真实解析值 > 非空共享默认值 > 系统默认值或空值”
- AND 后续新案件仅在 Parser 对应值为空、纯空格、缺失、空数组或 Parser 值为系统默认值时使用非空共享默认值，Parser 提取的真实非空值仍优先并保持 report 来源
- AND Parser 自动解析值不得进入共享 patch
- AND 已有案件不因共享默认值更新而被回写；案件、检材、设备标识和主软件等报告事实不受影响
- AND 后端持久化是工作台事实源，`localStorage` 仅可用于一次性导入/忽略旧值的兼容迁移，不是案件或共享默认值事实源
- AND 当前合同不宣称多用户隔离

#### Scenario: 新案件系统默认值让位于共享默认值
- WHEN 新案件 Parser 对文号、检查地点、检查方法或检查硬件设备返回系统默认值（如 `SYN-TEST〔2026〕000号`、`合成检验鉴定中心` 等）
- AND 部署实例存在对应非空共享默认值
- THEN 新案件使用非空共享默认值预填并标记 system_default 来源
- AND 无对应共享默认值时保留 Parser 的系统默认值
- AND Parser 提取的非默认真实值保持 report 来源优先

#### Scenario: 审核编辑界面不展示共享默认值设置
- WHEN 审核编辑界面（案件审核编辑页）渲染
- THEN 不展示“共享默认值设置”信息块（保存范围、当前默认光盘编号前缀、修改规则说明）
- AND 不展示“案件草稿/共享默认值”分别的保存状态行和页面级保存状态面板
- AND 不展示“请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。”警告提示
- AND 每次导出仍询问本次 Word 下载文件名（下载文件名询问功能保留）

#### Scenario: 点击字段进入编辑
- WHEN 民警在预览页面上点击任意文本字段
- THEN 该字段切换为可编辑状态（输入框/文本域）
- AND 修改后自动保存到当前会话

#### Scenario: 修改委托人
- WHEN 民警修改委托人字段
- THEN 预览实时更新显示新值

#### Scenario: 修改案件简要情况
- WHEN 民警编辑案件简要情况（自由文本）
- THEN 预览实时更新

#### Scenario: 修改检查设备硬件
- WHEN 民警从硬件下拉框选择不同设备
- THEN 检查设备章节自动更新

#### Scenario: 修改软件版本号
- WHEN 民警修改软件版本号
- THEN 检查过程和检查设备章节中的版本号同步更新

#### Scenario: 编辑保存和版本冲突
- WHEN 用户修改字段、顺序、来源状态或模板选择
- THEN 客户端去抖后通过后端保存并显示保存成功、冲突或失败
- AND 版本冲突不得静默覆盖后端草稿

#### Scenario: 同一案件互斥和接管
- WHEN 第二个会话打开仍有有效心跳的案件
- THEN 后端拒绝普通编辑
- WHEN 租约连续 2 分钟无心跳且用户确认强制接管
- THEN 后端记录旧 session、新 client、部署实例和时间并允许接管

#### Scenario: 服务重启使旧租约失效
- WHEN 服务重启后存在上一个部署实例创建的 active lease
- THEN 旧 session 不再被显示为有效编辑者，租约按恢复合同失效或进入 expired
- AND 新会话可以重新获取租约，不得被旧租约永久阻塞
- AND 强制接管仍记录旧 session、新 client、部署实例和时间的本地会话审计事件

#### Scenario: 双写部分失败不单独展示状态
- WHEN 当前草稿保存成功而共享默认值保存失败，或反向发生
- THEN 后端仍返回稳定的草稿与共享默认值分别保存结果，草稿保存、自动保存与 revision 冲突行为不变
- AND 审核编辑界面不单独展示共享默认值保存状态，也不因此改变草稿保存结果

#### Scenario: 人员拖拽同步两种顺序
- WHEN 用户拖拽当前案件检查人员卡片并保存
- THEN 当前案件 InspectorSnapshot 顺序变为 user 确认顺序
- AND 草稿保存成功后，共享默认人员顺序通过稀疏更新保存，并分别返回两种保存状态

#### Scenario: 新案件继承且已有案件不回写
- WHEN 后端已保存一个或多个非空共享默认值，随后创建新案件
- THEN 新案件仅在对应报告值缺失、为空或无法识别时优先使用这些共享默认值
- AND 更新共享默认值不得修改此前已创建案件的草稿或来源状态

#### Scenario: 旧 localStorage 迁移
- WHEN 浏览器存在旧默认值且部署实例尚无迁移决定
- THEN 系统提示导入或忽略，不得静默写入共享默认值
- AND 导入或忽略只能成功一次并记录本地会话审计信息
- AND 迁移完成前后，localStorage 均不得成为工作台事实源

#### Scenario: 有效报告值优先
- WHEN 报告提供有效非空值且共享默认值也存在
- THEN 案件使用报告值并设为 report 来源

#### Scenario: 报告值缺失或不可用
- WHEN 报告字段缺失、为空或无法识别且共享默认值有效
- THEN 案件使用共享默认值并设为 system_default 来源
- AND 两种来源都不可用时保留 pending 或待填写提示

#### Scenario: 用户修改来源迁移
- WHEN 用户修改 report 或 system_default 字段
- THEN 对应 FieldState.source 统一变为 user
- AND confirmation 按业务规则独立保留或转为 pending

### Requirement: REQ-008: 附件图片上传

系统 MUST 满足以下现有合同：
#### Scenario: 上传检材照片
- WHEN 民警在附件区域点击"添加照片"按钮
- THEN 弹出文件选择器，支持选择本地 .jpg/.png 图片文件
- AND 支持一次选择多张图片

#### Scenario: 预览和管理已上传照片
- WHEN 图片上传完成
- THEN 预览区展示已上传的缩略图列表
- AND 每张图片支持删除和拖拽排序

#### Scenario: 导出时图片嵌入 .docx
- WHEN 导出 .docx 时
- THEN 附件2使用显式 `MaterialPhotoGroup`，每组绑定一个检材及其两张图片
- AND Renderer 不得根据文件名或数组位置猜测检材归属
- AND 当前排版规则：一个检材组左右两张图片居中，两个检材组上下两组

#### Scenario: 上传成功后持久化并恢复
- WHEN 用户在有效编辑租约下上传合法 JPG/JPEG/PNG
- THEN 后端校验真实签名、扩展名、大小和案件配额，原子写入资产后返回 opaque 引用
- AND 只有上传成功的引用才进入 CaseDraft，刷新、切换案件或重启后端仍能读取同一图片

#### Scenario: 图片变更受租约和 revision 保护
- WHEN 用户替换或删除图片
- THEN 新资产成功写入后才替换旧引用，草稿使用 expected revision 保存，冲突不得静默覆盖另一会话
- AND 只读或失效租约不能上传、替换或删除图片，未引用资产按宽限期安全清理

#### Scenario: 图片读取失败阻止静默导出
- WHEN 草稿引用的图片缺失、损坏或不属于当前案件
- THEN 资产列表、预览或读取接口返回稳定可恢复错误，工作台提示重新上传
- AND Word 预览/导出不得静默生成缺图结果，正式模板和 Legacy 输出规则保持不变

---

**CAP-004: 导出 .docx**

### Requirement: REQ-009: 导出标准格式笔录

系统 MUST 满足以下现有合同。所有正式 Word、RAR 和 Manifest 继续由 Legacy 链路生成和验证；工作台案件不要求 Canonical 才能审核或导出，Shadow 比较不参与案件状态、进度、门控或正式产物。
#### Scenario: 确认无误后导出
- WHEN 民警点击"导出 Word"按钮
- THEN 生产 Controller 使用审核后的 `InspectionReport` legacy DTO 和已验证的最终 `ArchiveManifest` 构造 `AttachmentPlan`
- AND 工作台案件使用其明确引用且当前重新校验通过的 approved 模板版本生成 .docx；没有模板引用的 Legacy 兼容案件继续使用 `word_templates/template.docx` 和 `current-template-v1`
- AND 带 Manifest 的正式渲染失败时必须明确失败，不得静默回退到无 Manifest 的 officecli batch 输出
- AND 当前导出不构造或消费 `CanonicalInspectionCase`/`DocumentRenderPlan`
- AND 附件2区域按 `MaterialPhotoGroup` 显式绑定检材和图片，不根据文件名或数组位置猜测归属
- AND 文件文号格式为 "xx电检〔YYYY〕xx号"
- AND 自动触发浏览器下载

#### Scenario: 归档完成后统一导出到用户路径
- WHEN 案件进入归档完成态且民警点击「导出」
- THEN 系统提示用户选择导出路径，并把「最新编辑数据生成的 Word + 全部 RAR 文件 + HashMyFiles 校验 HTML」统一写入该路径
- AND 生产 Controller 使用审核后的 `InspectionReport` legacy DTO 和已验证的最终 `ArchiveManifest` 构造 `AttachmentPlan`
- AND Word 使用案件明确引用且当前重新校验通过的 approved 模板版本生成 .docx；带 Manifest 的正式渲染失败时必须明确失败，不得静默回退到无 Manifest 的 officecli batch 输出
- AND RAR 文件复用已验证的最终分卷；HashMyFiles 校验 HTML 由后端调用 HashMyFiles.exe 对导出 RAR 生成，与 RAR 一并写入导出路径

#### Scenario: 可重复导出且 Word 用最新编辑
- WHEN 案件已导出成功后民警再次导出
- THEN 系统重新打开导出路径选择，Word 用导出时刻的最新编辑数据重新生成，RAR 复用已验证分卷，HashMyFiles HTML 重新生成
- AND 导出成功不关闭审核编辑，民警可继续修改并再次导出

#### Scenario: 导出后仍可修改
- WHEN 导出完成后
- THEN 预览页面不关闭，民警可继续修改并再次导出

#### Scenario: 每次询问、取消和物理文件隔离
- WHEN 用户点击导出
- THEN 系统重新打开文件名输入框，默认值为文号加 `.docx`；文号为空时默认值为空
- AND 取消、空名称或非法 Windows 名称不创建任务或文件
- WHEN 用户输入合法名称
- THEN 下载名按输入补全 `.docx`，服务器物理文件使用唯一安全名且不覆盖正式产物

#### Scenario: Legacy 安全门控和 Shadow 边界
- WHEN 案件满足导出条件并开始正式输出
- THEN 继续执行完整 inventory、路径/链接/文件变化、WinRAR、完整性、MD5、Manifest 和 Word 门控
- AND 任一门控失败都不得发布正式导出成功状态
- AND 导出路径写入失败、磁盘不可写或文件被占用时明确报错，不标记已导出
- WHEN 本变更的案件、任务或模板流程运行
- THEN 不启动 Shadow 真实样本治理，不调用 Canonical 作为正式输入；未来比较只能在独立边界和明确开关下进行

#### Scenario: 日期字段保持纯日期精度
- **WHEN** 用户编辑委托时间或刻录时间
- **THEN** 控件只允许选择年月日，不显示或提交时间和秒
- **AND** 现有中文日期值能够回显，空值保持为空

#### Scenario: 检查时间范围保持分钟精度
- **WHEN** 用户编辑检查起止时间
- **THEN** 控件使用 24 小时制的分钟精度，不提供秒选择
- **AND** 选择结果转换回现有中文分钟范围格式，不改变后端字段名或 Word 映射

#### Scenario: 日期和时间校验阻止非法导出
- **WHEN** 用户输入不存在的日期、非闰年 2 月 29 日或结束时间早于开始时间
- **THEN** 导出被阻止并显示明确校验提示
- **AND** 不创建或下载无效 Word 文件

#### Scenario: VML 宿主段落和占位符保持完整
- **WHEN** 系统使用正式模板填充 Word 文档
- **THEN** 正文中的 `w:pict`、`v:shape`、`v:textbox` 和 `w:txbxContent` 宿主结构保持存在
- **AND** 占位符只在 VML 文本框子树内替换，不删除宿主段落

#### Scenario: 数据摘要和附件分页保持确定性
- **WHEN** 数据摘要为空、为 null 或仅包含空白，或附件区域包含 0、1、2 张图片
- **THEN** 数据摘要使用“即时通讯、手机信息”作为固定默认值
- **AND** 附件摘要、附件 1、附件 2、附件 3 按既定分页规则生成且不产生无意义空白页

#### Scenario: 使用当前正式模板填充报告
- **WHEN** 用户导出有效审核报告且 `word_templates/template.docx` 存在
- **THEN** 系统使用带占位符和列表块的正式模板填充报告
- **AND** 委托人数组、检材、检查人员、检查过程和提取清单按模板约定展开
- **AND** 模板填充失败时不返回伪成功空文件

#### Scenario: 模板缺失时保持兼容回退
- **WHEN** 正式模板不可用
- **THEN** 系统按既有兼容路径处理并明确报告结果
- **AND** 不改变现有 Legacy DTO、Word 字段映射和附件安全门控

---

**CAP-005: 硬件设备管理**

### Requirement: REQ-010: 硬件设备 CRUD

系统 MUST 满足以下现有合同：
#### Scenario: 查看设备列表
- WHEN 民警进入设备管理页面
- THEN 展示所有已配置的取证硬件设备（名称、型号、描述）

#### Scenario: 添加新设备
- WHEN 民警填写设备名称、型号并保存
- THEN 该设备出现在生成笔录的硬件下拉框中

#### Scenario: 删除设备
- WHEN 民警删除某个设备
- THEN 该设备从列表中移除，但不影响已生成的笔录

---

### Requirement: REQ-011: 解析缓存

系统 MUST 满足以下现有合同：
#### Scenario: 首次解析后缓存
- WHEN 首次解析某个报告目录成功
- THEN 将完整解析结果（InspectionReport + rar_info）保存为 JSON 缓存文件
- AND 缓存键由现有 Windows 路径规范化后的具体报告目录生成，同一目录不因大小写、尾部分隔符或 deprecated `compress` 参数产生重复记录
- AND 缓存文件使用不透明键保存于 `output/parsed/`，记录包含源内容指纹、`cache_version` 和 `last_accessed_at`，不保存供前端展示的绝对路径
- AND 缓存载荷中的 `cache_version` 当前为 `7`，用于隔离主软件及逐检材设备名称新解析语义
- AND 有效解析缓存最多保留 5 条，按 LRU 规则淘汰最久未使用记录，淘汰顺序在访问时间相同或并发写入时保持稳定

#### Scenario: 重复解析时复用缓存
- WHEN 再次请求解析相同的报告目录
- AND 规范化目录键相同、缓存版本相同且源内容指纹未变化
- THEN 直接返回缓存中的解析结果，跳过原始报告文件读取与解析
- AND 命中时更新该记录的 `last_accessed_at`，不新增重复记录
- AND 解析缓存与最终归档/Manifest 缓存彼此分离
- AND 缓存命中不会在解析阶段执行 WinRAR，也不会复用或伪造 WinRAR 结果

#### Scenario: 缓存失效
- WHEN 报告目录的源内容指纹变化、缓存损坏或缓存版本过期
- THEN 重新解析并更新缓存
- AND 无效记录在读取或淘汰时清除，不占用有效缓存上限

#### Scenario: LRU 淘汰
- WHEN 新建第 6 个不同报告目录的有效解析缓存
- THEN 删除 `last_accessed_at` 最早的一条记录，并保留最近使用的 5 条
- AND 淘汰只删除 `output/parsed/` 中的解析缓存文件，不调用归档文件删除逻辑

#### Scenario: 用户一键清空解析缓存
- WHEN 用户在阶段 1 主流程点击“清空解析缓存”并确认
- THEN 调用 `DELETE /api/v1/cache/report-parsing`，返回 `cleared_count`
- AND 清理中按钮禁止重复提交，成功、空缓存和失败均显示明确结果
- AND 清空后下次解析报告必须重新读取原始目录；当前页面已加载到前端内存的报告和编辑内容不要求立即清除
- AND 清空不删除 RAR、ArchiveManifest、归档下载文件、Word 导出、原始报告目录、默认设置或其他输出

#### Scenario: 同步文件操作不阻塞请求
- **WHEN** 用户发起报告解析或清空解析缓存请求
- **THEN** 同步文件系统工作在线程池或等价受控边界执行，不阻塞 FastAPI 事件循环
- **AND** 成功、业务错误和服务错误均结束请求并返回可处理结果

#### Scenario: 请求超时或 Abort 后恢复交互
- **WHEN** 解析或清缓存请求发生网络失败、超时或前端 Abort
- **THEN** 请求状态、按钮状态和错误提示恢复到可重试状态
- **AND** 不重复提交、不伪造清理数量，并保持解析缓存与归档生命周期隔离

### Requirement: REQ-012: 解析与最终归档分离

系统 MUST 满足以下现有合同：
#### Scenario: 工作台解析阶段不执行真实压缩
- WHEN 工作台报告目录登记成功并进入解析
- THEN 系统先持久化案件壳、来源绑定和解析任务，解析成功后保存 CaseDraft
- AND 解析、审核、草稿保存和预览均不自动调用 WinRAR，也不生成占位 Manifest
- AND 只有用户显式选择“立即开始压缩”后才进入受控 Legacy 显式归档入口；选择“稍后压缩”时持久化 `archive_deferred`

#### Scenario: Legacy 兼容解析建立归档上下文但不压缩
- WHEN `/records/*` Legacy 兼容入口解析报告目录，无论 deprecated `compress` 参数为何值
- THEN 解析阶段可以建立不透明 `archive_context_id`，但不调用 WinRAR、不生成占位 Manifest
- AND 真实归档仍需兼容客户端显式调用独立归档入口，不能由工作台预览动作隐式触发

#### Scenario: 预览归档与正式导出分离
- WHEN 预览阶段已生成 validated `ArchiveManifest`
- THEN 正式 Word 只消费该 Manifest，不再次调用 WinRAR
- AND Word 导出前和每个 part 下载前都重新校验同一物理文件的存在性、精确大小和完整 MD5
- AND 前端、Manifest、Word 与下载文件的文件名、字节数、MD5及分卷顺序必须一致

#### Scenario: 已验证 Manifest 的安全复用
- WHEN 同一归档上下文、输入目录快照、案件归档基础名和首光盘编号均未变化，且已有已验证 Manifest
- THEN 文书失败后的同次安全重试可以复用该归档结果而不重复执行 WinRAR
- AND 盘号后填或盘号修改不破坏 Manifest 复用（盘号从复用指纹中解耦）
- AND 新的导出请求仍重新验证实际 part 的存在性、大小和完整 MD5
- AND 不影响归档输入的普通表单字段和附件2照片编辑不使 Manifest 失效
- AND 重新解析案件、输入目录变化或案件归档基础名变化时旧 Manifest 必须失效
- AND 重新解析同一报告目录时，若原始输入内容指纹、归档审核指纹和已登记 Manifest 均未变化，且所有 RAR 分卷存在、大小和 MD5 校验有效，则允许跨新 archive context 复用已有 Manifest/RAR
- AND 若 RAR 缺失、大小变化或 MD5 不一致，禁止复用并重新生成归档；旧归档文件由独立归档生命周期策略处理
- AND 解析缓存被 LRU 淘汰或一键清空不会删除已验证 RAR、Manifest、当前页面下载或 Word 导出所需的运行时登记

#### Scenario: 稍后压缩可恢复
- WHEN 用户选择“稍后压缩”
- THEN 案件和草稿生命周期持久化为 `archive_deferred`，页面显示“暂未压缩”
- AND 刷新或后端重启后仍显示该状态，并可从案件操作区再次选择立即压缩

#### Scenario: 立即压缩保持受控 Legacy 边界
- WHEN 用户选择“立即开始压缩”
- THEN 后端校验 case/source/draft revision，创建唯一 attempt，持久化 workbench context 绑定并进入既有受控 Legacy/Archive Runtime 入口
- AND 不显示伪造进度；任务只按真实的 `workflow_milestone`、所有权、租约、完整性和 Manifest 门控推进
- AND 任一步准备失败时数据库状态全部回滚，不把案件标为成功

#### Scenario: 立即压缩在重启后必须重新确认
- WHEN 案件处于 `archive_queued` 或归档执行中，应用随后重启且尚无已验证正式产物
- THEN 案件生命周期转为 `archive_interrupted`，归档尝试标记为 `interrupted`
- AND 页面说明上次压缩未完成，旧运行时 handle 不恢复、不续跑、不自动生成新的压缩任务
- WHEN 用户重新进入案件并确认立即压缩
- THEN 后端先复核 SourceRecord，再生成新的 opaque 归档上下文和 attempt；旧 handle 的状态不能影响新尝试

#### Scenario: archive_interrupted 的可查看、编辑和退出路径
- WHEN 案件处于 `archive_interrupted`
- THEN 已存在的 CaseDraft 仍可查看和编辑，半成品 RAR、半成品 Manifest 和旧运行时 handle 不得作为正式产物、Word 输入或新尝试输入
- WHEN 用户选择“稍后压缩”并提交有效 revision
- THEN 案件允许转为 `archive_deferred`，不创建新的尝试，同时保留中断审计记录
- WHEN 用户重新确认来源并再次点击“立即压缩”
- THEN 后端原子接受新的 attempt 和归档上下文；失败时案件保持 `archive_interrupted`
- AND `archive_interrupted` 不得直接转为 `archiving`、`archive_verified`、`exporting_word` 或 `exported`

#### Scenario: 解析失败不询问压缩
- WHEN 目录解析失败
- THEN 案件卡片保留失败和重试入口，但不得返回或显示压缩时机询问

#### Scenario: 案件打开提供立即/稍后后台压缩选择
- WHEN 案件报告解析完成后用户打开案件
- THEN 系统提供「立即开始压缩」与「稍后压缩」两个选择，作为启动后台压缩的主触发入口
- AND 「立即开始压缩」创建受控后台归档任务，任务按 REQ-025 的固定里程碑与资源准入推进，不阻塞审核编辑
- AND 「稍后压缩」持久化 `archive_deferred`，页面显示「暂未压缩」，并从案件卡片操作区可再次启动压缩
- AND 解析失败时案件卡片保留失败与重试入口，不询问压缩时机

#### Scenario: 后台压缩不阻塞审核编辑
- WHEN 案件处于压缩执行中
- THEN 民警仍可查看、编辑并保存案件草稿，压缩在后台独立推进
- AND 审核编辑不改变已密封快照；压缩产物只由快照与归档计划决定，不因编辑中途变化
- AND 压缩、完整性、MD5 与 Manifest 各阶段完成状态实时反映在案件卡片上

---

**CAP-006: 废弃兼容参数边界**

### Requirement: REQ-013: deprecated compress 请求参数

系统 MUST 满足以下现有合同：
#### Scenario: 当前 UI 不提供压缩开关
- WHEN 用户通过当前页面提交本地报告目录
- THEN 页面不展示“压缩为 .rar”复选框，也不提供默认勾选或取消勾选操作
- AND 后端仅为旧请求兼容保留 `compress` 参数
- AND 任意参数值都不触发解析阶段压缩、不决定 `ArchiveContext` 创建，也不构成最终归档状态证据

---

**CAP-007: 压缩包直接上传**

### Requirement: REQ-014: Legacy 兼容入口上传 .rar/.zip 压缩包

系统 MUST 满足以下现有合同：
#### Scenario: 上传 .rar 文件并解析
- WHEN 用户通过文件选择器选择 .rar 文件上传
- THEN 后端接收文件，调用 WinRAR CLI 解压到临时目录
- AND 解析 JSON 数据，构建 InspectionReport
- AND 直接计算上传的 .rar 文件的 MD5 和文件大小
- AND 跳过压缩步骤

#### Scenario: 上传 .zip 文件并解析
- WHEN 用户选择 .zip 文件上传
- THEN 使用 Python zipfile 标准库解压

#### Scenario: 压缩包内缺少必需文件
- WHEN 解压后的 data/ 目录下缺少必需 JSON 文件
- THEN 返回 422 错误，明确提示缺少哪个文件

---

**CAP-008: 文件信息展示**

### Requirement: REQ-015: 展示 MD5 和文件大小

系统 MUST 满足以下现有合同：
`rar_info` 是旧解析响应兼容字段，不是最终归档事实源，也不能驱动正式附件或最终导出。

#### Scenario: 压缩包直接上传返回兼容文件信息
- WHEN 用户直接上传 `.rar` 或 `.zip` 压缩包并解析成功
- THEN `rar_info` 包含该上传压缩包的实际文件名、MD5、`size_bytes` 和格式化大小

#### Scenario: 文件夹解析不产生最终归档信息
- WHEN 后端直接读取 `report_dir` 完成文件夹解析
- THEN `rar_info` 中的空值或零值仅为 legacy 兼容数据，不表示最终归档已完成
- AND `compress=false` 不能作为 `rar_info=null` 的可靠语义
- AND 最终归档文件名、大小和 MD5 只来自已验证的 `ArchiveManifest`

---

**CAP-009: 软件工具列表动态生成**

### Requirement: REQ-016: 按实际操作生成 software_tools

系统 MUST 满足以下现有合同：
系统 MUST 根据报告来源和实际运行环境生成 `software_tools`。主软件名称和版本均为可靠候选时，列表包含主软件、WinRAR 和 HashMyFiles；主软件名称或版本不完整时，不加入主软件工具，只保留 WinRAR 和 HashMyFiles。主软件确认状态由 `inspection.primary_software` 和统一导出门控管理，不写死具体厂商或产品名称。
MD5 校验由 HashMyFiles.exe 执行，新解析案件的运行时工具条目显示 HashMyFiles；存量案件仍持久化旧值 Python hashlib，识别逻辑同时兼容两者（`python hashlib`/`python_hashlib` 与 `hashmyfiles`）。

| 条件 | 名称 | 版本来源 |
|:---:|------|---------|
| 主软件名称和版本均为可靠候选 | 报告提供的主取证软件 | 报告来源字段及 provenance |
| 始终 | WinRAR压缩管理软件 | `detect_winrar_version()`；未检测到时版本为空并标记未确认 |
| 始终（新解析案件） | HashMyFiles | 固定 `2.51`（HashMyFiles.exe 实际使用版本） |

#### Scenario: WinRAR 始终显示
- WHEN 生成 software_tools
- THEN 始终包含"WinRAR压缩管理软件"
- AND 版本号为实际检测值；未检测到时不伪造默认版本
- AND 用户可在预览中修改版本号

#### Scenario: HashMyFiles 显示实际校验工具版本
- WHEN 生成 software_tools
- THEN 包含"HashMyFiles"，版本号为 `2.51`（MD5 校验由 HashMyFiles.exe 执行）
- AND 存量案件报告仍保留 "Python hashlib"，不影响后续识别与导出

#### Scenario: 主软件候选不完整时不加入主软件工具
- WHEN 主软件名称或版本缺失，或尚未形成可靠候选
- THEN `software_tools` 不加入主软件工具
- AND 仍包含 WinRAR 和 HashMyFiles
- AND `inspection.primary_software` 保留确认状态，由导出门控决定是否允许正式导出

---

**CAP-010: 附件1 电子数据提取固定清单自动填充**

### Requirement: REQ-017: 从最终 ArchiveManifest 生成提取清单

系统 MUST 满足以下现有合同：
#### Scenario: 归档完成后生成附件1
- WHEN 独立归档执行完成且最终 `ArchiveManifest` 验证通过
- THEN `AttachmentPlan` 按 Manifest 中每个实际 part 生成一行数据：
  - 列结构固定为：序号、电子数据、来源、提取方式、文件MD5哈希值
  - 电子数据 = 实际 part 文件名
  - 来源 = 审核后的 `evidence_number` 去重并按顺序使用“、”拼接，最后追加“内提取”；同一来源文本供各 part 行使用，不声称每个 part 独立对应一个检材编号
  - 提取方式 = 使用 `inspection.hardware_device`；缺失时使用“取证设备”；生成当前固定的检查、报告、压缩和 MD5 描述
  - 文件MD5哈希值 = 该实际 part 的 MD5 哈希值
- AND Word 和附件3使用同一 Manifest，不从 `rar_info`、ArchivePlan 或目录扫描重新生成卷列表

#### Scenario: 每个 RAR 完成即回填并覆盖
- WHEN 后台压缩的某个 part 完成并通过完整性/MD5 校验
- THEN 后端立即将该 part 的文件名、文件大小和 MD5 写入案件记录的检查结果（`rar_filename`、`file_size`、`md5_hash` 对应位置）与附件1（`extract_list`）对应行，实时增量更新
- AND 自动值覆盖该字段的既有值（含手工编辑值）；来源列仍按审核后的 `evidence_number` 生成，提取方式使用 `inspection.hardware_device`，缺失时使用「取证设备」
- AND 未完成 part 对应位置保持未填写，不提前生成空行占位

#### Scenario: 解析响应兼容字段不驱动附件1
- WHEN 文件夹解析仅返回空值/零值 `rar_info`，或压缩包直传返回上传文件的兼容 `rar_info`
- THEN 这些解析响应字段均不作为正式附件1或最终导出的归档事实源
- AND 正式附件1只按已验证 `ArchiveManifest` 派生的 `AttachmentPlan` 生成

---

**CAP-011: 受控分卷归档与最终 Manifest**

### Requirement: REQ-018: 当前生产归档合同

系统 MUST 满足以下现有合同：
- WinRAR 分卷档位固定为十进制 4GB、22GB、45GB；4GB 和 22GB 档预计超过 2 卷时升级，45GB 档最多 3 卷，输入超过 135GB 在执行前阻止。
- 初始执行后最多允许 2 次向上 replan。`volume_size_bytes` 是档位每卷上限，`size_bytes` 是 WinRAR 实际 part 文件大小。
- 每个 part 的 `disc_capacity_bytes` 必须只根据该 part 的 `size_bytes` 独立选择最小可容纳容量；不得继承 Manifest 档位值。
- 每个 `VolumeSlot` MUST 有稳定身份、序号、计划版本和容量/输入范围；光盘编号默认由共享前缀连续生成，用户可修改完整编号但必须非空且在案件内唯一，允许不连续，刻录日期独立保存。
- replan 必须保留仍有效的人工槽位映射；新增槽位进入 pending，删除槽位清除映射，匹配不得依赖预计 RAR 文件名；最终以通过验证的 Manifest 槽位、卷序和光盘编号为准。
- 最终 `ArchiveManifest` 是 Word 正文、附件1和附件3归档字段的唯一事实源。
- RAR 外部基础名来自报告案件名称并清理 Windows 非法字符、结尾空格和点；单卷为 `<案件名>.rar`，多卷为 `<案件名>.partN.rar`。
- WinRAR 以原始报告目录的父目录为工作目录、以原始报告根文件夹名为输入；归档内部保留该根文件夹、全部相对目录、多级嵌套、同名文件和业务空目录，不包含绝对路径、盘符、staging、cache、UUID或项目输出路径。
- 每个 part 只能通过有效 `archive_context_id`、`manifest_id` 和不透明 `part_id` 下载；客户端不得提交服务器路径，下载前必须重新验证 Manifest 对应物理文件。

#### Scenario: 真实验收边界
- WHEN 判断当前归档生产验收状态
- THEN 4GB 双卷和 22GB 单卷已有部分脱敏真实证据，但不宣称全部档位验收完成
- AND 22GB 双卷、45GB 真实执行和真实 replan 为延期，不是失败、取消或已完成
- AND 正式模板当前没有独立展示 `disc_capacity_bytes` 的位置，living spec 更新不改变 Word 布局
- AND 4GB 双卷与 22GB 单卷只有部分脱敏真实证据，不宣称全部档位验收完成
- AND 22GB 双卷、45GB 真实执行和真实向上 replan 继续延期，不是失败、取消或完成
- AND 这些资源型验收不阻塞日常 Legacy/Shadow 功能开发、Shadow 真实样本差异治理或 Canonical 代码、只读预览、编辑门控、候选输出隔离和回滚演练
- AND 2026-07-31 D 盘隔离环境的真实浏览器复验使用小型纯合成输入，仅生成单卷 RAR；多分卷边界由 Harness/自动化覆盖，不宣称已完成多分卷人工视觉验收；原生 Word 视觉检查单独记录，不与浏览器验收混同
- AND 这些资源型验收仍阻塞 Canonical 成为默认唯一正式生产输出和 OpenSpec 归档，但不否定已完成的 Phase 1–4 最终集成人工验收
- AND 只有在有足够资源的验收机器上补测通过，或由发布负责人明确记录风险接受后，才可解除上述正式发布门槛

#### Scenario: 初始计划、编号和 replan
- WHEN 用户在压缩前查看或修改计划
- THEN 页面逐卷显示预计分卷和光盘编号，拒绝空值或重复值，允许非连续唯一值
- WHEN inventory 变化并 replan
- THEN 仍存在的槽位保留有效人工编号，新槽位待确认，删除槽位清除映射，匹配不依赖预计 RAR 文件名

#### Scenario: Manifest 验证收敛
- WHEN 归档完成并通过 Manifest 验证
- THEN 验证后的 Manifest 保存最终槽位、卷序和光盘编号并成为权威
- AND 草稿计划与 Manifest 不一致时阻止交付完成状态

---

### Requirement: REQ-019: 案件壳和多案件工作台可恢复

系统 MUST 在用户提交报告后立即分配稳定 `case_id`，创建案件壳和持久化解析任务。解析成功后才写入完整 Legacy `InspectionReport`；解析失败时保留失败任务卡片，但该记录不得成为可审核、可归档或可导出的正式草稿。案件名称与案件摘要独立，修改案件名称不得改变正式 RAR 基础名规则。

#### Scenario: 提交报告后立即创建案件壳
- WHEN 用户提交报告来源
- THEN 系统立即创建案件壳和解析任务，工作台显示排队或解析中卡片
- AND 案件壳在解析成功前不可审核、归档或导出

#### Scenario: 解析成功或失败
- WHEN 解析成功
- THEN 写入完整 Legacy `InspectionReport`、`SourceRecord` 引用和解析版本并转为可审核
- WHEN 解析失败
- THEN 保留失败卡片、结构化错误和重试入口，不生成正式草稿

#### Scenario: 刷新或重启后恢复
- WHEN 用户刷新浏览器或关闭软件后重新打开
- THEN 后端返回尚未清理的案件壳/草稿和任务状态
- AND CaseShell、CaseDraft、revision、案件生命周期、解析/归档决定、SourceRecord、图片资产引用和自动保存结果均以后端持久化状态为准
- AND `queued` 解析任务转为 `failed_retryable`，`running/cancelling` 解析任务转为 `interrupted`，用户显式重试前不得重新执行
- AND `review_ready` 案件不得因为重启而重复解析
- AND 重启前已选择或开始立即压缩的案件转为 `archive_interrupted`，不得保持虚假的 `archive_queued` 或运行中状态
- AND 重启前运行中的 WinRAR 任务不默认成功、不自动重连、不自动接管、不自动续跑

### Requirement: REQ-020: 字段来源和待确认状态可追踪

每个可编辑叶子字段、检材字段、人员项和附件图片组 MUST 有 `FieldState`，包含稳定字段路径、来源 `report | user | system_default`、确认状态 `confirmed | pending` 和 revision。纯派生不可编辑字段继承来源，不单独维护状态；来源颜色不得进入 Word，pending 必须有文字提示。

#### Scenario: 来源展示和导出隔离
- WHEN 字段来自报告、系统默认值或人工修改
- THEN 审核界面显示相应来源
- AND Word 使用正式黑字，不携带来源颜色

#### Scenario: 待确认不只靠颜色
- WHEN 检材、关键字段或图片组处于 pending
- THEN 页面显示待人工确认文字和影响范围
- AND 正式导出执行现有确认门控

### Requirement: REQ-021: SourceRecord 保护来源可访问性

系统 MUST 为每个工作台来源创建 `SourceRecord`。来源提交合同是本机报告目录路径而非 ZIP/RAR 或其他上传文件。后端 MUST 校验路径存在、是允许的目录类型、位于授权来源根、当前账户可访问且包含可识别报告结构，再保存 opaque `source_id`、允许根授权、`source_type`、`case_id/task_id` 绑定、metadata/fingerprint、访问状态和最近复核时间。绝对路径只能存在于受控后端 locator 中；API、卡片、草稿 DTO、任务 DTO、审计摘要、普通日志和 SQLite 公共字段不得暴露绝对路径；来源失效时必须要求重新选择目录。来源复核与归档决策前的来源可用性检查 MUST 使用元数据级指纹（相对路径 + 类型 + 大小 + mtime），不得在复核或请求路径读取源文件内容。

#### Scenario: 来源绑定和重启复核
- WHEN 用户提交经后端验证的报告目录并创建解析任务
- THEN SourceRecord 绑定案件壳和 task_id，并保存允许根授权及 metadata/fingerprint
- AND 递归 metadata/fingerprint 可先保持 pending 并由独立来源复核完成；快速解析按 `Legacy Parser → 草稿持久化 → review_ready` 顺序执行，不以完整复核阻塞审核入口
- AND 来源复核使用元数据级指纹（path/type/size/mtime），不读取文件内容，以消除大目录复核负载
- WHEN 服务重启或任务恢复前访问来源
- THEN 后端复核允许根、路径、权限、链接安全性和 fingerprint/metadata，并识别仍处于待复核的 SourceRecord
- AND 恢复事务不得把 pending 复核标记为可信或来源变化；应用启动后按 `source_id + revision` 去重调度复核
- AND 调度失败保持 pending，记录 `SOURCE_REVALIDATION_PENDING` 并允许后续启动或显式重试
- AND 已经 `review_ready` 的案件不得因恢复重复创建或执行 Parser
- AND 暂时 I/O、权限或资源不可用保持 pending，草稿可以查看和编辑；归档继续等待来源可信状态，Word 导出须显示明确风险确认
- AND 已确认的路径、允许根、链接安全性、报告结构、大小、mtime 或元数据指纹发生变化，或来源被替换/不可用时，才标记 `requires_reselection`，阻止归档并要求重新选择和重新解析
- AND 同尺寸且时间戳保持不变的原地内容改写不在元数据指纹门的检测范围内；归档执行仍对实际归档内容做完整性校验

#### Scenario: 来源风险不阻止 Word 导出
- WHEN SourceRecord 为 `available`
- THEN 工作台直接执行现有 Legacy Word 导出，不显示来源风险确认
- WHEN SourceRecord 为 `pending`
- THEN 导出动作显示来源复核尚未完成的可取消确认，用户确认后继续现有 Legacy 导出
- WHEN SourceRecord 为 `requires_reselection`
- THEN 显示来源已变化、不可用或需要重新选择的更强确认，用户确认后仍可继续现有 Legacy 导出
- AND 提示状态来自当前后端 CaseDetail，不使用 localStorage、不伪造 `available`
- AND Legacy `/records/export` 不因 SourceRecord 状态增加拒绝门控；来源可信状态仍严格约束归档

#### Scenario: 来源路径不对外泄露
- WHEN API 返回错误、任务进度或审计日志
- THEN 只使用 opaque ID、错误码和安全摘要
- AND 不包含绝对路径、原始文件名集合或完整来源 JSON

#### Scenario: 工作台拒绝上传文件和无效目录
- WHEN 工作台请求使用 ZIP、RAR、普通文件、不存在目录、越界目录、无权限目录或结构无效目录
- THEN 后端拒绝创建案件，并返回稳定原因码，不回显完整路径
- AND 不复制整个报告目录到上传目录，也不把报告内容或完整文件列表写入 SQLite 公共数据

### Requirement: REQ-022: Phase 1D 最小归档中断和产物保护

Phase 1D MUST 只在现有 Legacy `/records/archive` 显式入口外围记录一次归档尝试，不建设第二套发布事实源。归档尝试记录只用于识别重启前未完成的归档操作、证明自有 staging/进程资源归属、记录接受/完成/中断/失败/清理结果，以及支撑幂等恢复和正式产物保护；它不是新的公共输出链路，也不改变现有 Scheduler/Worker、进度、自动重试或正式 Manifest 合同。

受控工作台准备路径 MUST 将 attempt 绑定到 case、source ID、shell/draft revision、服务端 report fingerprint 和单向 context hash。正式完成 MUST 使用同一个可信证据服务处理正常执行和重启恢复；调用方提供的 Manifest ID 单独不能把 attempt 或案件变成 succeeded/verified。完成前必须验证 publish intent、Manifest index identity、public Manifest、source/draft 绑定和物理 RAR 内容。

发布 intent 只能在事务重新读取服务端 CaseShell、SourceRecord、CaseDraft 和 active workbench binding 后创建。正式目录身份绑定 Legacy executor 的正式 runtime context 和 Manifest ID，workbench context 仍是单向绑定权威。文件移动前必须再次执行相同 source/draft/report/context 校验；revision 或 source trust 改变必须阻止移动、索引登记和成功证据。

如果可信正式目录已存在而 intent 仍为 `intent_persisted`，恢复只能在验证 intent、attempt、case、source/draft/report identity、Manifest index 和物理 RAR 后按 `published`、`indexed` 顺序推进，不得直接跳到 indexed 或发布第二份资产。正常路径和恢复路径调用同一可信完成服务；该服务在写事务内重新读取 SourceRecord、CaseShell、CaseDraft，并要求 attempt、shell、draft 各恰好更新一行，零行更新时回滚全部状态。成功提交后但尚未写入最终 verified marker 的崩溃不得把 succeeded 降级为 interrupted。

恢复必须区分身份/完整性/目标冲突与临时 SQLite lock、index 不可用、文件锁和瞬时 I/O/权限错误。临时错误保留当前可恢复状态和证据，确认性冲突进入安全 conflict；不得以不完整证据发布成功。输入 snapshot、Manifest、index、marker 和正式目录的失败清理只处理已证明属于当前 attempt 的资源；未知资源不删除、不覆盖、不终止。

SourceRecord 目录 fingerprint MUST 使用规范化相对路径、条目类型、真实文件字节摘要和稳定排序集合。每个文件必须在打开句柄前后检查，并在摘要后重新扫描；任何变化、消失、新增、删除、临时访问错误或不一致都必须保持 pending/暂时不可验证，不得生成可信 available fingerprint。绝对路径和 metadata-only cache 不属于公共合同。

#### Scenario: 归档中断时保持可恢复且不发布半成品
- WHEN 归档执行在正式产物验证和可信完成提交前中断，或重启发现未完成归档尝试
- THEN 系统将未完成归档尝试和案件状态按既有恢复合同标记为 `interrupted`/`archive_interrupted`，不伪造 `succeeded`、`completed` 或 `100%`
- AND 未通过完整 Manifest/RAR、来源、所有权和绑定完整性门控的资产不得成为正式发布结果；可恢复状态和后续处理沿既有 deferred 或新 attempt 合同执行

### Requirement: REQ-023: 独立 Review 后的归档一致性、恢复与外部变更加固

归档发布、恢复和正式产物门控 MUST 继续使用完整不可变身份、owner/revision/lease/fence 和同一份 durable Manifest 证据，不得新增第二套发布事实源。发布 intent 的身份至少覆盖 case、attempt、source、source/draft revision、report fingerprint、source/input/archive fingerprint、Manifest/public Manifest、正式相对目录、context binding 和 fence；缺失或任一不一致 MUST 安全拒绝，完整相同的合法 intent 重入 MUST 幂等返回原记录。

应用停止达到有界等待上限时，属于本部署实例的 pending/running claim MUST 在 owner、attempt、task revision、lease 和 fence 条件仍成立时收敛为现有 `interrupted`/可恢复状态；不得把未完成工作标为 succeeded、completed 或 100%，不得改写其他部署实例的 claim。已经完成 durable 发布并通过可信完成门控的 attempt MUST 保持成功。重复停止、Worker 超时后的迟到返回和重启恢复 MUST 幂等。

归档执行 MUST 在执行开始、产物生成后和正式发布前重新确认源材料集合、条目类型、实际字节和关键元数据。文件增加、删除、替换、截断、同大小同时间戳内容变化或读取期间不稳定 MUST 使本次执行安全失败，不得发布混合源版本的 RAR、inventory 或 Manifest；失败不产生成功状态或可复用正式索引，重试必须重新建立源证据。

正式发布到索引、Manifest/MD5 确认和完成状态提交之间 MUST 继续核对同一 durable intent、fence、public Manifest、文件集合、顺序、字节数和摘要。正式卷、Manifest 或索引被替换、修改、删除、新增或重命名时 MUST 拒绝成功、复用、下载和 Word 导出；恢复遇到部分发布目录也不得直接提升为完成，不得删除或覆盖历史正式资产掩盖冲突。marker MUST 在 durable intent/fence 已建立且正式移动完成后才由明确发布所有者删除一次。

归档尝试内部状态为 `accepted | running | succeeded | failed | interrupted`，另有 `cleanup_status` 为 `not_required | pending | succeeded | failed | unknown`。恢复主要处理未完成的 accepted/running；已完成但停在 indexed 的 intent 只允许补写最终 verified，绝不把 succeeded 改回 interrupted。新的用户确认必须创建新的 attempt_id，不得复用旧记录。attempt_id、revision、PID、内部 staging locator 和 marker 摘要只能用于后端归属证明和诊断，API、DTO、错误和普通日志不得返回这些内部字段。

#### Scenario: 完整 intent 身份重入与冲突
- WHEN 同一合法发布 intent 使用完整相同身份重入
- THEN 系统返回原 durable intent 且不创建第二条记录
- WHEN 任一不可变身份字段缺失或不同，或历史 intent 被其他 attempt/fence 复用
- THEN 系统返回安全 conflict，不覆盖原 intent、不发布或标记成功

#### Scenario: 有界停止收敛本实例 claim
- WHEN shutdown 等待上限到达且本实例仍有 pending/running claim
- THEN claim 和 attempt 进入可恢复 interrupted 状态，未完成任务不显示成功或 100%
- AND 已可信完成的 attempt 保持 succeeded，其他实例 claim 不变，重复 shutdown/recovery 幂等

#### Scenario: 执行期间源材料变化
- WHEN 源文件在归档执行、产物生成或正式发布前被替换、删除、新增、截断或同大小同时间戳改写
- THEN 本次归档安全失败，不登记正式 Manifest 或成功状态，重试重新获取源证据

#### Scenario: 正式产物变化
- WHEN staging 或正式发布目录中的任一卷、Manifest 或索引在后续门控前被修改、替换、删除、新增或重命名
- THEN 系统拒绝完成、复用、下载和 Word 导出，不污染历史正式资产

#### Scenario: 重启后不自动接管归档资源
- WHEN 应用重启时存在未完成的 Legacy 归档尝试、WinRAR 进程或 staging
- THEN 归档尝试标记为 `interrupted`，案件进入 `archive_interrupted`，用户确认前不得重新执行
- AND 系统不得连接、等待、接管或自动终止无法证明属于本系统的 WinRAR 进程
- AND 系统不得仅凭目录名、PID、进程名或命令行片段认定 staging 或进程归属

#### Scenario: 自有 staging 的最低归属证明
- WHEN staging 位于应用控制的 staging 根，具有系统生成且不可猜测的 attempt_id，数据库或受控索引存在对应记录，且 ownership marker 与 attempt_id、部署实例和受控根匹配
- THEN 系统可以将未完成 staging 标记为隔离或执行安全清理
- AND 多次恢复或清理必须幂等，清理失败不得阻止案件、草稿、任务和图片资产恢复
- AND marker 格式和存储结构不得进入公共 DTO

#### Scenario: staging 归属证据缺失或冲突
- WHEN 任一最低归属证据缺失、记录冲突、marker 不匹配或无法确认
- THEN 资源一律视为未知，不删除、不终止相关进程、不覆盖
- AND 系统只记录不含绝对路径的安全诊断结果

#### Scenario: 半成品和正式产物隔离
- WHEN 重启或失败后发现未验证的 RAR 或 Manifest
- THEN 半成品 RAR 不进入正式产物索引，半成品 Manifest 不注册、不返回、不驱动 Word 导出
- AND 已完成并通过校验的 RAR、Manifest 和 Word 不因案件恢复或普通清理被删除

#### Scenario: 归档恢复不泄露路径
- WHEN API、DTO、错误响应、任务状态或普通日志返回归档恢复结果
- THEN 只返回 opaque ID、稳定错误码和安全摘要
- AND 不返回绝对路径、staging 物理路径、完整进程命令行或原始文件列表

### Requirement: REQ-024: 检材和人员顺序由案件权威数组驱动

检材默认排序 MUST 使用自然升序；编号重复或无法识别时保持报告原始相对顺序。用户拖拽后，案件数组成为审核界面、正文、附件摘要、附件 1、附件 2、附件 3 和 Word 的唯一顺序来源。人员卡片顺序同理，并同步更新共享默认人员顺序。

#### Scenario: 默认排序和拖拽一致性
- WHEN 编号全部可识别且互不重复
- THEN 按自然升序建立默认数组
- WHEN 编号重复或无法识别
- THEN 保持报告原始相对顺序
- WHEN 用户拖拽并保存
- THEN 正文、附件和 Word 使用同一有序数组，不得下游二次排序

### Requirement: REQ-025: 后台归档阶段里程碑和资源准入可恢复

解析任务可以并行；压缩任务最多 6 个 running，但不要求启动 6 个 WinRAR。调度器 MUST 综合配置化的磁盘空间、临时空间、CPU、IO、输入规模和当前进程数决定运行或排队。归档任务覆盖 inventory、规划、WinRAR、完整性、MD5、Manifest 生成和验证。

归档进度类型 MUST 固定为 `workflow_milestone`，使用单调的 `0/10/20/30/75/85/90/95/100` 里程碑；它表示真实工作流阶段，不表示 WinRAR 内部压缩字节百分比。TaskRecord 复用现有状态、阶段、percent、时间、错误和 cancel 字段，内部补充阶段、心跳、活动指标、worker 状态和后端权威 allowed_actions；公共案件卡片只返回安全摘要，不返回 Worker ID、内部租约、绝对路径、堆栈、技术日志、完整错误代码或完整进程信息。

资源快照的 `io_busy_percent` MUST 允许明确不可用状态。平台没有 `busy_time` 时仅跳过可选 I/O 忙碌阈值，继续执行空间、CPU、输入规模、WinRAR 进程数、并发、租约、所有权和其他门控；诊断必须有限、非刷屏且不含平台路径、堆栈或原始异常。

#### Scenario: 立即或稍后压缩及资源排队
- WHEN 报告解析成功
- THEN 系统询问立即开始或暂不压缩，暂不压缩不创建运行中的压缩进程
- WHEN 并发上限或资源准入不满足
- THEN 新任务排队并显示安全原因

#### Scenario: 可选磁盘 I/O 忙碌指标不可用
- WHEN 平台的 `disk_io_counters()` 返回 `None` 或合法返回对象不含 `busy_time`
- THEN 资源快照明确表达 I/O 忙碌指标不可用，不伪装成 `0%` 或精确百分比
- AND Scheduler 不因该可选指标永久失败或忙循环，仅跳过 I/O 忙碌阈值并继续执行其他资源、任务所有权和租约门控
- AND 存在 `busy_time` 的平台继续使用原有连续采样公式

#### Scenario: 真实阶段才推进固定里程碑
- WHEN 任务进入归档阶段
- THEN 后端只在真实阶段开始或门控成功时持久化对应的固定里程碑，并同时返回阶段文字
- AND 里程碑单调不下降，不读取 WinRAR CLI 连续百分比，不使用历史最大值、钳制、平滑、过滤、时间、文件/字节数量或输出大小制造中间百分比
- AND WinRAR 执行期间保持 30%；WinRAR 成功后才进入 75%，完整性通过后才进入 85%，MD5 和 Manifest 真实开始后才分别进入 90% 和 95%，完整 Manifest 验证及正式完成提交成功后才进入 100%

#### Scenario: WinRAR 长耗时阶段以真实活动摘要证明仍在运行
- WHEN 大文件归档长时间停留在创建 RAR 分卷阶段
- THEN 案件卡片主要显示归档阶段文字、阶段 X/N、indeterminate 活动态、已运行时间、任务状态、最近心跳、当前检测分卷数量和当前输出总字节数
- AND output_volume_count 只表示当前 attempt 受控 staging 中匹配分卷名规则的文件数量，output_bytes 只表示这些文件当前已写出的总字节数
- AND 两项活动指标不得换算为压缩完成比例；输出大小暂时不变化不得单独判定失败、卡死或触发自动取消

#### Scenario: Worker 心跳和所有权状态准确
- WHEN Worker 持有并执行当前归档任务
- THEN Worker 按受控频率更新 last_heartbeat_at，并节流写入聚合后的分卷数、输出字节数和 last_output_change_at
- AND 不得为每个文件系统变化事件写数据库
- WHEN Worker 未持有任务、正在恢复或等待接管
- THEN worker_state 和卡片文字准确显示未分配、恢复中或等待接管，不得显示仍在运行

#### Scenario: 失败取消和重启恢复最后阶段
- WHEN 归档任务失败、取消或被服务重启中断
- THEN 持久化任务状态、当前或失败阶段、最后里程碑、时间和安全错误信息
- AND 失败或取消不得进入 100%，半成品 RAR/Manifest 不得成为正式结果
- AND 页面刷新从 TaskRecord 恢复阶段、里程碑、时间、心跳、活动指标、Worker 状态、失败/取消和允许操作
- AND 服务重启先显示恢复中或等待接管；Worker 重新取得持久化任务所有权后才更新心跳并显示仍在运行
- AND 重新取得任务所有权不表示自动连接旧 WinRAR、复用旧半成品或断点续压

#### Scenario: 案件工作台卡片是主进度入口
- WHEN 用户打开案件工作台而未进入案件详情
- THEN 每张案件卡片直接显示该案件当前或最近一次归档任务安全摘要，包含案件信息、状态/阶段、活动摘要和主要操作
- AND 允许操作按状态表达取消、重试或查看结果；前端不得只显示数字百分比
- AND 创建 RAR 分卷阶段不得以静止 30% 进度条作为主要反馈，indeterminate 动画必须同时提供无障碍文字
- AND 不得以与案件卡片分离的归档任务卡片作为唯一入口

#### Scenario: 卡片内容随归档状态替换
- WHEN 案件尚未归档
- THEN 卡片显示未归档状态和归档入口，不显示空进度或空活动指标
- WHEN 任务等待执行、恢复中或等待 Worker 接管
- THEN 卡片显示等待/恢复文字和最后确认里程碑，不得显示仍在运行
- WHEN 任务正在执行
- THEN 卡片突出当前阶段，显示活动文字、已运行时间和取消操作
- WHEN 任务失败、取消或完成
- THEN 卡片分别显示安全失败摘要、取消时阶段或完成信息和查看结果操作；完成后不再显示心跳、Worker 状态或动态动画

#### Scenario: 默认卡片不展开技术详情
- WHEN 当前或历史归档任务包含完整阶段时间线、逐卷文件名/大小/MD5、Manifest 路径/内容、Worker ID、内部租约、精确心跳时间戳、完整错误代码、堆栈、技术日志、重试/调度诊断或进程信息
- THEN 默认案件卡片不平铺这些字段，只提供归档详情或查看结果入口
- AND 案件列表 API 不返回绝对路径、堆栈、Worker ID、内部租约或完整技术日志

#### Scenario: 卡片响应式和无障碍
- WHEN 卡片处于窄屏、长文号、长失败摘要或大数字场景
- THEN 次要活动指标可以隐藏或收起，但案件信息、状态、阶段文字和主要操作必须保留
- AND 成功、失败、取消和运行中状态不得只依赖颜色；减少动态效果时仍通过文字得知当前阶段或恢复状态

#### Scenario: 重启中断而非自动接管
- WHEN 服务重启时存在 running 任务或 WinRAR 进程
- THEN 任务标记为 interrupted 或 failed_retryable
- AND 只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，不信任或发布半成品 RAR/Manifest
- AND 用户确认后重新执行，不实现断点续压或 WinRAR 重连

### Requirement: REQ-026: WinRAR 进度策略决策保留 Legacy 安全边界

Phase 3 开始前 MUST 完成 WinRAR 进度能力 spike 和明确产品/架构决策。RAR 5.90、RAR 7.23 普通 pipe 及 RAR 7.23 ConPTY 的合成实验已经证明 CLI 百分比混合不同作用域且可重复回退。当前合同不读取连续 WinRAR 百分比，而使用 `workflow_milestone`；现有 WinRAR、RAR 分卷、Legacy 显式压缩、inventory、路径/变化、完整性、MD5、Manifest、Word 和发布门控保持不变。

#### Scenario: 失败 spike 形成明确适配决定
- WHEN 普通 pipe 和 ConPTY spike 均证明 WinRAR CLI 百分比不可作为稳定总进度
- THEN 产品/架构决定采用固定 workflow_milestone，并允许按任务顺序实现后台归档能力
- AND spike 文档和合成测试继续作为放弃连续 CLI 百分比的证据
- AND 该决定本身不表示其他后台任务或 Phase 3 人工验收自动完成

#### Scenario: 里程碑适配不削弱 Legacy
- WHEN 后台任务包装现有归档执行
- THEN WinRAR 运行期间只报告正在创建 RAR 分卷的阶段里程碑和活动状态
- AND 不解析或推断内部连续百分比，不改变 RAR 分卷或基础名规则
- AND 任一既有正式安全门控失败时不得推进到后续里程碑或正式完成

### Requirement: REQ-027: 预置模板版本可复现且切换不触发归档

系统只允许选择已注册且审核通过的模板版本。每个版本 MUST 有独立模板 ID、版本号、指纹、校验规则和验收记录。案件保存所选模板及版本。审核编辑界面不提供案件 Word 模板选择器；案件模板在创建/解析时确定并保持，导出前重新校验案件引用的模板。

#### Scenario: 审核编辑界面不展示模板选择器
- WHEN 审核编辑界面（案件审核编辑页）渲染
- THEN 不展示“案件 Word 模板”选择块（已审核模板版本下拉、已审核标签、模板 ID/版本/验收摘要、应用模板版本按钮）
- AND 案件保留创建时保存的模板 ID 和版本（template_ref）
- AND 没有模板引用的兼容案件继续使用 `current-template-v1`

#### Scenario: 模板注册与管理保持可用
- WHEN 管理员在模板管理页注册、审核或删除模板版本
- THEN 既有模板注册、审核、删除保护、案件引用保护与默认值行为保持可用
- AND 审核编辑界面不提供按案件切换模板入口

#### Scenario: 导出前重新校验案件引用模板
- WHEN 案件导出 Word
- THEN 后端按案件引用的模板 ID、版本、指纹和规则重新校验并执行现有 VML、分页、表格、附件和 Word 安全门控
- AND 校验失败时不发布 Word

### Requirement: REQ-028: 无登录环境的审计身份不冒充认证身份

强制接管、默认值迁移、共享默认值修改和重要任务操作 MUST 记录 client instance ID、session ID、可选本地显示名称、部署实例和时间。系统不得把这些字段描述为真实人员身份或认证结果。

#### Scenario: 记录接管和默认值操作
- WHEN 用户确认接管、导入/忽略旧默认值或修改共享默认值
- THEN 审计记录保存上述无认证身份字段集合
- AND 界面显示为本地会话审计，不显示已认证人员

### Requirement: REQ-029: 案件工作台承接完整生成笔录能力

案件工作台 MUST 是电子检查笔录的主生产入口，使用既有 Legacy `InspectionReport` 字段合同、校验规则、日期时间处理、附件模型、预览投影和 Word 导出映射。工作台可以重组布局并增加案件状态、自动保存、租约、来源和多案件控制，但不得维护简化的第二编辑器。后端 `/records/*` 保留为 Legacy 兼容入口和唯一正式 Legacy 输出管线，不构成第二个持久化工作台流程。

#### Scenario: 完整审核编辑器
- WHEN 案件达到 `review_ready`
- THEN 工作台暴露全部 Legacy 审核字段、数据摘要、附件信息、图片编辑、必填/格式校验、预览、正式 Word 导出和自定义下载名称
- AND CaseDraft、revision 和编辑租约仍是工作台写入权威

#### Scenario: 统一入口和兼容路由
- WHEN 用户打开旧前端生成 URL
- THEN URL 引导到工作台，不暴露竞争性的上传/编辑流程
- AND 后端 `/records/*` 兼容合同、Legacy Parser、Word、Manifest 和正式归档安全门控保持可用

#### Scenario: 工作台预览不自动归档
- WHEN 工作台已持久化 CaseShell、SourceRecord 和解析任务，并在解析成功后保存 CaseDraft
- THEN 用户可以审核和保存草稿，预览动作本身不得启动 WinRAR 或创建归档任务
- AND 只有用户显式选择“立即开始压缩”后才进入受控 Legacy/Archive Runtime 入口
- AND 用户选择“稍后压缩”时持久化 `archive_deferred`，不启动归档

#### Scenario: 完整能力不退化工作台优化
- WHEN 用户切换案件、刷新、失去租约或收到来源警告
- THEN 工作台保留案件卡片状态、自动保存结果、只读警告、来源状态、重试和返回列表体验
- AND 不重新引入旧页面的混合归档上传流程或重复字段、校验、附件和导出规则

#### Scenario: 上传入口在案件网格中跟随案件
- WHEN 案件工作台当前页没有任何案件
- THEN 网格内只显示“上传报告目录”卡片，不显示案件卡片
- WHEN 当前页有一个案件
- THEN “上传报告目录”卡片显示在该案件卡片的右侧同一行
- WHEN 当前页有 k 个案件（k ≥ 1）
- THEN “上传报告目录”卡片显示在第 k 个案件卡片之后的下一个网格位置
- AND 该入口不占用网格上方工具条的位置

#### Scenario: 满页隐藏上传入口
- WHEN 案件工作台当前页已显示满 2 行共 6 个案件
- THEN 当前页不显示“上传报告目录”卡片
- AND 案件仍按每页最多 6 个分页展示

#### Scenario: 空页仅显示上传入口
- WHEN 案件工作台当前页没有案件
- THEN 页面不展示空态插图或空态提示组件
- AND 网格内仅呈现“上传报告目录”卡片作为登记入口

#### Scenario: 不提供手动案件名称/编号输入
- WHEN 用户登记报告目录
- THEN 案件名称和案件编号不得通过手动输入框提供，登记请求携带空名称与空编号
- AND 解析成功后服务端用报告内容解析出的案件名称/编号/摘要仅填补空白的案件标签
- AND 案件卡片在解析完成前以兜底文案展示案件名称

#### Scenario: 案件前端不展示 Demo 就绪状态
- **WHEN** 用户进入电子数据检查入口或案件工作台
- **THEN** 页面不展示“Demo 环境就绪状态”区域
- **AND** 页面不展示后端、WinRAR、归档输出根三项就绪状态
- **AND** 页面不因该展示发起 Demo 就绪接口请求

#### Scenario: 案件删除先确认后执行
- **WHEN** 用户点击案件卡片的“删除”操作
- **THEN** 页面弹出标题为“确认删除吗？”的确认提示
- **WHEN** 用户点击“确认”
- **THEN** 前端调用对应案件的 DELETE API，服务端真实删除该案件的工作台业务记录
- **AND** 删除成功后案件不再出现在工作台列表中

#### Scenario: 取消案件删除
- **WHEN** 删除确认提示已经打开
- **AND** 用户点击“取消”或关闭提示
- **THEN** 不调用删除 API，案件和工作台列表保持不变

#### Scenario: 用户确认后任意案件状态均可删除
- **WHEN** 用户确认删除
- **AND** 案件处于解析失败、归档中断、归档完成、正式导出、处理中、清理中或已完成清理等任一状态
- **THEN** 服务端均执行删除，不因任务、租约、工作状态、清理流程或正式产物存在而拒绝
- **AND** 删除平台受控的归档压缩目录及其中产物删除后留下的空案件上级目录、Manifest 索引记录、正式 Word 文件、归档快照、临时文件和案件图片
- **AND** 仅删除确认案件对应且为空的上级目录；包含其他案件或其他文件的目录必须保留
- **AND** 保留案件来源目录等不由平台拥有的外部文件
- **AND** 自动保留清理流程的正式产物保护规则不改变；本场景是用户在工作台确认后的显式删除

#### Scenario: 统一平台外壳和父子导航
- **WHEN** 用户进入首页、电子数据检查模块、生成笔录或设备管理页面
- **THEN** 页面使用同一个 `PlatformShell`
- **AND** 电子数据检查笔录是一级入口，生成笔录和设备管理是其二级入口
- **AND** 旧 `/generate` 和 `/devices` 地址通过路由重定向并保留可用查询参数和 hash

#### Scenario: 电子数据检查入口默认进入案件工作台
- **WHEN** 用户访问 `/electronic-inspection`、点击平台总首页的电子数据检查入口或点击侧栏一级“电子数据检查笔录”
- **THEN** 系统进入 `/electronic-inspection/workbench`
- **AND** 直接访问 `/electronic-inspection` 时保留查询参数和 hash
- **AND** 平台总首页及电子数据检查下的其他二级功能保持可用
- **AND** 系统不再展示独立的电子数据检查模块首页

#### Scenario: 案件工作台提供紧凑的来源目录校验控制项
- **WHEN** 用户进入案件工作台
- **THEN** 页面标题区右上角显示紧凑的来源目录校验控制项
- **AND** 用户可以在该处开启或关闭来源目录授权校验
- **AND** 选择结果继续使用既有浏览器持久化偏好，并用于后续首次登记和重新登记请求
- **AND** 刷新、上传目录、分页和案件卡片操作保持可用

#### Scenario: 审核编辑页保留真实交互语义
- **WHEN** 用户进入审核编辑页
- **THEN** 页面显示真实案件摘要、当前步骤、待核对提示、保存状态和结构摘要 Drawer
- **AND** `Esc`、`Ctrl+S`、底部操作栏和重复操作保护只触发已实现的当前页面行为，不伪造服务器保存或 Word 最终版式

### Requirement: REQ-030: 盘号后填与顺序映射

首个光盘编号可在压缩前或压缩后输入，系统按 part 顺序生成全序列并一一映射到各 RAR。

#### Scenario: 压缩前未填盘号仍可压缩
- WHEN 用户未填写首个光盘编号即启动压缩
- THEN 系统仍按固定体积分卷执行压缩，压缩阶段不因缺少盘号失败
- AND 案件进入「待补盘号」中间态，卡片显示未填盘号提示并提供补填入口

#### Scenario: 压缩后输入首个盘号自动映射
- WHEN 压缩完成后用户输入首个光盘编号
- THEN 系统校验盘号格式与日期（`GPyyyyMMdd-序号`），按 part 顺序自动生成全序列并一一映射到各 RAR
- AND 映射结果持久化，案件从「待补盘号」转为「归档完成」候选
- AND 盘号仍可按 REQ-018 约定在案件内唯一前提下由用户修改，允许不连续，刻录日期独立保存

#### Scenario: 压缩前已填盘号保持现行为
- WHEN 用户压缩前已填写首个光盘编号
- THEN 系统按现行为在计划阶段生成预计盘号序列，压缩完成后按 part 顺序映射
- AND 后填与先填两种路径最终得到一致的 RAR↔盘号 一一对应关系

### Requirement: REQ-031: 归档完成与已导出状态机

归档完成态、导出路径提示、已导出标记与彻底删除。

#### Scenario: 全部对应完成后进入归档完成态
- WHEN 全部 RAR 完成、全部 MD5 计算完成且所有盘号映射完成
- THEN 案件进入「归档完成」状态
- AND 系统提示用户输入导出路径；提示只在盘号补齐后出现，未补齐时保持「待补盘号」

#### Scenario: 导出成功后标记已导出
- WHEN 统一导出写入用户路径成功
- THEN 案件卡片标记为「已导出」
- AND 导出成功后仍可再次导出（可重复），卡片提供「彻底删除」按钮

#### Scenario: 彻底删除仅删平台内产物
- WHEN 已导出案件执行「彻底删除」
- THEN 复用 `case-workbench-delete` 能力，确认后删除案件记录及平台内受控产物（解析缓存、归档快照、压缩 RAR、导出记录）
- AND 用户导出路径下的外部副本不被删除；外部原始资料目录不属于平台删除范围

### Requirement: REQ-ARCHIVE-IMMUTABLE-INPUT

The archive execution input MUST be a task/attempt/deployment-bound sealed snapshot; mutable source bytes MUST NOT be used as the execution or publication authority.

#### Scenario: sealed execution input
- WHEN a task begins archive execution
- THEN the service creates a task/attempt/deployment-bound snapshot under the controlled output root, copies the complete authorized inventory in parallel (default 4 workers, `BIJI_ARCHIVE_COPY_WORKERS`-configurable) without following links or reparse points, verifies every relative path, size and modified-time metadata, and durably marks it `sealed`
- AND file content is flushed to the OS but not per-file fsynced at copy time; the snapshot directory rename, owner marker and file-list metadata remain durably persisted
- AND content not yet written back at power loss can leave partial or zero-filled bytes, which size-based metadata verification catches when truncated and archive-output RAR validation plus crash-retry rebuild from source cover otherwise
- AND the snapshot manifest records per-file relative path, size and modified-time metadata, not per-file content SHA-256
- AND WinRAR, inventory, RAR validation and Manifest generation read only the sealed snapshot, never the mutable source directory
- AND an unsealed, missing, owner-mismatched, incomplete or metadata-mismatched snapshot cannot enter WinRAR, publication, reuse or success
- AND source changes after sealing cannot change the bytes read by this attempt; failure, cancellation, crash and retry never reuse a prior attempt snapshot

### Requirement: REQ-ARCHIVE-PUBLICATION-GENERATION

Formal publication MUST use a unique durable publication generation bound to the task, attempt, deployment, fence, Manifest and exact physical file set; partial or tampered generations MUST fail closed.

#### Scenario: durable publication generation
- WHEN a validated staging set is published
- THEN a unique `publication_id` and generation digest bind task, attempt, deployment, fence, Manifest, exact file set, sizes and MD5 values in the durable publish intent
- AND the staging set is sealed before same-filesystem atomic rename, historical formal directories are never overwritten, and a partial/crashed generation remains pending or recoverable rather than succeeded
- AND the completion transaction can set attempt and task to `succeeded` only when the sealed publication identity, intent/fence, current revisions, Manifest and index projection agree
- AND download, reuse, recovery and Word export resolve the durable publication identity and re-run the existing physical integrity gate; post-completion tampering is rejected

### Requirement: REQ-ARCHIVE-MANIFEST-PROJECTION

The JSON Manifest index MUST remain a rebuildable projection of SQLite durable publication facts and MUST NOT be treated as an independent success authority.

#### Scenario: fail-closed derived index
- WHEN the JSON Manifest index is missing, malformed, structurally invalid, digest-inconsistent or concurrently updated
- THEN it is never interpreted as an empty authoritative list
- AND SQLite durable publication facts are the only authority and may rebuild the projection under a cross-process lock with temp-file flush/fsync and atomic replacement
- AND if the projection cannot be rebuilt or persisted, public completion cannot report success

### Requirement: REQ-ARCHIVE-OWNERSHIP-CAS

Shutdown and recovery MUST use bounded compare-and-set ownership checks for task revision, deployment owner, worker owner, attempt and fence before changing claims or deleting markers.

#### Scenario: current claim shutdown and marker ownership
- WHEN bounded shutdown or recovery handles a pending/running archive claim
- THEN it re-reads current durable revision, deployment owner, worker owner token, attempt and fence, and performs bounded CAS only while the current claim remains owned and interruptible
- AND revision races are retried or reported as unresolved, never silently ignored; transferred ownership and durable succeeded facts are not downgraded
- AND staging markers serialize task, attempt, deployment, controlled root and random token; their fence binding is established by cross-checking the durable intent `fence_id` and current DB fence before deletion, and only the matching publisher deletes once after durable intent/fence and formal move; an already-deleted marker for the same publication is idempotent success

---

## 存储路径

| 用途 | 路径 |
|------|------|
| 解析缓存 | `output/parsed/`（本地，不得进入 Git） |
| 归档文件 | `output/compressed/`（本地，不得进入 Git） |
| 归档登记索引 | `output/compressed/.archive-manifest-index.json`（本地，不得进入 Git；与解析缓存独立） |
| 导出 .docx | `output/exports/`（本地，不得进入 Git） |
| 硬件设备配置 | `packages/backend/app/data/hardware_devices.json` |

## 跨功能约束

- **MUST**: API 响应字段名用 camelCase，Python 内部用 snake_case，Controller 层做转换
- **MUST**: 当前正式输出是 legacy DTO 管线；`template_filler_service.py` 是带最终 Manifest 的正式渲染路径，失败时不回退；officecli batch 只保留为无 Manifest 兼容回退
- **MUST**: 生成的 .docx 使用案件明确引用且当前重新校验通过的 approved 模板版本；没有模板引用的 Legacy 兼容案件使用 `word_templates/template.docx`（`current-template-v1` TemplateProfile）；渲染失败时必须明确报错，不得静默切换版本或回退
- **MUST**: 基于 AGENTS.md 治理规则，Level 1 小修改无需 OpenSpec change；架构或公共合同变更仍需完整流程
- **MUST**: `rar_info` 是 ParseReportResponse 的旧兼容字段（`RarInfo | null`）；其 null/空值/零值不由 deprecated `compress` 参数可靠决定，也不代表最终归档状态
- **MUST**: 解压操作仅存在于 BE_Repository 层（`file_storage.py`）
- **MUST**: 软件工具列表由报告来源与运行环境共同生成；新解析案件 WinRAR 和 HashMyFiles 始终显示（存量案件保留 Python hashlib），WinRAR 未检测到时不伪造默认版本，主软件候选不完整时保持未确认
- **MUST**: 主软件只从 `data_report_info.json.contents[].value` 的明确主产品句式绑定名称和紧随其后的版本；括号可属于主名称，后续“子模块/插件/组件”的名称和版本不得覆盖主字段
- **MUST**: `entrust_time`（委托时间）使用中文格式（如 `2026年6月30日`），由 `format_time_chinese()` 转换
- **MUST**: legacy `InspectionResult.file_size` 在文件夹解析中只保留空值/零值兼容语义；压缩包直传的实际大小位于 `rar_info.size_bytes`，最终归档大小只以已验证 `ArchiveManifest.parts[].size_bytes` 为准
- **MUST**: 设备解析时优先结构化 JSON，再正则回退；按检材分别读取手机品牌及手机型号/设备型号，以单个空格生成设备名称，型号已含品牌时不重复；“手机”只作为检材类型，品牌和型号均缺失时才参与兜底
- **MUST**: 当前模板附件2中同一检材的两张照片固定在同一表格行的左右两个槽位，单元格边距为零并分别向中间对齐；保持图片比例且不修改正式模板资产
- **MUST**: DOCX 生成格式遵循项目模板/构建器定义的标准结构；自动化验证不替代人工视觉验收
- **MUST**: SQLite 只保存案件业务 DTO、任务/租约/revision/索引元数据、SourceRecord 和 opaque 资产引用；图片、来源快照、缓存、临时文件和正式产物保存在受控文件系统资产中，不写入 Base64、完整 HTML、原始 JSON 集合或不可控二进制
