# Extensible Report and Template Platform Specification

本文件是本变更的规范合同。规范中的“系统”包括报告解析、业务规划、压缩、页面规划、模板渲染和现有兼容 API；阶段标记表示交付边界，不表示阶段二、三在阶段一中自动启用。

文档真相源边界：本 `spec.md` 记录已批准的业务合同和目标行为；`design.md` 记录设计决策、字段语义与兼容策略；`tasks.md` 记录当前实现、自动化和人工验收状态；`openspec/specs/` 下的 living spec 只描述当前生产已经具备的能力。代码和测试是当前实现证据，用于发现文档漂移，但不会自动改写或取消本规范中已批准的业务规则。

当前生产收口状态（2026-07-23）：正式输出仍由 `InspectionReport` legacy DTO 管线生成。Shadow 已接入真实生产 Controller 的解析、归档/预览和 Legacy DOCX 成功后的导出输入旁路，只用于脱敏观测和比较，不改变现有响应或正式产物；Canonical 仍未接入正式输出，`DocumentRenderPlan` 尚无生产类型、构造器或消费方。本规范中以 canonical 正式输出或 `DocumentRenderPlan` 为前提的场景仍是批准后的目标行为；不得以类型存在、单元测试可调用或 Shadow 旁路接线替代 Canonical 正式切换和真实人工验收证据。

最近生产稳定化事实：旧版报告与同厂商新版报告均由 Legacy 兼容 DTO 输出；解析和清缓存请求有存活性边界；解析缓存只覆盖解析器实际依赖的数据；`ArchiveContext` 的 metadata 使用有 TTL 和容量限制的快照。上述缓存与快照优化不改变正式归档的完整 inventory、全量内容指纹、可读性、符号链接、路径越界及 Manifest/RAR 校验边界。

需求6补充：来源目录根白名单校验保留为可恢复能力，但当前浏览器用户可在电子数据检查笔录首页关闭该校验。首页开关状态持久化在浏览器本地；关闭后允许登记任意满足基础路径安全校验的本机报告目录，开启后恢复配置根目录校验。案件工作台不展示开关。

延期的大容量归档验收只约束发布门槛：它不阻塞 Shadow 真实样本差异治理，也不阻塞 Canonical 代码、只读预览、编辑门控、候选输出隔离或回滚演练的开发与验证；但在验收机器补测通过或发布负责人明确记录风险接受前，Canonical 不得成为默认唯一正式生产输出，本变更不得完成最终验收或 OpenSpec 归档。

## ADDED Requirements

### Requirement: Canonical case normalization

当前 `pipeline_mode` 默认仍为 `legacy`，Shadow 旁路已由生产 Controller 接线但不参与正式结果决策；Canonical 模型、适配器和编排器尚未接入正式输出。本规范描述 Canonical 迁移目标的完整合同，但实际行为按 `pipeline_mode` 分阶段生效。

系统 SHOULD 将每份受支持报告转换为 `CanonicalInspectionCase`，再进行业务规则计算和文档生成。目标主迁移方向为 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`：`InspectionReport` 是现有公共契约的兼容投影。规范化结果 SHOULD 具有稳定的 `caseId`、来源摘要、报告创建/报告时间、案件名称、检材列表、主取证软件、检查人员快照、归档清单和附件输入；原始文件路径和字段来源 SHOULD 保留在 provenance 中但不得泄漏到用户文书正文。

当前生产状态：`pipeline_mode` 默认 `legacy`，现有 `InspectionReport` 管线产生唯一正式输出；Shadow 只在后台旁路记录脱敏比较结果，不参与正式结果决策。`canonical_to_inspection_report` 和 `inspection_report_to_canonical` 已实现并可通过测试调用，但 Canonical 正式输出尚未启用。不得把“类型存在”“单元测试可调用”或“Shadow 旁路接线”写成“Canonical 生产已启用”。

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

### Requirement: Archive input paths use a persisted optional authorization mode

系统 MUST 保留 `UPLOAD_BASE`、`BIJI_ALLOWED_INPUT_ROOTS` 和精确目录授权令牌的既有校验实现，并支持按来源登记请求选择授权模式。请求未提供 `source_authorization_enabled` 时 MUST 默认为 `true`，保持直接 API 调用的既有安全行为；浏览器首页开关首次使用时默认为 `false`，并将用户选择持久化在浏览器本地。

当 `source_authorization_enabled=true` 时，案件目录 MUST 是配置允许根目录的真实严格子目录，或通过受控精确目录令牌授权；根目录外普通 `report_dir` MUST 返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`。当 `source_authorization_enabled=false` 时，系统 MUST 跳过配置根目录/精确令牌的授权边界，允许登记任意满足基础路径安全校验的本机报告目录。两种模式都 MUST 保留空/相对/穿越/UNC/设备路径、symlink、junction、mount point、其他 reparse point、输入输出区域重叠和不支持报告结构校验。

