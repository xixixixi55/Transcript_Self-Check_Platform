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
| 创建时间 | contents[tp=创建时间] | 一(七) 检查开始时间 |
| 报告时间 | contents[tp=报告时间] | 一(七) 检查结束时间 |

#### Scenario: 解析案件字段供当前笔录使用
- **WHEN** 解析受授权报告目录中的 `data_case_info.json`
- **THEN** 系统提取表中字段并填入当前 `InspectionReport`/`CaseDraft`，无法确认的字段保持为空，不伪造案件事实

#### Scenario: 新案件委托时间默认留空并提示选择
- **WHEN** 系统完成报告解析并首次初始化新案件草稿
- **THEN** `introduction.entrust_time` 保持为空且字段处于待确认状态
- **AND** 审核页面在日期控件附近提示用户选择委托日期

#### Scenario: 报告创建时间不作为委托时间
- **WHEN** 报告 `data_case_info.json` 包含“创建时间”或旧委托时间种子
- **THEN** 系统 MUST NOT 将报告“创建时间”或旧种子写入 `introduction.entrust_time`
- **AND** “创建时间”仍按现有合同参与检查起止时间计算

#### Scenario: 用户人工维护委托时间
- **WHEN** 用户在审核页面选择委托时间并保存草稿
- **THEN** 系统保留用户选择的日期供预览和 Word 导出使用
- **AND** 日期使用既有中文纯日期格式，后续加载已保存案件时不得清空或覆盖用户值

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

#### Scenario: 检材编号与设备目录保持行内对应关系
- **WHEN** 新格式设备行通过 `tb2` 路径明确指向设备目录，且检材编号顺序与设备目录字母序不同
- **THEN** 系统按每行的明确路径绑定检材编号、设备型号和标识字段
- **AND** 后续排序、审核编辑与 Word 导出不得拆散同一检材记录内的对应字段
- **AND** 编号全部可识别且互不重复时，完整检材记录按检材编号自然升序输出

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
- AND 正式 Word 的检材情况在设备品牌型号后追加“手机”再显示“一部”；设备名称已包含同一类型名称时不重复追加
- WHEN 检材类型已由报告或用户确认为平板
- THEN 审核预览、检查过程和正式 Word 只显示该检材序列号，不显示 IMEI
- AND 正式 Word 的检材情况在设备品牌型号后追加“平板”再显示“一部”；设备名称已包含同一类型名称时不重复追加
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
- AND 后端使用与 Word 相同的 Manifest→legacy附件投影生成附件1预览表格，前端显示每个 part 的文件名、审核后检材来源、案件提取方式快照（缺失时使用自动生成值）和MD5；不得继续显示解析期空表或旧 `rar_info`
- AND WinRAR 不可用或归档失败时仍允许继续审核和编辑，但正式 Word 导出保持阻止

### Requirement: REQ-006: 检查过程自动生成

系统 MUST 根据结构化检材、最终选中的检查硬件设备和新案件初始化时采集的本机检查环境快照生成检查过程。步骤3 MUST 使用运行文枢的本机 Windows 系统信息及本机火绒安全软件安装信息，不得写死硬件型号、Windows 版本或火绒版本。

本机环境快照 MUST 与新案件草稿一同保存，使审核编辑、自动保存和最终 Word 使用相同事实。系统只读取环境元数据，不得自动启动火绒、执行杀毒或把自动识别等同于已完成病毒扫描。既有案件和人工编辑的历史步骤不得因应用升级或本机环境变化被批量重写。

Windows 系统展示名称 MUST 按“系统代际 + 位数版本类型”的顺序显示，位数与版本类型之间不得有空格，并 MUST 忽略 `DisplayVersion` 发布版本号；例如 Windows 10 的 `21H2` 不得出现在检查过程文本中。

步骤3在已识别的 Windows 展示名称后 MUST 补充“操作系统”，形成例如“Windows 10 64位家庭版操作系统启动正常”的完整表述；操作系统信息无法识别时仍使用“操作系统信息待确认”，不得重复拼接“操作系统”。

#### Scenario: 使用实际硬件与本机环境生成步骤3

- WHEN 新案件最终选中的检查硬件设备为“TEST-A 手机取证工作站”
- AND 本机识别到“Windows 11 64位专业版”及火绒安全软件版本“TEST-6.0.7.0”
- THEN 步骤3使用“TEST-A 手机取证工作站”“Windows 11 64位专业版”和“火绒安全软件（版本号为TEST-6.0.7.0）”
- AND 步骤3显示“Windows 11 64位专业版操作系统启动正常”
- AND 审核编辑、自动保存与最终 Word 使用同一环境快照生成的文本
- AND 文本中不出现写死的 FL-901、Windows 10 或 6.0.6.1

#### Scenario: Windows 发布版本号不进入展示名称

- WHEN 本机识别到 Windows 10、`DisplayVersion` 为 `21H2`、版本类型为企业版
- THEN 步骤3显示“Windows 10 企业版”及已识别的系统位数
- AND 步骤3不显示 `21H2`

#### Scenario: 火绒存在但版本无法读取

- WHEN 本机可靠识别到火绒安全软件但版本字段缺失、损坏或不可访问
- THEN 步骤3显示“火绒安全软件（版本号待确认）”
- AND 系统不使用历史版本、其他安全软件版本或固定默认版本填充

#### Scenario: 未识别到火绒安全软件

- WHEN 本机安装信息和受控文件版本来源均未识别到火绒安全软件
- THEN 步骤3显示“安全软件待确认（版本号待确认）”
- AND 杀毒结果显示“待确认”，不得声称已使用火绒或“未发现病毒”

#### Scenario: 操作系统信息读取异常

- WHEN Windows 系统信息源不可用、返回无法识别的值或应用运行在非 Windows 环境
- THEN 步骤3显示“操作系统信息待确认”
- AND 系统不回退到 Windows 10、当前年份推断或报告正文中的系统描述

#### Scenario: 检查硬件设备为空

- WHEN 新案件完成共享默认应用后 `inspection.hardware_device` 仍为空
- THEN 步骤3显示“检查硬件设备待确认”
- AND 系统不从检材型号、主取证软件名称、设备列表顺序或报告正文猜测硬件设备

#### Scenario: 审核页修改检查硬件设备

- WHEN 用户在审核页把检查硬件设备从“TEST-A 手机取证工作站”修改为“TEST-B 手机取证工作站”
- THEN 步骤3使用已保存的同一环境快照，把设备名称重投影为“TEST-B 手机取证工作站”
- AND 系统不重新读取本机环境，不改变步骤1、步骤2、步骤4或其他人工编辑字段

#### Scenario: 既有案件保持稳定

- WHEN 应用升级后打开一个缺少环境快照的既有案件，或本机 Windows/火绒版本在草稿创建后发生变化
- THEN 系统不因加载、轮询或普通保存自动改写该案件现有步骤3
- AND 用户仍可在检查过程编辑器中人工确认或修改内容

---

**CAP-003: 全文在线编辑**

### Requirement: REQ-007: 任意字段可编辑

系统 MUST 满足以下现有合同。工作台编辑通过后端自动保存并携带草稿 revision；编辑会话使用心跳租约，连续无心跳达到既定超时后才允许用户确认接管。版本冲突、租约冲突和保存失败不得静默覆盖后端草稿。系统通过部署实例作用域的后端事实源维护九项笔录默认设置，并在统一平台外壳中提供独立管理入口；案件审核编辑只修改当前案件，不得隐式更新笔录默认设置。

#### Scenario: 审核编辑界面规范化多个委托人
- WHEN 报告识别结果或用户输入使用顿号、中英文逗号/分号、斜杠、竖线或换行分隔多个委托人
- THEN 系统将各委托人拆分为非空数组项并清理分隔符两侧空白
- AND 审核编辑界面直接使用中文顿号连接显示规范化后的委托人
- AND 用户编辑后保存的字段继续使用拆分后的委托人数组

#### Scenario: 集中查看和保存笔录默认设置
- WHEN 用户进入“笔录默认设置”页面
- THEN 系统展示当前委托单位前缀、文号格式、检查地点、检查方法、检查硬件设备、数据摘要、检查要求、有序检查人员和文件哈希算法
- AND 文号格式由编号前内容和编号后内容组成，并展示使用示例；设置页不要求用户输入技术占位符
- AND 页面不展示或提交光盘编号前缀及附件1提取方式，不展示当前版本及案件基础信息、文件哈希算法、检查人员顺序下方的说明提示
- AND 用户可显式保存一个或多个修改，或用空值清除对应默认设置
- AND 检查硬件设备使用与审核编辑相同的下拉选择能力，候选项来自“电子设备管理”，不得自由输入未管理设备
- AND 检查人员使用与审核编辑相同的人员库卡片编辑器，支持添加、删除和拖拽调整保存顺序
- AND 保存使用服务端当前 revision；成功后页面展示已提交的新值与 revision
- AND `default_template_ref`、部署实例 ID、迁移状态和其他系统元数据不得作为业务字段开放编辑
- AND 案件字段优先级为“当前案件用户手工修改 > Parser 非空真实解析值 > 非空共享默认值 > 系统默认值或空值”
- AND 后续新案件仅在 Parser 对应值为空、纯空格、缺失、空数组或 Parser 值为系统默认值时使用非空共享默认值，Parser 提取的真实非空值仍优先并保持 report 来源
- AND 已有案件不因共享默认值更新而被回写；案件、检材、设备标识和主软件等报告事实不受影响
- AND 后端持久化是工作台事实源，`localStorage` 仅可用于一次性导入/忽略旧值的兼容迁移，不是案件或共享默认值事实源
- AND 当前合同不宣称多用户隔离

#### Scenario: 哈希算法设置只影响后来新建案件
- WHEN 用户保存 MD5、SHA-1 或 SHA-256
- THEN 后续新案件在 `inspection.result.hash_algorithm` 固化规范值 `md5`、`sha1` 或 `sha256`
- AND 已创建案件不被回写，存量缺失字段按 MD5 兼容
- AND 空值或候选集合外算法整体拒绝且不推进默认值 revision

#### Scenario: 检查要求默认值只影响后来新建案件
- WHEN 用户保存非空检查要求默认值，随后创建新案件
- THEN Parser 返回真实非空检查要求时保持该值和 report 来源优先
- AND Parser 仅返回固定系统检查要求、空值或缺失时，新案件使用非空共享检查要求并标记 system_default 来源
- AND 共享检查要求为空时继续使用既有固定系统检查要求“上述检材内电子数据的提取、固定和恢复”
- AND 后续修改或清空共享检查要求不得回写已有案件

#### Scenario: 数据摘要默认值只影响后来新建案件
- WHEN 用户保存非空数据摘要默认值，随后创建新案件
- THEN Parser 返回真实非空数据摘要时保持该值和 report 来源优先
- AND Parser 仅返回固定系统摘要、空值或缺失时，新案件使用非空共享数据摘要并标记 system_default 来源
- AND 共享数据摘要为空时继续使用既有固定系统摘要“即时通讯、手机信息”
- AND 后续修改或清空共享数据摘要不得回写已有案件

