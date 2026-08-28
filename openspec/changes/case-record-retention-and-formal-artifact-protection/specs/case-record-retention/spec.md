# OpenSpec 差异：case-record-retention

## ADDED Requirements

### Requirement: REQ-RET-001: deployment 级案件保留策略和模式

系统 MUST 持久化 deployment-scoped retention policy，模式固定为 `disabled`、`preview_only` 或 `enforce`。新安装和 v10→v11 升级 MUST 默认使用 `disabled`；默认 `retention_days` 为 30，合法范围为 1–3650 天；默认 `scan_interval_seconds` 为 86400 且不得小于 3600；默认 `batch_size` 为 20，合法范围为 1–1000。deployment 运维配置的 canonical names MUST 为 `BIJI_CASE_RETENTION_MODE`、`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和 `BIJI_CASE_RETENTION_BATCH_SIZE`，并写入 `case_retention_policies`。现有 `workbench.successful_case_retention_days` MUST 仅在 v10→v11 首次创建当前 deployment policy row 且新的 DAYS 环境变量缺失时提供 days；合法新 DAYS 始终优先，非法新 DAYS 不得回退旧键；非法旧值使用 30 天并记录诊断，policy row 创建后 Coordinator 不得直接读取旧键。旧键永远不能设置 mode、scan interval、batch、policy revision 或启用 enforce。不同 deployment MUST 不共享 policy、revision、anchor 或 cleanup state；非法配置 MUST 禁止 enforce 并 fail closed，不得使用 0、负数或其他魔法值静默启停。

#### Scenario: 新安装和升级默认安全模式

- **WHEN** 新安装或 v10→v11 migration 完成
- **THEN** policy mode 为 `disabled` 且 retention days 为 30
- **AND** 系统不自动把历史案件加入 enforce
- **AND** `disabled` 只允许恢复已有未完成 cleanup run，不创建新的删除 run
- **AND** 若新的 DAYS 环境变量缺失，只有 v10→v11 首次创建 policy row 才可读取合法旧键，之后 Coordinator 只读取 durable policy row

#### Scenario: 非法配置阻止 enforce

- **WHEN** canonical `BIJI_CASE_RETENTION_*` 配置、retention days、scan interval、batch size、deployment root 或 policy mode 无效，或旧键值非法/试图改变 v11 mode
- **THEN** 系统拒绝进入 `enforce`
- **AND** 非法旧值在首次 policy row 创建时使用 30 天并记录稳定兼容诊断，已有 policy row 不被旧键覆盖
- **AND** 返回稳定配置 blocker 并保留已有 durable state
- **AND** 不执行案件工作数据清理

### Requirement: REQ-RET-002: 保守 retention anchor 和到期判断

系统 MUST 使用以下 durable 事实计算 retention anchor：

```text
max(
  case_last_meaningful_mutation_at,
  latest_verified_formal_publication_at,
  latest_successful_word_export_at
)
```

`case_last_meaningful_mutation_at` MUST 来自 case retention durable record，并由报告/正式输入/来源/模板/附件变化和有效正式 retry 更新；页面打开、轮询、排序、纯展示偏好、只读 preview 和诊断读取不得更新。`latest_verified_formal_publication_at` MUST 精确定义为目标案件全部有效 publication 中最大的非空 `archive_publish_intents.publication_verified_at`；该字段 nullable，只能通过绑定 publication identity、durable succeeded/verified state、fence、Manifest digest、file inventory 和 ownership 的 NULL-only CAS 从 NULL 写入。普通读取、下载和重复验证不得更新时间，真正重新发布 MUST 创建新的 `publication_id`。v10 publication MUST 先经过受控 revalidation；失败保持 NULL 并阻止对应案件进入 enforce。不得使用普通 `updated_at`、文件 mtime、Manifest index 时间、下载时间或首次导出时间推断。`latest_successful_word_export_at` MUST 来自 durable formal Word artifact 的验证时间。所有持久化、比较、CAS、审计和 retention 计算时间 MUST 是带时区的 UTC timestamp；公共 API MUST 返回带时区 ISO 8601，前端、工作台、运维界面和人工验收 MUST 按 `Asia/Shanghai` 展示；无时区时间、缺失、冲突、无法验证或超过可信 UTC 5 分钟的未来时间 MUST 使 anchor unknown 并返回稳定 blocker。`expires_at_utc` MUST 为 `retention_anchor_utc + (retention_days × 24 hours)`；30 天等于连续 720 小时。Word/publication revalidation 成功或 meaningful mutation 后重新计算期限。

#### Scenario: 后续正式变化延后到期时间

- **WHEN** 案件在首次导出后又发生 meaningful mutation、verified publication 或成功 Word artifact export
- **THEN** 系统使用对应 durable 时间事实与既有 anchor 的最大值重新计算 retention anchor
- **AND** `expires_at_utc` 从新的 UTC anchor 加 `retention_days × 24 hours` 计算，不按无时区本地文本比较
- **AND** 不使用创建时间、首次导出时间或文件 mtime 替代这些事实

#### Scenario: 缺失或异常时间事实 fail closed

- **WHEN** case mutation time、`publication_verified_at`、verified Word artifact 时间缺失，或任一 timestamp 无时区/超过可信 UTC 5 分钟
- **THEN** 系统将 anchor 标记为 unknown
- **AND** preview 返回 `RETENTION_*_MISSING`、`RETENTION_PUBLICATION_TIME_MISSING`、`RETENTION_TIME_INVALID` 或 `RETENTION_TIME_IN_FUTURE` 稳定 blocker
- **AND** 案件不进入自动清理候选

### Requirement: REQ-RET-003: 自动清理资格必须同时满足保护条件

自动或策略驱动的案件记录清理 MUST 仅在以下条件全部满足时执行：案件处于允许清理的终态；不存在 queued、running、cancel-requested、interrupted、retryable 或恢复中的任务；不存在有效编辑租约；不存在未完成 publication、archive retry 或 Word export；RAR/Manifest/MD5/Word 正式输出集合完整且验证通过；案件不是尚未导出或导出失败待处理状态；所有必要 publication 已完成受控 revalidation 且有合法非空 `publication_verified_at`；retention 已到期；deployment、case、task 和资产 ownership 可证明；数据库事实与文件状态一致；不存在 active cleanup run；不存在 active/recovery/referenced snapshot，且 snapshot ownership、marker/sealed 状态和文件状态一致。状态不明、Manifest 不一致、authority 缺失、ownership 不明、未来时间、publication revalidation 未完成/失败、snapshot 活跃/恢复引用/ownership 不明/文件删除失败 MUST fail closed 并跳过，并使用 `RETENTION_SNAPSHOT_ACTIVE`、`RETENTION_SNAPSHOT_RECOVERY_REFERENCED`、`RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN` 或 `CLEANUP_SNAPSHOT_DELETE_FAILED` 等稳定 code。Cancelled、failed、interrupted、failed_retryable、从未成功正式输出的案件默认不得由定时 Coordinator 自动删除。

#### Scenario: 合格案件进入 enforce 候选

- **WHEN** 案件处于允许终态、正式 RAR/Manifest/MD5/Word 均完整且 verified、anchor 已到期，且任务、租约、恢复、publication、ownership、文件和 cleanup claim 检查均通过
- **THEN** `enforce` Coordinator 可以创建该案件的 cleanup run
- **AND** run 仍须在执行各阶段重新校验 revision、authority 和文件一致性

#### Scenario: 活跃、未导出或失败待重试案件被跳过

- **WHEN** 案件存在活动任务/租约/恢复、未完成 publication、publication revalidation 未完成或失败、未验证 Word、active/recovery/referenced snapshot、snapshot ownership 未知、snapshot 文件删除失败、failed_retryable、interrupted、未导出或状态未知
- **THEN** Scheduler 将案件标记为 skipped/blocked 并返回稳定 reason code
- **AND** 不删除任何案件记录或正式文件

### Requirement: REQ-RET-004: cleanup preview 必须确定性且是安全投影

系统 MUST 提供 preview 或等价 dry-run 语义，返回候选案件、不合格案件及稳定原因码、拟清理数据类别、明确保留的正式产物类别、retention anchor、到期判断、任务/租约/恢复/冲突摘要、policy revision、case revision 和 digest。preview MUST 稳定排序，MUST NOT 返回绝对路径、数据库表名、owner token、lease、fence、attempt、context 或原始敏感文件名；preview 与 Coordinator 执行 MUST 使用同一版本化资格规则。

#### Scenario: Preview 展示候选和保留边界

- **WHEN** 客户端查询 deployment 的 retention preview
- **THEN** 每个案件返回 candidate/blocked/skipped 状态、稳定 blocker、anchor/due、计划清理类别和保留的 RAR/Manifest/MD5/Word 类别
- **AND** 预览结果带有 policy/case revision 或 digest，可用于检测陈旧结果

#### Scenario: Preview 不泄露内部路径或身份

- **WHEN** preview 包含 work files、staging、snapshot、task 或 authority 信息
- **THEN** 响应只返回安全摘要和稳定 opaque identity
- **AND** 不返回路径、表名、token、lease/fence/attempt/context 或可恢复的原始工作 payload

### Requirement: REQ-RET-005: Coordinator 执行时二次校验和清理白名单

真实自动清理 MUST 只由 `enforce` deployment Coordinator 调用，客户端不得直接请求 retention 逐案件执行、提交路径、文件列表或删除类别。Coordinator MUST 在 claim 前、文件删除前、SQLite records 清理事务前和标记 succeeded 前重新校验 case revision、policy revision、任务、租约、retry/recovery、publication revalidation、Word artifact、authority、ownership、anchor/due、deployment owner、snapshot 状态和文件集合。执行只允许 design 明确的案件工作数据白名单；`archive_input_snapshots` 是 work-only `DELETE`，snapshot 文件和 row MUST 在 source 删除/compact 前处理，v11 不得将其 `source_id` 改为 nullable 或保留 snapshot tombstone row；正式 RAR/分卷、Manifest、MD5、Word、publication generation、现有 publication authority 和 formal Word artifact MUST NOT 被自动 retention 清理删除。正式引用的 attempt/intent/fence 只能保留最小 source tombstone FK，非正式 source row 和 `asset_references` 才能按矩阵删除。显式工作台 DELETE 不属于本自动清理流程。

#### Scenario: 旧 preview 或陈旧 claim 被拒绝

- **WHEN** preview 后案件 revision、policy revision、任务、租约、publication、Word artifact、authority 或 ownership 发生变化
- **THEN** Coordinator 拒绝 claim 或执行并返回 `stale`/`conflict` blocker
- **AND** 不执行部分未知范围的删除

#### Scenario: 执行只清理白名单工作数据

- **WHEN** Coordinator 通过所有二次校验并执行清理
- **THEN** 只处理已证明 ownership 的草稿、来源工作投影、`asset_references`、终态普通任务、snapshot/staging/cache/temp 等白名单类别；snapshot leaf 文件先删除并验证，records transaction 再删除 `archive_input_snapshots` row，之后才允许处理 source row
- **AND** case tombstone、publication facts、正式 RAR/Manifest/MD5/Word、formal Word artifact 和审计事实保持可识别、可验证和可门控

### Requirement: REQ-RET-006: 清理状态、幂等和部分失败必须持久化

系统 MUST 为每个 cleanup run 持久化 run identity、deployment/case、policy/case revision、claim/lease/fence、phase、文件步骤结果、snapshot 删除结果、retry、稳定 error/result 和 timezone-aware UTC timestamps。成功状态机为 `planned → claimed → preflighted → work_files_cleaned → records_cleaned → verified → succeeded`；非成功状态至少包括 `blocked`、`stale`、`cancelled`、`interrupted`、`partial_failure`、`failed_retryable` 和 `failed_terminal`。同一 deployment/case 不得存在两个 active run；重复请求或重复恢复 MUST 返回同一安全结果。文件、snapshot row、数据库和最终 authority 校验的部分成功 MUST 显式记录，不得伪装为 succeeded，也不得转化为自动正式产物删除。

#### Scenario: 重复恢复返回同一结果

- **WHEN** 同一案件同一 revision 已存在进行中或已成功 cleanup run，Scheduler 或恢复 Coordinator 再次处理
- **THEN** 系统返回现有 run 的安全状态或幂等结果
- **AND** 不创建竞争性第二个 active run

#### Scenario: 文件或数据库步骤部分失败

- **WHEN** snapshot 文件删除、snapshot row 删除、SQLite records transaction 或最终 authority 校验任一步骤失败
- **THEN** 系统记录已经完成的 phase 和稳定 `partial_failure`/`failed_retryable`/`failed_terminal` 结果
- **AND** 不标记 succeeded，不删除正式产物，并保留可安全恢复的 durable facts

### Requirement: REQ-RET-007: 取消、互斥和重启恢复只处理受控清理

cleanup active 时，autosave、新 parse/archive/cleanup task、archive retry/recovery、publication 创建/更新、Word export 和新 edit lease MUST 通过稳定 conflict 被拒绝；反向条件下 cleanup claim MUST 失败。取消和停止 MUST 等待受控进程及本实例 owned 工作资源进入可识别状态；有界时间内无法收尾时 MUST 转为 `interrupted` 或 `partial_failure`。启动恢复 MUST 只接管本 deployment、owner/lease/fence、case revision、policy revision 和 publication/Word authority 仍匹配的未完成 run，不提供备份 undelete。

#### Scenario: 并发工作流阻止陈旧清理

- **WHEN** cleanup active 时发生 autosave、archive retry、publication update 或 Word export，或 cleanup claim 期间已有这些操作
- **THEN** 新操作或 cleanup claim 返回稳定 conflict/stale
- **AND** cleanup 不覆盖新 revision，不使 verified publication 降级

#### Scenario: 重启后恢复本 deployment 的未完成 run

- **WHEN** 进程在任一 durable cleanup phase 后退出并重新启动
- **THEN** Coordinator 从 SQLite 读取最后阶段、owner、lease/fence、已完成文件步骤、revision 和 authority
- **AND** 只继续或安全重试匹配的 run，其他 deployment/owner 或不一致 authority 的 run 保持 interrupted/blocked

### Requirement: REQ-RET-008: 自动调度不得被普通 API 绕过

Scheduler MUST 使用 deployment policy 的 `disabled`、`preview_only`、`enforce` 模式和固定的周期/batch/单 coordinator claim 规则。canonical 配置名 MUST 为 `BIJI_CASE_RETENTION_MODE`、`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和 `BIJI_CASE_RETENTION_BATCH_SIZE`；这些配置只能由 deployment bootstrap/运维路径写入 durable policy，普通 API 不得修改。旧 `workbench.successful_case_retention_days` 仅在 v10→v11 首次创建当前 deployment policy row 且新 DAYS 缺失时提供 days，合法新 DAYS 优先，非法旧值使用 30 并记录诊断，policy row 创建后 Coordinator 不得直接读取旧键，旧键不得设置 mode 或启用 enforce。`disabled` 不扫描新候选，`preview_only` 只计算 preview，`enforce` 才允许 Coordinator 执行；未完成必要 publication revalidation 的案件不得进入 enforce；默认周期为 24 小时，最小 1 小时，默认 batch size 为 20，空扫描不得忙轮询，停止 grace 为 30 秒。公共 UI/API 本期只提供 retention status、blocker、preview、run status/progress/failure/recovery 和正式产物保护查询，不提供 retention-specific 普通用户 execute/delete/force-delete/cancel 合同；显式工作台 DELETE 由 `case-workbench-delete` 变更单独定义。

#### Scenario: Scheduler 跳过不确定案件并遵守 mode

- **WHEN** Scheduler 运行在 `disabled`、`preview_only` 或 `enforce`，且扫描到 authority、文件一致性、ownership、policy 或 claim 无法确定的案件
- **THEN** `disabled` 不创建新执行 run，`preview_only` 只返回 blocker，`enforce` 跳过该案件
- **AND** 不因 mode 或空扫描而绕过保护或忙轮询

#### Scenario: 公共请求不能 force delete

- **WHEN** 客户端提交 retention 逐案件执行、force-delete、路径、表名、文件列表或正式产物删除意图
- **THEN** API 拒绝请求并返回安全错误
- **AND** 不部分执行自动 retention 记录清理，自动真实清理仍只由受控 `enforce` Coordinator 负责
