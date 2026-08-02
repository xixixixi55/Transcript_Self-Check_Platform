# Design: 案件记录保留与正式产物保护

## Planning Status

- 状态：`Spec frozen / Planning Review passed`。
- Review：`Phase 5 Final Spec Freeze Review`。
- 基线：`8d6800417deec09003c0a304340b8ba8c7037a3f`。
- 结果：`PASS`。C-01、C-02、C-03 及 H-01–H-05 全部关闭，无 Critical、High 或阻断性 Medium。
- 审查范围：proposal、design、tasks、4 组 delta specs；v10 schema/source/snapshot/publication/Word 事实；living specs；相关 active changes 的直接冲突。
- 证据：change strict、living specs strict、`verify:docs:strict`、`git diff --check` 和 OpenSpec status 全部通过。
- 时间合同：durable 时间、比较、CAS、审计和 retention 计算使用带时区 UTC；API 返回带时区 ISO 8601；界面和人工验收按 `Asia/Shanghai` 展示；默认 30 天按连续 720 小时计算。
- 规划结论：允许提交 Phase 5 立项包，Planning Review 到此终止。PASS 只批准规划基线，不表示实现完成；Phase 5A 开始前必须先执行 active change/schema overlap gate 和当前 v10 事实复核，不得绕过 tasks 批量实现。

## Context

Phase 1–4 已把案件工作台和正式归档从页面内存迁移到可恢复的单机持久化模型。当前 SQLite schema 为 v10；案件包含 CaseShell、CaseDraft、SourceRecord、TaskRecord、编辑租约和 revision；归档包含 sealed input snapshot、ArchiveAttempt、ArchivePlan、publish intent/fence、publication generation、Manifest/index、RAR/分卷、Word 和安全下载/复用门控。现有 Scheduler/Worker/Coordinator 已具备 ownership、lease、CAS、取消、重试、启动恢复和有界停止。

当前的 `archive_publish_intents`、`archive_publish_fences`、正式 `archive_assets` 和 publication durable facts 是正式 RAR/Manifest/MD5 的事实来源；`.archive-manifest-index.json` 是可重建投影。现有 `/records/*` 的部分 Manifest/Word 行为仍依赖 `archive_context_id`、进程内 runtime store 或请求中的 report，因此不能在删除 `case_draft.report_json` 后作为 cleaned case 的唯一访问入口。

本 design 冻结：清理案件工作数据不等于删除正式产物；正式 publication authority 不建立第二套竞争事实源；正式 Word 通过新增 durable artifact 事实独立保留；清理后的公共访问使用稳定的 `case_id`、`publication_id` 和 `word_artifact_id`。

## Goals / Non-Goals

### Goals

- 只清理明确归属于目标案件、且不再被运行流程需要的工作数据。
- 保持现有 publication durable facts 为 RAR/Manifest/MD5 的唯一权威。
- 让清理后的 cleaned tombstone 仍可安全列出、验证和访问正式 RAR/Manifest/MD5/Word。
- 把保留资格、清理阶段、claim、失败、恢复和审计写入 SQLite durable state。
- 在 v10→v11 migration、Windows 文件系统和现有 archive/Word/autosave 并发边界上形成可执行合同。

### Non-Goals

- 不提供任何正式 RAR、分卷、Manifest、MD5、Word、publication generation 或正式 publication authority 的删除 API。
- 不删除原始授权来源目录，不使用目录名、文件名、索引缺失或路径相似性推断 ownership。
- 不实现多实例共享 SQLite/输出根、多节点、高可用、远程数据库或自动 undelete。
- 不让 Canonical 进入正式链路，不恢复 Shadow，不处理 TD-3 至 TD-6。

## Decisions

### 1. 一个业务 change，按安全依赖分阶段

本 change 覆盖 T020–T025，因为保留策略、表级矩阵、正式产物访问、后端清理、公共投影、工作台和验收 gate 共同定义同一条安全边界。实施顺序为：5A 合同/重叠 → 5B v11/model → 5C 后端安全核心 → 5D 公共查询与 Legacy 边界 → 5E 工作台 → 5F 文档/验收 → 5G Review/archive。

### 2. 身份、deployment 和 ownership

- 数据库沿用仓库已有 `deployment_instance_id` 字段名表达 deployment identity；公共语义称为 `deployment_id`。
- cleanup 的范围由 durable `(deployment_id, case_id)`、case revision、任务/attempt/publication/Word 关联和受控根 ownership 共同证明。
- 客户端只能提交 opaque `case_id`、preview revision/digest 或查询用的 `publication_id`/`word_artifact_id`；不得提交路径、表名、文件列表、output root、attempt、context、lease、fence 或 token。
- 不同 deployment 不共享 retention policy、anchor、cleanup state、claim 或正式资产查询结果。

### 3. 清理后的正式产物访问模型

#### 3.1 唯一 authority 关系

“Formal artifact authority” 是一个能力边界名称，不是新增的 RAR/Manifest 平行权威表。

