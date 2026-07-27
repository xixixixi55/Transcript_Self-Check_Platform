# Design: 持久化案件工作台与归档任务协调

> 变更包：`persistent-case-workbench-and-archive-coordination`
> 设计状态：Phase 1B Service/API 与 Phase 1C 前端工作台已实现；Phase 1D 及后续阶段仍未开始

## 1. 总体架构决策

### D-001：以 CaseDraft 作为唯一编辑源，以 Legacy InspectionReport 作为报告主体

**决定**：案件草稿保存一个版本化的 Legacy `InspectionReport`，并在其旁边保存来源状态、顺序、模板引用、归档计划和任务引用。审核页面不再把 React state 视为持久化源；页面只负责展示和提交变更。

**理由**：当前正式 Parser、正文、附件和 Word builder 都围绕 Legacy DTO 工作。直接把 Canonical 引入草稿会同时改变解析、模板、Shadow 和导出合同，超出本轮边界。旁挂元数据可以实现恢复和新 UI，同时保持 Legacy 输出兼容。

**拒绝方案**：

- 只保存页面 JSON：刷新、重启和多案件切换都会丢失状态。
- 以 Canonical 替代 Legacy：违反当前生产边界，并把暂停的 Shadow/Canonical 工作重新引入本轮。
- 只保存最终 Word：无法恢复审核中间态，也无法在模板切换后安全重新生成。

案件创建采用两步状态：提交时先写入 `CaseShell + PARSE_QUEUED/PARSING`，解析成功后在同一案件 ID 上生成 `CaseDraft`；失败时只保留可重试任务卡片。这样工作台能立即反馈，不会把解析失败的半成品当作正式草稿。

### D-002：SQLite 保存事务性元数据，文件系统保存大对象和正式产物

**决定**：引入部署实例级 SQLite 元数据存储；SQLite 只保存 CaseShell/CaseDraft 业务 DTO、任务/租约/版本/索引元数据、SourceRecord 和 opaque asset 引用。Base64 图片、完整 HTML、原始 JSON 集合和其他大对象不进入 SQLite；来源快照、图片、解析缓存、临时归档目录和正式产物继续由受控文件系统资产管理。任何 Redis/Celery 或进程内缓存只能作为执行器/加速器，不能作为唯一状态源。

**理由**：本部署无登录且是本机 Windows 应用，案件壳、草稿和任务需要跨刷新、重启恢复；SQLite 可事务性更新和原子迁移，同时通过 opaque 引用避免把大报告和二进制内容塞入关系数据库。

**拒绝方案**：

- 继续使用进程内字典：重启即丢失，无法满足恢复。
- 只使用 localStorage：多用户共享、后台任务和安全清理无法统一。
- 让 Redis 成为唯一持久化：部署实例的恢复和正式产物索引会依赖额外服务，且不能替代文件系统安全门控。

### D-003：后端任务记录是调度与恢复边界

**决定**：解析、归档、Word、清理都登记为 `TaskRecord`。任务有 `task_id`、`case_id`、类型、状态、阶段、进度快照、输入版本、尝试次数、进程标识、错误码、取消请求、创建/开始/结束时间。服务重启时，原 `running` 任务统一转为 `interrupted` 或 `failed_retryable`；只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，并等待用户确认后重新执行，不自动重连或接管 WinRAR。

**理由**：把“后台仍在运行”“已中断”“可重试”“需要人工确认”区分开，才能支持多案件、取消、删除保护和真实进度，同时避免把半成品 RAR/Manifest 当作正式结果。

### D-002A：图片二进制使用案件绑定的受控资产存储

每个图片使用 `asset-<opaque-random-id>` 作为公共引用。二进制写入部署实例数据目录下的案件隔离资产目录，SQLite `asset_references` 只保存 `asset_id`、`asset_kind=image`、SHA-256、原始文件名的安全投影、扩展名、媒体类型和大小。上传先写同一受控目录中的临时文件，校验真实 JPG/JPEG/PNG 签名并原子改名，数据库引用创建成功后才返回 DTO；失败时删除临时或未登记文件。单张上限 10 MiB，案件上限 200 张/1 GiB，过期未引用资产和孤立临时文件按宽限期清理。

