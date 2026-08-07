# 审核编辑界面移除案件模板与共享默认值展示

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: openspec/specs/electronic-inspection-record/spec.md REQ-007 共享默认值展示与保存状态; REQ-027 模板选择器

> Spec: `openspec/changes/remove-audit-edit-template-and-defaults-display/specs/electronic-inspection-record/spec.md`
> 范围：删除审核编辑界面（案件审核编辑页）的“案件 Word 模板”展示块与“共享默认值设置/保存状态”展示；**只移除前端展示，不改变共享默认值与模板后台功能**。

## 级别与范围

- 级别：Level 2。
- 本变更独立于 `extensible-report-template-platform` 与 `case-shared-defaults`，只维护本文件；不创建 proposal、design。
- 目标是删除审核编辑界面的两类展示，不新增或扩大任何能力；后端模板注册/审核/导出校验与共享默认值持久化/预填逻辑保持不变。
- 当前作用域为前端 Layer 11（Components）、Layer 12（Pages）及对应测试；不触碰 Layer 10 Hooks 的行为逻辑。

## 当前实现盘点

### 需求1：案件 Word 模板展示

- 审核编辑页 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 渲染 `<TemplateSelector>`（`packages/frontend/src/components/TemplateSelector.tsx` 的“案件 Word 模板”卡片），展示已审核模板版本下拉、已审核标签、模板 ID/版本/验收摘要并可切换案件模板。
- 页面通过 `useTemplateRegistry`（`packages/frontend/src/hooks/useTemplateRegistry.ts`）加载已审核模板并保存案件模板引用；案件草稿 `case_drafts.template_ref_json` 保存 `template_id` + `version`。
- 模板注册/审核/删除管理在 `packages/frontend/src/pages/TemplateManagePage.tsx` + `packages/frontend/src/components/TemplateManager.tsx`，不受本次删除影响。

### 需求2：共享默认值设置与保存状态展示

- `packages/frontend/src/components/RecordEditorForm.tsx` 在 workbenchMode 下展示“共享默认值设置”信息块（保存范围、当前默认光盘编号前缀、修改规则说明）与“案件草稿/共享默认值”保存状态行；非 workbench 分支展示“常用字段默认设置”同类信息；并展示“请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。”警告。
- 页面级 `packages/frontend/src/components/CaseSaveStatusPanel.tsx` 展示“案件草稿/共享默认值”两种保存状态与重试/加载服务端动作，仅被审核编辑页使用。
- 共享默认值功能（后端 `shared_defaults` 表、`SharedDefaultsService`、草稿保存时的稀疏 patch、新案件预填、`useCaseDraftAutosave`/`useCaseRecordSession`）保持不变。

## 目标行为

### 需求1

- 审核编辑界面不再展示“案件 Word 模板”选择块，页面不再调用 `useTemplateRegistry`。
- 案件保留创建时保存的模板 ID 和版本；没有模板引用的兼容案件继续使用 `current-template-v1`。
- 模板注册/审核管理页、后台模板校验与导出前重新校验逻辑保持不变。

### 需求2

- 审核编辑界面不再展示“共享默认值设置”信息块、草稿/共享默认值保存状态（表单内与页面级面板）、以及“请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。”警告。
- 共享默认值功能本身保留：后端稀疏增量更新、草稿成功前提、新案件预填、字段优先级、部署实例事实源不变。
- 每次导出仍询问本次 Word 下载文件名（`WordDownloadNameDialog` 行为不变）。

## 验收标准