- RAR、分卷、Manifest、MD5、publication generation 的唯一 durable authority 继续是现有 `archive_publish_intents` 及其 publication durable facts。
- `archive_publish_fences` 继续承担正式发布 CAS/fence 证明；Phase 5 不重新定义 Phase 1–4 fence 合同。
- 正式 `archive_assets` 继续记录已发布文件集合和受控 asset facts；没有 FK 的逻辑 ownership 不得依靠 cascade 推断。
- `.archive-manifest-index.json` 继续是可重建、fail-closed 的派生投影，不是删除资格、publication authority 或正式产物存在性的唯一依据。
- 新增的 durable `formal_word_artifacts` 只记录正式 Word artifact；它不替代 RAR/Manifest authority，也不保存完整 `report_json`。
- `archive_publish_intents.publication_verified_at` 是既有 publication durable fact 的不可变验证时间字段；它不创建新的 authority，且只有在该 intent 的 publication 文件集合、Manifest、MD5 和 RAR 完整性验证通过并提交 `phase='verified'` 时写入。
- case shell 的 cleaned tombstone 只保留最小案件身份、保留状态和正式身份关联，不成为第二案件事实源。

如需 artifact catalog/read model，只能由上述 durable facts 重建；catalog 缺失不否定已有 authority，但 catalog 与 durable facts 不一致时公共访问必须 fail-closed。

#### 3.2 稳定公共身份和行为

清理后固定以下身份：

| 身份 | 语义 | 清理后公共行为 |
|---|---|---|
| `case_id` | 保留的案件 tombstone identity | 列出该案件仍保留的正式 RAR/Manifest/MD5/Word 安全投影和 retention 状态 |
| `publication_id` | 正式 RAR/Manifest/MD5 publication identity | 验证 Manifest、文件集合摘要和受控正式 RAR/分卷下载/复用 |
| `word_artifact_id` | 正式 Word 文件 identity | 验证来源 publication、摘要/大小并下载正式 Word |

清理后的访问不得依赖 `archive_context_id`、进程内 runtime store、TTL context、已删除 `case_draft.report_json`、普通任务 payload、派生 JSON index 或客户端路径。现有 task/context 路径可以继续服务未清理案件的兼容行为，但不得成为 cleaned case 的唯一正式入口。

#### 3.3 正式 Word durable artifact

成功 Word 导出必须在清理功能启用前完成以下 durable 链路：最终 Word 文件写入受控正式输出根，并在 SQLite 的 `formal_word_artifacts` 记录以下字段：

- `deployment_instance_id`、`case_id`、`publication_id`；
- 唯一 `word_artifact_id`；
- 文件摘要、大小、受控内部相对路径；
- 生成时间、验证时间和状态；
- 来源 Manifest digest；
- 模板 identity/version；
- 最小审计关联。

正式 Word 只有在记录存在、物理文件存在、摘要/大小匹配且来源 publication 仍为有效 verified authority 时才可下载。Word 记录和物理正式文件不受案件工作记录清理影响，不提供 Word 删除 API。不存在 durable Word 事实时，案件不得进入自动清理候选，`enforce` 也不得绕过该保护。

### 4. v10 表级 KEEP/COMPACT/DELETE/DERIVED/NEW 矩阵

下面的矩阵是 Phase 5 实现必须遵守的逐表合同。`COMPACT` 只能删除明确列出的工作字段；不得用“终态”或“案件相关”作为泛化删除条件。