#### Scenario: 新案件按格式填写文号编号
- WHEN 用户保存非空文号格式并在之后创建新案件，且 Parser 没有返回真实文号
- THEN 系统将编号前内容和编号后内容固化为该案件的文号格式快照
- AND 审核编辑页只要求用户输入数字编号，输入按字符串处理并保留前导零
- AND 系统立即将编号前内容、编号和编号后内容组合为完整 `document_number`，供页面标题、预览、Word 和默认导出文件名共同使用
- AND 编号为空时完整文号为空并保持待填写状态

#### Scenario: Parser 文号和存量案件保持兼容
- WHEN Parser 返回不匹配案件文号格式的真实完整文号，或已有案件没有文号格式快照
- THEN 系统保留真实完整文号，并在审核编辑页继续提供完整文号编辑
- AND 后续修改共享文号格式不得回写已有案件

#### Scenario: 默认设置保存冲突与失败
- WHEN 用户基于过期 revision 保存笔录默认设置，或请求失败
- THEN 系统不得覆盖服务端较新值
- AND 页面明确提示冲突或失败，并提供重新加载当前值的操作
- AND 未知字段请求仍整体拒绝且不得发生部分写入

#### Scenario: 清空默认设置
- WHEN 用户在独立页面清空一项标量默认值或全部检查人员并成功保存
- THEN 后端将对应默认值持久化为空
- AND 后续新案件在该字段没有非空共享默认值时回到 Parser 真实值、系统默认值或空值
- AND 清空操作不改变其他未修改默认值、模板默认版本或已有案件

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

#### Scenario: 案件编辑不再隐式更新默认设置
- WHEN 用户在案件审核编辑页修改文号、委托单位前缀、检查地点、检查方法、检查硬件设备、检查人员或光盘编号并保存草稿
- THEN 修改只进入当前案件草稿
- AND 草稿请求不生成或提交 `shared_defaults_patch`
- AND 当前笔录默认设置保持不变

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

#### Scenario: 草稿保存不携带默认设置写入
- WHEN 当前案件草稿保存成功、失败或发生 revision 冲突
- THEN 后端仍返回稳定的草稿保存结果，草稿保存、自动保存与 revision 冲突行为不变
- AND 审核编辑界面不提交或单独展示共享默认值保存状态，也不因此改变草稿保存结果

#### Scenario: 人员拖拽只更新当前案件顺序
- WHEN 用户拖拽当前案件检查人员卡片并保存
- THEN 当前案件 InspectorSnapshot 顺序变为 user 确认顺序
- AND 笔录默认设置中的检查人员顺序保持不变

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

#### Scenario: 单张图片大小限制
- WHEN 用户选择大小小于或等于 100MB 的合法 JPG/JPEG/PNG 图片
- THEN 前端不得因单文件大小拒绝该图片，后端允许其继续进入真实图片、案件数量与总容量校验流程
- WHEN 用户选择大小超过 100MB 的图片
- THEN 前端拒绝该文件并提示“图片不能超过 100MB”
- AND 绕过前端直接请求后端时，后端返回稳定错误码 `ASSET_IMAGE_TOO_LARGE`，错误提示明确单张图片超过 100MB 限制

#### Scenario: 图片变更受租约和 revision 保护
- WHEN 用户替换或删除图片
- THEN 新资产成功写入后才替换旧引用，草稿使用 expected revision 保存，冲突不得静默覆盖另一会话
- AND 只读或失效租约不能上传、替换或删除图片，未引用资产按宽限期安全清理

#### Scenario: 人工检材编辑后继续上传图片
- WHEN 用户已成功绑定图片，随后人工添加或修改检材，并在本地字段自动保存完成前继续上传下一张图片
- THEN 前端以最后一次成功绑定的图片列表作为图片域 CAS 基线，把图片绑定到服务端最新草稿
- AND 绑定返回后把尚未保存的人工检材编辑重放到新 revision 并交由既有自动保存队列收敛
- AND 同一会话内的字段编辑不得被误报为图片列表已被另一会话修改，真实图片域并发仍必须返回冲突

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
- AND 未提交导出目录的一般 Legacy 兼容请求继续触发浏览器下载

#### Scenario: 导出目录选择器保持可见并记住上次目录
- WHEN 民警从案件工作台点击「统一导出」，或从审核编辑界面点击「导出 Word」，并完成 Word 文件名确认
- THEN 目录选择器窗口保持在浏览器窗口前方且可见、可操作，不得被浏览器覆盖
- AND 成功选择目录后，系统持久化该导出目录作为本地偏好
- AND 两处入口复用同一导出目录偏好，后续再次打开时默认定位到上次成功选择且仍然存在的目录
- AND 用户取消选择不得覆盖已记忆目录，已记忆目录不存在或偏好损坏时安全回退到系统默认位置
- AND 被判定为程序目录或用户数据目录的选择不得写入目录偏好，后续合法选择仍从上一次有效目录继续

#### Scenario: 审核编辑界面单独导出 Word 到所选目录
- WHEN 民警在审核编辑界面点击「导出 Word」、确认文件名并在 Windows 原生目录选择器中选择目录
- THEN 系统使用导出时刻已保存的最新审核数据生成 `.docx`，并将其直接写入所选目录
- AND 案件已有成功归档时，单独 Word 导出复用统一导出的已验证最终 `ArchiveManifest`、持久化光盘映射和 `AttachmentPlan`，附件一及其他附件的结构和版式保持一致
- AND 附件1的“电子数据”、“提取方法”和“文件MD5哈希值”数据单元格在首页与续页均允许西文在单词中间换行
- AND 附件1的“来源”将每个检材编号单独换行显示，编号间保留顿号，“检材内提取”在编号后单独占一行
- AND 案件尚无成功归档时继续使用 report-only 兼容分支，不伪造 `ArchiveManifest` 或归档完成状态
- AND 单独 Word 导出复用统一导出的目录授权、路径校验、目录记忆和文件名清洗规则，不再触发浏览器下载
- AND 单独 Word 导出不复制 RAR、不生成 HashMyFiles PNG、不改变案件的统一导出完成状态，成功后继续停留在审核编辑界面

#### Scenario: 取消审核编辑界面的导出目录选择
- WHEN 民警确认 Word 文件名后关闭或取消 Windows 原生目录选择器
- THEN 系统不生成、不下载也不写入 Word 文件
- AND 页面保持可编辑，既有目录偏好不被覆盖，用户可以再次发起导出

#### Scenario: 归档完成后统一导出到用户路径
- WHEN 案件进入归档完成态且民警点击「导出」
- THEN 系统提示用户选择导出文件夹，把最新编辑数据生成的 Word 与全部 RAR 文件写入所选文件夹
- AND 本次统一导出不在所选文件夹的上级目录生成新的 RAR 文件
- AND 所选目录位于文枢程序目录或用户数据目录中时，系统必须在签发目录授权和写入任何文件前明确拒绝，不得污染便携发布包或内部工作数据
- AND 生产 Controller 使用审核后的 `InspectionReport` legacy DTO 和已验证的最终 `ArchiveManifest` 构造 `AttachmentPlan`
- AND Word 使用案件明确引用且当前重新校验通过的 approved 模板版本生成 .docx；带 Manifest 的正式渲染失败时必须明确失败，不得静默回退到无 Manifest 的 officecli batch 输出
- AND 检查笔录的统一导出不得启动 HashMyFiles 或生成校验截图；现有截图能力保留，供后续鉴定文书流程接入
- AND Word 与 RAR 副本必须先完整暂存后统一发布；任一步失败时保留上一版完整导出，不得形成新旧产物混合包
- AND 再次导出到含旧 `hash-verification.png` 或 `hash-verification.html` 的同一目录时，成功发布必须移除这些历史校验产物；发布失败则恢复旧完整导出

#### Scenario: 可重复导出且 Word 用最新编辑
- WHEN 案件已导出成功后民警再次导出
- THEN 系统重新打开导出路径选择，Word 用导出时刻的最新编辑数据重新生成，RAR 复用已验证分卷，不生成 HashMyFiles PNG
- AND 导出成功不关闭审核编辑，民警可继续修改并再次导出

#### Scenario: 导出后仍可修改
- WHEN 导出完成后
- THEN 预览页面不关闭，民警可继续修改并再次导出

#### Scenario: 每次询问、取消和物理文件隔离
- WHEN 用户点击导出
- THEN 系统重新打开文件名输入框，默认值为文号加 `.docx`；文号为空时默认值为空
- AND 取消、空名称或非法 Windows 名称不创建任务或文件
- WHEN 用户输入合法名称
- THEN Word 文件名按输入补全 `.docx`；目录导出先在所选目录同卷暂存后原子发布，失败时不覆盖既有同名文件
- AND 未提交目录的 Legacy 兼容请求仍使用唯一安全服务器文件并按该 Word 文件名下载

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

#### Scenario: Word 委托人统一使用顿号
- WHEN 正式模板或兼容回退路径生成包含多个委托人的 Word
- THEN 系统在最终拼接前识别委托人数组项中残留的常见分隔符
- AND Word 中的不同委托人统一使用中文顿号连接

#### Scenario: 模板缺失时保持兼容回退
- **WHEN** 正式模板不可用
- **THEN** 系统按既有兼容路径处理并明确报告结果
- **AND** 不改变现有 Legacy DTO、Word 字段映射和附件安全门控

### Requirement: 检查人员库维护单位与职位

检查人员库 MUST 维护姓名、单位、职位和警号，不维护启用/停用状态；所有未删除人员统一显示并可供案件选择。新增人员的四项业务字段均为必填。历史 v1 人员数据中的 `enabled` 值被忽略，原停用人员按可用处理；历史数据缺少职位时以空值兼容加载并允许后续补充。

#### Scenario: 查看和选择全部检查人员
- WHEN 用户进入检查人员管理或案件人员选择入口
- THEN 系统展示所有未删除人员的姓名、单位、职位和警号
- AND 不显示状态列或启用/停用操作

#### Scenario: 职位进入案件快照和正式文书
- WHEN 用户选择具有职位的检查人员并保存或导出案件
- THEN `InspectorSnapshot`、兼容投影和正式文书保留该职位
- AND 人员库后续修改或删除不改写既有案件快照
- AND 历史快照缺少职位时继续可读且不产生重复分隔符

---

**CAP-005: 硬件设备管理**

### Requirement: REQ-010: 硬件设备 CRUD

系统 MUST 为每台取证硬件设备维护名称和所属公司。设备列表 API MUST 对缺少公司字段的旧配置返回空字符串兼容值，并忽略旧配置中已废弃的型号和描述；新建设备必须提供非空名称和所属公司，更新设备时不得因未提交公司字段而清除既有公司。

