# Tasks: 案件工作台上传报告目录入口布局

workflow_level: 2

> 规格：`openspec/changes/case-workbench-upload-box-grid/specs/electronic-inspection-record/spec.md`
> 范围：将案件工作台的上传报告目录入口从网格上方工具条移入案件网格，作为末尾添加卡片；满页（每页 6 个）隐藏上传入口；空页仅显示上传入口；移除案件名称/编号手动输入框。

## 前端组件/样式（Layer 11）

- [x] T001 将上传卡片样式适配为网格填充卡片并瘦身工具条。
  - 文件：`packages/frontend/src/components/CaseWorkbenchDirectoryPickerCard.tsx`、`packages/frontend/src/platformShell.css`
  - 内容：`.case-workbench-directory-picker` 从工具条固定宽度改为填满网格格子（`width/height: 100%`）；移除 `.case-workbench-page__fields` 与 `.case-workbench-page__empty` 样式；`.case-workbench-page__submission` 只承载刷新按钮并右对齐。
  - 验证：组件测试保持通过。

## 前端页面（Layer 12）

- [x] T002 在案件工作台将上传入口移入案件网格并移除手动名称/编号输入。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`
  - 内容：删除 `caseName`/`caseNumber` 状态和两个输入框；`submit` 改为无参登记；上传卡片渲染到网格 `Row` 末尾，仅当 `items.length < CASE_PAGE_SIZE` 时显示；空态移除 `Empty` 组件，直接渲染仅含上传卡片的网格；工具条只保留刷新按钮。
  - 验证：页面测试覆盖满页隐藏、空态仅上传卡片、输入框移除、删除到空后上传卡片恢复。

## 前端组件/页面（Layer 11–12）

- [x] T003 为案件卡片增加当前页序号。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/platformShell.css`、对应前端测试文件
  - 内容：案件卡片按当前页渲染 1–6 的可见序号；上传报告目录卡片不参与编号。
  - 验证：页面测试覆盖满页 1–6 序号和非满页连续编号，组件定向测试覆盖序号展示。
  - 后续修订：T005 已确认分页位置序号无业务意义并移除；本任务保留为历史实现证据。

## 综合验证

- [x] T004 运行受影响测试和 Level 2 门控。
  - 文件：`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`、`packages/frontend/src/components/CaseWorkbenchDirectoryPickerCard.test.tsx`
  - 内容：核对 delta 与最终行为，运行架构、类型、前端测试和文档检查。
  - 验证：`npm run verify:quick`、受影响前端测试、`npx tsx scripts/check-docs.ts --strict --change case-workbench-upload-box-grid`、`git diff --check`。

- [x] T005 移除无业务意义的案件列表序号并保持上传入口不变。
  - 文件：`packages/frontend/src/components/CaseCard.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/platformShell.css`、对应前端测试、本变更包 delta spec 与 living spec。
  - 内容：删除当前页序号圆圈与 position 传递；上传报告目录的 DOM、尺寸、虚线框、图标、文案、间距、悬停、点击行为和 `.case-workbench-directory-picker` 样式保持不变。
  - 验证：页面和组件测试断言无序号且上传入口布局/行为回归通过，运行 scoped strict docs 与 `git diff --check`。
  - 证据：工作台与上传目录组件回归测试通过；生产 diff 未修改 `CaseWorkbenchDirectoryPickerCard.tsx` 或 `.case-workbench-directory-picker` 选择器，浏览器实际渲染核对虚线框、图标、文案和入口行为保持原状；独立复审 PASS。