| 表/记录类别 | 操作 | 精确保留或删除内容 | 资格/引用条件 | 顺序、失败恢复和验证 |
|---|---|---|---|---|
| `case_shells` | `COMPACT/KEEP TOMBSTONE` | v11 增加/保留 `deployment_instance_id`、`case_id`、`record_cleaned` lifecycle、tombstone/cleanup revision、retention state、cleaned timestamp、last meaningful mutation、最小安全标题/摘要和正式身份关联；清空可编辑描述、source/path/task 工作引用 | 所有正式 authority、Word artifact 和 cleanup result 已 durable；无 active lease/task/recovery | 最后处理 shell；SQLite 事务内单调增加 tombstone revision；查询确认不可编辑且可按 case_id 找到正式身份 |
| `case_drafts` | `DELETE` | 删除完整 `report_json`、field states、草稿模板选择、草稿 asset refs 和其他可编辑 payload | publication verified、Word artifact verified、无 active lease/recovery、case retention claim 有效 | 先清除依赖引用再删除；事务失败整体回滚；查询确认 cleaned case 无可编辑草稿 |
| `source_records` 和 source/work projections | `DELETE/COMPACT` | 没有保留正式引用的 source row `DELETE`；被正式 `archive_attempts`/`archive_publish_intents`/`archive_publish_fences` 引用的 row `COMPACT/KEEP SOURCE TOMBSTONE`，只保留 `source_id`、`deployment_instance_id`、`case_id`、tombstone 状态、revision 和时间；`internal_path`、allowed root、allowed root id、metadata、fingerprint、原始 source type、task 绑定全部清空为 NULL/安全 tombstone 值；原始授权来源文件绝不删除 | 正式 FK 只指向最小 source tombstone；publication authority 不读取 source row，正式 fingerprint 只来自 publication durable facts；无恢复/snapshot/非正式任务引用的 row 才可 DELETE | 先处理 snapshot/context/非正式引用和 owned files，再删除无正式引用 row；正式引用 row 只 compact；`foreign_key_check`、authority/Manifest 校验和敏感字段断言通过 |
| 普通 `task_records` | `DELETE/COMPACT` | 解析、编辑、预览等终态工作任务可删除或 compact；清除大型 counters/process binding/path payload | 终态、无 recovery/audit/publication/Word 引用 | 在 draft/source 清理前处理；失败回滚；任务历史只保留安全摘要 |
| 正式关联 `task_records` | `COMPACT/KEEP MINIMUM` | 保留 task identity、case/deployment、终态、finished time、publication/word artifact 关联和必要审计锚点；删除结果 payload、路径和非必要工作字段 | 正式 publication 或 Word artifact 仍引用；不得只因终态删除 | 在 attempt/intent 处理前确定引用；重启和正式下载不依赖大型 task payload |
| `edit_leases` 和 revision | `KEEP UNTIL RELEASE/COMPACT` | 有效 lease 保留；过期 lease 按既有失效合同处理；保留预期 case revision 和 cleanup revision | 有效 lease 阻止 claim；cleanup active 阻止新 lease/autosave | claim 前和 DB 清理前 CAS；cleaned 后 tombstone revision 单调递增 |
| `archive_input_snapshots`、`archive_context_bindings`、`archive_plans` | `DELETE` | `archive_input_snapshots` 是 work-only/recovery-only 记录，不是 RAR、Manifest、MD5 或 Word authority；删除 snapshot manifest、context binding、staging locator、plan payload，清理完成后不保留 snapshot row 或 snapshot 文件 | 不存在 queued/running/cancel-requested/interrupted/retryable 或恢复中的 attempt；不再被 archive retry/recovery/Manifest 生成或执行流程引用；deployment/case/task/attempt ownership、marker/sealed 状态和 durable row 一致；snapshot 文件删除成功；任一不满足则使用稳定 blocker 并跳过 | 先删除并验证受控 snapshot leaf container，再在 records-cleaned SQLite transaction 中删除 snapshot row；确认不存在剩余 snapshot FK 后才可删除/compact source；数据库失败整体回滚，文件阶段保持 `work_files_cleaned`/`failed_retryable`，不删除正式输出 |
| `archive_attempts` | `COMPACT/KEEP` 或受限 `DELETE` | 正式 publication 引用的 attempt 保留 attempt/task/publication identity、`source_id` 历史引用、终态、必要摘要和审计锚点；未发布失败/取消 attempt 才可删除其 staging/snapshot/路径等明细 | 正式引用行永不删，且其 `source_id` 必须指向最小 source tombstone；非正式行必须终态、无 retry/recovery 引用、文件已处理且失败结果已审计 | 先检查 intent/fence/recovery 引用；不能仅因终态删除；重启/Manifest 验证后复核引用；FK 检查通过 |
| `archive_publish_intents` | `KEEP` | 已提交或正式发布 intent、publication identity、generation、Manifest/digest/file set、状态、`publication_verified_at` 和时间事实保持完整 | 正式 publication authority 永久在本 change 保护范围内；`source_id` 只保持到最小 source tombstone 的历史 FK，不作为 authority 查询入口；无 authority 的非正式 intent 仅在恢复合同明确终止且已审计时受限处理 | 任何正式 authority 缺失或冲突即阻断；verified transition 与 `publication_verified_at` 在同一事务提交；SQLite 查询可直接重建 Manifest authority |
| `archive_publish_fences` | `KEEP` 或受限 `COMPACT` | 正式 publication 的终态 fence/CAS 证明保留；活跃、恢复、并发相关 fence 不清理；正式 fence 的 `source_id` 只指向最小 source tombstone | 只有明确无 publication、无 recovery、无并发用途的失效 fence 可 compact；正式 fence 不得因 source work 清理而失效 | 不重新定义 Phase 1–4 CAS；cleanup 与 active fence 冲突时 stale/blocked；FK 检查和 publication generation 验证通过 |
| `archive_assets` | 正式行 `KEEP`；工作行受限 `DELETE` | RAR/Manifest/MD5/Word 对应正式 asset 保留；snapshot/staging/temp 只删除 owned 非正式 asset | 表无 FK；必须证明 deployment/case/task/attempt ownership、受控根、状态和无 recovery 引用 | 不依靠 cascade；只删除 owned leaf container；物理文件失败不得进入 records_cleaned |
| `.archive-manifest-index.json` | `DERIVED/REBUILDABLE` | 不作为 authority、资格或删除依据；缺失/损坏可从 SQLite intent/publication facts 重建 | durable facts 仍可读；不一致时拒绝访问并记录诊断 | 清理前后可重建并比对 digest；孤立文件不能生成可信记录 |
| `audit_events` | `KEEP` | Phase 5 不删除既有审计；新增 preview、claim、跳过、执行、失败、取消、恢复、完成和 authority 校验事件；payload 最小化 | 审计事实无法闭合时阻断清理 | 审计写入与 cleanup result 同一 SQLite 事务或明确 partial failure；公共投影不泄露路径/安全身份 |
| `asset_references` | `DELETE` | 这是案件工作引用表；删除 case-linked work references、metadata 和 payload。若历史正式输出曾依赖该表，先把必要 identity/digest 回填到 `archive_assets` 或 `formal_word_artifacts`，然后该表不再作为正式 authority | 无 active task/recovery 引用，正式 authority/Word artifact 已完成 backfill 且不再读取该表；回填缺失时 fail-closed | 在 `case_drafts.asset_refs_json` 和工作 task 清理后删除；事务失败回滚；验证正式 asset/Word gate 不查询该表 |
| `shared_defaults`、`template_versions`、`template_approvals`、`deployment_owners`、`schema_migrations` | `KEEP/OUTSIDE CASE CLEANUP` | 这些是 deployment/global control 或模板治理事实，不属于案件工作记录；Phase 5 不删除、不 compact、不因 case retention 改写 | 不参与单案件清理资格；schema migration 只增加 Phase 5 对象和明确版本事实 | migration 前后行数/版本和 deployment scope 校验；cleanup 不触碰这些表 |
| `case_retention_policies` | `NEW` | deployment mode、retention days、`scan_interval_seconds`、`batch_size`、policy revision、activated/created/updated time | `(deployment_instance_id)` 唯一；不同 deployment 隔离 | v11 migration 创建为 disabled；无效配置禁止 enforce；启动读取 durable policy |
| `case_retention_records` | `NEW` | deployment/case、eligibility/state、三个 anchor 时间、`publication_verified_at` 来源摘要、anchor/due、blocker、policy/case revision、cleanup revision、timestamps | `(deployment_instance_id, case_id)` 唯一；缺失事实为 unknown/ineligible；record 是可重算 projection，不替代 intent/Word authority | 先写 retention record，再生成 preview/claim；重启可恢复同一事实；authority revision 变化时重算 |
| `case_cleanup_runs` | `NEW` | run identity、deployment/case、policy/case revision、owner/claim token、lease expiry、fence epoch、phase、retry、file result、error/result、timestamps | 同一 deployment/case 最多一个 active run；claim 使用 SQLite CAS | file/DB 非原子步骤以 phase/result 表示；不能把 partial failure 写成 succeeded |
| `formal_word_artifacts` | `NEW` | Word artifact identity、publication/case/deployment、relative path、digest、size、Manifest digest、template identity/version、generated/verified time、status | `word_artifact_id` 唯一；publication 必须是 verified authority | 成功导出后先持久化并验证；清理不触碰；下载再次验证物理文件和 publication |

