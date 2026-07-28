# Tasks: persistent-case-workbench-and-archive-coordination

> 本文件定义后续实现顺序；Phase 1A/1B 已在基线提交完成，Phase 1C 和 Phase 1D 已完成；Phase 2 及后续阶段仍未开始。
> 目标合同：`openspec/specs/electronic-inspection-record/spec.md`
> 设计：`design.md`

## 执行规则

- 五个 Phase 可分别实现、定向验证、人工验收和提交；阶段间只通过版本化 SharedTypes/API 合同连接。
- 每个 Phase 内按 Layer 0 → Layer 23 排列；每个代码任务后紧跟覆盖同一合同的测试任务。
- 实施前必须审计其他活跃变更包的重叠任务；不自动删除或降级旧包，不把 Canonical 或 Shadow 真实样本任务作为本包隐式前置条件。
- 所有测试数据必须显式标记 `SYNTHETIC/TEST/FIXTURE`，不提交真实案件、人员、设备号、路径、RAR、Manifest、DOCX 或运行输出。
- 任一阶段不得启动 Canonical 或 Shadow 真实样本治理；Legacy 仍是唯一正式输出。
- 每个阶段完成后至少执行该阶段定向架构检查、类型检查和测试；全部阶段合并后再安排 Level 3 独立 Code Review 和完整 Harness 门控。

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
| 来源已确认变化或不再安全 | `requires_reselection` | 禁止正式 Word/归档；重新选择来源并重新解析 |
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

- [x] **1D-003** 补齐固定的来源复核恢复流程：数据库恢复后保持未完成 SourceRecord 为 `pending`；应用启动完成后由受控执行器按 `source_id + revision` 去重重新调度；调度失败保持 `pending` 并记录 `SOURCE_REVALIDATION_PENDING`，允许后续启动或显式重试；暂时 I/O/权限/资源不可用不得直接变成来源变化，确认 fingerprint/根/链接/结构变化、来源替换或不可继续使用时才转 `requires_reselection`；不得为 `review_ready` 案件重复解析；正式 Word/归档和显式重试遵循可信状态门控。
- [x] **1D-003T** 增加服务测试：启动后重新调度成功、调度失败保留 pending、同一 source/revision 多次启动幂等、暂时不可验证、确认变化、来源重新选择与重新解析、草稿仍可查看/编辑、来源变化阻止正式输出，以及 `review_ready` 不重复 Parser。
- [x] **1D-004** 在现有 Legacy `/records/archive` 调用外围登记最小归档尝试：执行前记录 attempt、输入 revision、受控 staging 标识和系统创建记录；只记录 accepted/running/succeeded/failed/interrupted 及 cleanup 结果；重启只映射未完成尝试到 `interrupted`/`archive_interrupted`，不创建 Worker、队列、进度或自动重试路径；用户重新确认并由后端接受新尝试后才创建新 handle 和新记录；已 succeeded 且 Manifest 已验证的记录不可回退。
- [x] **1D-004T** 增加归档尝试服务测试：草稿在 archive_interrupted 下可查看/编辑、稍后压缩转 deferred、立即确认前置来源复核、新 attempt/new handle 被接受后才离开中断态、旧 handle/半成品不复用、用户确认前不调用 Legacy 归档、succeeded 尝试不被恢复流程回退。
- [x] **1D-005** 建立 staging/进程归属证明和安全处理边界：清理必须同时具备受控 staging 根、不可猜测 attempt_id、数据库/受控索引归档记录、staging 内系统 ownership marker、marker 与记录/部署实例/root 匹配五项证据；证据缺失、冲突或无法确认时视为未知，不删除、不终止、不覆盖，只记录安全诊断；自有未完成 staging 可隔离或清理，半成品不注册 Manifest、不返回用户、不驱动 Word；清理失败不阻止案件恢复。
- [x] **1D-005T** 增加安全测试：五项证据全部满足时清理、缺失/冲突/marker 不匹配时未知资源不删除不覆盖、未知 WinRAR 不终止、伪造目录名/PID 不通过归属证明、半成品 RAR/Manifest 不发布、正式产物不误删、多次恢复/清理幂等、内部 PID/启动时间/locator 不进入公共 DTO 和绝对路径不泄露。

#### Legacy 兼容回归和人工验收

