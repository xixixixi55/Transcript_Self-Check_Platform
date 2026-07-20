# Extensible Report and Template Platform Specification

本文件是本变更的规范合同。规范中的“系统”包括报告解析、业务规划、压缩、页面规划、模板渲染和现有兼容 API；阶段标记表示交付边界，不表示阶段二、三在阶段一中自动启用。

## ADDED Requirements

### Requirement: Canonical case normalization

系统 MUST 将每份受支持报告先转换为 `CanonicalInspectionCase`，再进行业务规则计算和文档生成。主迁移方向 MUST 为 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`：`InspectionReport` 是现有公共契约的兼容投影，不是新领域事实来源。规范化结果 MUST 具有稳定的 `caseId`、来源摘要、报告创建/报告时间、案件名称、检材列表、主取证软件、检查人员快照、归档清单和附件输入；原始文件路径和字段来源 MUST 保留在 provenance 中但不得泄漏到用户文书正文。

#### Scenario: 旧格式和新格式统一到同一内部模型

- **WHEN** 系统接收当前已支持的旧格式或新格式报告
- **THEN** `ReportAdapter` 分别读取其既有结构并输出同一套 `CanonicalInspectionCase`，旧报告字段和新报告字段的现有优先级保持不变

#### Scenario: 不支持的结构不能生成部分正确的报告

- **WHEN** 核心文件缺失、结构签名不匹配或必需字段无法得到可靠候选
- **THEN** 系统返回结构化的 `ParseIssue`，不生成可导出的半成品文书、不写入成功缓存，并保留用户可确认的字段候选（如有）

### Requirement: Material identifiers and phone/tablet display policy

阶段一的最终检材类型只允许 `phone` 或 `tablet`。`ReportAdapter` 可以返回候选类型；报告明确且可靠提供类型时可以自动选择，无法可靠判断时 MUST 保持待确认并由审核页面确认。系统不得仅根据是否存在 IMEI 推断类型；每个检材在最终导出前 MUST 完成类型确认。原始 identifiers MUST 保留在 `CanonicalInspectionCase` 中，显示规则只能控制模板可见性。

系统 MUST 将检材表示为 `Material`，并通过通用 `Identifier` 集合承载 `imei1`、`imei2`、`serialNumber` 及未来标识。解析层 MAY 收集原始候选，但最终展示策略 MUST 在规范化后的业务规则层执行：`phone` 只允许显示 IMEI1/IMEI2，`tablet` 只允许显示序列号。设备类型不明确时 MUST 要求确认或阻止导出，不能同时显示两组标识来掩盖歧义。

#### Scenario: 手机只显示两个 IMEI

- **WHEN** `Material.kind` 为 `phone` 且存在一个或两个合法 IMEI
- **THEN** 正文、检查过程和相关模板字段只输出存在的 IMEI1/IMEI2，不输出序列号

#### Scenario: 平板只显示序列号

- **WHEN** `Material.kind` 为 `tablet` 且存在序列号
- **THEN** 正文、检查过程和相关模板字段只输出序列号，不输出 IMEI

#### Scenario: 标识缺失或设备类型有冲突

- **WHEN** 手机/平板无法可靠分类，或分类要求的标识缺失/非法
- **THEN** 系统显示可解释的确认错误并阻止最终导出；不得把解析层发现的全部字段直接交给模板

#### Scenario: 报告明确类型时自动选择

- **WHEN** 报告可靠提供 `phone` 或 `tablet` 类型
- **THEN** 审核页面预选该类型并允许用户复核，原始 identifiers 仍完整保留

#### Scenario: IMEI 存在不能单独判定类型

- **WHEN** 报告只有 IMEI 线索而没有可靠类型来源
- **THEN** 系统不自动选择 `phone`，材料保持待确认并在导出门控中阻止最终导出

#### Scenario: 每个检材都必须完成类型确认

- **WHEN** 任一检材仍为待确认或不属于 `phone`/`tablet`
- **THEN** 上传、解析、审核和中间编辑仍可继续
- **AND** 统一导出门控返回检材类型阻断项
- **AND** 最终正式导出被拒绝

### Requirement: Inspector library and snapshots

当前模板中检查人员按一人一行渲染，默认单文本框格式为 `单位　姓名（警号）`；若人员较多，附件一页面计划可以增加整框高度或为附件一最后一页预留空间，但人员整框始终只出现在最后一页且不得拆页。

系统 MUST 提供单机检查人员库，至少持久化姓名、单位和警号；人员库数据文件 MUST 位于应用数据目录、不得进入 Git；人员库只能由后端 Repository 访问，前端不得直接读取或写入 JSON。每条记录 MUST 有唯一 ID；姓名、单位、警号 MUST 通过非空、去除首尾空白、长度和基础字符校验。一份报告 MUST 能按用户选择任意数量的人员，并保持选择顺序。保存报告时 MUST 复制为有序的 `InspectorSnapshot[]`，历史报告渲染不得随人员库后续修改而变化。Repository 上层接口 MUST 保持稳定，以便后续替换为 SQLite 或服务端存储。

#### Scenario: 选择任意数量并保持顺序

- **WHEN** 用户从单机人员库选择人员并按顺序确认
- **THEN** `CanonicalInspectionCase.inspectors` 与 Word 中检查人员顺序完全一致，允许零人或任意多人（业务校验另有最低要求时单独报错）

#### Scenario: 人员库修改不影响已保存报告

- **WHEN** 已保存报告引用的人员姓名、单位或警号后来在人员库中被修改
- **THEN** 重新预览/导出该报告仍使用其 `InspectorSnapshot`，而不是重新读取当前人员库

#### Scenario: 单机存储损坏

- **WHEN** 人员库文件损坏、字段缺失或写入过程中进程中断
- **THEN** Repository 使用原子写入和上一份有效备份恢复；若无法恢复则只阻止人员库操作，不删除或改写报告数据

#### Scenario: 人员字段校验失败

- **WHEN** 姓名、单位或警号为空、仅含空白、超出允许长度或包含基础校验禁止的字符
- **THEN** Repository 拒绝保存并返回字段级错误，原人员库文件保持不变

#### Scenario: 人员库写入失败

- **WHEN** 临时文件写入、校验、flush/fsync 或原子替换失败
- **THEN** Repository 删除未提交的临时文件并保留原文件，不能返回“保存成功”

#### Scenario: 模板分别绑定检查人员字段

- **WHEN** 当前模板使用多个段落或单元格展示检查人员
- **THEN** `InspectorSnapshot` 保持 `unit`、`name`、`police_number` 等结构化字段，TemplateProfile 分别绑定这些字段；业务模型不得预先拼接展示字符串。单一文本框可由 Profile 配置默认格式 `单位　姓名（警号）`

#### Scenario: 检查人员过多时保持整框

- **WHEN** 检查人员数量超过附件一最后一页的默认可用空间
- **THEN** 页面计划增加人员整框高度或调整最后一页空间
- **AND** 所有检查人员仍按快照顺序一人一行
- **AND** 整框保持在附件一最后一页且不跨页拆分

### Requirement: Report-authoritative software tools

正常情况下主取证软件由报告适配器自动识别；无法可靠识别时，报告 MUST 进入审核页面并将软件名称和版本标记为待确认，用户可以人工填写或修正。主软件确认前允许审核和编辑，但 MUST 阻止最终正式导出；不得使用历史固定软件、不得从普通组件猜测，也不得仅生成 WinRAR 和 Python hashlib 后将文书视为完整。

阶段一系统 MUST 从报告来源得到主取证软件名称和版本，不得用硬编码名称或环境检测值覆盖它。`softwareTools` 只允许包含主取证软件、WinRAR 和 Python hashlib 三类工具；WinRAR/Python 的版本可以来自执行环境，但主取证软件的名称和版本 MUST 以报告为准。

#### Scenario: 报告明确主取证软件

- **WHEN** 报告可靠绑定了主取证软件名称和版本
- **THEN** 规范化模型和正文/工具列表使用报告中的名称与版本，并只保留这三类工具

#### Scenario: 多个主软件候选互相矛盾

- **WHEN** 报告中发现多个不能判定唯一来源的主软件名称或版本
- **THEN** 系统保留候选和 provenance，提示用户确认，不静默选择环境默认值或第一个字符串

#### Scenario: 主软件无法可靠识别时可编辑但不可导出

- **WHEN** 适配器无法可靠识别主取证软件名称或版本
- **THEN** 审核页面允许用户分别填写或修正名称和版本并保留待确认状态
- **AND** 系统不使用历史固定软件或普通组件猜测
- **AND** 主软件确认前最终正式导出被统一门控拒绝，并返回可操作提示

#### Scenario: 仅有执行工具不能视为完整工具列表

- **WHEN** 主取证软件尚未确认而当前只能确定 WinRAR 和 Python hashlib
- **THEN** 工具列表被标记为不完整
- **AND** 系统允许继续审核编辑但禁止最终正式导出

### Requirement: Review remains editable while final export is gated

系统 MUST 通过一个集中导出校验流程判断最终正式导出，而不是由 parser、service、renderer 各自维护阻断逻辑。存在阻断项时，上传、解析、审核、保存和中间编辑仍可用；只有当所有检材类型已确认、主取证软件名称和版本已确认、图片数量合法、首个光盘编号合法、WinRAR 可调用且需要的最终 `ArchiveManifest` 已验证时，才允许正式导出。校验结果 MUST 包含稳定诊断代码和可操作提示，并一次返回适用的阻断项；不得静默降级或掩盖错误。

#### Scenario: 多个阻断项统一返回

- **WHEN** 报告同时存在待确认检材类型、待确认主软件、奇数图片或 WinRAR 不可用
- **THEN** 用户仍可在审核页面编辑并保存中间结果
- **AND** 统一导出校验返回所有适用阻断项及修复提示
- **AND** 最终正式导出被拒绝直到阻断项全部清除

### Requirement: Disc sequence and date authority

系统 MUST 只要求用户填写首个光盘编号，格式为 `GPyyyyMMdd-序号`；系统 MUST 校验日期和序号，并按首个序号的位宽保留前导零生成后续编号。光盘编号日期 MUST 同时作为附件摘要检查日期和附件三刻录日期；正文检查起止时间 MUST 继续来自报告创建时间和报告时间，不得使用光盘日期。

#### Scenario: 多卷连续编号

- **WHEN** 用户输入 `GP20260718-001` 且最终归档有三卷
- **THEN** 生成 `GP20260718-001`、`GP20260718-002`、`GP20260718-003`，附件一/三按同一顺序使用这些编号

#### Scenario: 非法首编号

- **WHEN** 首编号不符合 `GPyyyyMMdd-序号`、日期无效或序号溢出
- **THEN** 系统在规划前返回字段级错误，不执行压缩、不生成 DOCX

### Requirement: Archive input authorization uses opaque contexts

系统 MUST 支持多个配置型允许根目录：`UPLOAD_BASE` 加部署者配置的 `BIJI_ALLOWED_INPUT_ROOTS`。案件目录 MUST 是允许根目录的真实严格子目录，默认不得直接把允许根目录本身作为一个案件输入；不同磁盘和不同案件父目录可以并存，系统不得要求搬迁或复制既有案件。

普通远程请求提交 `report_dir` MUST 不能自动获得信任。当前没有受控本机目录选择桥时，根目录外目录 MUST 返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`。未来精确目录授权只能由受控本机操作产生短期、不可预测、绑定单一具体目录的一次性令牌，令牌不能扩大到父目录、相邻目录或整盘，普通前端不能自行构造。