#### 4.1 v10 source reference/FK 与 source tombstone 决策

当前 v10 的 source reference/FK 清单必须完整覆盖以下关系：

- `case_shells.source_id` 是必填的案件工作 source identity；v11 table rebuild 后允许为 NULL，cleaned shell 清空该工作引用。
- `archive_attempts.source_id`、`archive_publish_intents.source_id` 和 `archive_publish_fences.source_id` 是 `NOT NULL REFERENCES source_records(source_id)` 的正式历史 FK。
- `archive_input_snapshots.source_id` 是 `NOT NULL REFERENCES source_records(source_id)` 的工作快照 FK；它不是正式 publication authority，snapshot row 必须在 source 删除/compact 前删除，不改成 nullable，也不保留指向 source tombstone 的历史 snapshot row。
- `archive_context_bindings.source_id` 是工作 context 的逻辑引用，不得因没有 SQL FK 而跳过 ownership、recovery 和清理前引用检查。

不能在保留正式 rows 的同时直接删除其 source row。本 change 冻结以下 v11 方案：

- `case_shells.source_id` 和 `parse_task_id` 在 v11 table rebuild 后允许为 NULL；清理完成的 shell 清空工作引用，只保留 tombstone identity。
- `source_records` 在 v11 table rebuild 后允许敏感工作列为空，并增加明确的 source tombstone 状态。没有正式引用的 source row 删除；被正式 attempt/intent/fence 引用的 row 永久或至少在其正式引用生命周期内保留为最小 tombstone，只保留 `source_id`、`deployment_instance_id`、`case_id`、tombstone 状态、revision 和 UTC timestamps。
- 正式 `archive_attempts`、`archive_publish_intents`、`archive_publish_fences` 保持 `source_id` 外键，但该 FK 只表达历史身份完整性；正式 publication authority、Manifest 校验和下载门控不得读取 source tombstone 的路径、root、metadata 或 fingerprint。正式 fingerprint 必须已经写入 publication durable facts。
- `archive_input_snapshots` 必须先完成受控 snapshot leaf 文件删除和文件存在性验证，再在同一 records-cleaned 事务中删除 snapshot row；只有确认不存在 snapshot row 或其他 FK/逻辑引用后，source row 才能 DELETE 或 COMPACT。snapshot 相关 attempt 状态、recovery、ownership、marker/sealed 一致性或文件删除失败时分别返回 `RETENTION_SNAPSHOT_ACTIVE`、`RETENTION_SNAPSHOT_RECOVERY_REFERENCED`、`RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN` 或 `CLEANUP_SNAPSHOT_DELETE_FAILED`，不得进入 records cleanup。
- `archive_context_bindings`、`archive_plans` 和非正式 attempt/fence 引用必须在 source row 删除/compact 前处理；`asset_references` 先完成正式 asset/Word backfill，再删除，不得成为正式 authority。
- v10→v11 migration 在一个事务中完成上述 table rebuild、字段迁移、索引/唯一约束创建和安全 backfill；连接保持 `foreign_keys=ON`，提交前执行 `foreign_key_check` 和 schema validation。任何 FK、backfill 或校验失败都整体回滚，不使用无条件 cascade。

固定的清理顺序为：先完成 cleanup preflight、claim 和 owned 文件阶段；records-cleaned SQLite transaction 内再严格执行：

