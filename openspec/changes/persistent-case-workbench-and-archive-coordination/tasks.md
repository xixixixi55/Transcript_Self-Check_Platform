# Tasks: persistent-case-workbench-and-archive-coordination

> 本文件定义后续实现顺序；Phase 1–4 已实现完成，阶段自动验证、完整 Harness 和最终集成人工验收均已通过。2026-07-30 首次最终集成人工验收发现公共 HTTP 归档任务没有运行时调度/Worker 接管，仍保持 `queued/unassigned`；2026-07-31 完成 runtime 接线、Windows 缺少 `busy_time` 的兼容降级、staging ownership marker 发布时序和工作台 autosave/revision 协调四项修复，并在 D 盘隔离环境完成真实浏览器复验。`1D-017R`、Final Review 和 2026-08-01 Production Review 均已通过；Production Review 结论适用于现有 Legacy-only、单 Windows 实例支持模型，当前已具备归档准备条件，`OpenSpec 归档阻断解除` 已按现有 gate 记录为解除。Phase 5 和 OpenSpec archive 尚未开始。TD-1/TD-2 已关闭，TD-4/TD-5 保留为环境债务，TD-3/TD-6 保留为 Low 技术债。
> 目标合同：`openspec/specs/electronic-inspection-record/spec.md`
> 设计：`design.md`

## 2026-07-31 最终集成人工验收阻塞记录（历史首次结果）

- **发现现象**：公共 HTTP 工作台创建的归档任务持续为 `queued`、`worker_state=unassigned`、`workflow_milestone=0`；直接调用现有 `ArchiveSchedulerService.claim_next` 和 `ArchiveWorkerService.run` 可以完成归档，不能替代公共主链路证据。
- **根因**：工作树中虽已构造 `ArchiveRuntimeCoordinator`，但 `packages/backend/app/main.py` 仍创建无 lifespan 的静态 FastAPI 对象，从未在正式 startup 调用 runtime `start()`；同时任务 API 尚未把新任务的已绑定 opaque context 登记到该 coordinator，且工厂传入 runtime 的构造契约未闭合。因此 HTTP 创建的 durable queued 任务没有被应用运行时接管。
- **修复**：增加惰性 `create_app`/FastAPI lifespan 启停；复用同一 Scheduler、Worker、任务仓储和资源准入；任务记录发布前登记既有 attempt/context，启动前已存在的 queued 任务可被同一服务实例接管；shutdown 使用有界等待并把未完成 claim 安全转为 interrupted，Worker 停止检查不伪造成功；未引入第二套队列、调度器或 Worker。
- **自动化证据（本轮）**：`tests/test_archive_runtime_lifecycle.py` 3 passed（启动前 queued 接管、公共 HTTP 自动接管并完成合成 Manifest 发布、单任务失败后继续处理、重复 startup、空队列退避和 shutdown）；Scheduler/Worker 回归 15 passed；工作台公共 HTTP/任务/revision/来源回归 26 passed；恢复/发布/Manifest/marker 受影响回归 66 passed，marker 唯一删除回归 1 passed；`verify:full` 通过（架构、typecheck、前端 208 tests、后端 764 passed/3 skipped、构建、严格文档），Python `compileall`、仓库资产检查、OpenSpec strict 和 `git diff --check` 通过。所有证据均为隔离合成测试；仍不替代用户人工验收。
- **历史验收状态**：本记录保留首次人工验收未通过的事实；自动测试和轻量 HTTP 冒烟当时不能替代用户重新执行受影响人工验收。2026-07-31 真实浏览器复验已完成并通过，当前结论见“Phase 1–4 最终集成人工验收记录”；`1D-017R`、最终 Review、Production Review、Phase 5 和 OpenSpec archive 仍保持未完成，不得归档、commit 或 push。

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
- [x] **1D-017R** 完整 Harness 退出码为 0 后重新执行独立 Level 3 Code Review；无阻断性 Critical/High/Medium 后才恢复 OpenSpec 归档准备。2026-08-01 完整 `verify:full` 退出码为 `0`，随后独立 Level 3 Review 结论为 `PASS`（Critical/High/Medium/Low 阻断均为 0）；本项完成，但不等同于 Final Review、Production Review、Phase 5 或 OpenSpec archive 完成。

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

#### 2026-07-31 `1D-017R` Review 后独立归档一致性加固

独立 Level 3 Review 结论为 `REJECT`，本轮只处理 M-1 至 M-4 四项 Medium 与关联 L-1：发布 intent 完整不可变身份、shutdown 有界停止后的本实例 claim 收敛、执行期间源材料一致性、正式产物发布到完成确认之间的一致性，以及 marker 与 durable intent/fence 的顺序。`1D-017R` 不在本轮重新执行，修复完成后另行独立重审。

- [x] **1D-038**（M-1）按现有数据模型补齐 publish intent 的完整不可变身份比较；缺失字段、不一致身份、不同 task/attempt/revision/计划/Manifest/所有权/fence 均安全 conflict，同一合法 intent 重入保持幂等，历史 intent 不可被后续 attempt 改写。
- [x] **1D-038T** 覆盖完整身份幂等、逐字段冲突、并发创建/恢复和既有 intent 不覆盖；临时移除完整比较防护时，关键重入测试必须失败并恢复。
- [x] **1D-039**（M-2）在 coordinator 有界 shutdown 中收敛仍属于本实例的 pending/running claim，保留 owner、attempt、task revision、lease 和 fence 条件，已 durable 完成的 attempt 不降级，其他部署实例不受影响。
- [x] **1D-039T** 覆盖正常/超时 Worker、pending/running claim、重复 shutdown、迟到完成、重启恢复、多实例隔离；临时移除超时收敛防护时，关键生命周期测试必须失败并恢复。
- [x] **1D-040**（M-3）在执行开始、产物生成后和正式发布前复核稳定源材料字节证据；变化、替换、删除、新增、截断和同大小同时间戳改写安全失败，重试重新建立证据，不污染正式资产。
- [x] **1D-040T** 覆盖多文件单文件变化、RAR 阶段/发布前变化、失败无正式 Manifest、重试新证据和稳定正常发布；临时移除源变化门控时，关键故障注入测试必须失败并恢复。
- [x] **1D-041**（M-4）闭合正式目录、Manifest/index、完成确认、恢复、复用、下载和 Word 门控之间的 intent/fence/文件集合/摘要一致性，并保护历史正式资产。
- [x] **1D-041T** 覆盖 staging/正式发布/索引前后修改、替换、删除、新增卷、Manifest 篡改、部分发布恢复和正常幂等发布；临时移除正式产物门控时，关键测试必须失败并恢复。
- [x] **1D-042**（L-1）将 marker 删除移至 durable intent/fence 建立且正式移动完成之后，确保明确发布所有者最多删除一次，并覆盖移动后崩溃恢复，不恢复重复删除问题。
- [x] **1D-042T** 覆盖 marker 成功/缺失/失败、恢复和重复发布顺序；若需要扩大公共合同，保留为独立后续风险并说明原因。
- [x] **1D-043T** 完成本轮定向测试、受影响 Runtime/Scheduler/Worker/发布/Manifest/Word/浏览器既有回归、必要的故障注入及四个 Medium 的测试有效性验证，再运行授权的完整 `verify:full`、OpenSpec strict、compileall、资产检查、diff check 和纯合成隔离归档冒烟；保持 `1D-017R`、Final Review、Production Review、Phase 5 和 archive 未完成。

