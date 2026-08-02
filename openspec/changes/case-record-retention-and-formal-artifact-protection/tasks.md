# Tasks: 案件记录保留与正式产物保护

> 除本条已记录的 Planning Review 外，所有产品实现、测试、E2E、人工验收和后续 Review 任务保持未勾选。创建或修订本 change 不等于产品能力已完成。
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

除上述规划 Review gate 外，Phase 5A 及后续产品实现、schema migration、publication revalidation、Coordinator、API/UI、单元测试、集成测试、E2E、Harness、人工验收、T025 Code Review、Final Review、Production Review、archive readiness 和 OpenSpec archive 均保持未勾选；后续必须从 Phase 5A 开始，并先执行 active change/schema overlap gate 和当前 v10 事实复核。

本轮 remediation 已将以下实施前决策写入 proposal/design/delta；这些是规划证据，不代表产品实现完成：

- 正式 publication 的验证时间固定为 `archive_publish_intents.publication_verified_at`；字段只能通过绑定 publication/fence/digest/inventory/ownership 的 NULL-only CAS 从 NULL 首次写入；v10 历史 publication 初始为 NULL，受控 revalidation 失败保持 NULL 并返回 `RETENTION_PUBLICATION_UNVERIFIED` 或 `RETENTION_PUBLICATION_TIME_MISSING`，不得使用普通 `updated_at` 推断；真正重新发布创建新的 `publication_id`。
- source FK 清单包含 `case_shells.source_id`、`archive_attempts.source_id`、`archive_publish_intents.source_id`、`archive_publish_fences.source_id` 和 `archive_input_snapshots.source_id`；snapshot 是 work-only DELETE，文件和 row 必须在 source 删除/compact 前处理，不改为 nullable、不保留 snapshot tombstone row；正式引用的 attempt/intent/fence 保留到最小 source tombstone 的历史 FK；提交前执行 `foreign_key_check` 和无遗留 snapshot FK 验证。
- canonical deployment 配置键固定为 `BIJI_CASE_RETENTION_MODE`、`BIJI_CASE_RETENTION_DAYS`、`BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS` 和 `BIJI_CASE_RETENTION_BATCH_SIZE`；旧键只在 v10→v11 首次创建 policy row 且新 DAYS 缺失时提供 days，非法旧值回落 30 天并记录诊断，policy row 创建后 Coordinator 停止读取，旧键不得设置 mode 或启用 enforce。
- 所有 durable timestamp、比较、CAS、audit 和 retention 计算使用带时区 UTC；公共 API 返回带时区 ISO 8601，前端、工作台、运维和人工验收按 `Asia/Shanghai` 展示；无时区时间拒绝参与资格判断。
- 默认到期时间为 `expires_at_utc = retention_anchor_utc + (retention_days × 24 hours)`；30 天等于连续 720 小时，不按无时区本地文本比较。

## 1. Phase 5A — 范围、重叠和合同（T020、T024）

- [ ] 1.1 **T024** 审计 `openspec/changes/` 下所有 active change，更新 `design.md` 依赖矩阵，逐项记录 shared/API/schema/正式产物/Legacy/Canonical/Shadow 边界；完成条件：覆盖 `case-shared-defaults`、`extensible-report-template-platform`、`report-parsing-cache-management`、`large-report-preview-liveness` 及其他当前 active change，未修改其他 change；验证：active change status 和 Git 审计；证据：本 change `design.md`。
- [ ] 1.2 **T020** 在 `packages/shared/types/`、`packages/shared/constants/` 和 `packages/shared/utils/` 冻结 policy mode、eligibility、preview/status/run、case/publication/word artifact identity、稳定错误码和安全投影；完成条件：公共类型不包含路径、表名、owner token、lease/fence/attempt/context，且不包含公共人工执行/force-delete 合同；验证：SharedTypes contract、typecheck 和 `tests/test_check_contracts.py`；证据：类型测试与 delta/data-model 文档。
- [ ] 1.3 **T020** 将 v10 的 `case_shells`、`case_drafts`、source/work projections、`asset_references`、task、lease/revision、`archive_input_snapshots`/binding/plan、attempt、intent、fence、asset、Manifest index、audit 和 global control tables 逐项映射为 `KEEP`、`COMPACT`、`DELETE`、`DERIVED/REBUILDABLE` 或 `NEW`；完成条件：每行都有字段、资格、引用、顺序、失败恢复和清理后验证，明确 `archive_input_snapshots.source_id` 为 work-only DELETE、source row 删除前必须删除 snapshot row、source tombstone/FK 方案；验证：SQLite `foreign_key_list`/schema introspection fixture；证据：design 矩阵和 migration fixture。
- [ ] 1.4 **T020** 冻结 30 天 deployment policy、`disabled/preview_only/enforce`、anchor 三个 durable 来源、`publication_verified_at` 的 NULL-only CAS/v10 revalidation/enforce gate、UTC timezone-aware 时间、`expires_at_utc = anchor_utc + retention_days × 24 hours`、API ISO 8601、Asia/Shanghai 展示、5 分钟未来时间阈值、缺失 blocker code 和 required Word/publication set；完成条件：不使用创建时间/首次导出时间/普通 `updated_at` 单独计算；验证：shared/backend contract tests；证据：retention delta 和配置测试。
- [ ] 1.5 **T020** 冻结现有 `archive_publish_intents` 为 RAR/Manifest/MD5 唯一 authority、fence/asset/index 边界、durable Word artifact 和 cleaned case 稳定访问身份；完成条件：不创建竞争性 `formal_artifact_authority` 表、不提供正式产物删除 API；验证：authority delta 和 Legacy gate 审查；证据：formal-artifact-authority/electronic-inspection-record specs。
- [ ] 1.6 **T020T** 建立规划合同测试矩阵，覆盖 modes、到期/未来时间、活动任务/租约、未导出、失败待重试、Word/publication authority 缺失、稳定身份访问和正式产物保护；完成条件：每个 blocker 有稳定反向断言；验证：测试计划审查；证据：T022T/T023T 测试映射。

