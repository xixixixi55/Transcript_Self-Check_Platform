# Design: 持久化案件工作台与归档任务协调

> 变更包：`persistent-case-workbench-and-archive-coordination`
> 设计状态：Phase 1–4 实现、自动化验证和真实浏览器复验已完成；2026-07-30 首次最终集成人工验收发现正式应用生命周期未接入 Archive Scheduler/Worker，随后补齐 runtime 接线、Windows 缺少 `busy_time` 的可选指标降级、staging ownership marker 发布时序，以及工作台 autosave 与归档决策的 revision 协调。2026-07-31 D 盘隔离环境真实浏览器复验通过，Phase 3、Phase 4 和 Phase 1–4 最终集成人工验收已通过；RAR/Manifest/MD5、取消/重试、停止/重启恢复和真实双会话冲突证据见 `tasks.md`。设计仍为 Demo-ready（有条件），不是 Production-ready；`1D-017R`、Final Review、Production Review、OpenSpec archive 和 Phase 5 仍未完成；TD-1 至 TD-6 保留。

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

**决定**：`TaskRecord` 是解析任务和最小归档尝试记录的状态边界；它不是本阶段的调度器或持久化归档 Worker。任务有 `task_id`、`case_id`、类型、状态、阶段、进度快照、输入版本、尝试次数、进程标识、错误码、取消请求、创建/开始/结束时间。服务重启时，解析任务按既有 `queued`/`running`/`cancelling` 到 `failed_retryable`/`interrupted` 的合同恢复；已经进入现有 Legacy 显式归档入口的归档尝试转为 `interrupted`，案件生命周期转为 `archive_interrupted`。恢复只等待用户确认后重新执行，不自动重连、接管、等待或重新开始 WinRAR。

**理由**：把“后台仍在运行”“已中断”“可重试”“需要人工确认”区分开，才能支持多案件、取消、删除保护和可恢复的阶段里程碑，同时避免把半成品 RAR/Manifest 当作正式结果。

### D-003A：Phase 1D 只记录归档尝试，不建设归档 Worker

Phase 1D 在现有 `/records/archive` Legacy 显式入口外围增加最小归档尝试记录：启动现有同步归档执行前登记不可猜测的 opaque `attempt_id`、案件/草稿 revision、受控 staging 标识和系统创建时间；执行结束后登记成功或安全失败。该记录只用于恢复判定、资源归属证明和审计诊断，不负责排队、调度、并发限制、进度计算、断点续压或自动重试。

重启恢复规则固定如下：

- `archive_queued` 或 `archiving` 只要在重启时仍未形成已验证正式产物，就转为 `archive_interrupted`；关联归档尝试为 `interrupted`，错误码使用稳定的 `ARCHIVE_RESTART_INTERRUPTED`。
- `archive_interrupted` 下已有 `CaseDraft` 仍可查看和编辑；页面必须提示“上次压缩因应用重启或执行中断未完成”。半成品 RAR/Manifest 不得作为正式产物使用。
- `archive_interrupted -> archive_deferred` 是允许的显式转换：用户选择“稍后压缩”后，案件进入 `archive_deferred`，不创建新 handle 或归档尝试，并保留上次中断的审计/诊断记录，不得静默清除中断提示历史。
- `archive_interrupted -> archive_queued` 只有在用户重新确认来源、再次点击“立即压缩”，来源复核通过，并且后端原子创建新的 `attempt_id`/归档尝试记录和新的 opaque Legacy context 后才允许。新尝试被后端接受后案件才离开 `archive_interrupted`。
- 新尝试创建、来源复核或 handle 创建任一失败时，案件保持 `archive_interrupted`，不得产生可执行的半成品尝试。
- `archive_interrupted` 不得直接转换为 `archiving`、`archive_verified`、`exporting_word` 或 `exported`；不得恢复旧 handle、复用旧半成品或自动重新启动压缩。
- `archive_deferred` 在重启后保持不变；已验证的 `archive_verified`、`exporting_word` 或 `exported` 记录及其正式产物不因恢复流程回退或删除。

最小归档尝试记录的职责仅限于：识别重启前未完成操作、证明自有 staging/进程资源归属、记录接受/完成/中断/失败/清理结果，以及支撑幂等恢复和正式产物保护。它不属于 Phase 3 归档任务平台，不提供持久化 Worker、任务队列、多任务调度、进度百分比、自动重试、WinRAR 续跑或分卷重规划。

记录的内部状态采用 `accepted | running | succeeded | failed | interrupted`，另有 `cleanup_status` 记录 `not_required | pending | succeeded | failed | unknown`。重启只将未完成的 `accepted/running` 尝试转为 `interrupted`；已经完成且通过归档门控、已登记验证 Manifest 的 `succeeded` 尝试不可被恢复流程改回 `interrupted`。新一轮确认必须创建新的 `attempt_id`，不得复用旧记录。

记录可以在后端内部保存 `attempt_id`、案件/草稿/source revision、进程 PID、进程启动时间、进程命令行、内部 staging locator、ownership marker 摘要和安全错误码；绝对路径、PID、进程启动时间、进程命令行和内部 locator 只用于后端归属证明和诊断，不进入公共 API、DTO、普通日志或前端。

