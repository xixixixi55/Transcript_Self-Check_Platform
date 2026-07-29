# Electronic Inspection Record: Persistent Workbench Contract

本文件是 persistent-case-workbench-and-archive-coordination 的变更合同。实现与测试完成前，不修改 openspec/specs/ 下的 living spec。

## Contract vocabulary

- CaseShell：提交报告后立即创建的案件记录；解析成功前不含可审核 Legacy InspectionReport。
- CaseDraft：解析成功后的可编辑草稿；report 始终是 Legacy InspectionReport。
- SourceRecord：受控来源记录，保存 opaque 来源 ID、允许根授权、内部路径、绑定关系和复核结果。
- FieldState：可编辑字段、检材字段、人员项或附件图片组的来源与确认状态。
- TaskRecord：可恢复的解析任务和最小归档尝试记录；本阶段不把它扩展为持久化归档 Worker。
- VolumeSlot：不依赖预计 RAR 文件名的稳定逻辑分卷槽位。
- VerifiedManifest：完整归档门控通过后生成并验证的正式 Manifest。

## Requirement: 案件壳和多案件工作台可恢复

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

## Requirement: 自动保存和编辑租约防止互相覆盖

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

## Requirement: 共享默认值与当前案件双写可区分

部署实例 MUST 共享完整文号、检查地点、检查方法、检查硬件、检查人员及顺序、光盘编号前缀。用户修改这些字段后，经校验和防抖，当前案件来源变为 user，同时更新共享默认值供以后新案件继承。草稿保存结果和共享默认值保存结果 MUST 分别返回。

#### Scenario: 案件字段修改同步共享默认值

- **WHEN** 用户修改文号、地点、方法、硬件或光盘前缀且校验和防抖完成
- **THEN** 当前案件字段保存为 user 来源并提交共享默认值更新
- **AND** API 分别返回 draft_save_status 和 shared_defaults_save_status

#### Scenario: 双写部分失败可见

- **WHEN** 一侧保存成功而另一侧失败
- **THEN** 页面分别显示两个结果和可重试动作
- **AND** 不得显示为一次全部成功

#### Scenario: 人员拖拽同步两种顺序

- **WHEN** 用户拖拽当前案件检查人员卡片并保存
- **THEN** 当前案件 InspectorSnapshot 顺序变为 user 确认顺序
- **AND** 共享默认人员顺序同时更新并分别返回两种保存状态

#### Scenario: 旧 localStorage 迁移

- **WHEN** 浏览器存在旧默认值且部署实例尚无迁移决定
- **THEN** 系统提示导入或忽略，不得静默写入共享默认值
- **AND** 导入或忽略只能成功一次并记录无认证身份审计信息

## Requirement: 解析值优先于共享默认值

字段初始化 MUST 遵循 report > system_default 的来源优先级，pending 是独立确认状态。有效非空解析值来源为 report；报告缺失、为空或无法识别时才使用共享默认值；用户修改后来源统一为 user。

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

## Requirement: 字段来源和待确认状态可追踪

每个可编辑叶子字段、检材字段、人员项和附件图片组 MUST 有 FieldState，包含稳定字段路径、来源 report | user | system_default、确认状态 confirmed | pending 和 revision。纯派生不可编辑字段继承来源，不单独维护状态；来源颜色不得进入 Word，pending 必须有文字提示。

#### Scenario: 来源展示和导出隔离

- **WHEN** 字段来自报告、系统默认值或人工修改
- **THEN** 审核界面显示相应来源
- **AND** Word 使用正式黑字，不携带来源颜色

#### Scenario: 待确认不只靠颜色

- **WHEN** 检材、关键字段或图片组处于 pending
- **THEN** 页面显示待人工确认文字和影响范围
- **AND** 正式导出执行现有确认门控

## Requirement: SourceRecord 保护来源可访问性

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

## Requirement: 解析后压缩时机决策

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

## Requirement: Phase 1D 最小归档中断和产物保护

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

## Requirement: 检材和人员顺序由案件权威数组驱动

