# Proposal: 案件记录保留与正式产物保护

> 变更包：`case-record-retention-and-formal-artifact-protection`
> 级别：Level 3
> 范围：Phase 5 完整范围（T020–T025）
> 基线：Phase 1–4 归档于 `2026-08-01-persistent-case-workbench-and-archive-coordination`
> 状态：Spec frozen / Planning Review passed；本文件记录已冻结的规划基线，不表示 Phase 5 产品实现、测试、人工验收或后续 Review gate 已完成

## Planning Review Record

- Review 名称：`Phase 5 Final Spec Freeze Review`。
- Review 基线：`8d6800417deec09003c0a304340b8ba8c7037a3f`。
- 最终结果：`PASS`。
- 审查范围：本 proposal、design、tasks、4 组 delta specs；当前 v10 schema、source/snapshot/publication/Word 事实；living specs；以及相关 active changes 的直接合同冲突。
- 关键关闭项：C-01、C-02、C-03 及 H-01–H-05 全部关闭；无 Critical、High 或阻断性 Medium。
- 验证证据：change strict、living specs strict、`verify:docs:strict`、`git diff --check` 和 OpenSpec status 全部通过。
- 时间合同：durable 时间、比较、CAS、审计和 retention 计算使用带时区 UTC；公共 API 返回带时区 ISO 8601；用户界面和人工验收按 `Asia/Shanghai` 展示；默认 30 天按连续 720 小时计算。
- 结论：允许提交 Phase 5 立项包；Planning Review 到此终止，不再增加新的 Spec Freeze Review。PASS 只批准规划基线，不表示 Phase 5 产品实现已完成；后续必须从 tasks 的 Phase 5A 开始，并先执行 active change/schema overlap gate 和当前 v10 事实复核，不得绕过 tasks 批量实现。

## Phase 5A Pre-implementation Gate Record

- Gate 名称：`Phase 5A pre-implementation overlap gate and v10 fact verification`。
- 审查基线：`3edcd2c41b732efbb8d264798e2c3d980be33e5a`；对应现有 tasks 的 `1.1 T024`，未新增任务编号。
- Gate 结果：`PASS`。本次只完成 active change 重叠审计、v10 事实核对和首批实现切片确认；没有修改产品代码、测试或 schema，没有启动 Coordinator、enforce 或案件清理。

### Active change overlap 结论

| Active change | 实际交集 | v11/authority/policy 冲突 | 顺序与 Gate 结论 |
|---|---|---|---|
| `case-shared-defaults` | SharedTypes/constants、deployment defaults、既有 `shared_defaults` 表 | 未定义 v11、retention mode/days/interval/batch 或 publication/Word authority；保留独立的 `case_retention_policies` | Phase 5A 先记录；若未来同时迁移，须合并事务并保持对象语义隔离；不阻断 |
| `extensible-report-template-platform` | 模板 identity、Manifest/Word 来源、Legacy/Canonical/Shadow | 未定义 v11 或第二 RAR/Manifest authority；当前仍保持 Legacy 正式输出、Canonical 未启用、Shadow 旁路 | Phase 5 保留 Legacy-only 和模板 identity/version 记录；不阻断 |
| `large-report-preview-liveness` | preview、`archive_context_id`、runtime/cache 和 `/records/*` 兼容路径 | 未定义 v11、retention policy 或新的 formal artifact authority；runtime context 不是 cleaned case 的目标入口 | 先建立本 change 的稳定 identity 访问再改兼容路由；不阻断 |
| `report-parsing-cache-management` | parsing cache 和缓存生命周期 | 明确 cache 仅为 work cache，不是正式 authority，也不定义 retention policy | 不把 cache 纳入正式保留资格；不阻断 |
| Word/template 相关 active changes（含 `template-2026`、`docx-vml-pagination`、`preview-export-correction`、`export-name-and-datetime-controls`） | 模板/渲染/文件名局部行为 | 未定义与 `word_artifact_id` 冲突的身份或新的 authority；不改变模板公共合同 | formal Word artifact 记录最终模板 identity/version；不阻断 |
| 其他当前 active changes（parser、UI、上传、demo 和请求存活性变更） | 局部前端、解析或缓存文件 | 未引用 workbench schema/migration、v11、publication authority 或 retention policy | 仅保留登记，不修改其他 change；潜在文件交集不阻断 |

