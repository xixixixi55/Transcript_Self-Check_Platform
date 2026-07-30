# Tasks: persistent-case-workbench-and-archive-coordination

> 本文件定义后续实现顺序；Phase 1 实现、历史阶段合成验收和自动验证已完成，当前为 Demo-ready（有条件）但不是 Production-ready。Phase 2 已实现完成，自动验证和轻量开发冒烟通过；Phase 3 进度产品/架构决策、T011/T011T 共享合同及 T012/T012T 卡片摘要 UI 已完成，T013–T015 未开始；Phase 4–5 未开始。Phase 1–4 最终集成人工验收、`1D-017R`、Production Review 和归档解除均未完成；TD-1 至 TD-6 保留。
> 目标合同：`openspec/specs/electronic-inspection-record/spec.md`
> 设计：`design.md`

## 执行规则

- 五个 Phase 可分别实现和自动验证；每阶段只做服务启动、核心页面和新功能可访问性的轻量开发冒烟，并记录为“实现完成、自动验证通过、等待最终集成人工验收”。Phase 1–4 全部实现后再统一执行完整 Harness、集成检查和一次完整端到端人工验收；轻量冒烟不等同正式人工验收，阶段 checkpoint commit 由用户单独授权。
- 每个 Phase 内按 Layer 0 → Layer 23 排列；每个代码任务后紧跟覆盖同一合同的测试任务。
- 实施前必须审计其他活跃变更包的重叠任务；不自动删除或降级旧包，不把 Canonical 或 Shadow 真实样本任务作为本包隐式前置条件。
- 所有测试数据必须显式标记 `SYNTHETIC/TEST/FIXTURE`，不提交真实案件、人员、设备号、路径、RAR、Manifest、DOCX 或运行输出。
- 任一阶段不得启动 Canonical 或 Shadow 真实样本治理；Legacy 仍是唯一正式输出。
- 每个阶段完成后执行该阶段定向测试、前后端全量测试、类型检查、架构检查、生产构建、严格文档检查、资产检查和 `git diff --check`；Phase 1–4 全部实现并完成最终集成人工验收后，再安排最终 Level 3 独立 Code Review 和归档判断。

## Phase 1 — 案件草稿、共享默认值、任务和工作台基础

**阶段目标**：建立持久化基础和可恢复工作台，但不改变 Legacy 归档/Word 安全门控。

### Layer 0 — SharedTypes

- [x] **T001** 在 `packages/shared/types/` 新增 `CaseShell`、`CaseDraft`、`SourceRecord`、`ClientIdentity`、`SharedDefaults`、`FieldState`、`EditLease`、`TaskRecord`、生命周期状态、双写结果和版本化 API DTO；保持 `InspectionReport` Legacy 主体。验证：共享类型编译，DTO 不包含绝对路径、大对象或敏感运行输出。
- [x] **T001T** 为 T001 增加类型契约测试/fixture，覆盖案件壳/正式草稿边界、任务状态、租约状态、无认证身份、双写结果、opaque asset 引用、默认值迁移结果和旧 `InspectionReport` 投影。验证：TypeScript typecheck 和合成 DTO round-trip。

### Layer 1/2 — SharedConstants and SharedUtils

- [x] **T002** 在 `packages/shared/constants/` 定义案件壳/解析失败/interrupted 状态、错误码、默认保留期配置键、租约周期、任务阶段和 API 版本；在 `packages/shared/utils/` 定义解析值优先级、状态迁移、双写结果聚合、自动保存冲突、无认证身份和生命周期纯函数。验证：禁止组件或服务重复硬编码状态值。
- [x] **T002T** 在对应 `*.test.ts` 覆盖合法/非法状态迁移、report > system_default > pending 优先级、双写状态聚合、版本冲突、ClientIdentity 和边界时间；使用 `SYNTHETIC/TEST` 数据。验证：Vitest。

### Layer 10/11/12 — Frontend Workbench

- [x] **T003** 新增 `useCaseWorkbench.ts`、`useCaseDraftAutosave.ts`、`useEditLease.ts`、`useTaskRecords.ts` 和案件工作台/案件编辑页面；以 `case_id` 加载案件壳/草稿，显示排队、解析中和失败卡片。工作台来源使用授权报告目录路径登记，不接受压缩包上传；解析成功后提供立即/稍后压缩决策。草稿保存使用 revision，租约使用后端心跳、失效和强制接管合同；旧前端生成地址只保留兼容重定向，后端 `/records/*` 合同继续保留。
- [x] **T003T** 新增工作台页面、自动保存、租约 Hook 和压缩决策的合成 Vitest/RTL 测试，覆盖提交即建壳卡片、每页 6 卡片、分页、目录路径提交、无上传控件、API 失败、保存冲突、网络失败保留输入、租约释放和只读占用。项目当前没有可执行 Playwright/E2E harness，因此快速切换/刷新恢复通过请求序列保护实现，并列入人工验收；测试数据均使用 `SYNTHETIC/TEST` 标记。
- [x] **T003F** 完成统一生产入口融合：案件详情复用 Legacy `RecordEditorForm` 的完整字段、日期时间校验、附件编辑、预览和 Word 导出映射；工作台补齐自定义下载文件名、检查人员加载和后端共享默认值保存，并保留案件状态、来源、租约、自动保存和多案件 UI 优化。旧 `RecordGeneratePage.tsx` 与报告压缩包上传入口停用，旧前端地址重定向到工作台。

### Layer 20 — Persistence Repositories

- [x] **T004** 新增 `case_workbench_repository.py`、`task_record_repository.py`、`shared_defaults_repository.py`、`edit_lease_repository.py`、`source_record_repository.py`、`asset_reference_repository.py`、`audit_event_repository.py`、`workbench_database.py`、`workbench_serialization.py` 和持久化错误/辅助模块；SQLite 只保存业务 DTO/元数据/opaque 引用，提供事务、revision、原子更新和实例数据目录隔离。验证：不写 Git 工作区，不暴露原始路径，不写入 Base64/HTML/原始 JSON 集合。
- [x] **T004T** 新增对应 repository 测试；覆盖案件壳与正式草稿约束、SourceRecord 绑定/复核、重启重载、事务回滚、幂等迁移、双写独立记录、唯一租约、过期租约、opaque asset 和大对象拒绝、损坏数据恢复。验证：pytest。

### Layer 21 — Services

- [x] **T005** 新增 `packages/backend/app/services/case_draft_service.py`、`shared_defaults_service.py`、`edit_lease_service.py`、`task_record_service.py`、`source_record_service.py` 和 `case_lifecycle_service.py`；实现目录来源授权/结构验证、提交即建壳、解析成功/失败/重试、report > system_default > pending 初始化、双写分别返回、15 秒续租、2 分钟接管前提、ClientIdentity 审计、重启 interrupted、来源重新选择、立即/稍后压缩决策和只清理本系统解析 staging 的服务边界。共享默认值以 `/workbench/defaults` 为正式持久化来源，工作台不使用 localStorage 作为案件或默认值事实源。
- [x] **T005T** 新增对应 service 测试；覆盖解析失败不可审核、来源失效/重新选择、普通编辑互斥、强制接管、默认值双写部分失败、重启中断、活跃任务删除前阻止和 revision 冲突。非自有进程终止不在本阶段调用，后台归档执行仍未实现。

### Layer 22/23 — Controllers and Routes

- [x] **T006** 新增 `packages/backend/app/controllers/workbench_controller.py`、`defaults_controller.py`、`lease_controller.py`、`source_controller.py` 和 `packages/backend/app/routes/workbench_routes.py`；提供报告目录路径登记、案件分页/详情、草稿补丁、默认值迁移与读写、任务状态/取消、租约读写、来源复核/重新选择、压缩时机决策和删除前检查 API，保留现有 Legacy `/records/*` 上传边界。
- [x] **T006T** 新增 controller/route 测试；用 httpx 合成请求验证目录授权/结构错误、提交即建壳、分页、版本冲突 409、双写状态、租约互斥、压缩决策、来源路径隔离、任务状态、删除阻止和错误响应不泄露路径。

### 1C-IMAGE-ASSETS

- [x] 为案件图片增加受控二进制存储、opaque asset API、签名/扩展名/容量校验、租约保护、原子落盘、恢复、损坏阻止和孤立资产清理；CaseDraft 只保存资产引用。
- [x] 工作台编辑器使用持久化图片 Hook，上传成功后才更新草稿引用；切换、刷新和后端重启后恢复，删除/替换遵循 revision，预览和正式 Word 导出读取资产接口。
- [x] 增加后端资产 API/Service/Repository 与前端 Hook 测试，覆盖恢复、跨案件隔离、租约、revision、损坏/超限拒绝、清理和错误不泄露路径。

### Phase 1 internal gates