- [x] **1D-007** 对既有 Legacy Parser、Word builder/export、Manifest authority、archive execution、VML/分页、附件和图片门控进行合成回归；不得修改 `word_templates/template.docx`，不得引入 Canonical/Shadow 或 Phase 3 进度。
- [x] **1D-007T** 运行并补充针对性后端/前端测试，覆盖 Legacy 解析、归档失败/重试、Manifest 缺失/篡改/分卷校验、Word 内容与附件图片、路径安全和恢复状态 API；所有 fixture 明确标记 `SYNTHETIC/TEST/FIXTURE`。
- [x] **1D-008** 完成合成数据人工验收：多案件切换、刷新、关闭/重启恢复、解析失败重试、来源暂时不可验证/确认变化、租约失效、图片资产、deferred、立即归档中断、新 handle、staging 保护和正式产物保护；只保存脱敏的验收结论，不保存真实报告或生成产物。2026-07-28 验收结论：合成双案件可独立登记、解析、编辑、刷新和重载，解析/来源/租约/图片/归档中断与正式产物保护矩阵通过；失败任务仅进入可重试状态，未生成可审核草稿；未使用真实案件、报告或正式产物。
- [x] **1D-008T** 完成定向架构检查、类型检查、相关后端/前端测试和 `git diff --check`；2026-07-28 定向结果：后端 Phase 1D 文件 3 次稳定通过、单测 5 次稳定通过，独立 PowerShell 全量后端 `642 passed, 3 skipped, 8 warnings`；前端恢复/工作台/图片资产/审核编辑/导出定向 `36 passed`；架构、类型、严格文档、资产和 diff 检查通过。用户随后在独立 PowerShell 执行 `npm.cmd run verify:full`，退出码为 `0`；后端结果为 `642 passed, 3 skipped, 8 warnings`，前端 TypeScript 与生产构建通过，`verify:docs:strict` 通过。已知非阻断 warning 为 `ARCHIVE_CONFIGURED_ROOT_INVALID` 和 Vite chunk 大于 500 kB。

### Phase 1 gate

- [x] 案件提交后立即显示案件壳卡片，解析失败卡片可重试但不可审核、归档或导出。
- [x] 共享默认值修改后立即成为以后新案件的默认来源；当前草稿和共享默认值保存状态分别可见。
- [x] 刷新和重启后状态可恢复；`archive_deferred` 保持不变，`archive_queued/archiving` 转为 `archive_interrupted` 并等待用户重新确认；重启前 running WinRAR 不自动接管或续跑，正式产物不受影响。

## Phase 2 — 审核顺序、人员卡片、字段来源和导出命名

**阶段目标**：让案件数组成为所有审核、正文、附件和 Word 的共同顺序源，并把来源状态显式化。

### Layer 0/2 — Contract and pure rules

- [ ] **T007** 在 `packages/shared/types/` 扩展稳定 `evidence_id`、`InspectorSnapshot`、`FieldState`、来源/确认枚举和 Word 下载名称 DTO；在 `packages/shared/utils/` 新增 `naturalEvidenceOrder.ts`、`fieldProvenance.ts`、`downloadFileName.ts`。验证：旧 Legacy DTO 仍可投影。
- [ ] **T007T** 在 `packages/shared/utils/*.test.ts` 覆盖检材 2/10、重复/无法识别回退、用户修改来源迁移、待确认提示状态、非法 Windows 字符、空名和 `.docx` 补全。验证：Vitest。

### Layer 10/11/12 — Review UI and export name

- [ ] **T008** 改造 `packages/frontend/src/components/EvidenceEditor.tsx`、`InspectorEditor.tsx` 为拖拽/卡片交互；新增 `ReviewSourceLegend.tsx`、`WordDownloadNameDialog.tsx` 等 Phase 2 顺序/来源能力，不再创建独立的工作台字段、校验、附件或导出实现。
- [ ] **T008T** 为上述组件和 Hook 增加 RTL/E2E 测试；覆盖拖拽顺序持久化、姓名/单位/警号三字段人员卡片、来源颜色与文字提示、Word 每次弹窗、取消不导出和非法名称拒绝。

### Layer 20/21 — Ordered snapshots and provenance persistence

- [ ] **T009** 新增 `packages/backend/app/services/case_order_service.py`、`field_provenance_service.py`，改造 `report_parse_input_repository.py` 和 `inspector_repository.py` 的案件快照投影；只在案件创建时初始化默认顺序，保存拖拽后的数组和来源状态。
- [ ] **T009T** 新增/修改 `tests/test_case_order_service.py`、`tests/test_field_provenance_service.py`、`tests/test_report_parse_input_repository.py`；覆盖报告原始顺序回退、重复编号、下游不得二次排序、人员库变化不改历史快照、图片组和人员项来源覆盖。

### Layer 21 — Legacy projection

- [ ] **T010** 在 `packages/backend/app/services/legacy_report_projection_service.py` 或现有 Legacy builder 适配点统一生成正文、附件摘要、附件 1/2/3 和 Word 所需顺序投影；移除下游独立排序入口，但不改变 RAR 基础名规则。
- [ ] **T010T** 在 `tests/test_legacy_report_projection_service.py`、`tests/test_record_generator_service.py` 增加合成多检材/多人员回归；验证审核顺序与正文、附件和 Word 顺序一致，来源颜色未进入 DOCX。

### Phase 2 gate

- [ ] 拖拽后的案件检材/人员顺序刷新后仍一致，所有 Legacy 投影和 Word 输出共用该顺序。
- [ ] 默认值、报告解析值和人工修改值可区分，待确认有文字提示并进入门控。
- [ ] Word 名称按次输入且只影响下载名；服务器物理文件名安全、唯一、不可覆盖。

## Phase 3 — 归档映射、后台归档和真实进度

**阶段目标**：在现有正式归档安全门控外包一层可恢复任务，不以任务化为理由削弱任何检查。