#### 2026-07-31 加固验证证据（1D-038 至 1D-042T）

- **M-1 / 1D-038**：`ArchivePublishIntentRepository` 现在比较 attempt、case/source、source/draft revision、report/source/input/archive fingerprint、Manifest/正式目录、public Manifest 及 fence/context 完整身份；缺失 fence 或任一字段不一致均返回 `ARCHIVE_PUBLISH_INTENT_CONFLICT`，同一完整身份重入仍返回原 intent，不改写历史记录。逐字段冲突与并发精确重入测试 `2 passed`。
- **M-2 / 1D-039**：coordinator 有界停止后，对仍属于本实例且 revision/owner/attempt 绑定一致的 claim 使用同一事务转换为 `interrupted`；错误 owner 被忽略，已 durable succeeded 的 attempt 不降级，迟到完成和重复 shutdown 保持幂等。pending/running 参数化生命周期测试 `2 passed`，任务未出现 succeeded/100 幽灵状态。
- **M-3 / 1D-040**：源目录使用稳定目录枚举、句柄内前后 stat、内容摘要和再次枚举；执行前、Executor 返回后、Manifest 组装后/正式移动前复核同一输入证据。同大小同时间戳改写、执行后变化、发布前变化均安全返回 `ARCHIVE_INPUT_CHANGED`，不登记正式资产；恢复原输入后重试重新建立证据。执行故障注入与文件身份测试 `4 passed`。
- **M-4 / 1D-041**：Manifest registry 拒绝同 `manifest_id` 的身份重绑定；正式目录要求 Manifest 文件集合精确一致；完成、恢复、复用、结果下载均要求同 attempt 的 `verified` intent、fence、Manifest identity 和物理摘要一致。公共 TestClient 结果/下载在完成后篡改正式卷时返回 `422`，索引被标记无效，历史目录不被覆盖；正式产物门控、Manifest identity 和结果篡改测试通过。
- **L-1 / 1D-042**：marker 删除已移到 durable intent/fence 建立且 staging 移动到正式目录之后；发布所有者单次删除，缺失 marker 和崩溃后恢复删除均幂等，不恢复此前重复删除回归。真实发布顺序测试通过；本轮不扩大公共 schema 或部署合同。
- **测试有效性**：临时恢复 M-1 的旧三字段比较时，完整身份重入测试 `DID NOT RAISE` 失败；临时移除 M-2 pending 收敛时两个 timeout 参数用例仍为 `running` 而非 `interrupted`；临时移除 M-3 源变化门控时两个源变化用例 `DID NOT RAISE`；临时移除 M-4 最终物理校验时公共篡改用例收到 `200` 而非 `422`。四项实现均已恢复，恢复后关键回归 `90 passed, 5 warnings`。
- **证据边界与限制**：本轮新增证据均为自动化、`create_app + TestClient` 和纯合成临时目录；没有把服务/组件测试冒充新的浏览器人工验收，也未重复原生 Word 视觉检查。此前真实浏览器验收和原生 Word 视觉证据仍分别保留；小型合成输入只产生单卷 RAR，多分卷边界仍以既有 Harness/自动化证据为准。`ARCHIVE_CONFIGURED_ROOT_INVALID` 等既有环境/非阻断 warning 保留记录，不作为本轮安全门控通过依据。`1D-017R` 仍未勾选，等待本轮加固完成后的独立重审。
- **完整门控证据**：第一次 `verify:full` 暴露 6 个 `ReportParsingCacheService` 缓存回归，原因是共享 fingerprint 被错误扩大为强一致二次枚举；修复为通用 fingerprint 保持原语义、归档执行单独使用稳定字节/metadata 采样后，第二次 `verify:full` 退出码为 `0`，架构检查、TypeScript 类型检查、前端 `44 files / 211 tests`、后端 `785 collected / 3 skipped / 无失败`、生产构建和 `verify:docs:strict` 均通过。随后独立 `compileall`、仓库资产检查（539 个跟踪文件）、strict 文档检查、`git diff --check` 均通过；隔离纯合成公共 HTTP 自动接管轻量冒烟 `2 passed`。前端 jsdom/React `act`、Ant Design 弃用、Vite chunk 大小及后端 `ARCHIVE_CONFIGURED_ROOT_INVALID` 仍为既有非阻断警告/环境限制，未被本轮扩大或隐藏。

### Demo checkpoint 状态（2026-07-28）

本次独立 Review 结论接受为甲方 Demo checkpoint 判定：Phase 1D 为 **Demo-ready（有条件）**，不是 Production-ready；当前 `Production-ready = 否`。本结论不等同于独立 Level 3 Production Review 通过，不解除 OpenSpec 归档阻断，也不完成 `1D-017R`。历史 Demo 冒烟与阶段验收记录可以保留；Phase 1–4 最终集成人工验收已于 2026-07-31 通过，但不得据此宣称本 Level 3 变更包已生产完成。允许在独立工作范围内继续甲方 Demo 后续功能。

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

#### 当前技术债处置（2026-08-01）

- **TD-1：已关闭**。Publish intent 已使用完整身份比较，并与 task、attempt、deployment、fence 交叉校验；原段落保留为历史发现。
- **TD-2：已关闭**。Marker 删除已后置到 durable intent/fence 建立及正式原子移动之后，并由发布层承担唯一删除责任；原段落保留为历史发现。
- **TD-3：保留 Low**。无正式目录的失效 intent 仍由恢复扫描处理，当前以终态 conflict/invalidated 和幂等恢复收敛；后续可优化扫描成本。
- **TD-4：保留环境债务**。应用无法阻止外部程序修改授权来源目录，但 sealed snapshot、前后证据和 fail-closed 门控覆盖支持链路；不属于本轮代码阻断。
- **TD-5：保留环境债务**。应用无法完全阻止管理员级正式目录篡改，但 Manifest、MD5、SQLite 身份和公共下载/复用校验会拒绝不一致结果；不属于本轮代码阻断。
- **TD-6：保留 Low**。真实字节 fingerprint 的性能优化仍需生产规模基线，不得以 metadata-only 缓存替代当前安全算法。

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
- [x] 独立 Level 3 复审无阻断性 Critical、High 或 Medium；2026-08-01 复审结果为 Critical/High/Medium/Low 均为 0。