- [x] **1C-LIVENESS** 工作台登记只在 HTTP 请求内完成来源授权/结构门控和 CaseShell/parse Task 持久化；解析执行器复用 Legacy `parse_report`，按“快速来源门控 → Parser → 草稿落库 → `review_ready`”运行，完整 SourceRecord metadata/fingerprint 在 `review_ready` 后独立复核。提交响应和审核入口不得等待完整扫描，解析执行器异常必须落为 `failed_retryable`，来源复核失败只要求重新选择来源；同一 task 不得重复执行，保留重启后的 `interrupted`/可重试恢复合同。

- [x] **1A — SharedTypes、SQLite schema/migration、Repositories**：案件壳/草稿、SourceRecord、ClientIdentity、双写结果、opaque asset 引用和 SQLite 大对象拒绝规则可持久化、迁移、回滚。
- [x] **1B — Services 和 API**：提交即建壳、解析失败/重试、来源复核与重新选择、解析/默认优先级、草稿/共享默认值双写、interrupted 重启语义和删除前置条件可通过 API 表达；定向后端回归 52 passed，保留既知配置 warning。
- [x] **1C — 工作台、自动保存和租约**：6 卡片分页、排队/解析中/失败状态、自动保存、15 秒心跳、2 分钟接管警告和分别显示保存结果；定向前端测试通过，保留 Legacy 输出链路。
- [x] **1D — 刷新/重启恢复、兼容回归和人工验收**：恢复 CaseShell/CaseDraft/Task/Source/asset/lease/归档决定；闭合解析中断、失败、重试和来源复核；在现有 Legacy 显式归档外围增加最小归档尝试中断日志和 staging/进程归属证明；不自动接管、等待、续跑或重启旧 WinRAR；不信任半成品 RAR/Manifest；完成 Legacy 解析/归档/Manifest/Word 回归和人工验收。Phase 1D 不建设持久化归档 Worker、调度器、真实进度或自动重试。

### Phase 1D — 恢复状态矩阵、最小归档边界和验证任务

**阶段目标**：在不进入 Phase 2/3/4 的前提下，让浏览器刷新、应用重启和 Legacy 显式归档中断都产生真实、可诊断、需要用户确认的状态；所有正式产物继续由现有 Legacy 门控保护。

**明确不做**：持久化归档 Worker、归档并发调度、最多 6 个任务资源准入、WinRAR 进度解析、真实百分比、分卷 replan、自动续跑、未知进程接管、旧 runtime handle 持久化、模板平台、Canonical、Shadow、USN 可信度和正式产物删除 UI。

**既有变更包协调结果**：`large-report-preview-liveness`、`report-request-liveness-fix`、`report-parsing-cache-management`、`upload-compression-toggle-fix`、`preview-export-correction`、`docx-vml-pagination`、`template-2026` 和 `support-legacy-and-new-report-formats` 作为既有 Legacy/缓存/模板兼容能力和回归输入保留，不在 Phase 1D 重复实现；`extensible-report-template-platform` 的 Canonical、Shadow、模板平台和阶段二/三候选任务保持暂停或另行处理；审核编辑、政务工作台和导出控件变更包只作为 Phase 1C 已完成能力，不重新开范围。

#### Phase 1D recovery matrix

| 对象/重启前状态 | 重启后状态 | 用户动作与门控 |
|---|---|---|
| `parse` task `queued` | task=`failed_retryable`，案件=`parse_failed_retryable` | 用户显式重试；重试前重新验证来源；不得自动重跑 |
| `parse` task `running/cancelling` | task=`interrupted`，案件=`parse_failed_retryable` | 用户显式重试；同一 task/attempt 不重复执行 |
| 案件 `review_ready` 或 parse task `succeeded` | 保持原状态 | 不重新解析；继续按来源/租约门控编辑、Word 和归档 |
| SourceRecord 后置复核未完成 | 数据库恢复后保持 `pending`；应用启动完成后由受控执行器重新调度 | 调度按 `source_id + revision` 去重；调度失败仍为 `pending` 并允许后续重试；草稿可查看/编辑 |
| 来源已确认变化或不再安全 | `requires_reselection` | 严格阻止归档；Word 允许在明确风险确认后继续导出；重新选择来源并重新解析可消除风险 |
| `archive_deferred` | 保持 `archive_deferred` | 用户以后重新选择立即压缩 |
| `archive_queued/archiving` 且无已验证正式产物 | 案件=`archive_interrupted`，归档尝试=`interrupted` | 显示上次中断；来源复核后用户再次确认；生成新 handle；不得自动执行 |
| `archive_interrupted` 且已有草稿 | 保持 `archive_interrupted` | 草稿可查看/编辑；页面显示中断提示；用户可选择稍后压缩或重新确认立即压缩 |
| `archive_interrupted` + 用户选择稍后压缩 | `archive_deferred` | 不创建新 attempt/handle，保留中断审计 |
| `archive_interrupted` + 新来源复核通过且新尝试被接受 | `archive_queued` | 创建新 attempt/new handle 后才离开中断态；失败则保持 `archive_interrupted` |
| 上一部署实例的 active lease | 失效或 `expired` | 旧 session 不再阻塞；新会话可重新获取；接管仍记审计 |
| 可证明属于本系统的未完成 staging | 标记隔离或安全清理 | 清理必须幂等；失败只留下安全诊断，不阻止案件恢复 |
| 无法证明归属的进程、目录或文件 | 保持不动并记录安全诊断 | 不终止、不删除、不以名称或 PID 推断归属 |
| 已验证 RAR、Manifest、Word | 保持并可复用 | 恢复和普通清理不得删除正式产物 |

#### Layer 0/1/2 — 恢复合同和纯规则

- [x] **1D-001** 在 `packages/shared/types/`、`packages/shared/constants/` 和 `packages/shared/utils/` 明确 `archive_interrupted` 生命周期、`ARCHIVE_RESTART_INTERRUPTED`/`SOURCE_REVALIDATION_PENDING` 错误语义、解析/归档恢复迁移、租约重启失效和最小归档 attempt record 状态；明确 `archive_interrupted` 的允许/禁止转换。不得新增 Phase 3 调度、真实进度或自动重试合同。验证：公共 DTO 不含绝对路径、PID、进程启动时间、命令行、物理 staging locator 或敏感运行输出。
- [x] **1D-001T** 增加共享类型和纯函数测试，覆盖上述状态矩阵、非法迁移、归档中断后不能直接进入 Legacy 执行、`pending` 与 `requires_reselection` 区分、lease 重启失效和恢复/清理幂等语义。数据使用 `SYNTHETIC/TEST/FIXTURE`。

#### Layer 10/11/12 — 工作台恢复展示

- [x] **1D-006** 改造案件工作台恢复展示：刷新和后端重启后从 API 恢复案件、草稿、图片、来源、任务、租约和归档决定；`archive_interrupted` 下允许查看/编辑草稿并显示上次压缩中断提示；允许用户选择稍后压缩转 deferred，或在来源复核和新 attempt/new handle 被后端接受后转 queued；不恢复旧 `archiveContextId`、旧半成品或自动压缩；不使用 localStorage 作为事实源。
- [x] **1D-006T** 增加前端测试：刷新后状态恢复、6 卡片不串案、成功案件不重解析、lease 重启后可重新获取、pending/changed 来源差异、deferred 保持、archive_interrupted 提示和新 handle 进入 Legacy。

#### Layer 20 — 持久化恢复记录

- [x] **1D-002** 扩展 Workbench repositories 和 SQLite migration：原子恢复 parse task、最小 archive attempt record、案件生命周期、SourceRecord pending 复核标记和旧 lease；数据库恢复只保留 pending，不在事务内执行来源复核；恢复必须可重复执行，正式 RAR/Manifest/Word 资产索引不参与删除或回退。
- [x] **1D-002T** 增加 repository 测试：queued/running/cancelling 矩阵、成功案件不重复解析、archive_queued/archiving 转 archive_interrupted、旧 lease 失效、pending 来源可再次发现、succeeded attempt 不回退、重复恢复和多次启动不重复写入、正式产物保护。

#### Layer 21 — 解析、来源和最小归档安全服务

