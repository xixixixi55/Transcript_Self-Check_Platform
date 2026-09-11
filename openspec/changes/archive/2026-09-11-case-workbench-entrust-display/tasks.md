# Tasks: 案件工作台展示委托信息

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: 案件卡片委托信息与阶段提示精简场景已同步到现行 electronic-inspection-record 规格，列表只读投影合同已同步到 data-model。

> 规格：`openspec/changes/case-workbench-entrust-display/specs/electronic-inspection-record/spec.md`
> 范围：案件卡片标题继续展示案件名称，将案件编号辅助信息替换为报告中的委托人和委托单位。

## 共享类型（Layer 0）

- [x] T001 为案件列表项增加委托单位和委托人只读投影。
  - 文件：`packages/shared/types/workbench.ts`
  - 验证：共享与前端 TypeScript 类型检查。

## 后端服务（Layer 21）

- [x] T002 从既有案件草稿报告投影委托单位和委托人到工作台列表，不新增持久化副本。
  - 文件：`packages/backend/app/services/case/case_lifecycle_service.py`、`tests/test_workbench_services.py`
  - 验证：后端定向测试区分解析前兜底与解析后真实委托信息。

## 前端组件（Layer 11）

- [x] T003 保持案件名称为卡片标题，并以带标签的委托人、委托单位替换案件编号。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCard.test.tsx`、`packages/frontend/src/caseWorkbench.css`
  - 验证：组件定向测试覆盖名称标题、委托信息、缺失兜底及案件编号不再展示。

## 收尾

- [x] T004 核对增量与实现、同步现行规格，并完成 Level 2 门控。
  - 验证：`npm run verify:quick`、受影响前后端测试、`npm run verify:docs:strict -- --change case-workbench-entrust-display`、`git diff --check`。
  - manual_acceptance: N/A（信息展示合同由组件测试覆盖，无新增复杂视觉或真实桌面依赖）。
  - 证据：案件卡片 3 个测试文件共 24 项通过；工作台服务 25 项通过；`npm run verify:quick` 与 `git diff --check` 通过；严格文档检查在任务收尾后复跑。

## 反馈补丁：精简阶段提示

- [x] T005 删除案件卡片各阶段中与标题、状态数据或操作按钮重复的下一步提示文案。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/components/CaseCardCompletion.test.tsx`、`packages/frontend/src/caseWorkbench.css`。
  - 内容：保留阶段标题、时间、分卷/进度信息和操作按钮；删除压缩后台运行、补盘后导出、压缩完成后导出等重复说明，并清理不再使用的提示样式。
  - 验证：案件卡片完成状态定向测试、前端类型检查、Impeccable 检测、限定范围严格文档检查和 `git diff --check`。
  - manual_acceptance: N/A（用户截图已明确待删除元素，组件回归可直接验证文案不存在）。
  - 证据：案件卡片 3 个测试文件共 24 项通过；`npm run verify:quick` 与 `git diff --check` 通过；Impeccable 机械检测返回零项问题；严格文档检查在任务收尾后复跑。