1. 校验 cleanup claim、policy revision、case revision、lease/fence 和互斥条件；
2. 确认 snapshot 文件阶段已成功且 snapshot row 不再被恢复流程使用；
3. 删除允许删除的 `archive_input_snapshots` rows；
4. compact 必须保留的 task、attempt 和 source facts；
5. 删除允许删除的普通 task、work projections 和 `asset_references`；
6. 删除 `case_drafts`；
7. 删除没有其他 FK/逻辑引用的 `source_records`；
8. 将仍被正式 attempt/intent/fence 引用的 source compact 为最小 tombstone；
9. compact `case_shells` 为 cleaned tombstone；
10. 更新 retention record、cleanup run 和 audit anchor；
11. 执行 `foreign_key_check`、无遗留 snapshot FK、publication authority、Word artifact authority 和 cleaned-case 可访问性后置验证；
12. 提交事务。

任一步数据库失败时整个 SQLite transaction 回滚；如果此前 snapshot/其他工作文件已经安全删除，cleanup run 保持 `work_files_cleaned` 或 `failed_retryable`，重启按 durable run facts 验证文件状态后恢复，不重新删除未知路径，也不触碰正式输出。

### 5. Retention anchor 和资格

#### 5.1 Anchor 的 durable 来源

```text
retention_anchor = max(
  case_last_meaningful_mutation_at,
  latest_verified_formal_publication_at,
  latest_successful_word_export_at
)
expires_at_utc = retention_anchor_utc + (retention_days × 24 hours)
```

- `case_last_meaningful_mutation_at` 是 v11 `case_retention_records` 的 durable 字段；以下操作更新它：报告内容修改、影响正式输入的案件字段修改、source 增删/替换、影响正式输出的模板选择或配置变化、影响正式输出的附件/资产变化、创建会改变正式结果的任务、对正式结果重新发起有效 retry。
- 页面打开、轮询、列表排序、纯展示偏好、只读 preview 和诊断读取不更新它。
- `latest_verified_formal_publication_at` 精确定义为目标 deployment/case 全部有效 publication 中最大的非空 `archive_publish_intents.publication_verified_at`。该字段 nullable，只能在同一 intent/generation 完成 publication 文件集合、Manifest digest、file inventory、MD5 和 RAR 完整性验证并将 `phase`/`publication_status` 提交为 durable succeeded/verified 的事务中通过 NULL-only CAS 写入；普通读取、下载和重复验证不更新时间，失败、取消、单纯 retry 请求和文件 mtime 不更新。真正重新发布必须创建新的 `publication_id`，由新 publication 获得自己的验证时间。
- `latest_successful_word_export_at` 只来自 `formal_word_artifacts.verified_at`；Word 重新导出且验证成功才更新；失败、下载时间和文件 mtime 不更新。
- 所有持久化、比较、CAS、审计及 retention 计算时间使用 timezone-aware UTC timestamp；SQLite 文本统一保存带 `Z` 的 UTC ISO 8601，读取后必须解析为 aware UTC，禁止无时区本地时间参与资格判断。公共 API 返回带时区的 ISO 8601 时间；前端、工作台、运维界面和人工验收统一转换为 `Asia/Shanghai` 展示。超过当前可信 UTC 时间 5 分钟以上为异常。
- Word、publication 或 meaningful mutation 成功后重新开始 retention 期限；尚未生成或尚未验证 Word 的案件永远不具备自动清理资格。

缺失或异常的稳定 blocker 至少包括：

- `RETENTION_CASE_MUTATION_TIME_MISSING`
- `RETENTION_PUBLICATION_MISSING`
- `RETENTION_PUBLICATION_UNVERIFIED`
- `RETENTION_PUBLICATION_TIME_MISSING`
- `RETENTION_WORD_ARTIFACT_MISSING`
- `RETENTION_WORD_ARTIFACT_UNVERIFIED`
- `RETENTION_TIME_INVALID`
- `RETENTION_TIME_IN_FUTURE`
- `RETENTION_NOT_EXPIRED`

v10→v11 migration 不安全回填 `publication_verified_at`，所有既有 publication 初始为 NULL；不得把普通 `updated_at`、文件 mtime、Manifest index 时间、下载时间或首次导出时间推断为验证时间。migration 后必须执行受控 publication revalidation：从 SQLite publish intent、Manifest digest、正式 file inventory 和正式文件读取并重新验证 Manifest、RAR/分卷、MD5 和摘要；全部通过后才通过 NULL-only CAS 写入验证时间，任一步失败保持 NULL 并记录 `RETENTION_PUBLICATION_UNVERIFIED` 或 `RETENTION_PUBLICATION_TIME_MISSING`。revalidation 不是重新发布，不改变原 publication identity，也不因重复 revalidation 延长 retention。`enforce` 不得清理仍有必要 publication 未完成 revalidation 或 `publication_verified_at` 为空的案件。

`publication_verified_at` 的写入条件必须同时绑定原 `publication_id`、当前 durable succeeded/verified 状态、publication fence、Manifest digest、file inventory、正式文件摘要和 deployment/case ownership；等价 CAS 只能允许 `NULL → verified_at_utc`。CAS 未命中时重新读取 durable fact：已有合法非空值保持不变，状态、authority、digest、inventory 或 ownership 不一致时 fail-closed。普通 publication 读取、下载、Manifest 重复校验和 Word 访问不得更新该字段。