- [x] **1D-003** 补齐固定的来源复核恢复流程：数据库恢复后保持未完成 SourceRecord 为 `pending`；应用启动完成后由受控执行器按 `source_id + revision` 去重重新调度；调度失败保持 `pending` 并记录 `SOURCE_REVALIDATION_PENDING`，允许后续启动或显式重试；暂时 I/O/权限/资源不可用不得直接变成来源变化，确认 fingerprint/根/链接/结构变化、来源替换或不可继续使用时才转 `requires_reselection`；不得为 `review_ready` 案件重复解析；归档和显式解析重试遵循来源可信门控。Word 不因来源状态被后端阻止，风险状态由工作台在导出时明确提示并由用户确认。
- [x] **1D-003T** 增加服务测试：启动后重新调度成功、调度失败保留 pending、同一 source/revision 多次启动幂等、暂时不可验证、确认变化、来源重新选择与重新解析、草稿仍可查看/编辑、来源变化阻止归档但不阻止经风险确认的 Word，以及 `review_ready` 不重复 Parser。
- [x] **1D-004** 在现有 Legacy `/records/archive` 调用外围登记最小归档尝试：执行前记录 attempt、输入 revision、受控 staging 标识和系统创建记录；只记录 accepted/running/succeeded/failed/interrupted 及 cleanup 结果；重启只映射未完成尝试到 `interrupted`/`archive_interrupted`，不创建 Worker、队列、进度或自动重试路径；用户重新确认并由后端接受新尝试后才创建新 handle 和新记录；已 succeeded 且 Manifest 已验证的记录不可回退。
- [x] **1D-004T** 增加归档尝试服务测试：草稿在 archive_interrupted 下可查看/编辑、稍后压缩转 deferred、立即确认前置来源复核、新 attempt/new handle 被接受后才离开中断态、旧 handle/半成品不复用、用户确认前不调用 Legacy 归档、succeeded 尝试不被恢复流程回退。
- [x] **1D-005** 建立 staging/进程归属证明和安全处理边界：清理必须同时具备受控 staging 根、不可猜测 attempt_id、数据库/受控索引归档记录、staging 内系统 ownership marker、marker 与记录/部署实例/root 匹配五项证据；证据缺失、冲突或无法确认时视为未知，不删除、不终止、不覆盖，只记录安全诊断；自有未完成 staging 可隔离或清理，半成品不注册 Manifest、不返回用户、不驱动 Word；清理失败不阻止案件恢复。
- [x] **1D-005T** 增加安全测试：五项证据全部满足时清理、缺失/冲突/marker 不匹配时未知资源不删除不覆盖、未知 WinRAR 不终止、伪造目录名/PID 不通过归属证明、半成品 RAR/Manifest 不发布、正式产物不误删、多次恢复/清理幂等、内部 PID/启动时间/locator 不进入公共 DTO 和绝对路径不泄露。

#### Legacy 兼容回归和人工验收

- [x] **1D-007** 对既有 Legacy Parser、Word builder/export、Manifest authority、archive execution、VML/分页、附件和图片门控进行合成回归；不得修改 `word_templates/template.docx`，不得引入 Canonical/Shadow 或 Phase 3 进度。
- [x] **1D-007T** 运行并补充针对性后端/前端测试，覆盖 Legacy 解析、归档失败/重试、Manifest 缺失/篡改/分卷校验、Word 内容与附件图片、路径安全和恢复状态 API；所有 fixture 明确标记 `SYNTHETIC/TEST/FIXTURE`。
- [x] **1D-008** 完成合成数据人工验收：多案件切换、刷新、关闭/重启恢复、解析失败重试、来源暂时不可验证/确认变化、租约失效、图片资产、deferred、立即归档中断、新 handle、staging 保护和正式产物保护；只保存脱敏的验收结论，不保存真实报告或生成产物。2026-07-28 验收结论：合成双案件可独立登记、解析、编辑、刷新和重载，解析/来源/租约/图片/归档中断与正式产物保护矩阵通过；失败任务仅进入可重试状态，未生成可审核草稿；未使用真实案件、报告或正式产物。

`1D-008` 只记录 2026-07-28 当时 Phase 1D 的历史合成阶段验收，不等同于
Phase 1–4 最终集成人工验收，不代表 Production Review 或 OpenSpec 归档通过。

- [x] **1D-008T** 完成定向架构检查、类型检查、相关后端/前端测试和 `git diff --check`；2026-07-28 定向结果：后端 Phase 1D 文件 3 次稳定通过、单测 5 次稳定通过，独立 PowerShell 全量后端 `642 passed, 3 skipped, 8 warnings`；前端恢复/工作台/图片资产/审核编辑/导出定向 `36 passed`；架构、类型、严格文档、资产和 diff 检查通过。用户随后在独立 PowerShell 执行 `npm.cmd run verify:full`，退出码为 `0`；后端结果为 `642 passed, 3 skipped, 8 warnings`，前端 TypeScript 与生产构建通过，`verify:docs:strict` 通过。已知非阻断 warning 为 `ARCHIVE_CONFIGURED_ROOT_INVALID` 和 Vite chunk 大于 500 kB。

#### Phase 1D independent Review remediation

首次独立 Level 3 Code Review 于 2026-07-28 未通过，报告 4 个 High、1 个 Medium 和 1 个 Low。H2 的“来源状态应由后端阻止 Word”结论经用户确认属于业务合同理解错误；正确合同是 Word 始终允许导出，`pending`/`requires_reselection` 仅要求用户在工作台明确确认风险。其余发现及 H2 风险确认体验在本节修复。原 Phase 1D 实现与验收历史保留，但 OpenSpec 归档继续阻断。

- [x] **1D-009** 核验 H1/H3/H4/M1/L1 及重新定义后的 H2 调用链，保存只含合成数据的失败回归证据；不得修改 Legacy Word 内容、模板、VML、分页或后端 Legacy 导出许可。
- [x] **1D-009T** 增加旧实现失败的回归测试：通用 lifecycle 绕过、Word 风险确认、正式 Manifest 与 attempt 提交崩溃窗口、工作台 context 省略/错配 attempt、来源 revision conflict、staging 根目录保护。
- [x] **1D-010** 在领域/服务层禁止通用 lifecycle 直接写入 `archive_queued`；受控立即归档必须在来源复核、context 和新 attempt 全部成功后原子同步 shell/draft/attempt，失败保持原状态。
- [x] **1D-011** 保持 Legacy `/records/export` 和所有来源状态下 Word 可导出；工作台在 `pending` 与 `requires_reselection` 下显示不同的明确确认，取消不导出、确认后正常调用既有导出。
- [x] **1D-012** 建立最小可恢复归档完成提交协议：正式 Manifest 持久索引通过后把身份绑定到同一 attempt；恢复时重新验证索引、case/attempt/source revision 与物理产物，可信则补记 succeeded/`archive_verified`，否则 interrupted；不得重复发布。
- [x] **1D-013** 服务端持久化工作台 context 来源及 attempt 绑定的不可逆摘要；省略、伪造、跨 attempt/case 或过期绑定均拒绝，真正 Legacy context 维持既有兼容。
- [x] **1D-014** 将来源 revision conflict 作为过期复核结果重新读取，调度、并发和临时错误不得走空 fingerprint 失效路径；真实 fingerprint 变化仍进入 `requires_reselection`。
- [x] **1D-015** staging cleanup 明确拒绝根目录，仅接受受控根的 attempt 专属直接子目录且 marker/记录/部署/root 全部匹配；其他 attempt 和未知资源保持不动。
- [x] **1D-016T** 运行各发现定向测试、Phase 1D、Legacy Parser/Word/Manifest/归档兼容、前端工作台与导出测试、后端全量、typecheck、lint:arch、严格文档、资产及 diff 检查；2026-07-28 用户在独立 PowerShell 执行 `npm.cmd run verify:full`，退出码为 `0`：后端 `650 passed, 3 skipped, 10 warnings`，前端 TypeScript 与生产构建通过，`verify:docs:strict` 通过，未出现 `KeyboardInterrupt`、测试失败或递归脚本失败。已知非阻断 warning 为 `ARCHIVE_CONFIGURED_ROOT_INVALID` 和 Vite chunk 大于 500 kB。
- [ ] **1D-017R** 完整 Harness 退出码为 0 后重新执行独立 Level 3 Code Review；无阻断性 Critical/High/Medium 后才恢复 OpenSpec 归档准备。按当前统一验收策略，本项延后到 Phase 1–4 实现、功能冻结、全量自动测试、完整 Harness 和最终集成人工验收之后执行；当前不得据历史 Harness 或阶段验收提前勾选。

#### Second independent Review remediation (2026-07-28)

第二次独立 Level 3 Code Review 于 2026-07-28 未通过：Critical 0、High 4、Medium 1、Low 1。L1 staging 安全已通过；H2 Word 导出行为符合真实业务合同，仅提示文案仍需修复。H1、H3、H4、M1 重新打开；`1D-017R` 与 OpenSpec 归档解除 gate 保持未完成。本节追加修复任务，不删除首次 Review 的实现、验证和 `1D-016T` 历史；Phase 2–4 仍未开始。当时由于本轮将继续修改代码，新的完整 Harness gate 保持未完成；后续完成状态见本节及 Review gate。

