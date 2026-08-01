# Proposal: 持久化案件工作台与归档任务协调

> 变更包：`persistent-case-workbench-and-archive-coordination`
> 状态：Phase 1–4 已完成；完整 Harness 和最终集成人工验收已通过；`1D-017R` 已于 2026-08-01 通过。Final Review 曾因四项有限问题判定为 `REJECT`，remediation 后于 2026-08-01 重新执行并判定为 `PASS`。Production Review 已按现有 Legacy-only、单 Windows 实例支持模型于 2026-08-01 判定为 `PASS`；当前已具备归档准备条件，现有 gate 的 `OpenSpec 归档阻断解除` 已记录为解除。Phase 5 和 OpenSpec archive 尚未开始，不得据此宣称已执行归档。部署、恢复、容量边界和风险接受详见同变更包 `design.md` 与 `tasks.md`。
> 日期：2026-07-26
> 级别：Level 3

## 2026-07-31 独立 Review 加固范围与根因记录

本轮只处理 `1D-017R` 独立 Level 3 Review 的 M-1 至 M-4 与关联低风险项 L-1；不重新执行 `1D-017R`，也不开始 Phase 5、Final Review、Production Review 或 OpenSpec archive。以下记录基于 Review 指向的实际调用链：

| 项 | 当前状态转换/持久化顺序 | 身份、并发或外部变化窗口 | 失败后 durable/file 状态及影响 | 可复现故障模型 |
|---|---|---|---|---|
| M-1 | `persist_publish_intent` 在同一 attempt 重入时先查已有 intent，但原比较只覆盖 Manifest、目标目录和 archive fingerprint；其余身份仍可进入同一返回路径。 | source key、input fingerprint、source/draft revision、report fingerprint、public Manifest、context/fence 等不可变事实可变化，而旧 intent 已 durable。 | 旧 intent 可能被错误复用，后续 published/indexed/verified 证据会关联到不同来源、计划或 fence；历史 intent 不能安全区分。 | 同一 attempt 以单个未比较字段不同的参数重入，原实现返回已有 intent 而非冲突；并发恢复可能沿用错误身份。 |
| M-2 | coordinator 停止时只对 `Future.cancelled()` 的 claim 调用 interrupted 收敛；超出有界等待的仍存活 Future 没有统一落库转换。 | shutdown deadline 与 Worker 完成之间存在窗口；本实例 claim 仍持有 task owner，但实际 Worker 可能已脱离；其他部署实例不应被本实例改写。 | 数据库可永久显示 running/claimed 而无存活 Worker；重启恢复只能看到不完整事实，且不能把未完成任务安全标为 succeeded。 | 使用阻塞 Worker 超过 shutdown 上限，原实现 stop 返回后 task/attempt 仍 running；Worker 后续返回还可能与恢复状态竞争。 |
| M-3 | 执行开始验证 inventory 并计算一次 input fingerprint，WinRAR/归档产物生成后没有在关键阶段再次确认源目录。 | 文件可在归档执行中增加、删除、替换、截断或同大小同时间戳改写；仅路径、数量或 metadata 不能证明字节未变。 | RAR、inventory 或 Manifest 可能来自混合源版本；若继续发布会污染正式资产，重试也可能复用不可信证据。 | 执行器完成后或正式移动前修改一个源文件（保持名称/大小/时间戳），原实现仍可完成发布。 |
| M-4 | staging 移动后依次写 intent phase、Manifest index、完成状态；验证对象与最终目录、索引和完成提交之间缺少统一的外部变化闭合检查。 | staging 发布前、正式发布后到索引/完成之间，正式卷、Manifest 或索引可被替换、删除、新增或重命名。 | 任务可能成功而正式对象已不是验证对象；恢复、下载、复用或 Word 导出可能读取篡改后的资产，或历史 index 被冲突覆盖。 | 在 staging 验证、正式发布、索引或完成确认的边界注入单卷替换/Manifest 修改/新增卷，原实现不能始终阻止成功。 |
| L-1 | 旧顺序先删除 staging ownership marker，再持久化 intent/fence 并移动；marker 删除与 durable 发布身份不是同一安全边界。 | 删除后进程崩溃或 intent/fence 创建失败时，目录可能失去归属证据；恢复难以判断是否仍为本实例发布资源。 | 低概率留下未知 staging 或让恢复过早清理；不能恢复旧的重复删除行为，也不应由 marker 取代 intent/fence。 | 在 marker 删除与 intent/fence 建立之间注入崩溃/失败，观察归属证明和恢复分类。 |