路径校验 MUST 拒绝空/相对/穿越/UNC/设备路径、symlink、junction、mount point 和其他 reparse point，并检查目录链和每个清单文件；输入目录与输出、staging、cache 互相包含时 MUST 返回 `ARCHIVE_INPUT_OUTPUT_OVERLAP`。创建上下文和调用 WinRAR 前 MUST 再次校验文件清单和指纹；变化返回 `ARCHIVE_INPUT_CHANGED`，不得继续执行。

`report_dir` MUST 标记为 deprecated，仅允许用于创建带随机 UUID 的 `archive_context_id`。上下文公共摘要只能包含标识、文件数、总字节数、状态和时间，不得包含完整本地路径。规划、WinRAR、验证、MD5、Manifest、重试和 DOCX 接口 MUST 只接受 `archive_context_id`；上下文过期、不存在和并发分别返回 `ARCHIVE_CONTEXT_EXPIRED`、`ARCHIVE_CONTEXT_NOT_FOUND` 和 `ARCHIVE_CONTEXT_BUSY`。当前上下文只保存在进程内存中，服务重启后按不存在处理；清理不得删除用户原始输入。

#### Scenario: 配置根目录下不同案件目录

- **WHEN** 用户选择 `UPLOAD_BASE` 或 `BIJI_ALLOWED_INPUT_ROOTS` 下的具体案件子目录
- **THEN** 系统建立上下文并返回不含路径的公共摘要
- **AND** 其他案件目录仍可独立选择，不共享案件授权范围

