# Tasks: 案件工作台删除

workflow_level: 2

> 规格：`openspec/changes/case-workbench-delete/specs/electronic-inspection-record/spec.md`
> 范围：为案件工作台补充用户确认后的真实删除能力；用户确认后允许删除任意案件状态及平台受控正式产物，外部原始资料目录仍不属于平台删除范围。

## 共享类型/共享常量（Layer 0–1）

- [x] T001 更新工作台删除 API 契约和端点常量。
  - 文件：`packages/shared/types/workbench.ts`、`packages/shared/constants/index.ts`
  - 内容：定义删除成功结果，补充删除端点常量；保留现有删除预检契约。
  - 验证：Shared typecheck。

## 前端 Hook（Layer 10）

- [x] T002 在工作台 Hook 中接入真实删除请求。
  - 文件：`packages/frontend/src/hooks/useCaseWorkbench.ts`
  - 内容：新增 `deleteCase`，调用案件 DELETE API；请求失败沿用现有工作台错误解析。
  - 验证：Hook 定向测试覆盖成功请求和失败传播。

## 前端组件（Layer 11）

- [x] T003 将卡片删除预检入口调整为删除入口。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCard.test.tsx`、`packages/frontend/src/components/CaseCardDelete.test.tsx`
  - 内容：显示“删除”操作并将点击事件交给页面确认流程，不在组件内直接删除。
  - 验证：组件测试覆盖删除操作回调，既有归档操作回归通过。

## 前端页面（Layer 12）

- [x] T004 在案件工作台增加确认弹窗和删除后刷新。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`
  - 内容：点击删除后显示“确认删除吗？”；“取消”不调用 API；“确认”调用真实删除并刷新列表。
  - 验证：页面测试覆盖确认、取消、删除成功和删除失败提示。

## 后端 Repository/Service/Controller（Layer 20–23）

- [x] T005 实现事务内案件工作数据删除。
  - 文件：`packages/backend/app/repository/case/case_deletion_repository.py`、`packages/backend/app/repository/case/case_workflow_repository.py`、`packages/backend/app/services/case/case_lifecycle_service.py`、`packages/backend/app/controllers/workbench_controller.py`
  - 内容：新增 DELETE `/workbench/cases/{case_id}`；按外键依赖顺序删除案件工作台记录，不再以案件状态、任务、租约、清理流程或正式产物作为用户确认后的阻断条件。
  - 验证：Service/Controller 测试覆盖任意状态的真实删除和部署隔离。

## 综合验证

- [x] T006 运行受影响测试和 Level 2 门控。
  - 文件：`tests/test_workbench_services.py`、`tests/test_workbench_controller.py`、`packages/frontend/src/hooks/useCaseWorkbench.test.tsx`、`packages/frontend/src/components/CaseCard.test.tsx`、`packages/frontend/src/components/CaseCardDelete.test.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`
  - 内容：补充合成数据回归，核对 delta 与实现并完成文档同步。
  - 验证：`npm run verify:quick`、受影响前后端测试、当前变更严格文档检查、`git diff --check`。

## 需求修订：确认后允许删除任意状态和正式产物

- [x] T007 移除确认后的状态/任务/租约/清理/正式产物阻断。
  - 文件：`packages/backend/app/repository/case/case_deletion_repository.py`、`packages/backend/app/controllers/workbench_controller.py`
  - 内容：删除预检始终返回允许；确认后的 DELETE 对归档完成、归档中断、解析失败、处理中和已清理状态均执行真实删除。
  - 验证：Service/Controller 状态回归。

- [x] T008 清理平台自有正式产物和临时文件。
  - 文件：`packages/backend/app/services/case/case_artifact_deletion_service.py`、`packages/backend/app/repository/archive/archive_manifest_repository.py`、`packages/backend/app/repository/archive/archive_manifest_index_repository.py`、`packages/backend/app/services/case/case_lifecycle_service.py`、`packages/backend/app/services/runtime/workbench_factory_service.py`
  - 内容：删除案件受控压缩目录及删除后留下的空案件上级目录、Word 产物、归档快照、临时文件和案件图片，并同步 Manifest 索引；拒绝越界路径，不删除外部来源目录。
  - 验证：正式 RAR/Manifest/Word、图片、来源目录保留和路径安全测试。

