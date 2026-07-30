# Electronic Inspection Record: Persistent Workbench Contract

本文件是 persistent-case-workbench-and-archive-coordination 的变更合同。Phase 1–2 已实现并
确认的合同可以同步到 `openspec/specs/` 下的 living spec；Phase 3 已实现完成、自动验证通过、
轻量冒烟通过，等待 Phase 1–4 最终集成人工验收；Phase 3 正式人工验收和 Phase 4–5 尚未完成。未实现合同仍只保留在本 delta spec 中，不得提前写成
当前生产事实。

## Contract vocabulary

- CaseShell：提交报告后立即创建的案件记录；解析成功前不含可审核 Legacy InspectionReport。
- CaseDraft：解析成功后的可编辑草稿；report 始终是 Legacy InspectionReport。
- SourceRecord：受控来源记录，保存 opaque 来源 ID、允许根授权、内部路径、绑定关系和复核结果。
- FieldState：可编辑字段、检材字段、人员项或附件图片组的来源与确认状态。
- TaskRecord：Phase 1 中是可恢复解析任务和最小归档尝试记录；Phase 3 共享合同已增加归档里程碑、活动和 Worker 状态字段，T013/T013T 已实现计划、任务和安全卡片摘要的持久化事实源，T014/T014T 已实现复用该事实源的 Worker 与调度执行，T015/T015T 已完成公共安全 API 与案件卡片真实数据对接。
- VolumeSlot：不依赖预计 RAR 文件名的稳定逻辑分卷槽位。
- VerifiedManifest：完整归档门控通过后生成并验证的正式 Manifest。

## ADDED Requirements

### Requirement: 案件壳和多案件工作台可恢复

系统 MUST 在用户提交报告后立即分配稳定 case_id，创建案件壳和持久化解析任务。解析成功后才写入完整 Legacy InspectionReport；解析失败时保留失败任务卡片，但该记录不得成为可审核、可归档或可导出的正式草稿。案件名称与案件摘要独立，修改案件名称不得改变正式 RAR 基础名规则。

#### Scenario: 提交报告后立即创建案件壳

- **WHEN** 用户提交报告来源
- **THEN** 系统立即创建案件壳和解析任务，工作台显示排队或解析中卡片
- **AND** 案件壳在解析成功前不可审核、归档或导出

#### Scenario: 解析成功或失败

- **WHEN** 解析成功
- **THEN** 写入完整 Legacy InspectionReport、SourceRecord 引用和解析版本并转为可审核
- **WHEN** 解析失败
- **THEN** 保留失败卡片、结构化错误和重试入口，不生成正式草稿

#### Scenario: 刷新或重启后恢复

- **WHEN** 用户刷新浏览器或关闭软件后重新打开
- **THEN** 后端返回尚未清理的案件壳/草稿和任务状态
- **AND** CaseShell、CaseDraft、revision、案件生命周期、解析/归档决定、SourceRecord、图片资产引用和自动保存结果均以后台持久化状态为准
- **AND** `queued` 解析任务转为 `failed_retryable`，`running/cancelling` 解析任务转为 `interrupted`，用户显式重试前不得重新执行
- **AND** `review_ready` 案件不得因为重启而重复解析
- **AND** 重启前已选择或开始立即压缩的案件转为 `archive_interrupted`，不得保持虚假的 `archive_queued` 或运行中状态
- **AND** 重启前运行中的 WinRAR 任务不默认成功、不自动重连、不自动接管、不自动续跑

### Requirement: 自动保存和编辑租约防止互相覆盖

编辑内容 MUST 通过后端自动保存并携带草稿 revision。编辑会话 MUST 使用心跳租约，建议每 15 秒续租，连续 2 分钟无心跳后才允许接管。强制接管必须警告并记录无认证身份审计信息。

#### Scenario: 编辑保存和版本冲突

- **WHEN** 用户修改字段、顺序、来源状态或模板选择
- **THEN** 客户端去抖后保存并显示保存成功、冲突或失败
- **AND** 版本冲突不得静默覆盖后端草稿

#### Scenario: 同一案件互斥和接管

- **WHEN** 第二个会话打开仍有有效心跳的案件
- **THEN** 后端拒绝普通编辑
- **WHEN** 租约连续 2 分钟无心跳且用户确认强制接管
- **THEN** 后端记录旧 session、新 client、部署实例和时间并允许接管

#### Scenario: 服务重启使旧租约失效

- **WHEN** 服务重启后存在上一个部署实例创建的 active lease
- **THEN** 旧 session 不再被显示为有效编辑者，租约按恢复合同失效或进入 expired
- **AND** 新会话可以重新获取租约，不得被旧租约永久阻塞
- **AND** 若用户执行强制接管，仍记录旧 session、新 client、部署实例和时间的审计事件

### Requirement: 共享默认值与当前案件双写可区分

后端持久化 MUST 是工作台共享默认值的事实源，当前作用域为部署实例/本地操作者，不表示
多用户隔离。共享范围严格限定为完整文号、检查地点、检查方法、检查硬件、检查人员及顺序、
光盘编号前缀六项。用户明确修改其中一项后，工作台经校验和防抖先保存当前草稿；草稿保存
成功时才以稀疏 patch 更新本次明确修改的非空共享字段。后续新案件仅在 Parser 对应字段为空、
纯空格、缺失或空数组时使用可用的非空共享默认值，已有案件不得被回写或批量修改。Parser
自动解析值不得进入共享 patch。草稿保存结果和共享默认值保存结果 MUST 分别返回；
`localStorage` 不是工作台案件或共享默认值事实源。

#### Scenario: 案件字段修改同步共享默认值