#### Scenario: 根目录外普通 report_dir

- **WHEN** 普通 API 提交不在配置根目录内的 `report_dir` 且没有受控精确授权令牌
- **THEN** 系统返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`
- **AND** 不建立上下文、不扫描目录、不调用 WinRAR

#### Scenario: 无效的固定根目录配置

- **WHEN** `UPLOAD_BASE` 或 `BIJI_ALLOWED_INPUT_ROOTS` 中包含不存在、相对、不可访问或非目录项
- **THEN** 系统忽略该配置项并记录不含路径的 `ARCHIVE_CONFIGURED_ROOT_INVALID` 安全 warning
- **AND** 不会因为配置无效而放宽为任意 `report_dir`，未获其他根目录授权的案件仍返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`

#### Scenario: 后续接口只接受 archive_context_id

- **WHEN** 归档或 DOCX 导出请求提交客户端路径而没有有效上下文
- **THEN** 系统阻止请求并且错误响应不包含该路径

### Requirement: Archive planning and WinRAR execution are separate

阶段一自动分卷只支持 WinRAR RAR 分卷。未检测到或无法调用 WinRAR 时，系统 MUST 允许上传、解析、审核和编辑报告，但 MUST 禁止自动压缩和最终正式导出；错误提示 MUST 说明需要安装并确保 WinRAR 可调用。系统不得降级生成 ZIP，不得生成虚假的或占位的 `ArchiveManifest`。现有 ZIP/RAR 上传解析能力保持不变，但不替代本次自动分卷产物。