#### Scenario: 查看设备所属公司
- WHEN 民警进入设备管理页面
- THEN 系统只展示每台设备的名称和所属公司
- AND 旧配置缺少所属公司时页面显示待补充状态而不是加载失败
- AND 旧配置中的型号和描述不在列表、表单或设备 API 响应中展示

#### Scenario: 新增带所属公司的设备
- WHEN 民警填写设备名称和非空所属公司并保存
- THEN 系统持久化这两个字段并在刷新后的设备列表中显示
- AND 该设备继续出现在审核编辑界面的硬件设备下拉框中

#### Scenario: 所属公司为空
- WHEN 民警新增设备或编辑旧设备但提交的所属公司为空或仅包含空白
- THEN 系统拒绝该次提交并提示补充所属公司
- AND 不覆盖该设备已保存的其他字段或既有非空公司

#### Scenario: 更新设备时未提交所属公司
- WHEN 更新请求没有携带 `company` 字段
- THEN 系统保持该设备当前所属公司不变
- AND 名称仍按当前更新合同处理

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
- AND 任意审核字段或图片引用的合法保存不得使归档任务进入中断/失败，也不得因审核内容变化触发 `ARCHIVE_ATTEMPT_BINDING_STALE`
- AND 压缩、完整性、MD5 与 Manifest 各阶段完成状态实时反映在案件卡片上

#### Scenario: 压缩期间上传图片可靠绑定到最新草稿
- WHEN 民警启动后台压缩后在审核编辑界面上传图片
- THEN 图片上传完成后系统立即保存图片资产引用及其检材映射，且页面离开前必须等待该保存完成
- AND 若保存发生在归档正式发布的短临界区，归档完成事务只把已验证的 RAR 结果合并到最新草稿，不得覆盖新图片引用或其他并发审核编辑
- AND 若图片保存与归档完成回填发生竞争，系统必须识别仅由归档完成产生的 revision 推进并自动合并重试，不得向审核页面返回 409；最终草稿同时保留图片引用与已验证 RAR/MD5/附件1字段
- AND 已密封的归档输入快照、RAR 内容和发布证据仍保持不变

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

### Requirement: REQ-015: 展示哈希和文件大小

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

#### Scenario: Manifest 区分内部 MD5 与案件业务哈希
- WHEN 新案件完成 RAR 归档
- THEN 每个 `ArchivePart.md5` 继续用于完整性、复用、下载与发布安全门
- AND 每个 part 同时保存案件 `hash_algorithm` 与对应 `hash_value`
- AND MD5 案件复用内部 MD5，SHA-1 与 SHA-256 摘要分别为 40 与 64 个十六进制字符
- AND 旧 Manifest 缺少新增字段时以 MD5 和原 `md5` 兼容投影

#### Scenario: 文书和附件跟随业务哈希
- WHEN SHA-1 或 SHA-256 案件归档完成
- THEN 检查结果、附件1列标题、系统自动生成的提取方式、Word 正文和附件3显示所选算法名称与完整大写摘要；案件自定义提取方式快照保持原文
- AND legacy `md5_hash` 键仅作为兼容载体，不得导致用户界面固定显示 MD5 标签

---

**CAP-009: 软件工具列表动态生成**

### Requirement: REQ-016: 按实际操作生成 software_tools

系统 MUST 满足以下现有合同：
系统 MUST 根据报告来源和实际运行环境生成 `software_tools`。主软件名称和版本均为可靠候选时，列表包含主软件、WinRAR 和 HashMyFiles；主软件名称或版本不完整时，不加入主软件工具，只保留 WinRAR 和 HashMyFiles。主软件确认状态由 `inspection.primary_software` 和统一导出门控管理，不写死具体厂商或产品名称。

可靠主软件名称候选 MUST 移除表示取证塔、取证设备、取证工作站、采集设备或硬件设备的括号描述，同时保留报告识别到的软件名称和独立版本；不得擅自映射为其他产品名称，也不得把硬件描述作为软件工具名称导出。

新案件审核草稿初始化时，系统 MUST 以最终选中的检查硬件设备为键，从设备配置中唯一解析所属公司，将规范化后的公司与报告可靠识别的主软件名称直接拼接为审核及正式文书使用的名称。该转换是显式设备配置驱动的显示投影，不得从报告正文、软件名称或设备型号猜测公司。

公司前缀 MUST 只应用于报告可靠识别的主取证软件，并同步到 `inspection.primary_software.name`、`inspection.primary_software.display_name`、兼容字段 `inspection.result.software_name`、`inspection.software_tools` 中的主软件条目以及检查步骤 4。WinRAR、HashMyFiles、人工新增工具、主软件候选和 provenance MUST 保持原值。

检查步骤 4 MUST 同时记录启动主取证软件和使用同一主取证软件处理全部检材两个动作，格式为“启动{软件名称}软件（版本号为{版本号}）使用{软件名称}软件对检材{全部检材编号}进行检查。”；软件名称已以“软件”结尾时不得重复追加。软件名称、版本号和有序检材编号 MUST 来自当前案件结构化数据，不得写死产品、版本或检材编号。

#### Scenario: 报告主软件自动添加所属公司
- WHEN 新案件最终选中的硬件设备唯一匹配设备配置且所属公司为“美亚柏科”
- AND 报告可靠识别的主取证软件名称为“手机大师NEXT”且版本完整
- THEN 审核编辑界面的主软件名称和软件工具列表显示“美亚柏科手机大师NEXT”
- AND 检查步骤 4、检查结果和最终 Word 使用同一名称
- AND 公司与软件名称之间不自动添加空格、短横线或括号

#### Scenario: 已有公司前缀不重复添加
- WHEN 设备所属公司为“美亚柏科”且报告主软件名称已经以“美亚柏科”开头
- THEN 系统保留该软件名称
- AND 所有主软件派生字段只包含一次“美亚柏科”前缀

#### Scenario: 检查步骤 4 记录实际软件处理动作
- WHEN 当前案件主取证软件为“美亚手机大师-并行版V3”、版本号为“V3.2.08602”，且有多个有序检材编号
- THEN 检查步骤 4 先记录启动该软件，再记录使用同一软件对全部检材进行检查
- AND 启动和使用动作中的软件名称完全一致，版本号只在启动动作中记录一次
- AND 最终 Word 使用当前案件保存的同一步骤内容，不退回只描述启动软件的旧句式

#### Scenario: 已有案件的旧自动步骤在导出时安全兼容
- WHEN 已有案件步骤 4 与当前软件名称、版本号和有序检材编号组成的旧自动模板精确一致
- THEN Word 生成前把该步骤投影为同时包含启动和使用动作的新句式
- AND 该兼容投影不回写案件草稿；不精确匹配旧自动模板的人工编辑步骤保持原文

#### Scenario: 运行时和人工工具不添加设备公司
- WHEN 系统生成或展示 WinRAR、HashMyFiles 或用户人工新增的软件工具
- THEN 这些工具保持各自名称
- AND 不因当前硬件设备所属公司而添加“美亚柏科”或其他公司前缀

#### Scenario: 设备公司无法安全确定
- WHEN 最终硬件设备未匹配配置、匹配到多个设备、所属公司为空，或主取证软件尚未可靠识别
- THEN 系统保持报告已有软件名称和确认状态
- AND 不从设备型号、报告正文、其他案件或列表顺序猜测公司
- AND 用户仍可在审核编辑界面人工确认或修改主软件

#### Scenario: 既有案件和人工编辑不被追溯覆盖
- WHEN 设备所属公司在某案件草稿创建后被修改，或案件中的主软件已经由用户人工编辑
- THEN 系统不批量改写既有案件草稿、已导出文书或人工编辑的软件名称
- AND 新公司值只参与之后初始化的新案件草稿

### REQ-034: 检材可提取状态

系统 MUST 在报告解析时按每项检材 IMEI1、IMEI2、序列号是否至少存在一个非空值自动生成“是否可提取”状态，并在审核编辑界面展示且允许人工修正。用户将检材设为无法提取时，界面 MUST 显示无法提取原因输入框；原因随案件草稿保存，留空时 MUST 作为待核对项提示并阻止审核编辑界面的 Word 导出。无法提取时审核页隐藏 IMEI/序列号，Word 检材情况和检查过程步骤 1 使用用户填写的原因替代设备标识。缺少新字段的存量数据按同一规则兼容推导，并在没有原因时保留既有“无法提取”兜底文案。

#### Scenario: 无设备标识的检材
- WHEN IMEI1、IMEI2 和序列号全部为空
- THEN 检材自动标记为无法提取
- AND 检材情况显示“设备名一部（无法提取）”
- AND 检查过程显示“将设备名（无法提取）编号为检材编号”

#### Scenario: 用户填写无法提取原因
- GIVEN 审核编辑界面的手机为“HUAWEI ADY-AL10”，且原有 IMEI1 和 IMEI2
- WHEN 用户将该检材设为“无法提取”并填写原因
- THEN 原因随案件草稿保存
- AND 审核界面隐藏 IMEI1、IMEI2 和序列号
- AND Word 检材情况显示“HUAWEI ADY-AL10手机一部（用户填写的原因）”
- AND Word 检材情况不得输出该检材的 IMEI 或序列号
- AND 检查过程步骤 1 显示“将HUAWEI ADY-AL10（用户填写的原因）编号为检材编号”

#### Scenario: 无法提取原因留空
- WHEN 检材被设为“无法提取”且原因为空白
- THEN 审核编辑界面显示原因输入框和明确的待填写提示
- AND 该原因进入审核待核对清单
- AND 审核编辑界面的 Word 导出保持阻止，直至用户填写原因
- AND 存量数据生成 Word 时继续使用“无法提取”作为兼容兜底

MD5 校验由 HashMyFiles.exe 执行，新解析案件和存量案件的运行时工具条目均显示 HashMyFiles；存量案件可继续持久化旧值 Python hashlib，读取与正式导出时投影为 HashMyFiles，底层识别逻辑同时兼容两者（`python hashlib`/`python_hashlib` 与 `hashmyfiles`）。

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
- AND 存量案件即使仍持久化 "Python hashlib"，审核界面与正式导出也统一显示 "HashMyFiles 2.51"

#### Scenario: 主软件候选不完整时不加入主软件工具
- WHEN 主软件名称或版本缺失，或尚未形成可靠候选
- THEN `software_tools` 不加入主软件工具
- AND 仍包含 WinRAR 和 HashMyFiles
- AND `inspection.primary_software` 保留确认状态，由导出门控决定是否允许正式导出

### Requirement: 审核页主取证软件单点展示与编辑

完整审核编辑器 MUST 在“软件工具”区域中只展示一次主取证软件名称和版本，并将主软件确认状态、名称和版本编辑入口合并到同一主软件行；不得在软件工具区域下方重复展示独立的主取证软件区块。该展示合并 MUST 继续使用 `inspection.primary_software` 作为唯一权威编辑结构，不改变现有派生字段、检查步骤或正式导出门控。