- [x] **1D-018** 封闭 `archive_queued` 的全部非法写入口：搜索并约束 controller、通用 lifecycle、Draft PATCH、archive decision repository、普通 repository、批量及内部调用；仅受控归档准备服务可创建并绑定 attempt/context、完成来源确认后迁移 shell/draft；失败保持 shell/draft 不变且不遗留有效 queued attempt/context，重复请求幂等且不创建多个有效 queued attempt。
- [x] **1D-018T** 覆盖 lifecycle 直接写入、Draft PATCH、repository 普通入口、合法归档准备、各准备步骤失败回滚/清理和重复准备幂等测试。
- [x] **1D-019** 建立统一可信完成证据验证入口：`succeed()` 不得仅凭 Manifest 字符串改变状态，必须校验 attempt 状态、Manifest 索引身份、case/attempt/source revision 绑定、正式 RAR 存在及完整性和现有正式校验信息；controller、正常执行和恢复服务共用同一完成提交标准。
- [x] **1D-019T** 覆盖不存在或错配 Manifest、RAR 缺失/损坏、source revision 错配、完整可信证据成功和重复成功幂等测试；禁止使用 fake Manifest ID 证明成功。
- [x] **1D-020** 在现有架构内增加最小可恢复正式发布协议：持久化发布意图及产物身份，使恢复可区分发布前、意图已持久化未移动、已移动未登记、索引与物理产物均可信、证据冲突/不完整；不引入 Worker、队列、调度、进度、自动续跑或进程接管。
- [x] **1D-020T** 通过崩溃注入覆盖发布意图持久化前、持久化后移动前、`os.replace` 后索引保存前、索引保存后 attempt 成功前，以及正式目录篡改/不完整；验证恢复幂等、不重复发布、不产生第二份正式 RAR/Manifest，并验证未知产物保留和重新发起新 attempt 的边界。
- [x] **1D-021** 完整绑定工作台归档的 case、attempt、source、source revision、draft revision、服务端报告身份/内容摘要、context hash 和有效状态；执行时重新读取服务端 CaseDraft/SourceRecord，工作台路径使用服务端草稿并拒绝客户端替换的 `report_json`；明确区分工作台 context 与真正 Legacy context。
- [x] **1D-021T** 覆盖准备后草稿/source revision 变化、客户端替换报告、正确绑定、context 重放/错配/过期、attempt ID 缺失及 Legacy `report_json` 兼容测试。
- [x] **1D-022** 修复 revision conflict 分类：conflict 后有限重试并重新读取 SourceRecord、重新获取/计算当前 fingerprint，与最新持久化可信 fingerprint 比较；真实变化进入 `requires_reselection`，临时访问或计算失败保持 `pending`/稳定临时失败结果，禁止旧任务覆盖新 revision。
- [x] **1D-022T** 覆盖真实文件系统或等效持久化交错下的来源变化、来源未变化、临时访问/计算失败和多次 conflict 有限终止测试。
- [x] **1D-023** 仅修正 Word 风险提示文案：`pending` 和 `requires_reselection` 均明确说明确认后仍可导出 Word，归档仍可受来源状态阻止；不增加后端 Word 禁止门控。
- [x] **1D-023T** 覆盖前端提示内容、确认后导出、取消不导出和刷新/重启后按服务端状态提示；确认 Legacy 导出兼容且没有“Word 和压缩均未开放”的文案。
- [x] **1D-024T** 完成本轮定向回归、Legacy Parser/Word/VML/分页/Manifest/Legacy archive 兼容、typecheck、lint:arch、文档/资产检查及 diff 检查；完整 Harness 已由用户在独立 PowerShell 运行并通过，才可进入新的独立 Level 3 Review。保持 `1D-017R`、OpenSpec 归档解除 gate 未完成。

本轮本地定向、后端/前端全量、typecheck、build、lint:arch、严格文档、资产和 diff 检查均已完成；完整 Harness 子门控随后由用户在独立 PowerShell 完成，故本任务已完成。

#### Third independent Review remediation (2026-07-28)

第三次独立 Level 3 Code Review 于 2026-07-28 未通过：Critical 0、High 4、Medium 1。H1 通用入口封闭、H2 Word 风险确认合同、M1 revision conflict 重算方向及 L1 staging 安全保持完成；H3 可信完成/发布恢复和 H4 并发边界重新打开。此前实现、测试、`1D-016T` 历史结果及上一轮 Harness 结果均保留；新的完整 Harness gate、`1D-017R`、独立 Review gate、OpenSpec 归档解除 gate 继续未完成，Phase 2–4 未开始。

- [x] **1D-025** 修复 `os.replace` 后、publish intent `published` 阶段落库前的恢复协议：严格校验 intent、attempt、case、source/draft/report 身份及可信 Manifest/RAR 后，允许受控地补推进 `intent_persisted -> published -> indexed`，再调用统一可信完成服务；已有 Manifest 复用不得跳过阶段迁移，不重复发布正式产物。
- [x] **1D-025T** 增加真实故障注入和幂等测试：移动完成但未标记 `published` 后重启恢复成功、不进入 `interrupted`、不产生第二份正式产物；覆盖可信 Manifest 复用和正式目录身份不匹配。
- [x] **1D-026** 强制工作台 attempt 的统一可信完成服务必须存在唯一且匹配的 publish intent，并校验 case/attempt/source revision/draft revision/report digest/目标位置、Manifest index、物理 RAR 及允许完成的发布阶段；Legacy 归档继续走独立兼容分支。
- [x] **1D-026T** 覆盖缺失或错配 publish intent、有效索引但缺少意图、完整证据成功和重复完成幂等；普通调用方不能凭 Manifest ID 直接成功。
- [x] **1D-027** 在正式发布前的不可分割服务边界内再次读取并校验服务端 CaseDraft、SourceRecord、context、attempt、case、目标身份及报告摘要；发生草稿或来源变化时不得移动、索引或成功登记正式产物。
- [x] **1D-027T** 覆盖生成期间草稿/source revision 变化、旧 report/context 绕过失败、未变化正常完成及正式目录/index 不产生。
- [x] **1D-028** 将统一可信完成提交收敛到事务内重新校验 attempt、source、draft、shell 绑定和生命周期，并对 attempt/shell/draft 更新实施恰好一行的 rowcount 保护，任一步失败整体回滚，避免状态分裂。
- [x] **1D-028T** 覆盖完成事务并发修改、shell/draft 零行更新、正常三方一致及重复完成幂等。
- [x] **1D-029** 区分发布恢复中的确认性证据冲突与临时基础设施错误；临时锁、I/O、权限、文件占用和 index 不可用不得永久写入 `conflict`，应保留当前意图阶段和产物，等待后续显式核验；确认错配/篡改才进入 `conflict`，不自动重复发布。
- [x] **1D-029T** 覆盖临时 index/文件/SQLite 错误可再次恢复、确认性身份或摘要错配进入 conflict、多次临时失败幂等且不产生第二份产物。
- [x] **1D-030T** 完成本轮定向回归、Legacy Parser/Word/VML/分页/Manifest/Legacy archive 兼容、后端/前端全量、typecheck、lint:arch、构建、严格文档、资产及 diff 检查；新的完整 Harness gate 待用户独立 PowerShell 验证后再完成，并保持 `1D-017R`、独立 Review 和归档解除 gate 未完成。
- [x] **1D-031** 修复 Windows 文件系统在同尺寸快速改写且元数据未变化时错误复用旧 selected-content fingerprint 的问题；来源内容指纹不得仅凭 size/时间/inode 元数据跳过当前字节读取。
- [x] **1D-031T** 先复现并修复 `test_selected_content_fingerprint_reuses_unchanged_bytes_and_tracks_paths`，再通过文件系统指纹、报告解析缓存、本轮 Review remediation 定向测试及后端全量测试；随后用户独立 PowerShell 执行完整 Harness 通过，退出码为 `0`。
- [x] **1D-032** 修复 `ReportParseInFlightRegistry` 在共享任务完成通知与 entry 清理之间的并发窗口，避免完成任务已退出但 registry 仍短暂报告 active，以及相关调度时序下的错误状态观察。
- [x] **1D-032T** 复现 `test_max_lifetime_bounds_wait_without_starting_duplicate_task` 的间歇性 `active_count == 1`，补充有界清理同步，并重复运行该用例 20 次及同文件定向测试（`5 passed`）。

本轮新的完整 Harness gate：已完成。此前用户于 2026-07-28 独立 PowerShell 执行 `npm.cmd run verify:full` 曾得到 `670 passed, 1 failed, 3 skipped, 12 warnings`；失败为 Windows 文件系统 selected-content fingerprint 未识别同尺寸快速改写。修复后最新完整 Harness 已由用户独立 PowerShell 重新执行并通过，退出码为 `0`，后端 `671 passed, 3 skipped, 12 warnings`，前端 TypeScript/生产构建及文档门控通过。该 gate 仅表示完整 Harness 验证通过，不表示独立 Level 3 Review 通过。`1D-017R`、独立 Level 3 Review gate、OpenSpec 归档解除 gate 保持未完成，Phase 2–4 未开始。

用户随后再次执行完整 Harness，退出码为 `1`：`670 passed, 1 failed, 3 skipped, 12 warnings`；失败为 `test_report_parse_inflight_service.py::test_max_lifetime_bounds_wait_without_starting_duplicate_task`，表现为后台任务完成清理的竞态。该问题已由 `1D-032`/`1D-032T` 修复并完成定向验证；新的完整 Harness gate仍未完成，待用户重新执行并确认退出码为 `0`。