系统 MUST 先生成可审计的 `ArchivePlan`，再由独立执行器调用 WinRAR。`ArchivePlan` 只表示执行前预计档位、预计卷数和目标容量，不能作为 Word 数据来源。分卷档位 MUST 使用十进制 4GB、22GB、45GB：从 4GB 开始，若预计超过 2 卷则升级；45GB 档最多 3 卷；超过 135GB MUST 在执行前阻止处理。案件名称 MUST 作为归档基础名称，分卷 MUST 使用 `.part1.rar` 等标准命名。系统 MUST 设定 `maxReplanAttempts = 2`，表示初始执行后最多允许两次向上重新规划。

公共可序列化 `ArchivePlan` MUST 只包含业务决策、相对输入条目和安全诊断；不得包含输入绝对路径、输出/staging/cache 目录、WinRAR 安装路径或运行时文件映射。上述路径只允许存在于后端内部执行上下文。

#### Scenario: 档位选择

- **WHEN** 输入数据估算为不超过 8GB、超过 8GB 且不超过 44GB、超过 44GB 且不超过 135GB
- **THEN** 规划分别选择 4GB、22GB、45GB 档，并记录十进制目标字节数、预计卷数和最大卷数

#### Scenario: 超过容量上限

- **WHEN** 输入数据估算超过 135GB
- **THEN** `ArchivePlan` 状态为 `blocked`，显示原因，不调用 WinRAR、不写入半成品卷、不进入附件规划