草稿只保存 opaque 引用；新增/替换/删除图片先通过租约保护的资产 API，再通过 `CaseDraft` revision 保存引用。revision 冲突不会释放或覆盖另一会话的引用。读取接口按 `case_id + asset_id` 校验归属并校验指纹，缺失/损坏返回稳定错误码。前端恢复、预览和 `/records/export` 适配器均读取持久化二进制，Legacy 模板、图片缩放、VML、分页和正式归档链路不变。

## 2. 共同数据合同

### 2.1 核心实体

| 实体 | 关键字段 | 权威关系 |
|---|---|---|
| `CaseShell` | `case_id`, case name/summary, source ref, parse task ref, lifecycle, timestamps | 提交报告后立即创建；解析成功前不含可审核 `report` |
| `CaseDraft` | `case_id`, `case_number`, `case_name`, `case_summary`, `report`, `report_version`, `field_states`, opaque asset refs, `template_ref`, `archive_plan_id`, `lifecycle`, timestamps | 解析成功后的审核根实体；`case_name` 不改变 RAR 基础名；不含 Base64/HTML/原始 JSON 大对象 |
| `SharedDefaults` | singleton `deployment_id`, `revision`, 文号/地点/方法/硬件/有序人员/光盘前缀 | 部署实例共享；新案件复制值和来源标记，当前案件用户修改经校验和防抖后同时更新共享默认值 |
| `FieldState` | `field_path`, `subject_id`, `source`, `confirmation`, `revision`, `last_changed_at` | 来源状态覆盖可编辑叶子、检材、人员、图片组；派生显示字段不单独建状态 |
| `EditLease` | `case_id`, `session_id`, owner token, `last_heartbeat_at`, `expires_at`, takeover audit | 一个案件最多一个有效租约；15 秒建议心跳，2 分钟失联可接管 |
| `TaskRecord` | `task_id`, `case_id`, `kind`, `status`, `stage`, `percent`, counters, input revision, retry/cancel/error | 任务状态和恢复依据；压缩运行数硬上限 6 |
| `SourceRecord` | opaque `source_id`, internal path, allowed root grant, source type, case/task refs, metadata/fingerprint, accessibility/review status | 来源授权与重启复核权威；绝对路径只存在后端受控存储 |
| `ArchivePlan` | `plan_id`, `plan_revision`, input inventory revision, ordered `volume_slots`, mapping revision | 预计计划不是正式依据；最终由 VerifiedManifest 收敛 |
| `VolumeSlot` | stable `slot_id`, ordinal, logical span/capacity, status, `disc_mapping` | 槽位身份独立于预计文件名，replan 尽量沿用 |
| `DiscMapping` | `slot_id`, full `disc_number`, `date`, source `default|user`, confirmation | 编号非空、案件内唯一；日期独立 |
| `TemplateVersion` | template ID, semantic version, file fingerprint, validation rules, approval record, asset reference | 仅 approved 版本可被案件引用 |
| `ExportArtifact` | artifact ID, case ID, kind, physical safe path/name, user download name, source revisions, validity, manifest/template refs | 正式 RAR/Manifest/Word 与案件记录独立清理 |

所有实体必须带 schema/version 字段或可迁移版本；跨表更新使用事务。接口返回的路径必须是受控的 opaque ID 或安全相对标识，不暴露原始本机路径。

### 2.2 案件生命周期

```text
CASE_CREATED
  -> PARSE_QUEUED -> PARSING -> REVIEW_READY
  -> PARSE_FAILED_RETRYABLE
  -> ARCHIVE_DEFERRED
  -> ARCHIVE_QUEUED -> ARCHIVING -> ARCHIVE_VERIFIED
  -> EXPORTING_WORD -> EXPORTED

任一可恢复阶段 -> FAILED_RETRYABLE
服务重启时 running WinRAR -> INTERRUPTED -> 用户确认后重新执行
用户取消 -> CANCELLING -> CANCELLED (进程和临时文件确认清理后)
EXPORTED -> RECORD_RETENTION_EXPIRED -> RECORD_CLEANED
```