- **WHEN** 用户修改文号、地点、方法、硬件或光盘前缀且校验和防抖完成
- **THEN** 当前案件字段保存为 user 来源，草稿保存成功后提交仅包含本次明确修改字段的稀疏共享默认值更新
- **AND** API 分别返回 draft_save_status 和 shared_defaults_save_status
- **AND** 空值不清除已保存的共享默认值，未修改字段不进入 patch

#### Scenario: 双写部分失败可见

- **WHEN** 一侧保存成功而另一侧失败
- **THEN** 页面分别显示两个结果和可重试动作
- **AND** 不得显示为一次全部成功

#### Scenario: 人员拖拽同步两种顺序

- **WHEN** 用户拖拽当前案件检查人员卡片并保存
- **THEN** 当前案件 InspectorSnapshot 顺序变为 user 确认顺序
- **AND** 草稿保存成功后，共享默认人员顺序通过稀疏更新保存，并分别返回两种保存状态

#### Scenario: 新案件继承且已有案件不回写

- **WHEN** 后端已保存一个或多个非空共享默认值，随后创建新案件
- **THEN** 新案件仅在对应报告值缺失、为空或无法识别时优先使用这些共享默认值
- **AND** 更新共享默认值不得修改此前已创建案件的草稿或来源状态

#### Scenario: 旧 localStorage 迁移

- **WHEN** 浏览器存在旧默认值且部署实例尚无迁移决定
- **THEN** 系统提示导入或忽略，不得静默写入共享默认值
- **AND** 导入或忽略只能成功一次并记录无认证身份审计信息
- **AND** 迁移完成前后，`localStorage` 均不得成为工作台事实源

### Requirement: 解析值优先于共享默认值

案件字段 MUST 遵循 user > report > system_default 的来源优先级，对应业务优先级为“当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值”；pending 是独立确认状态。有效非空解析值来源为 report；报告为空、纯空格、缺失或空数组时才使用共享默认值；用户修改后来源统一为 user，保存和刷新不得退回较低优先级。

#### Scenario: 有效报告值优先

- **WHEN** 报告提供有效非空值且共享默认值也存在
- **THEN** 案件使用报告值并设为 report 来源

#### Scenario: 报告值缺失或不可用

- **WHEN** 报告字段缺失、为空或无法识别且共享默认值有效
- **THEN** 案件使用共享默认值并设为 system_default 来源
- **AND** 两种来源都不可用时保留 pending 或待填写提示

#### Scenario: 用户修改来源迁移

- **WHEN** 用户修改 report 或 system_default 字段
- **THEN** 对应 FieldState.source 统一变为 user
- **AND** confirmation 按业务规则独立保留或转为 pending

### Requirement: 字段来源和待确认状态可追踪

每个可编辑叶子字段、检材字段、人员项和附件图片组 MUST 有 FieldState，包含稳定字段路径、来源 report | user | system_default、确认状态 confirmed | pending 和 revision。纯派生不可编辑字段继承来源，不单独维护状态；来源颜色不得进入 Word，pending 必须有文字提示。

#### Scenario: 来源展示和导出隔离

- **WHEN** 字段来自报告、系统默认值或人工修改
- **THEN** 审核界面显示相应来源
- **AND** Word 使用正式黑字，不携带来源颜色

#### Scenario: 待确认不只靠颜色

- **WHEN** 检材、关键字段或图片组处于 pending
- **THEN** 页面显示待人工确认文字和影响范围
- **AND** 正式导出执行现有确认门控

### Requirement: SourceRecord 保护来源可访问性

系统 MUST 为每个工作台来源创建 SourceRecord，来源提交合同是本机报告目录路径而非 ZIP/RAR 或其他上传文件。后端 MUST 校验路径存在、是允许的目录类型、位于授权来源根、当前账户可访问且包含可识别报告结构，再保存 opaque source_id、允许根授权、source_type、case_id/task_id 绑定、metadata/fingerprint、访问状态和最近复核时间。绝对路径只能存在于受控后端 locator 中；API、卡片、草稿 DTO、任务 DTO、审计摘要、普通日志和 SQLite 公共字段不得暴露绝对路径；来源失效时必须要求重新选择目录。

#### Scenario: 来源绑定和重启复核

- **WHEN** 用户提交经后端验证的报告目录并创建解析任务
- **THEN** SourceRecord 绑定案件壳和 task_id，并保存允许根授权及 metadata/fingerprint
- **AND** 为保证登记接口及时返回，递归 metadata/fingerprint 以 `pending` 状态延后到独立来源复核；快速解析任务只执行授权、目录结构和 Legacy Parser 所需的关键输入验证，并按 `Legacy Parser → 草稿持久化 → review_ready` 顺序完成。完整复核不得阻塞 Parser 或审核入口；只有确认来源发生变化或不再安全时才将 SourceRecord 标记为 `requires_reselection` 并提示重新选择，不撤销已成功生成的草稿。
- **WHEN** 服务重启或任务恢复前访问来源
- **THEN** 后端复核允许根、路径、权限、链接安全性和 fingerprint/metadata，并识别所有仍处于待复核的 SourceRecord
- **AND** 数据库恢复事务完成后，未完成的后置复核保持 `pending`，不得在恢复事务中标记为可信或来源变化
- **AND** 应用启动完成后，受控执行器按 `source_id + revision` 去重重新调度所有 `pending` 复核
- **AND** 调度失败保持 `pending`，记录可识别的 `SOURCE_REVALIDATION_PENDING` 状态并允许后续启动或显式重试再次调度
- **AND** 复核恢复不得为已经 `review_ready` 的案件重复创建或执行 Parser
- **AND** 暂时 I/O、权限或资源不可用保持 `pending`，草稿可以查看和编辑；归档继续等待来源可信状态，Word 预览和导出仍允许，但工作台必须在导出前明确提示复核尚未完成并由用户确认
- **AND** 已确认的路径、允许根、链接安全性、报告结构或 fingerprint 变化、来源被替换或不可继续使用时，才标记为 `requires_reselection`，阻止归档并要求重新选择来源和重新解析；Word 仍允许在更强风险警告后由用户确认继续