#### Scenario: 归档执行验证

- **WHEN** WinRAR 执行完成
- **THEN** 系统校验卷名、卷号连续性、卷数、每卷实际大小、总卷数上限、文件存在性和每卷 MD5；任一失败都不能提交为最终归档

#### Scenario: WinRAR 不可用时只允许进入审核

- **WHEN** WinRAR 未检测到或无法调用
- **THEN** 上传、解析、审核和编辑仍可用
- **AND** 自动压缩被禁用
- **AND** 系统不生成 `ArchiveManifest`，不生成 ZIP 降级产物
- **AND** 最终正式导出被拒绝并返回可操作的 WinRAR 可用性错误

### Requirement: Archive re-planning uses one final manifest

系统 MUST 将规划和实际执行结果区分保存。若实际结果不符合当前计划，执行器 MUST 在最多 `maxReplanAttempts` 次内丢弃 staging 结果、升级到下一档并重新执行；若重试仍失败、没有可用下一档或达到重试上限，则阻止导出并返回明确错误。重新规划完成后 MUST 生成新的不可变 `ArchiveManifest`，后续附件一、附件三、正文和 DOCX MUST 只引用该 manifest，不得使用预计文件名、预计大小、预计卷数，也不得重新扫描目录或重新计算第二份卷列表。最终 manifest 至少 MUST 包含每卷实际文件名、实际大小、MD5、分卷序号、光盘容量、光盘编号、刻录日期和连续性校验结果。

#### Scenario: 实际压缩结果超出规划

- **WHEN** 4GB 规划实际生成 3 卷，或 45GB 规划实际生成超过 3 卷
- **THEN** 系统在临时目录中重新规划/执行，最多重试两次；最终只保留通过验证的档位结果，并将所有规划尝试写入不含敏感值的诊断日志

#### Scenario: 实际压缩结果少于预计

- **WHEN** 压缩比使实际卷数少于预计但仍满足当前档位限制
- **THEN** 系统保留通过验证的最终 manifest，记录预计与实际差异，不因为推测而修改已生成文件名或附件编号

#### Scenario: 重试耗尽

- **WHEN** 实际结果在最大重试次数内仍不符合计划，或 45GB 档仍超过三卷
- **THEN** 系统返回明确的归档规划错误，不生成 Word、不创建附件页面计划、不提交新的最终归档

### Requirement: Pipeline mode and shadow comparison are centralized

系统 MUST 使用一个集中配置 `pipeline_mode = legacy | shadow | canonical` 控制迁移运行语义，不得在 parser、service 和 renderer 中散落互相矛盾的独立布尔开关。默认值 MUST 为 `legacy`，配置 MUST 在后端应用启动时从统一运行时配置读取并注入管线；模式切换 MUST 记录配置版本和时间。

#### Scenario: Legacy mode

- **WHEN** `pipeline_mode` 为 `legacy`
- **THEN** 旧管线产生唯一正式输出；新 canonical/plan/renderer 不执行正式导出

#### Scenario: Shadow mode

- **WHEN** `pipeline_mode` 为 `shadow`
- **THEN** 旧管线仍产生唯一正式输出；新管线只在隔离目录生成规范化结果、规划和脱敏比较数据，不产生第二份正式文书、不替换正式归档。比较至少覆盖案件字段、检材类型、IMEI1/IMEI2或序列号、检查时间、主软件、检查人员顺序、ArchiveManifest 和附件一/二/三页面数量

#### Scenario: Shadow 不执行真实重复压缩

- **WHEN** `pipeline_mode` 为 `shadow` 且旧管线已产生正式归档
- **THEN** 新管线不得调用 WinRAR 或执行第二次真实压缩
- **AND** ArchiveManifest 比较使用既有正式结果与非执行性的计划/清单投影
- **AND** 不产生第二份正式归档或可被正式导出的新 manifest

#### Scenario: Shadow diagnostics protect sensitive data

