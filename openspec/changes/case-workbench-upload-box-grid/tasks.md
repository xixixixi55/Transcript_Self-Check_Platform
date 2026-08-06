# Tasks: 案件工作台上传报告目录入口布局

workflow_level: 2

> Spec: `openspec/changes/case-workbench-upload-box-grid/specs/electronic-inspection-record/spec.md`
> 范围：将案件工作台的上传报告目录入口从网格上方工具条移入案件网格，作为末尾添加卡片；满页（每页 6 个）隐藏上传入口；空页仅显示上传入口；移除案件名称/编号手动输入框。

## Frontend Components / Styles（Layer 11）

- [x] T001 将上传卡片样式适配为网格填充卡片并瘦身工具条。
  - 文件：`packages/frontend/src/components/CaseWorkbenchDirectoryPickerCard.tsx`、`packages/frontend/src/platformShell.css`
  - 内容：`.case-workbench-directory-picker` 从工具条固定宽度改为填满网格格子（`width/height: 100%`）；移除 `.case-workbench-page__fields` 与 `.case-workbench-page__empty` 样式；`.case-workbench-page__submission` 只承载刷新按钮并右对齐。
  - 验证：组件测试保持通过。

## Frontend Pages（Layer 12）

- [x] T002 在案件工作台将上传入口移入案件网格并移除手动名称/编号输入。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`
  - 内容：删除 `caseName`/`caseNumber` 状态和两个输入框；`submit` 改为无参登记；上传卡片渲染到网格 `Row` 末尾，仅当 `items.length < CASE_PAGE_SIZE` 时显示；空态移除 `Empty` 组件，直接渲染仅含上传卡片的网格；工具条只保留刷新按钮。
  - 验证：页面测试覆盖满页隐藏、空态仅上传卡片、输入框移除、删除到空后上传卡片恢复。

## 综合验证

- [x] T003 运行受影响测试和 Level 2 门控。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`、`packages/frontend/src/components/CaseWorkbenchDirectoryPickerCard.test.tsx`
  - 内容：核对 delta 与最终行为，运行架构、类型、前端测试和文档检查。
  - 验证：`npm run verify:quick`、受影响前端测试、`npx tsx scripts/check-docs.ts --strict --change case-workbench-upload-box-grid`、`git diff --check`。