#### Scenario: 来源风险不阻止 Word 导出

- **WHEN** SourceRecord 为 `available`
- **THEN** 工作台直接执行现有 Legacy Word 导出，不显示来源风险确认
- **WHEN** SourceRecord 为 `pending`
- **THEN** 工作台在导出动作中持续显示“来源复核尚未完成”的明确确认，用户取消时不导出，用户确认时继续调用现有 Legacy 导出
- **WHEN** SourceRecord 为 `requires_reselection`
- **THEN** 工作台显示更强的“来源已变化、不可用或需要重新选择，导出内容可能与当前来源不一致”确认，用户取消时不导出，用户确认时继续调用现有 Legacy 导出
- **AND** 提示状态来自当前后端 CaseDetail，不使用 localStorage、不伪造 `available`
- **AND** Legacy `/records/export` 不因 SourceRecord 状态增加拒绝门控；来源可信状态仍严格约束归档

#### Scenario: 来源路径不对外泄露

- **WHEN** API 返回错误、任务进度或审计日志
- **THEN** 只使用 opaque ID、错误码和安全摘要
- **AND** 不包含绝对路径、原始文件名集合或完整来源 JSON

#### Scenario: 工作台拒绝上传文件和无效目录

- **WHEN** 工作台请求使用 ZIP、RAR、普通文件、不存在目录、越界目录、无权限目录或结构无效目录
- **THEN** 后端拒绝创建案件，并返回稳定原因码，不回显完整路径
- **AND** 不复制整个报告目录到上传目录，也不把报告内容或完整文件列表写入 SQLite 公共数据

### Requirement: 解析后压缩时机决策

解析成功后系统 MUST 明确询问用户立即开始压缩或稍后压缩。决策 MUST 使用案件 shell revision 原子持久化；解析失败案件不得出现该询问。

#### Scenario: 稍后压缩可恢复

- **WHEN** 用户选择“稍后压缩”
- **THEN** 案件和草稿生命周期持久化为 `archive_deferred`，页面显示“暂未压缩”
- **AND** 刷新或后端重启后仍显示该状态，并可从案件操作区再次选择立即压缩

#### Scenario: 立即压缩保持 Legacy 边界

- **WHEN** 用户选择“立即开始压缩”
- **THEN** 后端记录 `archive_queued` 并返回 opaque Legacy preview handle
- **AND** 只有受控归档准备事务可以写入 `archive_queued`；通用 lifecycle、Draft PATCH、普通 archive decision 和普通 repository 入口不得直接写入
- **AND** 该事务校验 case/source/draft revision，创建唯一 attempt，持久化 workbench context 绑定，并同步迁移 shell/draft；任一步失败时数据库状态全部回滚
- **AND** 前端进入现有 Legacy 显式压缩入口，不显示伪造进度、不启动 Phase 3 后台编排

#### Scenario: 立即压缩在重启后必须重新确认

- **WHEN** 案件处于 `archive_queued` 或归档执行中，应用随后重启且尚无已验证正式产物
- **THEN** 案件生命周期转为 `archive_interrupted`，归档尝试标记为 `interrupted`
- **AND** 页面说明上次压缩因应用重启或执行中断未完成，不继续显示 queued/running
- **AND** 旧运行时 preview handle 不恢复、不续跑、不自动生成新的压缩任务
- **WHEN** 用户重新进入案件并确认立即压缩
- **THEN** 后端先复核 SourceRecord，再生成新的 opaque Legacy preview handle 并进入现有 Legacy 显式归档入口
- **AND** 旧 handle 的状态不能影响新一次归档尝试

#### Scenario: archive_interrupted 的可查看、编辑和退出路径

- **WHEN** 案件处于 `archive_interrupted`
- **THEN** 已存在的 CaseDraft 仍可查看和编辑，页面保留“上次压缩因应用重启或执行中断未完成”的提示
- **AND** 半成品 RAR、半成品 Manifest 和旧运行时 handle 不得作为正式产物、Word 输入或新尝试输入使用
- **WHEN** 用户选择“稍后压缩”并提交有效 revision
- **THEN** 案件允许从 `archive_interrupted` 转为 `archive_deferred`
- **AND** 不创建新的归档尝试或 handle，同时保留上次中断的审计/诊断记录
- **WHEN** 用户重新确认来源并再次点击“立即压缩”
- **THEN** 后端先完成来源复核，并原子接受新的 `attempt_id`、归档尝试记录和 opaque Legacy context
- **AND** 只有新尝试被接受后，案件才从 `archive_interrupted` 转为 `archive_queued`
- **AND** 新尝试失败、来源复核失败或 context 创建失败时案件保持 `archive_interrupted`
- **AND** `archive_interrupted` 不得直接转为 `archiving`、`archive_verified`、`exporting_word` 或 `exported`，不得自动重启压缩或复用旧半成品

#### Scenario: 解析失败不询问压缩

- **WHEN** 目录解析失败
- **THEN** 案件卡片保留失败和重试入口，但不得返回或显示压缩时机询问

### Requirement: Phase 1D 最小归档中断和产物保护