开关 MUST 只出现在电子数据检查笔录首页；案件工作台不得重复展示或提供该开关，但其登记和来源重新登记请求 MUST 读取首页持久化偏好。用户重新开启开关后，后续登记请求恢复授权根校验；已登记来源的后续解析、归档和 Manifest 校验边界不因开关变化而放宽。

`report_dir` MUST 标记为 deprecated，仅允许用于创建带随机 UUID 的 `archive_context_id`。上下文公共摘要只能包含标识、文件数、总字节数、状态和时间，不得包含完整本地路径。规划、WinRAR、验证、MD5、Manifest、重试和 DOCX 接口只接受 `archive_context_id`；上下文过期、不存在和并发分别返回稳定错误码，清理不得删除用户原始输入。

#### Scenario: 首页关闭校验并持久化

- **WHEN** 用户在电子数据检查笔录首页关闭“来源目录校验”并重新打开系统
- **THEN** 开关仍保持关闭，案件工作台不显示该开关
- **AND** 后续目录登记请求携带 `source_authorization_enabled=false`

#### Scenario: 关闭校验时登记任意本机目录

- **WHEN** `source_authorization_enabled=false` 且用户提交配置根目录外的有效本机报告目录
- **THEN** 系统建立来源和不含路径的公共上下文摘要
- **AND** 不返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`

#### Scenario: 重新开启校验后恢复边界

- **WHEN** `source_authorization_enabled=true` 且用户提交没有配置授权或精确令牌的根目录外 `report_dir`
- **THEN** 系统返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`
- **AND** 不建立来源、不调用解析器或 WinRAR

#### Scenario: 两种模式都保留基础路径安全校验

- **WHEN** 任一模式提交相对、UNC、设备、链接或与系统输出区域重叠的路径
- **THEN** 系统返回对应稳定路径错误
- **AND** 不扫描目录、不建立上下文、不回显完整路径

#### Scenario: 后续接口只接受 archive_context_id

- **WHEN** 归档或 DOCX 导出请求提交客户端路径而没有有效上下文
- **THEN** 系统阻止请求并且错误响应不包含该路径

#### Scenario: 工作台通过 Windows 原生窗口选择报告目录

- **WHEN** 用户在本地 Windows 案件工作台点击“上传报告目录/添加案件”卡片
- **THEN** 后端在本机桌面会话中弹出 Windows 原生文件夹选择窗口
- **AND** 用户选择的真实绝对路径只在后端内部传给既有来源登记、路径安全和报告结构校验链路
- **AND** 后端在同一请求内创建案件壳、来源记录和解析任务并启动解析，前端不再要求用户填写路径后点击独立登记按钮
- **AND** 不上传或复制整个报告目录，不把绝对路径写入公共响应、日志或浏览器状态
- **AND** 选择任意满足既有基础安全校验的本机目录，不把选择范围硬编码为桌面目录

#### Scenario: 取消 Windows 原生目录选择

- **WHEN** 用户关闭或取消 Windows 文件夹选择窗口
- **THEN** 后端返回取消标记，不创建案件、来源记录或解析任务
- **AND** 前端恢复可点击状态且不显示错误请求提示

#### Scenario: Windows 原生目录选择器不可用

- **WHEN** 后端不在可交互的 Windows 桌面会话、选择器启动失败或选择器超时
- **THEN** 请求返回不包含路径或内部异常的稳定错误码和可操作提示
- **AND** 不创建案件、不复制报告目录、不绕过既有路径和来源安全校验

### Requirement: Archive planning and WinRAR execution are separate

阶段一自动分卷只支持 WinRAR RAR 分卷。未检测到或无法调用 WinRAR 时，系统 MUST 允许上传、解析、审核和编辑报告，但 MUST 禁止自动压缩和最终正式导出；错误提示 MUST 说明需要安装并确保 WinRAR 可调用。系统不得降级生成 ZIP，不得生成虚假的或占位的 `ArchiveManifest`。现有 ZIP/RAR 上传解析能力保持不变，但不替代本次自动分卷产物。