`CASE_CREATED`/`PARSE_QUEUED` 只代表案件壳和任务已持久化，不代表存在可审核报告；`PARSE_FAILED_RETRYABLE` 不能进入审核、归档或导出。`REVIEW_READY` 不代表已压缩；`ARCHIVE_VERIFIED` 必须同时有验证后的 Manifest；`EXPORTED` 是 Word 成功并通过现有门控，不代表正式产物可被案件清理删除。状态迁移必须由后端服务校验前置状态，前端不能直接写目标状态。

### 2.3 任务状态和进度

任务状态：`queued | running | cancelling | interrupted | succeeded | failed_retryable | failed_terminal | cancelled | blocked`。归档阶段：`inventory | planning | winrar | integrity | md5 | manifest`。

默认权重固定在版本化常量中：inventory 15%、planning/replan 10%、WinRAR 45%、完整性校验 10%、MD5 15%、Manifest 生成和验证 5%。实际实现不得在组件内重复硬编码；阶段权重由 SharedConstants 提供。

阶段进度必须使用实际计数或受支持的 WinRAR 结构化进度信号：

```text
stagePercent = clamp(completedUnits / max(totalUnits, 1) * 100, 0, 100)
taskPercent = floor(sum(weight[i] * stagePercent[i]) / 100)
```

为防止 replan 造成回退，任务保存每个阶段的 `reported_percent`，只允许取历史最大值；replan 发生时重新记录计划版本和原因，但不能用新总数把已展示百分比降低。阶段文字必须同时说明“规划重算/等待资源/正在 WinRAR”等当前状态。

Phase 3 开始前必须先完成当前正式 WinRAR 版本的进度能力 spike，验证信号来源、解析稳定性、失败行为和合成输入下的百分比一致性。spike 未通过时，Phase 3 不得宣布完成；迁移期间保留现有 Legacy 显式压缩路径，不用时间、循环动画或输出文件大小冒充百分比，也不因此直接让现有压缩全部失效。若当前版本能力不足，先汇报并选择受支持版本或适配方式，再决定新任务进度接入。

## 3. 顺序、来源和 Legacy 投影

### 3.1 检材顺序

解析器只负责产生 `evidence_list` 的报告原始顺序和识别结果。自然排序是一次性的默认初始化：所有编号唯一且可识别才按数字片段自然升序；重复或无法识别时保留原始相对顺序。草稿保存 stable `evidence_id` 与有序数组；拖拽只改变数组，不修改报告原始来源快照。

正文、附件摘要、附件 1/2/3 和 Word builder 都接收同一个 `ordered_evidence` 投影。任何下游模块不得按显示名、文件名或自己的 `sort()` 再排序。旧 DTO 缺少 stable ID 时，在案件创建时按原顺序生成一次并固化。

### 3.2 检查人员

人员库仍由现有后端 `InspectorRepository` 管理；案件保存 `InspectorSnapshot[]`，每项复制姓名、单位、警号和稳定引用。审核 UI 用卡片显示三项，不在卡片内直接编辑；拖拽更新案件快照。确认保存后，同一顺序写入共享默认人员顺序，供以后新案件继承；当前案件快照不因人员库后续修改而变化。

### 3.3 来源状态

字段路径采用稳定的业务路径，例如 `introduction.document_number`、`evidence.<id>.model`、`inspectors.<id>.badge_number`、`photo_groups.<id>`。用户编辑统一调用 `markUserEdited`，不允许组件自行猜测颜色。系统默认继承调用 `markSystemDefault`；解析初始化调用 `markReportParsed`。待确认是独立的 `confirmation` 状态，必须通过文字和导出门控表达。

Word builder 只接收字段值和 Legacy 投影，不接收 UI 来源颜色。导出前把仍 pending 且受门控约束的字段交给现有校验服务；不得通过把状态改成 confirmed 来绕过业务校验。

### 3.4 解析值、共享默认值和双写状态

案件初始化对每个字段执行固定优先级：有效且非空的报告解析值优先，FieldState.source 为 `report`；报告缺失、为空或无法识别时才读取共享默认值，source 为 `system_default`；两者都不可用时保持待填写或 `pending`；用户修改后统一为 `user`。`pending` 只属于 confirmation，不是 source 的替代值。