- **WHEN** Shadow 比较发现差异
- **THEN** 日志只记录字段名称、是否一致、脱敏来源和诊断代码，不记录完整案件名称、人员姓名、警号、IMEI、序列号或原始 JSON

#### Scenario: Canonical mode

- **WHEN** `pipeline_mode` 为 `canonical`
- **THEN** 新管线产生唯一正式输出；canonical 解析、规划、manifest 校验或 renderer 发生数据正确性错误时直接返回明确失败，不自动静默切回 legacy。人工运维可将集中配置改回 `legacy`

#### Scenario: Mode-aware cache behavior

- **WHEN** pipeline mode 发生切换
- **THEN** 原始解析缓存按 source fingerprint、adapter/schema/profile 版本复用；规划、manifest、render 和正式输出缓存必须按模式/plan/template 版本隔离或失效，不能把 shadow 结果当成正式文书缓存

### Requirement: Attachment one page plan

系统 MUST 先生成 `Attachment1Plan` 再渲染附件一。行数 MUST 等于最终 `ArchiveManifest` 的卷数；每页最多四项；表头只在第一页出现且不得由 Word 自动重复；“附件1”只在第一页；来源框和提取方法框每页分别生成合并框；检查人员整框只在最后一页，并 MUST 设置不可拆页/保持完整。

#### Scenario: 页面规划跨页边界

- **WHEN** 页面规划器接收一个用于跨页边界测试的、已验证的五条 part 记录（该测试 fixture 不代表阶段一允许生成五卷）
- **THEN** 页面计划有两页，行数为 5，第一页 4 行并显示表头和“附件1”，第二页 1 行且不重复表头；两页均有各自来源合并框和提取方法合并框，检查人员框只在第二页

#### Scenario: 归档失败时不生成附件一

- **WHEN** final manifest 尚未通过卷校验
- **THEN** `Attachment1Plan` 不可创建，导出被阻止而不会产生缺少卷信息的空表

### Requirement: Attachment two photo page plan

系统 MUST 先生成 `PhotoPagePlan` 再渲染附件二。0 张图片允许导出且不生成附件二图片页；正数图片数量 MUST 为偶数，否则禁止导出；每页最多四张；四张使用 2×2，二张使用左右布局且在页面上下居中；支持任意偶数数量。每张图片 MUST 在 5.64cm × 7.52cm 框内按比例完整显示，不裁剪、不拉伸。附件二多页时仅第一页显示“附件2”，后续页不重复标题但保持相同图片区域和版式；没有附件二时附件三仍显示“附件3”，不重新编号。

当前模板 MUST 以检材组为附件2的领域单位。每个参与附件2的检材 MUST 绑定恰好两张有效图片；`PhotoPagePlan` MUST 先建立 `MaterialPhotoGroup` 再按检材组分页。每个 `MaterialPhotoGroup` MUST 包含 `material_id`、`material_number`、相关显示文字、两张有序图片和 `source_order`；同一检材的两张图片 MUST 同页左右排列，不得跨页或与其他检材图片交叉。每个 `Attachment2PagePlan` MUST 包含本页的 `material_groups`、`inspection_result_material_numbers` 和布局类型；每页最多两个检材组，每组固定两张图片，两个组按上下区域排列，剩余单组页使用同一可用区域居中布局。

图片归属 MUST 来自审核后明确提交的 `photo_groups` 映射，而不是 Renderer 根据扁平数组位置、文件名或图片方向重新猜测。导出前 MUST 校验每张图片恰好归属一个检材、每组有且仅有两张图片、检材和组内图片顺序稳定、组内图片 ID 覆盖全部实际图片且无孤立图片。页面检查结果文字 MUST 只显示当前页 `inspection_result_material_numbers` 去重后的有序编号；两组时合并显示两个编号，单组页只显示该组编号。

#### Scenario: 0 张图片不生成附件二

- **WHEN** 报告没有图片
- **THEN** 图片数量规则允许导出
- **AND** `PhotoPagePlan.pages` 为空，不生成附件二图片页
- **AND** 若存在附件三，其标题仍为“附件3”而不因附件二缺失重排

