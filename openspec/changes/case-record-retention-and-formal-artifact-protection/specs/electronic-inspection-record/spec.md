# OpenSpec Delta: electronic-inspection-record

## ADDED Requirements

### Requirement: REQ-EIR-RET-001: Legacy 是清理前后正式输出唯一链路

案件记录清理前后，Legacy `/records/*` 兼容入口和既有 Legacy formal output chain MUST remain the only formal output path. Cleanup status、retention preview、现有 publication authority、formal Word artifact 和 cleaned tombstone MUST NOT introduce a second generation page or second formal renderer. 清理后的正式访问 MUST 按 `case_id`、`publication_id` 或 `word_artifact_id` 进入现有 Legacy/publication authority services；未清理案件的 task/context 入口只能作为兼容路径。

#### Scenario: 清理状态不改变 Legacy 正式输出

- **WHEN** 用户查看 cleaned case 的正式产物或兼容客户端调用 `/records/*` 的正式消费能力
- **THEN** 系统继续使用 Legacy-compatible DTO、既有 publication authority、Manifest/MD5/RAR/Word 完整性门控
- **AND** 不重新创建独立生成页面、第二正式 renderer 或 Canonical 输出

#### Scenario: 缺少 durable authority 时 Legacy 也拒绝

- **WHEN** cleaned case 的 publication facts、Manifest、formal Word artifact 或来源完整性事实不完整
- **THEN** Legacy formal download/export/reuse gate fail closed
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

持久化案件工作台 MUST 展示 policy mode、保留、到期、eligible、skipped、blocked、previewed、processing、cancelled、partial failure、failed、retryable、recoverable 和 `record_cleaned` 等安全状态及稳定原因。Preview MUST 使用 opaque case ID、revision/digest，不要求客户端提交路径、数据库身份或正式文件删除列表。工作台 MUST 不提供普通案件立即删除、公共人工 execute 或正式产物删除按钮；清理完成后不得编辑草稿，但正式产物入口 MUST 按 case/publication/Word artifact authority 状态单独展示。所有时间值 MUST 来自 timezone-aware UTC durable facts，公共 API MUST 返回带时区 ISO 8601，工作台显示 MUST 统一转换为 `Asia/Shanghai`。

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

- **WHEN** existing Legacy client submits a supported parse/export request
- **THEN** request continues to use its existing compatibility contract and Legacy formal chain
- **AND** it does not create a second retention or formal output fact source

#### Scenario: Legacy 请求携带删除意图被拒绝

- **WHEN** a Legacy request includes a path, cleanup category, formal artifact deletion flag, public execute intent or stale case revision
- **THEN** backend rejects the unsupported or stale input
- **AND** no cleanup or formal artifact deletion occurs
