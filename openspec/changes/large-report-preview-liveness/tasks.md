# 任务：大型报告预览活性

> 变更：`large-report-preview-liveness`
> Level：3
workflow_level: 3
> 状态：`PROPOSED`；当前修复的实现及定向/完整自动化检查已完成。合成基准、修复后人工验收和最终审查门控仍未完成。
> 范围：预览活性、解析器快照/缓存身份、执行中复用，以及延后构建完整 ArchiveContext。
> 明确排除：Shadow、Canonical 和完整 Harness 执行。

## 目标与验收门控

只有覆盖 `openspec/changes/large-report-preview-liveness/specs/electronic-inspection-record/spec.md` 中的需求并通过以下门控，才算实施完成：

- 代表性外部多检材报告的首次预览以合理余量低于 90 秒；
- 有效缓存命中预览低于 15 秒；
- 预览不构建完整 ArchiveContext，也不枚举完整输入树；
- 同目录并发请求共享一个昂贵解析任务，包括前端 Abort 后的请求；
- 不为单独计算指纹而重新打开核心 JSON 和实际 Parser 依赖；
- Legacy 和 New 合成 DTO 等价测试通过；
- 正式归档准备仍执行完整清单、可读性、路径/链接、变更、完整内容指纹、WinRAR、Manifest、RAR、下载和导出验证；
- 真实报告路径、案件名称、业务数据、生成输出和性能日志均位于 Git 和仓库文档之外。

## 实施顺序

任务按架构层排序。依照 Harness 架构规则，每个实施任务后紧跟其验证任务。

### 第 0/1 层 — 共享契约和常量