系统 MUST 先生成可审计的 `ArchivePlan`，再由独立执行器调用 WinRAR。`ArchivePlan` 只表示执行前预计档位、预计卷数和目标容量，不能作为 Word 数据来源。分卷档位 MUST 使用十进制 4GB、22GB、45GB：从 4GB 档开始，`ceil(total_bytes / tier_volume_bytes) <= max_part_count` 时选择该档位；若预计超过 2 卷（4GB 档）或超过 2 卷（22GB 档）则升级；45GB 档最多 3 卷；超过 135GB MUST 在执行前阻止处理。案件名称 MUST 作为归档基础名称，分卷 MUST 使用 `.part1.rar` 等标准命名。系统 MUST 设定 `max_replan_attempts = 2`，表示初始执行后最多允许两次向上重新规划。

分卷档位（WinRAR `-v` 参数值）与每卷最终光盘容量是两个独立概念。档位由规划器在压缩前选定，光盘容量在 Manifest 组装时根据 WinRAR 实际输出的 `size_bytes` 独立计算。

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

系统 MUST 将规划和实际执行结果区分保存。若实际结果不符合当前计划，执行器 MUST 在最多 `maxReplanAttempts` 次内丢弃 staging 结果、升级到下一档并重新执行；若重试仍失败、没有可用下一档或达到重试上限，则阻止导出并返回明确错误。重新规划完成后 MUST 生成新的不可变 `ArchiveManifest`，后续附件一、附件三、正文和 DOCX MUST 只引用该 manifest，不得使用预计文件名、预计大小、预计卷数，也不得重新扫描目录或重新计算第二份卷列表。最终 manifest 至少 MUST 包含每卷实际文件名、实际大小、MD5、分卷序号、**根据实际大小独立计算的光盘容量 (`disc_capacity_bytes`)**、WinRAR 分卷档位上限 (`volume_size_bytes`)、光盘编号、刻录日期和连续性校验结果。`disc_capacity_bytes` MUST 按 `size_bytes` 选择最小可容纳档位（≤4GB→4GB, ≤22GB→22GB, ≤45GB→45GB），超过 45GB 时返回验证失败；不得简单继承 manifest 级档位值。

#### Scenario: 实际压缩结果超出规划

- **WHEN** 4GB 规划实际生成 3 卷，或 45GB 规划实际生成超过 3 卷
- **THEN** 系统在临时目录中重新规划/执行，最多重试两次；最终只保留通过验证的档位结果，并将所有规划尝试写入不含敏感值的诊断日志

#### Scenario: 实际压缩结果少于预计

- **WHEN** 压缩比使实际卷数少于预计但仍满足当前档位限制
- **THEN** 系统保留通过验证的最终 manifest，记录预计与实际差异，不因为推测而修改已生成文件名或附件编号

#### Scenario: 重试耗尽

- **WHEN** 实际结果在最大重试次数内仍不符合计划，或 45GB 档仍超过三卷
- **THEN** 系统返回明确的归档规划错误，不生成 Word、不创建附件页面计划、不提交新的最终归档

### Requirement: ArchivePart disc capacity is independent of tier volume

系统 MUST 在生成最终 `ArchiveManifest` 时为每个 `ArchivePart` 独立计算 `disc_capacity_bytes`，不得使用 manifest 级 `volume_size_bytes`（WinRAR 分卷档位上限）替代。`disc_capacity_bytes` 只来源于该 part 的 `size_bytes`（WinRAR 实际输出文件大小），按最小可容纳档位规则计算：

- `0 < size_bytes ≤ 4_000_000_000` → `4_000_000_000`
- `4_000_000_000 < size_bytes ≤ 22_000_000_000` → `22_000_000_000`
- `22_000_000_000 < size_bytes ≤ 45_000_000_000` → `45_000_000_000`
- `size_bytes ≤ 0` 或 `size_bytes > 45_000_000_000` → 该 part 无效，Manifest 验证失败

`disc_capacity_bytes` MUST 在 `assemble_archive_manifest()` 中计算、在 `validate_manifest_files()` 中重新推导核对、在 `validate_published_manifest()` 中再次校验。重规划后 MUST 随新 part 的 `size_bytes` 重新计算。系统 MUST 不接受客户端或旧数据传入的未经校验的容量值。

#### Scenario: 两卷不同光盘容量

