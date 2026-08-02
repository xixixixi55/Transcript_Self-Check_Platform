# Tasks: 案件记录保留与正式产物保护

> 除本条已记录的 Planning Review，以及下方明确标记为 Slice 5A-1 foundation 的已完成任务外，所有产品实现、测试、E2E、人工验收和后续 Review 任务保持未勾选。创建或修订本 change 不等于 Phase 5 产品能力已完成。
> 原任务 T020–T025 和 Phase 5 gate 通过任务编号保留追溯；本节的 Spec Freeze Remediation 不新增原任务编号。

## Spec Freeze Remediation（规划修订，不属于原 T020–T025 编号）

- [x] 固定 publication/Word/tombstone 的清理后稳定访问模型；
- [x] 固定 v10 表级 KEEP/COMPACT/DELETE/DERIVED/NEW 矩阵，包括 source tombstone/FK、`asset_references` 和 global control tables；
- [x] 固定 retention anchor 的 durable 来源、操作和 blocker code，包括 `publication_verified_at`、缺失时间和全链路 UTC timezone-aware 规则；
- [x] 移除公共人工删除执行合同，只保留 status/preview/run/protection 查询；
- [x] 固定 Scheduler mode、周期、batch、单 coordinator claim、canonical deployment 配置键和 shutdown；
- [x] 固定 cleanup 与 autosave/archive/retry/publication/Word 的互斥和 CAS；
- [x] 正式确定 schema v11 最小 durable 模型和 migration 边界；
- [x] 固定 Windows 文件根、ownership、错误码和重试合同；
- [x] 更新 proposal、design、delta requirements、依赖矩阵和本任务追溯；
- [x] 冻结 `archive_input_snapshots.source_id` 的 work-only DELETE、source FK 和恢复顺序；
- [x] 冻结 `publication_verified_at` 的 NULL-only CAS、v10 publication revalidation 和 enforce gate；
- [x] 冻结旧 retention key 的首次迁移读取、配置优先级、非法值和 policy row 创建后停读规则；
- [x] 冻结 `expires_at_utc = retention_anchor_utc + (retention_days × 24 hours)` 及 UTC/Asia/Shanghai 展示边界；
- [x] Phase 5 Final Spec Freeze Review（独立 Planning Review 复审）已通过。
  - Review result：`PASS`。
  - baseline：`8d6800417deec09003c0a304340b8ba8c7037a3f`。
  - 关闭项：C-02、H-01、H-03 最终关闭；C-01、C-03、H-02、H-04、H-05 及 Windows/Legacy-only/Canonical/Shadow/Word/`asset_references` 既有关闭项无回归。
  - 验证证据：change strict、living strict（`openspec validate --specs --strict --no-interactive`）、`verify:docs:strict`、`git diff --check` 和 OpenSpec status 通过。
  - 结论：允许提交 Phase 5 立项包；Planning Review 到此终止，不再增加新的 Spec Freeze Review。此项只批准规划基线，不表示产品实现完成。

除上述规划 Review gate 和下方 Slice 5A-1 foundation 任务外，Phase 5A 后续产品实现、publication revalidation、Coordinator、API/UI、集成测试、E2E、Harness、人工验收、T025 Code Review、Final Review、Production Review、archive readiness 和 OpenSpec archive 均保持未勾选；后续必须继续按 tasks 执行，不得把 foundation 解释为完整 retention 能力。

本轮 remediation 已将以下实施前决策写入 proposal/design/delta；这些是规划证据，不代表产品实现完成：