- [x] **T1 — 定义明确的预览/归档就绪契约**
  - 需求：REQ-PREVIEW-SNAPSHOT-001、REQ-ARCHIVE-LIFECYCLE-001、REQ-FRONTEND-LIVENESS-003。
  - 文件：`packages/shared/types/archive.ts`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`。
  - 增加区分 `not_prepared`、`preparing`、`ready` 和 `failed` 的就绪状态；定义可空/明确的外壳摘要；保留 `InspectionReport`、`rar_info`、`ArchiveManifest` 和 Legacy DTO 字段。
  - 仅当 Controller 设计选择新路由时，增加与源无关的归档准备端点常量。
  - API 名称与现有 camelCase/snake_case 边界约定保持兼容。

- [x] **T2 — 验证共享契约兼容性**
  - 需求：REQ-PREVIEW-SNAPSHOT-004、REQ-ARCHIVE-LIFECYCLE-001。
  - 文件：`packages/shared/types/*.ts` 测试/类型检查覆盖及现有归档类型测试。
  - 验证现有消费者可编译、正式 `ArchiveManifest` 不变，且不能只用 `idle` 表示就绪。
  - 只运行定向共享类型检查；本阶段不运行完整 Harness 门控。

### 第 10/11/12 层 — 前端预览和归档生命周期界面

- [x] **T3 — 使预览归档准备变为被动操作**
  - 需求：REQ-FRONTEND-LIVENESS-001、REQ-FRONTEND-LIVENESS-002。
  - 文件：`packages/frontend/src/hooks/useArchivePreparation.ts`、`packages/frontend/src/hooks/useReportParser.ts`。
  - 移除加载报告及光盘编号变化触发的归档执行/轮询副作用。保留后续用户操作可调用的显式准备，并使用独立的加载、Abort、错误、重试和过期尝试处理。
  - 保留现有预览超时值；不得延长。

- [x] **T4 — 测试被动预览 Hook 和重试清理**
  - 需求：REQ-FRONTEND-LIVENESS-001、REQ-FRONTEND-LIVENESS-002、REQ-PARSE-INFLIGHT-002。
  - 文件：`packages/frontend/src/hooks/useArchivePreparation.test.tsx`、`packages/frontend/src/hooks/useReportParser.test.ts`。
  - 增加测试，证明加载报告不会调用归档执行或创建轮询循环；显式准备具有独立加载/错误清理；超时/网络取消会结束预览加载；过期响应不能替换更新的尝试。
  - 仅使用模拟 HTTP 响应和合成报告值。

- [x] **T5 — 显示明确的归档未准备状态并保留导出门控**
  - 需求：REQ-ARCHIVE-LIFECYCLE-001、REQ-FRONTEND-LIVENESS-003。
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`、现有归档状态组件，契约需要时包括 `packages/frontend/src/hooks/useRecordExport.ts`。
  - 显示归档准备未就绪时仍可审核；不将 `idle` 显示为就绪状态。在上下文就绪且 Manifest 已验证前，保持正式导出阻塞。

- [x] **T6 — 测试审核状态和导出边界**
  - 需求：REQ-FRONTEND-LIVENESS-001、REQ-FRONTEND-LIVENESS-003、REQ-CHANGE-BOUNDARIES-001。
  - 文件：现有页面/归档状态测试，或与变更组件相邻的新测试。
  - 验证报告仍可编辑、不自动启动归档请求、未准备状态可见，并以可操作消息阻止导出。

### 第 20 层 — 受控文件系统和解析器输入存储库

- [x] **T7 — 实现请求输入快照和依赖索引**
  - 需求：REQ-PREVIEW-SNAPSHOT-002、REQ-PREVIEW-SNAPSHOT-003、REQ-PARSE-CACHE-001。
  - 文件：新增 `packages/backend/app/repository/report_parse_input_repository.py`；仅在快照边界集成需要时修改 `packages/backend/app/repository/html_parser.py` 和 `packages/backend/app/repository/filesystem_identity_repository.py`。
  - 实现核心 JSON 单次加载、格式结果复用、有序设备行、证据目录映射、明确的设备元数据候选选择，以及同次读取中捕获路径元数据和内容摘要的依赖记录。
  - 拒绝不安全/绝对依赖路径。不递归媒体、附件 HTML、导航载荷或无关 JSON。不在返回/公共数据中暴露绝对路径。
  - 保持 Legacy 和 New 解析器适配器兼容；不得静默引入无界回退扫描。

- [x] **T8 — 测试快照读取及候选/依赖范围**
  - 需求：REQ-PREVIEW-SNAPSHOT-002、REQ-PREVIEW-SNAPSHOT-003、REQ-PREVIEW-SNAPSHOT-004。
  - 文件：新增 `tests/test_report_parse_input_repository.py`；定向补充 `tests/test_html_parser.py` 和 `tests/test_filesystem_identity_repository.py`。
  - 使用合成 Legacy 和 New 固件断言每个核心 JSON 只加载一次、复用设备目录解析、候选文件有界且明确、不打开媒体和无关 JSON、依赖路径为相对路径，并且捕获的元数据/摘要稳定。
  - 使用合成固件增加与现有解析器行为的 DTO 等价断言。

- [x] **T9 — 实现元数据优先的依赖验证**
  - 需求：REQ-PARSE-CACHE-001、REQ-PARSE-CACHE-002、REQ-PARSE-CACHE-003。
  - 文件：`packages/backend/app/repository/report_parsing_cache_repository.py`、`packages/backend/app/services/report_parsing_cache_service.py`，以及按需使用 T7 的快照/身份存储库。
  - 将依赖清单与现有缓存载荷/版本/LRU 记录共同存储。先验证路径、大小、mtime 和稳定身份；复用未变化摘要；只重新计算变化/新增依赖；候选成员变化时作废缓存。
  - 保留原子写入、损坏清理、LRU 行为、缓存清除隔离和不透明缓存键。不得改动 ArchiveManifest/RAR/Word 输出。

- [x] **T10 — 测试缓存失效和单遍行为**
  - 需求：REQ-PARSE-CACHE-001、REQ-PARSE-CACHE-002、REQ-PARSE-CACHE-003。
  - 文件：`tests/test_report_parsing_cache.py`、`tests/test_report_parser_service.py` 及变更模块相邻的存储库测试。
  - 断言首次解析合并读取/解析/摘要工作；缓存命中不重新打开未变化依赖；依赖元数据/内容变化会失效；无关媒体/附件变化不会失效；新增候选会失效；格式错误/失败写入会清理；清除缓存不改动归档生命周期文件。
  - 增加读取计数器，证明旧有“先计算指纹再执行 Parser”的重复遍历已消失。

### 第 21 层 — 解析器编排和运行时生命周期

- [x] **T11 — 将快照解析与报告 Parser 和缓存集成**
  - 需求：REQ-PREVIEW-SNAPSHOT-001 至 REQ-PREVIEW-SNAPSHOT-004、REQ-PARSE-CACHE-001。
  - 文件：`packages/backend/app/services/report_parser_service.py`、`packages/backend/app/repository/report_parse_input_repository.py`、`packages/backend/app/services/report_parsing_cache_service.py`。
  - 让 Parser 接受一个请求快照，复用核心/配置/设备数据，每项实际依赖只解析一次，登记依赖清单，并返回不变的 Legacy 兼容报告结果。`compress` 保持弃用，在文件夹预览中不起作用。
  - 不向解析器服务增加 ArchiveContext 清单或 WinRAR 工作。

- [x] **T12 — 测试 Parser 阶段复用和 DTO 等价**
  - 需求：REQ-PREVIEW-SNAPSHOT-001 至 REQ-PREVIEW-SNAPSHOT-004。
  - 文件：`tests/test_report_parser_service.py`，必要时新增定向解析器快照测试。
  - 断言公共 JSON 读取次数、每设备候选读取次数、不递归整个报告、Legacy/New DTO 等价、`rar_info` 兼容、失败安全，且不调用 Shadow/Canonical。

- [x] **T13 — 实现有界同目录执行中注册表**
  - 需求：REQ-PARSE-INFLIGHT-001 至 REQ-PARSE-INFLIGHT-003。
  - 文件：`packages/backend/app/services/report_parse_inflight_service.py` 及其与 `packages/backend/app/services/report_parser_service.py` 的集成。
  - 在依赖发现前按规范化不透明目录身份获取。共享有界 Future/任务，使取消的等待方脱离但不取消共享工作，发布一个结果/错误，强制容量和最大生存期，并安全移除完成/失败条目。
  - 现有缓存存储锁继续作为一致性保护，而不是昂贵工作的首个去重边界。不得记录原始路径。

- [x] **T14 — 测试执行中加入、取消、容量和失败清理**
  - 需求：REQ-PARSE-INFLIGHT-001 至 REQ-PARSE-INFLIGHT-003。
  - 文件：新增 `tests/test_report_parse_inflight_service.py`，补充 `tests/test_report_parser_service.py`。
  - 使用屏障/伪构造器和合成目录断言同键两个请求只运行一个构造器、跟随方取消不启动第二个构造器、不同键相互独立、容量有界、失败可重试且不残留永久条目。

- [x] **T15 — 将上下文外壳与完整 ArchiveContext 实体化分离**
  - 需求：REQ-ARCHIVE-LIFECYCLE-001 至 REQ-ARCHIVE-LIFECYCLE-003。
  - 文件：`packages/backend/app/services/archive/archive_runtime_service.py`（包括同处的生命周期记录）、`packages/backend/app/services/archive/archive_source_runtime_service.py`、`packages/backend/app/services/archive/archive_execution_service.py`。
  - 增加不透明、短期有效、已授权且有明确就绪状态但无清单的外壳；预览只使用外壳。增加与源无关的显式准备操作，重新验证授权、构建完整清单并升级/发布完整上下文。
  - 保留正式 `verify_input_inventory`、完整输入内容指纹、WinRAR 规划/执行、RAR 完整性、Manifest、下载和导出验证。外壳和解析缓存必须被拒绝作为正式证据。

- [x] **T16 — 测试外壳就绪和正式归档安全**
  - 需求：REQ-ARCHIVE-LIFECYCLE-001 至 REQ-ARCHIVE-LIFECYCLE-003、REQ-CHANGE-BOUNDARIES-001、REQ-CHANGE-BOUNDARIES-002。
  - 文件：`tests/test_archive_runtime_service.py`、`tests/test_archive_source_runtime_service.py`、`tests/test_archive_execution_service.py`。
  - 断言创建预览外壳不调用完整清单、外壳执行被拒绝、显式准备构建当前清单、源变更/链接/不可读文件失败，且所有正式归档/Manifest/RAR 门控仍有效。断言未引入 Shadow 或 Canonical 行为。

### 第 22/23 层 — HTTP 边界

- [x] **T17 — 不含完整上下文地返回预览，并公开显式准备边界**
  - 需求：REQ-PREVIEW-SNAPSHOT-001、REQ-ARCHIVE-LIFECYCLE-001、REQ-ARCHIVE-LIFECYCLE-002。
  - 文件：`packages/backend/app/controllers/record_controller.py`、`packages/backend/app/controllers/archive_controller.py`，仅在选择专用准备路由时修改 `packages/backend/app/routes/__init__.py`。
  - 从预览端点移除同步完整 `create_archive_context`。返回报告及明确就绪/外壳状态。将外壳未就绪、容量、超时和解析器失败映射为不含路径或报告数据的稳定安全错误。
  - 只增加从已授权报告目录源实体化完整上下文所需的准备请求。

- [x] **T18 — 测试控制器响应和归档边界**
  - 需求：REQ-PREVIEW-SNAPSHOT-001、REQ-ARCHIVE-LIFECYCLE-001 至 REQ-ARCHIVE-LIFECYCLE-003、REQ-FRONTEND-LIVENESS-003。
  - 文件：`tests/test_record_controller.py` 和 `tests/test_shadow_pipeline.py`（归档控制器集成用例）。
  - 在模拟集成中断言预览响应先于清单返回、明确未准备状态不是 `idle`、旧仅报告字段保持兼容、外壳不能导出、准备会创建完整上下文且错误不泄露路径/内容。

## 跨层验证和验收

- [ ] **T19 — 增加合成性能/读取次数基准** [DEFERRED]
  - 需求：REQ-ACCEPTANCE-001、REQ-PARSE-CACHE-001、REQ-PARSE-INFLIGHT-001。
  - 文件：后端测试套件相邻的新合成基准/测试；不使用真实报告或生成输出。
  - 断言预览避免完整清单、每项核心 JSON 每任务只读取一次、同一依赖不会先用于指纹再用于 Parser、缓存命中满足合成预算、同键并发只运行一个昂贵任务。
  - 状态说明：已有定向读取次数、缓存和执行中测试，但尚未发现单独的 T19 基准记录。在提供明确合成基准证据前保持任务未完成。

- [x] **T20 — 运行限定范围验证并准备人工验收**
  - 需求：上述全部需求。
  - 文件：无生产文件；仅在任务完成时更新本任务文件。
  - 运行定向后端/前端测试、`lint:arch`、类型检查、`git diff --check` 和适用的仓库资产检查。准备仅供人工使用的外部报告验证清单，但不记录路径、案件数据、日志或输出。在实现、人工验收和独立审查完成并询问用户是否执行完整 Harness 门控前，不运行 `verify:full`。

- [x] **T21 — 在 Legacy 流程/结果投影中保留全部检材编号**
  - 需求：REQ-PREVIEW-SNAPSHOT-004。
  - 文件：`packages/backend/app/services/report_parser_service.py`、`tests/test_report_parser_service.py`。
  - 保持现有 Legacy DTO 结构，同时将有序 `evidence_list` 投影到流程步骤和结果字符串。增加合成多检材回归测试；保留单检材措辞，不改变归档、前端、模板、Shadow 或 Canonical 行为。

- [x] **T22 — 允许在不准备归档时仅导出报告 Word**
  - 需求：REQ-FRONTEND-LIVENESS-003、REQ-ARCHIVE-LIFECYCLE-003。
  - 文件：`packages/backend/app/controllers/record_controller.py`、`packages/frontend/src/hooks/useRecordExport.ts`、`packages/frontend/src/pages/RecordGeneratePage.tsx`、`packages/frontend/src/components/ReviewActionBar.tsx` 及其定向测试。
  - 将显式 Word 报告生成与归档准备解耦，同时保留全部报告验证。提供正式归档标识符时，保留现有完整清单、Manifest、RAR、WinRAR、路径/链接和变更门控。部分归档标识符安全失败；仅报告导出不启动归档或 Shadow 任务。

- [x] **T23 — 在兼容 Legacy 的 DTO 中保留单检材设备显示名称**
  - 需求：REQ-PREVIEW-SNAPSHOT-004。
  - 文件：`packages/backend/app/services/report_parser_service.py`、`tests/test_report_parser_service.py`。
  - 保持 `device_name` 为规范化型号显示值，保留 `model` 和 `device_type` 语义，作废过期解析缓存，并覆盖合成 Legacy/New 单检材投影，不改变共享 DTO 结构。

- [x] **T24 — 第 1 部分：将可变修订版与归档所有权分离**
  - 需求：REQ-ARCHIVE-LIFECYCLE-004。
  - 文件：`packages/backend/app/services/archive/archive_worker_service.py`、`packages/backend/app/services/archive/archive_runtime_coordinator_service.py`。
  - 将 `process_tree_id` 加绑定尝试 ID 视为所有权身份。在工作进程启动前及协调器回退中收敛取消，且不允许用 `failed_retryable` 覆盖 `cancelling`。

- [x] **T25 — 验证准备/取消竞态修复**
  - 需求：REQ-ARCHIVE-LIFECYCLE-004。
  - 文件：`tests/test_archive_worker_service.py`、`tests/test_archive_runtime_lifecycle.py`。
  - 复现认领后及条目准备阻塞期间的取消；断言任务取消和 `ARCHIVE_CANCELLED`。单独替换所有者令牌，并断言过期工作进程仍收到 `ARCHIVE_TASK_OWNERSHIP_LOST`。

- [x] **T26 — 第 2 部分：公开并中断缓慢的完整清单准备**
  - 需求：REQ-ARCHIVE-LIFECYCLE-002、REQ-ARCHIVE-LIFECYCLE-004。
  - 文件：归档运行时协调器/源/上下文服务及 `packages/backend/app/repository/archive/archive_input_repository.py`。
  - 在完整遍历前将已认领任务推进到 `inventory`，并通过上下文准备向目录枚举传播协作取消回调。保留所有正式归档门控和清单发布规则。

- [x] **T27 — 验证清单可见性和协作取消**
  - 需求：REQ-ARCHIVE-LIFECYCLE-004、REQ-ACCEPTANCE-002。
  - 文件：`tests/test_archive_input_repository.py`、`tests/test_archive_runtime_lifecycle.py` 及现有归档运行时/源/工作进程测试。
  - 断言被阻塞的准备已处于清单里程碑、遍历在取消边界停止，且定向归档生命周期套件保持通过。

## 实施后门控

- [x] Level 3 独立代码审查已完成。增加过期所有者/尝试绑定保护及集成回归后，独立审查通过。
- [ ] 已针对外部多检材报告完成人工验收，且未增加敏感产物。早期证据早于 T24-T27；需重新执行归档阶段/取消验收，且不记录敏感路径、业务数据、生成输出或性能日志。[DEFERRED]
- [ ] 完整 Harness 执行已完成并通过；早期运行早于 T24-T27，不得复用为当前证据。[DEFERRED]
- [ ] 除非另有请求，否则不提交或推送。[N/A]
