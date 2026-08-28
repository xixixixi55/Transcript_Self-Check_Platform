# OpenSpec 差异：data-model

## ADDED Requirements

### Requirement: REQ-DATA-RET-001: v11 durable 模型保留清理和正式事实

若本 change 新增 retention、cleanup、Word artifact、tombstone 或持久化字段，数据模型 MUST 从当前 v10 单调升级为正式 v11。v11 MUST 持久化 deployment policy、case retention record、cleanup run/claim/phase/result、formal Word artifact、case shell tombstone 字段、`archive_publish_intents.publication_verified_at`、source tombstone/FK 约束、`archive_input_snapshots.source_id` work-only DELETE 边界、`asset_references` 清理边界以及必要的 task/publication/审计关联。`archive_input_snapshots` 不是正式 authority，snapshot 文件和 row MUST 在 source 删除/compact 前安全处理，v11 不得将其 source FK 改为 nullable 或保留 snapshot tombstone row。RAR/Manifest publication authority MUST 继续由现有 `archive_publish_intents`、fences、formal assets 和 publication durable facts 提供，不得创建竞争性的 `formal_artifact_authority` RAR/Manifest 表。关键状态 MUST NOT 只存在于内存、日志或临时 JSON。

#### Scenario: 进程重启后恢复清理事实

- **WHEN** 进程在 cleanup run 的文件步骤或数据库步骤中退出
- **THEN** 重启后的 Coordinator 可以从 SQLite v11 识别最后 phase、owner、claim/lease/fence、revision、已完成步骤、policy revision 和正式 publication/Word authority
- **AND** 不依赖 runtime context 或临时 JSON 决定是否继续

#### Scenario: 清理后保留最小案件和正式事实

- **WHEN** 合格 cleanup run 完成工作记录删除/compact
- **THEN** SQLite 仍能识别 deployment、case tombstone、retention result、publication/generation、Manifest/MD5/RAR authority、Word artifact 和审计锚点
- **AND** case shell 不包含完整报告、原始路径或可编辑工作 payload

### Requirement: REQ-DATA-RET-002: v10→v11 migration 必须事务化且可回滚

schema MUST 从 v10 升级到正式版本 11；migration MUST 在单个 SQLite transaction 中创建/扩展 retention policy、retention record、cleanup run、formal Word artifact、`publication_verified_at`、source tombstone、nullable shell work references、`archive_input_snapshots.source_id` work-only NOT NULL FK 和 task 最小字段，并处理 `asset_references`。migration MUST 保持 `foreign_keys=ON`，在提交前执行 `foreign_key_check`、无遗留 snapshot FK 和 schema validation；失败 MUST 整体回滚且不得留下部分 schema；重复启动 MUST 幂等；升级前 MUST 成组备份 SQLite、正式 RAR/Manifest/MD5/Word、approved template、受控 assets 和 authority/audit；旧版本应用 MUST NOT 直接打开 v11；Git 回退 MUST NOT 被当作数据回滚，数据回滚只能使用匹配备份。所有历史 `publication_verified_at` 初始为 NULL，不得从 `updated_at`、mtime、index 或下载记录 backfill；migration 后的受控 revalidation 失败 MUST 保持 NULL 并阻止对应案件 enforce。升级事务 MUST 默认 policy mode 为 disabled，不得批量删除历史案件。

#### Scenario: migration 成功后服务使用 v11

- **WHEN** v10 database 完成 migration 并通过 schema validation
- **THEN** service 使用 v11 durable policy、retention、cleanup run 和 Word artifact facts
- **AND** 既有 publication intent/fence/asset/Manifest authority 保持可读
- **AND** cleanup policy 默认不在 migration transaction 中批量删除案件

#### Scenario: migration 失败不留下半成品

- **WHEN** 新表、字段、唯一约束、索引、FK、source tombstone table rebuild、`publication_verified_at` backfill 或 timezone-aware timestamp 校验任一步骤失败
- **THEN** SQLite transaction 回滚到可恢复的 v10 状态
- **AND** 应用不以“部分成功”状态继续 cleanup
- **AND** 旧应用对已升级 v11 database 明确拒绝打开

### Requirement: REQ-DATA-RET-003: 表级矩阵、ownership 和 CAS 保护正式事实

数据模型 MUST 按 design 中冻结的表级 KEEP/COMPACT/DELETE/DERIVED/NEW 矩阵执行：`case_shells` 保留最小 cleaned tombstone；`case_drafts`、`asset_references` 和 path-bearing source work projection 仅在正式 authority/Word verified 后按白名单删除；`archive_input_snapshots` 仅为 work/recovery 记录，必须先删除受控 snapshot 文件再在 records transaction 中删除 row，且其 `source_id` FK 不得改为 nullable；被正式 attempt/intent/fence 引用的 source row 只 compact 为最小 tombstone 并继续满足 FK；普通任务可在无引用终态 compact/delete；正式 publication 关联的 task/attempt/intent/fence/asset/Word facts 保留；Manifest index 只可重建。清理 MUST 在 `foreign_keys=ON` 下按依赖顺序执行：先校验 claim/互斥和 snapshot 文件阶段，再删除 snapshot rows、compact 保留 facts、删除白名单 work rows/drafts、处理 source、compact shell、更新 run/audit、执行 FK/authority 后置验证并提交；不得关闭外键或无条件级联删除 shell。cleanup claim、case revision、policy revision、lease/fence、deployment ownership 和正式 generation 的不一致 MUST 使操作被拒绝或进入可恢复失败状态；所有 timestamp MUST 是 timezone-aware UTC。

#### Scenario: 外键或正式引用拒绝危险删除

- **WHEN** 白名单删除仍被正式 publication、Word artifact、generation、恢复、下载/Manifest 验证、活动任务或 snapshot source FK 引用
- **THEN** cleanup transaction 拒绝或回滚危险删除
- **AND** case shell、publication authority、formal assets、Word artifact 和正式 rows 不被级联删除
- **AND** cleanup result 记录稳定 blocker

#### Scenario: 陈旧 owner 不能提交清理

- **WHEN** cleanup worker 使用旧 case/policy revision、旧 lease/fence、不同 deployment owner 或不匹配 claim 提交记录清理
- **THEN** SQLite CAS 拒绝提交
- **AND** 既有清理结果、tombstone revision 和正式 authority 不被覆盖、降级或删除