选定合同：发布 intent 的身份必须使用现有 Spec/数据模型中的完整不可变集合（case、attempt、source、source/draft revision、report fingerprint、source/input/archive fingerprint、Manifest/public Manifest、正式相对目录、context binding 与 fence），缺失或不一致一律 conflict，只有完整合法相同才幂等重入。shutdown 只收敛本实例且仍满足 owner、attempt、lease/revision/fence 的 claim；未完成只能进入现有 interrupted/可恢复状态，已经 durable verified 的状态不得降级。源材料在开始、执行完成后和正式发布前使用稳定字节证据复核；正式发布、索引和完成确认重新核对同一 intent、Manifest、文件集合、顺序、字节数和摘要。marker 仅在 durable intent/fence 已建立且正式移动完成后由明确发布所有者删除一次，恢复沿同一边界处理。

## Why

## 2026-08-01 第二轮独立 Review remediation

本轮独立 Level 3 Review 已确认上一轮 M-1 至 M-4 为阻断项，当前只实施这些阻断项及关联 L-1，不重新执行 `1D-017R`，不开始 Final Review、Production Review、Phase 5 或 OpenSpec archive。修复前置安全模型如下：外部来源目录只负责形成一次受授权的输入，任务在 WinRAR 前复制、逐文件验证并 durable seal 一个 task/attempt/deployment 绑定的不可变执行输入快照；WinRAR、inventory、RAR 和 Manifest 只读取该 sealed 快照。

正式发布使用任务绑定的 `publication_id` generation。SQLite 的 publish intent/fence/publication 记录是唯一 durable 事实源；正式目录通过同文件系统原子改名进入受保护 generation，JSON Manifest index 只是可重建投影。只有 sealed generation、完整 Manifest/index 投影、owner/fence 和当前 revision 在同一完成事务中一致时，attempt 与 task 才能进入 succeeded。旧的缺 task identity 或缺 publication identity 记录不自动补认，按冲突/恢复策略处理。

本轮实现会按 Level 3 规则完成 schema/migration、repository/service/recovery 链路和真实文件系统/SQLite 故障注入；磁盘快照成本、受控输出根和共享 SQLite 的 deployment ownership 均在 `design.md` 中明确。所有新证据使用 `SYNTHETIC/TEST/FIXTURE` 数据，`word_templates/template.docx` 不变。

当前电子检查笔录流程以单个页面和 React 内存状态为中心。解析结果、编辑结果、归档准备状态和默认值没有共同的后端持久化模型；归档执行仍是同步链路；审核顺序、字段来源、光盘编号映射和模板选择没有成为可恢复的案件合同。

甲方已经确认本轮需要把这些能力统一到多案件工作台中，同时继续保持最近完成的大型报告快速预览和“用户明确操作后才启动完整归档”的边界。若分别为排序、默认值、任务进度和模板选择增加局部状态，容易再次出现刷新丢失、Word 顺序不一致、replan 覆盖人工编号和正式产物被错误清理等问题，因此本变更包把案件草稿、共享默认值、后台任务、来源状态、归档计划和模板引用定义为一套版本化合同。

## What

### Capabilities