### D-003B：归属证明优先于 staging 和进程清理

清理自有 staging 至少必须同时满足以下五项证据：

1. 资源位于应用控制的 staging 根；
2. 存在系统生成且不可猜测的 `attempt_id`；
3. 数据库或受控索引中存在对应的归档尝试记录；
4. staging 中存在系统写入的 ownership marker；
5. marker 与归档尝试记录中的 `attempt_id`、部署实例和受控 staging 根匹配。

部署实例标识、进程 PID、进程启动时间和内部 locator 只能作为后端内部的附加归属证据。目录名、文件名、PID、进程名或命令行片段单独出现时都不足以证明归属。marker 的格式和存储结构由实现决定，但不得进入公共 DTO。

- 五项证据任一缺失、记录冲突、marker 不匹配或无法确认时，一律视为未知资源：不得删除、不得终止相关进程、不得覆盖，只留下不含绝对路径的安全诊断状态。
- 能证明属于本系统且属于未完成归档尝试的 staging，可以安全清理或隔离；多次执行必须幂等。
- 半成品 RAR 不得进入正式产物索引，半成品 Manifest 不得注册、返回或驱动 Word 导出。
- 清理失败不得阻止 CaseShell、CaseDraft、任务和图片资产恢复；清理状态必须可诊断，并允许之后再次安全处理。
- 已完成且通过校验的 RAR、Manifest 和 Word 属于正式产物，恢复和普通案件清理不得删除。

### D-002A：图片二进制使用案件绑定的受控资产存储

每个图片使用 `asset-<opaque-random-id>` 作为公共引用。二进制写入部署实例数据目录下的案件隔离资产目录，SQLite `asset_references` 只保存 `asset_id`、`asset_kind=image`、SHA-256、原始文件名的安全投影、扩展名、媒体类型和大小。上传先写同一受控目录中的临时文件，校验真实 JPG/JPEG/PNG 签名并原子改名，数据库引用创建成功后才返回 DTO；失败时删除临时或未登记文件。单张上限 10 MiB，案件上限 200 张/1 GiB，过期未引用资产和孤立临时文件按宽限期清理。

草稿只保存 opaque 引用；新增/替换/删除图片先通过租约保护的资产 API，再通过 `CaseDraft` revision 保存引用。revision 冲突不会释放或覆盖另一会话的引用。读取接口按 `case_id + asset_id` 校验归属并校验指纹，缺失/损坏返回稳定错误码。前端恢复、预览和 `/records/export` 适配器均读取持久化二进制，Legacy 模板、图片缩放、VML、分页和正式归档链路不变。

## 2. 共同数据合同

### 2.1 核心实体

| 实体 | 关键字段 | 权威关系 |
|---|---|---|
| `CaseShell` | `case_id`, case name/summary, source ref, parse task ref, lifecycle, timestamps | 提交报告后立即创建；解析成功前不含可审核 `report` |
| `CaseDraft` | `case_id`, `case_number`, `case_name`, `case_summary`, `report`, `report_version`, `field_states`, opaque asset refs, `template_ref`, `archive_plan_id`, `lifecycle`, timestamps | 解析成功后的审核根实体；`case_name` 不改变 RAR 基础名；不含 Base64/HTML/原始 JSON 大对象 |
| `SharedDefaults` | singleton `deployment_id`, `revision`, 文号/地点/方法/硬件/有序人员/光盘前缀 | 后端持久化的部署实例/本地操作者作用域事实源；草稿成功保存时仅稀疏更新用户明确修改的非空字段，后续新案件仅在 Parser 对应值为空时继承，已有案件不回写 |
| `FieldState` | `field_path`, `subject_id`, `source`, `confirmation`, `revision`, `last_changed_at` | 来源状态覆盖可编辑叶子、检材、人员、图片组；派生显示字段不单独建状态 |
| `EditLease` | `case_id`, `session_id`, owner token, `last_heartbeat_at`, `expires_at`, takeover audit | 一个案件最多一个有效租约；15 秒建议心跳，2 分钟失联可接管 |
| `TaskRecord` | existing task identity/status/stage/percent/timestamps/error/cancel fields; Phase 3 persists stage ordinal, heartbeat, output activity, worker ownership/recovery and allowed-action facts | 后端任务、恢复和诊断事实源；`percent` 在归档任务中只表示里程碑；可以包含不进入列表 DTO 的内部字段 |
| `ArchiveTaskCardSummary` | safe projection of case/task status, stage label/index/count, milestone, display times, compact activity, safe failure summary and allowed actions | 案件列表卡片专用摘要；不包含 Worker ID、路径、堆栈、日志、完整错误码、进程或内部租约 |
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
  -> ARCHIVE_INTERRUPTED (服务重启或执行中断，需要重新确认)
  -> EXPORTING_WORD -> EXPORTED