检材默认排序 MUST 使用自然升序；编号重复或无法识别时保持报告原始相对顺序。用户拖拽后，案件数组成为审核界面、正文、附件摘要、附件 1、附件 2、附件 3 和 Word 的唯一顺序来源。人员卡片顺序同理，并同步更新共享默认人员顺序。

#### Scenario: 默认排序和拖拽一致性

- **WHEN** 编号全部可识别且互不重复
- **THEN** 按自然升序建立默认数组
- **WHEN** 编号重复或无法识别
- **THEN** 保持报告原始相对顺序
- **WHEN** 用户拖拽并保存
- **THEN** 正文、附件和 Word 使用同一有序数组，不得下游二次排序

## Requirement: 预计分卷和光盘编号映射以 Manifest 收敛

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

## Requirement: 后台任务真实进度和资源准入可恢复

解析任务可以并行；压缩任务最多 6 个 running，但不要求启动 6 个 WinRAR。调度器 MUST 综合配置化的磁盘空间、临时空间、CPU、IO、输入规模和当前进程数决定运行或排队。归档任务覆盖 inventory、规划、WinRAR、完整性、MD5、Manifest 生成和验证。

#### Scenario: 立即或稍后压缩及资源排队

- **WHEN** 报告解析成功
- **THEN** 系统询问立即开始或暂不压缩，暂不压缩不创建运行中的压缩进程
- **WHEN** 并发上限或资源准入不满足
- **THEN** 新任务排队并显示原因

#### Scenario: 真实单调进度

- **WHEN** 任务进入归档阶段
- **THEN** 百分比来自实际计数或已验证 WinRAR 信号并同时返回阶段
- **AND** 百分比单调不下降，不使用时间、循环动画或输出文件大小冒充进度

#### Scenario: 重启中断而非自动接管

- **WHEN** 服务重启时存在 running 任务或 WinRAR 进程
- **THEN** 任务标记为 interrupted 或 failed_retryable
- **AND** 只终止能够证明由本系统启动的进程树，清理本系统拥有的 staging，不信任或发布半成品 RAR/Manifest
- **AND** 用户确认后重新执行，不实现断点续压或 WinRAR 重连

## Requirement: WinRAR 进度能力先验收再收口

Phase 3 开始前 MUST 完成当前正式 WinRAR 版本的进度能力 spike。真实百分比未验证前，Phase 3 不得宣布验收完成；迁移期间必须保留现有 Legacy 显式压缩能力。当前版本不支持可靠百分比时，必须先汇报并选择受支持版本或适配方式，不得用未验证策略让现有压缩全部失效。

#### Scenario: spike 通过后进入 Phase 3

- **WHEN** spike 证明受支持 WinRAR 版本可以提供稳定、可解释进度
- **THEN** Phase 3 才允许进入真实进度实现和验收
- **AND** 证据使用合成输入和外部环境记录

#### Scenario: spike 未通过时保留 Legacy

- **WHEN** 当前版本无法提供可靠百分比
- **THEN** 系统报告能力缺口并暂停 Phase 3 完成门槛
- **AND** 迁移期间保留 Legacy 显式压缩，不伪造百分比，也不直接让现有压缩失效

## Requirement: Word 下载名称与正式产物隔离

每次点击导出 Word 文档 MUST 弹出文件名输入框，默认值为 文号.docx；文号为空时默认值为空。不记忆上次输入；未输入 .docx 时自动补全；取消不导出。继续校验 Windows 非法字符和空名称。下载名称只控制下载名，服务器物理文件名必须唯一、安全、不可覆盖。

#### Scenario: 每次询问、取消和物理文件隔离

- **WHEN** 用户点击导出
- **THEN** 系统重新打开输入框，取消或非法名称不创建任务/文件
- **WHEN** 用户输入合法名称
- **THEN** 下载名按输入补全，服务器物理文件使用唯一安全名且不覆盖正式产物

## Requirement: 预置模板版本可复现且切换不触发归档

