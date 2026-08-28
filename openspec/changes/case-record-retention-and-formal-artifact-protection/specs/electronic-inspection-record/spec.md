# OpenSpec 差异：electronic-inspection-record

## MODIFIED Requirements

### Requirement: REQ-007: 任意字段可编辑

系统 MUST 通过后端 revision 合同自动保存工作台编辑；版本冲突、租约冲突和保存失败不得静默覆盖后端草稿。后端即使以 HTTP 2xx 返回业务层保存结果，前端也 MUST 根据 `draft_save_status` 和持久化 `draft` 是否存在判断保存是否真正成功；当状态不是 `saved` 或 `draft` 为空时，页面 MUST 显示失败/冲突状态、保留当前输入和待保存标记，并让手动保存返回失败，不得调用成功回调或重复发送同一请求形成循环。导出 Word MUST 在存在未完成保存时停止并显示可重试提示；没有未完成保存时仍可直接进入既有 Legacy Word 导出链路。

#### Scenario: HTTP 200 业务失败不会形成保存循环

- **WHEN** 用户修改案件字段后导出 Word，后端返回 HTTP 200 但 `draft_save_status` 不是 `saved` 或 `draft` 为空
- **THEN** 页面显示保存失败/冲突并保留当前输入，手动保存返回失败
- **AND** 不持续重发 `PATCH /draft`，导出显示保存未完成提示且不调用 Word 导出接口

#### Scenario: 无待保存修改仍可直接导出

- **WHEN** 案件没有未完成的草稿保存，用户不上传图片直接点击导出 Word
- **THEN** 页面跳过保存循环并进入既有 Legacy Word 导出链路，成功生成并触发下载

#### Scenario: 归档完成案件上传图片仍沿用当前生命周期保存

- **WHEN** 用户在 `archive_verified` 案件中上传图片并保存/导出，编辑请求按草稿保存合同省略 `lifecycle`
- **THEN** 后端沿用服务端当前案件生命周期，不把缺省值误判为 `review_ready` 的状态流转
- **AND** 图片资产引用与草稿一并保存成功，导出可以继续进入既有 Legacy Word 导出链路

#### Scenario: 人工检材编辑后继续上传图片

- **WHEN** 用户已成功绑定图片，随后人工添加或修改检材，并在本地字段自动保存完成前继续上传下一张图片
- **THEN** 前端直接以最后一次成功绑定的图片列表作为图片域 CAS 基线，不使用旧草稿 revision 预保存字段
- **AND** 图片绑定返回最新服务端草稿后，系统把尚未保存的人工检材编辑重放并通过既有 autosave rebase 队列保存
- **AND** 同一会话内的字段编辑不得被误报为“图片列表已被另一会话修改”，真实图片域并发仍返回冲突

## ADDED Requirements

### Requirement: REQ-EIR-RET-001: Legacy 是清理前后正式输出唯一链路

案件记录清理前后，Legacy `/records/*` 兼容入口和既有 Legacy formal output chain MUST remain the only formal output path. Cleanup status、retention preview、现有 publication authority、formal Word artifact 和 cleaned tombstone MUST NOT introduce a second generation page or second formal renderer. 清理后的正式访问 MUST 按 `case_id`、`publication_id` 或 `word_artifact_id` 进入现有 Legacy/publication authority services；未清理案件的 task/context 入口只能作为兼容路径。

#### Scenario: 清理状态不改变 Legacy 正式输出

- **WHEN** 用户查看 cleaned case 的正式产物或兼容客户端调用 `/records/*` 的正式消费能力
- **THEN** 系统继续使用 Legacy-compatible DTO、既有 publication authority、Manifest/MD5/RAR/Word 完整性门控
- **AND** 不重新创建独立生成页面、第二正式 renderer 或 Canonical 输出

#### Scenario: 缺少 durable authority 时 Legacy 也拒绝