文号、检查地点、检查方法、检查硬件、光盘编号前缀和检查人员顺序属于“案件字段 + 部署共享默认值”的双写字段。自动保存服务在校验和防抖完成后提交两个独立操作，并分别返回 `draft_save_status` 与 `shared_defaults_save_status`。一侧失败不能伪装为整体成功，也不能静默回滚另一侧已经成功的写入；前端显示两个结果和重试入口。人员拖拽同样更新当前案件 `InspectorSnapshot[]` 与共享默认人员顺序。

### 3.5 无登录审计身份

系统没有登录时，接管、默认值迁移、共享默认值修改和重要任务操作使用 `ClientIdentity`：`client_instance_id`、`session_id`、可选 `local_display_name`、`deployment_instance_id` 和时间。该对象只表示本地会话审计，不表示认证人员、真实民警或权限证明。API 与日志使用这组 opaque/本地标识，不推断真实身份。

### 3.6 SourceRecord 与来源复核

`SourceRecord` 是案件壳和解析任务的来源权威，包含 opaque `source_id`、source type、后端内部路径、允许根授权、case/task 绑定、metadata/fingerprint、访问状态和最近复核时间。绝对路径只能存在于后端受控存储和内部审计字段；前端 DTO、外部 API、普通日志和错误消息只返回 opaque ID、安全摘要和错误码。

来源登记和 Legacy 快速解析前必须验证允许根、路径存在性、权限、链接安全性和报告核心结构；这条快速路径不执行完整目录 metadata/fingerprint。解析器自身读取的关键输入必须保持稳定，成功生成草稿后立即进入 `review_ready`。完整 metadata/fingerprint 作为独立的后置来源复核异步执行；复核失败只将 SourceRecord 标记为 `requires_reselection` 并提示重新选择，不回退已成功生成的草稿或案件生命周期。显式重试、来源替换和立即压缩仍须经过相应的完整来源门控。来源、图片和其他大对象只通过 opaque asset 引用进入 CaseDraft，SQLite 不保存内容本体。

## 4. 归档计划、稳定槽位和 Manifest

初次规划生成有序 `VolumeSlot`，每个槽位获得独立 UUID。规划输入包括经过完整 inventory 的输入修订、容量策略和共享光盘前缀；预计卷名只是展示属性，不是槽位身份。映射默认值由前缀和槽位序号生成，保存时校验非空和案件内唯一。

replan 接收上一版 `VolumeSlot[]` 和新规划结果，使用槽位 lineage/逻辑序号、容量区间和稳定输入分片标识做匹配；不读取或比较预计 RAR 文件名。能够证明仍代表同一逻辑分卷的旧槽位保留 `slot_id` 和有效人工映射；无法匹配的槽位新建 ID 并置为 `pending`；不再存在的槽位和映射标记 removed，不进入最终 Manifest。

归档执行前必须重新验证案件草稿版本、映射唯一性、输入 inventory、路径/链接/文件变化和计划版本。WinRAR、完整性、MD5 和 Manifest 验证全部成功后，生成 `VerifiedManifest` 并把它保存为 `ExportArtifact`；Word 的附件 3 和下载元数据只能从此 Manifest 读取最终卷和光盘编号。

## 5. 调度器和资源准入

调度器分两层：

1. **队列层**：按任务优先级和创建时间选择 queued 任务，保证压缩 `running` 数不超过 6，解析任务不占用压缩槽位。
2. **资源准入层**：在启动每个 WinRAR 前读取配置化的最小可用磁盘空间、临时空间、CPU 使用率、IO 使用率、输入规模上限、WinRAR 进程数和全局进程数。任一条件不满足则保留 queued，并返回具体原因。

准入配置保存在部署配置中并有版本；不允许前端覆盖安全阈值。任务运行中若资源降至保护阈值，调度器停止启动新任务并可请求当前任务有序取消；不强杀已写入的正式产物。WinRAR 进程必须由任务记录绑定。服务重启时不自动重连或接管 WinRAR：先把原 running 任务标记为 `interrupted`/`failed_retryable`，只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，并将半成品 RAR/Manifest 标记为不可发布；用户确认后重新执行。断点续压和 WinRAR 重连不在本包范围内。

## 6. API 和前端编排

Layer 0 只定义 DTO 和错误合同，建议路由族如下；具体路径实现时仍须与现有路由注册方式兼容：