结论：未发现其他 active change 明确占用 `WORKBENCH_DATABASE_SCHEMA_VERSION = 11`、定义不可兼容 migration、替换 `archive_publish_intents` authority、要求临时 `report_json` 作为唯一正式 Word 入口，或以不同 durable row 作为 retention policy authority。已登记的合同交集不改变 Legacy-only、Canonical 未启用、Shadow 暂停边界。

### v10 implementation fact baseline

- `packages/backend/app/repository/workbench_schema.py` 的实际数据库 schema 为 v10，migration tuple 为 1–10。当前 `case_shells.source_id`、`parse_task_id` 和 `archive_context_bindings.source_id` 是逻辑引用而非完整 SQL FK；其余 source 相关 SQL FK、`NOT NULL`、索引和 cascade 以 design 的表级矩阵为实现输入，不在本 Gate 擅自改变。
- `WorkbenchDatabase.connect()` 开启 `PRAGMA foreign_keys = ON`、busy timeout，并要求 delete journal；`initialize()` 在 `BEGIN IMMEDIATE` 中应用未完成 migration、写入 `schema_migrations`/`user_version`、运行 `validate_schema` 和 deployment owner 检查，成功后提交，异常整体 rollback；高于支持版本或 migration 集合不连续时拒绝打开。`normalize_utc()` 拒绝无时区输入并归一化到 UTC。
- 当前 source repository 仍保存内部路径、allowed root、root identity、metadata 和 fingerprint，并通过 revision/发布 fence 保护 source 变更。当前 snapshot repository 创建/seal/恢复 work-only snapshot，并将物理 snapshot 清理后标记为 `cleaned`；v11 的 row DELETE、source tombstone 和 FK table rebuild 尚未实现，分别由后续 2.1/2.6/2.8 任务承担。`asset_references` 由 case/asset identity 管理工作引用，当前没有正式 RAR/Manifest/Word authority 语义。
- 当前 `archive_publish_intents` 持久化 attempt/case/source、publication identity、Manifest JSON、publication digest、file set、status、phase、fence 和 `updated_at`；`seal_publication` 绑定 active fence，publication durable state 由 intent/fence/assets/Manifest 校验链恢复。v10 尚无 `publication_verified_at`，因此不得把现有 `updated_at` 当作 retention anchor；NULL-only CAS、历史 revalidation 和 enforce gate 仍是后续实现任务。
- 当前 Word 入口 `record_generator_service.generate_docx()` 以请求中的 report、可选 Manifest/context 和模板 registry 生成文件；`record_controller.py` 的 `/records/export` 要求 `report_json`，Manifest 校验与下载路径使用 runtime context。成功文件目前没有 `formal_word_artifacts` durable row/`word_artifact_id`，这是后续 2.4/3.8 的实现缺口，不是本 Slice 的实现内容。
- 可复用基础包括 case/task revision 与事务 CAS、edit lease heartbeat/expiry、task claim/cancel/restart recovery、publication fence、durable publish-intent reconciliation，以及 FastAPI lifespan 的 archive runtime 启停和有界停止。本 Gate 不重新实现或改变 Phase 1–4 合同。

### Slice 5A-1 confirmation

下一步允许实施的首批切片是“共享合同与 schema v11 migration foundation”，只建立 durable foundation：retention mode/blocker/policy/status/preview/run/Word identity 安全 DTO 和 constants/config parsing contract；v10→v11 单事务 migration；`case_retention_policies`、`case_retention_records`、`case_cleanup_runs`、`formal_word_artifacts`；`case_shells`、`source_records`、`task_records` 和 `archive_publish_intents.publication_verified_at` 的最小扩展；必要索引、唯一约束、source FK rebuild 和 `foreign_key_check` migration fixtures。