| 编号 | 能力 | 类型 | 目标 |
|---|---|---|---|
| CAP-CASE | 多案件工作台与可恢复案件草稿 | ADDED | 后端保存 Legacy `InspectionReport`、编辑状态、任务引用和生命周期；工作台每页 6 个案件卡片 |
| CAP-SOURCE | 持久化来源记录与访问复核 | ADDED | 用户登记并验证授权报告目录路径，来源以 opaque ID 绑定案件/任务，保存允许根、metadata/fingerprint 和复核状态；绝对路径不出后端 |
| CAP-DEFAULTS | 部署实例共享默认值与显式迁移 | ADDED | 用户明确修改六字段且当前草稿成功保存后稀疏更新；已有浏览器 `localStorage` 只能经一次性、可审计的导入确认迁移 |
| CAP-LEASE | 自动保存、编辑会话租约与安全删除 | ADDED | 15 秒心跳、2 分钟失联后可接管；解析/压缩期间只能取消并等待清理后删除 |
| CAP-ORDER | 检材和检查人员的权威顺序 | MODIFIED | 自然升序只作为默认值；人工拖拽后的案件数组同时驱动审核、正文、附件和 Word |
| CAP-PROVENANCE | 字段来源和待确认状态 | ADDED | 覆盖可编辑叶子字段、检材字段、人员项和附件图片组，并随草稿保存 |
| CAP-ARCHIVE-TASK | 归档计划、映射、后台任务和阶段里程碑进度 | ADDED | 预计分卷与光盘编号一一映射；replan 按稳定槽位保留有效映射；任务最多 6 个并发且受资源准入控制；案件卡片直接显示可恢复的 `workflow_milestone` |
| CAP-EXPORT-NAME | Word 下载名称与服务器物理文件名分离 | MODIFIED | 每次导出弹窗输入下载名称，物理文件名始终唯一、安全且不可覆盖 |
| CAP-TEMPLATE | 已审核预置模板注册和选择 | ADDED | 模板有独立 ID、版本、指纹、规则和验收记录；切换模板不重新压缩，仅使旧 Word 结果失效 |
| CAP-CLEANUP | 案件记录与正式产物独立清理 | ADDED | 成功导出案件记录默认保留 30 天；RAR、Manifest、Word 不因案件记录清理而自动删除 |

### Phase 1C product convergence

案件工作台是唯一主生产入口，是支持多案件、持久化和恢复的“生成笔录”，不是旧生成页面的
简化替代品。案件详情复用 Legacy 的正式字段配置、InspectionReport 适配、校验、日期时间、
附件编辑、预览和 Word 导出能力，同时保留工作台的案件卡片、状态同步、自动保存、revision、
编辑租约、来源状态和立即/稍后压缩决策。旧前端生成页面和报告压缩包上传 UI 停用，旧地址仅
重定向；后端 `/records/*` Legacy 兼容接口和正式输出安全门控不变。

这里的“Legacy”表示继续保留的后端兼容接口和唯一正式输出管线，不表示存在第二个工作台
生产流程。持久化案件工作台先保存 CaseShell、SourceRecord 和解析任务，解析成功后保存
CaseDraft；用户完成审核和草稿保存后，再显式选择立即压缩或稍后压缩。工作台预览不会自动
启动归档。仅调用既有 `/records/*` 的兼容客户端继续遵循其 Legacy 请求/响应合同。

### Persistent case image assets

工作台图片必须作为案件绑定的持久化资产处理：受控应用数据目录保存二进制，SQLite 只保存 opaque `asset_id`、SHA-256 指纹和安全元数据。上传接口仅接受 JPG/JPEG/PNG，并校验签名、扩展名、大小、案件数量和总容量；临时文件原子改名后才创建资产引用。草稿引用变化必须经过有效编辑租约和 revision 自动保存，替换失败保留旧引用，删除引用后清理不再使用的资产。图片恢复、预览和 Word 导出均通过案件资产接口读取，不依赖浏览器 `File` 对象；公共 DTO、日志和错误不得包含服务器绝对路径。

## Scope