#### 2026-08-01 Final Review 结果（remediation 后）

- **审查基线与范围**：基线为 `1ffd6ba7b4b24cb894a75263f64b54c27ddadf3c`，当前 `HEAD` 为 `de36694e0e84aaf83360db933cdba6ecdbf7ec1f1`；remediation diff 为 8 个预期文件、`+251/-92`，只复核前次四项阻断及其直接回归，不重新打开 `1D-017R`、M-1 至 M-4B/L-1，不扩大产品合同。
- **retry 公共投影**：公共 retry 响应仅返回安全 `task` projection；代码和已通过的工作台、runtime/attempt/worker/persistence 回归确认不含 `archive_context_id`、`archive_attempt_id`、fence、lease、owner、内部路径或其他持久化绑定字段。请求模型继续拒绝内部绑定字段；新 attempt 创建、revision、lease、冲突/失败和 Runtime/Scheduler/Worker 接管合同保持不变，前端仍只消费 `data.task`。
- **change/living strict 与 schema v10**：`openspec validate persistent-case-workbench-and-archive-coordination --strict --no-interactive` 通过；`openspec validate --specs --strict --no-interactive` 为 `1 passed, 0 failed`；Phase 1D delta Scenario 具有实际中断、不可虚假成功、半成品不得正式发布及既有恢复/完整性门控语义。living spec 已具备 `## Purpose`/`## Requirements` 和合法 Requirement/Scenario 层级，data model 记录 schema v10 及已批准的 sealed snapshot、deployment owner、publication generation 和 Manifest durable/projection 边界。
- **状态合同**：proposal、design 和本节当前状态一致：Phase 1–4、完整 Harness、最终集成人工验收和 `1D-017R` 已完成；前次 Final Review 因四项问题为 `REJECT`，remediation 已完成，本次复审判定 `Final Review = PASS`；当前允许进入 Production Review，但 Production Review、Phase 5 和 OpenSpec archive 尚未开始。
- **额外只读检查**：`npm.cmd run verify:docs:strict` 通过，`git diff --check` 通过。前次已提交的定向测试、授权环境 `verify:full` 和独立 remediation Review 证据与当前 HEAD 一致，本轮未重复执行测试、Harness、浏览器或 Word 视觉检查。
- **非阻断说明**：既有 `ARCHIVE_CONFIGURED_ROOT_INVALID`、UI/Vite 警告以及 TD-3、TD-4、TD-5、TD-6 仍按已批准边界记录为非阻断技术债/环境债务；未发现 Critical、High 或阻断性 Medium，也未发现本次 remediation 直接引入的支持链路回归。

#### 2026-08-01 Production Review 结果

- **实际 gate 与基线**：当前 `tasks.md` 没有独立的 Production Review 任务编号；本轮使用既有 `Phase 1D Review gate`、其前置的 Phase 1–4/完整 Harness/最终集成人工验收/`1D-017R`/Final Review 证据，以及同 gate 的 `OpenSpec 归档阻断解除` checkbox。审查基线为 `HEAD=072cc50e5f14f0b8d8ffe5a55619b45dd75330a0`，只做部署准备、运行生命周期、资产边界、恢复升级和运维证据核对，不重新打开 M-1 至 M-4B/L-1，不开始 Phase 5 或 archive。
- **支持部署模型**：单个 Windows 应用实例、单个 FastAPI 进程、单个前端和该实例拥有的 in-process Scheduler/Worker；每个 deployment 独占应用安装目录、SQLite 数据根、`packages/output`、`compressed/.staging` 和 `.inputs`。不支持共享 SQLite/输出根、多节点、远程数据库、共享 NAS、对象存储或管理员级篡改防御。
- **部署与配置合同**：`design.md` 第 13 节已补齐当前实际的 Node/pnpm/Python/requirements、WinRAR/RAR 分卷、officecli、前端 build/preview、后端 uvicorn 启停命令、端口、Windows ACL 和全部现有 `BIJI_*` 关键配置。输入根无效时 readiness/授权 fail-closed；数据根无效不回退默认根；输出根为安装目录固定根且无替代根；WinRAR 不可用返回 `WINRAR_UNAVAILABLE`，不降级为 ZIP；非法资源/运行时阈值不静默降低门控。
- **生命周期与资产结论**：FastAPI lifespan 统一启动/有界停止 runtime；重复 startup、空队列、Windows 缺少 `busy_time`、单任务失败、取消、重启恢复、stale revision/fence、durable succeeded 和未知 staging 均符合既有合同。SQLite schema v10 是 durable 权威；sealed input、marker、staging、publication generation、RAR、Manifest、JSON index、Word 和下载链路的边界、权限和 fail-closed 行为均已记录。前端/API 只显示稳定错误码和摘要，不暴露路径、栈、token、fence、lease、attempt/context 或内部 locator。
- **备份/恢复/升级/回滚结论**：已记录停止一致状态后同时备份匹配的 SQLite、正式 RAR/Manifest、Word、模板和 deployment 资产；不以 JSON index 单独备份或恢复；staging/未完成 snapshot/cache 不能提升为成功。恢复要求匹配 deployment/database/output/template，缺失或不一致保持 interrupted/failed/conflict。schema v10 迁移为事务门控且失败回滚；旧代码不能打开 v10，Git 回退不等于数据回滚。
- **诊断与容量结论**：`/health`、`/api/v1/demo/readiness`、任务状态/里程碑和安全进程日志足以支持当前单机模型；集中监控和内建日志轮换登记为非阻断运维债务。sealed snapshot、staging、RAR、Manifest、Word 和 temp 的峰值容量、`135 GB` 输入上限、D 盘/正式数据盘要求及 TD-3/TD-4/TD-5/TD-6 均已准确记录；4GB 双卷、22GB 单卷证据与延期的大容量人工验收未被夸大为已完成能力。
- **风险接受与结论**：按照本轮指定的当前 Legacy-only 支持模型，未完成的大容量人工验收/TD-6 只约束未声明支持的规模，不阻断本次单机部署准备；仍保留 `REQ-018` 的容量边界和延期记录。未发现正式支持主链路中的 Critical、High 或阻断性 Medium，未发现配置/运行/资产/恢复与实际代码的阻断性矛盾，Production Review = `PASS`。因此既有 gate 的 `OpenSpec 归档阻断解除` 可记录为 `[x]`；这不等同于执行 Phase 5 或 OpenSpec archive。
- **状态**：`1D-017R` 已通过；Final Review 已通过；Production Review 已通过；`OpenSpec 归档阻断解除` 已勾选；Phase 5 和 OpenSpec archive 尚未开始。