Phase 1D MUST 只在现有 Legacy `/records/archive` 显式入口外围记录一次归档尝试，不建设持久化归档 Worker、调度器、并发准入、真实进度、断点续压或自动重试。归档尝试记录只用于识别重启前未完成的归档操作、证明自有 staging/进程资源归属、记录接受/完成/中断/失败/清理结果，以及支撑幂等恢复和正式产物保护；它不是新的正式归档输出链路。

The controlled workbench preparation path MUST bind the attempt to the case,
source ID and revision, draft revision, server-side report fingerprint and
one-way context hash before it moves the shell and draft to `archive_queued`.
Formal completion MUST use one trusted evidence service for normal execution
and restart recovery. A caller-provided Manifest ID alone MUST NOT change an
attempt or case to a succeeded/verified state. Before success, the service
MUST validate the internal publish intent, Manifest index identity and public
Manifest, source/draft bindings, and the physical RAR contents. A durable
publish intent distinguishes persisted-before-move, published-before-index,
indexed-before-success, and conflict/incomplete recovery states without
introducing a worker, queue, scheduler, progress or automatic retry contract.

The publish intent MUST be created only after a transaction re-reads the
server-side CaseShell, SourceRecord, CaseDraft and active workbench binding.
The final directory identity is bound to the Legacy executor's formal runtime
context and Manifest ID, while the persistent workbench context remains the
one-way binding authority. Before `os.replace`, the service MUST perform the
same source/draft/report/context validation again. A changed draft revision,
source revision or source trust state MUST prevent the move, index registration
and success evidence.

If a trusted final directory exists while the intent is still
`intent_persisted`, recovery MAY advance it through `published` and then
`indexed` only after validating the intent, attempt, case, source/draft/report
identity, Manifest index and physical RAR. It MUST NOT jump directly to
`indexed` or publish a second artifact. The normal path and restart path MUST
call the same trusted completion service. That service MUST re-read SourceRecord,
CaseShell and CaseDraft inside its write transaction and require exactly one
row update for attempt, shell and draft; any zero-row update rolls back all
state changes. A crash after the success commit but before the final `verified`
phase marker MUST never turn the succeeded attempt into `interrupted`.

Recovery MUST classify confirmed identity/integrity/target conflicts separately
from temporary SQLite locks, index unavailability, file locks and transient
I/O/permission errors. Temporary errors retain the current intent phase and
formal output for later explicit verification, without deleting, overwriting,
republishing or adding a worker/queue/retry scheduler. Legacy contexts retain
the existing client-report contract and do not use the workbench completion
shortcut.

The workbench publish boundary MUST also persist a `publish_fence` in the same
database transaction that performs the final server-fact validation and creates
the publish intent. The fence MUST bind case, attempt, source and source
revision, draft revision, report digest, context hash and shell revision, with
at most one active fence per case and attempt. Every ordinary write that could
change a bound CaseDraft, SourceRecord or CaseShell MUST reject while the fence
is active, or atomically invalidate the fence before changing the facts. A
`pending_verification` fence after restart MUST invalidate the old runtime
context, allow later editing, and become non-completable when such editing
changes the bound facts; it MUST NOT permanently block the case.

Startup recovery MUST first convert stale accepted/running execution state and
any failed attempt with a non-terminal publish intent to interrupted, update
the user-facing shell/draft to a non-running state, and deactivate the old
runtime context. Only then may it reconcile non-terminal publish intents. A
trusted final directory MUST be matched to its persisted intent and fence; an
intent without a final directory remains safely interrupted and is never
republished. A temporary reconciliation error MUST preserve the intent, fence,
index and formal artifact without leaving a false running state. A confirmed
identity or integrity conflict MAY enter conflict; it MUST not delete or
overwrite the unknown artifact.

SourceRecord directory fingerprints MUST use normalized relative paths, entry
types, actual file-byte digests and a stable sorted collection structure. Each
file MUST be checked through an open handle before and after reading, and the
collection MUST be rescanned after digesting. A file change, disappearance,
addition, deletion, temporary access error or inconsistent scan MUST keep the
source in a stable pending/temporarily unverifiable state rather than produce a
trusted available fingerprint. No absolute path or metadata-only cache is part
of the public contract.

The report-parser inflight registry MUST separate active builders from a
completing Future. It MUST remove and identity-check the active entry under the
registry lock, publish the same Future in a completing map, complete the Future
outside the lock, and finally remove only the matching completing entry. A
same-key caller MUST reuse that Future during both phases; callbacks MAY
re-enter registry queries without deadlock, and active_count MUST count only
builders still running.

归档尝试记录的内部状态为 `accepted | running | succeeded | failed | interrupted`，另有 `cleanup_status` 为 `not_required | pending | succeeded | failed | unknown`。恢复主要处理未完成的 `accepted/running` 记录；对于已完成但仍停在 `indexed` 的 intent，只允许补写最终 `verified` 阶段，绝不把 `succeeded` 记录改回 `interrupted`。新的用户确认必须创建新的 `attempt_id`，不得复用旧记录。

后端可以在内部记录 `attempt_id`、案件/草稿/source revision、进程 PID、进程启动时间、内部 staging locator、ownership marker 摘要和安全错误码。API、DTO、错误和普通日志不得返回绝对路径、PID、进程启动时间、命令行或内部 staging locator；这些字段只能用于后端归属证明和诊断。

#### Scenario: 重启后不自动接管归档资源

- **WHEN** 应用重启时存在未完成的 Legacy 归档尝试、WinRAR 进程或 staging
- **THEN** 归档尝试标记为 `interrupted`，案件进入 `archive_interrupted`，用户确认前不得重新执行
- **AND** 系统不得连接、等待、接管或自动终止无法证明属于本系统的 WinRAR 进程
- **AND** 系统不得仅凭目录名、PID、进程名或命令行片段认定 staging 或进程归属