第四次独立 Level 3 Review 于 2026-07-28 未通过：4 个 High、1 个 Medium。H1 通用生命周期入口、H2 Word 风险确认、H3-A 任意 Manifest ID 成功绕过、L1 staging 安全和 selected-content fingerprint 保持完成；重新打开 publish fence TOCTOU、重启虚假 running、发布后 failed reconciliation、SourceRecord 真实字节 fingerprint 和 Future callback 锁边界。此前任务、Review 和 Harness 历史全部保留；本轮新完整 Harness gate、`1D-017R`、独立 Review gate、OpenSpec 归档解除 gate 保持未完成，Phase 2–4 未开始。

- [x] **1D-033** 建立持久化 publish fence，并在同一数据库事务中完成最终服务端事实校验、fence 建立和 publish intent 确认；所有会改变绑定事实的写入口识别 active fence，pending verification 不永久阻塞编辑，fence 生命周期幂等且不得伪造、重复发布或留下永久 active fence。
- [x] **1D-033T** 覆盖 active fence 写入阻断或原子失效、os.replace 前 fence 失效、fence 创建失败回滚、pending verification 编辑失效旧 attempt、正常发布及重复请求幂等。
- [x] **1D-034** 修正启动恢复顺序，先失效旧 runtime context、将 accepted/running/执行中状态转为 interrupted 或内部 pending verification，再核验持久化 intent、fence、Manifest index 和正式目录；不保留虚假 running/archiving。
- [x] **1D-034T** 覆盖临时恢复错误、旧 context 失效、Shell/Draft 非运行态、正式证据保留、显式再次核验成功和不重复执行 WinRAR。
- [x] **1D-035** 以非终态 publish intent 为 reconciliation 入口，发现 failed/interrupted/pending verification attempt；publish intent 建立后不再写普通不可恢复 failed，发布后错误只进入可恢复状态或确认性 conflict。
- [x] **1D-035T** 覆盖 os.replace 后 Manifest/index/SQLite 临时失败、failed+intent 发现、再次核验成功、确认冲突、多次恢复幂等及不重复正式产物。
- [x] **1D-036** 将 SourceRecord fingerprint 改为稳定排序的路径/条目类型/实际字节摘要，使用句柄前后状态和集合前后快照检测并发变化；临时不可验证保持 pending，不使用 metadata-only 缓存。
- [x] **1D-036T** 覆盖同尺寸同 mtime 字节变化、重命名/新增/删除、遍历顺序、读取中变化、临时访问失败、M1 conflict 重算实际字节 fingerprint 和公共 DTO 不泄露路径。
- [x] **1D-037** 将 Future completing 状态与 active registry 分离；锁内移除 active entry 并登记 completing，锁外完成 Future，确保 callback 可重入且同 key 不重复 builder。
- [x] **1D-037T** 覆盖成功/异常 callback 重入 active_count、同 key run、其他 key 提交、completing 清理、单 builder 和无死锁。

本轮定向验证已完成：schema v5、第四次 Review remediation、恢复/Future 回归合计 `69 passed, 5 warnings`；Legacy Manifest/归档执行/filesystem identity 兼容回归 `35 passed`；未运行完整 Harness。新完整 Harness gate：未完成；须由用户独立 PowerShell 执行 `npm.cmd run verify:full` 并确认退出码为 `0` 后再更新。`1D-017R`、独立 Level 3 Review gate、OpenSpec 归档解除 gate 保持未完成，Phase 2–4 未开始。

用户随后独立 PowerShell 执行完整 Harness，退出码为 `1`：后端 `678 passed, 3 skipped, 12 warnings`；失败为 `tests/test_workbench_services.py::test_invalid_source_requires_reselection_without_exposing_locator`，实际返回 `pending` 而合同要求 `requires_reselection`。定向复现已通过；根因核验为普通失效来源与字节指纹读取期间专用瞬时错误的分类边界需要保持分离。该结果不完成新的完整 Harness gate；`1D-017R`、独立 Level 3 Review gate、OpenSpec 归档解除 gate保持未完成，Phase 2–4 未开始。

用户随后再次在独立 PowerShell 执行完整 Harness，输出显示退出码为 `0`：后端 `679 passed, 3 skipped, 12 warnings`；前端 TypeScript 检查与生产构建通过，Vite 仅报告 chunk 大于 500 kB；`verify:docs:strict` 通过。既有 `ARCHIVE_CONFIGURED_ROOT_INVALID` warning 保持非阻断。该结果完成本轮新的完整 Harness gate，但不等同于独立 Level 3 Review 通过；`1D-017R`、独立 Level 3 Review gate、OpenSpec 归档解除 gate保持未完成，Phase 2–4 未开始。

### Demo checkpoint 状态（2026-07-28）

本次独立 Review 结论接受为甲方 Demo checkpoint 判定：Phase 1D 为 **Demo-ready（有条件）**，不是 Production-ready；当前 `Production-ready = 否`。本结论不等同于独立 Level 3 Production Review 通过，不解除 OpenSpec 归档阻断，也不完成 `1D-017R`。历史 Demo 冒烟与阶段验收记录可以保留，但 Phase 1–4 最终集成人工验收仍未完成；允许在独立工作范围内继续甲方 Demo 后续功能，但不得宣称本 Level 3 变更包已生产完成。

#### Demo 后生产加固技术债

以下问题不进入单用户、单窗口、顺序演示的 Demo 主路径，登记为 Demo 后生产加固事项；本节不表示这些问题已修复。

- **TD-1 — Publish intent 幂等身份校验不完整（Medium）**
  - 复现条件：同一 attempt 的 publish intent 重入时，仅部分字段相同，而 source key、input fingerprint、public Manifest、source revision、draft revision、report digest 或 fence/context 身份发生变化。
  - 最坏风险：错误复用意图或把不属于当前绑定的 Manifest/正式产物关联到 attempt，造成归档身份错误。
  - 不进入 Demo 主路径原因：Demo 为单用户、单浏览器窗口，不进行归档故障重入，也不在正常归档完成前重复触发同一案件归档。
  - Demo 规避：每个案件只准备并显式归档一次；归档完成前不重复点击归档、不模拟重启或恢复。
  - 正式修复方向：已有 intent 重入时完整比较所有不可变身份字段；任一不一致立即返回 publish intent conflict。
  - 缺失测试：逐字段错配 source key、input fingerprint、public Manifest、source/draft revision、report digest、fence/context 的重入拒绝与幂等测试。
  - 计划：Demo 后生产加固阶段处理。

- **TD-2 — staging marker 移除时机偏早（Low）**
  - 复现条件：marker 已移除，但 durable intent/fence 尚未建立时发生数据库异常、进程崩溃或断电。
  - 最坏风险：留下无法由持久证据自动识别的孤儿 staging；当前安全策略不会因此误删未知资源。
  - 不进入 Demo 主路径原因：Demo 不模拟数据库异常、进程崩溃或断电。
  - Demo 规避：使用受控临时 staging；演示期间不强制终止进程、不锁定数据库、不删除 staging。
  - 正式修复方向：在 durable intent 和 active fence 成功建立后再移除 marker，或补充等效的持久归属证明。
  - 缺失测试：marker 移除前后各相邻步骤故障注入、孤儿 staging 识别和未知资源保留测试。
  - 计划：Demo 后生产加固阶段处理。

- **TD-3 — 无正式目录的失效 intent 会被重复扫描（Low）**
  - 复现条件：fence 已 invalidated、正式目录不存在，但 intent 仍处于 reconciliation 会扫描的非终态。
  - 最坏风险：长期产生无效恢复扫描和噪声；不会误发布或误删除正式/未知产物。
  - 不进入 Demo 主路径原因：Demo 不修改已进入归档准备状态的草稿，不模拟中断恢复。
  - Demo 规避：归档准备后不编辑案件、不刷新重启、不重复执行恢复核验。
  - 正式修复方向：在 fence 已 invalidated 且正式目录不存在时，将 intent 推进为明确终态。
  - 缺失测试：失效 fence、缺失正式目录、重复启动 reconciliation 的终态推进与幂等测试。
  - 计划：Demo 后生产加固阶段处理。

- **TD-4 — 应用外部修改来源目录（Medium，外部环境风险）**
  - 复现条件：应用外部的用户、同步工具或其他进程在来源复核或归档过程中修改、替换或删除来源文件。
  - 最坏风险：来源内容与服务端绑定版本不一致，归档可能被拒绝或进入待核验状态；应用内部 fence 无法阻止外部文件系统写入。
  - 不进入 Demo 主路径原因：这是应用边界外的文件系统并发，不属于单用户顺序演示合同。
  - Demo 规避：演示开始前准备合成或脱敏来源目录；演示期间保持来源目录只读，不修改、替换或删除文件。
  - 正式修复方向：明确外部文件系统变更的产品边界，补充受控目录权限/只读约束或外部变化检测与人工重选流程；不引入本变更包范围外的缓存平台。
  - 缺失测试：外部改写、替换、删除及读取中变化的端到端分类和用户提示测试。
  - 计划：Demo 后生产加固阶段处理。