- **WHEN** WinRAR 在 45GB 档位产生两卷，实际大小分别为 45GB 和 2GB
- **THEN** Part 1 的 `disc_capacity_bytes = 45_000_000_000`，Part 2 的 `disc_capacity_bytes = 4_000_000_000`，两卷的 `volume_size_bytes` 均为 `45_000_000_000`

#### Scenario: 22GB 档单卷对应 22GB 光盘

- **WHEN** WinRAR 在 22GB 档位产生单卷，实际大小 9GB
- **THEN** 该 part 的 `disc_capacity_bytes = 22_000_000_000`

#### Scenario: 尾卷选择 4GB 光盘

- **WHEN** WinRAR 在 22GB 档位产生两卷，实际大小分别为 22GB 和 1GB
- **THEN** Part 1 的 `disc_capacity_bytes = 22_000_000_000`，Part 2 的 `disc_capacity_bytes = 4_000_000_000`

#### Scenario: 篡改或不一致的光盘容量被拒绝

- **WHEN** 已发布 Manifest 中某 part 的 `disc_capacity_bytes` 与从其 `size_bytes` 重新计算的值不一致
- **THEN** `validate_published_manifest` 返回 false，`validate_manifest_files` 返回 `ARCHIVE_MANIFEST_INVALID`

#### Scenario: 重规划后容量重新计算

- **WHEN** 归档在 4GB 档执行失败后重规划到 22GB 档并产生新的实际 part
- **THEN** 新 Manifest 中每个 part 的 `disc_capacity_bytes` 根据新 `size_bytes` 独立计算，不继承旧档位或旧 Manifest 的值

### Requirement: Pipeline mode and shadow comparison are centralized

系统 MUST 使用一个集中配置 `pipeline_mode = legacy | shadow | canonical` 控制迁移运行语义，不得在 parser、service 和 renderer 中散落互相矛盾的独立布尔开关。默认值 MUST 为 `legacy`，配置 MUST 在后端应用启动时从统一运行时配置读取并注入管线；模式切换 MUST 记录配置版本和时间。

#### Scenario: Legacy mode

- **WHEN** `pipeline_mode` 为 `legacy`
- **THEN** 旧管线产生唯一正式输出；新 canonical/plan/renderer 不执行正式导出

#### Scenario: Shadow mode

- **WHEN** `pipeline_mode` 为 `shadow`
- **THEN** 旧管线仍产生唯一正式输出；新管线只在后台旁路的隔离内存中生成规范化结果、规划和脱敏比较数据，并通过有容量/TTL的受限诊断Store提供查询，不产生第二份正式文书、不替换正式归档。比较至少覆盖案件编号、检材类型与实际业务字段、IMEI1/IMEI2或序列号、检查时间、主软件名称/版本、检查人员顺序、外部RAR命名、根目录保留、相对路径集合、输入文件数量/总字节、ArchiveManifest 和附件一/二/三页面数量

#### Scenario: Shadow 不执行真实重复压缩

- **WHEN** `pipeline_mode` 为 `shadow` 且旧管线已产生正式归档
- **THEN** 新管线不得调用 WinRAR 或执行第二次真实压缩
- **AND** ArchiveManifest 比较使用既有正式结果与非执行性的计划/清单投影
- **AND** 不产生第二份正式归档或可被正式导出的新 manifest

#### Scenario: Shadow missing facts are not matched

- **WHEN** Legacy 或 Shadow 一侧缺少待比较字段，或两侧均缺少该字段
- **THEN** 结果分别记录 `mismatch` 或 `not_comparable`，不得静默显示 `matched`

#### Scenario: Shadow export observation point is explicit

- **WHEN** Legacy DOCX 已成功生成
- **THEN** Shadow 只比较该次正式导出已经准备好的业务/附件输入，不宣称完整最终渲染输入比较，且不再次生成 DOCX
- **WHEN** Legacy DOCX 生成失败
- **THEN** Shadow 记录脱敏的 `LEGACY_DOCX_RENDER_FAILED` 失败诊断，不留下 `matched` 的导出结果，Legacy 错误仍按原合同返回

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