本轮明确不包含：启动 Scheduler/Coordinator、创建 enforce run、preview 扫描、实际案件或文件清理、任何现有记录删除、历史 publication 自动标记 verified、Word 生成/持久化链路、清理执行 API、公共 UI、API route 改造或完整测试/Harness/人工验收。只有 Slice 5A-1 的 migration 和共享合同实现及其定向验证完成后，才可进入后续 5B/5C 任务。

## Why

Phase 1–4 已提供持久化案件工作台、版本化草稿、Archive Scheduler/Worker、sealed input snapshot、publication generation、SQLite durable authority、Manifest/index、正式 RAR 与 Word 导出，以及 ownership、lease、fence、CAS、恢复、取消、重试、日志和安全投影基础。

当前仍缺少案件工作记录的 deployment 级保留策略、确定性 preview、安全清理编排、清理状态工作台展示、清理失败/取消/重启恢复和综合治理闭环。长期保留草稿、任务、来源工作投影和临时资源会造成数据与容量累积；直接删除案件又可能破坏正式 RAR、Manifest、MD5、Word、publication generation 及其 SQLite 权威事实。

本变更冻结一条安全边界：只清理明确归属于目标案件、且不再被运行流程需要的案件工作数据；正式 publication、正式 RAR/分卷、Manifest、MD5、正式 Word 及其 durable authority 具有独立生命周期，不能被案件工作记录清理删除。

## What Changes