#### Scenario: 四张及多页图片

- **WHEN** 用户上传四张或八张图片
- **THEN** 页面计划分别生成一页或两页，每页四张、四张为 2×2，每张图片的 fit mode 为 contain

#### Scenario: 两张图片

- **WHEN** 用户上传两张图片
- **THEN** 两张图片左右排列，每个图片框保持规定尺寸并在页面可用高度内上下居中

#### Scenario: 奇数图片禁止导出

- **WHEN** 用户上传一张、三张或其他奇数张图片
- **THEN** 页面规划返回明确的偶数数量错误，模板渲染器和 DOCX 导出均不执行

#### Scenario: 多页附件二只在第一页显示标题

- **WHEN** 正偶数图片数量大于四张并生成多页附件二
- **THEN** 只有第一页显示“附件2”
- **AND** 后续页面不重复标题并保持相同图片区域和版式

### Requirement: Attachment three follows the final manifest

系统 MUST 为每个最终归档卷生成一页 `Attachment3Plan`；只有第一页显示“附件3”，后续页结构一致但不显示该标题。每页 MUST 使用 manifest 中对应的归档文件、MD5、光盘编号和刻录日期；不得重新从目录或报告原始字段推导这些值。

#### Scenario: 三卷附件三

- **WHEN** final manifest 有三卷且首光盘号有效
- **THEN** 附件三生成三页，三页分别绑定 part1/part2/part3，只有第一页有“附件3”，三页的日期均来自光盘号日期

#### Scenario: 附件一和附件三一致

- **WHEN** 归档执行发生升级重规划
- **THEN** 附件一的行和附件三的页面都引用同一 `ArchiveManifest.parts[].partId`，不会出现卷数、MD5、文件名或编号不一致

### Requirement: Current template is a versioned profile

系统 MUST 将正式模板登记为固定的 `current-template-v1`，由固定 `TemplateProfile` 描述其资产哈希、占位符、表格、VML 文本框、当前受控重复区、图片区、分页和保持完整约束。阶段一 MUST 只支持该 Profile 和当前 DOCX Renderer 的受控扩展；通用模板设计器、通用重复块 DSL、任意 DOCX 自动绑定、可视化模板编辑和无标记模板识别均属于阶段三，阶段一不得实现或静默启用这些能力。

#### Scenario: 选择当前正式模板

- **WHEN** 阶段一导出电子数据检查笔录
- **THEN** `DocumentRenderPlan.templateId` 为 `current-template-v1`，渲染器按 Profile 定位字段并校验模板资产版本

#### Scenario: 模板资产被替换

- **WHEN** 模板路径存在但内容哈希与 Profile 不一致
- **THEN** 导出被阻止并提示模板版本不匹配，不自动使用未知模板

### Requirement: Preserve VML, page breaks, and black text

系统 MUST 在模板渲染时保留当前模板的 VML 文本框、文本框宿主段落、图片关系、普通分页符、页眉页脚结构和表格边框。正文、动态段落、表格动态内容、页眉页脚和 VML 文本框内字体颜色 MUST 统一为黑色；不得用删除宿主段落、奇偶页分节符或重新生成整份模板来实现替换。

#### Scenario: VML placeholder replacement

- **WHEN** `current-template-v1` 中 VML 文本框包含动态占位符
- **THEN** 只替换文本框内部文本并保留 `w:pict`/`v:textbox`/`w:txbxContent` 结构，动态字体颜色为黑色

#### Scenario: Attachment pagination regression

- **WHEN** 生成包含任意偶数图片和多卷附件三的文档
- **THEN** 分页只按 `DocumentRenderPlan` 的普通分页点生效，不产生空白页、奇数页/偶数页分节符或被拆开的检查人员框

### Requirement: InspectionReport compatibility boundary