#### Scenario: 自有 staging 的最低归属证明

- **WHEN** staging 同时满足以下条件：位于应用控制的 staging 根；具有系统生成且不可猜测的 `attempt_id`；数据库或受控索引存在对应归档尝试记录；staging 内存在系统写入的 ownership marker；marker 与归档尝试记录中的 `attempt_id`、部署实例和受控 staging 根匹配
- **THEN** 系统可以将未完成 staging 标记为隔离或执行安全清理
- **AND** 多次恢复或清理必须幂等，清理失败不得阻止案件、草稿、任务和图片资产恢复
- **AND** marker 格式和存储结构可以由实现决定，但不得进入公共 DTO

#### Scenario: staging 归属证据缺失或冲突

- **WHEN** 任一最低归属证据缺失、记录冲突、marker 不匹配或无法确认
- **THEN** 资源一律视为未知，不删除、不终止相关进程、不覆盖
- **AND** 系统只记录不含绝对路径的安全诊断结果

#### Scenario: 半成品和正式产物隔离

- **WHEN** 重启或失败后发现未验证的 RAR 或 Manifest
- **THEN** 半成品 RAR 不进入正式产物索引，半成品 Manifest 不注册、不返回、不驱动 Word 导出
- **AND** 已完成并通过校验的 RAR、Manifest 和 Word 不因案件恢复或普通清理被删除

#### Scenario: 归档恢复不泄露路径

- **WHEN** API、DTO、错误响应、任务状态或普通日志返回归档恢复结果
- **THEN** 只返回 opaque ID、稳定错误码和安全摘要
- **AND** 不返回绝对路径、staging 物理路径、完整进程命令行或原始文件列表

### Requirement: 检材和人员顺序由案件权威数组驱动

检材默认排序 MUST 使用自然升序；编号重复或无法识别时保持报告原始相对顺序。用户拖拽后，案件数组成为审核界面、正文、附件摘要、附件 1、附件 2、附件 3 和 Word 的唯一顺序来源。人员卡片顺序同理，并同步更新共享默认人员顺序。

#### Scenario: 默认排序和拖拽一致性

- **WHEN** 编号全部可识别且互不重复
- **THEN** 按自然升序建立默认数组
- **WHEN** 编号重复或无法识别
- **THEN** 保持报告原始相对顺序
- **WHEN** 用户拖拽并保存
- **THEN** 正文、附件和 Word 使用同一有序数组，不得下游二次排序

### Requirement: 预计分卷和光盘编号映射以 Manifest 收敛

每个 VolumeSlot MUST 有稳定身份、序号、计划版本和容量/输入范围。光盘编号默认由共享前缀连续生成；用户可修改完整编号但必须非空且在案件内唯一，允许不连续；刻录日期独立。replan 使用稳定槽位身份保留有效人工映射；新增槽位 pending，删除槽位清除映射；最终以验证后的 Manifest 为准。

#### Scenario: 初始计划、编号和 replan

- **WHEN** 用户在压缩前查看或修改计划
- **THEN** 页面逐卷显示预计分卷和光盘编号，拒绝空值/重复值，允许非连续唯一值
- **WHEN** inventory 变化并 replan
- **THEN** 仍存在槽位保留有效人工编号，新槽位待确认，删除槽位清除映射，匹配不依赖预计 RAR 文件名

#### Scenario: Manifest 验证收敛

- **WHEN** 归档完成并通过 Manifest 验证
- **THEN** 验证后的 Manifest 保存最终槽位、卷序和光盘编号并成为权威
- **AND** 草稿计划与 Manifest 不一致时阻止交付完成状态

### Requirement: 后台归档阶段里程碑和资源准入可恢复

解析任务可以并行；压缩任务最多 6 个 running，但不要求启动 6 个 WinRAR。调度器 MUST 综合配置化的磁盘空间、临时空间、CPU、IO、输入规模和当前进程数决定运行或排队。归档任务覆盖 inventory、规划、WinRAR、完整性、MD5、Manifest 生成和验证。

归档进度类型 MUST 固定为 `workflow_milestone`。它表示工作流已经进入或完成的真实阶段，不表示 WinRAR 内部压缩字节百分比。版本化合同 MUST 使用固定且单调的 `0/10/20/30/75/85/90/95/100` 里程碑，分别对应等待归档或资源准入、核对 inventory/路径、前置检查通过、创建 RAR 分卷、RAR 成功后开始完整性校验、完整性通过、开始 MD5、开始写入并验证 Manifest、正式归档完成。

TaskRecord MUST 复用已有 `status`、`stage`、`percent`、`created_at`、`started_at`、`finished_at`、`error_code`、`error_summary` 和 `cancel_requested`；Phase 3 增加或内部持久化 `stage_label`、1-based `stage_index`、版本化 `stage_count`、`progress_kind=workflow_milestone`、`updated_at`、`last_heartbeat_at`、`output_volume_count`、`output_bytes`、`last_output_change_at`、`worker_state` 和后端权威 `allowed_actions`。`percent` 在归档任务中表示固定里程碑；不得创建 `progress_percent`、`completed_at` 或 `error_message` 等同义字段。

案件列表 MUST 使用 `ArchiveTaskCardSummary` 或等价安全摘要投影，不直接返回全部 TaskRecord/Worker 诊断字段。摘要只表达卡片所需的状态、阶段文字/序号、里程碑、展示时间、紧凑活动指标、安全失败摘要和 `allowed_actions`；不得包含 Worker ID、内部租约、绝对路径、堆栈、技术日志、完整错误代码、完整进程信息或完整任务历史。