- 正式 publication 的验证时间固定为 `archive_publish_intents.publication_verified_at`；字段只能通过绑定 publication/fence/digest/inventory/ownership 的 NULL-only CAS 从 NULL 首次写入；v10 历史 publication 初始为 NULL，受控 revalidation 失败保持 NULL 并返回 `RETENTION_PUBLICATION_UNVERIFIED` 或 `RETENTION_PUBLICATION_TIME_MISSING`，不得使用普通 `updated_at` 推断；真正重新发布创建新的 `publication_id`。
- source FK 清单包含 `case_shells.source_id`、`archive_attempts.source_id`、`archive_publish_intents.source_id`、`archive_publish_fences.source_id` 和 `archive_input_snapshots.source_id`；snapshot 是 work-only DELETE，文件和 row 必须在 source 删除/compact 前处理，不改为 nullable、不保留 snapshot tombstone row；正式引用的 attempt/intent/fence 保留到最小 source tombstone 的历史 FK；提交前执行 `foreign_key_check` 和无遗留 snapshot FK 验证。
- canonical deployment 配置键固定为 `BIJI_CASE_RETENTION_MODE`、`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和 `BIJI_CASE_RETENTION_BATCH_SIZE`；旧键只在 v10→v11 首次创建 policy row 且新 DAYS 缺失时提供 days，非法旧值回落 30 天并记录诊断，policy row 创建后 Coordinator 停止读取，旧键不得设置 mode 或启用 enforce。
- 所有 durable timestamp、比较、CAS、audit 和 retention 计算使用带时区 UTC；公共 API 返回带时区 ISO 8601，前端、工作台、运维和人工验收按 `Asia/Shanghai` 展示；无时区时间拒绝参与资格判断。
- 默认到期时间为 `expires_at_utc = retention_anchor_utc + (retention_days × 24 hours)`；30 天等于连续 720 小时，不按无时区本地文本比较。

## 1. Phase 5A — 范围、重叠和合同（T020、T024）

- [x] 1.1 **T024** 审计 `openspec/changes/` 下所有 active change，更新 `design.md` 依赖矩阵，逐项记录 shared/API/schema/正式产物/Legacy/Canonical/Shadow 边界；完成条件：覆盖 `case-shared-defaults`、`extensible-report-template-platform`、`report-parsing-cache-management`、`large-report-preview-liveness` 及其他当前 active change，未修改其他 change；验证：active change status 和 Git 审计；证据：本 change `design.md`。
  - Phase 5A pre-implementation gate：`PASS`；审查基线 `3edcd2c41b732efbb8d264798e2c3d980be33e5a`。
  - overlap 结论：未发现其他 active change 明确占用 schema v11、替换 `archive_publish_intents` authority、定义冲突的 Word identity 或 retention policy durable authority；已登记的潜在文件交集不阻断。
  - v10 事实证据：`workbench_schema.py`/`workbench_database.py`、source/snapshot/reference、publication/fence/asset、Word/controller、lease/revision/recovery/runtime 代码已核对；具体结果记录于本 change `design.md` 的 Phase 5A Gate section。
  - 首批切片确认：仅允许进入 Slice 5A-1 共享合同与 v11 migration foundation；本任务未执行 migration、清理、Coordinator、API/UI 或测试实现。

### Phase 5A first implementation slice confirmation（记录，不新增任务编号）

- 允许下一步：SharedTypes/constants/config parsing contract、v10→v11 migration foundation、四个新增 durable 对象、既定字段扩展、唯一约束/索引、source FK rebuild 和 `foreign_key_check` fixture。
- 明确排除：Scheduler/Coordinator、`enforce`、preview 扫描、任何案件/文件删除、历史 publication 自动 verified、Word 生成/持久化、清理执行 API、公共 UI/API route 改造和完整测试/Harness/人工验收。
- Gate 完成后，Slice 5A-1 foundation 已实现；不得将本记录解释为完整 retention、cleanup、Coordinator、API/UI 或正式 Word 能力已实现。
- [x] 1.2 **T020** 在 `packages/shared/types/`、`packages/shared/constants/` 和 `packages/shared/utils/` 冻结 policy mode、eligibility、preview/status/run、case/publication/word artifact identity、稳定错误码和安全投影；完成条件：公共类型不包含路径、表名、owner token、lease/fence/attempt/context，且不包含公共人工执行/force-delete 合同；验证：SharedTypes contract、typecheck 和 `tests/test_check_contracts.py`；证据：类型测试与 delta/data-model 文档。
  - Slice 5A-1 evidence：新增 retention SharedTypes、constants、UTC utility 和纯配置解析合同；`python -m pytest tests/test_check_contracts.py -q`、shared build/typecheck 和 `npm.cmd run verify:quick` 的 `lint:arch`/`typecheck` 阶段通过；quick 文档阶段仍报告 13 个待后续 living `data-model` 同步的 type drift。
- [x] 1.3 **T020** 将 v10 的 `case_shells`、`case_drafts`、source/work projections、`asset_references`、task、lease/revision、`archive_input_snapshots`/binding/plan、attempt、intent、fence、asset、Manifest index、audit 和 global control tables 逐项映射为 `KEEP`、`COMPACT`、`DELETE`、`DERIVED/REBUILDABLE` 或 `NEW`；完成条件：每行都有字段、资格、引用、顺序、失败恢复和清理后验证，明确 `archive_input_snapshots.source_id` 为 work-only DELETE、source row 删除前必须删除 snapshot row、source tombstone/FK 方案；验证：SQLite `foreign_key_list`/schema introspection fixture；证据：design 矩阵和 migration fixture。
  - Slice 5A-1 evidence：v11 migration 保留 source identity、重建所有 source FK 相关表、保持 snapshot `source_id` 非空 FK，提交前执行 `foreign_key_check`；migration fixture 和 targeted foundation tests 通过。
- [x] 1.4 **T020** 冻结 30 天 deployment policy、`disabled/preview_only/enforce`、anchor 三个 durable 来源、`publication_verified_at` 的 NULL-only CAS/v10 revalidation/enforce gate、UTC timezone-aware 时间、`expires_at_utc = anchor_utc + retention_days × 24 hours`、API ISO 8601、Asia/Shanghai 展示、5 分钟未来时间阈值、缺失 blocker code 和 required Word/publication set；完成条件：不使用创建时间/首次导出时间/普通 `updated_at` 单独计算；验证：shared/backend contract tests；证据：retention delta 和配置测试。
  - 实现证据：`packages/shared/utils/retentionRules.ts` 增加 UTC-aware/可信时钟边界，`packages/backend/app/repository/retention_time.py` 固化 UTC-Z、5 分钟未来阈值和连续 24 小时 expiry；`RETENTION_DISPLAY_TIME_ZONE`、默认值和稳定 blocker/error constants 已存在。
  - 验证：`tests/test_retention_contract_matrix.py`、`tests/test_retention_utc_z.py`、`packages/frontend/src/__tests__/retentionRules.test.ts`；后端 32 passed、前端 retention 3 passed、lint/typecheck 通过。未把创建时间、首次导出时间或普通 `updated_at` 用作 anchor。
  - 提交/推送：实现证据已包含于 `1562948`（`feat(retention): add durable policy authority contracts`），已推送 `origin/codex/demo-next-stage`。
- [x] 1.5 **T020** 冻结现有 `archive_publish_intents` 为 RAR/Manifest/MD5 唯一 authority、fence/asset/index 边界、durable Word artifact 和 cleaned case 稳定访问身份；完成条件：不创建竞争性 `formal_artifact_authority` 表、不提供正式产物删除 API；验证：authority delta 和 Legacy gate 审查；证据：formal-artifact-authority/electronic-inspection-record specs。
  - 实现/审查证据：`FormalWordArtifactRepository` 仅按当前 deployment/case 绑定既有 `archive_publish_intents`，verified artifact 要求 `phase='verified'`、`publication_status='verified'` 和非空 `publication_verified_at`；safe projection 不返回内部相对路径；`test_retention_contract_matrix.py` 断言孤立 publication 被拒绝且不存在 `formal_artifact_authority` 表。Legacy/Canonical/Shadow 边界由本 change delta 与 living `electronic-inspection-record` spec 保持一致。
  - 第二轮独立只读实施复审：`PASS`，无 Critical/High/阻断 Medium；non-blocking 建议留给后续运行时资格测试。
  - 提交/推送：实现证据已包含于 `1562948`，已推送 `origin/codex/demo-next-stage`。
- [x] 1.6 **T020T** 建立规划合同测试矩阵，覆盖 modes、到期/未来时间、活动任务/租约、未导出、失败待重试、Word/publication authority 缺失、稳定身份访问和正式产物保护；完成条件：每个 blocker 有稳定反向断言；验证：测试计划审查；证据：T022T/T023T 测试映射。
  - 测试矩阵证据：`tests/test_retention_contract_matrix.py` 覆盖未来时间、expiry 范围、活动任务/租约/恢复、publication/Word 缺失或未验证、snapshot、ownership、authority 和 not-expired 稳定 code，以及路径安全/public projection/竞争 authority 断言；现有 publication CAS、UTC-Z、cleanup phase 和 foundation tests 继续覆盖对应反向路径。
  - 提交/推送：实现证据已包含于 `1562948`，已推送 `origin/codex/demo-next-stage`。

## 2. Phase 5B — 数据模型与迁移（T022、T022T）

- [x] 2.1 **T022** 在 `workbench_schema.py`/`workbench_database.py` 实现规划中冻结的 v10→v11 事务 migration；完成条件：版本正式为 11，新增 policy/retention/run/Word artifact、`publication_verified_at`、source tombstone、nullable shell references、`archive_input_snapshots.source_id` work-only NOT NULL FK/DELETE 边界、`asset_references` 清理边界和 shell/task 最小字段，未新增 RAR/Manifest 平行 authority；验证：迁移前后 schema、所有 source FK/check、旧版本拒绝、重复启动幂等、revalidation NULL 初始状态和回滚测试；证据：migration tests。
  - Slice 5A-1 evidence：`python -m pytest tests/test_retention_foundation.py tests/test_publication_verified_foundation.py tests/test_workbench_persistence.py tests/test_archive_schema_migration.py tests/test_template_controller.py tests/test_template_profile_service.py -q` 通过；v10 fixture、v11 fresh schema、FK check、NULL publication time、初始 disabled policy、幂等和现有回归均有断言。

### Slice 5A-1 validation record

- `python -m pytest tests/test_check_contracts.py -q`：5 passed；Slice foundation targeted pytest：38 passed；`npm.cmd run test:backend`（`verify:backend` 的实际脚本）：802 passed、3 skipped、16 warnings。
- `npm.cmd run verify:quick`：`lint:arch`、shared/frontend typecheck 通过；文档阶段以 1 退出，原因是新增 SharedTypes 尚未同步到 living `openspec/specs/data-model.md` 的 13 个 type-drift。本轮禁止修改 living specs，该同步保留给后续文档任务。
- `openspec.cmd validate case-record-retention-and-formal-artifact-protection --strict --no-interactive`、`openspec.cmd validate --specs --strict --no-interactive` 和 `git diff --check` 通过；`npm.cmd run verify:docs:strict` 同样仅因上述 13 个 deferred type-drift 失败。

### Slice 5A-1 Review Remediation

- Independent Implementation Review result: `REJECT`.
- High finding closed: `publication_verified_at` NULL-only CAS now accepts only `phase='verified'`; `indexed`, `publishing`, `failed` and other non-verified phases fail closed while digest, file-set, fence, deployment/case and ownership checks remain required.
- Blocking Medium findings closed: `partial_failure` is represented consistently in the shared phase union, backend repository validation/status projection, SQLite v11 CHECK/index contract, living data model and round-trip/invalid-phase tests; the non-empty v10 graph fixture now covers deployment, case, draft, task, source, attempt, snapshot, context binding, intent, fence, work/formal assets and asset reference relationships.
- Migration evidence: successful v10→v11 upgrade preserves identities, source FK relationships, non-empty draft/work/publication authority, `archive_input_snapshots.source_id` NOT NULL, NULL historical `publication_verified_at`, disabled policy, no cleanup run and no formal Word artifact; `foreign_key_check` is empty and reopen is idempotent. Failure injection rolls back to v10 with the complete graph intact and no partial v11 tables, after which a clean retry succeeds.
- Remediation evidence: `python -m pytest tests/test_publication_verified_foundation.py tests/test_retention_phase_foundation.py tests/test_retention_migration_graph.py tests/test_retention_foundation.py tests/test_retention_utc_z.py tests/test_check_contracts.py -q` — 21 passed; `npm.cmd run verify:backend` — 813 passed, 3 skipped. A standalone full pytest run had one existing archive-retry timing failure; the isolated retry passed and the repository backend gate passed.
- `6.1 T024` remains checked because the living data-model reconciliation and final documentation gates are now evidenced. No new task is checked here; all cleanup, Coordinator, revalidation, durable Word, API/UI, E2E/Harness, manual acceptance, Code Review, Final Review, Production Review and archive tasks remain unchecked. The known `CaseRetentionRepository.upsert` insert-only warning remains deferred to its later repository task.

### Slice 5A-1 Second Independent Implementation Review（记录，不新增业务任务编号）

- [x] `Slice 5A-1 Second Independent Implementation Review = PASS`
  - 审查基线：`928bd629790953ac0fb7e03c4e3adc404bf85c5f`；该 baseline 是 Slice 开始前的 Git HEAD，审查对象是该 HEAD 上的完整未提交工作树。
  - Publication CAS blocker：`CLOSED`；仅允许 `phase='verified'`，`indexed` fail-closed，并继续绑定 publication/deployment/case、digest、file-set、fence、ownership 和 NULL-only 条件。
  - `partial_failure` blocker：`CLOSED`；已贯通 SharedTypes、Python、SQLite、repository、living model 和测试，不映射为 `succeeded`。
  - Migration evidence blocker：`CLOSED`；完整非空 v10 数据图 migration 成功，rollback 后 schema 和完整数据图仍为 v10，`foreign_key_check` 为空，历史 `publication_verified_at` 保持 `NULL`，policy 默认 `disabled`，不创建 cleanup run 或 formal Word artifact，v11 重开幂等。
  - 复审结论：无 Critical、High 或阻断性 Medium；SharedTypes/living model 无 drift、UTC-Z 无回归、schema/FK 无回归，Slice 边界无越界。
  - 验证证据：第二次复审定向测试 10 passed；remediation 定向测试 21 passed；UTC-Z 12 passed；`verify:backend` 813 passed/3 skipped；`verify:quick`、`verify:docs:strict`、change strict、living specs strict、`git diff --check` 全部 PASS。
  - retry timing 测试曾偶发失败，隔离重跑通过且最终 `verify:backend` 通过，记录为非阻断 flaky evidence。
  - 结论边界：允许形成一个 Slice 5A-1 本地实现提交；不代表 Phase 5 全部完成，不代表 T025 独立 Level 3 Code Review 已完成，不允许开始 Slice 5A-2/后续功能或 archive。
  - 非阻断 Warning：`CaseRetentionRepository.upsert` 当前为 INSERT-only，交由后续 retention repository/service 任务处理。

### Slice 5A-1 UTC-Z contract remediation and living data-model reconciliation

- 首次 living data-model reconciliation 判定为 `BLOCKED`：除 13 个真实公共 SharedTypes type-drift 外，部分新 v11 repository 通过 `utc_now()`/`normalize_utc()` 写入 `+00:00`，不符合 Phase 5 durable SQLite UTC `Z` 合同。
- 根因已核实：旧 helper 仍服务既有 v10/Phase 1–4 读取和持久化路径；新 v11 policy、retention record、cleanup run、formal Word artifact 写入路径需要显式的 canonical UTC-Z helper。
- 修复方式：新增集中式 `workbench_time.py` 的 `utc_now_z()`/`normalize_utc_z()`；保留 `utc_now()`/`normalize_utc()` 的历史读取兼容；新 v11 repository 和 retention 时间 helper 全部切换到 UTC `Z`；不重写历史时间、不回填 `publication_verified_at`、不启动 revalidation/cleanup。
- UTC-Z 定向证据：`python -m pytest tests/test_retention_utc_z.py tests/test_retention_foundation.py tests/test_publication_verified_foundation.py tests/test_check_contracts.py -q`：12 passed；覆盖 aware offset 转换、naive 拒绝、policy/retention/run/Word durable 写入、NULL-only publication 时间和无 SQL 本地时间默认值。
- living data-model 已同步实际的 13 个公共 SharedTypes、schema v11 foundation、FK/唯一约束/索引、UTC `Z` 写入及安全投影边界；后续 cleanup、Coordinator、preview/enforce、历史 publication revalidation、Word 文件持久化、cleaned-case routes、API/UI、Windows 删除和 E2E 仍仅保留在 active delta/tasks。
- 最终门控证据：`npm.cmd run verify:docs:strict`、`npm.cmd run verify:quick`、change/living OpenSpec strict 和 `git diff --check` 全部通过；本次同步未修改 delta specs、proposal/design 或后续实现任务。
- [x] 2.2 **T022** 新增 deployment-scoped policy/retention repository；完成条件：`disabled/preview_only/enforce`、30 天、`scan_interval_seconds`、batch、policy revision、anchor/due/blocker、canonical `BIJI_CASE_RETENTION_*` 配置和 deployment isolation 均 durable；旧键只在 v10→v11 首次创建 policy row 且新 DAYS 缺失时读取，非法旧值使用 30 并记录诊断，policy row 创建后不再直接读取；验证：非法配置、旧键兼容/优先级/停读、版本切换和重启测试；证据：retention repository tests。
  - 实现范围：`RetentionPolicyRepository.sync_from_environment()` 只在显式 canonical 配置存在时读取配置并更新 durable policy；有效变更单调递增 revision、配置不变不增 revision、变更记录 UTC-Z `activated_at`；非法配置 fail-closed 且保留既有 row；`get()` 只读取 `case_retention_policies`。v10→v11 初次创建仍固定 `disabled`，旧 key 只由首次 migration 且新 DAYS 缺失的 bootstrap 兼容路径读取；新安装不使用旧 key。
  - 验证：`tests/test_retention_foundation.py` policy sync/非法配置/旧键停读断言，`tests/test_retention_migration_graph.py` v10→v11 默认 disabled/identity preservation，`tests/test_retention_utc_z.py` durable UTC-Z；最终 `npm.cmd run verify:backend`：831 passed、3 skipped、16 warnings，`npm.cmd run verify:quick` 退出码 0；第二轮独立只读实施复审 `PASS`。
  - 提交/推送：实现证据已包含于 `1562948`，已推送 `origin/codex/demo-next-stage`；当前任务证据文档随后单独提交。
- [x] 2.3 **T022** 新增 cleanup run/claim repository；完成条件：run identity、owner、claim token、lease expiry、fence epoch、policy/case revision、phase、retry、file result 和 error/result durable，同一 deployment/case 只有一个 active run；验证：唯一约束/CAS/owner takeover 测试；证据：cleanup repository tests。
  - 实现范围：`CleanupRunRepository`/`cleanup_run_helpers.py` 持久化 planned run、policy/case snapshot，并在 SQLite transaction 内执行当前 durable policy/case revision CAS；claim 分配 owner/token、UTC-Z lease、单调 fence epoch，活动 lease 冲突，过期 lease 可 owner takeover；phase/result/retry/lease renewal 受 owner/token/fence/case/policy CAS 保护；recovery listing 仅限当前 deployment，public projection 不暴露内部 claim/lease/fence。
  - 测试：`tests/test_cleanup_run_repository.py` 覆盖 5 个合成场景（revision 变化 fail-closed、live conflict、expired takeover/new fence、old owner stale、renewal/过期 lease、active unique、terminal 后新 run、partial recovery/idempotency）；与现有 retention foundation/UTC-Z/phase/contract matrix 合计 31 passed；最终 `npm.cmd run verify:backend`：836 passed、3 skipped、16 warnings，`npm.cmd run verify:quick` 单独重跑退出码 0。
  - Review/remediation：独立只读复审先发现当前 revision CAS 和过期新 lease 两个阻断 Medium；已修复并补负向测试/突变验证（突变均按预期失败）；最终独立复审 `PASS`，无 Critical/High/阻断 Medium。`verify:docs:strict`、change strict、living specs strict 均通过。
  - 提交/推送：实现与 living spec 已包含于 `f67ae7e`（`feat(retention): add durable cleanup run claims`），已推送 `origin/codex/demo-next-stage`；当前 tasks 证据随后单独提交。
- [x] 2.4 **T022** 新增 `formal_word_artifacts` repository；完成条件：持久化 `word_artifact_id`、case/publication/deployment、digest/size、相对路径、Manifest digest、template identity/version、生成/验证时间和状态；不保存完整 `report_json`，不创建 RAR/Manifest authority 表；验证：Word artifact 重启、摘要和孤立文件 fail-closed 测试；证据：Word artifact tests。
  - 实现范围：`FormalWordArtifactRepository` 持久化 Word artifact 的 deployment/case/publication identity、受控相对路径、SHA-256 文件/Manifest digest、0–`2^53-1` size、template identity/version、UTC-Z 生成/验证时间和 `pending|verified|invalid` 状态；`verified_at` 与 `status='verified'` 双向一致；artifact 不保存完整 `report_json`，不创建 RAR/Manifest 平行 authority。
  - fail-closed 范围：创建和重启读取均要求当前 deployment/case 绑定的既有 publication row；verified artifact 读取时重新要求 publication phase/status 为 `verified` 且 `publication_verified_at` 非空；安全 projection 不返回内部相对路径；孤立 publication/文件、摘要格式、size、状态时间不一致均拒绝。实际 Word 文件生成、物理摘要复验、下载链路留给 3.1/3.8。
  - 验证：`python -m pytest tests/test_formal_word_artifact_repository.py tests/test_retention_foundation.py tests/test_retention_contract_matrix.py tests/test_retention_utc_z.py -q`：35 passed；`npm.cmd run verify:backend`：842 passed、3 skipped、16 warnings；摘要校验 mutation 和 publication read-revalidation mutation 均按预期失败后恢复；`npm.cmd run verify:quick`、`npm.cmd run verify:docs:strict`、change/living specs strict 均通过。
  - Review/remediation：独立只读复审首轮 REJECT 两个阻断 Medium（读取时 publication authority 未复验、`status`/`verified_at` 约束不对称）；已补充同事务 authority revalidation、双向状态约束和负向测试，最终复审 `PASS`，无 Critical/High/阻断 Medium。
  - 提交/推送：代码和测试提交 `ed33a9a`（`feat(retention): harden formal word artifact persistence`），已通过 commit hook 并推送 `origin/codex/demo-next-stage`；推送后 ahead/behind `0/0`。
- [x] 2.5 **T022** 将 `case_shells` compact 为最小 `record_cleaned` tombstone，并清理 `case_drafts` 可编辑 payload；完成条件：保留 case/deployment identity、safe summary、retention/cleanup state、tombstone revision、cleaned time、anchor 和正式身份关联；验证：cleaned case 不可编辑但可查询正式产物；证据：workbench repository/service tests。
  - 实现范围：新增 `CaseTombstoneRepository.compact_cleaned`，在 deployment-scoped claim、policy/case/cleanup revision、live lease/fence、retention anchor、verified publication/Word authority 和 active-work blockers 全部通过后，以一个 SQLite transaction 删除 `case_drafts`，保留 safe tombstone 与 formal rows，清空 case number/source/task/report payload，推进 retention/run 到 `completed`/`records_cleaned`；cleaned detail 仅返回 tombstone，draft save/get 和 lifecycle mutation fail-closed。
  - 部署隔离：`CaseShellRepository`、`CaseDraftRepository` 的读写、asset binding 和 lifecycle CAS 均绑定当前 `deployment_instance_id`；tombstone active-lease blocker 通过 case shell deployment 绑定，避免跨 deployment 误阻断或访问。
  - 验证：`python -m pytest tests/test_case_tombstone_repository.py -q`：7 passed；受影响 repository/formal/publication/persistence 回归：50 passed；`npm.cmd run verify:backend`：854 passed、3 skipped、16 warnings；`npm.cmd run lint:arch`、`npm.cmd run typecheck`、commit hook `npm.cmd run verify:quick` 通过。移除一个 deployment predicate 的窄范围 mutation 按预期失败（`DID NOT RAISE`），恢复后 tombstone 7 passed。
  - 失败/回滚边界：publication/Word authority、active lease、naive UTC anchor 和 claim 不一致均在 transaction 前/内 fail-closed；authority failure 测试确认 draft、shell、cleanup run 整体保持不变；正式 publication/Word rows 未删除。物理文件、snapshot/source whitelist cleanup 和公共 artifact API 留给后续任务。
  - 提交/推送：`c3e49f5`（`feat(retention): add cleaned case tombstone boundary`），已推送 `origin/codex/demo-next-stage`；推送后 ahead/behind `0/0`。
- [x] 2.6 **T022** 在 repository 层按 design 矩阵执行白名单删除/compact 和 `PRAGMA foreign_keys=ON` 顺序；完成条件：snapshot 文件先安全删除并验证、`archive_input_snapshots` row 在 source 删除/compact 前删除，正式 intent/fence/attempt 只引用最小 source tombstone，非正式 source row 和 `asset_references` 按白名单处理，正式 intent/Word/authority 不被 cascade 删除，`archive_assets` 无 FK 时仍通过 durable ownership 控制；验证：每个 source FK/逻辑引用分支、snapshot active/recovery/ownership/file-failure blockers、`foreign_key_check`、无遗留 snapshot FK、rollback/blocked 测试；证据：FK matrix、migration fixture 和 pytest。
  - 实现范围：新增 `CaseRecordCleanupRepository.compact_work_records`，在现有 deployment-scoped `records_cleaned` transaction 内按冻结顺序处理 snapshot、formal attempt/task、context、普通 task/attempt、临时 owned asset、plan、draft、`asset_references` 和 source；正式 intent/fence/attempt、publication/Word authority、已发布 asset 保留。正式引用 source 只压缩为最小 tombstone，未引用 source 删除，最后执行 `PRAGMA foreign_key_check`。
  - 文件阶段边界：repository 不接受客户端路径或文件清单，只消费内部 path-free `file_step_result`（version 1、ownership proof、精确 snapshot/temporary asset IDs）；要求 snapshot row 已为 `cleaned` 且临时 asset 仍由当前 task/plan durable ownership 证明。active、recovery、缺少 receipt、ID 不匹配、未知 ownership 均 fail-closed；canonical path、Windows reparse/root 校验和物理删除留给 3.5。
  - 验证：`python -m pytest tests/test_case_record_cleanup_repository.py -q`：5 passed；`python -m pytest tests/test_case_tombstone_repository.py tests/test_case_record_cleanup_repository.py -q`：12 passed；`npm.cmd run verify:backend`：859 passed、3 skipped、16 warnings；`npm.cmd run lint:arch`、`npm.cmd run typecheck` 通过。禁用 snapshot row 删除的 mutation 使正向测试按预期失败（残留 1 条 snapshot row），恢复后联合测试通过。
  - 回滚/保护边界：snapshot active/recovery/ownership/file-failure blocker 在任何记录变更前拒绝；未知 temporary asset 和 FK/正式引用冲突由事务整体 rollback；正式 publication/Word/Manifest/MD5/已发布 asset 未进入删除白名单，原始来源物理文件未触碰。
  - 提交/推送：代码、测试和 living spec 提交 `63c621b`（`feat(retention): add whitelist records cleanup`），commit hook `verify:quick` 通过；tasks 证据提交后推送 `origin/codex/demo-next-stage`。
- [x] 2.7 **T022** 补充 SQLite、正式 RAR/Manifest/MD5、Word、template、assets、policy、authority/audit 的成组备份、恢复和应用回滚边界；完成条件：明确 Git rollback 不等于 data rollback，旧应用拒绝 v11；验证：文档和受控恢复演练计划；证据：design/data-model 文档。
  - 实现范围：新增 `harness/retention-backup-recovery.md` 作为受控运维演练计划，并在 living `openspec/specs/data-model.md` 记录 v11 grouped backup、隔离恢复、derived index rebuild、policy disabled、authority/Word/FK 校验和应用回滚边界。覆盖 SQLite、正式 RAR/Manifest/MD5、Word、template、owned work assets、policy 和 audit 七组事实。
  - 回滚边界：明确 Git/application rollback 不等于 data rollback；v10→v11 继续使用现有单事务 migration、`foreign_keys=ON`、integrity/FK/schema validation；旧应用打开 v11 必须拒绝，不执行逆向 SQL、手工降表或 undelete。备份引擎和生产恢复执行仍不作为本任务新增 API，需在集中 Production Review/受控人工演练中执行。
  - 验证：`python -m pytest tests/test_workbench_persistence.py::test_corrupt_or_incompatible_database_fails_safe -q`：1 passed；`npm.cmd run verify:docs:strict`、`openspec.cmd validate case-record-retention-and-formal-artifact-protection --strict --no-interactive`、`openspec.cmd validate --specs --strict --no-interactive` 均通过。
  - 未完成边界：未复制或覆盖任何真实数据库、正式文件、模板或凭据；实际生产备份/恢复和旧版本二进制演练留给 T024T/Production Review，v11 migration/FK 失败矩阵的新增 pytest 留给 2.8。
  - 提交/推送：`5210319`（`docs(retention): define backup recovery boundaries`），commit hook `verify:quick` 通过；tasks 证据补充后推送 `origin/codex/demo-next-stage`。
- [x] 2.8 **T022T** 为 v11 migration、完整 source FK 顺序（含 `archive_input_snapshots.source_id`）、snapshot work-only DELETE、deployment isolation、tombstone、Word artifact backfill、`publication_verified_at` NULL-only CAS/revalidation、authority 保留和升级失败增加 pytest；完成条件：失败不留下半成品 schema，既有 publication facts 不降级，snapshot row 不在 source 删除/compact 后残留；验证：定向 pytest；证据：migration/retention test report。
  - 实现范围：扩展 `tests/test_retention_migration_graph.py`，注入 v11 migration 中途 SQL failure，断言事务整体回滚到 v10、schema_migrations/旧 source/snapshot/publication facts 保持、无 `_v10` 半成品和无 v11 新表；恢复后再次升级并通过完整 graph 校验。既有 graph 同时覆盖 non-empty v10→v11、完整 source FK、snapshot source identity、deployment owner、policy disabled、Word 无伪造 backfill、publication verified time 保持 NULL、重复初始化和 validation rollback。
  - 相关回归：`python -m pytest tests/test_retention_migration_graph.py -q`：3 passed；migration/FK/publication/Word/tombstone/records-cleaned 联合回归：38 passed；`archive_input_snapshots.source_id` 仍为 NOT NULL FK，records cleanup 后无遗留 snapshot row，formal publication/Word authority 与 source tombstone 保护通过。
  - 全量结果：`npm.cmd run verify:backend` 收集 863 项，859 passed、3 skipped；唯一失败为既有 `test_submit_returns_before_slow_parse_task_finishes` 的 0.3 秒时序阈值（0.329 秒），隔离重跑 1 passed、1 warning，未触及 2.8 代码或断言。最终 Phase 5 全量门控将再次重跑并记录稳定结果。
  - 提交边界：未改变 migration/product contract；新增 pytest 仅强化失败回滚证据。现有 living data-model 已准确描述该 migration/rollback 行为，本任务仅需同步 tasks evidence 后提交推送。

## 3. Phase 5C — 后端安全核心（T022、T022T）

- [ ] 3.1 **T022** 在 retention service 实现 anchor、`publication_verified_at` NULL-only CAS/v10 revalidation/enforce gate、Word `verified_at`、UTC aware/未来时间检查和完整 eligibility predicate；完成条件：unknown、publication verified time missing、revalidation 未完成/失败、Manifest 不一致、authority/ownership 缺失、活动任务/租约/恢复、未验证 Word/publication 均 fail-closed，`expires_at_utc` 使用 `anchor_utc + retention_days × 24 hours`，禁止使用无时区时间或普通 `updated_at`；验证：正反服务、revalidation、CAS、republish identity 和时区 fixture；证据：retention service tests。
- [ ] 3.2 **T022** 实现确定性 preview/dry-run；完成条件：按 case ID 稳定排序，返回候选/跳过、原因、清理/保留类别、anchor/due、policy/case revision、任务/租约/恢复摘要和安全 digest，不含内部身份；验证：DTO snapshot 和敏感字段断言；证据：preview tests。
- [ ] 3.3 **T022** 实现仅由 `enforce` Coordinator 调用的清理执行和四个二次校验点；完成条件：claim 前、文件前、SQLite 事务前、succeeded 前均重验 revision、lease、任务、retry/recovery、publication、Word、authority、ownership、policy 和 owner；客户端不能扩展白名单；验证：stale/concurrent tests；证据：cleanup execution tests。
- [ ] 3.4 **T022** 实现 `planned→claimed→preflighted→work_files_cleaned→records_cleaned→verified→succeeded` 状态机及 blocked/stale/cancelled/interrupted/partial/failed 状态；完成条件：文件/DB 非原子失败显式记录，重复请求幂等，不把部分成功标为 succeeded；验证：文件、SQLite、最终 authority 故障注入；证据：cleanup recovery tests。
- [ ] 3.5 **T022** 实现受控 Windows work-file cleanup；完成条件：canonical roots、ownership、case-insensitive root check、symlink/junction、UNC/设备路径、owned leaf、正式 output/source root 保护和稳定错误码符合 design；验证：synthetic Windows fixtures；证据：Windows cleanup tests。
- [ ] 3.6 **T022** 接入 deployment policy Scheduler/Coordinator；完成条件：disabled/preview_only/enforce、24 小时周期、1 小时最小值、`scan_interval_seconds`、batch 20、空扫描等待、canonical `BIJI_CASE_RETENTION_*` 配置、单 coordinator CAS、policy revision、30 秒 shutdown grace、旧键首次迁移读取/新 DAYS 优先/非法旧值回落 30/创建 policy row 后停读和非法配置 fail-closed 均实现；验证：scheduler/coordinator、旧键生命周期和 enforce gate tests；证据：runtime tests。
- [ ] 3.7 **T022** 实现 cleanup 与 autosave、parse/archive/cleanup task、archive retry/recovery、publication 更新、Word export、新 edit lease 的双向 conflict/CAS；完成条件：cleanup active 时上述操作拒绝，反向操作阻止 claim，不依赖进程内 mutex；验证：并发/恢复/owner takeover tests；证据：cleanup runtime tests。
- [ ] 3.8 **T022** 改造正式产物查询/验证链路，使 cleaned case 使用 case/publication/word artifact identity；完成条件：现有 task/context 只作未清理兼容，清理后不读取 draft/report、runtime context 或 index 作为唯一 authority；验证：重启、清理后列表/Manifest/MD5/RAR/Word gate 和 tamper tests；证据：archive authority tests。
- [ ] 3.9 **T022T** 增加后端资格、preview、Windows、snapshot blocker/删除失败、publication revalidation/NULL-only CAS、republish identity、enforce gate、UTC 到期计算、幂等、partial failure、取消收尾、重启恢复、互斥、正式产物保护和稳定 identity 访问 pytest；完成条件：每个 T022 delta scenario 有可定位证据；验证：定向 pytest；证据：后端测试报告。

## 4. Phase 5D — API 和兼容边界（T023、T023T）

- [ ] 4.1 **T023** 在 SharedTypes/constants 增加 policy/status/preview/run、case/publication/word artifact identity、稳定错误码、UTC ISO 8601 时间和安全投影 DTO；完成条件：不含路径、表名、token、lease/fence/attempt/context，也不含公共人工执行字段；无时区 timestamp 被拒绝；验证：typecheck/contract tests；证据：SharedTypes tests。
- [ ] 4.2 **T023** 注册 retention status、blocker、preview/dry-run、run status/progress/failure/recovery 和 cleaned formal artifact query 语义；完成条件：不提供公共逐案件 execute/delete/cancel/force-delete API，不接受路径、表名、文件列表或正式删除标记；验证：FastAPI TestClient 正反路径；证据：API controller tests。
- [ ] 4.3 **T023** 完成安全 projection、错误映射和日志脱敏；完成条件：覆盖 not due、active task、lease、recovery、snapshot active/recovery/ownership/file-delete failure、Word/publication missing/unverified/revalidation blocker、conflict、file busy、access denied、partial failure、config invalid 和 stale；验证：响应/日志敏感字段扫描；证据：API tests。
- [ ] 4.4 **T023** 适配 `record_controller.py`、`archive_controller.py`、归档 task routes 的 Legacy cleaned-case 边界；完成条件：可按 case/publication/word artifact identity 访问正式产物，Legacy 仍唯一正式输出，task/context 不成为 cleaned case 唯一入口；验证：Legacy parse/export/download/Manifest/Word 集成回归；证据：controller tests。
- [ ] 4.5 **T023** 增加 Canonical/Shadow 不调用断言；完成条件：清理不生成第二 RAR/Manifest/Word，不使用 Shadow/Canonical 作为资格、authority、审计或成功事实；验证：mock/spy integration tests；证据：Legacy/Shadow regression report。
- [ ] 4.6 **T023T** 增加 API preview/status/run、cleaned artifact access、Legacy compatibility、authority fail-closed、CAS/stale 和 Canonical/Shadow isolation 集成回归；完成条件：每条 T023 delta scenario 有可定位测试；验证：定向 pytest/TestClient；证据：API integration report。

## 5. Phase 5E — 案件工作台（T021、T021T）

- [ ] 5.1 **T021** 扩展 workbench hooks 消费 policy/status/preview/run/identity DTO；完成条件：刷新、多案件切换和重启后状态从后端恢复，确认/查询不携带路径或内部身份；验证：Hook tests；证据：frontend hook tests。
- [ ] 5.2 **T021** 扩展案件卡片、状态 badge 和 archive status 展示 policy mode、到期、eligible、skipped、blocked、processing、cleaned、失败/恢复和正式产物保护状态；完成条件：工作数据状态与正式产物状态分开，所有时间按 `Asia/Shanghai` 展示且不改变 UTC 比较事实；验证：RTL tests；证据：component tests。
- [ ] 5.3 **T021** 在工作台提供 preview/dry-run、blocker、run progress、失败/恢复提示；完成条件：不提供普通案件立即删除、人工 execute、force-delete 或正式产物删除按钮，不重新引入独立生成页；验证：page/route inspection；证据：page tests。
- [ ] 5.4 **T021** 处理 cleaned tombstone 的不可编辑详情和按稳定 identity 的正式产物入口；完成条件：不再提供草稿编辑，正式下载/验证以 durable authority 为准；验证：page/session tests；证据：workbench tests。
- [ ] 5.5 **T021T** 增加多案件、多任务、policy mode、preview、到期/跳过、Word/publication 保护、刷新恢复和 Legacy compatibility E2E；完成条件：只使用 `SYNTHETIC/TEST/FIXTURE`，不写入真实输入、人员、路径或生成资产；验证：Playwright；证据：E2E report 和 asset scan。
- [ ] 5.6 **T021T** 增加前端安全投影测试；完成条件：不渲染路径、token、lease/fence/attempt/context，不显示人工执行或 Canonical/Shadow 正式状态；验证：Vitest/RTL；证据：hook/component/page tests。

## 6. Phase 5F — Harness、文档和验收边界（T024、T024T）

- [x] 6.1 **T024** 在每个已完成 slice 的实现和验证证据完成后同步 living `electronic-inspection-record`、`data-model`、API/data-model 文档；完成条件：只同步已实现行为，不伪称后续能力已存在；验证：OpenSpec specs strict 和 docs strict；证据：Slice 5A-1 UTC-Z reconciliation record、2.4–2.7 data-model/Harness evidence、docs report。本次勾选覆盖截至 2.7 已同步的真实交付，Phase 5 后续实现及验收仍未完成。
- T022 living sync evidence：`openspec/specs/data-model.md` 补充 cleanup-run repository 的当前 revision CAS、lease takeover/fence、phase/result CAS 和 public projection 边界；明确本 slice 仍未实现 Scheduler、文件删除或 records compact。
- T022/2.4 living sync evidence：`openspec/specs/data-model.md` 补充 formal Word artifact repository 的 SHA-256/size/status 校验、publication authority 创建/读取 fail-closed、UTC-Z 和安全 projection 边界；明确本 slice 仍未实现真实 Word 文件生成、物理摘要复验或 cleaned-case 下载链路。
- T022/2.5 living sync evidence：`openspec/specs/data-model.md` 补充 cleaned tombstone 的 claim/authority/blocker 前置条件、case_drafts 原子删除、shell safe summary/identity 保留、formal rows 保留、`records_cleaned` 边界和 `CASE_RECORD_CLEANED` 不可编辑行为；在 2.5 边界明确 snapshot/source/task whitelist cleanup、物理文件删除和公共 artifact 查询仍未实现。
- T022/2.6 living sync evidence：`openspec/specs/data-model.md` 补充 path-free file-step receipt、snapshot row 删除顺序、formal source minimum tombstone、非正式 source/work whitelist、formal authority 保留和 `foreign_key_check` 提交前置条件；明确物理路径安全、实际文件删除和公共 artifact listing/download 仍留给后续任务。
- [ ] 6.2 **T024** 更新 `harness/directory.md`、架构/测试入口和 Level 3 verify/review/archive 记录（如新增目录）；完成条件：层级、测试入口、依赖和命令可追溯；验证：架构/docs 检查；证据：Harness report。
- [ ] 6.3 **T024** 维护 active change 依赖矩阵、schema version overlap gate 和实施先后；完成条件：不修改、合并或归档其他 change，直接冲突未解决时阻止实现；验证：Git/status 审计；证据：design/tasks/review notes。
- [ ] 6.4 **T024T** 准备人工验收清单，使用 `SYNTHETIC/TEST/FIXTURE` 输入和外部受控大报告边界；完成条件：不写真实输入、人员、路径或生成资产；验证：asset policy scan 和验收记录；证据：repository-assets policy。
- [ ] 6.5 **T024T** 准备 SQLite、正式 RAR/Manifest/MD5、Word、template/assets、policy 和 authority 成组备份/恢复/回滚演练边界；完成条件：不把 Git rollback 当 data rollback，不实现 undelete；验证：受控 deployment 记录；证据：Production Review 输入材料。

## 7. Phase 5G — Verify、Review、Production 和 Archive Gates（T025）

- [ ] 7.1 **Phase 5 verify gate** 完成 SharedTypes、v11 migration、backend、API、frontend、E2E、Legacy/authority、Word、Windows failure 和 asset policy 的定向验证；完成条件：T020T/T021T/T022T/T023T 证据可定位；验证：按 Level 3 规则执行 `verify:full` 或等价完整 Harness（执行者按仓库规则确认）；证据：完整 verify report。
- [ ] 7.2 **Phase 5 integrated acceptance gate** 完成多案件、多任务、preview、Coordinator enforce、取消收尾、重试、重启、活动保护、未导出/失败保护、正式 RAR/Manifest/Word 保留和 Legacy cleaned access 验收；完成条件：只触及白名单，正式 authority 全部可验证；验证：合成数据 + 外部受控大报告；证据：人工验收记录。
- [ ] 7.3 **T025 independent Level 3 Code Review** 启动独立评审，覆盖 authority source-of-truth、Word artifact、表级矩阵、v11 migration、claim/CAS、Windows、恢复、API 安全投影和 Canonical/Shadow 隔离；完成条件：PASS 或所有阻断项完成 remediation；验证：独立 reviewer 报告；证据：review artifact。
- [ ] 7.4 **Final Review gate** 完成需求覆盖、实现正确性、spec/design/tasks 一致性和 active dependency 复核；完成条件：T020–T025 全部可追溯，未混入 TD-3 至 TD-6 或自动 undelete；验证：OpenSpec/Harness review；证据：Final Review record。
- [ ] 7.5 **Production Review gate** 确认单 Windows deployment、备份、恢复、容量、权限/占用、Legacy-only、Canonical 未启用和 Shadow 暂停；完成条件：发布边界和回滚路径明确；验证：Production Review；证据：Production Review record。
- [ ] 7.6 **Archive readiness gate** 确认 verify、integrated acceptance、独立 Code Review、Final Review、Production Review、docs strict、living spec sync 和 status 均满足归档协议；完成条件：人类明确确认 archive；验证：status JSON、diff check 和归档前清单；证据：archive readiness record。
- [ ] 7.7 **OpenSpec archive** 仅在全部 gate 通过且获得明确归档指令后执行；完成条件：归档记录、living specs、代码和资产与 Review 一致；验证：archive command、strict docs/status 和 Git diff；证据：archive record。

## Original Task Traceability

| 原任务 | 对应 tasks | 完成证据 |
|---|---|---|
| T020 | 1.2–1.5、2.1–2.7、4.1 | SharedTypes、v11/data-model、authority/Word、API contract |
| T020T | 1.6、3.9 | protection/anchor/Windows/backend test report |
| T021 | 5.1–5.4 | workbench status/preview/cleaned access changes and tests |
| T021T | 5.5–5.6 | Playwright/RTL comprehensive report |
| T022 | 2.1–2.7、3.1–3.8 | migration/repository/service/Coordinator/authority evidence |
| T022T | 2.8、3.9 | pytest and failure-injection evidence |
| T023 | 4.1–4.5 | SharedTypes/status-preview/Legacy/stable identity evidence |
| T023T | 4.6 | API integration regression evidence |
| T024 | 1.1、6.1–6.3 | dependency/Harness/API/data-model documentation |
| T024T | 6.4–6.5、7.2 | synthetic/external acceptance and backup boundary |
| T025 | 7.3–7.7 | independent review, Final/Production/archive records |