#### Scenario: 已识别主软件只展示一次

- **WHEN** 报告已识别主取证软件名称和版本，且 `software_tools` 包含对应主软件条目
- **THEN** 完整审核编辑器只在“软件工具”的主软件行显示一次该名称和版本
- **AND** 同一区域继续显示报告自动识别或人工确认状态，不再渲染第二个独立主取证软件区块
- **AND** WinRAR、HashMyFiles 等其他软件工具继续各显示一条

#### Scenario: 在软件工具区域确认主软件

- **WHEN** 主取证软件名称、版本缺失或待确认
- **THEN** 用户可以直接在“软件工具”的主软件行填写或修改名称和版本
- **AND** 待核对导航继续定位到同一行中的确认状态、名称或版本
- **AND** 编辑继续更新 `inspection.primary_software`，并沿用既有兼容字段、软件工具投影、检查步骤和导出门控

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
  - 提取方式 = 优先使用案件创建时固化的附件1提取方式快照；快照为空或缺失时使用 `inspection.hardware_device`，缺失硬件时使用“取证设备”，并按案件文件哈希算法生成既有检查、报告、压缩和哈希描述
  - 文件MD5哈希值 = 该实际 part 的 MD5 哈希值
- AND Word 和附件3使用同一 Manifest，不从 `rar_info`、ArchivePlan 或目录扫描重新生成卷列表
- AND 附件3每页元数据框依次只显示检验单位、光盘编号、文件哈希和刻录时间，不显示“文件名”行；正文检查结果和附件1仍使用 Manifest 的实际 part 文件名

#### Scenario: 每个 RAR 完成即回填并覆盖
- WHEN 后台压缩的某个 part 完成并通过完整性/MD5 校验
- THEN 后端立即将该 part 的文件名、文件大小和 MD5 写入案件记录的检查结果（`rar_filename`、`file_size`、`md5_hash` 对应位置）与附件1（`extract_list`）对应行，实时增量更新
- AND 自动值覆盖 Manifest 控制的文件名、大小和哈希字段；来源列仍按审核后的 `evidence_number` 生成，提取方式优先使用案件快照，快照为空或缺失时使用 `inspection.hardware_device`，缺失硬件时使用「取证设备」
- AND 未完成 part 对应位置保持未填写，不提前生成空行占位

#### Scenario: 解析响应兼容字段不驱动附件1
- WHEN 文件夹解析仅返回空值/零值 `rar_info`，或压缩包直传返回上传文件的兼容 `rar_info`
- THEN 这些解析响应字段均不作为正式附件1或最终导出的归档事实源
- AND 正式附件1只按已验证 `ArchiveManifest` 派生的 `AttachmentPlan` 生成

---

**CAP-011: 受控分卷归档与最终 Manifest**

### Requirement: REQ-018: 当前生产归档合同

系统 MUST 满足以下现有合同：
- WinRAR 标准分卷档位固定为二进制 4GB、22GB、45GB（`1GB = 1024³` 字节）；4GB 和 22GB 档预计超过 2 卷时升级，45GB 档最多 5 卷，标准分卷最多覆盖 225GB，不新增 75GB 档。
- 输入不超过 225GB 时使用 `archive_mode=standard_split`；超过 225GB 且仍在安全整数范围内时，不报总量超限，改用 `archive_mode=oversized_single_volume` 生成不分卷的 `<案件名>.rar`。
- 模式只由压缩前归档输入总量决定；压缩后的实际 RAR 大小只写入 Manifest，不触发介质切换或重新分卷。恰好 `225 × 1024³` 字节仍属于标准分卷。
- 标准分卷初始执行后最多允许 2 次向上 replan。其 `volume_size_bytes` 是档位每卷上限，`size_bytes` 是 WinRAR 实际 part 文件大小；超大单卷的 `volume_size_bytes`、`volume_tier_gb` 与 `disc_capacity_bytes` 为空，不套用每卷不超过 45GB 的校验。
- 默认资源准入不得以旧 135GB 上限阻断超大单卷；部署人员仍可显式配置本机输入安全上限。附件与 Word 计划必须保留超大单卷的空容量字段，不得伪造光盘容量档位。
- 每个 part 的 `disc_capacity_bytes` 必须只根据该 part 的 `size_bytes` 独立选择最小可容纳容量；不得继承 Manifest 档位值。
- 每个 `VolumeSlot` MUST 有稳定身份、序号、计划版本和容量/输入范围；标准分卷由用户填写 `GPyyyyMMdd-序号` 或 `GPyyyyMMddXX-序号` 首盘号并按实际 part 顺序生成连续光盘编号，超大单卷由用户填写唯一 `YPyyyyMMdd-序号` 或 `YPyyyyMMddXX-序号` 硬盘编号，其中可选的 `XX` 为两位数字用户标识；错误介质前缀不得完成映射，系统不得自动补写或删除用户标识。
- replan 必须保留仍有效的人工槽位映射；新增槽位进入 pending，删除槽位清除映射，匹配不得依赖预计 RAR 文件名；最终以通过验证的 Manifest 槽位、卷序和介质编号为准。
- 最终 `ArchiveManifest` 是 Word 正文、附件1和附件3归档字段的唯一事实源。
- RAR 外部基础名来自报告案件名称并清理 Windows 非法字符、结尾空格和点；单卷为 `<案件名>.rar`，多卷为 `<案件名>.partN.rar`。
- WinRAR 以原始报告目录的父目录为工作目录、以原始报告根文件夹名为输入；归档内部保留该根文件夹、全部相对目录、多级嵌套、同名文件和业务空目录，不包含绝对路径、盘符、staging、cache、UUID或项目输出路径。
- 每个 part 只能通过有效 `archive_context_id`、`manifest_id` 和不透明 `part_id` 下载；客户端不得提交服务器路径，下载前必须重新验证 Manifest 对应物理文件。
- 未包含 `archive_mode` 的历史 Manifest 继续按旧十进制档位复核；所有新 Manifest 必须显式记录标准分卷或超大单卷模式。
- 标准分卷的正式 Word 使用“封盘、刻录、光盘”语义，附件摘要列出全部实际光盘编号；超大单卷使用“拷贝、硬盘1块、硬盘编号”语义。

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

每个可编辑叶子字段、检材字段、人员项和附件图片组 MUST 有 `FieldState`，包含稳定字段路径、来源 `report | user | system_default`、确认状态 `confirmed | pending` 和 revision。纯派生不可编辑字段继承来源，不单独维护状态；来源颜色不得进入 Word，pending 必须有文字提示。审核编辑页 MUST 不显示单独的“文号来源”行或页面级“字段来源”说明块。

#### Scenario: 页面级来源说明移除且导出隔离
- WHEN 用户进入审核编辑页，字段来自报告、系统默认值或人工修改
- THEN 页面不显示单独的“文号来源”行或“字段来源”说明块
- AND `FieldState` 数据、待人工确认文字和正式导出确认门控保持不变
- AND Word 使用正式黑字，不携带来源颜色

#### Scenario: 待确认不只靠颜色
- WHEN 检材、关键字段或图片组处于 pending
- THEN 页面显示待人工确认文字和影响范围
- AND 正式导出执行现有确认门控

### Requirement: REQ-021: 来源复核不得递归扫描完整报告目录

系统 MUST 为每个工作台来源创建 `SourceRecord`。来源提交合同是本机报告目录路径而非 ZIP/RAR 或其他上传文件。案件为导出后可删除的短生命周期工作数据；用户确认压缩期间不修改源目录时，来源复核 MUST 只检查授权路径、允许根、链接/reparse、报告结构以及核心报告文件的路径、类型、大小和 mtime，不得为展示审核页或提交归档决策而递归枚举全部媒体文件。后端仍保存 opaque `source_id`、允许根授权、`source_type`、`case_id/task_id` 绑定、metadata/fingerprint、访问状态和最近复核时间；绝对路径只能存在受控后端 locator 中。来源目录缺失、越界、结构无效或核心报告文件身份变化时必须要求重新选择目录。

#### Scenario: 来源绑定和有界重启复核
- WHEN 用户提交经后端验证的报告目录并创建解析任务
- THEN SourceRecord 绑定案件壳和 task_id，并保存允许根授权及 metadata/fingerprint
- AND 有界核心来源 fingerprint 可先保持 pending 并由独立来源复核完成；快速解析按 `Legacy Parser → 草稿持久化 → review_ready` 顺序执行
- AND 来源复核只对授权 locator、报告根目录、`data` 目录和核心报告文件计算路径/类型/大小/mtime 指纹，不读取内容或遍历深层媒体树
- WHEN 服务重启或任务恢复前访问来源
- THEN 后端复核允许根、路径、权限、链接安全性和 fingerprint/metadata，并识别仍处于待复核的 SourceRecord
- AND 恢复事务不得把 pending 复核标记为可信或来源变化；应用启动后按 `source_id + revision` 去重调度复核
- AND 调度失败保持 pending，记录 `SOURCE_REVALIDATION_PENDING` 并允许后续启动或显式重试
- AND 已经 `review_ready` 的案件不得因恢复重复创建或执行 Parser
- AND 暂时 I/O、权限或资源不可用保持 pending，草稿可以查看和编辑；归档提交时执行同一有界快速复核，Word 导出须显示明确风险确认
- AND 已确认的路径、允许根、链接安全性、报告结构或核心报告文件路径、类型、大小、mtime 发生变化，或来源被替换/不可用时，才标记 `requires_reselection`

#### Scenario: 解析完成后快速开放直接压缩
- WHEN Parser 已成功生成可审核草稿
- THEN 后端只对授权 locator、报告根目录、`data` 目录和核心报告文件执行有界身份检查并将来源置为可用
- AND 审核页无需等待完整报告目录递归扫描即可显示“直接压缩”入口
- AND 深层媒体文件的数量不得线性增加来源复核或归档决策请求耗时

#### Scenario: 核心来源身份失效
- WHEN 授权路径、允许根、链接/reparse 安全、报告结构或核心报告文件的路径、类型、大小、mtime 与已登记身份不一致
- THEN 来源变为 `requires_reselection` 并阻止归档
- AND 暂时 I/O/权限失败保持 `pending` 并允许有界重试
- AND 检查不得读取媒体文件内容或递归遍历深层媒体树

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

SourceRecord 的生产可用性身份 MUST 使用 REQ-021 的授权路径、报告结构与核心报告文件有界元数据指纹。完整媒体目录不再生成逐文件内容摘要，也不作为审核入口、归档提交或发布前的重复信任门。发布 intent、attempt/case/source/draft revision、Manifest 身份和物理 RAR 校验仍是完成权威。

#### Scenario: 有界来源身份与输出权威分离
- WHEN 工作台复核来源或归档发布核对当前来源记录
- THEN 来源可用性只使用授权 locator、报告结构和核心报告文件有界指纹
- AND 正式完成仍须通过 durable intent、Manifest、RAR 存在性/字节数/MD5 与发布代次门控