- [x] OpenSpec 归档阻断解除。

### Phase 1 gate

- [x] 案件提交后立即显示案件壳卡片，解析失败卡片可重试但不可审核、归档或导出。
- [x] 用户明确修改六项字段且当前草稿成功保存后，稀疏更新共享默认值；以后新案件仅在 Parser 对应字段为空时使用共享值，当前草稿和共享默认值保存状态分别可见。
- [x] 刷新和重启后状态可恢复；`archive_deferred` 保持不变，`archive_queued/archiving` 转为 `archive_interrupted` 并等待用户重新确认；重启前 running WinRAR 不自动接管或续跑，正式产物不受影响。

### Phase 1 共享默认值最终合同修正（2026-07-29）

- [x] **T005P** 统一新案件六字段优先级为“当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值”；共享默认值只补齐 Parser 空白、缺失或空数组，已有案件不回写。
- [x] **T005PT** 增加旧实现下失败的后端回归测试，并复用前端纯规则、草稿刷新、稀疏 patch、revision conflict 和跨案件隔离测试；验证人员结构/顺序与光盘完整编号不会被共享值错误覆盖。测试有效性证据：旧实现 `2 failed, 5 passed`；最终后端定向回归 `238 passed, 3 warnings`，其中共享默认值/工作台 `41 passed, 1 warning`、Legacy Parser/Word/VML/分页 `91 passed`、Manifest/附件投影/显式归档 `106 passed, 2 warnings`；前端定向回归 `16 passed`。
- [x] **T005PV** 本次 typecheck、`lint:arch`、前端生产构建、严格文档检查、资产检查和 `git diff --check` 通过。历史阶段状态为“实现完成、自动验证通过、等待 Phase 1–4 最终集成人工验收”；该验收已于 2026-07-31 通过。`1D-017R`、最终 Review、Production Review、OpenSpec archive 和 Phase 5 仍未完成。

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
- [x] Phase 2 阶段状态（2026-07-29）：实现完成、自动验证通过、轻量冒烟通过；最终人工结论并入 2026-07-31 Phase 1–4 最终集成人工验收。
- [x] Phase 2 正式人工验收（并入 Phase 1–4 最终集成人工验收）：2026-07-31 随最终集成范围通过；本项结论不以本阶段合成测试或轻量冒烟替代。

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

- [x] **T013**（依赖：T011）新增 `packages/backend/app/repository/archive_plan_repository.py`、`archive_task_repository.py`、`archive_asset_repository.py`、`resource_snapshot_repository.py`；持久化计划/槽位/映射、阶段与里程碑、开始/更新/结束/心跳时间、输出总字节、分卷数、最近输出变化、Worker 持有/恢复、错误/取消、进程绑定、临时目录和正式产物索引。活动快照按受控节奏聚合写入，不为每个文件系统变化写数据库；内部诊断可比卡片摘要更完整，并提供当前/最近任务的安全投影查询。
- [x] **T013T**（依赖：T013）新增对应 pytest；覆盖事务/版本冲突、真实阶段原子持久化、心跳与活动快照节流、输出暂不变化不自动失败/取消、失败/取消最后阶段、刷新/重启重载、Worker 恢复状态、当前/最近任务选择、内部诊断与卡片安全投影隔离、正式产物独立于案件删除和路径不泄露。

### Layer 21 — Planner, scheduler and archive worker

- [x] **T014**（依赖：T011、T013）改造 planner 并新增 mapping/progress/scheduler/worker/resource-admission services。Worker 按受控频率写心跳，观察当前 attempt 受控 staging 中匹配分卷数量和总字节，节流更新活动摘要但不推算百分比；只在真实安全边界推进 `workflow_milestone`，WinRAR 期间固定 30。准确持久化进程退出、失败、取消和 Worker 所有权/恢复状态；服务重启后未重新取得任务所有权前保持恢复中/等待接管，取得任务记录所有权不等于连接旧 WinRAR、复用半成品或续压。保留 inventory、路径/链接/变化、WinRAR、完整性、MD5、Manifest、发布和 Legacy 显式压缩门控。
- [x] **T014T**（依赖：T014）新增 mapping/progress/scheduler/worker service 测试；覆盖并发/资源排队、真实门控推进、WinRAR 固定 30、心跳和分卷/字节活动更新、活动停滞不单独判失败或取消、节流、进程退出/失败/取消、重启恢复/等待接管/新 Worker 所有权、旧 WinRAR/半成品不接管、重试新 attempt、Legacy 兼容及全部正式安全门控。

### Layer 22/23 — Task API

- [x] **T015**（依赖：T011、T013、T014；对接 T012 卡片 DTO）改造 archive/record controllers 并新增 task controller/routes；提供归档决定、映射、取消/重试、任务详情/历史和进度查询。案件列表直接内嵌当前或最近归档任务的 `ArchiveTaskCardSummary`，供现有工作台轮询事实源展示阶段、里程碑、紧凑活动、展示时间、安全失败摘要和 `allowed_actions`；完整日志、历史、逐卷诊断和内部技术字段只由详情接口按安全投影返回。预览仍不创建完整 `ArchiveContext`。
- [x] **T015T**（依赖：T015）新增 controller/route 集成测试；覆盖列表无需额外任务轮询即可取得卡片摘要、摘要信息密度和状态替换所需字段、刷新/重启恢复、取消/重试权限、安全失败投影、Manifest 未验证不显示 100/完成、列表不返回 Worker ID/租约/路径/堆栈/日志/进程信息、详情接口与列表摘要边界，以及 T012 Hook 与真实 API 对接。

### Phase 3 gate