### Phase 3 prerequisite — WinRAR progress capability spike

- [ ] 在进入 Phase 3 实现和验收前，使用 `SYNTHETIC/TEST/FIXTURE` 输入验证当前正式 WinRAR 版本是否能稳定提供可解释的实际进度信号；记录信号来源、解析稳定性、失败行为和百分比一致性，不记录真实案件或产物。验证：外部 spike 记录和合成回归证据。
- [ ] spike 未通过时暂停 Phase 3 完成门槛，先汇报并选择受支持 WinRAR 版本或适配方式；迁移期间保留现有 Legacy 显式压缩能力，不使用时间、动画或输出文件大小伪造百分比，也不直接让现有压缩失效。

### Layer 0/1/2 — Archive contracts

- [ ] **T011** 在 `packages/shared/types/` 新增 `VolumeSlot`、`DiscMapping`、`ArchivePlanSnapshot`、`ProgressSnapshot`、进度能力状态、Legacy 压缩兼容状态、资源准入 DTO 和任务取消/重试 DTO；在 `packages/shared/constants/` 固化归档阶段权重与错误码；在 `packages/shared/utils/` 实现稳定槽位 reconcile、唯一编号和单调进度聚合。
- [ ] **T011T** 在共享测试中覆盖初始连续编号、非连续唯一编号、空/重复拒绝、stable slot replan、增删槽位、Manifest 收敛和进度不回退。验证：Vitest。

### Layer 10/11/12 — Archive status UI

- [ ] **T012** 新增 `useArchiveTask.ts`、`ArchiveStatusPanel.tsx`、`ArchiveVolumeMappingTable.tsx`、`ArchiveStartDialog.tsx`；在 `ReviewActionBar.tsx` 或现有导出操作区最左侧显示未压缩红色、真实阶段绿色进度、完成/失败和重试入口。
- [ ] **T012T** 增加 RTL/E2E 合成任务测试；覆盖计划逐卷映射、唯一校验、replan 保留/新增/删除、暂不压缩、37%/68% 等实际快照展示和切换案件后任务继续。

### Layer 20 — Archive metadata and process repositories

- [ ] **T013** 新增 `packages/backend/app/repository/archive_plan_repository.py`、`archive_task_repository.py`、`archive_asset_repository.py`、`resource_snapshot_repository.py`；持久化计划版本、槽位 lineage、映射、进程绑定、临时目录和正式产物索引。
- [ ] **T013T** 新增对应 pytest；覆盖事务重试、计划版本冲突、进程/临时目录恢复、正式产物索引独立于案件删除和不暴露原始路径。

### Layer 21 — Planner, scheduler and archive worker

- [ ] **T014** 改造 `packages/backend/app/services/archive_planner_service.py` 为稳定槽位计划/replan；新增 `archive_mapping_service.py`、`archive_progress_service.py`、`archive_scheduler_service.py`、`archive_task_worker_service.py` 和 `resource_admission_service.py`。将现有 `archive_execution_service.py` 包装成阶段化 worker，保留完整 inventory、路径/链接/变化、WinRAR、完整性、MD5、Manifest 验证；进度适配只在 spike 通过后启用，不替换 Legacy 显式压缩路径。
- [ ] **T014T** 新增 `tests/test_archive_mapping_service.py`、`tests/test_archive_progress_service.py`、`tests/test_archive_scheduler_service.py`、`tests/test_archive_task_worker_service.py`；覆盖 6 任务硬上限、资源不足排队、解析并行、阶段实际计数、spike 通过/未通过分支、无可靠信号时不显示假百分比、Legacy 压缩兼容、取消/重启/重试和安全门控回归。

### Layer 22/23 — Task API

- [ ] **T015** 改造 `packages/backend/app/controllers/archive_controller.py`、`record_controller.py`，新增 `task_controller.py` 和 `packages/backend/app/routes/task_routes.py`；提供“立即开始/暂不压缩”、计划映射修改、任务取消/重试和进度查询，预览仍不创建完整 `ArchiveContext`。
- [ ] **T015T** 新增 controller/route 集成测试；覆盖选择暂不压缩不启动 WinRAR、replan 自动返回新计划、Manifest 未验证不显示完成、失败原因可重试和错误不泄露路径。

### Phase 3 gate

- [ ] 当前正式 WinRAR 版本进度能力 spike 已通过，或已形成受支持版本/适配方式的明确产品与技术决定；未通过不得宣布 Phase 3 验收完成。
- [ ] 归档任务最多 6 个运行，资源不足排队且显示原因；不得假装启动 6 个 WinRAR。
- [ ] 进度来自实际计数/已验证 WinRAR 信号，阶段和百分比单调、可解释；无信号不使用假进度，同时现有 Legacy 显式压缩能力保持可用。
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
- [ ] **T021T** 增加 `tests/e2e/persistent-case-workbench.spec.ts`；使用合成多案件、多任务和合成模板覆盖刷新/重启、6 卡片分页、切换案件、唯一租约、取消后删除、顺序一致、来源状态、真实进度、模板切换和产物保护。

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