- 建立 deployment 级 retention policy：`disabled`、`preview_only`、`enforce` 三种模式；默认保留 30 天；新安装和 v10→v11 升级均为 `disabled`，不得在升级后批量删除历史案件。
- 冻结 deployment 运维配置入口：`BIJI_CASE_RETENTION_MODE`、`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和 `BIJI_CASE_RETENTION_BATCH_SIZE`。策略以 `case_retention_policies` 为 durable 事实；现有 `workbench.successful_case_retention_days` 仅在 v10→v11 首次创建当前 deployment policy row 且新 DAYS 环境变量缺失时作为 days 兼容输入，非法旧值回落 30 天并记录诊断；policy row 创建后 Coordinator 不再直接读取旧键，旧键永远不能设置 mode 或启用 enforce。
- 固化 retention anchor：

  ```text
  max(
    case_last_meaningful_mutation_at,
    latest_verified_formal_publication_at,
    latest_successful_word_export_at
  )
  ```

-  三个时间均来自 durable 事实，缺失、冲突、未来时间或无法验证时 fail-closed；到期时间固定为 `expires_at_utc = retention_anchor_utc + (retention_days × 24 hours)`，不按无时区本地文本比较。
- `archive_publish_intents.publication_verified_at` 是 publication verification 的唯一 durable 时间来源；它只能通过 NULL-only CAS 从 `NULL` 首次写入，普通读取、下载和重复验证不更新时间；v10 历史 publication 先受控 revalidation，失败保持 NULL，候选不得进入 enforce，真正重新发布创建新的 `publication_id`。所有持久化、比较、CAS、审计和 retention 计算使用带时区 UTC，公共 API 返回带时区 ISO 8601，前端/工作台/运维/人工验收按 `Asia/Shanghai` 展示。
- 固化 v10 表级 KEEP/COMPACT/DELETE/DERIVED/NEW 矩阵，包含字段、资格条件、FK/逻辑引用、顺序、失败恢复和验证方式。
- 冻结 v10 外键和工作快照处理：source 关系清单包含 `case_shells.source_id`、`archive_attempts.source_id`、`archive_publish_intents.source_id`、`archive_publish_fences.source_id` 和 `archive_input_snapshots.source_id`；其中 snapshot 是 work-only `DELETE`，snapshot 文件和 row 必须在 source 删除/compact 前安全处理，v11 不把其 `source_id` 改为 nullable，也不保留指向 source tombstone 的历史 snapshot row。正式 publication/attempt/fence 保留对最小 source tombstone 的历史 `source_id` 引用；非正式 source row 可删除；v11 事务重建必要 shell/source 约束并清理 `asset_references`，不得关闭外键或由实现者选择删除路径。
- 继续使用现有 `archive_publish_intents`、`archive_publish_fences`、正式 `archive_assets` 和 publication durable facts 作为 RAR/Manifest/MD5 的唯一权威来源；在既有 intent 上增加不可变的 `publication_verified_at` 事实，不创建第二套 authority。`formal-artifact-authority` 是能力边界名称，不代表新增与 publish intent 平行的 RAR/Manifest authority 表。
- 为成功 Word 导出增加独立 durable formal Word artifact 事实：稳定 `word_artifact_id`、publication 关联、Manifest digest、模板 identity/version、摘要、大小、受控相对路径和验证时间。清理后 Word 通过 `word_artifact_id` 访问，不依赖已删除的 `report_json` 或 runtime context。
- 清理后的公共身份固定为 `case_id`、`publication_id` 和 `word_artifact_id`。按 `case_id` 列出保留正式产物，按 `publication_id` 验证/访问 Manifest、MD5、RAR，按 `word_artifact_id` 验证/访问 Word；不得依赖 `archive_context_id`、进程内 runtime store、TTL context、普通任务 payload、路径或派生 JSON index。
- 增加确定性 cleanup preview/dry-run：返回候选、跳过原因码、计划清理类别、明确保留类别、anchor、到期判断、任务/租约/恢复/冲突摘要和 revision/digest 安全摘要。preview 与 Coordinator 执行使用同一版本化资格规则，执行时在 claim、文件删除前、SQLite 清理前和 succeeded 前重复校验。
- 自动真实清理只由 deployment retention policy 的受控 Coordinator 执行。本期不提供公共逐案件清理执行 API、普通工作台立即删除按钮或没有实际身份基础的人员级执行合同；公共 UI/API 只提供 retention 状态、blocker、preview、run 状态、失败和恢复信息以及正式产物保护结果。
- 增加 cleanup run、claim、phase、partial failure、幂等、重试、取消收尾和启动恢复；清理与 autosave、parse/archive/retry、publication 更新、Word export 通过 durable claim、case revision 和 CAS 互斥。
- 正式确定 schema v11 的最小 durable 模型，采用 v10→v11 单事务 migration、升级前成组备份、旧应用拒绝打开 v11、匹配备份回滚；不把关键事实放入内存或临时 JSON。
- 保持 Legacy `/records/*` 为唯一正式输出链路；Canonical 不进入正式链路，Shadow 继续暂停；不增加正式产物删除 API。

### 原任务到本 change 的追溯映射

| 原任务 | 本 change 任务组 | 规划职责 | Schema/API/UI | 验证与治理 |
|---|---|---|---|---|
| T020 | 5A、5B、5D | retention、稳定身份、v10 表矩阵、Word artifact、公共安全合同 | v11、SharedTypes、DTO | contract/spec/data-model 检查 |
| T020T | 5A、5C | 到期、阻断、正式产物保护、Windows 和 authority 场景 | 无实现前勾选 | shared/backend 测试证据 |
| T022 | 5B、5C | migration、repository、资格、preview、Coordinator、清理状态机 | SQLite、内部 cleanup task | pytest、故障注入、恢复 |
| T022T | 5B、5C | migration/FK、幂等、部分失败、重启和文件失败验证 | 无新增公共入口 | pytest 证据 |
| T023 | 5D | SharedTypes、status/preview/run API、稳定 artifact 身份、Legacy 边界 | 公共查询/preview，不提供人工执行 | API 集成回归 |
| T023T | 5D | API 安全投影、Legacy/Manifest/Word/CAS 回归 | 不提供正式删除 API | TestClient/集成报告 |
| T021 | 5E | 工作台 retention 状态、preview、blocker、进度、失败/恢复展示 | 不提供立即删除按钮 | Hook/component/page 验证 |
| T021T | 5E | 多案件、多任务、刷新恢复和正式产物保护 E2E | 不重新引入生成页 | 合成数据 E2E |
| T024 | 5A、5F | active overlap、API/data-model/Harness 文档、依赖和 gate | 不修改其他 change | docs/Harness 证据 |
| T024T | 5F、5G | 合成数据人工验收、外部大报告边界、备份/恢复边界 | 不提交真实资产 | 验收与 Production Review |
| T025 | 5G | 独立 Level 3 Code Review、Final/Production/archive readiness | 不改变产品契约 | 独立 Review 记录 |

实施顺序固定为：范围/重叠与共享合同 → 表级模型和 v11 migration → 后端安全核心 → 公共查询/preview 与兼容边界 → 工作台 → Harness/文档/人工验收边界 → 独立 Review、Production Review 和 archive gate。除已记录的 Planning Review 外，所有产品实现、测试、E2E、人工验收和后续 Review 任务仍保持未勾选。

## Capabilities

### New Capabilities

- `case-record-retention`：deployment policy、retention eligibility、preview、Coordinator 清理、状态/结果/审计、幂等、取消收尾、重启恢复和安全公共投影。
- `formal-artifact-authority`：由既有 publication durable facts、正式资产记录、formal Word artifact 记录和 case tombstone 共同形成的正式产物生命周期边界；不创建竞争性的 RAR/Manifest authority。

### Modified Capabilities

- `electronic-inspection-record`：补充清理后按 `case_id`/`publication_id`/`word_artifact_id` 访问正式产物的边界，并保持 Legacy 唯一正式输出、Canonical 未启用、Shadow 暂停。
- `data-model`：补充 v11 retention policy、case retention、cleanup run/claim、Word artifact、tombstone 和现有 publication authority 保留合同。

本 change 只新增 delta specs，不提前修改 living specs；实现完成并通过 archive gate 后，才按仓库流程决定是否同步 living specs。

## Scope

### In Scope

- 案件记录生命周期、deployment policy、30 天默认保留期、模式/周期/batch/版本和 fail-closed 配置行为。
- durable retention anchor、自动清理资格、未导出/失败待重试/活动任务/租约/恢复中的保护。
- v10 所有相关表和记录类别的 KEEP/COMPACT/DELETE/DERIVED/NEW 矩阵、ownership、FK 顺序、Windows 文件失败和恢复语义。
- v10→v11 的 source tombstone/FK table rebuild、`asset_references` 工作引用清理、`publication_verified_at` backfill 规则和 `foreign_key_check` 提交门控。
- cleanup preview、Coordinator 执行、claim、二次校验、幂等、失败重试、取消收尾、启动恢复、审计和稳定结果。
- 现有 publication intent/fence/asset authority 的独立保留，以及 durable formal Word artifact 和清理后的稳定公共身份。
- SharedTypes、公共 status/preview/run 查询和安全错误投影；Legacy `/records/*` 兼容和正式下载/验证门控。
- 工作台保留、到期、blocker、preview、运行、失败/恢复和 cleaned tombstone 状态。
- schema v11、备份/恢复/回滚边界、自动化测试、E2E、Harness、人工验收、独立 Code Review、Production Review 和 archive gate。

### Non-Goals

- 不增加或实现正式 RAR、分卷、Manifest、MD5、Word、publication generation 或正式 publication authority 的删除 API。
- 不删除原始授权来源目录，不按目录名、索引缺失、文件名或模糊关联推断资产归属。
- 不提供公共逐案件清理执行 API、普通案件立即删除按钮或没有真实权限基础的人员级执行合同。
- 不实现多实例共享 SQLite/输出根、多节点、高可用、远程数据库或新的分布式队列。
- 不实现从备份自动 undelete 已清理案件；备份恢复只定义边界。
- 不重新引入独立生成页面，不改变 Legacy 唯一正式输出，不启用 Canonical 正式链路，不恢复 Shadow 真实治理。
- 不处理 TD-3 至 TD-6，不重写 Phase 1–4 已完成的工作台、归档、发布、恢复和安全合同。
- 不修改模板、真实输入、真实人员、真实路径或生成资产；人工验收使用合成/外部受控边界。
- 本次 Gate 只完成 Phase 5A 的实施前事实核对，不实施 T020–T025，不执行 schema migration；后续必须从确认的 Slice 5A-1 开始，且不得把 Gate 记录解释为产品实现、测试、人工验收或后续 Review gate 已完成。

## Impact

- **SharedTypes/Constants/Utils**：新增 retention policy、preview/status/run、stable artifact identity、错误码和安全投影；不暴露路径、owner token、lease、fence、attempt、context 或数据库结构。
- **SQLite/Repository/Service**：从 v10 事务升级至 v11；增加 retention policy/record、cleanup run/claim、formal Word artifact、`publication_verified_at`、source tombstone 和 shell tombstone 字段；重建必要 FK 并处理 `asset_references`；不增加 RAR/Manifest 平行 authority。
- **Scheduler/Coordinator**：只在 `enforce` 下按 24 小时周期、最小 1 小时、batch 20 执行候选；同一 deployment 单 coordinator claim；停止 grace 30 秒；不因升级立即批量清理。
- **Controllers/Routes**：提供 retention status、blocker、preview、run 状态和清理后正式产物安全查询/门控；不提供公共人工执行、正式删除或路径目标 API。
- **Frontend**：展示 policy mode、保留/到期/blocker、preview、run、失败/恢复和 cleaned tombstone；不提供立即删除按钮或独立生成页。
- **Tests/Docs/Harness**：新增 migration/FK/authority/Word/Windows/CAS/恢复测试规划、API/data-model 文档、active overlap 矩阵和 Level 3 gates。

## Active Change Dependency Gates

| Active change | 交集 | Phase 5 前置检查 |
|---|---|---|
| `large-report-preview-liveness` | archive context、preview、controller/routes | 清理后正式访问不得依赖 runtime context；context 只作为未清理兼容入口 |
| `extensible-report-template-platform` | template、Manifest、Legacy/Canonical/Shadow、Word 来源 | 不改变 Legacy-only、Canonical 未启用、Shadow 暂停；Word artifact 记录最终模板 identity/version |
| `case-shared-defaults` | SharedTypes/constants、deployment defaults、既有 `shared_defaults` | retention policy 使用独立 durable policy；若同时 migration 必须合并事务，不能占用/覆写 v11 语义 |
| `report-parsing-cache-management` | parsing cache、cache routes、Manifest 边界 | cache 只能是 work cache，不能成为正式 authority 或清理资格依据 |
| Word/template active changes | Word 文件和模板版本事实 | 在 Word artifact durable 事实完成前不得启用 `enforce`；不修改模板合同 |
| 其他 active changes | parser、Legacy/UI、上传和预览局部交集 | 只登记依赖，不修改或归档；不得改变本 change 的 authority、Legacy/Canonical/Shadow 和 v11 gate |

只存在潜在文件交集而没有公共合同冲突的 active change 不自动阻断；上述直接合同交集必须在 Phase 5A 记录通过后才能进入实现。

## Acceptance Boundary

本 change 只有在完整验证、清理/正式产物保护后端与 API 测试、工作台综合 E2E、合成数据人工验收、独立 Level 3 Code Review、Final Review 和 Production Review 均形成证据，并确认 archive readiness 后，才可进入 OpenSpec archive。任何状态不明、数据库与文件不一致、ownership 不明、publication/Word authority 缺失、稳定身份无法访问或 Canonical/Shadow 越界都必须阻断成功。