- [x] 普通 pipe/ConPTY spike 已形成明确产品与技术决定：不读取 WinRAR CLI 连续百分比，采用 `workflow_milestone`；该项只关闭前置决策，不代表 T011–T015 或 Phase 3 验收完成。
- [x] 归档任务最多 6 个运行，资源不足排队且显示原因；不得假装启动 6 个 WinRAR。
- [x] `workflow_milestone` 只由真实归档阶段推进，固定、单调、持久化且刷新/重启可恢复；WinRAR 运行期间保持 30 并显示活动状态，不伪造连续百分比，同时现有 Legacy 显式压缩能力保持可用。
- [x] 案件工作台每张案件卡片以受控信息密度直接显示当前或最近归档任务摘要；WinRAR 主要使用 indeterminate 活动态和最多两行活动信息，状态化内容、响应式和无障碍合同通过；详情扩展信息不得替代卡片主入口或泄露到列表摘要。
- [x] 计划映射经校验后进入 Manifest，附件 3、Word 和完成状态只读取验证后的 Manifest。
- [x] 现有正式 inventory、变化、WinRAR、完整性、MD5、Manifest 和 Word 门控全量定向回归通过。
- [x] Phase 3 阶段状态（2026-07-30）：实现完成、自动验证通过、轻量冒烟通过；2026-07-31 受影响主链路真实浏览器复验通过。
- [x] Phase 3 正式人工验收（并入 Phase 1–4 最终集成人工验收）：2026-07-31 通过真实工作台/公共 HTTP、Scheduler/Worker 自动接管、阶段里程碑、RAR、Manifest、MD5、取消/重试和停止/重启恢复复验；不得以本阶段合成测试或轻量冒烟替代。

## Phase 4 — 已审核预置模板

**阶段目标**：增加受控模板选择和复现，不建设任意模板平台，不触发压缩或 Manifest 重建。

### Layer 0/1/2 — Template contract

- [x] **T016** 在 `packages/shared/types/` 定义 `TemplateId`、`TemplateVersionRef`、`TemplateApprovalRecord`、模板校验结果和 Word artifact validity；在 `packages/shared/constants/` 定义 approved 状态和模板错误码。
- [x] **T016T** 在共享测试中覆盖版本指纹、未审核/未知模板拒绝、案件引用序列化、切换失效 Word 但不改变归档引用。验证：Vitest/typecheck。

### Layer 10/11/12 — Template selection UI

- [x] **T017** 新增 `useTemplateRegistry.ts`、`TemplateSelector.tsx`，改造审核页显示 approved 模板的 ID/版本/验收摘要，保存案件模板引用并提示旧 Word artifact 失效。
- [x] **T017T** 增加 Hook、组件和 E2E 测试；覆盖只显示 approved 版本、选择/切换、旧 Word 失效和切换不触发压缩。仓库当前没有 Playwright 依赖或可执行 E2E harness，使用可执行的 Hook 单测、组件 RTL 和页面级 HTTP 流程集成测试覆盖同一场景；不以不可运行的伪 E2E 文件替代证据。

### Layer 20/21 — Template registry and generator

- [x] **T018** 新增 `packages/backend/app/repository/template_registry_repository.py`、`template_approval_repository.py`；改造 `template_profile_service.py`、`record_generator_service.py` 按案件模板版本读取受控资产并重新校验。
- [x] **T018T** 新增 `tests/test_template_registry_repository.py`、`tests/test_template_profile_service.py`、`tests/test_record_generator_service.py`；使用合成/已审核 fixture，覆盖指纹变化、规则校验、VML/分页/表格/附件安全门控和模板切换不启动压缩。

### Layer 22/23 — Template API

- [x] **T019** 新增模板列表/案件选择 controller，并接入现有 `packages/backend/app/routes/workbench_routes.py`，避免建立平行工作台路由事实源；只返回 approved 版本和安全摘要。
- [x] **T019T** 增加 controller/route 集成测试；覆盖未知 DOCX、未审核版本拒绝、导出前重新校验、RAR/Manifest 不变和错误不泄露路径。

### Phase 4 gate

- [x] 每个模板有独立 ID、版本、指纹、规则和验收记录，案件可复现所选版本。
- [x] 模板切换不重新压缩、不重建 Manifest；下一次导出重新校验并生成 Legacy Word。
- [x] 未审核或未知 DOCX 不能进入案件模板引用，现有 Word 安全门控保持通过。
- [x] Phase 4 阶段状态（2026-07-30）：实现完成、自动验证通过、轻量冒烟通过；2026-07-31 受影响主链路真实浏览器复验通过。
- [x] Phase 4 正式人工验收（并入 Phase 1–4 最终集成人工验收）：2026-07-31 通过真实工作台模板/Word 相关流程和最终集成范围复验；不得以本阶段合成测试或轻量冒烟替代。

### Phase 1–4 最终集成人工验收记录（2026-07-30 首次失败；2026-07-31 复验通过）

- [x] 修复正式归档发布中 staging ownership marker 被执行层和发布层重复删除的直接集成回归；发布层保持唯一删除所有者，定向测试、受影响回归和重新执行的完整 Harness 通过。
- [x] 使用 D 盘隔离目录、纯合成案件和受控模板完成 API、持久化、模板治理、revision 冲突、Word artifact 失效、正式 Word、Legacy/VML/6 页分页、附件顺序、真实 WinRAR、RAR inventory/完整性/MD5/Manifest/发布链路核验；验收资产已清理，未进入仓库。
- [x] 模板未知、未审核、指纹不匹配和规则失败均被稳定安全错误拒绝；正式生成前会重新校验当前模板，失败时不生成看似成功的 Word。
- [x] Phase 3/4 及 Phase 1–4 最终集成人工验收：2026-07-30 首次真实 HTTP 验收发现任务持续为 `queued`/`unassigned`，原因是正式应用生命周期未接入现有 Scheduler/Worker；2026-07-31 补齐四项修复后，在 D 盘隔离环境由真实工作台/公共 HTTP 创建纯合成归档任务，任务自动经历 `queued/unassigned/0` 到归档阶段并达到 `succeeded/released/100/completed`。取消不虚假成功，重试创建新 attempt，停止/重启后已有任务安全恢复；RAR、inventory、完整性、MD5、Manifest、光盘映射和 staging marker 发布均通过。
- [x] 浏览器视觉及输出边界验收：2026-07-31 真实浏览器完成编辑光盘编号后立即压缩、快速连续点击、取消/重试、停止/重启和双会话 revision 冲突复验；页面不再出现要求刷新重试的 409，真实冲突仍安全拒绝且不创建归档任务。原生 Word 视觉检查作为独立证据已完成；本次小型纯合成输入只生成单卷 RAR，多分卷边界由 Harness/自动化覆盖，不冒充多分卷人工视觉验收。首次 Codex 浏览器不可用属于历史环境限制，不覆盖本次真实浏览器证据。
- [x] 四项修复收口：运行时 coordinator 接入正式应用 lifespan；Windows 缺少 `busy_time` 时以 `io_busy_percent=None` 跳过可选 I/O 阈值而不伪造 `0%`；staging ownership marker 由发布层保持唯一删除所有者；工作台立即归档先等待 autosave、`PATCH → reload detail → archive decision` 使用最新 revision，并由 `archiveDecisionInFlight` 与服务端唯一活动任务门控防止重复计划/任务。