| 路由族 | 作用 |
|---|---|
| `/workbench/cases` | 分页列表、创建、读取、草稿补丁、删除前检查 |
| `/workbench/cases/{case_id}/lease` | 获取、心跳、释放、强制接管 |
| `/workbench/cases/{case_id}/archive-plan` | 读取预计计划、更新卷映射、确认计划 |
| `/workbench/tasks` | 任务列表、状态、取消、重试、进度快照 |
| `/workbench/defaults` | 共享默认值读写、旧 localStorage 一次性迁移 |
| `/workbench/sources` | 来源选择、SourceRecord 摘要、来源复核和失效后的重新选择 |
| `/workbench/templates` | approved 模板列表、版本和校验摘要 |
| `/workbench/cases/{case_id}/template` | 读写案件模板引用并使旧 Word 失效 |
| 现有 `/records/*` | Legacy 解析、归档和 Word 兼容适配；不得删除正式安全门控 |

自动保存接口使用 `If-Match`/草稿 revision 或等价字段；案件字段双写接口必须分别返回 draft save 和 shared-default save 状态。任务状态可用短轮询起步，但状态源必须是后端任务记录，后续可替换为 SSE 而不改变 DTO。前端工作台只消费案件卡片 DTO，审核页按 `case_id` 加载完整草稿和租约，不保留第二份“正式顺序”，也不接触 SourceRecord 的绝对路径。

Phase 1B 的实际 API 入口为 `/api/v1/workbench/*`：工作台通过 JSON
`POST /workbench/cases` 登记本机报告目录路径。服务使用
`ArchiveAuthorizationService` 校验目录存在性、目录类型、授权根、访问权限和报告结构，
并在部署实例 SQLite 中原子写入 CaseShell、parse TaskRecord、SourceRecord 和提交审计，
再用后台任务执行 Legacy 解析；案件列表默认返回 6 个 opaque 卡片。绝对路径只保存在
受控的部署实例 locator 文件中，SQLite 业务字段只保存 opaque locator/root 引用，公共
DTO、任务、审计摘要、日志和错误消息不返回绝对路径。来源重新选择使用 JSON
`source_path`，不接受工作台 ZIP/RAR 上传。

解析成功后，`POST /workbench/cases/{case_id}/archive-decision` 以
`expected_revision` 原子记录 `immediate` 或 `deferred`：`deferred` 持久化为
`archive_deferred` 并在刷新后显示“暂未压缩”；`immediate` 持久化为
`archive_queued`，创建 opaque Legacy preview source，并由现有 `/records/archive`
显式压缩入口继续执行。该入口不引入 Phase 3 后台编排或伪造进度。解析失败只保留可重试
卡片，不出现压缩询问。

案件列表默认返回 6 个 opaque 卡片。详情返回 shell、可选 draft、SourceRecord
摘要和 parse task；草稿保存使用 `expected_revision`，冲突返回 HTTP 409。Phase 1C
前端通过案件工作台入口加载分页卡片，通过 `case_id` 加载独立详情，并以后端 revision
保存草稿；自动保存、共享默认值和租约状态分别展示。
旧前端 `RecordGeneratePage.tsx` 不再作为独立生产页面；`/electronic-inspection/generate`
和 `/generate` 仅保留兼容重定向到案件工作台。后端 `/records/*` 继续保留 Legacy
解析、归档和 Word 合同，不从工作台删除或改写正式 RAR、Manifest、Word 产物。

## 7. 模板注册和导出失效

预置模板注册表由后端维护，资产来自受控 `word_templates` 或应用数据目录。注册必须记录模板 ID、版本、文件指纹、占位符/结构校验规则、通过的验收记录和注册时间。删除或替换模板资产不会静默改变已保存案件；案件引用的版本必须可复现，否则导出阻止并报告模板缺失。

案件模板切换事务只更新 `template_ref`、模板 revision 和旧 Word artifact 的 validity；不触碰 `ArchivePlan`、`VerifiedManifest`、RAR 或归档任务。Word 导出再次执行模板校验、Legacy report 投影、VML/分页/表格/附件检查和现有安全门控。

## 8. 清理、取消和产物保护