任一可恢复阶段 -> FAILED_RETRYABLE
服务重启时 running WinRAR -> INTERRUPTED -> 用户确认后重新执行
ARCHIVE_QUEUED/ARCHIVING --服务重启--> ARCHIVE_INTERRUPTED
ARCHIVE_INTERRUPTED --来源复核 + 用户重新确认--> ARCHIVE_QUEUED（新 attempt_id/new handle）
ARCHIVE_INTERRUPTED --用户选择稍后压缩--> ARCHIVE_DEFERRED（保留中断审计）
ARCHIVE_INTERRUPTED -X-> ARCHIVING/ARCHIVE_VERIFIED/EXPORTING_WORD/EXPORTED（不得跳过新尝试）
用户取消 -> CANCELLING -> CANCELLED (进程和临时文件确认清理后)
EXPORTED -> RECORD_RETENTION_EXPIRED -> RECORD_CLEANED
```

`CASE_CREATED`/`PARSE_QUEUED` 只代表案件壳和任务已持久化，不代表存在可审核报告；`PARSE_FAILED_RETRYABLE` 不能进入审核、归档或导出。`REVIEW_READY` 不代表已压缩；`ARCHIVE_INTERRUPTED` 不能进入 Legacy 归档，必须先重新复核来源并由用户再次确认；`ARCHIVE_VERIFIED` 必须同时有验证后的 Manifest；`EXPORTED` 是 Word 成功并通过现有门控，不代表正式产物可被案件清理删除。状态迁移必须由后端服务校验前置状态，前端不能直接写目标状态。

### 2.3 任务状态和进度

任务状态：`queued | running | cancelling | interrupted | succeeded | failed_retryable | failed_terminal | cancelled | blocked`。归档执行阶段至少区分 `queued | inventory | preflight_verified | winrar | integrity | integrity_verified | md5 | manifest | completed`。

Phase 1D 不新增归档调度或真实进度语义。归档尝试的 `interrupted` 只表示执行未完成和需要用户重新确认，不表示可以续跑、估算进度或恢复旧 WinRAR。

Phase 3 的进度种类固定为 `workflow_milestone`，表示归档工作流已经进入或完成的真实阶段，不表示 WinRAR 内部压缩字节百分比。里程碑由 SharedConstants 版本化定义，前端不得重复硬编码：

| 百分比 | 阶段 | 阶段文字 |
|---:|---|---|
| 0 | `queued` | 等待归档或资源准入 |
| 10 | `inventory` | 正在核对文件清单与路径 |
| 20 | `preflight_verified` | 归档前置检查通过 |
| 30 | `winrar` | 正在创建 RAR 分卷 |
| 75 | `integrity` | RAR 分卷创建完成，正在校验 |
| 85 | `integrity_verified` | 分卷完整性校验通过 |
| 90 | `md5` | 正在计算 MD5 |
| 95 | `manifest` | 正在写入并验证 Manifest |
| 100 | `completed` | 归档完成 |

只有对应真实阶段开始或门控成功时才持久化下一里程碑。WinRAR 进程运行期间保持 30，使用动态条纹或加载图标表示仍在运行，不允许数值随时间、输入/输出字节、文件数或视觉输出自动增长。WinRAR 成功退出后才进入 75；完整性门控通过后才进入 85；MD5 和 Manifest 分别在真实阶段开始时进入 90 和 95；只有完整 Manifest 验证和正式完成提交成功后才进入 100。

失败、取消或中断保存当前执行阶段、该阶段对应的最后里程碑、稳定错误码和安全错误摘要；不得为显示单调而取 WinRAR 历史最大值、钳制、平滑、过滤回退或估算。复用既有 `created_at`、`started_at`、`finished_at`、`error_code`、`error_summary` 和 `cancel_requested`，新增 `updated_at` 支撑运行/完成时间展示；后端状态机通过 `allowed_actions` 权威表达 `cancel`、`retry` 或 `view_result`。

创建 RAR 分卷阶段的卡片主要反馈是 indeterminate 活动态，而不是静止的 30% 进度条。摘要同时提供 1-based `stage_index`、版本化 `stage_count`、`last_heartbeat_at`、`output_volume_count`、`output_bytes`、`last_output_change_at` 和 `worker_state`。`output_volume_count` 是当前 attempt 受控 staging 中匹配分卷名规则的文件数量，可能包含正在写入的当前卷；`output_bytes` 是这些匹配文件当前在磁盘上的总字节数。两者只证明输出活动，不能除以计划卷数、输入大小或任何估计值形成百分比。

Worker 按受控频率更新心跳，并节流聚合后的输出活动快照；不得把每个文件系统变化事件直接写入数据库。输出大小暂时不变不能单独判定卡死、失败或触发取消，因为 WinRAR 可能处于 CPU 密集或缓冲阶段。`worker_state` 至少区分未分配、启动中、持有且运行、恢复中、等待接管和已释放；只有持有当前任务且运行的 Worker 才能让卡片显示“仍在运行”。

刷新后从持久化 `TaskRecord` 恢复阶段、里程碑、时间、心跳、输出活动、失败/取消和允许操作。服务重启先恢复最后确认的里程碑并进入恢复中/等待接管；Worker 重新取得持久化任务所有权后才更新心跳和活动摘要。这里的“重新接管”不表示自动连接旧 WinRAR、复用旧半成品或续压；旧进程和 staging 仍遵循归属证明、interrupted、新 attempt 和用户确认合同。

RAR 5.90、RAR 7.23 普通 pipe 及 RAR 7.23 ConPTY spike 已证明 CLI 百分比混合不同作用域且可重复回退。产品/架构决定是不再解析连续 WinRAR 百分比，而采用上述 `workflow_milestone`；该决定完成 Phase 3 版本/适配前置项，同时保留 WinRAR、分卷、Manifest、Legacy 显式压缩和全部安全门控。实验依据见 `winrar-progress-capability-spike.md`。

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

案件字段执行固定优先级：当前案件用户手工修改 > Parser 有效非空解析值 > 非空共享默认值 > 系统默认值或空值。新案件初始化时，有效 Parser 值的 FieldState.source 为 `report`；仅在报告字段缺失、为空、纯空格或空数组时读取共享默认值，source 为 `system_default`；两者都不可用时保持待填写或 `pending`；用户修改后统一为 `user`，保存和刷新不得退回较低优先级。`pending` 只属于 confirmation，不是 source 的替代值。

文号、检查地点、检查方法、检查硬件、光盘编号前缀和检查人员顺序属于“案件字段 + 部署共享默认值”的双写字段。自动保存服务在校验和防抖完成后提交两个独立操作，并分别返回 `draft_save_status` 与 `shared_defaults_save_status`。一侧失败不能伪装为整体成功，也不能静默回滚另一侧已经成功的写入；前端显示两个结果和重试入口。人员拖拽同样更新当前案件 `InspectorSnapshot[]` 与共享默认人员顺序。

共享默认值的当前作用域是部署实例/本地操作者，不表示多用户隔离。后端
`/workbench/defaults` 是事实源；工作台只在用户明确修改六项字段之一且当前草稿保存成功后，
用稀疏 patch 更新对应的非空共享值。后续新案件仅在 Parser 对应字段为空、纯空格、缺失或
空数组时使用可用的非空共享默认值，不会回写或批量修改已有案件。Parser 自动解析值不进入
共享 patch；`localStorage` 不是工作台案件或共享默认值事实源。

### 3.5 无登录审计身份

系统没有登录时，接管、默认值迁移、共享默认值修改和重要任务操作使用 `ClientIdentity`：`client_instance_id`、`session_id`、可选 `local_display_name`、`deployment_instance_id` 和时间。该对象只表示本地会话审计，不表示认证人员、真实民警或权限证明。API 与日志使用这组 opaque/本地标识，不推断真实身份。

### 3.6 SourceRecord 与来源复核

`SourceRecord` 是案件壳和解析任务的来源权威，包含 opaque `source_id`、source type、后端内部路径、允许根授权、case/task 绑定、metadata/fingerprint、访问状态和最近复核时间。绝对路径只能存在于后端受控存储和内部审计字段；前端 DTO、外部 API、普通日志和错误消息只返回 opaque ID、安全摘要和错误码。

来源登记和 Legacy 快速解析前必须验证允许根、路径存在性、权限、链接安全性和报告核心结构；这条快速路径不执行完整目录 metadata/fingerprint。解析器自身读取的关键输入必须保持稳定，成功生成草稿后立即进入 `review_ready`。完整 metadata/fingerprint 作为独立的后置来源复核异步执行。

数据库恢复事务只将未完成的 SourceRecord 复核保持为 `pending`，不得在恢复事务中把它标记为可信或来源变化。应用启动完成后，受控恢复协调器查询所有仍为 `pending` 且属于有效案件的 SourceRecord，并按 `source_id + revision` 去重后提交给受控来源复核执行器。调度成功后由执行器完成复核；调度失败保留 `pending`，记录稳定的 `SOURCE_REVALIDATION_PENDING` 诊断并允许后续启动或显式重试再次调度。该流程不得为已经 `review_ready` 的案件重新创建或执行 Parser。

来源状态必须区分“暂时无法验证”和“已确认发生变化”：`pending` 表示尚未完成可信确认，草稿仍可查看和编辑；归档继续受来源可信状态门控，Word 预览和导出始终允许，但工作台必须在导出动作发生时显示明确、可取消的风险确认。复核成功才转为 `available`。允许根、路径、链接安全性、报告结构或 fingerprint 已确认不匹配、来源被替换或不可继续使用时，才将 SourceRecord 标记为 `requires_reselection`，严格阻止归档并要求重新选择来源和重新解析；Word 仍允许在更强风险警告后由用户确认继续。暂时 I/O/权限/资源不可用或调度失败必须保持 `pending`，不得直接等同为来源已经变化。来源风险提示只读取后端返回的当前状态，不使用 localStorage，也不把状态伪装为 `available`。来源、图片和其他大对象只通过 opaque asset 引用进入 CaseDraft，SQLite 不保存内容本体。

### D-003C：独立 Review 修复采用最小可恢复提交和不可逆 context 绑定

首次独立 Level 3 Code Review 发现通用 lifecycle 绕过、正式 Manifest 与 attempt 成功登记之间的崩溃窗口、工作台 context 可省略 attempt、并发来源复核误判以及 staging 根目录保护不足。修复保持 Phase 1D 边界：不引入归档 Worker、队列、调度、进度、自动续跑或接管。

- 通用 lifecycle 服务拒绝直接写入 `archive_queued`；只有归档 attempt repository 的受控事务能够同步创建 attempt 并迁移 CaseShell/CaseDraft。
- 工作台 preview context 只持久化不可逆摘要、case 和 attempt 绑定，不持久化或恢复可执行 handle。旧/错配 binding 可被识别并拒绝，但应用重启后仍不能恢复旧 runtime context。
- 完整 Legacy Manifest 持久索引保存成功后，当前 attempt 记录同一份 source/input/archive 身份摘要。重启恢复重新读取持久索引并复核物理 RAR、Manifest ID、attempt、case、source 和 revision；全部匹配才补记 `succeeded`/`archive_verified`，否则仍按 interrupted 处理。
- SourceRecord revision conflict 表示复核结果已过期，处理方式是重新读取最新记录；不得把并发、调度或临时错误翻译为“空 fingerprint 即来源失效”。
- staging 清理仅允许受控根的直接 attempt 子目录，根目录本身及其他层级始终视为未知。

### D-003D：第三次独立 Review 的发布恢复与并发收敛

第三次独立 Level 3 Review 于 2026-07-28 未通过（Critical 0、High 4、Medium 1）。H1 通用 `archive_queued` 入口、H2 Word 风险确认合同、M1 conflict 后 fingerprint 重算和 L1 staging 根目录保护保持完成；本节只补充 H3/H4 的实现边界，不删除前两轮实现、测试或 Harness 历史。

- `archive_publish_intents` 的身份字段由持久化 workbench context hash、case/attempt/source、source/draft revision、report fingerprint、Manifest/index 身份和正式目标相对目录共同约束。正式目标目录使用 Legacy 执行器产生的 runtime context 加 Manifest ID；runtime context 与 workbench context 不混用，Legacy context 仍不创建 workbench attempt/intent。
- 正式移动前，受控服务在 publish intent 创建事务内重新读取 shell、SourceRecord、CaseDraft 和 active workbench binding，并在紧邻 `os.replace` 的边界再次校验。草稿、来源、context、attempt、case、报告身份或可信状态变化时不移动、不登记 index、不写 succeeded；失败 attempt 的 binding 失效。
- 恢复允许在可信正式目录存在且身份匹配时补推进 `intent_persisted -> published -> indexed`，然后调用同一可信完成服务；复用已有 Manifest 也必须遵守阶段顺序。意图存在但正式目录尚未移动时只安全中断并等待显式新 attempt，不自动执行归档。
- 可信完成服务在数据库写事务内重新读取并校验 attempt、SourceRecord、CaseShell、CaseDraft、active binding 和 publish intent；attempt、shell、draft 更新必须各恰好影响一行，任一失败整体回滚。数据库成功后但 intent `verified` 标记前崩溃只补阶段标记，不回退 succeeded。
- 恢复错误只在明确身份错配、目标冲突、Manifest/RAR 完整性失败或篡改时进入 `conflict`。SQLite 锁、index 暂不可用、文件占用、临时 I/O/权限异常保留当前意图阶段和正式产物，不删除、不覆盖、不重复发布，后续只由显式恢复核验再次尝试；不引入 Worker、队列、调度或后台自动重试。

本轮新增 `1D-025` 至 `1D-029T` 已完成，`1D-030T`、新的完整 Harness gate、`1D-017R`、独立 Review gate 和归档解除 gate 均保持未完成；截至本段对应的历史节点 Phase 2–4 尚未开始，后续状态见变更包 `tasks.md` 的各 Phase gate。

### D-003E：第四次独立 Review 的 publish fence、运行态恢复与真实来源摘要

第四次独立 Level 3 Review 于 2026-07-28 未通过（Critical 0、High 4、Medium 1）。本轮已完成 `1D-033` 至 `1D-037T` 的本地实现和定向验证；新的完整 Harness 与独立 Review gate 仍未完成。实现不引入 Worker、队列、调度、自动续跑、进程接管或 Phase 2–4 能力。

- 数据库 schema 升至 v5，新增内部 `archive_publish_fences`。每个 fence 绑定 case、attempt、source、source revision、draft revision、report fingerprint、不可逆 context hash 和建立时 shell revision；active 状态按 case 和 attempt 唯一。受控 intent 创建事务在最终读取服务端 shell/source/draft/binding 后同时创建 active fence 和 `intent_persisted` intent。普通 draft/source/shell 写入口遇到 active fence 拒绝；pending verification 允许编辑，并在同一写事务中使旧 fence invalidated，使旧 attempt 和旧正式证据不可补记成功。
- 正式发布前只验证仍有效的 active fence 后执行 `os.replace`；发布后阶段仍按 `published`、`indexed`、统一可信完成服务顺序推进。恢复先在数据库事务内使旧 accepted/running 及具有非终态 intent 的 failed attempt 转为 interrupted、失效 runtime context 并同步 shell/draft 非运行态，再把 active fence 转为 pending verification。正式目录、Manifest/index、intent 和 fence 作为持久证据保留，不自动重新执行 WinRAR、不重复移动和不删除未知产物。
- Reconciliation 以所有非终态 publish intent 为入口，覆盖 accepted/running/failed/interrupted 等 attempt 状态。临时 index/SQLite/I/O/权限错误保持 interrupted、pending verification fence 和现有证据；仅确认性身份/完整性/目标冲突进入 conflict。可信证据通过同一完成服务从 interrupted/pending verification 收敛到 succeeded，并在同一事务内严格校验 source、draft、shell、attempt 和 fence，三次状态更新均要求恰好一行。
- SourceRecord 来源 fingerprint 使用规范化相对路径、条目类型、实际文件字节摘要和稳定排序结构；每个文件使用句柄前后 `fstat`，文件读取两次并比较摘要，整个集合在摘要前后重新扫描。文件变化、消失、加入、删除、I/O 或权限异常返回临时不可验证结果，由 SourceRecord 保持 pending；不使用 metadata-only 缓存、绝对路径或 USN/Canonical/Shadow 机制。
- `ReportParseInFlightRegistry` 用 completing map 表示 Future 已脱离 active registry 但 callback 尚未完成。锁内确认 entry 身份、删除 active 并登记 completing，锁外调用 `set_result`/`set_exception`，finally 只清理相同 Future。active_count 只统计真正运行中的 builder，同 key 在 active 或 completing 期间复用同一 Future。

## 4. 归档计划、稳定槽位和 Manifest

初次规划生成有序 `VolumeSlot`，每个槽位获得独立 UUID。规划输入包括经过完整 inventory 的输入修订、容量策略和共享光盘前缀；预计卷名只是展示属性，不是槽位身份。映射默认值由前缀和槽位序号生成，保存时校验非空和案件内唯一。

replan 接收上一版 `VolumeSlot[]` 和新规划结果，使用槽位 lineage/逻辑序号、容量区间和稳定输入分片标识做匹配；不读取或比较预计 RAR 文件名。能够证明仍代表同一逻辑分卷的旧槽位保留 `slot_id` 和有效人工映射；无法匹配的槽位新建 ID 并置为 `pending`；不再存在的槽位和映射标记 removed，不进入最终 Manifest。

归档执行前必须重新验证案件草稿版本、映射唯一性、输入 inventory、路径/链接/文件变化和计划版本。WinRAR、完整性、MD5 和 Manifest 验证全部成功后，生成 `VerifiedManifest` 并把它保存为 `ExportArtifact`；Word 的附件 3 和下载元数据只能从此 Manifest 读取最终卷和光盘编号。

## 5. 调度器和资源准入

调度器分两层：

1. **队列层**：按任务优先级和创建时间选择 queued 任务，保证压缩 `running` 数不超过 6，解析任务不占用压缩槽位。
2. **资源准入层**：在启动每个 WinRAR 前读取配置化的最小可用磁盘空间、临时空间、CPU 使用率、IO 使用率、输入规模上限、WinRAR 进程数和全局进程数。任一条件不满足则保留 queued，并返回具体原因。

准入配置保存在部署配置中并有版本；不允许前端覆盖安全阈值。任务运行中若资源降至保护阈值，调度器停止启动新任务并可请求当前任务有序取消；不强杀已写入的正式产物。WinRAR 进程必须由任务记录绑定。服务重启时不自动重连或接管 WinRAR：先把原 running 任务标记为 `interrupted`/`failed_retryable`，只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，并将半成品 RAR/Manifest 标记为不可发布；用户确认后重新执行。断点续压和 WinRAR 重连不在本包范围内。

`ArchiveResourceSnapshot.io_busy_percent` 是资源准入的可选服务器事实：当 `psutil.disk_io_counters()` 返回 `None`，或平台返回对象没有 `busy_time`（例如合法的 Windows `sdiskio`）时，采样器必须显式返回 `None`，并清空连续采样基线。`None` 表示“该可选指标不可用”，不是 `0%`；资源准入只跳过 I/O 忙碌阈值这一项，仍执行输出/临时空间、CPU、输入规模、WinRAR 进程数、并发上限以及任务所有权/租约等其他门控。采样器不得从 `read_time`/`write_time` 伪造忙碌百分比，并对不可用诊断做提供者生命周期内的一次性限流记录。

上述调度器、资源准入和 `workflow_milestone` 属于 Phase 3，不在 Phase 1D 实现。Phase 1D 只在现有同步 Legacy 归档调用外围登记最小归档尝试和恢复日志；它不创建持久化归档 Worker，不维护归档队列，不自动拉起新进程，也不把旧 `TaskRecord.percent` 当作归档进度权威。

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

自动保存接口使用 `If-Match`/草稿 revision 或等价字段；案件字段双写接口必须分别返回 draft save 和 shared-default save 状态。任务状态可用现有工作台轮询起步，但状态源必须是后端任务记录，后续可替换为 SSE 而不改变 DTO；案件卡片不得建立第二套轮询事实源。案件列表 DTO 直接内嵌当前或最近一次归档任务的 `ArchiveTaskCardSummary`，完整日志、历史和逐卷诊断由详情接口提供。

卡片默认最多组织四类内容：案件基本信息；当前归档状态和阶段；最多两行活动或状态摘要；受控的主要操作。各状态采用替换而非累加：

- 未归档：状态和归档前检查/归档入口，不渲染空进度或活动占位。
- 等待/恢复：最后确认里程碑和等待执行、恢复中或等待 Worker 接管文字，不显示“仍在运行”。
- 运行中：突出阶段文字；WinRAR 阶段显示 indeterminate 动画、阶段 X/N、已运行时间，两行内显示易读分卷数/输出大小和相对最后活动时间；30% 仅作次要说明。
- 失败：安全可理解的失败摘要、失败阶段/时间和适用的已生成卷数替换普通活动指标；提供查看原因和重试。
- 已取消：取消状态、所在阶段、取消时间以及重新归档/详情入口。
- 已完成：压缩为完成状态、100%、总分卷数、完成时间和查看结果；不再显示心跳、Worker 状态或动画。

完整阶段时间线、逐卷文件名/大小/MD5、Manifest 路径/内容、历史任务、Worker ID、内部租约、精确心跳时间戳、完整错误代码、堆栈、技术日志、重试/调度诊断和进程信息不进入默认卡片。次要操作进入更多菜单或详情入口。相对时间可由已有摘要时间在浏览器本地刷新，不因此增加后端请求。

窄屏可隐藏次要活动指标，但必须保留案件信息、状态、阶段文字和主要操作。状态不能只靠颜色；indeterminate 动画必须配套文字，并尊重减少动态效果设置。长文号、长错误摘要和大数字必须截断、换行或安全格式化，不能撑破卡片或破坏多卡片快速扫描。

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
显式压缩入口继续执行。该入口不引入 Phase 3 后台编排或伪造进度。若应用在入口执行前后
重启，恢复流程将其转为 `archive_interrupted`，旧 handle 失效；用户必须重新复核来源并
再次选择立即压缩，后端生成新的 handle。解析失败只保留可重试卡片，不出现压缩询问。

T015 完成后，工作台 `immediate` 决定改为创建持久化归档 TaskRecord 并交给 T014
调度/Worker；公共响应只返回安全任务投影，不返回可用于直接执行的 context/attempt。
`/records/archive` 继续服务非工作台 Legacy 兼容调用，但拒绝工作台绑定的归档上下文，
从而不能绕过资源准入、任务所有权和正式安全门控。

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

任何正式产物删除 API 都不在本变更包中注册；未来若产品允许显式删除，应作为单独 Level 3 决策、权限和双重确认设计。Phase 1D 的恢复清理只处理有归属证明的未完成 staging 和进程资源；清理动作必须幂等，未知资源不触碰，清理失败不阻止案件/草稿恢复。

## 9. 分阶段依赖与独立交付

| 阶段 | 可独立验收的合同 | 明确前置条件 | 禁止的隐式依赖 |
|---|---|---|---|
| 1 | CaseDraft/Defaults/Task/Lease/Workbench v1 | 现有 Legacy parse/export 继续可用 | 不读取页面 state 推断后端草稿 |
| 2 | Order/Inspector/Provenance/DownloadName v1 | 只依赖阶段 1 的版本化草稿 DTO；可用合成草稿测试 | 不要求阶段 3 归档完成才能保存编辑 |
| 3 | ArchivePlan/Mapping/WorkflowMilestone v1 | 依赖阶段 1 task/asset contract；WinRAR 进度策略决策已完成；Legacy 归档门控保持原实现 | 不解析 CLI 连续百分比，不用旧预计文件名、RAR 大小、时间或动画作为百分比权威 |
| 4 | TemplateRegistry/TemplateRef v1 | 依赖案件草稿和 Word export DTO；可用注册 fixture | 不要求重新压缩或重建 Manifest |
| 5 | integrated acceptance/cleanup boundary | 阶段 1-4 的合同和定向验收证据 | 不把 Shadow 真实样本差异治理混入验收 |

### Phase 1 internal gates

| 小门控 | 范围 | 必须证明 |
|---|---|---|
| 1A | SharedTypes、SQLite schema/migration、Repositories | CaseShell/CaseDraft、SourceRecord、ClientIdentity、双写结果、opaque asset 引用和 SQLite 大对象拒绝规则可持久化、迁移、回滚 |
| 1B | Services 和 API | 提交即建壳、解析任务失败/重试、来源复核、默认值优先级、草稿/共享默认值双写状态、interrupted 重启语义和删除前置条件可通过 API 表达 |
| 1C | 工作台、自动保存和租约 | 6 卡片分页、排队/解析中/失败状态、自动保存、15 秒心跳、2 分钟接管警告和分别显示保存结果 |
| 1D | 刷新/重启恢复、兼容回归和历史合成阶段验收 | CaseShell/CaseDraft/Task/Source/asset/lease 可恢复；解析中断、来源复核和重试闭环；归档准备通过单事务绑定 attempt/context/source/draft 证据后才进入 `archive_queued`；正式发布通过持久化意图和统一完成证据恢复，不自动续跑；自有 staging 可幂等清理或隔离；半成品不发布；Legacy 解析/归档/Manifest/Word 回归通过。历史合成阶段验收不等同于 Phase 1–4 最终集成人工验收 |

每阶段完成时运行定向测试、前后端全量测试、类型、架构、生产构建、严格文档、资产和 diff
检查，并只做服务启动、核心页面和新功能可访问性的轻量开发冒烟。Phase 1–4 全部实现后再
统一进行完整 Harness、集成检查和完整端到端人工验收；最终 Review 与归档判断在此之后进行。
轻量冒烟不等同正式人工验收，阶段 checkpoint commit 是否创建由用户单独授权；运行
`verify:full` 前仍按 `AGENTS.md` 询问执行者。

### Phase 1C request liveness correction

The workbench submission request performs only source authorization and bounded report-structure validation before atomically creating the CaseShell, parse Task, and pending SourceRecord. It MUST NOT attach Legacy parsing to FastAPI `BackgroundTasks` or wait for recursive source metadata/fingerprint work. A bounded in-process dispatcher starts the same Legacy `parse_report` path after the transaction; the fast path is `parse readiness -> Legacy Parser -> draft persistence -> review_ready`. Full source metadata/fingerprint verification starts only after `review_ready`, remains independent of the parse task lifecycle, and changes only SourceRecord status when it fails. The dispatcher deduplicates an active `(case_id, task_id)` and treats unhandled parse-worker exceptions as retryable task failures. Restart recovery continues to use the persisted `queued`/`running` to `failed_retryable`/`interrupted` contract. A restart recovery pass must also find pending post-parse SourceRecord verification, requeue it within the bounded verifier or keep it explicitly pending; transient unavailability remains pending, while a confirmed source change requires reselection and a new parse before formal Word/archive execution.

## 10. 兼容策略与安全门控

- 现有 `POST /records/parse`、`/records/archive`、`/records/export` 在迁移期间保留 Legacy DTO 适配；新工作台调用新路由并通过共享类型通信。
- 归档阶段可把现有同步执行封装为一个可持久化任务 worker，先不重写 `ArchiveExecutionService` 的安全检查；完成一项门控才更新任务阶段。
- WinRAR pipe/ConPTY spike 的能力结论保留为设计证据；Phase 3 不读取 CLI 连续百分比，只由真实门控推进 `workflow_milestone`。现有 Legacy 显式压缩路径保持可用；断点续压和重连不作为迁移方案。
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

- SharedUtils：自然排序回退、编号唯一性、文件名校验、固定里程碑转换、非法回退/跳阶段拒绝、状态迁移边界、解析/默认优先级和双写结果聚合。
- Repositories/Services：SQLite 事务、版本冲突、租约、迁移幂等、CaseShell/解析失败、SourceRecord 复核、ClientIdentity、opaque asset 边界、稳定槽位 replan、调度准入、取消清理和模板指纹。
- Hooks/Components：RTL 验证来源标记、拖拽顺序、租约警告、6 卡片分页、导出名称弹窗，以及案件卡片内任务阶段、里程碑次要说明、indeterminate 运行态、心跳/输出活动、恢复状态、无障碍文字和允许操作展示。
- Controllers/Routes：HTTP 集成验证自动保存、草稿/共享默认值分别返回、来源复核、恢复中断、任务取消、删除保护、模板切换不触发归档和 Manifest 结果投影。
- Phase 1D recovery matrix：合成验证 CaseShell/CaseDraft/Task/Source/asset/lease 的刷新与重启恢复、解析 queued/running/cancelling 的单次显式重试、成功案件不重复解析、数据库恢复保留 pending、启动后来源复核调度成功/失败、多次启动按 source/revision 幂等、暂时不可验证与已确认变化的不同门控、`archive_interrupted` 的查看编辑、deferred 退出、重新确认和新 handle。
- Phase 1D archive safety：使用合成 staging 和受控 attempt record 验证五项归属证明、证据缺失/冲突时未知进程/文件不终止不删除不覆盖、自有 staging 幂等清理或隔离、半成品 RAR/Manifest 不发布、succeeded attempt 不回退、正式产物不误删以及清理失败不阻止案件恢复。
- WinRAR spike：保留普通 pipe 和 ConPTY 合成失败证据；验证 Legacy 显式压缩仍可用，并证明 Phase 3 只采用 `workflow_milestone`、不产生 WinRAR 连续假进度。
- E2E/人工：使用合成多案件、多任务和合成模板；真实大报告只在用户明确执行的外部验收中使用，证据不得进入仓库。

## 12. 与已有活跃变更包的协调

仓库当前存在其他活跃 OpenSpec 变更包，其中部分包含 Canonical、模板平台或归档规划的候选设计。本包不删除、不改写、不自动归档这些包；它只为本轮甲方确认的五阶段工作定义新的统一合同。

实施前必须完成一次重叠审计并在本包任务记录中标记每个重叠项：

- 与案件草稿、顺序、默认值、归档任务或模板选择重复的任务，统一迁移到本包的合同，避免两套 DTO、两套状态机或两套权威来源并存。
- Canonical 适配、Canonical 正式输出、Shadow 真实样本差异治理相关任务保持暂停或另行处理，不作为本包前置条件。
- 仍需保留的现有 Legacy 安全门控和已验收模板资产作为兼容依赖，不复制其实现合同。

若活跃包的设计与本包的 Legacy-only、Shadow 暂停或正式产物保护边界冲突，必须在开始实现前记录冲突处理决定；不能靠任务执行顺序或前端 feature flag 隐式解决。