- **WHEN** cleaned case 的 publication facts、Manifest、formal Word artifact 或来源完整性事实不完整
- **THEN** Legacy 正式下载/导出/复用门控以安全失败方式处理
- **AND** retention cleanup 不通过另一条链路补认或生成正式文件

### Requirement: REQ-EIR-RET-002: Canonical 和 Shadow 不参与 Phase 5 清理决策

Canonical MUST remain outside formal output, retention eligibility, cleanup authority, publication, download and Word gate decisions. Shadow MUST remain paused and isolated from cleanup status, progress, candidate selection, success/failure, formal artifact protection and audit outcome；其诊断 MUST NOT 作为 cleanup fact source 或验收替代。

#### Scenario: Canonical/Shadow 结果不改变候选

- **WHEN** Canonical 没有 production output 或 Shadow 产生孤立诊断结果，而 retention preview 运行
- **THEN** preview 和 execution 只使用 Legacy、SQLite、publication facts、Word artifact 和文件完整性事实
- **AND** Canonical/Shadow 状态不能使不合格案件变为 eligible

#### Scenario: 清理执行不调用暂停链路

- **WHEN** Scheduler 或 Coordinator 开始 retention preview 或 cleanup run
- **THEN** run 不调用 Canonical formal rendering 或 Shadow real-sample governance
- **AND** 不生成第二 RAR、Manifest 或 Word

### Requirement: REQ-EIR-RET-003: 工作台只呈现保留/preview/run 生命周期

持久化案件工作台 MUST 展示 policy mode、保留、到期、eligible、skipped、blocked、previewed、processing、cancelled、partial failure、failed、retryable、recoverable 和 `record_cleaned` 等安全状态及稳定原因。Preview MUST 使用 opaque case ID、revision/digest，不要求客户端提交路径、数据库身份或正式文件删除列表。Retention UI/API MUST 不提供自动清理的公共人工 execute、force-delete 或正式产物删除选项；显式 `case-workbench-delete` DELETE 由其自身确认和受控路径规则处理。清理完成后不得编辑草稿，但正式产物入口 MUST 按 case/publication/Word artifact authority 状态单独展示。所有时间值 MUST 来自 timezone-aware UTC durable facts，公共 API MUST 返回带时区 ISO 8601，工作台显示 MUST 统一转换为 `Asia/Shanghai`。

#### Scenario: 多案件工作台展示候选和跳过原因

- **WHEN** 用户从工作台打开 retention preview
- **THEN** 每个案件卡片显示 policy mode、到期判断、清理/保留类别、处理状态或稳定 blocker
- **AND** 一个案件的 blocker 不会被错误投影为另一个案件的成功

#### Scenario: 清理失败可展示恢复状态

- **WHEN** cleanup run 进入 cancelled、partial failure、failed、failed_retryable 或 interrupted
- **THEN** 工作台显示可解释的失败/等待恢复/重试状态
- **AND** 不显示“已删除正式产物”，不要求用户直接操作服务器文件，也不提供 force-delete

### Requirement: REQ-EIR-RET-004: Legacy 兼容请求不绕过清理和 authority 合同

现有 Legacy `/records/*` request/response compatibility MUST remain available for its existing parsing and formal output boundaries，但 Legacy request MUST NOT bypass deployment policy mode、cleanup qualification、publication/Word authority protection、revision/CAS、ownership 或稳定 identity gate。Deprecated 或 unrelated request fields MUST NOT 被解释为清理执行、人工授权或正式产物删除指令。

#### Scenario: Legacy 客户端继续使用正式合同

- **WHEN** 现有 Legacy 客户端提交受支持的解析/导出请求
- **THEN** 请求继续使用既有兼容合同和 Legacy 正式链路
- **AND** 不创建第二个保留策略或正式输出事实源

#### Scenario: Legacy 请求携带删除意图被拒绝

- **WHEN** Legacy 请求包含路径、清理类别、正式产物删除标记、公共执行意图或过时案件修订
- **THEN** 后端拒绝不受支持或过时的输入
- **AND** 不发生清理或正式产物删除