#### Scenario: 立即或稍后压缩及资源排队

- **WHEN** 报告解析成功
- **THEN** 系统询问立即开始或暂不压缩，暂不压缩不创建运行中的压缩进程
- **WHEN** 并发上限或资源准入不满足
- **THEN** 新任务排队并显示原因

#### Scenario: 真实阶段才推进固定里程碑

- **WHEN** 任务进入归档阶段
- **THEN** 后端只在真实阶段开始或门控成功时持久化对应的固定里程碑，并同时返回阶段文字
- **AND** 里程碑单调不下降，不读取 WinRAR CLI 连续百分比，不使用历史最大值、钳制、平滑、过滤、时间、文件/字节数量或输出大小制造中间百分比
- **AND** WinRAR 执行期间保持 30%，前端使用不确定进度动态条纹或加载图标作为主要活动反馈，`总体里程碑：30%` 只能作为次要说明
- **AND** WinRAR 成功后才进入 75%，完整性通过后才进入 85%，MD5 和 Manifest 真实开始后才分别进入 90% 和 95%，完整 Manifest 验证及正式完成提交成功后才进入 100%

#### Scenario: WinRAR 长耗时阶段以真实活动摘要证明仍在运行

- **WHEN** 大文件归档长时间停留在创建 RAR 分卷阶段
- **THEN** 案件卡片主要显示“归档中”“正在创建 RAR 分卷”“阶段 X / N”、indeterminate 活动态、已运行时间、任务状态、最近心跳、当前检测分卷数量和当前输出总字节数
- **AND** `output_volume_count` 只表示当前 attempt 受控 staging 中匹配分卷名规则的文件数量，可能包含正在写入的当前卷
- **AND** `output_bytes` 只表示这些匹配文件当前在磁盘上已经写出的总字节数
- **AND** 两项活动指标不得换算为压缩完成比例，不得显示“已完成若干分卷，占总任务百分比”
- **AND** 输出大小暂时不变化不得单独判定失败、卡死或触发自动取消，因为任务可能处于 CPU 密集或缓冲阶段

#### Scenario: Worker 心跳和所有权状态准确

- **WHEN** Worker 持有并执行当前归档任务
- **THEN** Worker 按受控频率更新 `last_heartbeat_at`，并节流写入聚合后的分卷数、输出字节数和 `last_output_change_at`
- **AND** 不得为每个文件系统变化事件写数据库
- **WHEN** Worker 未持有任务、正在恢复或等待接管
- **THEN** `worker_state` 和卡片文字准确显示未分配、恢复中或等待接管，不得显示“仍在运行”

#### Scenario: 失败取消和重启恢复最后阶段

- **WHEN** 归档任务失败、取消或被服务重启中断
- **THEN** 持久化任务状态、当前或失败阶段、该阶段对应的最后里程碑、时间和安全错误信息
- **AND** 失败或取消不得进入 100%，半成品 RAR/Manifest 不得成为正式结果
- **AND** 页面刷新从 TaskRecord 恢复阶段、里程碑、开始/更新时间、心跳、输出字节、分卷数、最近输出变化、Worker 状态、失败/取消和允许操作
- **AND** 服务重启先恢复最后确认里程碑并显示恢复中或等待接管；Worker 重新取得持久化任务所有权后才更新心跳并显示仍在运行
- **AND** 重新取得任务所有权不表示自动连接旧 WinRAR、复用旧半成品或断点续压

#### Scenario: 案件工作台卡片是主进度入口

- **WHEN** 用户打开案件工作台而未进入案件详情
- **THEN** 每张案件卡片直接显示该案件当前或最近一次归档任务摘要，默认最多组织案件基本信息、状态/阶段、最多两行活动或状态摘要和主要操作四类内容
- **AND** 允许操作至少按状态表达取消、重试或查看结果；前端不得只显示数字百分比
- **AND** 创建 RAR 分卷阶段不得以静止 30% 进度条作为主要反馈，indeterminate 动画必须同时提供“任务仍在运行”或恢复状态等无障碍文字，不能只依赖颜色或动画
- **AND** 不得以与案件卡片分离的归档任务卡片作为唯一入口
- **AND** 案件详情可以额外显示任务日志、分卷清单和历史记录，但不得替代案件卡片摘要

#### Scenario: 卡片内容随归档状态替换

- **WHEN** 案件尚未归档
- **THEN** 卡片显示未归档状态和归档前检查/归档入口，不显示空进度或空活动指标
- **WHEN** 任务等待执行、恢复中或等待 Worker 接管
- **THEN** 卡片显示等待/恢复文字和最后确认里程碑，不得显示“仍在运行”
- **WHEN** 任务正在执行
- **THEN** 卡片突出当前阶段，显示活动文字、已运行时间、取消操作，并将易读的分卷数量/输出大小与相对最后活动时间限制在最多两行
- **WHEN** 任务失败
- **THEN** 安全可理解的失败摘要、失败阶段/时间和适用的已生成分卷数替换普通活动指标，并提供查看原因和重试
- **WHEN** 任务已取消
- **THEN** 卡片显示取消时阶段、取消时间和重新归档或查看详情操作
- **WHEN** 任务已完成
- **THEN** 卡片压缩显示完成、100%、总分卷数、完成时间和查看结果，不再显示心跳、Worker 状态或动态动画

#### Scenario: 默认卡片不展开技术详情

- **WHEN** 当前或历史归档任务包含完整阶段时间线、逐卷文件名/大小/MD5、Manifest 路径/内容、Worker ID、内部租约、精确心跳时间戳、完整错误代码、堆栈、技术日志、重试/调度诊断或进程信息
- **THEN** 默认案件卡片不平铺这些字段，只提供归档详情或查看结果入口
- **AND** 案件列表 API 不返回绝对路径、堆栈、Worker ID、内部租约或完整技术日志