#### Scenario: 归档中断时保持可恢复且不发布半成品
- WHEN 归档执行在正式产物验证和可信完成提交前中断，或重启发现未完成归档尝试
- THEN 系统将未完成归档尝试和案件状态按既有恢复合同标记为 `interrupted`/`archive_interrupted`，不伪造 `succeeded`、`completed` 或 `100%`
- AND 未通过完整 Manifest/RAR、来源、所有权和绑定完整性门控的资产不得成为正式发布结果；可恢复状态和后续处理沿既有 deferred 或新 attempt 合同执行

### Requirement: REQ-023: 独立 Review 后的归档一致性、恢复与外部变更加固

归档发布、恢复和正式产物门控 MUST 继续使用完整不可变身份、owner/revision/lease/fence 和同一份 durable Manifest 证据，不得新增第二套发布事实源。发布 intent 的身份至少覆盖 case、attempt、source、source/draft revision、report fingerprint、source/input/archive fingerprint、Manifest/public Manifest、正式相对目录、context binding 和 fence；缺失或任一不一致 MUST 安全拒绝，完整相同的合法 intent 重入 MUST 幂等返回原记录。

应用停止达到有界等待上限时，属于本部署实例的 pending/running claim MUST 在 owner、attempt、task revision、lease 和 fence 条件仍成立时收敛为现有 `interrupted`/可恢复状态；不得把未完成工作标为 succeeded、completed 或 100%，不得改写其他部署实例的 claim。已经完成 durable 发布并通过可信完成门控的 attempt MUST 保持成功。重复停止、Worker 超时后的迟到返回和重启恢复 MUST 幂等。

用户确认压缩期间不修改源目录后，归档执行 MUST 以 Worker 唯一完整 inventory 的路径、类型、大小和 mtime 作为容量规划与 Manifest 输入统计，WinRAR 直接读取授权源目录。产物生成后不得为证明源目录持续不变而再次执行全目录枚举；完成权威收敛到 RAR 完整性、连续分卷/容量、每卷 MD5、durable intent、Manifest 与发布代次的物理文件校验。

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

#### Scenario: 执行期来源不变承诺
- WHEN 用户确认后启动直接源压缩
- THEN 系统不在 WinRAR 前后或发布前重复全量扫描源目录
- AND 用户违反承诺导致的混合时点源内容不在额外检测保证内，但 WinRAR 或输出门观察到失败时不得发布成功

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
- AND 案件 lifecycle 为最终状态时优先展示最终结果；只有与当前 lifecycle 兼容的活动任务才显示阶段、进度和分卷等运行信息，历史任务不得覆盖最终状态
- AND 允许操作按状态表达取消、重试、打开、导出或删除；前端不得只显示数字百分比
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
- AND `archive_complete` 在工作台展示为「待导出」并推荐统一导出，`exported` 只展示已导出最终结果并推荐删除案件

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

内置模板以不可变版本保存。当前 `electronic-inspection-record@1.0.4` 是唯一分发的内置 `word_templates/template.docx`，不包含批注结构、附件二示例媒体、身份相关核心/自定义属性或 WPS `docVars`；保留附件二空白定位段落、VML、分页、表格、动态图片渲染合同和 `1.0.3` 的全部可见版式。历史 `1.0.0`～`1.0.3` 不再作为仓库资产分发，也不进入模板管理列表或新案件可选列表。启动迁移将指向这些退役内置版本的默认值和案件引用幂等迁移到 `1.0.4`，用户选择的自定义默认模板和自定义案件模板引用保持不变。

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

#### Scenario: 内置模板隐私净化保持既有案件可导出
- WHEN 部署首次注册清理后的内置模板版本
- THEN 新案件默认引用 `electronic-inspection-record@1.0.3`
- AND 已明确引用 `1.0.0`～`1.0.3` 的案件模板引用迁移到 `1.0.4`
- AND 新案件不能选择历史内置版本，模板管理列表只展示最新内置版本，管理接口不能将历史版本重新设为默认
- AND 历史版本的注册、审批和 DOCX 资产保持不变，不物理删除或改写既有案件引用
- AND 用户选择的其他默认模板不被启动迁移覆盖
- AND 新版模板导出只包含本次动态上传图片，不包含批注或模板示例图片
- AND 核心属性使用通用系统身份，自定义属性和 WPS `docVars` 不存在，所有渲染相关 OOXML 部件与净化前基线逐字节一致

#### Scenario: 当前内置模板水平居中
- WHEN 当前模板由 Microsoft Word 原生渲染
- THEN 正文左右排版边界围绕页面中心平衡，附件一固定表格、主标题可见字形和首页/页脚粗横线相对页面水平居中
- AND “一、绪论”“二、检查”略突出于二级标题，“（三）检查过程”“（四）检查结果”与其他二级标题对齐
- AND 既有页数、分页、表格列宽、VML、页眉和页脚保持不变

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

#### Scenario: 案件卡片不显示无业务意义的列表序号
- WHEN 案件工作台当前页展示一个或多个案件
- THEN 案件卡片不显示仅代表当前页位置的序号圆圈
- AND 上传报告目录卡片仍位于案件卡片之后的下一个网格位置，现有尺寸、虚线框、图标、文案、间距、悬停与点击行为保持不变

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
- **THEN** 页面弹出标题为“确认删除该案件？”的确认提示
- **AND** 已导出案件直接显示“删除案件”推荐操作；其他状态将删除收纳到更多菜单
- **AND** 已导出案件的确认提示明确说明已导出到目标目录的文件不会被删除
- **WHEN** 用户点击“确认删除”
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

#### Scenario: 平台 Sidebar 默认折叠并提供图标名称
- **WHEN** 用户首次进入任一使用 `PlatformShell` 的页面
- **THEN** Sidebar 默认以折叠图标轨道展示，主内容区同步使用折叠宽度
- **AND** 用户悬停折叠态的品牌、一级导航或展开控制时看到对应名称
- **AND** 折叠态子菜单由点击打开，避免悬停名称与子菜单同时出现；展开后恢复既有菜单层级和交互
- **AND** 折叠态子菜单打开后，对应图标的悬停名称立即关闭且不拦截子菜单选项
- **AND** 已完整显示名称的“案件工作台”等二级选项不再重复显示黑色名称提示
- **AND** 用户从案件工作台点击折叠态“首页”图标时进入平台首页 `/`
- **AND** 图标菜单项继续提供可访问名称、键盘 Focus 和当前路由状态

#### Scenario: 首页按已开放功能展示成果总览
- **WHEN** 用户进入平台首页，且文书模块分别处于 `available` 或 `comingSoon` 状态
- **THEN** 首页只为 `available` 模块展示成果卡，不为 `comingSoon` 模块展示功能入口、统计卡或“更多能力”区域
- **AND** 成果卡预留累计成果、近两周变化和数据更新时间，累计成果为第一视觉焦点
- **AND** 1、2、3 个已开放模块根据实际内容宽度自然形成单卡、双列或三列布局，不按模块名称编写专属位置
- **AND** 成果卡为只读展示，不提供进入业务功能的链接或按钮；业务导航继续由平台 Sidebar 承担

#### Scenario: 首页成果数据尚未接入或暂不可用
- **WHEN** 某个已开放模块的成果统计尚未接入
- **THEN** 累计成果、近两周变化和更新时间显示 `—`，并明确显示“数据待接入”
- **AND** 页面不得显示虚构数字、虚构趋势或把待接入状态展示为真实 `0`
- **WHEN** 已接入的成果统计暂时不可用
- **THEN** 页面显示“统计暂时不可用”，并保持成果卡结构稳定

#### Scenario: 首页展示已接入的准确成果数据
- **WHEN** 某个已开放模块获得已确认口径的累计成果、近两周变化和更新时间
- **THEN** 首页按中文数字格式展示准确累计值、带符号的近两周变化和明确更新时间
- **AND** 页面只展示聚合统计，不显示案件名称、人员、设备编号或其他敏感明细

#### Scenario: 案件工作台和审核编辑页合并主内容滚动条
- **WHEN** 用户进入案件工作台或审核编辑页，且页面内容超过视口高度
- **THEN** 页面主内容只使用 `PlatformShell` 内容区作为垂直滚动容器
- **AND** 浏览器文档不因默认外边距或根节点溢出额外产生第二条页面滚动条
- **AND** 侧栏和审核编辑页底部操作栏的现有定位行为保持不变

#### Scenario: 电子数据检查导航入口默认进入案件工作台
- **WHEN** 用户访问 `/electronic-inspection` 或点击侧栏一级“电子数据检查笔录”
- **THEN** 系统进入 `/electronic-inspection/workbench`
- **AND** 直接访问 `/electronic-inspection` 时保留查询参数和 hash
- **AND** 平台总首页的成果展示及电子数据检查下的其他二级功能保持可用
- **AND** 系统不再展示独立的电子数据检查模块首页

#### Scenario: 案件工作台提供紧凑的来源目录校验控制项
- **WHEN** 用户进入案件工作台
- **THEN** 页面标题区右上角显示紧凑的来源目录校验控制项
- **AND** 用户可以在该处开启或关闭来源目录授权校验
- **AND** 选择结果继续使用既有浏览器持久化偏好，并用于后续首次登记和重新登记请求
- **AND** 刷新、上传目录、分页和案件卡片操作保持可用

#### Scenario: 附件2按检材顺序展示双图片槽位
- **WHEN** 用户在审核编辑页查看或编辑附件2检材照片
- **THEN** 页面按照审核后的检材顺序显示检材分组，每个检材固定展示“图片 1”和“图片 2”两个槽位
- **AND** 已有图片仍按扁平有序列表每两张归入一个检材组，图片持久化、`photo_groups` 映射和 Word 导出合同保持不变
- **AND** 用户只能从当前有序列表的下一个空槽继续添加图片；删除已有图片后，后续图片按既有顺序前移并重新对应检材，不允许产生隐藏的中间空槽
- **AND** 检材不足以容纳已有图片时，多余图片必须显示为待处理图片并允许删除，不得静默隐藏
- **AND** 没有检材时页面提示先添加检材，不提供无归属图片上传入口；已有无归属图片仍作为待处理图片显示并允许删除
- **AND** 页面显示“每个检材对应两张图片，按检材顺序依次对应。”，不把正反面语义强加给图片槽位

#### Scenario: 收起附件2图片完整展示并查看逐检材完成度
- **WHEN** 用户点击附件2的收起图标按钮
- **THEN** 页面隐藏图片缩略图、双图片上传槽位和批量导入操作，仅按审核后的检材顺序展示各检材的图片完成度摘要
- **AND** 每个检材根据当前有序图片列表分别显示 `0/2`、`1/2` 或 `2/2`，使未填写、部分填写和填写完整三种状态可区分
- **AND** 用户点击展开图标按钮后恢复既有完整展示和全部上传、删除操作，收起或展开不得修改图片列表、检材映射或保存状态
- **AND** 展开/收起按钮只显示图标，不同时显示文字；鼠标悬浮或键盘聚焦时提示当前可执行的“展开图片”或“收起图片”动作，并提供同义可访问名称和明确的展开状态