- 新增一个部署实例级的案件元数据、来源记录和任务持久化边界，推荐使用 SQLite 保存业务 DTO、关系元数据和 opaque asset 引用，文件系统继续保存来源快照、缓存、临时文件和正式产物。SQLite 不保存 Base64 图片、完整 HTML、原始 JSON 集合或其他大对象。
- 增加 `SourceRecord`（或等价内部模型），记录 opaque 来源 ID、后端内部路径及允许根授权、来源类型、案件/任务绑定、metadata/fingerprint 和重启后的访问复核结果；API、日志和前端不得暴露绝对路径。
- 以案件内稳定 ID 和版本号串联草稿、解析任务、归档任务、Word 导出和清理记录。
- 继续使用 Legacy `InspectionReport` 作为草稿和正式 Word 输入；本变更不引入 Canonical 预览、编辑门控、候选输出或正式切换。
- 让 `evidence_list`、`inspector_snapshots`、附件图片组和字段来源成为案件草稿中的显式状态，并通过统一投影进入审核界面和 Legacy Word 链路。
- 把完整 inventory、路径/链接/文件变化校验、WinRAR、完整性校验、MD5、Manifest 和 Word 安全门控置于后台任务恢复模型中，不能因为异步化而降级。
- 建立已审核预置模板的注册、版本锁定、校验和复现边界；不允许任意未知 DOCX 上传。

## Non-Goals

- 不启动或恢复 Shadow 真实样本差异治理；Shadow 仍保持暂停，不能成为本变更的验收依据或正式输出路径。
- 不进入 Canonical 开发、Canonical 预览、编辑门控、候选输出或正式切换。
- 不修改甲方现有模板本身，除非后续单独审核的预置模板需要新增注册资产；不建设任意模板设计器或 Stage 3 通用模板平台。
- 工作台不接受 ZIP/RAR 或其他报告文件上传，也不复制报告目录；现有 Legacy `/records/*` 上传兼容能力保持隔离，不作为工作台来源合同。
- 工作台登记请求只等待来源授权/结构门控及案件壳、解析任务、pending SourceRecord 的原子持久化；同一 Legacy Parser 由受控可去重执行器异步执行，快速路径完成 Parser 和草稿落库后立即进入 `review_ready`，递归来源 metadata/fingerprint 只在其后独立复核，不能让 HTTP 请求或审核入口等待完整扫描，也不能留下永久 queued/running 状态。
- 不改变案件名称与案件摘要的语义，也不因修改案件名称而改变当前正式 RAR 基础名规则。
- 不在首版删除案件记录时删除正式 RAR、Manifest 或 Word；是否显式删除正式产物留待独立产品决策。
- 不把浏览器 `localStorage` 默认值作为案件或共享默认值事实源；共享默认值只能通过后端
  `/workbench/defaults` 持久化并显示独立保存结果。

## Invariants

1. Legacy 是唯一正式生产输出链路；`InspectionReport` 是案件草稿的报告主体，禁止以 Canonical 替代它。
2. 正式归档必须由用户明确触发或确认“立即开始”，最终以验证后的 Manifest 为唯一正式依据。
3. 审核界面颜色只表示来源，不得进入 Word；正式 Word 继续使用正式黑字和现有安全门控。
4. 案件顺序、人员顺序、光盘映射、模板引用和字段来源都必须后端持久化，不能只保存在页面内存或隐式 localStorage。
5. 新案件字段遵循“当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值”；共享默认值仅补齐 Parser 的空白、缺失或空数组，且不回写已有案件。
6. 案件记录、运行任务、临时文件和正式产物拥有独立生命周期与清理策略。
7. 无登录环境中的接管、默认值迁移和共享默认值修改只能记录 client instance ID、session ID、可选本地显示名称、部署实例和时间，不得表述为认证人员身份。

## Five implementation phases