### Windows Archive Runtime 兼容修复（2026-07-31）

- **发现现象**：真实 Windows 启动时，`psutil.disk_io_counters()` 返回合法的 `sdiskio`，但对象只有 `read_time`/`write_time` 等字段而没有 `busy_time`；`ArchiveRuntimeResourceProvider._io_busy_percent()` 无条件访问该字段，导致每次 Scheduler 迭代抛出 `AttributeError`。Coordinator 虽安全捕获并等待下一轮，但公共 HTTP 创建的任务无法被接管。
- **合同核对**：现有 `ArchiveResourceSnapshot` 只有数值型 `io_busy_percent`，不能表达可选指标不可用；资源准入必须继续保护空间、CPU、输入规模、WinRAR 进程数、并发、租约和所有权等既有门控。
- **修复语义**：`io_busy_percent=None` 明确表示 I/O 忙碌指标不可用。Windows 缺少 `busy_time` 或 `disk_io_counters()` 返回 `None` 时，采样器不读取不存在的属性、不从 `read_time`/`write_time` 伪造百分比，并清空连续采样基线；准入只跳过 I/O 忙碌阈值，其他门控继续生效。不可用诊断按 ResourceProvider 生命周期限流，避免每轮刷屏。

- [x] **WIO-001** 修改 `ArchiveResourceSnapshot`、资源准入和 `ArchiveRuntimeResourceProvider`，支持不可用 I/O 指标；保持存在 `busy_time` 平台的初始化、时间差为零和计数器重置行为，不新增第二套采样器、Scheduler 或 Worker。
- [x] **WIO-001T** 增加合成测试：`disk_io_counters()` 为 `None`、Windows 风格 `sdiskio` 缺少 `busy_time`、存在 `busy_time` 的既有采样、连续采样初始化/零时间差/计数器重置、不可用指标下 Scheduler 不永久失败或忙循环，以及正式 `create_app + TestClient + 公共 HTTP` 生命周期自动接管 queued 任务；继续运行 shutdown、重复 startup、单任务失败、marker 唯一删除、取消、租约、revision、恢复、Manifest 和发布门控回归。测试数据必须为 `SYNTHETIC/TEST/FIXTURE`。
- [x] **WIO-001V** 通过“恢复无条件 `busy_time` 访问后 Windows 兼容测试失败”的测试有效性验证；完成定向测试、Runtime/Scheduler/Worker/资源准入/公共 HTTP 回归、取消/恢复/发布/Manifest/marker 回归、真实 Windows 轻量启动、`verify:full`、OpenSpec strict、Python `compileall`、仓库资产检查和 `git diff --check`。相关真实浏览器复验随后于 2026-07-31 通过 Phase 3/4 及 Phase 1–4 最终集成验收；`1D-017R`、最终 Review、Production Review、OpenSpec archive 和 Phase 5 仍未完成。

- **自动化与真实运行证据（2026-07-31）**：资源采样/Runtime 生命周期定向 `9 passed`；资源、Scheduler、Worker、Runtime、公共 HTTP、取消、租约、revision 和任务回归 `74 passed, 3 warnings`；恢复、发布、Manifest、marker、Legacy 归档门控及来源回归 `80 passed, 5 warnings`；架构检查和 TypeScript typecheck 通过。将无条件 `busy_time` 访问临时恢复后，Windows 兼容用例按预期以 `AttributeError` 失败，修复已恢复。真实 Windows `pnpm dev` 以指定 `BIJI_ALLOWED_INPUT_ROOTS` 启动，公共 HTTP 纯合成任务最终观察到 `queued/unassigned/0 → succeeded/released/100/completed`；日志仅有一次 `ARCHIVE_IO_METRIC_UNAVAILABLE`，无 `busy_time`/`AttributeError`/Scheduler 迭代异常；服务进程树有界停止，合成输入、RAR、Manifest 索引记录、隔离数据库、日志和临时资产已清理。`verify:full` 退出码 `0`（前端 `208 passed`，后端全量 `773 collected` 无失败）；OpenSpec strict、Python `compileall`、仓库资产检查和 `git diff --check` 均通过。以上是自动化和真实运行证据，与下方真实浏览器人工验收及原生 Word 视觉检查分别记录。

### 工作台立即归档 revision 竞态修复与浏览器复验（2026-07-31）

- **人工发现的操作时序**：真实工作台直接编辑光盘编号，在 debounce/autosave 完成前点击“立即开始压缩”，旧实现先完成草稿 PATCH，随后用页面缓存的旧 `CaseDetail.shell.revision` 提交归档决策，公共接口返回 HTTP 409；页面只能提示“压缩决策未完成，请刷新案件后重试”。
- **根因分类**：主因是归档提交读取陈旧 revision；保存成功后草稿 revision 已更新，但本地 `CaseDetail.shell.revision` 没有同步更新。旧路径还只在 `hasPending` 判断为真时调用 `saveNow()`，不能把立即操作统一建模为“先确认保存”。光盘编号没有第二套本地状态，后端 draft/shell 原子 revision、租约、编号校验和归档计划事实源均保持不变。
- **修复合同**：立即归档路径无条件等待现有 autosave 的在飞请求或当前待保存 patch；保存失败、租约失败或真实冲突直接终止，不发送归档决策。保存后通过既有 `reloadDetail` 读取服务端权威 `CaseDetail.shell.revision`，归档决策只使用该 revision，并在成功后重新加载详情；不新增 revision/保存队列。`archiveDecisionInFlight` 只抑制同一次点击并发，服务端仍以 revision/租约/唯一活动任务门控拒绝真实冲突。
- **自动化证据**：新增页面级公共 HTTP 交互测试 `3 passed`（旧实现恢复为旧 revision 后关键竞态用例 `2 failed`，断言从期望 `6` 回退为 `5`）；新增后端公共 TestClient 流程 `1 passed`；工作台/autosave/session/归档规则前端定向 `25 passed`，工作台控制器/持久化后端定向 `47 passed`。随后前端全量 `44 files / 211 tests`、后端全量 `774 collected`、`verify:full` 均通过。
- **真实浏览器与公共 HTTP 证据**：D 盘隔离环境、纯合成报告和真实 `pnpm dev` 下，浏览器未等待编辑 `SY20260731-002` 后立即点击压缩，服务日志顺序为 `PATCH draft 200 → GET case detail 200 → POST archive-decision 200`，页面显示“已进入等待归档”，无 409/刷新提示；任务由 Scheduler/Worker 自动接管并达到 `succeeded / completed / 100 / released`。公共结果、实际 RAR 和 Manifest 的 MD5 均为 `e7d8db6e3234f3b10669539aba1b827e`，Manifest 光盘编号为 `SY20260731-002`，ownership marker 发布通过且无重复删除错误。快速连续点击的真实页面公共历史仅有 `1` 个 task、`attempt=1`，最终成功。
- **真实并发冲突证据**：两个浏览器会话同时打开同一纯合成案件；第二会话保持只读并记录租约冲突，随后通过其公共 Draft API 将 revision 从 `1` 保存为 `2`。第一会话仍持有旧草稿，立即压缩时保存请求返回 HTTP 409；页面显示“案件版本发生冲突，当前输入未覆盖服务端新版本”，没有刷新提示、没有 archive-decision 请求、公共归档历史为 `0`，服务端 revision 和租约合同继续生效。
- **状态保持**：本记录补充竞态缺陷、修复和最终复验证据；Phase 3/4 正式人工验收及 Phase 1–4 最终集成人工验收已于 2026-07-31 通过。`1D-017R`、Final Review、Production Review、OpenSpec archive 和 Phase 5 仍未完成。

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