系统只允许选择已注册且审核通过的模板版本。每个版本 MUST 有独立模板 ID、版本号、指纹、校验规则和验收记录。案件保存所选模板及版本。切换模板不重新压缩、不重新生成 Manifest，仅使旧 Word 失效；下次导出重新校验模板并生成 Word。

#### Scenario: 选择和切换模板

- **WHEN** 用户打开模板选择器或切换 approved 版本
- **THEN** 只显示 approved 版本，保存案件引用并使旧 Word 失效
- **AND** 未知 DOCX、未审核版本、RAR、Manifest 和光盘映射不受模板切换影响

#### Scenario: 导出前重新验证

- **WHEN** 用户切换模板后再次导出
- **THEN** 后端按 ID、版本、指纹和规则重新校验并执行现有 VML、分页、表格、附件和 Word 安全门控
- **AND** 校验失败时不发布 Word

## Requirement: 无登录环境的审计身份不冒充认证身份

强制接管、默认值迁移、共享默认值修改和重要任务操作 MUST 记录 client instance ID、session ID、可选本地显示名称、部署实例和时间。系统不得把这些字段描述为真实人员身份或认证结果。

#### Scenario: 记录接管和默认值操作

- **WHEN** 用户确认接管、导入/忽略旧默认值或修改共享默认值
- **THEN** 审计记录保存上述无认证身份字段集合
- **AND** 界面显示为本地会话审计，不显示已认证人员

## Requirement: SQLite 只保存业务 DTO 和 opaque 资产引用

SQLite MUST 只保存案件业务 DTO、任务/租约/版本/索引元数据、SourceRecord 和 opaque asset 引用，不保存 Base64 图片、完整 HTML、原始 JSON 集合或其他大对象。图片、来源快照、缓存、临时文件和正式产物继续保存于受控文件系统资产。

#### Scenario: 大对象使用受控资产引用

- **WHEN** 案件包含图片组、来源快照或大对象
- **THEN** CaseDraft 只保存 opaque asset_id 和必要 metadata/fingerprint
- **AND** 实际内容由受控资产存储管理

#### Scenario: 草稿序列化边界

- **WHEN** 保存或读取 CaseDraft
- **THEN** SQLite 记录只包含可迁移业务 DTO 和元数据
- **AND** Base64、完整 HTML、原始 JSON 集合和不可控二进制被拒绝写入

## Requirement: 案件清理保护正式产物

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

## Requirement: Legacy 正式边界和 Shadow 暂停不被削弱

所有正式 Word、RAR 和 Manifest MUST 继续由 Legacy 链路生成和验证。案件草稿保存 Legacy InspectionReport，不要求 Canonical 才能审核或导出。Shadow 比较不参与案件状态、进度、门控或正式产物。

#### Scenario: Legacy 安全门控

- **WHEN** 案件满足导出条件并开始正式输出
- **THEN** 继续执行完整 inventory、路径/链接/文件变化、WinRAR、完整性、MD5、Manifest 和 Word 门控
- **AND** 任一门控失败都不得发布正式完成状态

#### Scenario: Shadow 和 Canonical 边界

- **WHEN** 本变更的案件、任务或模板流程运行
- **THEN** 不启动 Shadow 真实样本治理，不调用 Canonical 作为正式输入
- **AND** 未来比较只能在独立边界和明确开关下进行

## Requirement: 案件工作台图片资产可持久化恢复

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

## Requirement: 案件工作台承接完整生成笔录能力

案件工作台 MUST be the primary production entry for electronic inspection records. It MUST
use the same Legacy `InspectionReport` field contract, validation rules, date/time handling,
attachment model, preview projection, and Word export mapping as the existing generation
capability. The workbench presentation MAY reorganize the layout and add case status, autosave,
lease, source, and multi-case controls, but MUST NOT maintain a simplified second editor.

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

#### Scenario: 完整能力不退化工作台优化

- **WHEN** the user switches cases, refreshes, loses a lease, or receives a source warning
- **THEN** the workbench preserves its case-card status, autosave result, read-only warning,
  source status, retry, and return-to-list experience
- **AND** it does not reintroduce the old page's mixed archive-upload flow or duplicate field,
  validation, attachment, or export rules