默认保留 30 天，等于连续 720 小时；`expires_at_utc` 必须使用 UTC aware timestamp 加 `retention_days × 24 hours` 计算，不能按无时区本地文本比较。合法范围为 1–3650 天；禁用使用 policy mode，不使用 0、负数或其他魔法值。Cancelled、failed、interrupted、failed_retryable、从未成功正式输出或恢复中的案件默认不得由定时 Coordinator 自动删除。

#### 5.2 Eligibility predicate

自动候选必须同时满足：案件处于允许清理的终态；不存在 queued/running/cancel-requested/interrupted/retryable 或恢复中任务；不存在有效 edit lease；不存在未完成 publication；RAR/Manifest/MD5/Word 完整且验证通过；不属于未导出或导出失败待处理案件；retention 已到期；deployment/case/task/asset ownership 可证明；SQLite facts 与物理文件一致；没有 active cleanup run。状态不明、Manifest 不一致、authority/ownership 缺失或未来时间一律 fail-closed。

### 6. Preview、公共边界和无人工执行

Preview/dry-run 使用版本化 policy predicate，稳定按 case ID 排序，至少返回候选/跳过、稳定 blocker、计划清理类别、保留正式类别、anchor/due、任务/租约/恢复/冲突摘要、policy revision、case revision 和 digest。不得返回绝对路径、表名、token、lease、fence、attempt、context 或敏感原始文件名。

本期没有可靠的用户、角色或人员级认证授权模型，因此不提供公共逐案件清理执行 API、普通案件立即删除按钮、没有实际身份基础的人员级执行合同或 force-delete。公共 UI/API 只允许：

- retention 状态、资格和 blocker 查询；
- preview/dry-run；
- cleanup run 状态、进度、失败和恢复信息查询；
- 清理后按 `case_id` 查询正式产物安全投影；
- 按 `publication_id`/`word_artifact_id` 进入既有验证/下载门控。

真正删除只由 deployment policy 为 `enforce` 的 Coordinator 执行。客户端不提交路径、表名、删除类别或文件列表。若未来出现人员级人工执行需求，必须另建 Level 3 change。

### 7. Cleanup phase、claim 和并发

#### 7.1 Durable run identity and state

每个 `case_cleanup_runs` 至少绑定 `cleanup_run_id`、deployment/case、policy revision、plan/claim 时的 case revision、owner instance、claim token、lease expiry、fence epoch、current phase、retry count、file step result、result/error code 和 timestamps。同一 deployment/case 在任一时刻最多一个 active run，使用 SQLite partial unique index/CAS 保证。

成功状态机为：

```text
planned → claimed → preflighted → work_files_cleaned
        → records_cleaned → verified → succeeded
```

非成功状态至少包括 `blocked`、`stale`、`cancel_requested`、`cancelled`、`interrupted`、`partial_failure`、`failed_retryable`、`failed_terminal`。任何异常不得直接转为 `succeeded`。

#### 7.2 二次校验和互斥

Coordinator 在 claim 前、工作文件删除前、SQLite records 清理事务前和 succeeded 前重新校验：case revision、edit lease、任务状态、archive retry/recovery、未完成 publication、Word export、现有 intent/fence/asset authority、ownership、anchor/due、policy revision 和 deployment owner。

cleanup active 时，autosave、新 parse/archive/cleanup task、archive retry、Word export、publication 创建/更新和新 edit lease 必须通过稳定 conflict 被拒绝；反向条件下 cleanup claim 失败。实现使用 case revision + durable cleanup claim/CAS，不依赖进程内 mutex。已 verified publication 不得因 cleanup 恢复而降级。

#### 7.3 文件阶段、取消和恢复

文件删除先于 SQLite 工作记录清理。若文件已删除而 DB 事务未提交，保留数据库工作事实，状态为 `work_files_cleaned`/`partial_failure`/`failed_retryable`，重启从 durable phase 恢复，不重新删除未知路径。取消只停止后续候选并记录已完成安全步骤；不能在有界收尾前标记成功。SQLite records 清理必须单事务整体提交或回滚，正式产物始终不受影响。

### 8. Scheduler/Coordinator

策略表固定为 `case_retention_policies`，模式固定为：

- `disabled`：不扫描新候选，只恢复已有未完成 cleanup run；
- `preview_only`：按周期生成候选和 blocker，不执行删除；
- `enforce`：按同一 predicate 重新计算并只执行合格候选。

新安装和 v10→v11 升级默认为 `disabled`。策略至少有 `deployment_instance_id`、mode、`retention_days`、`scan_interval_seconds`、`batch_size`、policy revision、activated timestamp、created/updated timestamp。默认 `scan_interval_seconds=86400`，最小 `3600`；默认 `batch_size=20`，合法范围为 1–1000；retention days 合法范围为 1–3650。空扫描等待下一个周期，不忙轮询。

deployment 运维配置的 canonical names 固定为：

- `BIJI_CASE_RETENTION_MODE`：`disabled`、`preview_only` 或 `enforce`；
- `BIJI_CASE_RETENTION_DAYS`：1–3650，默认 30；
- `BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS`：不少于 3600，默认 86400；
- `BIJI_CASE_RETENTION_BATCH_SIZE`：1–1000，默认 20。

