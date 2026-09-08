# Tasks: 报告上级目录导出

workflow_level: 2

关联：portable-windows-distribution 的目标为部署及原生选择器兼容；export-name-and-datetime-controls 为命名及日期；direct-source-archive-and-root-name-fix 为压缩输入及根目录结构。均不包含本次输出位置及单份产物合同，建立独立变更。

- [x] T001 修改 `packages/backend/app/services/source/source_record_service.py`、目录控制器及导出控制器，由案件来源解析并验证报告上级目录；上传不读写历史。验证：来源及目录控制器定向 pytest。
- [x] T002 修改 `packages/backend/app/services/export/unified_export_service.py`、归档结果服务和本地导出位置记录，使最终 RAR 迁出工作区，重复导出复用已校验产物；失败保留可恢复原件，案件清理不删除外部文件。验证：统一导出、归档结果及删除回归。
- [x] T003 修改 `packages/frontend/src/components/PlatformSidebar.tsx`、工作台及 Word 导出调用，删除存储设置入口和选择目录交互，移除设置路由与运行时写入接线。验证：定向 Vitest、类型及构建。
- [x] T004 核对实现，同步 `openspec/specs/electronic-inspection-record/spec.md`，独立审查核心文件，运行 verify:quick、受影响测试及 scoped strict docs，记录证据。

T006 更新：临时压缩位于报告上级目录，校验后同卷重命名发布，统一导出复用唯一 RAR。内部工作区仅保留元数据；旧版产物兼容迁移，历史文件不批量迁移或删除。

## 验证证据（2026-09-07）

- T001：原任务控制器/运行时集成测试 `tests/test_record_controller.py`、`tests/test_archive_runtime_lifecycle.py`、`tests/test_workbench_controller.py` 共 90 项通过；来源解析、精确授权及其他目录拒绝有定向覆盖。本次目录选择器回归再次通过。
- T002：本次统一导出、归档导出、目录选择器、旧配置只读、本地目录登记、Manifest 权威性和保留策略共 64 项通过；覆盖迁移、重复复用、目标冲突、登记失败回滚和注册表损坏拒绝。原任务运行时回归覆盖多输出根迁出后重建结果服务，以及外部 RAR 篡改拒绝。
- T002 删除边界：复用现有案件删除测试增加迁出参数，登记外部 RAR 位置后删除案件，断言报告、外部 RAR 和 Word 保留，应用内产物删除；本次该文件 6 项通过。
- T003：原任务 useArchiveCompletion、CaseWorkbenchPage 和 CaseRecordGeneratePage 的 50 项前端测试通过；生产构建通过，仅有产物 chunk 大小提示。本次没有修改生产源码，不重复构建。
- T004：独立审查任务 `01a07afa-9836-70b3-b61d-e726041722e9` 最终复审通过，原 4 项核心问题已修复，无新增必须修复项。此后本次仅补充删除测试和文档，不改变被审查的生产实现。
- 规格核对：新增和修改 Requirement 已同步现行规格，旧存储设置 Requirement 已移除；恢复此前同步误删的跨功能约束，更新存储路径表和数据模型文档。
- manual_acceptance: N/A（本次只调整目录解析、迁移和入口移除；目录授权及文件生命周期以合成数据自动化验证，未改变原生选择器实现或 Word 版式。未执行真实业务数据/Windows 桌面端到端人工验收。）
- 本变更保持未归档；未提交或打包发布。

- [x] T005 修正归档失败提示（Level 1 反馈）：`archive_interrupted` 的说明兼容执行失败，不再断言发生应用重启；索引安全摘要移除已经删除的“归档存储设置”操作指引，并准确涵盖历史索引记录或文件不受当前案件库确认的情况。保留索引失败关闭边界，不自动信任或删除历史产物。复用归档 worker 23 项和压缩决策面板 6 项测试，全部通过；`git diff --check` 通过。manual_acceptance: N/A（仅文案，未改变交互与安全判断）。

- T001–T005 最终门控：`npm run verify:quick` 通过（架构、共享与前端类型、治理测试、快速文档和仓库资产卫生）；`npm run verify:docs:strict -- --change report-parent-export --details` 通过（14 项检查、0 漂移）。增量同步逐块核对通过；删除的正式 Requirement 仅为旧存储设置，跨功能约束完整保留；`git diff --check` 通过。

## T006 直接压缩落盘反馈（2026-09-08）

- [x] T006 归档前反馈：立即压缩就在报告文件夹的上一级同卷暂存，校验后排他重命名发布 RAR；登记和重启恢复复用最终位置，统一导出不复制新生成 RAR。验证直接落盘、冲突、发布中断、重启与旧产物兼容，完成定向回归、独立审查、verify:quick 和 scoped strict docs，并同步规格。

- 路径确认：选择 `D:\案件A\报告\index.html` 对应报告目录时，RAR 最终位置为 `D:\案件A`，不是 HTML 同目录。
- 实现：在目标上级目录的任务独占临时目录运行 WinRAR，同卷排他重命名发布，内部只记录发布日志与索引；复用现有最终位置登记及统一导出分支。
- 定向验证：首轮 106 项通过；独立审查指出的恢复授权与 Windows 只读清理问题修复后，64 项定向回归通过，包括失效授权拒绝发布、重启后临时目录消失、文件身份保持、登记失败回滚、同名冲突、删除计划边界及日志不冒充 RAR。
- 环境：C 盘临时目录空间不足；改用项目验证规则规定的 `D:/harness-temp-root` 后测试通过。工作区内临时目录触发目录保护的测试失败属环境隔离问题，未放宽生产保护。
- manual_acceptance: N/A（Windows 文件发布、清理与重启通过 SYNTHETIC 合成文件自动化验证；只替换测试中的 WinRAR 子进程，压缩命令和 Word 渲染逻辑未变。没有使用真实案件运行端到端压缩。）
- 最终受影响回归：直接发布仓储、归档执行、恢复、运行时生命周期、统一导出、归档导出、案件删除、Manifest 注册及权威性、worker 共 150 项通过。新增编辑期间中断恢复场景验证完成后保留最新文号。
- 独立复审：`/root/direct_archive_review` 按五维清单复审通过，无剩余 P1/P2 必须修复项；恢复授权、只读清理和草稿编辑兼容问题已修复。
- 工程门控：`npm run verify:quick` 通过；架构、类型、治理测试、快速文档及仓库资产检查均通过。未提交、打包或归档。
- 严格文档门控：完成任务记录更新后，`npm run verify:docs:strict -- --change report-parent-export --details` 通过（14 项、0 漂移）；增量与现行规格已同步，`git diff --check` 通过。