## 2026-08-01 第二轮独立 Review 安全加固（实现完成，门控后独立重审通过）

本轮基线为本地提交 `ac49518` 及其相对 `origin/codex/demo-next-stage` 的完整实现。第二次独立 Level 3 Review 结论为 `REJECT`：Critical 0、High 0、Medium 5（M-1、M-2、M-3、M-4A、M-4B）和 Low 1（L-1）。以下任务在实现阶段只修复这些阻断项及关联 marker owner；当时 `1D-017R` 保持未勾选，修复后另行独立重审。2026-08-01 门控后的独立重审已完成并通过，当前状态见下方最终记录。

- [x] **1D-044** 在本变更包中固化“sealed execution input”和“durable publication generation”两个安全边界，明确 SQLite 事实源、派生 index、共享 deployment owner、磁盘快照成本和旧记录兼容策略；不以离散源目录扫描或完成前最后一次 MD5 作为完整证明。
- [x] **1D-045**（M-1）补齐 task-bound intent/fence/attempt/publication 身份链和 schema migration；服务层一次性绑定 task/attempt，公共 API 不接受内部绑定字段，跨 task/staging/intent/recovery 复用安全拒绝，缺 task 身份的旧记录按冲突/恢复策略处理。
- [x] **1D-046**（M-2）让 bounded shutdown 基于当前 task revision、deployment owner、worker owner、attempt、lease/fence 做有界 CAS 收敛；revision 竞争重读重试，所有权转移和 durable succeeded 不降级，共享 SQLite recovery/active-fence normalization 只处理当前 deployment。
- [x] **1D-047**（M-3）实现 task/attempt 所有的 copying→verified→sealed 输入快照；逐文件复制、链接/reparse 防护、完整集合/大小/摘要验证、取消/崩溃/失败清理和新 attempt 隔离；WinRAR 实际读取 sealed 快照而非外部源目录。
- [x] **1D-048**（M-4A）实现 task-bound publication generation seal、同文件系统原子移动、受保护/read-only 边界、durable publication 摘要及完成事务内的 attempt/task succeeded 提交；恢复只完成同一 intent/fence/generation，历史正式资产不覆盖。
- [x] **1D-049**（M-4B）把 SQLite durable intent/publication 作为 Manifest index 唯一事实源；损坏/缺失/结构异常 index fail-closed 或从可信事实重建，加入跨进程锁、flush/fsync、原子替换和并发追加保护，index 失败不得报告成功。
- [x] **1D-050**（L-1）将 marker 绑定 task/attempt/deployment/root/token，并在删除前通过 durable intent `fence_id` 与当前 DB fence 交叉验证发布所有权；正式移动后仅发布层删除一次，同一合法重入的已删除 marker 幂等成功，身份不匹配不得删除。
- [x] **1D-051T** 为每个阻断项先加入可在修复前失败的真实故障注入，再完成 repository/service/controller/recovery/多 deployment/Windows 文件系统回归和测试有效性验证；仅使用合成数据；实现阶段保持 `1D-017R`、Final Review、Production Review、Phase 5 和 archive 未完成，待门控后的独立重审另行收口。

### 本轮实现与验证证据（2026-08-01）

- **安全边界与 schema**：`archive_input_snapshots` 持久化 copying→sealed→cleaned/invalidated 状态；seal 前完成并记录逐文件集合、大小和内容摘要校验，校验事实不是额外的持久化状态。WinRAR、inventory、RAR 和 Manifest 只读取 sealed 快照。SQLite schema/migration 升至 v10，补齐 task/deployment、attempt snapshot、publication identity、deployment owner 和恢复状态表；共享 SQLite 路径由 durable deployment owner 启动门控拒绝第二 deployment。
- **M-1/M-2**：publish intent/fence/attempt/task/publication 完整身份比较与一次性绑定已进入 repository/service/recovery 链；缺 task identity 的旧 intent 被显式标为 conflict，不作为合法重入。shutdown 重读当前 claim revision、owner token、deployment、attempt 和 fence 后做有界 CAS；竞争重读、所有权转移、已完成发布、重复 shutdown 与恢复均有测试。
- **M-3**：快照在复制完成、逐文件集合/大小/内容摘要验证和 durable seal 前不会进入 WinRAR；源文件在执行期间改写后恢复原字节/大小/mtime 也不影响 sealed 输入；未 sealed 快照在重启中只做任务目录白名单清理，失败或取消不被后续 attempt 复用。
- **M-4A/M-4B**：publication generation 用 task/attempt/deployment/fence/Manifest/file-set digest 固定身份；同文件系统原子改名后正式目录只读保护，完成事务引用同一 sealed generation。SQLite 是唯一 durable publication/index 事实源，JSON index 为可重建投影；跨进程锁、临时文件 flush/fsync/原子替换和损坏 index fail-closed/rebuild 已实现，index 失败不报告成功。
- **L-1**：marker 绑定 task、attempt、deployment、staging root 和随机 token；删除前交叉验证当前 intent/fence/发布所有权，正式移动后仅发布层删除一次。同一合法发布的并发/重入删除返回幂等成功，错配 marker 不删除。
- **测试有效性**：临时破坏 M-1 完整身份比较时 `test_task_b_cannot_bind_or_reuse_task_a_identity` 以 `DID NOT RAISE` 失败；绕过 M-2 当前 revision 收敛时 `test_shutdown_rereads_revision_after_worker_activity` 得到错误的 unresolved 状态；移除 M-3 sealed 前源证据校验时 `test_snapshot_change_before_seal_invalidates_input_and_never_executes` 以 `DID NOT RAISE` 失败；移除 M-4A 原子移动后的正式产物校验时 `test_publication_cutpoint_tamper_never_becomes_durable_success` 以 `DID NOT RAISE` 失败。四项临时破坏均已恢复，恢复后测试通过。
- **门控**：第二轮安全/Worker/恢复/既有发布回归定向集合 `65 passed, 5 warnings`；修正 task-bound 发布顺序的公共 HTTP 合成夹具 `1 passed`。重新执行完整 `verify:full` 通过：前端 `44` 个文件、`211 passed`，后端 `796 passed, 3 skipped, 16 warnings`，架构检查、TypeScript、生产构建和 `verify:docs:strict` 均通过。补充 `python -m compileall -q packages/backend/app`、仓库资产检查（540 个跟踪文件）和 `git diff --check` 均通过。
- **D 盘轻量冒烟边界**：在工作区 D 盘隔离 `--basetemp` 目录中使用纯合成数据执行公共 HTTP 自动接管/单任务失败后继续处理及 Windows `sdiskio` 缺少 `busy_time` 的回归，`2 passed, 1 warning`；临时目录已清理。该证据是 HTTP/TestClient 轻量自动化，不冒充新的浏览器人工验收；本轮没有修改 `word_templates/template.docx`。
- **状态限制**：上述实现和门控已由 2026-08-01 门控后的独立 Level 3 Review 正式裁定为 `PASS`，因此 `1D-017R` 已完成。Final Review、Production Review、Phase 5 和 OpenSpec archive 仍未开始，不能据此提前宣称 Production-ready 或完成归档。