系统 MUST 先生成 `Attachment1Plan` 再渲染附件一。数据行数 MUST 等于最终 `ArchiveManifest` 的卷数；每页最多四项；表头只在第一页出现且不得由 Word 自动重复；“附件1”只在第一页；来源框和提取方法框每个数据页分别生成合并框。数据页最多容纳四条分卷；总序号少于三条时，最后一个数据页可以按模板空白行补足视觉留白：一条分卷保留两条，二条分卷保留一条，三条及以上分卷不得保留斜线空白行。总序号达到三条后，即使最后一页只有一条或两条分卷，也不得再次添加斜线空白行。如果最后一个数据页恰好四条分卷，固定手写行 MUST 作为新的 `inspector_final` 页面，不得挤入四条数据所在页面。固定手写行和其页面 MUST 设置不可拆页/保持完整，不写入动态检查人员。

#### Scenario: 页面规划跨页边界

- **WHEN** 页面规划器接收一个用于跨页边界测试的、已验证的五条 part 记录（该测试 fixture 不代表阶段一允许生成五卷）
- **THEN** 页面计划有两页，行数为 5，第一页 4 行并显示表头和“附件1”，第二页 1 行且不重复表头；两页均有各自来源合并框和提取方法合并框，检查人员框只在第二页

#### Scenario: 四卷附件一将固定手写行独立起页

- **WHEN** 已验证的 `ArchiveManifest` 包含四条实际分卷
- **THEN** 页面计划先生成四条分卷数据页，再生成一个不含分卷行的 `inspector_final` 页面；固定手写行只出现在后一页

#### Scenario: 三份检材附件二续页单组居中

- **WHEN** 审核后的附件二包含三个检材组，每组恰好两张图片
- **THEN** 附件二第一页两组按上下区域对称排列，第二页单组在页面可用区域垂直居中；第二页仍保持组内两张图片左右排列，检材文字与图片组对应

#### Scenario: 三条及以上分卷不再使用斜线空白行

- **WHEN** 最终 `ArchiveManifest` 包含至少三条分卷，且最后一页少于四条数据
- **THEN** 所有附件一数据页和独立固定手写页均不添加斜线空白行

#### Scenario: 三卷附件一保持单页

- **WHEN** 已验证的 `ArchiveManifest` 包含三条实际分卷
- **THEN** 附件一只有一页并包含三条分卷行、表头、来源/提取方法合并框和末尾固定手写行
- **AND** 不得为了保留固定手写行把第三条分卷拆到第二页

#### Scenario: 归档失败时不生成附件一

- **WHEN** final manifest 尚未通过卷校验
- **THEN** `Attachment1Plan` 不可创建，导出被阻止而不会产生缺少卷信息的空表

### Requirement: Attachment two photo page plan

系统 MUST 先生成 `PhotoPagePlan` 再渲染附件二。0 张图片允许导出且不生成附件二图片页；正数图片数量 MUST 为偶数，否则禁止导出；每页最多四张；四张使用 2×2，二张使用左右布局且在页面上下居中；支持任意偶数数量。图片 MUST 按当前 `current-template-v1` 附件二页面母版的统一图片区域等比例完整显示，不裁剪、不拉伸，并尽量填满该母版区域。页面母版 MUST 以包含“附件2”标题锚点的第一页为唯一版式基准，一次确定图片区域、列宽、行高和分页锚点间距；不得根据后续页没有标题文字而重新计算或放大。附件二多页时仅第一页显示“附件2”，后续页清空标题文字但保留同等高度的空白标题锚点，并保持相同图片区域和版式；没有附件二时附件三仍显示“附件3”，不重新编号。

当前模板 MUST 以检材组为附件2的领域单位。每个参与附件2的检材 MUST 绑定恰好两张有效图片；`PhotoPagePlan` MUST 先建立 `MaterialPhotoGroup` 再按检材组分页。每个 `MaterialPhotoGroup` MUST 包含 `material_id`、`material_number`、相关显示文字、两张有序图片和 `source_order`；同一检材的两张图片 MUST 同页左右排列，不得跨页或与其他检材图片交叉。每个检材组的说明文字 MUST 使用独立的可读行框，不得被图片或表格边界遮挡；同页两个检材组 MUST 使用相同高度的上下区域并保留一致的组间间隔，两个完整检材组（图片和说明文字）分别在上、下区域内居中，不得连续堆叠在页面下半部。每个 `Attachment2PagePlan` MUST 包含本页的 `material_groups`、`inspection_result_material_numbers` 和布局类型；每页最多两个检材组，每组固定两张图片，两个组按上下区域排列；剩余单组页 MUST 复用双组页每个检材组的图片行高度，并在同一页面可用区域内垂直居中，不得缩小为低于双组页单组的图片高度。

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
- **THEN** 两张图片左右排列，沿用附件二页面母版的统一列宽、图片区域和行高，并在该母版区域内上下居中