- **TD-5 — 正式输出目录被外部程序修改（Medium，外部环境风险）**
  - 复现条件：RAR/Manifest 验证完成后、数据库完成提交前，外部程序打开、修改或移动正式输出目录或文件。
  - 最坏风险：物理产物与完成证据不一致，导致归档失败、待核验或冲突；现有协议不能阻止外部程序修改文件系统。
  - 不进入 Demo 主路径原因：Demo 不模拟文件锁、外部程序干预或归档期间的正式目录并发操作。
  - Demo 规避：归档期间不打开、修改或移动正在生成的正式输出目录，等待归档完成后再检查结果。
  - 正式修复方向：强化正式输出目录权限/隔离和提交前后完整性核验，明确外部程序干预后的人工处置合同。
  - 缺失测试：验证后篡改、文件锁、目录移动和恢复核验的分类、保留未知产物及不重复发布测试。
  - 计划：Demo 后生产加固阶段处理。

- **TD-6 — 真实字节 fingerprint 性能（Low）**
  - 复现条件：来源目录包含大量或大体积文件，需要完整读取字节并进行前后集合核验。
  - 最坏风险：来源复核、解析后核验或归档准备耗时增加，影响大目录交互体验；不降低当前 fingerprint 的可信度。
  - 不进入 Demo 主路径原因：Demo 使用规模受控的合成或脱敏数据，不代表生产大目录性能。
  - Demo 规避：演示前使用受控数据完成一次性能冒烟检查；不使用真实大目录作为 Demo 输入。
  - 正式修复方向：在生产加固阶段基于实际测量优化 I/O 和用户反馈；不得以 metadata-only 缓存替代当前安全算法，也不在本阶段引入 USN/Canonical/Shadow 缓存平台。
  - 缺失测试：不同文件数量、单文件大小、并发读写和失败重试下的耗时/资源基线测试。
  - 计划：Demo 后生产加固阶段处理。

#### 甲方 Demo 人工冒烟验收清单

验收数据只能使用合成或脱敏数据。每项由实际操作人勾选并记录结果；本清单通过不代表 Production-ready 或 OpenSpec 可归档。

- [ ] 启动前后端，确认使用本地 Demo 配置且没有加载真实案件、真实人员或真实运行资产。
- [ ] 创建至少两个案件，并分别选择不同的合成/脱敏报告目录。
- [ ] 分别解析两个报告，确认两个案件都进入可编辑状态。
- [ ] 编辑各自草稿并等待自动保存，确认保存结果清晰可见。
- [ ] 在两个案件之间切换，确认标题、来源、草稿字段和状态不串案。
- [ ] 为两个案件分别添加不同图片，确认图片引用属于对应案件。
- [ ] 刷新页面，确认案件、草稿和图片均可恢复。
- [ ] 预览 Word，确认预览使用当前案件内容。
- [ ] 导出 Word，确认导出成功且文件名属于当前案件。
- [ ] 检查 Word 的 VML 文本框、总页数、附件摘要第 3 页，以及附件 1/2/3 分别位于第 4/5/6 页；确认无多余空白页，默认数据摘要正确。
- [ ] 将一个案件置于 `pending` 来源状态，确认风险提示说明复核未完成，但用户确认后仍能导出 Word。
- [ ] 将另一个案件置于 `requires_reselection` 来源状态，确认出现更强风险提示，但用户风险确认后仍能导出 Word。
- [ ] 对一个状态正常且来源可信的案件执行一次显式归档。
- [ ] 检查该案件的 RAR、Manifest 和 Word 身份一致，属于同一案件且没有重复正式产物。
- [ ] 确认没有串案、错误文件名、异常页面提示或未预期的归档状态。

Demo 约束：单用户、单浏览器窗口、一次只归档一个案件；归档开始后不再编辑该案件；归档期间不修改来源目录；不重启前后端；不模拟 WinRAR 崩溃、文件锁、数据库锁、断电或极端并发；不得将 Demo 描述为生产级容灾版本。

### Phase 1D Review gate

以下未完成 gate 按统一验收策略延后到 Phase 1–4 实现后的最终集成阶段；历史阶段 Review
和 Harness 结果仅作为证据保留，不自动完成最终 Review 或解除归档阻断。

- [x] 首次/第二次 Review 的六项发现已按当时最终业务合同完成核验和回归修复；第三次 Review 修复状态见上方追加任务。
- [x] 用户独立 PowerShell 完整 Harness 退出码为 0；2026-07-28 Review 修复验证结果为后端 `650 passed, 3 skipped, 10 warnings`，前端 TypeScript/生产构建和 `verify:docs:strict` 通过。
- [x] 上一轮新的完整 Harness gate（第二次 Review remediation 历史）已完成：2026-07-28 用户在独立 PowerShell 执行 `npm.cmd run verify:full`，退出码为 `0`；后端 `661 passed, 3 skipped, 12 warnings`，前端 TypeScript 通过，前端生产构建通过，`verify:docs:strict` 通过，未出现 `KeyboardInterrupt`、测试失败或递归脚本失败。非阻断 warning 为 `ARCHIVE_CONFIGURED_ROOT_INVALID` 和 Vite chunk 大于 500 kB。
- [x] 第三次 Review remediation 的新完整 Harness gate 已完成：用户于 2026-07-28 在独立 PowerShell 执行 `npm.cmd run verify:full`，退出码为 `0`；后端 `671 passed, 3 skipped, 12 warnings`，前端 TypeScript/生产构建及文档门控通过。该记录不等同于独立 Level 3 Review 通过。
- [x] 第四次 Review remediation 的新完整 Harness gate 已完成：用户于 2026-07-28 在独立 PowerShell 执行完整 Harness，退出码为 `0`；后端 `679 passed, 3 skipped, 12 warnings`，前端 TypeScript/生产构建及 `verify:docs:strict` 通过。非阻断 warning 为 `ARCHIVE_CONFIGURED_ROOT_INVALID` 和 Vite chunk 大于 500 kB。该记录不等同于独立 Level 3 Review 通过。
- [ ] 独立 Level 3 复审无阻断性 Critical、High 或 Medium。
- [ ] OpenSpec 归档阻断解除。

### Phase 1 gate

- [x] 案件提交后立即显示案件壳卡片，解析失败卡片可重试但不可审核、归档或导出。
- [x] 用户明确修改六项字段且当前草稿成功保存后，稀疏更新共享默认值；以后新案件仅在 Parser 对应字段为空时使用共享值，当前草稿和共享默认值保存状态分别可见。
- [x] 刷新和重启后状态可恢复；`archive_deferred` 保持不变，`archive_queued/archiving` 转为 `archive_interrupted` 并等待用户重新确认；重启前 running WinRAR 不自动接管或续跑，正式产物不受影响。

### Phase 1 共享默认值最终合同修正（2026-07-29）

- [x] **T005P** 统一新案件六字段优先级为“当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值”；共享默认值只补齐 Parser 空白、缺失或空数组，已有案件不回写。
- [x] **T005PT** 增加旧实现下失败的后端回归测试，并复用前端纯规则、草稿刷新、稀疏 patch、revision conflict 和跨案件隔离测试；验证人员结构/顺序与光盘完整编号不会被共享值错误覆盖。测试有效性证据：旧实现 `2 failed, 5 passed`；最终后端定向回归 `238 passed, 3 warnings`，其中共享默认值/工作台 `41 passed, 1 warning`、Legacy Parser/Word/VML/分页 `91 passed`、Manifest/附件投影/显式归档 `106 passed, 2 warnings`；前端定向回归 `16 passed`。
- [x] **T005PV** 本次 typecheck、`lint:arch`、前端生产构建、严格文档检查、资产检查和 `git diff --check` 通过。当前状态为“实现完成、自动验证通过、等待 Phase 1–4 最终集成人工验收”。未执行前后端全量测试、完整 Harness、`1D-017R`、最终集成人工验收、最终 Review 或归档，Phase 3–5 保持未开始。

## Phase 2 — 审核顺序、人员卡片、字段来源和导出命名

**阶段目标**：让案件数组成为所有审核、正文、附件和 Word 的共同顺序源，并把来源状态显式化。

### Layer 0/2 — Contract and pure rules

- [x] **T007** 在 `packages/shared/types/` 扩展稳定 `evidence_id`、`InspectorSnapshot`、`FieldState`、来源/确认枚举和 Word 下载名称 DTO；在 `packages/shared/utils/` 新增 `naturalEvidenceOrder.ts`、`fieldProvenance.ts`、`downloadFileName.ts`。验证：旧 Legacy DTO 仍可投影。
- [x] **T007T** 在 `packages/shared/utils/*.test.ts` 覆盖检材 2/10、重复/无法识别回退、用户修改来源迁移、待确认提示状态、非法 Windows 字符、空名和 `.docx` 补全。验证：Vitest。

### Layer 10/11/12 — Review UI and export name

