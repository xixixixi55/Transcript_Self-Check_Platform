# Demo 就绪提示与来源授权引导

## 级别与范围

- 级别：Level 2。
- 本变更独立于 Phase 1D、`case-shared-defaults` 和现有案件工作台变更包，只维护本文件。
- 目标：在电子数据检查入口和案件工作台展示安全的 Demo 环境就绪状态，补充首次/重新登记来源目录的授权说明，并修正删除预检按钮语义。
- 不改变案件登记、解析、草稿、共享默认值、Legacy Parser、Word/VML/分页、Manifest、归档合同或 `word_templates/template.docx`。
- 不实现服务器配置修改、监控平台、后台探测队列、案件删除、保留期或产物清理。

## 设计说明

- 就绪 API 只返回四项固定能力的枚举状态、稳定错误码和固定处理建议；不返回路径、配置值、进程信息、命令行、异常或探测输出。
- 来源授权状态复用工作台进程内已加载的 `ArchiveAuthorizationStore` 配置结果，确保页面提示与实际登记校验一致；配置仍只在后端启动前生效。
- WinRAR 状态复用 `discover_winrar` 的能力结果，但仅投影为安全状态；不暴露可执行文件名、版本或路径。
- 归档输出根只检查既有目录的可访问/可写状态，不创建目录、不修改配置。
- 前端无法请求就绪 API 时，只能确认“后端当前不可用”，其他服务器能力显示“无法确认”。

## 验收标准

- [ ] 电子数据检查入口和案件工作台均显示后端、来源目录授权、WinRAR、归档输出根四项状态。
- [ ] 状态仅使用“已就绪 / 未配置 / 当前不可用 / 无法确认”，并附稳定错误码和固定处理建议。
- [ ] API 响应不含允许根目录内容、绝对路径、WinRAR 路径、PID、命令行、环境变量值或异常堆栈。
- [ ] 首次登记和重新登记均说明授权根约束、启动前配置和修改后重启要求。
- [ ] 未授权、不可访问、报告结构不支持在首次登记和重新登记中显示不同的安全提示。
- [ ] 案件卡片按钮显示“检查删除条件”，只调用既有删除预检，不执行删除或清理。

## 任务列表

### Layer 0–1：共享契约

- [x] 在 `packages/shared/types/demoReadiness.ts`、`packages/shared/types/index.ts` 和 `packages/shared/constants/index.ts` 增加固定就绪 DTO 与 API 端点。
- [x] 以 TypeScript typecheck 验证固定枚举、字段边界和前后端调用契约。

### Layer 20–23：后端安全快照

- [x] 在 `packages/backend/app/repository/demo_readiness_repository.py`、`packages/backend/app/services/demo_readiness_service.py`、`packages/backend/app/controllers/demo_readiness_controller.py` 和路由聚合中实现同步只读的安全快照。
- [x] 在 `tests/test_demo_readiness.py` 覆盖四项状态、异常降级、稳定错误码及路径/配置/进程信息不泄露。
- [x] 在来源控制器安全错误映射中区分未授权、不可访问和结构不支持。
- [x] 扩展 `tests/test_workbench_controller.py` 的来源登记/重新登记错误响应断言，验证稳定且不回显路径。

### Layer 10–12：前端提示与语义

- [x] 在 `packages/frontend/src/hooks/useDemoReadiness.ts` 和导出索引中实现一次性读取与网络失败安全降级。
- [x] 在 `packages/frontend/src/hooks/useDemoReadiness.test.tsx` 覆盖正常 DTO 和后端不可用降级。
- [x] 在 `packages/frontend/src/components/DemoReadinessNotice.tsx` 和来源重新登记组件中实现固定状态展示及授权说明。
- [x] 在对应组件测试中覆盖固定状态文案、无路径展示和三类来源错误提示。
- [x] 在 `ElectronicInspectionModulePage.tsx`、`CaseWorkbenchPage.tsx` 与 `CaseCard.tsx` 接入提示，并将按钮改为“检查删除条件”。
- [x] 更新页面测试，覆盖两个展示位置、首次登记说明、删除预检准确语义及安全错误提示。

### 验证与交付

- [x] 运行相关前后端定向测试、typecheck、`lint:arch`、前端生产构建、`verify:docs:strict`、`check:repository-assets` 和 `git diff --check`。
- [x] 检查 `git diff` 与 Git 状态，仅保留本变更预期文件；不 commit、不 push、不归档。

## 验证记录

- 后端定向测试：27 passed（1 个既有授权根配置 warning）。
- 前端定向测试：25 passed（保留既有 React Router / Ant Design 警告）。
- 前端全量测试：用户独立运行并报告通过；未提供测试数量和 warning 明细，不在文档中推测。
- 后端全量 pytest：用户独立运行并报告通过；未提供测试数量和 warning 明细，不在文档中推测。
- 安全测试有效性：临时回显 SYNTHETIC WinRAR 路径时脱敏测试按预期失败；恢复固定投影后通过。
- `verify:quick`、前端生产构建、`verify:docs:strict`、显式 `check:repository-assets` 和 `git diff --check`：通过。
- 轻量开发冒烟：后端健康检查与前端预览可启动；电子数据检查入口和案件工作台可打开；就绪提示、授权说明和“检查删除条件”可见；未发现浏览器控制台错误、白屏、崩溃或数据库迁移失败。该结果不等于正式人工验收。

## 人工验收

- [ ] 后端可用时进入电子数据检查入口和案件工作台，确认四项状态与处理建议一致。
- [ ] 停止后端后刷新页面，确认后端显示“当前不可用”，其余项显示“无法确认”，且页面不出现服务器细节。
- [ ] 分别使用未授权目录、不可访问目录和不支持的报告目录登记/重新登记，确认三类安全提示不同。
- [ ] 点击“检查删除条件”，确认只显示预检结果，案件、草稿、来源、归档和正式产物均未删除。

## 当前状态

- 实现完成。
- 自动验证通过。
- 等待 Phase 1–4 最终集成人工验收。
- 正式人工验收 gate 和最终 Review gate 均未勾选；本变更包不归档。