1. **案件草稿、共享默认值、任务和工作台基础**：建立持久化合同、案件壳、解析任务、案件卡片、自动保存、恢复、租约、删除前置条件和任务状态壳；内部再经过 1A（SharedTypes/schema/repositories）、1B（services/API）、1C（工作台/自动保存/租约）、1D（刷新重启恢复/兼容回归/人工验收）四道小门控，先不改变正式归档安全门控。
2. **审核顺序、人员卡片、字段来源和导出命名**：实现检材/人员稳定顺序、来源状态、默认值来源标识和逐次 Word 下载名称；顺序统一投影到 Legacy 正文与附件。
3. **归档映射、后台归档和阶段里程碑进度**：把规划、稳定槽位映射、用户确认、资源准入和可恢复后台归档接入案件任务；以真实门控推进固定 `workflow_milestone`，并在案件工作台卡片直接展示；最终以验证 Manifest 锁定结果。
4. **已审核预置模板**：实现模板注册、版本和验收记录、案件模板引用、切换失效和下次导出重新校验。
5. **综合验收、清理和 Shadow 边界**：完成多案件并发、恢复、清理、Legacy 兼容、正式产物保护和人工验收；仅记录 Shadow 暂停边界，不开展真实样本治理。

每个阶段都必须在版本化合同上独立实现，完成定向测试、前后端全量测试、工程门控和轻量开发
冒烟，并记录为“实现完成、自动验证通过、等待最终集成人工验收”。轻量冒烟不等同正式人工
验收；Phase 1–4 全部实现后再统一执行完整 Harness、集成检查和一次完整端到端人工验收，
随后进行最终 Review 和归档判断。阶段 checkpoint commit 仅在用户单独授权后创建。后续阶段
不得读取前端隐式状态来补足前置阶段缺失的数据；未完成能力必须显式显示为未就绪或由兼容
适配器拒绝，而不能假定“旧页面状态一定存在”。

仓库中已有的其他活跃变更包不在本轮自动删除、归档或降级。本包进入实施前，必须逐项标记与这些变更的关系（依赖、替代、暂停或无关），不得把已有 Canonical 任务或 Shadow 真实样本任务隐式带入本包。

## Impact

本变更跨越所有业务层；本轮 Windows 兼容修复只影响后端 Layer 21 资源采样/准入和合成测试，不改变公共 HTTP DTO、Legacy 正式输出门控或 Scheduler/Worker 的第二套实现。

| 层级 | 计划影响 | 计划内容 |
|---|---|---|
| Layer 0 SharedTypes | 新增/修改 | 案件壳/草稿、SourceRecord、来源状态、无登录审计身份、任务进度、租约、归档槽位、模板引用和 API DTO |
| Layer 1 SharedConstants | 新增 | 状态枚举、进度阶段、错误码、清理策略和版本常量 |
| Layer 2 SharedUtils | 新增/修改 | 自然排序、光盘编号唯一性、下载名称校验、阶段里程碑转换和状态迁移纯函数 |
| Layer 10 FE Hooks | 新增/修改 | 案件查询/自动保存、租约心跳、任务订阅、默认值迁移和导出弹窗流程 |
| Layer 11 FE Components | 新增/修改 | 工作台卡片、来源标记、检材/人员拖拽卡片、归档映射表、状态进度和模板选择 |
| Layer 12 FE Pages | 新增/修改 | 工作台路由与审核页编排；保留现有 Legacy 审核和导出边界 |
| Layer 20 BE Repository | 新增 | SQLite 业务 DTO/元数据与 opaque asset 引用、SourceRecord、文件系统资产索引、模板注册、任务锁和运行清理记录 |
| Layer 21 BE Services | 新增/修改 | 案件壳/解析失败、默认值双写、租约、任务调度、资源准入、跨平台资源采样、归档阶段里程碑、WinRAR spike 决策、模板和生命周期服务 |
| Layer 22 BE Controllers | 新增 | 工作台、默认值、任务、模板和映射 API 的参数校验与 DTO 转换 |
| Layer 23 BE Routes | 新增 | REST 路由注册；现有 `/records/*` 以 Legacy 兼容适配器保留 |

跨边界通信只通过 Layer 0 共享的 API 合同和 HTTP 调用；前端不得访问 SQLite、应用数据目录或人员库文件，后端不得依赖前端排序或 localStorage 作为正式输入。

## Acceptance overview