#### Scenario: 奇数图片禁止导出

- **WHEN** 用户上传一张、三张或其他奇数张图片
- **THEN** 页面规划返回明确的偶数数量错误，模板渲染器和 DOCX 导出均不执行

#### Scenario: 多页附件二只在第一页显示标题

- **WHEN** 正偶数图片数量大于四张并生成多页附件二
- **THEN** 只有第一页显示“附件2”
- **AND** 后续页面不重复标题但保留同高的空白标题锚点，并保持相同分页间距、图片区域和版式

### Requirement: Attachment three follows the final manifest

系统 MUST 为每个最终归档卷生成一页 `Attachment3Plan`；只有第一页显示“附件3”，后续页结构一致但不显示该标题。每页元数据框 MUST 依次只显示检验单位、光盘编号、文件哈希和刻录时间，不显示文件名行；其中 MD5、光盘编号和刻录日期 MUST 使用 manifest 中对应归档卷的值，不得重新从目录或报告原始字段推导。正文检查结果仍 MUST 使用该 manifest 的全部有序分卷文件名、实际大小、MD5 和光盘编号，不得退回报告中单个旧分卷字段。

#### Scenario: 三卷附件三

- **WHEN** final manifest 有三卷且首光盘号有效
- **THEN** 附件三生成三页，三页分别绑定 part1/part2/part3，只有第一页有“附件3”，三页的日期均来自光盘号日期
- **AND** 每页元数据框首行均为“检验单位”，不显示“文件名”行

#### Scenario: 附件一和附件三一致

- **WHEN** 归档执行发生升级重规划
- **THEN** 附件一的行和附件三的页面都引用同一 `ArchiveManifest.parts[].part_id`，不会出现卷数、MD5、文件名或编号不一致

### Requirement: Current template is a versioned profile

系统 MUST 将正式模板登记为固定的 `current-template-v1`，由固定 `TemplateProfile` 描述其资产哈希、占位符、表格、VML 文本框、当前受控重复区、图片区、分页和保持完整约束。阶段一 MUST 只支持该 Profile 和当前 DOCX Renderer 的受控扩展，并 MAY 允许用户在前端以已校验版本为源修改白名单内的文书固定标题、正文默认字体和字号。保存修改 MUST 发布新的不可变模板版本，重新计算包指纹并通过完整固定 Profile 结构校验；不得改写源版本或案件引用。通用模板设计器、通用重复块 DSL、任意 DOCX 自动绑定、自由拖拽排版和无标记模板识别均属于阶段三，阶段一不得实现或静默启用这些能力。

当前生产边界：`current-template-v1` TemplateProfile、`ArchiveManifest` 和 `AttachmentPlan` 已由 legacy DTO 渲染链消费；统一 `DocumentRenderPlan` 仍是未来合同目标，当前没有生产构造和消费。正式模板没有用于展示 `disc_capacity_bytes` 的独立位置，本变更不通过修改 Word 布局补充该位置。

内置模板版本 MUST 保持不可变和可复现。清理模板批注或附件二示例图片时 MUST 发布新版本，历史资产继续供既有案件引用；不得用新字节覆盖旧版本登记的资产。清理后的模板 MUST 不包含批注部件、批注标记、批注关系或附件二示例媒体，但 MUST 保留附件二标签、空白图片区段落、图片说明锚点、分页和 VML 文本框。新部署以及仍以旧内置模板为默认值的部署 MUST 使用清理后的新版本；用户明确选择的其他默认模板不得被启动迁移覆盖。

当前内置模板的 A4 左右页边距 MUST 对称；正文直接段落的左右排版边界 MUST 围绕页面中心平衡，附件一固定表格 MUST 相对页面水平居中。可见主标题 MUST 以页面中心为基准居中，不得依赖会把字形中心推离页面中心的前后制表符；“一、绪论”“二、检查” MUST 略突出于其下二级标题，“（三）检查过程”“（四）检查结果” MUST 与同级“（一）检查方法”“（二）检查设备”对齐；首页文号下方和各页页脚上方的粗横线 MUST 相对页面水平居中。修正版 MUST 发布为新版本，既有案件明确引用的旧内置版本继续从历史资产重导出；启动迁移只更新仍指向旧内置默认版本的共享默认值，不改写案件引用或用户自定义默认模板。