#### Scenario: 卡片响应式和无障碍

- **WHEN** 卡片处于窄屏、长文号、长失败摘要或大数字场景
- **THEN** 次要活动指标可以隐藏或收起，但案件信息、状态、阶段文字和主要操作必须保留，内容不得撑破布局
- **AND** 次要操作收进更多菜单或详情入口，按钮数量保持受控
- **WHEN** 用户不支持动画或启用减少动态效果
- **THEN** 仍通过明确文字得知“正在创建 RAR 分卷”或当前恢复状态
- **AND** 成功、失败、取消和运行中状态不得只依赖颜色；相对活动时间在前端本地刷新，不因此增加后端请求

#### Scenario: 重启中断而非自动接管

- **WHEN** 服务重启时存在 running 任务或 WinRAR 进程
- **THEN** 任务标记为 interrupted 或 failed_retryable
- **AND** 只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，不信任或发布半成品 RAR/Manifest
- **AND** 用户确认后重新执行，不实现断点续压或 WinRAR 重连

### Requirement: WinRAR 进度策略决策保留 Legacy 安全边界

Phase 3 开始前 MUST 完成 WinRAR 进度能力 spike 和明确产品/架构决策。RAR 5.90、RAR 7.23 普通 pipe 及 RAR 7.23 ConPTY 的合成实验已经证明 CLI 百分比混合不同作用域且可重复回退。Phase 3 MUST NOT 读取连续 WinRAR 百分比，而 MUST 使用 `workflow_milestone`。现有 WinRAR、RAR 分卷、Legacy 显式压缩、inventory、路径/变化、完整性、MD5、Manifest、Word 和发布门控保持不变。

#### Scenario: 失败 spike 形成明确适配决定

- **WHEN** 普通 pipe 和 ConPTY spike 均证明 WinRAR CLI 百分比不可作为稳定总进度
- **THEN** 产品/架构决定采用固定 `workflow_milestone`，完成版本/适配前置决策并允许 T011 按任务顺序开始
- **AND** spike 文档和合成测试继续作为放弃连续 CLI 百分比的证据
- **AND** 该决定本身不表示 T011–T015 已实现或 Phase 3 已验收

#### Scenario: 里程碑适配不削弱 Legacy

- **WHEN** Phase 3 后台任务包装现有归档执行
- **THEN** WinRAR 运行期间只报告“正在创建 RAR 分卷”的阶段里程碑和活动状态
- **AND** 不解析或推断内部连续百分比，不改变 RAR 分卷或基础名规则
- **AND** 任一既有正式安全门控失败时不得推进到后续里程碑或正式完成

### Requirement: Word 下载名称与正式产物隔离

每次点击导出 Word 文档 MUST 弹出文件名输入框，默认值为 文号.docx；文号为空时默认值为空。不记忆上次输入；未输入 .docx 时自动补全；取消不导出。继续校验 Windows 非法字符和空名称。下载名称只控制下载名，服务器物理文件名必须唯一、安全、不可覆盖。

#### Scenario: 每次询问、取消和物理文件隔离

- **WHEN** 用户点击导出
- **THEN** 系统重新打开输入框，取消或非法名称不创建任务/文件
- **WHEN** 用户输入合法名称
- **THEN** 下载名按输入补全，服务器物理文件使用唯一安全名且不覆盖正式产物

### Requirement: 预置模板版本可复现且切换不触发归档

系统只允许选择已注册且审核通过的模板版本。每个版本 MUST 有独立模板 ID、版本号、指纹、校验规则和验收记录。案件保存所选模板及版本。切换模板不重新压缩、不重新生成 Manifest，仅使旧 Word 失效；下次导出重新校验模板并生成 Word。

#### Scenario: 选择和切换模板

- **WHEN** 用户打开模板选择器或切换 approved 版本
- **THEN** 只显示 approved 版本，保存案件引用并使旧 Word 失效
- **AND** 未知 DOCX、未审核版本、RAR、Manifest 和光盘映射不受模板切换影响

#### Scenario: 导出前重新验证

- **WHEN** 用户切换模板后再次导出
- **THEN** 后端按 ID、版本、指纹和规则重新校验并执行现有 VML、分页、表格、附件和 Word 安全门控
- **AND** 校验失败时不发布 Word

### Requirement: 无登录环境的审计身份不冒充认证身份

强制接管、默认值迁移、共享默认值修改和重要任务操作 MUST 记录 client instance ID、session ID、可选本地显示名称、部署实例和时间。系统不得把这些字段描述为真实人员身份或认证结果。

#### Scenario: 记录接管和默认值操作

- **WHEN** 用户确认接管、导入/忽略旧默认值或修改共享默认值
- **THEN** 审计记录保存上述无认证身份字段集合
- **AND** 界面显示为本地会话审计，不显示已认证人员

### Requirement: SQLite 只保存业务 DTO 和 opaque 资产引用

SQLite MUST 只保存案件业务 DTO、任务/租约/版本/索引元数据、SourceRecord 和 opaque asset 引用，不保存 Base64 图片、完整 HTML、原始 JSON 集合或其他大对象。图片、来源快照、缓存、临时文件和正式产物继续保存于受控文件系统资产。

#### Scenario: 大对象使用受控资产引用

- **WHEN** 案件包含图片组、来源快照或大对象
- **THEN** CaseDraft 只保存 opaque asset_id 和必要 metadata/fingerprint
- **AND** 实际内容由受控资产存储管理

#### Scenario: 草稿序列化边界