- 用户登记并验证授权报告目录后立即出现排队/解析中案件壳卡片；解析成功才写入完整 Legacy `InspectionReport`，解析失败保留失败任务卡片但不可审核、归档或导出。
- 解析成功后必须询问“立即开始压缩”或“稍后压缩”；稍后压缩持久化为 `archive_deferred`，立即压缩只进入现有 Legacy 显式压缩入口，不伪造 Phase 3 后台进度。
- 目录不存在、无权限、越界、结构无效和压缩包输入均以稳定错误码拒绝；API、卡片、任务、审计摘要和 SQLite 公共字段不包含绝对路径。
- 刷新浏览器和关闭软件后，案件卡片、草稿、任务状态、来源状态、顺序和模板引用可恢复；重启前运行中的 WinRAR 任务只标记 interrupted/failed_retryable，不自动重连或接管。
- 同一案件正常情况下只有一个有效编辑租约；接管有警告并留下审计记录。
- 解析和压缩期间不能直接删除；取消、进程结束、临时文件清理确认后才允许删除案件记录，且不删除正式产物。
- 预计卷与光盘编号逐卷展示，编号非空且在案件内唯一；replan 保留有效人工映射、新卷为待确认、删除卷清除映射，Manifest 验证后成为权威。
- Phase 3 进度固定为 `workflow_milestone`：只在等待、inventory/路径核对、前置检查通过、WinRAR 开始/成功、完整性通过、MD5 开始、Manifest 开始/验证完成等真实边界推进，单调且可持久化；它不表示 WinRAR 内部字节百分比。WinRAR 运行期间数值固定在 30%，不得自动增长、解析、钳制、平滑或估算。
- 案件工作台的每张案件卡片定位为“归档任务摘要”，默认只组织案件基本信息、当前归档状态/阶段、最多两行活动摘要和主要操作。创建 RAR 分卷时以不确定进度动画作为主要活动反馈，`总体里程碑：30%` 只能作为次要说明；分卷数量、输出总字节数和相对活动时间只证明可观察活动，绝不换算为完成比例。失败、取消、恢复中和完成状态用对应摘要替换普通活动指标，避免卡片高度随内部字段增长。
- 完整时间线、逐卷文件名/大小/MD5、Manifest 内容或路径、历史任务、Worker ID、内部租约、精确心跳时间戳、完整错误码/堆栈/技术日志、调度诊断和进程信息只进入归档详情；案件列表 API 只返回卡片所需的安全摘要。窄屏仍保留案件信息、状态、阶段文字和主要操作；颜色、动画都必须有文字替代，长文号、长错误摘要和大数字不能撑破布局。
- 输出暂时不变化不能单独判定失败或触发取消；压缩可能处于 CPU 密集或缓冲阶段。页面刷新从持久化摘要恢复；服务重启后在 Worker 重新取得任务所有权前显示恢复中或等待接管，不得显示“仍在运行”。最多 6 个压缩任务只是硬上限，资源不足时排队；现有 Legacy 显式压缩能力和全部归档门控保持可用。
- 每次 Word 导出都重新询问下载名称并校验，服务器物理文件名独立、安全、唯一且不可覆盖。
- 模板切换不触发压缩或 Manifest 重建，只使旧 Word 结果失效；再次导出重新校验并使用案件锁定的模板版本。
- Legacy 正式输出、完整归档门控、Manifest 校验、Word 安全门控和现有输出管理回归通过。

## Risks and mitigations

主要风险是从内存状态迁移到持久化状态时出现案件/共享默认值双写不一致、来源授权失效、旧草稿版本不兼容、重启后误接管 WinRAR、replan 错配人工编号、里程碑早于真实门控推进和清理误删正式产物。设计通过分别返回草稿/共享默认值结果、SourceRecord 复核、版本化迁移、任务 interrupted 状态与自有进程树回收、稳定槽位 ID、固定阶段转换、WinRAR pipe/ConPTY 失败证据、独立正式产物索引和删除白名单降低风险；具体决策见 `design.md`，实施顺序和验证证据见 `tasks.md`。