#### Scenario: 批量导入使用纯图标入口
- **WHEN** 附件2处于展开状态且存在可归属的检材
- **THEN** 批量导入按钮只显示导入图标，不同时显示“批量导入图片”文字
- **AND** 鼠标悬浮或键盘聚焦时显示“批量导入图片”提示，并以同义可访问名称保留键盘和辅助技术可发现性
- **AND** 点击图标继续打开既有多图片选择流程，文件格式、数量、排序、容量和错误反馈规则保持不变

#### Scenario: 审核编辑页保留真实交互语义
- **WHEN** 用户进入审核编辑页
- **THEN** 页面显示真实案件摘要、待核对提示、保存状态和结构摘要 Drawer，不重复显示三步工作进度条
- **AND** `Esc`、`Ctrl+S`、底部操作栏和重复操作保护只触发已实现的当前页面行为，不伪造服务器保存或 Word 最终版式

#### Scenario: 审核编辑页底部操作使用纯图标按钮
- **WHEN** 用户查看审核编辑页底部操作栏
- **THEN** 返回、保存和导出操作的按钮表面只显示含义对应的图标，不显示原文字说明
- **AND** 每个按钮通过悬浮提示和无障碍名称提供完整操作名称
- **AND** 保存中、导出中、禁用、返回、保存和导出行为保持不变

#### Scenario: 全局外壳和审核页移除重复展示
- **WHEN** 用户进入统一平台外壳中的任一页面
- **THEN** 主内容区上方不显示包含“笔录自检平台（文枢）”和当前模块标题的独立顶部横栏
- **AND** 平台侧栏及其父子导航保持可用
- **WHEN** 用户进入审核编辑页
- **THEN** 页面不显示“案件工作台 / 审核编辑 / 导出 Word”三步工作进度条
- **AND** 页面不显示单独的“文号来源”行或页面级“字段来源”说明块
- **AND** 案件摘要、待核对导航、表单编辑、保存、归档和 Word 导出行为保持不变

#### Scenario: 使用右侧随屏栏展示四部分必填进度与待核对项
- **WHEN** 用户进入审核编辑页
- **THEN** 系统默认显示不长期遮挡编辑区的可拖动“进度 N/4”入口，入口在超宽屏下利用主表单右侧空白定位，不在页面顶部横向吸顶且不压缩主表单现有宽度
- **AND** 系统根据当前报告中的必填空缺实时显示 `N/4` 填写进度；某部分没有必填空缺时以绿色显示“必填已齐”，存在空缺时显示“缺少 N 项”
- **AND** 格式错误继续作为待核对提醒展示但不冒充必填空缺；检材完整性未人工确认时作为“一、绪论”的未完成条件并阻止右侧进度显示为绿色完成；“附件”汇总附件章节和页面上方首个光盘编号的提醒
- **AND** 存在检材且附件2任一双图片槽位未填充时，“附件”显示聚合的检材照片缺失项和剩余张数，补齐图片后该项消失
- **AND** 点击四部分标题时展开并定位到对应章节，点击具体提醒时继续定位到字段，目标不得被侧栏或底部操作栏遮挡
- **AND** 无论桌面分辨率或浏览器缩放比例如何，导航都只在用户点击入口后临时展开，并提供可立即收起的操作
- **AND** 四部分均无必填空缺且没有其他待核对项时，导航仍显示 `4/4` 和四部分绿色状态
- **AND** 必填空缺继续由当前报告派生；检材完整性确认使用既有案件草稿 `FieldState` 持久化，不写入报告或 Word，不新增后端端点、数据库字段或导出门控

#### Scenario: 人工确认检材列表完整性

- **WHEN** 用户进入审核编辑页且当前案件草稿尚未记录检材列表完整性确认
- **THEN** “（五）检材情况”显示红色“请确认检材是否完整？”按钮，右侧“一、绪论”和总进度不得显示为绿色完成
- **WHEN** 用户点击该按钮
- **THEN** 系统将检材列表完整性以既有 `FieldState` 标记为 `confirmed` 并保存到案件草稿，按钮消失，右侧进度按其他未完成项重新计算
- **AND** 用户增删、排序或修改任一检材后，既有完整性确认恢复为 `pending`，按钮和非绿色进度提示重新出现
- **AND** 按钮支持键盘操作、只读禁用和文字状态表达，不只依赖颜色

#### Scenario: 用户直接拖动待核对入口
- **WHEN** 审核编辑页存在待核对项，且用户直接拖动收起状态的右侧“待核对”入口
- **THEN** 浮层跟随 Pointer 操作移动并始终限制在当前可视区域内
- **AND** 用户无需先展开清单即可拖动，拖动结束不误触发展开；普通单击仍展开清单
- **AND** 展开和收起清单时以竖向“待核对”入口为位置基准，入口不得发生横向跳动
- **AND** 新位置在当前审核页面会话内保持，重新进入页面时恢复默认位置
- **AND** 用户可通过键盘操作将浮层重置到默认位置
- **AND** 拖拽位置不写入报告、草稿、浏览器持久化或服务端

#### Scenario: 待核对项精确定位到对应字段
- **WHEN** 用户点击任一待核对项
- **THEN** 系统使用该项的稳定字段级目标定位到对应字段或编辑块，并以焦点或短暂高亮标明落点
- **AND** 目标章节折叠时先展开章节再定位
- **AND** 字段目标暂时不存在时安全回退到对应章节，不抛出页面错误
- **AND** “光盘编号”定位到页面上方归档/盘号区域的“首个光盘编号”输入，不定位到底部附件章节

#### Scenario: 人工检材类型确认后清除重复待核对项

- **WHEN** 用户人工添加检材并把检材类型确认为手机或平板，且确认状态和来源有效
- **THEN** 待核对清单不再因兼容字段 `device_type` 为空而保留该检材的“设备类型”提示
- **AND** 未确认、非法确认来源或真实必要字段为空时仍按既有规则显示对应提示或导出阻断

#### Scenario: 案件简要人工核对提示使用紧凑标题标记
- **WHEN** 用户审核案件简要情况
- **THEN** 字段标题右侧以红色显示“（请注意人工核对）”
- **AND** 页面不再为报告解析准确性提示单独占用一整行
- **AND** 内容末尾存在空格、制表符或换行时仍单独显示删除多余空白的警告，没有尾部空白时不显示该警告

#### Scenario: 委托单位前缀与委托单位并排展示
- **WHEN** 用户在桌面宽度下审核委托单位信息
- **THEN** 字段标题显示为“委托单位前缀”，不显示“（共享默认值）”，并与“（一）委托单位”在同一行左右分栏展示
- **AND** 两个字段继续独立编辑和保存，不改变共享默认值或报告识别单位语义
- **AND** 可用宽度不足时两个字段自动回落为上下布局且不产生横向溢出

### Requirement: REQ-030: 归档介质编号由用户填写并按归档模式映射

介质编号可在压缩前或压缩后由用户在审核编辑界面以完整字符串输入。光盘、硬盘编号同时支持原有格式与日期后带两位数字用户标识的新格式；标准分卷按 part 顺序生成光盘编号全序列，超大单卷只映射一个硬盘编号。系统不得自动补写或删除用户标识。

#### Scenario: 压缩前未填盘号仍可压缩
- WHEN 用户未填写首个光盘编号即启动压缩
- THEN 系统仍按固定体积分卷执行压缩，压缩阶段不因缺少盘号失败
- AND 案件进入「待补盘号」中间态，卡片显示未填盘号提示并提供补填入口

#### Scenario: 压缩后输入首个盘号自动映射
- WHEN 压缩完成后用户输入首个光盘编号
- THEN 标准分卷系统校验盘号格式与日期，同时接受 `GPyyyyMMdd-序号` 和 `GPyyyyMMddXX-序号`（`XX` 为两位用户标识），按 part 顺序自动生成全序列并一一映射到各 RAR
- AND 映射结果持久化，案件从「待补盘号」转为「归档完成」候选
- AND 盘号仍可按 REQ-018 约定在案件内唯一前提下由用户修改，允许不连续，刻录日期独立保存

#### Scenario: 超大单卷输入硬盘编号
- WHEN 压缩前归档输入总量超过 `225 × 1024³` 字节并生成 `oversized_single_volume`
- THEN 审核编辑界面必须提示用户输入一个 `YPyyyyMMdd-序号` 或 `YPyyyyMMddXX-序号` 硬盘编号，其中可选的 `XX` 为两位数字用户标识
- AND 系统只把该用户输入编号映射到唯一完整 RAR，不自动生成后续编号
- AND `GP` 光盘编号不得使该案件进入映射完成态，编号为空时仍允许先执行压缩

#### Scenario: 归档完成或已导出后修改介质编号
- WHEN 案件已经归档完成或已导出，用户修改当前介质编号并重新提交
- THEN 审核编辑界面保持可用的编号编辑入口，并以当前持久化映射作为输入初值
- AND 系统按当前归档模式重建并持久化 RAR↔介质编号映射，不重新压缩 RAR
- AND 提交必须携带界面读取映射时的 plan 行 revision；过期 revision 必须拒绝，不能静默覆盖另一页面的新映射
- AND 修改后的映射用于后续单独 Word 导出和统一导出

#### Scenario: 压缩前已填盘号保持现行为
- WHEN 用户在归档模式尚未确定时提前填写介质编号
- THEN 审核编辑界面以单个“介质编号”完整字符串输入提示同时接受 GP/YP 的 `yyyyMMdd-序号` 与 `yyyyMMddXX-序号` 格式，不得把合法 YP 提前标记为光盘格式错误
- AND 模式确定后只保留与模式匹配的编号：标准分卷按 part 顺序生成 GP 序列，超大单卷保留唯一 YP 编号；前缀不匹配时提示用户改填但不使压缩失败
- AND 后填与先填两种路径最终得到一致的 RAR↔介质编号映射

#### Scenario: 固定介质前缀生成一致的 Manifest 日期与序列
- WHEN 用户按归档模式以 `GP` 或 `YP` 介质前缀，并以合法日期、可选两位用户标识和序号启动归档
- THEN 系统必须从同一次结构化编号解析结果取得日期；标准分卷生成全部连续光盘编号，超大单卷只保留一个硬盘编号，不得按固定字符位置截取日期
- AND 每个实际 RAR 的 `disc_number`、`disc_date` 与发布前复核使用同一序列事实源，多分卷归档必须完成发布
- AND 非法日期、非法编号或与归档模式不匹配的介质前缀仍按稳定错误拒绝

### Requirement: REQ-031: 归档完成与已导出状态机