清理服务只依据后端生命周期和可删除资产类型。案件删除前置检查必须确认：无 `PARSING`/`ARCHIVING` 任务、取消请求已完成、WinRAR 进程已退出、临时目录已清理、没有未保存的租约冲突。首版允许删除案件记录、草稿、任务记录和临时缓存；正式 RAR、Manifest、Word 的资产索引及文件保留。自动清理只处理已成功导出的案件记录到期项，跳过尚未导出和失败待重试案件。

任何正式产物删除 API 都不在本变更包中注册；未来若产品允许显式删除，应作为单独 Level 3 决策、权限和双重确认设计。

## 9. 分阶段依赖与独立交付

| 阶段 | 可独立验收的合同 | 明确前置条件 | 禁止的隐式依赖 |
|---|---|---|---|
| 1 | CaseDraft/Defaults/Task/Lease/Workbench v1 | 现有 Legacy parse/export 继续可用 | 不读取页面 state 推断后端草稿 |
| 2 | Order/Inspector/Provenance/DownloadName v1 | 只依赖阶段 1 的版本化草稿 DTO；可用合成草稿测试 | 不要求阶段 3 归档完成才能保存编辑 |
| 3 | ArchivePlan/Mapping/TaskProgress v1 | 依赖阶段 1 task/asset contract；Legacy 归档门控保持原实现 | 不用旧预计文件名、RAR 大小或假动画作为权威 |
| 4 | TemplateRegistry/TemplateRef v1 | 依赖案件草稿和 Word export DTO；可用注册 fixture | 不要求重新压缩或重建 Manifest |
| 5 | integrated acceptance/cleanup boundary | 阶段 1-4 的合同和定向验收证据 | 不把 Shadow 真实样本差异治理混入验收 |

### Phase 1 internal gates

| 小门控 | 范围 | 必须证明 |
|---|---|---|
| 1A | SharedTypes、SQLite schema/migration、Repositories | CaseShell/CaseDraft、SourceRecord、ClientIdentity、双写结果、opaque asset 引用和 SQLite 大对象拒绝规则可持久化、迁移、回滚 |
| 1B | Services 和 API | 提交即建壳、解析任务失败/重试、来源复核、默认值优先级、草稿/共享默认值双写状态、interrupted 重启语义和删除前置条件可通过 API 表达 |
| 1C | 工作台、自动保存和租约 | 6 卡片分页、排队/解析中/失败状态、自动保存、15 秒心跳、2 分钟接管警告和分别显示保存结果 |
| 1D | 刷新/重启恢复、兼容回归和人工验收 | 重启不自动接管 WinRAR；自有进程/staging 清理可证明；Legacy 解析/归档/Manifest/Word 回归通过，并完成人工验收 |

每阶段提交前运行该阶段的类型、架构和定向测试；所有阶段完成后才考虑完整 Harness 门控，并按 `AGENTS.md` 在运行 `verify:full` 前询问执行者。

### Phase 1C request liveness correction

The workbench submission request performs only source authorization and bounded report-structure validation before atomically creating the CaseShell, parse Task, and pending SourceRecord. It MUST NOT attach Legacy parsing to FastAPI `BackgroundTasks` or wait for recursive source metadata/fingerprint work. A bounded in-process dispatcher starts the same Legacy `parse_report` path after the transaction; the fast path is `parse readiness -> Legacy Parser -> draft persistence -> review_ready`. Full source metadata/fingerprint verification starts only after `review_ready`, remains independent of the parse task lifecycle, and changes only SourceRecord status when it fails. The dispatcher deduplicates an active `(case_id, task_id)` and treats unhandled parse-worker exceptions as retryable task failures. Restart recovery continues to use the persisted `queued`/`running` to `failed_retryable`/`interrupted` contract.

## 10. 兼容策略与安全门控

- 现有 `POST /records/parse`、`/records/archive`、`/records/export` 在迁移期间保留 Legacy DTO 适配；新工作台调用新路由并通过共享类型通信。
- 归档阶段可把现有同步执行封装为一个可持久化任务 worker，先不重写 `ArchiveExecutionService` 的安全检查；完成一项门控才更新任务阶段。
- WinRAR 进度能力必须在 Phase 3 前以 spike 验证。spike 未通过时，保留现有 Legacy 显式压缩路径，不能用新进度门控直接让现有压缩失效；断点续压和重连不作为迁移方案。
- 预览沿用最近修复的轻量路径，不提前创建完整 `ArchiveContext`；完整 inventory、WinRAR 和 Manifest 仍只在明确归档动作后运行。