- [x] **T008** 改造 `packages/frontend/src/components/EvidenceEditor.tsx`、`InspectorEditor.tsx` 为拖拽/卡片交互；新增 `ReviewSourceLegend.tsx`、`WordDownloadNameDialog.tsx` 等 Phase 2 顺序/来源能力，不再创建独立的工作台字段、校验、附件或导出实现。
- [x] **T008T** 为上述组件和 Hook 增加 RTL/E2E 测试；覆盖拖拽顺序持久化、姓名/单位/警号三字段人员卡片、来源颜色与文字提示、Word 每次弹窗、取消不导出和非法名称拒绝。

### Layer 20/21 — Ordered snapshots and provenance persistence

- [x] **T009** 新增 `packages/backend/app/services/case_order_service.py`、`field_provenance_service.py`，改造 `report_parse_input_repository.py` 和 `inspector_repository.py` 的案件快照投影；只在案件创建时初始化默认顺序，保存拖拽后的数组和来源状态。
- [x] **T009T** 新增/修改 `tests/test_case_order_service.py`、`tests/test_field_provenance_service.py`、`tests/test_report_parse_input_repository.py`；覆盖报告原始顺序回退、重复编号、下游不得二次排序、人员库变化不改历史快照、图片组和人员项来源覆盖。

### Layer 21 — Legacy projection

- [x] **T010** 在 `packages/backend/app/services/legacy_report_projection_service.py` 或现有 Legacy builder 适配点统一生成正文、附件摘要、附件 1/2/3 和 Word 所需顺序投影；移除下游独立排序入口，但不改变 RAR 基础名规则。
- [x] **T010T** 在 `tests/test_legacy_report_projection_service.py`、`tests/test_record_generator_service.py` 增加合成多检材/多人员回归；验证审核顺序与正文、附件和 Word 顺序一致，来源颜色未进入 DOCX。

### Phase 2 gate

- [x] 拖拽后的案件检材/人员顺序刷新后仍一致，所有 Legacy 投影和 Word 输出共用该顺序。
- [x] 默认值、报告解析值和人工修改值可区分，待确认有文字提示并进入门控。
- [x] Word 名称按次输入且只影响下载名；服务器物理文件名安全、唯一、不可覆盖。
- [x] Phase 2 阶段状态（2026-07-29）：实现完成、自动验证通过、轻量冒烟通过；等待 Phase 1–4 最终集成人工验收。
- [ ] Phase 2 正式人工验收（并入 Phase 1–4 最终集成人工验收）；不得以本阶段合成测试或轻量冒烟替代。

## Phase 3 — 归档映射、后台归档和阶段里程碑进度

**阶段目标**：在现有正式归档安全门控外包一层可恢复任务，以持久化 `workflow_milestone` 表达真实工作流阶段，并在案件工作台每张案件卡片直接展示当前或最近归档状态；不读取 WinRAR CLI 连续百分比，不以任务化为理由削弱任何检查。

### Phase 3 prerequisite — WinRAR progress capability spike

- [x] 在进入 Phase 3 实现和验收前，使用 `SYNTHETIC/TEST/FIXTURE` 输入验证当前正式 WinRAR 版本是否能稳定提供可解释的实际进度信号；记录信号来源、解析稳定性、失败行为和百分比一致性，不记录真实案件或产物。2026-07-30 结论：当前 RAR 5.90 的控制台百分比流包含无标签回退，`-inul` Legacy 路径无进度输出，spike 未通过；详见 `winrar-progress-capability-spike.md` 和 `tests/test_winrar_progress_capability_spike.py`。
- [x] spike 未通过后的版本/适配决策已完成：2026-07-30 正式否决 RAR 5.90、RAR 7.23 x64 普通 pipe 和独立 ConPTY 的连续 CLI 百分比适配，采用固定、单调、可持久化、可恢复的 `workflow_milestone`；它只表示真实归档阶段，不表示 WinRAR 内部字节进度。禁止取最大值、钳制、平滑、过滤回退或按时间/文件/字节估算。WinRAR、RAR 分卷、Legacy 显式压缩及全部正式安全门控保持不变。该决策解除 T011 的前置阻塞，但不表示 T011–T015 已实现；实验依据见 `winrar-progress-capability-spike.md`。

### Layer 0/1/2 — Archive contracts

- [x] **T011**（依赖：Phase 3 版本/适配决策）在 `packages/shared/types/` 新增或复用 `VolumeSlot`、`DiscMapping`、`ArchivePlanSnapshot`、`ProgressSnapshot`、Legacy 压缩兼容状态、资源准入和任务取消/重试 DTO；扩展现有 `TaskRecord`，复用既有状态、阶段、`percent`、时间、错误和取消字段，补充阶段序号/总数、`progress_kind=workflow_milestone`、`updated_at`、心跳、输出分卷数/总字节、最近输出变化、Worker 持有/恢复状态和 `allowed_actions`。另定义 `ArchiveTaskCardSummary` 或等价安全投影，只含卡片需要的状态、阶段、里程碑、展示时间、紧凑活动、安全失败摘要和允许操作，不暴露全部内部字段。在 SharedConstants 固化 `0/10/20/30/75/85/90/95/100` 阶段表、Worker 状态与错误码；在 SharedUtils 实现稳定槽位 reconcile、唯一编号、合法里程碑/Worker 状态转换及卡片允许操作规则。
- [x] **T011T**（依赖：T011）在共享测试中覆盖 stable slot/Manifest 收敛、固定里程碑、非法回退/跳门控拒绝、失败/取消最后阶段、Worker 持有/恢复转换、活动指标不得换算百分比、`allowed_actions`，以及卡片摘要不含 Worker ID、内部租约、路径、堆栈、技术日志或完整进程信息。验证：Vitest/typecheck。

### Layer 10/11/12 — Archive status UI

- [x] **T012**（依赖：T011）扩展现有 `CaseCard.tsx` 和 `useTaskRecords.ts`，按需新增 `ArchiveStatusPanel.tsx`、`ArchiveVolumeMappingTable.tsx`、`ArchiveStartDialog.tsx`；不复制轮询事实源。卡片定位为归档任务摘要，默认只组织案件信息、状态/阶段、最多两行活动或状态摘要和主要操作。WinRAR 阶段突出阶段文字和 indeterminate 活动态，30% 仅作次要说明；运行态显示易读的已运行时间、分卷数、输出大小和相对最后活动时间。未归档、等待/恢复、运行、失败、取消和完成使用状态化内容替换；详情承载完整时间线、逐卷/MD5、Manifest、历史、日志和诊断。实现窄屏裁剪、长文本/大数字布局、受控按钮数量、非颜色状态文字、减少动态效果兼容和动画文字替代。
- [x] **T012T**（依赖：T012）增加 RTL/E2E 合成任务测试；至少覆盖运行中卡片四类信息和两行活动密度、大文件长期停留 WinRAR 阶段但心跳/活动摘要仍证明活跃、30% 不增长且仅为次要说明、失败/取消/恢复中/完成内容替换、未归档无空指标、刷新恢复、相对时间本地刷新不增加请求、长文号/长错误摘要/大数字、窄屏保留核心信息、减少动态效果、非颜色/非动画文字提示，以及默认卡片不泄露 Worker ID、本机路径、堆栈、日志或内部进程信息。组件测试场景对应 delta spec 的卡片主入口、状态替换、技术详情隔离和响应式/无障碍场景。

### Layer 20 — Archive metadata and process repositories

- [ ] **T013**（依赖：T011）新增 `packages/backend/app/repository/archive_plan_repository.py`、`archive_task_repository.py`、`archive_asset_repository.py`、`resource_snapshot_repository.py`；持久化计划/槽位/映射、阶段与里程碑、开始/更新/结束/心跳时间、输出总字节、分卷数、最近输出变化、Worker 持有/恢复、错误/取消、进程绑定、临时目录和正式产物索引。活动快照按受控节奏聚合写入，不为每个文件系统变化写数据库；内部诊断可比卡片摘要更完整，并提供当前/最近任务的安全投影查询。
- [ ] **T013T**（依赖：T013）新增对应 pytest；覆盖事务/版本冲突、真实阶段原子持久化、心跳与活动快照节流、输出暂不变化不自动失败/取消、失败/取消最后阶段、刷新/重启重载、Worker 恢复状态、当前/最近任务选择、内部诊断与卡片安全投影隔离、正式产物独立于案件删除和路径不泄露。

### Layer 21 — Planner, scheduler and archive worker

- [ ] **T014**（依赖：T011、T013）改造 planner 并新增 mapping/progress/scheduler/worker/resource-admission services。Worker 按受控频率写心跳，观察当前 attempt 受控 staging 中匹配分卷数量和总字节，节流更新活动摘要但不推算百分比；只在真实安全边界推进 `workflow_milestone`，WinRAR 期间固定 30。准确持久化进程退出、失败、取消和 Worker 所有权/恢复状态；服务重启后未重新取得任务所有权前保持恢复中/等待接管，取得任务记录所有权不等于连接旧 WinRAR、复用半成品或续压。保留 inventory、路径/链接/变化、WinRAR、完整性、MD5、Manifest、发布和 Legacy 显式压缩门控。
- [ ] **T014T**（依赖：T014）新增 mapping/progress/scheduler/worker service 测试；覆盖并发/资源排队、真实门控推进、WinRAR 固定 30、心跳和分卷/字节活动更新、活动停滞不单独判失败或取消、节流、进程退出/失败/取消、重启恢复/等待接管/新 Worker 所有权、旧 WinRAR/半成品不接管、重试新 attempt、Legacy 兼容及全部正式安全门控。