- [x] 审核编辑界面不展示“案件 Word 模板”卡片（已审核模板版本下拉、已审核标签、模板 ID/版本/验收摘要、应用模板版本按钮）。
- [x] 审核编辑界面不展示“共享默认值设置”信息块（保存范围、当前默认光盘编号前缀、修改规则）。
- [x] 审核编辑界面不展示“案件草稿/共享默认值”保存状态行与页面级保存状态面板。
- [x] 审核编辑界面不展示“请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。”警告提示；导出仍询问下载文件名。
- [x] 案件保留模板 ID 和版本；无模板引用案件继续使用 `current-template-v1`；模板管理页与后台校验/导出校验无回归。
- [x] 共享默认值后端功能无回归：稀疏 patch、新案预填、字段优先级、草稿成功前提、部署实例事实源测试通过。
- [x] 前端定向测试、typecheck、lint:arch、`npm run verify:quick`、当前变更 scoped strict docs 和 `git diff --check` 通过。

## 任务列表

### Layer 11 FE_Components

- [x] 修改 `packages/frontend/src/components/RecordEditorForm.tsx`：删除 workbenchMode 的“共享默认值设置”信息块与“案件草稿/共享默认值”保存状态行、非 workbench 的“常用字段默认设置”块，以及“请谨慎修改文号；每次导出均会询问本次 Word 下载文件名。”警告；移除不再使用的 `draftSaveStatus`/`sharedDefaultsSaveStatus` props；保留 `defaultDiscPrefix`（附件区光盘编号字段仍使用）。
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/components/RecordEditorForm.test.tsx` + typecheck。
- [x] 删除“案件 Word 模板”之外的页面级保存状态面板组件 `CaseSaveStatusPanel` 及其同名测试文件（`packages/frontend/src/components/` 下，整块保存状态展示移除后该组件仅被审核编辑页使用，删除后不再被引用）。
  - 验证：前端 typecheck 与组件回归测试确认无残留引用。
- [x] 更新 `packages/frontend/src/components/RecordEditorForm.test.tsx`：移除对“每次导出均会询问本次 Word 下载文件名”“保存范围：...”“只更新本轮明确修改的共享默认值”的断言；保留审核编辑区域、附件编辑器与数据摘要用例。
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/components/RecordEditorForm.test.tsx`。

### Layer 12 FE_Pages

- [x] 修改 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx`：删除 `<TemplateSelector>` 展示块与 `useTemplateRegistry` 导入/接线（含 `templateRegistry` 相关 state）；删除 `<CaseSaveStatusPanel>` 展示与不再使用的 `loadServer`/`session.retrySave`/`sharedDefaultsSaveState`/`autosave.sharedState` 引用，以及传给 `RecordEditorForm` 的保存状态 props；保留导出询问文件名、模板引用导出校验与归档决策行为。
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/pages/CaseRecordGeneratePage.test.tsx` + typecheck。
- [x] 更新 `packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`：移除对“草稿已保存，共享默认值更新失败”状态文案的断言，保留“共享默认值失败时草稿保存后可导出”行为断言；清理模板接口 mock 依赖。
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/pages/CaseRecordGeneratePage.test.tsx`。

### 验证与收尾

- [x] 运行受影响前端定向测试、typecheck、`lint:arch`、`npm run verify:quick`、当前变更 scoped strict docs（`npm run verify:docs:strict -- --change remove-audit-edit-template-and-defaults-display`）与 `git diff --check`。
- [x] 核对 delta spec 与最终行为一致，按 `delta spec → 实现核对 → sync → 检查 living spec` 同步到 `openspec/specs/electronic-inspection-record/spec.md`（REQ-007 共享默认值展示、REQ-027 模板选择器）。

## 非目标与边界

- 不修改后端模板注册/审核/删除/导出校验与共享默认值持久化/预填逻辑。
- 不删除 `TemplateSelector`、`useTemplateRegistry` 及模板平台相关测试与后台（模板平台活跃变更包仍在使用）。
- 不改变 Word 下载文件名询问（`WordDownloadNameDialog`）、草稿自动保存、revision 冲突与归档决策行为。
- 不修改 `word_templates/template.docx`，不改变 Word/VML/分页/表格/附件合同。
- 不归档本变更包，不 commit、不 push。