这些本机配置只由 deployment bootstrap/运维启动路径读取并写入 `case_retention_policies`；每次有效 mode 或参数变更必须在同一 durable transaction 中递增 policy revision 并记录 activated timestamp，公共 API 不得修改它们。新安装或 v10→v11 没有 canonical 配置时创建 `disabled` policy；已有 v11 policy 在没有新配置时保持不变。配置缺失、非法、deployment/data root 不一致或 version overlap 时 Coordinator 拒绝 enforce 并记录稳定诊断。

旧键 `workbench.successful_case_retention_days`（代码常量别名 `RETENTION_CONFIG_KEY`）的生命周期固定为 `deprecated migration compatibility input`：

- 仅在 v10→v11 首次创建当前 deployment 的 `case_retention_policies` row 时读取；新安装不读取旧键。
- 仅当新的 `BIJI_CASE_RETENTION_DAYS` 环境变量缺失时提供 days；合法的新环境变量始终优先；新环境变量存在但非法时按非法配置 fail-closed，不回退旧键。
- 旧键只能提供首次迁移的 days，不能设置 `disabled`/`preview_only`/`enforce`、scan interval、batch size 或 policy revision，也不能启用 enforce。
- 旧值存在但非法时 retention days 使用 30，mode 仍为 `disabled`，并记录稳定兼容性诊断；不得静默转换为其他天数。
- policy row 创建后 Coordinator、review、enforce 和后续启动不再直接读取旧键；环境变更必须通过校验后的 policy row 和新的 policy revision 生效。
- 本 change 不删除旧键；后续移除必须另建 change；retention policy 不写入 `case-shared-defaults`。

同一 deployment 只能有一个 active coordinator claim，绑定 deployment、instance owner、claim token、policy revision、lease expiry 和 fence/epoch，通过 SQLite durable CAS 获取/续租；lease 失效后才允许接管。停止时停止接受新 run，等待不可中断事务完成或回滚，文件阶段有界退出；shutdown grace 固定 30 秒，超时记为 interrupted/recoverable。非法 policy、deployment/data root 不一致或 version overlap 时禁止 enforce 并产生稳定诊断。

从 `disabled/preview_only` 切换 `enforce` 必须产生新的 policy revision；旧 preview 不构成执行授权。首次升级不把历史案件自动加入 enforce。

### 9. Schema v11 和 migration

正式冻结 `WORKBENCH_SCHEMA_VERSION = 11`。v11 最小 durable 模型为：

1. `case_retention_policies`：deployment 唯一、mode、`retention_days`、`scan_interval_seconds`、`batch_size`、policy revision、activated/created/updated time；canonical 运维配置名见第 8 节。
2. `case_retention_records`：deployment/case 唯一、eligibility/status、last meaningful mutation、latest verified publication（由目标案件全部有效 publication 中非空 intent 的 `publication_verified_at` 最大值派生）、latest verified Word、UTC anchor、`expires_at_utc`、blocker、policy/case/cleanup revision 和 timestamps；到期使用 `anchor_utc + retention_days × 24 hours`。
3. `case_cleanup_runs`：第 7 节的 run/claim/lease/fence/phase/result 字段；需要 active-run 唯一约束、recoverable phase 索引、lease expiry 索引和 deployment scan 索引。
4. `formal_word_artifacts`：第 3.3 节的 Word artifact 字段；`word_artifact_id` 唯一，支持 case/publication 查询。
5. `case_shells` 扩展：deployment identity、tombstone/cleanup revision、retention/cleanup state、cleaned timestamp、last meaningful mutation 和安全显示摘要；`source_id`/`parse_task_id` 在 v11 可为 NULL 并在 cleaned 状态清空，不创建重复案件身份源。
6. `source_records` 扩展：正式引用所需的最小 source tombstone 和 nullable 敏感工作列；正式引用的 `source_id` FK 保持到 tombstone，authority 不读取 tombstone 工作字段。`archive_input_snapshots.source_id` 保持 work-only `NOT NULL` FK 语义直到 snapshot row 被删除，不改为 nullable、不保留 snapshot tombstone row。
7. `archive_publish_intents` 扩展 nullable 的不可变 `publication_verified_at`；通过绑定 publication identity、durable succeeded/verified state、fence、digest、inventory 和 ownership 的 NULL-only CAS 写入；该字段是现有 publication authority 的组成事实，不是新表或新 authority。
8. `task_records` 的最小正式关联字段：publication/Word artifact identity、终态和验证时间；大型 payload/path/process binding 可 compact；`asset_references` 先完成正式事实 backfill 后删除。
9. `audit_events` 使用既有表记录 Phase 5 事件；`shared_defaults`、模板治理表、deployment owner 和 schema migration 表不受案件清理影响；不新增第二套 publication authority 表。

v10→v11 在单一 SQLite transaction 中完成，包含必要的 `case_shells`/`source_records` table rebuild、nullable/FK 约束、`archive_input_snapshots.source_id` work-only FK、`publication_verified_at`、retention 对象、唯一约束和索引；重复启动幂等。迁移连接保持 `foreign_keys=ON`，提交前执行 `foreign_key_check`、schema validation 和 source tombstone 敏感字段断言；任何失败整体回滚并保持旧 schema 可恢复。所有历史 `publication_verified_at` 初始为 NULL，不做不安全时间回填；迁移后受控 revalidation 成功才可通过 NULL-only CAS 写入，失败保持 NULL 并阻止对应案件进入 enforce。启动时旧应用必须拒绝 v11；升级前成组备份 SQLite、正式 RAR/Manifest/MD5/Word、approved template、受控 assets 和 authority/audit。Git 回退不等于数据回滚，必须使用匹配的 v10/正式资产备份恢复。实现前必须执行一次 active change schema-version overlap gate，当前未发现其他 active change 明确占用 v11。