## 11. Phase 1C 统一生产入口收敛

案件工作台是“生成笔录”的主生产页面。案件详情页复用现有 `RecordEditorForm`、字段
配置、日期时间校验、附件编辑器、预览数据构造和 `useRecordExport`，只把持久化
`CaseDraft`、revision、编辑租约、来源状态和案件状态接入展示层。旧页面的上传/解析
编排和 localStorage 默认值不再由工作台使用；共享默认值改由 `/workbench/defaults`
持久化并单独显示保存结果。

工作台编辑器必须覆盖 Legacy 审核字段、数据摘要、附件信息、图片编辑、表单校验、
预览、正式 Word 导出和自定义下载文件名，但不复制旧页面的拥挤布局、混合上传流程或
独立业务规则。旧前端生成地址只做兼容重定向，`/records/*` 后端兼容接口和正式输出
安全门控保持不变。图片二进制继续遵循现有浏览器文件到导出调用的行为；CaseDraft
只持久化结构化附件数据和 opaque 资产引用，不把图片内容写入 SQLite。
- 归档上下文、Manifest、Word 和 RAR 的现有版本/指纹/路径变化/链接检查不能被“可恢复”接口绕开；解析缓存、案件草稿和模板校验结果不能充当正式证据。
- SQLite 只保存业务 DTO、元数据和 opaque asset 引用；不保存 Base64 图片、完整 HTML、原始 JSON 集合或其他大对象。绝对路径只存在于后端受控 SourceRecord，不进入 API、日志和前端。
- 不保存真实案件、人员、IMEI、序列号、本机路径、RAR、Manifest、DOCX 或运行输出到仓库；测试使用明确 `SYNTHETIC/TEST/FIXTURE` 数据。

## 11. 测试设计

- SharedUtils：自然排序回退、编号唯一性、文件名校验、进度单调聚合、状态迁移边界、解析/默认优先级和双写结果聚合。
- Repositories/Services：SQLite 事务、版本冲突、租约、迁移幂等、CaseShell/解析失败、SourceRecord 复核、ClientIdentity、opaque asset 边界、稳定槽位 replan、调度准入、取消清理和模板指纹。
- Hooks/Components：RTL 验证来源标记、拖拽顺序、租约警告、6 卡片分页、导出名称弹窗和任务阶段展示。
- Controllers/Routes：HTTP 集成验证自动保存、草稿/共享默认值分别返回、来源复核、恢复中断、任务取消、删除保护、模板切换不触发归档和 Manifest 结果投影。
- WinRAR spike：使用合成输入验证当前正式版本进度信号；未通过时记录能力缺口，验证 Legacy 显式压缩仍可用，不产生假进度。
- E2E/人工：使用合成多案件、多任务和合成模板；真实大报告只在用户明确执行的外部验收中使用，证据不得进入仓库。

## 12. 与已有活跃变更包的协调

仓库当前存在其他活跃 OpenSpec 变更包，其中部分包含 Canonical、模板平台或归档规划的候选设计。本包不删除、不改写、不自动归档这些包；它只为本轮甲方确认的五阶段工作定义新的统一合同。

实施前必须完成一次重叠审计并在本包任务记录中标记每个重叠项：

- 与案件草稿、顺序、默认值、归档任务或模板选择重复的任务，统一迁移到本包的合同，避免两套 DTO、两套状态机或两套权威来源并存。
- Canonical 适配、Canonical 正式输出、Shadow 真实样本差异治理相关任务保持暂停或另行处理，不作为本包前置条件。
- 仍需保留的现有 Legacy 安全门控和已验收模板资产作为兼容依赖，不复制其实现合同。

若活跃包的设计与本包的 Legacy-only、Shadow 暂停或正式产物保护边界冲突，必须在开始实现前记录冲突处理决定；不能靠任务执行顺序或前端 feature flag 隐式解决。