### Layer 22/23 — Task API

- [ ] **T015**（依赖：T011、T013、T014；对接 T012 卡片 DTO）改造 archive/record controllers 并新增 task controller/routes；提供归档决定、映射、取消/重试、任务详情/历史和进度查询。案件列表直接内嵌当前或最近归档任务的 `ArchiveTaskCardSummary`，供现有工作台轮询事实源展示阶段、里程碑、紧凑活动、展示时间、安全失败摘要和 `allowed_actions`；完整日志、历史、逐卷诊断和内部技术字段只由详情接口按安全投影返回。预览仍不创建完整 `ArchiveContext`。
- [ ] **T015T**（依赖：T015）新增 controller/route 集成测试；覆盖列表无需额外任务轮询即可取得卡片摘要、摘要信息密度和状态替换所需字段、刷新/重启恢复、取消/重试权限、安全失败投影、Manifest 未验证不显示 100/完成、列表不返回 Worker ID/租约/路径/堆栈/日志/进程信息、详情接口与列表摘要边界，以及 T012 Hook 与真实 API 对接。

### Phase 3 gate

- [x] 普通 pipe/ConPTY spike 已形成明确产品与技术决定：不读取 WinRAR CLI 连续百分比，采用 `workflow_milestone`；该项只关闭前置决策，不代表 T011–T015 或 Phase 3 验收完成。
- [ ] 归档任务最多 6 个运行，资源不足排队且显示原因；不得假装启动 6 个 WinRAR。
- [ ] `workflow_milestone` 只由真实归档阶段推进，固定、单调、持久化且刷新/重启可恢复；WinRAR 运行期间保持 30 并显示活动状态，不伪造连续百分比，同时现有 Legacy 显式压缩能力保持可用。
- [ ] 案件工作台每张案件卡片以受控信息密度直接显示当前或最近归档任务摘要；WinRAR 主要使用 indeterminate 活动态和最多两行活动信息，状态化内容、响应式和无障碍合同通过；详情扩展信息不得替代卡片主入口或泄露到列表摘要。
- [ ] 计划映射经校验后进入 Manifest，附件 3、Word 和完成状态只读取验证后的 Manifest。
- [ ] 现有正式 inventory、变化、WinRAR、完整性、MD5、Manifest 和 Word 门控全量定向回归通过。

## Phase 4 — 已审核预置模板

**阶段目标**：增加受控模板选择和复现，不建设任意模板平台，不触发压缩或 Manifest 重建。

### Layer 0/1/2 — Template contract

- [ ] **T016** 在 `packages/shared/types/` 定义 `TemplateId`、`TemplateVersionRef`、`TemplateApprovalRecord`、模板校验结果和 Word artifact validity；在 `packages/shared/constants/` 定义 approved 状态和模板错误码。
- [ ] **T016T** 在共享测试中覆盖版本指纹、未审核/未知模板拒绝、案件引用序列化、切换失效 Word 但不改变归档引用。验证：Vitest/typecheck。

### Layer 10/11/12 — Template selection UI

- [ ] **T017** 新增 `useTemplateRegistry.ts`、`TemplateSelector.tsx`，改造审核页显示 approved 模板的 ID/版本/验收摘要，保存案件模板引用并提示旧 Word artifact 失效。
- [ ] **T017T** 增加 Hook、组件和 E2E 测试；覆盖只显示 approved 版本、选择/切换、旧 Word 失效和切换不触发压缩。

### Layer 20/21 — Template registry and generator

- [ ] **T018** 新增 `packages/backend/app/repository/template_registry_repository.py`、`template_approval_repository.py`；改造 `template_profile_service.py`、`record_generator_service.py` 按案件模板版本读取受控资产并重新校验。
- [ ] **T018T** 新增 `tests/test_template_registry_repository.py`、`tests/test_template_profile_service.py`、`tests/test_record_generator_service.py`；使用合成/已审核 fixture，覆盖指纹变化、规则校验、VML/分页/表格/附件安全门控和模板切换不启动压缩。

### Layer 22/23 — Template API

- [ ] **T019** 新增模板列表/案件选择 controller 和 route，建议文件为 `packages/backend/app/controllers/template_controller.py` 和 `packages/backend/app/routes/template_routes.py`；只返回 approved 版本和安全摘要。
- [ ] **T019T** 增加 controller/route 集成测试；覆盖未知 DOCX、未审核版本拒绝、导出前重新校验、RAR/Manifest 不变和错误不泄露路径。

### Phase 4 gate

- [ ] 每个模板有独立 ID、版本、指纹、规则和验收记录，案件可复现所选版本。
- [ ] 模板切换不重新压缩、不重建 Manifest；下一次导出重新校验并生成 Legacy Word。
- [ ] 未审核或未知 DOCX 不能进入案件模板引用，现有 Word 安全门控保持通过。

## Phase 5 — 综合验收、清理和 Shadow 边界

**阶段目标**：验证五阶段合同在恢复、并发、清理和正式输出保护下闭合；Shadow 只保留暂停声明。

### Layer 0/1/2 — Retention contract

- [ ] **T020** 在 `packages/shared/types/` 和 `packages/shared/constants/` 固化案件记录/任务/临时文件/正式产物的独立清理策略、30 天默认保留期、配置项和清理结果 DTO；不得添加正式产物删除 API 合同。
- [ ] **T020T** 在共享测试中覆盖到期条件、活动任务保护、尚未导出保护、失败待重试保护和正式产物永不随案件记录清理删除。验证：Vitest。

### Layer 10/11/12 — Integrated workbench UI

- [ ] **T021** 完成案件工作台与任务、模板、来源和清理状态的后续整合；补充错误边界，不重新引入独立生成页面，也不增加 Canonical/Shadow 正式调用。
- [ ] **T021T** 增加 `tests/e2e/persistent-case-workbench.spec.ts`；使用合成多案件、多任务和合成模板覆盖刷新/重启、6 卡片分页、切换案件、唯一租约、取消后删除、顺序一致、来源状态、案件卡片 `workflow_milestone`、模板切换和产物保护。

### Layer 20/21 — Cleanup and recovery services

- [ ] **T022** 新增 `packages/backend/app/services/case_cleanup_service.py`、`artifact_retention_service.py` 和恢复编排入口；实现成功导出记录默认 30 天、配置化保留、活跃/未导出/失败案件跳过、取消后清理和案件/正式产物独立策略。
- [ ] **T022T** 新增 `tests/test_case_cleanup_service.py`、`tests/test_artifact_retention_service.py`；覆盖到期只删案件记录、不删 RAR/Manifest/Word、活跃任务保护、取消收尾、临时文件清理失败和重复清理幂等。

### Layer 22/23 — Integrated API boundary

- [ ] **T023** 完成 `packages/backend/app/controllers/`、`packages/backend/app/routes/` 的兼容适配和错误边界；确认旧 `/records/*` 仍使用 Legacy，工作台 API 只通过 SharedTypes，删除和清理接口不得触碰正式产物。
- [ ] **T023T** 增加后端集成回归；使用合成数据验证 API 恢复、任务取消、清理保护、Legacy 输出、Manifest/Word 门控和 Canonical/Shadow 未调用。

### Documentation and manual gates

- [ ] **T024** 更新 `harness/directory.md`、必要 API/数据模型文档和本变更包状态；同时记录已有活跃变更包的重叠关系、暂停项和保留依赖，确认 proposal/spec/design/tasks 与实现状态不漂移。验证：`git diff --check`、文档检查。
- [ ] **T024T** 准备人工验收清单：合成案件自动化证据 + 用户指定的真实大报告外部验证；不把真实输入、人员、路径、RAR、Manifest、DOCX 或运行输出写入仓库。完整 `verify:full` 前按 `AGENTS.md` 询问用户由谁执行。
- [ ] **T025** 进行 Level 3 独立 Code Review，重点检查持久化迁移、并发/租约、任务恢复、资源准入、正式门控、清理白名单、Legacy 兼容和 Shadow 边界。验证：审查结论和修复项回写本变更包，不进入 Canonical 或 Shadow 真实治理。

### Phase 5 gate

- [ ] 五阶段合同均有定向测试和人工验收证据，且没有依赖隐式前端状态。
- [ ] 案件记录清理和正式产物管理完全分离，首版没有误删正式 RAR、Manifest 或 Word 的路径。
- [ ] Legacy 是唯一正式输出，Shadow 真实样本治理仍暂停，Canonical 未进入生产链路。
- [ ] Level 3 verify、独立 review 和归档前状态由人类确认后再执行；本轮不提交、不推送。
