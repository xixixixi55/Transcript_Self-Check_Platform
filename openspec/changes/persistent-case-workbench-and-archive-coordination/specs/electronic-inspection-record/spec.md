# Electronic Inspection Record: Persistent Workbench Contract

本文件是 persistent-case-workbench-and-archive-coordination 的变更合同。实现与测试完成前，不修改 openspec/specs/ 下的 living spec。

## Contract vocabulary

- CaseShell：提交报告后立即创建的案件记录；解析成功前不含可审核 Legacy InspectionReport。
- CaseDraft：解析成功后的可编辑草稿；report 始终是 Legacy InspectionReport。
- SourceRecord：受控来源记录，保存 opaque 来源 ID、允许根授权、内部路径、绑定关系和复核结果。
- FieldState：可编辑字段、检材字段、人员项或附件图片组的来源与确认状态。
- TaskRecord：可恢复的解析、归档、导出或清理任务记录。
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
- **AND** 重启前运行中的 WinRAR 任务标记为 interrupted 或 failed_retryable，不默认成功或自动重连

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

系统 MUST 为每个来源创建 SourceRecord，包含 opaque source_id、后端内部路径、允许根授权、source_type、case_id/task_id 绑定、metadata/fingerprint、访问状态和最近复核时间。API、日志和前端不得暴露绝对路径；来源失效时必须要求重新选择。

#### Scenario: 来源绑定和重启复核

- **WHEN** 用户提交报告并创建解析任务
- **THEN** SourceRecord 绑定案件壳和 task_id，并保存允许根授权及 metadata/fingerprint
- **WHEN** 服务重启或任务恢复前访问来源
- **THEN** 后端复核允许根、路径、权限、链接安全性和 fingerprint/metadata，失败则要求重新选择

#### Scenario: 来源路径不对外泄露

- **WHEN** API 返回错误、任务进度或审计日志
- **THEN** 只使用 opaque ID、错误码和安全摘要
- **AND** 不包含绝对路径、原始文件名集合或完整来源 JSON

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