## 2. Phase 5B — 数据模型与迁移（T022、T022T）

- [ ] 2.1 **T022** 在 `workbench_schema.py`/`workbench_database.py` 实现规划中冻结的 v10→v11 事务 migration；完成条件：版本正式为 11，新增 policy/retention/run/Word artifact、`publication_verified_at`、source tombstone、nullable shell references、`archive_input_snapshots.source_id` work-only NOT NULL FK/DELETE 边界、`asset_references` 清理边界和 shell/task 最小字段，未新增 RAR/Manifest 平行 authority；验证：迁移前后 schema、所有 source FK/check、旧版本拒绝、重复启动幂等、revalidation NULL 初始状态和回滚测试；证据：migration tests。
- [ ] 2.2 **T022** 新增 deployment-scoped policy/retention repository；完成条件：`disabled/preview_only/enforce`、30 天、`scan_interval_seconds`、batch、policy revision、anchor/due/blocker、canonical `BIJI_CASE_RETENTION_*` 配置和 deployment isolation 均 durable；旧键只在 v10→v11 首次创建 policy row 且新 DAYS 缺失时读取，非法旧值使用 30 并记录诊断，policy row 创建后不再直接读取；验证：非法配置、旧键兼容/优先级/停读、版本切换和重启测试；证据：retention repository tests。
- [ ] 2.3 **T022** 新增 cleanup run/claim repository；完成条件：run identity、owner、claim token、lease expiry、fence epoch、policy/case revision、phase、retry、file result 和 error/result durable，同一 deployment/case 只有一个 active run；验证：唯一约束/CAS/owner takeover 测试；证据：cleanup repository tests。
- [ ] 2.4 **T022** 新增 `formal_word_artifacts` repository；完成条件：持久化 `word_artifact_id`、case/publication/deployment、digest/size、相对路径、Manifest digest、template identity/version、生成/验证时间和状态；不保存完整 `report_json`，不创建 RAR/Manifest authority 表；验证：Word artifact 重启、摘要和孤立文件 fail-closed 测试；证据：Word artifact tests。
- [ ] 2.5 **T022** 将 `case_shells` compact 为最小 `record_cleaned` tombstone，并清理 `case_drafts` 可编辑 payload；完成条件：保留 case/deployment identity、safe summary、retention/cleanup state、tombstone revision、cleaned time、anchor 和正式身份关联；验证：cleaned case 不可编辑但可查询正式产物；证据：workbench repository/service tests。
- [ ] 2.6 **T022** 在 repository 层按 design 矩阵执行白名单删除/compact 和 `PRAGMA foreign_keys=ON` 顺序；完成条件：snapshot 文件先安全删除并验证、`archive_input_snapshots` row 在 source 删除/compact 前删除，正式 intent/fence/attempt 只引用最小 source tombstone，非正式 source row 和 `asset_references` 按白名单处理，正式 intent/Word/authority 不被 cascade 删除，`archive_assets` 无 FK 时仍通过 durable ownership 控制；验证：每个 source FK/逻辑引用分支、snapshot active/recovery/ownership/file-failure blockers、`foreign_key_check`、无遗留 snapshot FK、rollback/blocked 测试；证据：FK matrix、migration fixture 和 pytest。
- [ ] 2.7 **T022** 补充 SQLite、正式 RAR/Manifest/MD5、Word、template、assets、policy、authority/audit 的成组备份、恢复和应用回滚边界；完成条件：明确 Git rollback 不等于 data rollback，旧应用拒绝 v11；验证：文档和受控恢复演练计划；证据：design/data-model 文档。
- [ ] 2.8 **T022T** 为 v11 migration、完整 source FK 顺序（含 `archive_input_snapshots.source_id`）、snapshot work-only DELETE、deployment isolation、tombstone、Word artifact backfill、`publication_verified_at` NULL-only CAS/revalidation、authority 保留和升级失败增加 pytest；完成条件：失败不留下半成品 schema，既有 publication facts 不降级，snapshot row 不在 source 删除/compact 后残留；验证：定向 pytest；证据：migration/retention test report。

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

- [ ] 6.1 **T024** 在全部实现和验证证据完成后再同步 living `electronic-inspection-record`、`data-model`、API/data-model 文档；完成条件：实现前不伪称能力已存在；验证：OpenSpec specs strict 和 docs strict；证据：docs report。
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
