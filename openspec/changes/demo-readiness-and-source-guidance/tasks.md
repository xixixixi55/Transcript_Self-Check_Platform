# Demo 就绪提示与来源目录开关边界

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: sync applied to openspec/specs/electronic-inspection-record/spec.md REQ-029, including page-level readiness display removal

## 级别与范围

- 级别：Level 2。
- 本变更独立于 Phase 1D、`case-shared-defaults` 和现有案件工作台变更包，只维护本文件。
- 目标：在电子数据检查入口和案件工作台展示安全的 Demo 环境就绪状态，并修正删除预检按钮语义。来源目录校验开关及其持久化登记模式由 `extensible-report-template-platform` 变更包的 8.4 任务统一管理，本变更包不再承载来源目录授权说明或开关入口。
- 不改变案件登记、解析、草稿、共享默认值、Legacy Parser、Word/VML/分页、Manifest、归档合同或 `word_templates/template.docx`。
- 不实现服务器配置修改、监控平台、后台探测队列、案件删除、保留期或产物清理。

## 设计说明

- 就绪 API 只返回三项固定能力的枚举状态、稳定错误码和固定处理建议；不返回路径、配置值、进程信息、命令行、异常或探测输出。
- 来源目录错误在来源校验开启时仍由真实登记链路返回；readiness API 不复制或展示来源目录授权状态。
- WinRAR 状态复用 `discover_winrar` 的能力结果，但仅投影为安全状态；不暴露可执行文件名、版本或路径。
- 归档输出根只检查既有目录的可访问/可写状态，不创建目录、不修改配置。
- 电子数据检查入口和案件工作台不再挂载 Demo 就绪提示，也不再为该提示请求就绪 API；后端就绪接口和安全投影组件保留。

## 验收标准

- [x] 电子数据检查入口和案件工作台不展示 Demo 环境就绪状态；来源目录校验控制项显示在案件工作台标题区。
- [x] 保留的就绪 DTO、独立投影组件和 API 仍仅使用“已就绪 / 未配置 / 当前不可用 / 无法确认”，并附稳定错误码和固定处理建议。
- [x] API 响应不含允许根目录内容、绝对路径、WinRAR 路径、PID、命令行、环境变量值或异常堆栈。
- [x] 来源目录校验开启时，首次登记和重新登记仍能区分未授权、不可访问、报告结构不支持等安全提示；关闭时允许登记任意满足基础路径安全检查的本机报告目录。
- [x] 案件卡片按钮显示“检查删除条件”，只调用既有删除预检，不执行删除或清理。

## 任务列表

### Layer 0–1：共享契约

- [x] 在 `packages/shared/types/demoReadiness.ts`、`packages/shared/types/index.ts` 和 `packages/shared/constants/index.ts` 增加固定就绪 DTO 与 API 端点。
- [x] 以 TypeScript typecheck 验证固定枚举、字段边界和前后端调用契约。

### Layer 20–23：后端安全快照

- [x] 在 `packages/backend/app/repository/demo_readiness_repository.py`、`packages/backend/app/services/demo_readiness_service.py`、`packages/backend/app/controllers/demo_readiness_controller.py` 和路由聚合中实现同步只读的安全快照。
- [x] 在 `tests/test_demo_readiness.py` 覆盖三项状态、异常降级、稳定错误码及路径/配置/进程信息不泄露。
- [x] 在来源控制器安全错误映射中区分未授权、不可访问和结构不支持（来源校验开启时）。
- [x] 扩展 `tests/test_workbench_controller.py` 的来源登记/重新登记错误响应断言，验证稳定且不回显路径。

### Layer 10–12：前端提示与语义

- [x] 在 `packages/frontend/src/hooks/useDemoReadiness.ts` 和导出索引中实现一次性读取与网络失败安全降级。
- [x] 在 `packages/frontend/src/hooks/useDemoReadiness.test.tsx` 覆盖正常 DTO 和后端不可用降级。
- [x] 在 `packages/frontend/src/components/DemoReadinessNotice.tsx` 和来源重新登记组件中实现安全投影；不再显示独立来源目录授权说明，来源目录校验入口由案件工作台提供。
- [x] 在对应组件测试中覆盖固定状态文案、无路径展示和三类来源错误提示；来源目录校验开启/关闭及浏览器持久化由 `extensible-report-template-platform` 的 8.4 测试覆盖。
- [x] 在 `ElectronicInspectionModulePage.tsx`、`CaseWorkbenchPage.tsx` 移除 DemoReadinessNotice 页面挂载；`CaseCard.tsx` 保持“检查删除条件”语义。
- [x] 更新页面测试，确认相关入口不展示 Demo 环境就绪状态，并覆盖案件工作台来源目录校验控制项、删除预检准确语义及安全错误提示。
- [x] 根据后续产品要求移除案件前端两处 Demo 环境就绪状态展示；页面不再为该展示主动请求就绪 API，后端接口和独立安全投影组件保留。

### 验证与交付

- [x] 运行相关前后端定向测试、typecheck、`lint:arch`、前端生产构建、`verify:docs:strict`、`check:repository-assets` 和 `git diff --check`。
- [x] 检查 `git diff` 与 Git 状态，仅保留本变更预期文件；不 commit、不 push、不归档。

## 验证记录

- 受影响后端定向测试：98 passed，2 个既有 `ARCHIVE_CONFIGURED_ROOT_INVALID` warning。
- 既有前端定向测试：7 个测试文件、22 passed；本次调整后的页面定向测试：2 个测试文件、28 passed；保留既有 Ant Design / React Router warning。
- 前端全量测试：用户独立运行并报告通过；未提供测试数量和 warning 明细，不在文档中推测。
- 后端全量 pytest：用户独立运行并报告通过；未提供测试数量和 warning 明细，不在文档中推测。
- 安全测试有效性：临时回显 SYNTHETIC WinRAR 路径时脱敏测试按预期失败；恢复固定投影后通过。
- 本次调整的 `lint:arch`、typecheck、`verify:quick`、显式 `check:repository-assets` 和 `git diff --check`：通过；当前 scoped strict docs 仍受既有人工验收任务未勾选影响。
- 轻量开发冒烟：后端健康检查与前端预览可启动；电子数据检查入口默认进入案件工作台；相关页面不再显示 Demo 就绪提示，案件工作台来源目录校验控制项和“检查删除条件”保持可用；未发现浏览器控制台错误、白屏、崩溃或数据库迁移失败。该结果不等于正式人工验收。

## 人工验收

- [N/A] Demo 就绪状态已从电子数据检查入口和案件工作台移除，无需进行该状态的页面展示人工验收。
- [N/A] 页面不再请求或展示 Demo 就绪状态，停止后端后的旧版状态降级验收不适用。
- [ ] 分别使用未授权目录、不可访问目录和不支持的报告目录登记/重新登记，确认三类安全提示不同。
- [ ] 点击“检查删除条件”，确认只显示预检结果，案件、草稿、来源、归档和正式产物均未删除。

## 当前状态

- 实现完成。
- 自动化代码验证通过；当前变更包的严格文档检查仍等待剩余人工验收任务处理。
- 等待 Phase 1–4 最终集成人工验收。
- 正式人工验收 gate 和最终 Review gate 均未勾选；本变更包不归档。