- [x] T009 补充需求修订的自动化证据。
  - 文件：`tests/test_workbench_services.py`、`tests/test_workbench_controller.py`、`tests/test_case_artifact_deletion_service.py`
  - 内容：覆盖归档完成、归档未完成（含上下文绑定/发布 fence 子记录）、解析失败、活动任务和正式产物删除。
  - 验证：受影响 pytest 定向测试。

- [x] T010 完成需求修订后的规格同步和 Level 2 门控。
  - 内容：同步 delta spec、living spec 和 data-model，运行架构、类型、前后端测试、资产和严格文档检查。
  - 验证：`npm run verify:quick`、受影响测试、`npx tsx scripts/check-docs.ts --strict --change case-workbench-delete`、`git diff --check`。

- [x] T011 将标准删除入口移出更多操作菜单。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCardDelete.test.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`
  - 内容：卡片直接展示“删除”按钮；“更多操作”不再提供标准或“彻底删除”入口，删除确认和服务端请求流程保持不变。
  - 验证：组件测试覆盖直接点击删除回调且菜单不再包含标准删除项；页面测试覆盖取消确认和确认删除回归。
  - 后续修订：T016 已按案件阶段重新分配入口权重；本任务保留为历史实现证据。

- [x] T012 运行需求修订后的前端验证和 Level 2 门控。
  - 内容：核对独立删除入口与 delta spec 一致，运行受影响前端测试、架构、类型、资产和严格文档检查。
  - 验证：`npm run verify:quick`、受影响 Vitest、`npx tsx scripts/check-docs.ts --strict --change case-workbench-delete`、`git diff --check`。

- [x] T013 统一所有案件状态的删除入口和交互语义。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/components/CaseCardCompletion.test.tsx`
  - 内容：移除已导出案件独立的“彻底删除”菜单项；所有案件状态只使用卡片上的“删除”按钮，并复用同一确认弹窗和 DELETE API。
  - 验证：导出完成卡片测试覆盖统一“删除”回调，更多操作菜单不出现“彻底删除”。
  - 后续修订：T016 保留统一删除能力，但将已导出设为直接推荐操作、其他状态收纳到更多菜单。

- [x] T014 清理案件关联的短路径归档快照及其辅助文件。
  - 文件：`packages/backend/app/services/case/case_artifact_deletion_service.py`、`tests/test_case_artifact_deletion_service.py`
  - 内容：按数据库中案件绑定的快照定位清理 `.inputs`、`.i`、`.t` 受控目录中的最终快照、`.copying` 临时目录和 owner marker；不删除其他案件快照或共享根目录，并继续拒绝越界定位。
  - 验证：后端定向测试覆盖标准相对 locator、`.i` locator、marker/临时目录清理和来源目录保留。

- [x] T015 完成统一删除需求的实现核对和 Level 2 门控。
  - 内容：核对统一入口与短路径快照清理的 delta spec、living spec 和实现一致。
  - 验证：`npm run verify:quick`、受影响前后端测试、`npm run verify:docs:strict -- --change case-workbench-delete`、`git diff --check`。

- [x] T016 按案件阶段收敛删除入口权重并更新确认文案。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、对应前端测试、本变更包 delta spec 与 living spec。
  - 内容：已导出阶段以「删除案件」为推荐操作，其他阶段将删除保留为更多菜单低权重能力；所有入口继续复用同一确认和 DELETE API；已导出确认明确说明已导出到目标目录的文件不会被删除。
  - 验证：状态操作矩阵、已导出菜单、确认/取消回归、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。
  - 证据：组件测试覆盖非导出阶段更多菜单删除、已导出直接删除与精确次要菜单；页面测试覆盖确认/取消及“已导出到目标目录的文件不会被删除”文案；独立复审 PASS。