- **WHEN** 保存或读取 CaseDraft
- **THEN** SQLite 记录只包含可迁移业务 DTO 和元数据
- **AND** Base64、完整 HTML、原始 JSON 集合和不可控二进制被拒绝写入

### Requirement: 案件清理保护正式产物

案件记录、草稿、运行任务和正式 RAR/Manifest/Word MUST 独立管理。成功导出后，案件卡片、草稿和任务记录默认保留 30 天，保留时间可配置；正式产物不因该策略自动删除。正在解析、压缩、尚未导出或失败待重试的案件不得自动清理。

#### Scenario: 成功案件到期清理

- **WHEN** 案件成功导出且超过记录保留期
- **THEN** 自动清理只删除案件记录、草稿、任务索引和允许删除的临时缓存
- **AND** 不删除正式 RAR、Manifest 或 Word

#### Scenario: 活跃案件和手动删除

- **WHEN** 案件正在解析、压缩、尚未导出或失败待重试
- **THEN** 自动清理跳过案件
- **WHEN** 用户请求删除正在解析或压缩的案件
- **THEN** 系统要求先取消任务、等待自有进程结束及 staging 清理完成，案件记录删除仍不删除正式产物

### Requirement: Legacy 正式边界和 Shadow 暂停不被削弱

所有正式 Word、RAR 和 Manifest MUST 继续由 Legacy 链路生成和验证。案件草稿保存 Legacy InspectionReport，不要求 Canonical 才能审核或导出。Shadow 比较不参与案件状态、进度、门控或正式产物。

#### Scenario: Legacy 安全门控

- **WHEN** 案件满足导出条件并开始正式输出
- **THEN** 继续执行完整 inventory、路径/链接/文件变化、WinRAR、完整性、MD5、Manifest 和 Word 门控
- **AND** 任一门控失败都不得发布正式完成状态

#### Scenario: Shadow 和 Canonical 边界

- **WHEN** 本变更的案件、任务或模板流程运行
- **THEN** 不启动 Shadow 真实样本治理，不调用 Canonical 作为正式输入
- **AND** 未来比较只能在独立边界和明确开关下进行

### Requirement: 案件工作台图片资产可持久化恢复

工作台 MUST 将用户新增、替换和删除的图片绑定到 `case_id`，并将图片二进制保存到受控应用资产存储；CaseDraft、API 和日志 MUST 只保存 opaque 资产引用、指纹和安全元数据，不得保存 Base64、完整二进制或服务器绝对路径。

#### Scenario: 上传成功后持久化并恢复

- **WHEN** 用户在有效编辑租约下上传合法 JPG/JPEG/PNG
- **THEN** 后端校验真实签名、扩展名、大小和案件配额，原子写入资产后返回 opaque 引用
- **AND** 只有上传成功的引用才进入 CaseDraft，刷新、切换案件或重启后端仍能读取同一图片

#### Scenario: 图片变更受租约和 revision 保护

- **WHEN** 用户替换或删除图片
- **THEN** 新资产成功写入后才替换旧引用，草稿使用 expected revision 保存，冲突不得静默覆盖另一会话
- **AND** 只读或失效租约不能上传、替换或删除图片，未引用资产按宽限期安全清理

#### Scenario: 图片读取失败阻止静默导出

- **WHEN** 草稿引用的图片缺失、损坏或不属于当前案件
- **THEN** 资产列表、预览或读取接口返回稳定可恢复错误，工作台提示重新上传
- **AND** Word 预览/导出不得静默生成缺图结果，正式模板和 Legacy 输出规则保持不变

### Requirement: 案件工作台承接完整生成笔录能力

案件工作台 MUST be the primary production entry for electronic inspection records. It MUST
use the same Legacy `InspectionReport` field contract, validation rules, date/time handling,
attachment model, preview projection, and Word export mapping as the existing generation
capability. The workbench presentation MAY reorganize the layout and add case status, autosave,
lease, source, and multi-case controls, but MUST NOT maintain a simplified second editor.
The retained backend `/records/*` endpoints are Legacy compatibility entries and the only formal
Legacy output pipeline; they are not a competing persistent workbench flow.

#### Scenario: 完整审核编辑器

- **WHEN** a case reaches `review_ready`
- **THEN** the workbench exposes all Legacy review fields, data summary, attachment information,
  image editing controls, required/format validation, preview, formal Word export, and custom
  download filename handling
- **AND** the case draft, revision, and edit lease remain the write authority for the workbench

#### Scenario: 统一入口和兼容路由

- **WHEN** a user opens the old frontend generation URL
- **THEN** the URL redirects to the workbench without exposing a competing upload/editor flow
- **AND** backend `/records/*` compatibility contracts, Legacy Parser output, Word, Manifest,
  and formal archive safety gates remain available and unchanged

#### Scenario: 工作台预览不自动归档

- **WHEN** 工作台已持久化 CaseShell、SourceRecord 和解析任务，并在解析成功后保存 CaseDraft
- **THEN** 用户可以审核和保存草稿，预览动作本身不得启动 WinRAR 或创建 Phase 3 后台归档任务
- **AND** 只有用户显式选择“立即开始压缩”后才进入受控 Legacy 显式归档入口
- **AND** 用户选择“稍后压缩”时持久化 `archive_deferred`，不启动归档

#### Scenario: 完整能力不退化工作台优化

- **WHEN** the user switches cases, refreshes, loses a lease, or receives a source warning
- **THEN** the workbench preserves its case-card status, autosave result, read-only warning,
  source status, retry, and return-to-list experience
- **AND** it does not reintroduce the old page's mixed archive-upload flow or duplicate field,
  validation, attachment, or export rules