#### Scenario: 选择当前正式模板

- **WHEN** 阶段一导出电子数据检查笔录
- **THEN** 当前生产链按 final `ArchiveManifest → AttachmentPlan → current-template-v1 TemplateProfile → 当前确定性 Renderer` 生成正式文书，并校验模板资产版本
- **AND** 该场景不构造或消费未来的 `DocumentRenderPlan`

#### Scenario: 模板资产被替换

- **WHEN** 模板路径存在但内容哈希与 Profile 不一致
- **THEN** 导出被阻止并提示模板版本不匹配，不自动使用未知模板

#### Scenario: 前端受控编辑发布新版本

- **WHEN** 用户在模板管理页以已校验的可用版本为源，修改文书固定标题、白名单字体或字号并保存
- **THEN** 系统从源资产副本生成新 ID/版本资产，并在重新通过包指纹、占位符、VML、表格与分页结构校验后将新版本记为已校验
- **AND** 源资产字节、源版本登记和已有案件引用保持不变

#### Scenario: 受控编辑拒绝越界修改

- **WHEN** 请求使用未审核或历史只读源模板、非白名单字体/字号、重复版本或未声明编辑字段
- **THEN** 系统返回稳定安全错误且不登记新模板资产

#### Scenario: 单独修改模板显示名称

- **WHEN** 用户在模板管理页为已审核模板提交去除首尾空白后非空且不超过 120 个字符的新名称
- **THEN** 系统只更新该模板的显示名称元数据
- **AND** 模板 ID、版本、DOCX 资产、指纹、校验规则、审批记录、默认状态和案件引用保持不变
- **AND** 空白、超长或包含额外字段的请求被拒绝且不改变已保存名称

#### Scenario: 管理页移除冗余标题说明

- **WHEN** 用户进入笔录模版管理、检查人员管理或取证硬件设备管理页面
- **THEN** 页面保留标题和主要管理内容，但不显示标题下方的说明文字

#### Scenario: 清理内置模板而保持既有案件可复现

- **WHEN** 系统升级到不含批注和附件二示例图片的内置模板版本
- **THEN** 新案件默认引用清理后的新版本，动态上传图片仍按附件二计划生成
- **AND** 已明确引用旧内置版本的案件继续从历史资产生成，不改写案件模板引用
- **AND** 用户选择的其他默认模板不被升级流程替换

#### Scenario: 修正模板整体偏右而保持历史版本

- **WHEN** 当前内置模板的正文段落或附件一表格相对 A4 页面视觉中心偏右
- **THEN** 系统发布左右排版边界平衡、附件一表格居中的新模板版本
- **AND** Microsoft Word 原生渲染保持既有页数、分页、VML、页眉页脚和表格列宽
- **AND** 历史内置版本继续供既有案件只读重导出，用户自定义默认模板不被迁移覆盖

#### Scenario: 修正标题层级和粗横线的可见中心

- **WHEN** 当前内置模板由 Microsoft Word 原生渲染
- **THEN** “电子数据检查笔录”的可见字形中心与 A4 页面中心一致，标题段落不含用于伪居中的前后制表符
- **AND** “一、绪论”“二、检查”略突出于二级标题，“（三）检查过程”“（四）检查结果”与其他二级标题对齐
- **AND** 首页文号下方及各页页脚上方的粗横线相对页面水平居中
- **AND** 页数、分页、段落可用宽度、表格列宽、VML 文本框、页眉和页脚内容保持不变

### Requirement: Preserve VML, page breaks, and black text

系统 MUST 在模板渲染时保留当前模板的 VML 文本框、文本框宿主段落、图片关系、普通分页符、页眉页脚结构和表格边框。正文、动态段落、表格动态内容、页眉页脚和 VML 文本框内字体颜色 MUST 统一为黑色；不得用删除宿主段落、奇偶页分节符或重新生成整份模板来实现替换。

#### Scenario: VML placeholder replacement

- **WHEN** `current-template-v1` 中 VML 文本框包含动态占位符
- **THEN** 只替换文本框内部文本并保留 `w:pict`/`v:textbox`/`w:txbxContent` 结构，动态字体颜色为黑色

#### Scenario: Attachment pagination regression

- **WHEN** 生成包含任意偶数图片和多卷附件三的文档
- **THEN** 当前生产分页只按 final Manifest 派生的 `AttachmentPlan` 和固定 TemplateProfile 中的确定性分页规则生效，不产生空白页、奇数页/偶数页分节符或被拆开的检查人员框