归档完成态、导出路径提示、已导出标记与阶段主操作。

#### Scenario: 全部对应完成后进入归档完成态
- WHEN 全部 RAR 完成、全部 MD5 计算完成且所有盘号映射完成
- THEN 案件进入既有 `archive_complete` 状态，工作台展示为「待导出」
- AND 卡片以「统一导出」为唯一推荐操作；提示只在盘号补齐后出现，未补齐时保持「待补盘号」并推荐打开案件
- AND 「待导出」阶段的更多菜单同时提供「打开案件」与「删除案件」；打开案件进入既有审核编辑路由，不触发统一导出，也不改变案件状态

#### Scenario: 导出成功后标记已导出
- WHEN 统一导出写入用户路径成功
- THEN 案件卡片标记为「已导出」
- AND 「已导出」状态 Tag 使用现有设计系统的成功语义绿色，不新增硬编码状态配色
- AND 卡片以「删除案件」作为唯一推荐操作，并在更多菜单保留「打开案件」与「再次导出」
- AND 导出请求期间只使用当前页面按钮 loading 并禁止重复提交，不新增持久化「导出中」状态

#### Scenario: 统一删除仅删平台内产物
- WHEN 任意状态案件通过当前阶段入口执行「删除」并完成确认
- THEN 复用 `case-workbench-delete` 能力，确认后删除案件记录及平台内受控产物（解析缓存、归档快照、压缩 RAR、导出记录）
- AND 已导出案件不额外提供「彻底删除」菜单项
- AND 案件绑定的 `.inputs`、`.i` 或 `.t` 快照目录及其 `.copying` 临时目录、owner marker 一并清理
- AND 用户导出路径下的外部副本不被删除；外部原始资料目录不属于平台删除范围

#### Scenario: 最终 lifecycle 优先于历史任务详情
- WHEN 案件 lifecycle 为 `exported`，但最近任务摘要仍含阶段 8/9、阶段 9/9、正在写入 Manifest 或归档活动文字
- THEN 卡片只展示「已导出」、导出完成时间与删除案件推荐操作
- AND 不展示历史阶段、Manifest 活动、归档状态或重复的已导出文案

#### Scenario: 案件卡片按阶段只提供一个推荐操作
- WHEN 案件卡片展示解析中、解析失败、待处理、压缩/归档中、待补盘号、待导出或已导出阶段
- THEN 实际可见的推荐操作依次为无、重试解析、打开案件、打开案件、打开案件、统一导出、删除案件
- AND 待导出阶段虽在更多菜单保留「打开案件」，但其仍是次要操作，不计为第二个推荐操作
- AND 测试按各阶段实际可见操作名称断言，不以按钮 `type` 属性代替业务操作断言

### Requirement: REQ-ARCHIVE-PHOTO-BINDING: 后台归档期间图片引用独立收敛

图片二进制上传后，系统 MUST 以调用方最后观察到的图片 ID 列表作为图片域 CAS 基线，把图片引用绑定到最新案件草稿；后台归档或普通字段保存引起的无关 revision 推进不得形成永久 409。

#### Scenario: 非图片字段或归档完成推进草稿 revision
- WHEN 图片二进制已上传成功，且后台归档完成回填或其他非图片字段保存已推进案件草稿 revision
- THEN 图片绑定读取最新案件草稿，只合并 `asset_refs`、`photo_ids` 与按最新已保存检材顺序生成的 `photo_groups`
- AND 后端对非图片 revision 竞争执行有界 CAS 重试，保留最新草稿中的归档可信字段与其他审核字段
- AND 成功响应返回最新草稿 revision，前端据此重基本地仍未保存的普通编辑，不再循环提交旧 revision

#### Scenario: 另一会话已经修改图片列表
- WHEN 请求携带的已观察图片 ID 基线与服务端当前图片 ID 列表不同
- THEN 后端返回稳定的图片绑定冲突，不得静默覆盖另一会话的图片增删或排序
- AND 已上传但未绑定的图片继续按既有孤儿保留期恢复，不得冒充已进入案件草稿

#### Scenario: 图片绑定失败时保持离页保护和重试基线
- WHEN 图片二进制上传成功但字段级绑定因租约失效、图片资产无效或真实图片域冲突而失败
- THEN 前端保留当前图片输入并阻止离开案件，显示可区分的失败原因
- AND 重试仍以最后一次成功绑定的图片列表为基线，不重复上传相同二进制

### Requirement: REQ-ARCHIVE-IMMUTABLE-INPUT: 用户确认边界下的单次直接源 inventory

用户明确确认压缩期间不会修改、移动、删除源目录或继续写入后，新归档尝试 MUST 直接读取已授权源目录。系统 MUST 只构建一次完整输入 inventory 供容量规划、Manifest 输入统计和 WinRAR 执行使用，不得复制全量快照，也不得在来源复核、归档提交、WinRAR 前后或 Manifest 读取阶段重复递归扫描同一目录。

#### Scenario: 直接压缩快速进入后台
- WHEN 来源核心身份可用且用户确认立即压缩
- THEN 归档决策请求快速创建后台任务并结束 loading
- AND 完整输入 inventory 在归档 Worker 中构建，工作台列表、案件详情和其他 HTTP 请求保持可用
- AND 同一 attempt 在 WinRAR 启动前只构建一次完整 inventory

#### Scenario: 输出准确性门保持
- WHEN WinRAR 完成直接源压缩
- THEN 系统仍执行 RAR 完整性测试、连续分卷与容量校验、每卷 MD5、Manifest/发布身份和最终产物存在性校验
- AND 任一输出校验失败不得标记归档完成或允许统一导出
- AND 输入 inventory 的文件数、总字节数和路径元数据来自本次 Worker 的唯一完整枚举

#### Scenario: 同一次新归档复用内部 MD5
- WHEN RAR 完整性测试通过且 Worker 为本次新生成的每个 part 组装 Manifest
- THEN 每个 part 只执行一次完整内容 MD5，并将该摘要绑定到 durable publish intent、Manifest 和精确文件集合
- AND 同一 attempt 后续密封、原子发布、索引与完成提交复用该可信摘要，同时继续核对目录边界、文件类型、文件名集合、顺序、精确字节数和已哈希文件的稳定身份元数据

- AND 发布切点观察到文件缺失、替换、增删、字节数变化或同大小文件身份/时间变化时仍必须安全失败

#### Scenario: 结果展示不重复读取大文件内容
- WHEN 已完成案件读取归档结果以展示 part、MD5 和盘号映射
- THEN 后端验证 task/attempt/deployment、durable publication digest、Manifest 身份以及物理文件的存在性、类型、名称集合和精确字节数
- AND 普通结果展示不得再次对全部 RAR 执行内容 MD5，也不得阻塞工作台事件循环
- AND 结果展示不是正式文件授权；下载、统一导出、恢复与跨 attempt 复用仍执行现有完整内容校验，发现同大小内容篡改时必须拒绝

#### Scenario: 审核编辑界面不提供单卷 RAR 下载
- WHEN 审核编辑界面的附件区域展示已完成的真实 RAR 归档信息
- THEN 页面继续展示各卷文件名、大小、MD5、分卷序号、光盘编号和验证状态
- AND 不显示「下载该 RAR」按钮，民警通过案件统一导出获取 RAR 产物
- AND 后端既有受控分卷下载能力及其他兼容入口保持不变

#### Scenario: 用户在压缩期间修改源目录
- WHEN 用户违反确认并在 inventory 或 WinRAR 执行期间修改、移动、删除或继续写入源目录
- THEN 系统不承诺通过额外的压缩前后全目录扫描检测该变化
- AND WinRAR 或输出完整性校验观察到的错误仍必须安全失败，不得伪造成功

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

### Requirement: REQ-GUIDED-REVIEW-SHELL — 默认对话式审核外壳

案件审核页面 MUST 在不改变现有业务事实、保存、归档、介质映射和导出机制的前提下，默认以对话式引导视图呈现当前用户可处理事项、系统处理状态和恢复入口；现有完整审核编辑能力 MUST 保留并可按需切换。

#### Scenario: 案件审核默认只展示对话式引导外壳

- **WHEN** 用户从案件工作台打开具有可审核草稿的案件，或刷新该案件审核地址
- **THEN** 页面默认只渲染对话式引导视图，不渲染现有完整审核编辑表单
- **AND** 引导视图以用户任务语言展示当前可处理事项、系统处理状态和恢复操作，不要求用户理解 `CaseDraft`、Manifest、Export Gate、revision 或分卷档位等内部术语
- **AND** 默认模式只属于当前页面展示状态，不写入报告、案件草稿、浏览器持久化或服务端
- **AND** 解析中、解析失败或尚无可审核草稿的案件继续使用现有状态和恢复入口，不伪装成可填写的对话步骤

#### Scenario: 上方展示历史处理轨迹且下方承载当前对话

- **WHEN** 对话式引导视图存在已经完成、自动处理、正在后台处理或当前需要用户操作的事项
- **THEN** 审核工作区纵向分为上方历史处理区和下方当前对话区
- **AND** 上方历史处理区按办理顺序展示已经完成的用户操作、系统自动沿用的信息摘要、后台任务阶段变化和已经恢复的异常，不重复展开完整审核表单
- **AND** 下方当前对话区始终承载当前推荐事项的说明、结构化控件和主要操作；没有用户事项时显示等待后台处理、办理完成或现有恢复入口
- **AND** 历史处理区独立滚动且占用剩余可用高度，当前对话区保持在审核工作区底部可见，不被历史内容推离视口，也不得遮挡平台导航或现有全局操作
- **AND** 窄屏和浏览器缩放下仍保持历史在上、当前对话在下的单列顺序，当前对话不得覆盖历史最后一条记录

#### Scenario: 历史处理轨迹不成为新的业务事实

- **WHEN** 页面把现有案件状态投影为历史处理记录
- **THEN** 当前页面会话可以保留本次操作的展示顺序，但不得新增持久化对话消息、办理历史表或案件业务字段
- **AND** 刷新或重新进入案件时，历史处理区根据当前 CaseDraft、FieldState、生命周期、归档和介质映射等现有事实重建办理摘要，不承诺还原逐字对话、精确操作时间或已经失效的中间状态
- **AND** 历史记录只描述用户可理解的办理结果，不展示内部路径、令牌、revision、Worker、堆栈、完整错误代码或技术日志
- **AND** 用户查看较早记录时，新后台状态不得强制把滚动位置拉回底部；只有用户仍位于历史末端时才可以跟随最新记录

#### Scenario: 对话外壳只投影现有事实和现有操作