系统 MUST 保持现有 `InspectionReport` 作为兼容 DTO；主适配方向是 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`。现有前端解析、编辑和导出请求在迁移期间 MUST 继续可用。`InspectionReport → CanonicalInspectionCase` 只作为旧 DTO 输入和历史迁移的 best-effort 入口，不承担 canonical 的完整回填。兼容适配器 MUST 明确无法从旧 DTO 恢复的字段来源、通用 identifiers、`InspectorSnapshot[]`、`ArchiveManifest`、`TemplateProfile` 信息、规划状态和其他新模型字段；不能把 `InspectionReport` 继续作为新领域层的唯一事实来源。

#### Scenario: 旧导出请求

- **WHEN** 现有前端提交 `InspectionReport` 和照片 ID
- **THEN** 后端将其转换为 canonical case，生成规划和 render plan 后导出，现有请求字段和响应下载行为保持兼容

#### Scenario: 新模型包含旧 DTO 不可表示内容

- **WHEN** canonical case 含有旧 DTO 无法表示的多卷、快照或模板配置数据
- **THEN** 兼容投影明确标记不可表示字段，并以 canonical、manifest 和 render plan 为导出事实来源，不静默覆盖关键数据

### Requirement: ReportProfile and provenance reservation

阶段二 MUST 提供 `ReportProfile`、`ReportAdapter`、字段候选和 `FieldProvenance` 的版本化接口。每个确认字段 MUST 保存来源文件、JSON 路径、适配规则、候选/确认状态和置信信息；同类报告的自动复用 MUST 基于结构指纹和适配器版本，不得只按文件名或案件名称匹配。

#### Scenario: 首次遇到新结构

- **WHEN** 结构指纹未命中已有 Profile
- **THEN** 系统执行结构发现并展示字段候选、来源文件、JSON 路径、规则和置信理由，等待用户确认后才保存 Profile

#### Scenario: 同类结构复用

- **WHEN** 新报告与已确认 Profile 的结构指纹、厂商和版本约束匹配
- **THEN** 系统自动使用该 Profile 生成候选 canonical case，并在摘要中显示命中的 Profile 版本和 provenance

### Requirement: TemplateProfile visual configuration reservation

阶段三 MUST 允许用户对 DOCX 的段落、表格、单元格、内容控件和文本框建立标准字段绑定，并描述重复区、图片区、显示条件、分页和保持完整规则。对无占位符普通模板的推荐 MUST 产生带证据的草稿 Profile，用户确认/修正前不得用于导出。

#### Scenario: 可视化绑定保存

- **WHEN** 用户点击模板元素并绑定标准字段、重复区域或图片区域
- **THEN** 系统保存可版本化的 TemplateProfile 草稿，并可回显元素定位、字段路径和格式化规则

#### Scenario: 无标记模板推荐需要确认

- **WHEN** 系统根据标签文本、表格结构、邻近关系和样式指纹推荐字段位置
- **THEN** 每条推荐显示证据和置信度，用户可以逐条接受、修正或撤销；未确认的推荐不能静默套用

## MODIFIED Requirements

### Requirement: 电子数据检查笔录生成

现有电子数据检查笔录 MUST 继续支持当前解析和导出入口。主迁移入口先按 `ReportAdapter → CanonicalInspectionCase → InspectionReport` 生成现有前端/导出兼容 DTO；canonical 管线的正式文档继续由 canonical case → plans → render plan → 固定 `current-template-v1` 生成。现有 `document_builder_service.py` officecli batch 路径在迁移期间作为 legacy 正式路径保留；默认管线切换前必须完成 Shadow 比较、两套输出回归和人工验收。

#### Scenario: 当前报告正常导出

- **WHEN** 用户上传当前旧/新报告、选择人员、输入首光盘号并提供零或任意偶数张图片
- **THEN** 系统完成解析、分卷、三类附件规划和 `current-template-v1` 渲染，输出的正文、附件和卷信息彼此一致

#### Scenario: 任一规划门控失败

- **WHEN** 标识规则、分卷上限、光盘格式、图片偶数校验、模板资产校验或 DOCX XML 校验失败
- **THEN** 导出失败且不提交最终文件；现有报告输入和已保存人员/模板 Profile 保持不变