### 2026-08-01 `1D-017R` 门控后独立 Level 3 Review 结果

- **基线与范围**：`origin/codex/demo-next-stage..HEAD`；base `374057992ce863f1c1a9eca591f2b5fc0ba82eb0`，HEAD `29d3c1e14031e9dbda4244cd785ca8dd22d9b466`，66 files，`+4311/-737`；工作树 clean，未修改产品代码或测试。
- **完整 Harness**：在独立审查前执行 `npm.cmd run verify:full`，沙箱外退出码为 `0`；架构、类型、前端测试、后端测试、生产构建和 `verify:docs:strict` 全部通过；后端 `796 passed, 3 skipped, 16 warnings`。沙箱内首轮的 `EPERM: lstat C:\Users\SYNTHETIC` 仅为执行环境权限失败，不作为代码结果。
- **独立安全裁定**：M-1、M-2、M-3、M-4A、M-4B、L-1 均 `PASS`；Critical、High、Medium、Low 阻断均为 `0`。未发现支持边界内的 durable false succeeded、历史正式资产覆盖、不可逆损坏、跨 task 复用或绕过 revision/ownership/fence/integrity 的主链路问题。
- **TD 状态**：TD-1 已关闭；TD-2 已关闭；TD-4/TD-5 保留为外部环境债务，现有 sealed snapshot、Manifest/MD5/SQLite 校验在支持链路中 fail-closed；TD-3、TD-6 保留为 Low 技术债。
- **文档澄清**：marker 序列化 payload 不直接存 `fence_id`；fence 绑定由 durable intent 的 `fence_id` 与当前 DB fence 在删除前交叉校验实现，不构成本轮阻断。此前技术债段落保留历史发现，以上述当前状态为准。
- **剩余门控（`1D-017R` 完成时、Final Review remediation 前快照）**：`1D-017R` 完成；Final Review、Production Review、Phase 5、OpenSpec archive 和 `OpenSpec 归档阻断解除` 仍保持未完成。

## 2026-08-01 Final Review 有限 remediation

本轮只处理 Final Review 明确的四项阻断：retry 公共响应安全投影、delta requirement 严格 Scenario、living specs 严格格式/schema v10 同步和 proposal 状态同步。不重新打开 `1D-017R`、M-1 至 M-4B/L-1，不修改 sealed-input/publication 架构，不开始 Production Review、Phase 5 或 OpenSpec archive。

- [x] **1D-052** 将 retry 公共 HTTP 响应收敛为批准的安全 `task` projection；保持内部 `enqueue()`/attempt/context/runtime 绑定结构、任务创建、revision、lease、冲突/失败合同和 `TaskRetryRequest` 的内部字段拒绝不变。
- [x] **1D-052T** 补充 retry API 回归：响应只含安全 `task`、不含 context/attempt/fence/lease/owner/路径等内部绑定字段；仍创建新 attempt，并由 Runtime/Scheduler/Worker 接管；覆盖 revision、lease、冲突和失败路径。定向集合通过：工作台 `5 passed`，runtime/attempt/worker/persistence `30 passed`，新 retry runtime 用例连续 5 次通过。
- [x] **1D-053** 修复 Phase 1D delta requirement 的合法 Scenario；将 electronic-inspection-record living spec 迁移到 `## Purpose`/`## Requirements` 严格结构并保留 REQ 身份、语义和场景；同步 data-model 的 schema v10 与已批准的 durable/projection 边界；同步 proposal 当前状态。
- [x] **1D-053T** 2026-08-01 通过 change strict、living specs strict、`verify:docs:strict`、`git diff --check` 和授权环境 `npm.cmd run verify:full`；完整门控为架构/类型/前端 `44 files, 211 passed`/后端 `797 passed, 3 skipped, 16 warnings`/构建/严格文档全部通过。已完成本轮 remediation diff 的独立定向审阅，Final Review 仍待重新执行。

#### 本轮状态

- `1D-017R`：已于 2026-08-01 通过，保持完成，不重新审查。
- Final Review：此前因上述四项问题为 `REJECT`；2026-08-01 remediation 后已重新执行并判定为 `PASS`，当前允许进入 Production Review。
- Production Review：2026-08-01 已按 Legacy-only、单 Windows 实例支持模型审查并判定为 `PASS`。
- Phase 5：未开始。
- OpenSpec archive：未开始；`OpenSpec 归档阻断解除` 已按现有 gate 勾选。

### Phase 5 gate

- [ ] 五阶段合同均有定向测试和人工验收证据，且没有依赖隐式前端状态。
- [ ] 案件记录清理和正式产物管理完全分离，首版没有误删正式 RAR、Manifest 或 Word 的路径。
- [ ] Legacy 是唯一正式输出，Shadow 真实样本治理仍暂停，Canonical 未进入生产链路。
- [ ] Level 3 verify、独立 review 和归档前状态由人类确认后再执行；本轮不提交、不推送。