- **WHEN** 对话式引导根据当前案件生成操作卡片
- **THEN** 卡片只来自当前 `InspectionReport`、既有 `FieldState`、既有待核对派生结果、案件生命周期、归档完成投影、图片状态、来源状态、编辑租约和现有导出反馈
- **AND** 对话层不新增 RequiredAction 后端接口、数据库表、案件字段、持久化对话历史、业务必填规则、确认规则或导出门控
- **AND** 用户在卡片中的操作继续调用现有字段更新、自动保存、图片绑定、来源重选、压缩决定、介质映射和 Word 导出能力
- **AND** 卡片是否消失完全由现有事实重新派生，不单独保存“已处理”或“已完成”标记

#### Scenario: 已由报告或默认设置确定的信息不重复询问

- **WHEN** 报告解析、案件草稿初始化或笔录默认设置已经提供符合现有规则的字段值
- **THEN** 对话式引导不为这些字段生成确认卡片或机械的“确认并继续”步骤
- **AND** 已由默认设置带入且信息完整的检查人员、检查地点、检查方法和硬件设备直接沿用现有案件快照与顺序
- **AND** 已生成的文号、已确认的检材信息和主取证软件继续沿用现有值；只有既有待核对或导出反馈指出缺失、格式错误、未确认或冲突时才展示对应操作
- **AND** 用户可通过“查看已整理信息”查看摘要并主动进入修改，但查看、展开或收起摘要不得修改任何业务数据

#### Scenario: 系统处理中间结果不冒充人工问题

- **WHEN** 后台压缩、完整性校验、MD5 或 Manifest 生成仍在执行，且 RAR 文件名、文件大小、MD5、实际卷数或介质模式尚未形成最终事实
- **THEN** 对话式引导把这些内容展示为系统处理状态，不要求用户手工填写系统产出字段
- **AND** 归档状态继续使用现有 `workflow_milestone`、阶段文字、运行时间、输出字节数和检测分卷数，不把活动指标换算为 WinRAR 连续完成百分比
- **AND** 系统状态与当前可处理的用户事项分区展示，后台状态变化不得抢走或清空用户正在操作的卡片

#### Scenario: 复用现有压缩决定和介质编号机制

- **WHEN** 案件处于现有压缩时机选择状态
- **THEN** 引导视图以简明说明展示“现在开始（推荐）”和“稍后处理”，并明确稍后处理对当前办理结果的现有影响
- **AND** 两个操作继续调用现有立即/稍后压缩入口，不改变来源确认、任务创建、资源调度、重试或案件生命周期
- **WHEN** 现有归档完成投影要求补充介质编号
- **THEN** 标准分卷继续使用现有首个 `GP` 光盘编号映射，超大单卷继续使用现有唯一 `YP` 硬盘编号映射
- **AND** 引导视图不得让用户选择 4GB、22GB 或 45GB 档位，也不得改写现有容量规划、盘号 CAS 或 Manifest 事实

#### Scenario: 在引导模式和完整审核编辑之间无损切换

- **WHEN** 用户在默认引导视图点击“完整审核编辑”
- **THEN** 页面切换为现有完整审核编辑视图，并提供“返回引导模式”入口
- **AND** 两种视图共用同一个案件会话、内存草稿、自动保存、编辑租约、图片资产、归档状态和导出操作，不复制或转换业务数据
- **AND** 同一时刻只渲染当前选中的视图；完整审核编辑器不得以 CSS 隐藏方式在引导模式后台同时渲染
- **AND** 模式切换不得丢失当前已输入内容、重启归档、重复上传图片、触发额外业务确认或改变案件生命周期
- **AND** 只读、租约失效、保存失败和图片尚未绑定的现有保护语义在两种视图中保持有效

#### Scenario: 引导视图保留全局控制而非强制单线问答

- **WHEN** 当前同时存在多个用户可处理事项或后台任务
- **THEN** 页面在下方当前对话区推荐一个当前事项，同时提供“查看全部待处理事项”“查看已整理信息”“完整审核编辑”和“返回案件列表”入口
- **AND** 用户可以从全部待处理事项进入任一现有字段或操作，不被强制锁定在固定的一题一页顺序中
- **AND** 页面分别表达“需要用户处理”的数量与“系统正在处理”的状态，不使用可能因异步变化产生倒退含义的固定“问题 X / Y”总进度
- **AND** 新出现的介质编号或恢复事项先进入上方历史处理区和待处理列表，在当前输入收敛后才成为下方当前对话，不突然替换用户正在编辑的内容

#### Scenario: 最终生成继续由现有保存与导出门控裁决

- **WHEN** 引导视图根据现有派生结果没有发现当前可处理的待核对事项
- **THEN** 页面可以展示“笔录已准备完成”和现有生成入口，但不得把对话层状态作为正式导出许可
- **AND** 用户点击生成后继续等待现有图片绑定和自动保存收敛，并调用现有 Word 导出或统一导出流程
- **AND** 现有 Export Gate、模板校验、归档校验或最新 revision 返回阻断时，页面以可操作的用户语言展示原有错误并返回对应现有操作，不绕过、放宽或复制门控
- **AND** 单独 Word 与统一导出的图片、归档和介质要求继续遵守各自现有合同，对话外壳不得把两种输出的条件合并成新的统一规则

#### Scenario: 对话助手保持专业、可访问且不阻断办理

- **WHEN** 引导视图展示獙豸助手、状态文案和操作卡片
- **THEN** 助手使用简洁、明确、专业、亲和且克制的办理语言，优先说明推荐操作及其影响
- **AND** 角色图像缺失、加载失败、动画关闭或用户启用减少动态效果时，全部文字、状态和操作仍保持可用
- **AND** 成功、警告、错误、只读和处理中状态不得只依赖角色表情、颜色或动画表达
- **AND** 历史处理区与当前对话区具有明确区域名称，键盘可以进入历史记录和当前控件，焦点、可访问名称、窄屏布局和现有快捷键行为保持可用

## 存储路径

### Requirement: REQ-ARCHIVE-STORAGE-SETTINGS

The deployment MUST allow the user to move RAR staging and durable archive generations away from the default application-data volume while retaining controlled-path and same-filesystem publication guarantees.

#### Scenario: select a custom archive storage directory
- **WHEN** the user opens archive storage settings from either expanded or collapsed platform navigation and selects an existing writable local directory
- **THEN** the deployment persists the selection and shows its dedicated `文枢归档工作区` child as the restart-bound destination
- **AND** after restart, new archive staging, verified RAR parts, Manifest projection, recovery and case cleanup use that configured archive root without moving completed parts back to the default system volume
- **AND** ordinary case data, uploaded images, logs and Word exports remain in their existing application-data locations

#### Scenario: configured archive storage is unavailable or unsafe
- **WHEN** the configured parent is missing, unwritable, or its dedicated workspace overlaps the packaged program resource root
- **THEN** the application exposes a stable actionable settings error and refuses to begin a new archive there
- **AND** it does not silently redirect that task to the default system volume

#### Scenario: apply or reset a restart-bound setting
- **WHEN** the user selects a different directory or restores the default
- **THEN** the settings surface distinguishes the active directory from the directory that will apply after restart
- **AND** no running archive is migrated, while verified archives under the previous/default root remain resolvable for result viewing, export and explicit case cleanup

#### Scenario: settings entry follows existing sidebar controls
- **WHEN** the platform sidebar is expanded or collapsed
- **THEN** the settings control uses the existing footer-button size, radius, shadow, hover and focus treatment
- **AND** its collapsed form retains the accessible name and right-side tooltip `归档存储设置`

| 用途 | 路径 |
|------|------|
| 解析缓存 | `output/parsed/`（本地，不得进入 Git） |
| 归档文件 | 默认 `output/compressed/`；配置后为所选目录下 `文枢归档工作区/compressed/`（本地，不得进入 Git） |
| 归档登记索引 | 与归档文件同根的 `compressed/.archive-manifest-index.json`（本地，不得进入 Git；与解析缓存独立） |
| 导出 .docx | `output/exports/`（本地，不得进入 Git） |
| 硬件设备配置 | `packages/backend/app/data/hardware_devices.json` |

## 跨功能约束

- **MUST**: API 响应字段名用 camelCase，Python 内部用 snake_case，Controller 层做转换
- **MUST**: 当前正式输出是 legacy DTO 管线；`template_filler_service.py` 是带最终 Manifest 的正式渲染路径，失败时不回退；officecli batch 只保留为无 Manifest 兼容回退
- **MUST**: 生成的 .docx 使用案件明确引用且当前重新校验通过的 approved 模板版本；没有模板引用的 Legacy 兼容案件使用 `word_templates/template.docx`（`current-template-v1` TemplateProfile）；渲染失败时必须明确报错，不得静默切换版本或回退
- **MUST**: 基于 AGENTS.md 治理规则，Level 1 小修改无需 OpenSpec change；架构或公共合同变更仍需完整流程
- **MUST**: `rar_info` 是 ParseReportResponse 的旧兼容字段（`RarInfo | null`）；其 null/空值/零值不由 deprecated `compress` 参数可靠决定，也不代表最终归档状态
- **MUST**: 解压操作仅存在于 BE_Repository 层（`file_storage.py`）
- **MUST**: 软件工具列表由报告来源与运行环境共同生成；新解析案件和存量案件均显示 WinRAR 与 HashMyFiles（旧 Python hashlib 数据仅作底层兼容），WinRAR 未检测到时不伪造默认版本，主软件候选不完整时保持未确认
- **MUST**: 主软件只从 `data_report_info.json.contents[].value` 的明确主产品句式绑定名称和紧随其后的版本；括号可属于主名称，后续“子模块/插件/组件”的名称和版本不得覆盖主字段
- **MUST**: 新案件草稿的 `entrust_time`（委托时间）不从报告“创建时间”推导，而是在首次初始化时按 `Asia/Shanghai` 当天日期预填为中文纯日期（如 `2026年6月30日`），并允许用户人工修改；已保存案件不得因再次加载而被当天日期覆盖
- **MUST**: legacy `InspectionResult.file_size` 在文件夹解析中只保留空值/零值兼容语义；压缩包直传的实际大小位于 `rar_info.size_bytes`，最终归档大小只以已验证 `ArchiveManifest.parts[].size_bytes` 为准
- **MUST**: 设备解析时优先结构化 JSON，再正则回退；按检材分别读取手机品牌及手机型号/设备型号，以单个空格生成设备名称，型号已含品牌时不重复；“手机”只作为检材类型，品牌和型号均缺失时才参与兜底
- **MUST**: 当前模板附件2中同一检材的两张照片固定在同一表格行的左右两个槽位，单元格边距为零并分别向中间对齐；保持图片比例；模板卫生修改必须发布不可变新版本，退役内置引用按当前迁移合同收敛
- **MUST**: DOCX 生成格式遵循项目模板/构建器定义的标准结构；自动化验证不替代人工视觉验收
- **MUST**: SQLite 只保存案件业务 DTO、任务/租约/revision/索引元数据、SourceRecord 和 opaque 资产引用；图片、来源快照、缓存、临时文件和正式产物保存在受控文件系统资产中，不写入 Base64、完整 HTML、原始 JSON 集合或不可控二进制