#### Scenario: Attachment 1 Latin fields wrap within words

- **WHEN** 附件1的“电子数据”、“提取方法”或“文件MD5哈希值”包含超出单元格当前行宽的连续西文字符
- **THEN** 首页和续页的对应数据单元格都允许西文在单词中间换行，不将整个文件名、提取方法或 MD5 整体挪到下一行

#### Scenario: Attachment 1 source uses one material number per line

- **WHEN** 附件1的“来源”包含一个或多个检材编号
- **THEN** 每个检材编号使用显式换行单独占一行，除最后一个编号外均保留顿号
- **AND** “检材内提取”在所有检材编号之后单独占一行

### Requirement: InspectionReport compatibility boundary

系统 MUST 保持现有 `InspectionReport` 作为兼容 DTO；主适配方向是 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`。现有前端解析、编辑和导出请求在迁移期间 MUST 继续可用。`InspectionReport → CanonicalInspectionCase` 只作为旧 DTO 输入和历史迁移的 best-effort 入口，不承担 canonical 的完整回填。兼容适配器 MUST 明确无法从旧 DTO 恢复的字段来源、通用 identifiers、`InspectorSnapshot[]`、`ArchiveManifest`、`TemplateProfile` 信息、规划状态和其他新模型字段；不能把 `InspectionReport` 继续作为新领域层的唯一事实来源。

#### Scenario: 旧导出请求

- **WHEN** 现有前端提交 `InspectionReport` 和照片 ID
- **THEN** 在 canonical 生产切换完成后，后端将其转换为 canonical case，生成规划和 render plan 后导出，现有请求字段和响应下载行为保持兼容
- **AND** 在切换前，生产 Controller 继续走 legacy DTO + final `ArchiveManifest` + `AttachmentPlan` 的正式路径，不得将兼容适配器可调用误报为 canonical 已接线

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

现有电子数据检查笔录 MUST 继续支持当前解析和导出入口。主迁移入口先按 `ReportAdapter → CanonicalInspectionCase → InspectionReport` 生成现有前端/导出兼容 DTO；canonical 管线的正式文档目标继续由 canonical case → plans → render plan → 固定 `current-template-v1` 生成。officecli batch 只保留为无 Manifest 兼容分支；当前 `/records/export` 要求有效 Manifest，带 Manifest 渲染失败时不得回退 officecli。默认管线切换前必须完成 Shadow 比较、两套输出回归和人工验收。

上述 canonical 生成链是批准目标而非当前生产事实。当前正式生产输出由 legacy `InspectionReport` DTO 管线生成，并消费已经验证的最终 `ArchiveManifest`、`AttachmentPlan` 和固定 TemplateProfile；Shadow 已接入生产 Controller 旁路但只保存脱敏诊断，Canonical 正式输出未启用，`DocumentRenderPlan` 未生产实现。

#### Scenario: 当前报告正常导出

- **WHEN** 用户上传当前旧/新报告、选择人员、输入首光盘号并提供零或任意偶数张图片
- **THEN** 系统完成解析、分卷、三类附件规划和 `current-template-v1` 渲染，输出的正文、附件和卷信息彼此一致

#### Scenario: 审核页单独导出与统一导出使用相同附件计划

- **WHEN** 案件已有成功归档，用户从审核编辑界面单独导出 Word
- **THEN** 系统使用统一导出所用的已验证最终 `ArchiveManifest`、持久化光盘映射和 `AttachmentPlan` 生成 Word
- **AND** 附件一及其他附件的结构和版式与同一案件的统一导出 Word 保持一致
- **AND** 单独导出仍不复制 RAR、不生成 HashMyFiles PNG、不改变统一导出完成状态

#### Scenario: 尚无成功归档时单独导出兼容 Word

- **WHEN** 案件尚无成功归档，用户从审核编辑界面单独导出 Word
- **THEN** 系统继续使用 report-only 兼容分支生成 Word
- **AND** 不伪造 `ArchiveManifest` 或归档完成状态

#### Scenario: 任一规划门控失败

- **WHEN** 标识规则、分卷上限、光盘格式、图片偶数校验、模板资产校验或 DOCX XML 校验失败
- **THEN** 导出失败且不提交最终文件；现有报告输入和已保存人员/模板 Profile 保持不变