### 10. Windows 文件安全和重试

工作文件候选必须位于明确 work/snapshot/staging/cache 根，与 durable deployment/case/task/attempt ownership 对应，并通过 canonical path、Windows 大小写不敏感的根比较、symlink/junction 拒绝、`..`/相对路径/UNC/设备路径拒绝。只删除 owned leaf container，不递归删除共享父目录，不触碰原始授权来源根或正式输出根。

稳定错误码至少包括：`CLEANUP_PATH_OUTSIDE_ALLOWED_ROOT`、`CLEANUP_OWNERSHIP_UNKNOWN`、`CLEANUP_SYMLINK_OR_JUNCTION_REJECTED`、`CLEANUP_FILE_IN_USE`、`CLEANUP_ACCESS_DENIED`、`CLEANUP_FILE_CHANGED`、`CLEANUP_FILE_DELETE_FAILED`。单次 run 对 transient 文件错误最多重试 3 次，采用有界退避（250ms、1000ms、2000ms）；仍失败转为 `failed_retryable`，不进入 `records_cleaned`。不得强杀非本实例/非本任务进程，不得因 ACL、杀毒软件或占用失败虚假记录完整清理。

### 11. API、工作台和 Legacy/Canonical/Shadow

公共 API 语义固定为 retention status、blocker、preview/dry-run、cleanup run status/progress/failure/recovery 和 cleaned case 的正式产物安全查询；具体 route 命名遵循现有 route 组织，但不能改变稳定身份语义。公共 DTO 只能有 case/publication/word artifact opaque IDs、状态、摘要、revision/digest 和稳定错误码。

所有公共时间字段返回带时区的 ISO 8601 UTC 值（例如 `2026-08-02T12:00:00Z`）；前端、工作台、deployment 运维界面和人工验收统一转换为 `Asia/Shanghai` 展示。客户端提交的 revision/preview/claim 时间若存在时必须带时区并先规范化为 UTC；无时区 timestamp 一律拒绝，不得参与 CAS、审计或 retention eligibility。

清理后：

- `case_id` 查询正式产物列表；
- `publication_id` 通过现有 intent/fence/Manifest/file integrity gate 验证和下载 RAR/Manifest/MD5；
- `word_artifact_id` 验证 Word artifact、来源 publication、摘要/大小后下载 Word；
- authority 或物理文件不一致时 fail-closed；
- 不暴露内部相对路径、attempt、context、lease、fence、token 或数据库表。

Legacy `/records/*` 仍是唯一正式输出兼容入口；未清理案件可保留 task/context 兼容路径，但 cleaned case 不依赖它。Canonical 不参与 retention、publication、下载或 Word gate；Shadow 保持暂停且不参与资格、成功、审计或正式保护。

### 12. 备份、恢复、容量和日志边界

备份必须成组保存 deployment-scoped SQLite、正式 RAR/Manifest/MD5/Word、approved template、受控 assets、policy 和 authority/audit。恢复使用匹配 deployment/schema/output root/template，恢复后重建并复核派生 index，拒绝孤立文件自动变可信。cleanup log 只记录稳定阶段、原因、数量、摘要和诊断，不记录路径/token/完整 payload；容量统计按 deployment、工作数据类别和正式保留类别分开。

## Active Change Dependency Matrix

| Active change | 文件/合同交集 | 实施先后和 gate |
|---|---|---|
| `case-shared-defaults` | SharedTypes/constants、`shared_defaults`、defaults API | retention policy 不混入六字段 defaults；若同时 migration 合并事务；Phase 5A 后才能实现 |
| `extensible-report-template-platform` | template、Manifest、Word、Legacy/Canonical/Shadow | Word artifact 记录模板 identity/version；保持 Legacy-only、Canonical 未启用、Shadow 暂停 |
| `report-parsing-cache-management` | parsing cache 和 cache cleanup | cache 只能是 work cache，不能成为 authority/资格；不得删除正式 output root |
| `large-report-preview-liveness` | archive context、preview、controller/routes | cleaned access 必须走 case/publication/word identity；runtime context 只作未清理兼容 |
| Word/template active changes | Word 输出和模板版本事实 | formal Word artifact durable record 是 `enforce` 前置条件；不修改模板合同 |
| 其他 active changes | parser、Legacy、上传、UI 局部文件 | 只登记依赖，不修改其他 change；发现 schema/API 直接冲突时阻止 5B/5D |

潜在文件交集本身不自动拒绝；公共 authority、Word durable fact、schema version、Legacy/Canonical/Shadow 边界若发生冲突，必须先完成对应 gate。

## Implementation Non-Negotiables

以下是实现时可选的内部类名、repository 文件名和 route 具体路径，但不得重新打开已冻结的业务语义：

- 不新增 RAR/Manifest 平行 authority；
- 不以 `archive_context_id` 或派生 index 作为 cleaned case 唯一入口；
- 不恢复公共人工执行/force-delete 合同；
- 不把字段/FK/版本/模式/周期/claim/互斥/错误码留给实现者猜测；
- 不在 Phase 5 修改 living specs、归档 change 或其他 active change。
