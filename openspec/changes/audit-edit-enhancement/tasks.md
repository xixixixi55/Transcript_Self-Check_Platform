# Tasks: 审核编辑界面增强

workflow_level: 3

> Spec: `openspec/changes/audit-edit-enhancement/specs/electronic-inspection-record/spec.md`
> 按架构层级从低到高排列（Layer 2、10 → 12、21）；包含审核编辑增强与既有解析/导出缺陷修复。

---

## 🔴 Phase 1: Frontend Hooks 层（Layer 10）

- [x] T001 **新增 useEditableState Hook**
  - 文件：`packages/frontend/src/hooks/useEditableState.ts`（新建）
  - 内容：
    - `editingField: string | null` — 当前处于编辑态的字段 ID
    - `startEdit(fieldId: string)` — 进入编辑
    - `stopEdit()` — 退出编辑
    - `isEditing(fieldId: string) -> bool` — 判断某字段是否在编辑
    - 同一时间最多一个字段处于编辑态（点击 B 字段时 A 自动退出编辑）
  - 验证：`pnpm typecheck`

- [x] T002 **useEditableState 测试**
  - 文件：`packages/frontend/src/hooks/useEditableState.test.ts`（新建）
  - 覆盖场景：
    - startEdit → isEditing 返回 true
    - stopEdit → isEditing 返回 false
    - 点击新字段 → 旧字段自动退出
    - 同时只有一个 editingField
  - 依赖：T001
  - 验证：`pnpm --filter @biji/frontend test`

---

## 🟣 Phase 2: Frontend Components 层（Layer 11）

- [x] T003 **新增 EditableField 组件**
  - 文件：`packages/frontend/src/components/EditableField.tsx`（新建）
  - 内容：
    - Props: `type: 'text' | 'textarea' | 'select'`, `value: string`, `onChange: (val: string) => void`, `options?: {label, value}[]`, `placeholder?: string`
    - 默认模式：纯文本 `<Text>` 展示，空值时显示占位符"点击编辑"
    - 点击切换为 `<Input>` / `<TextArea>` / `<Select>`（根据 type）
    - 失焦或 Enter → 保存，Escape → 取消
    - 按 design.md 使用组件内 `useState` 管理独立编辑态；`useEditableState` 保留给页面级协调场景
    - 使用 Ant Design `Typography.Text` + `Input` / `Input.TextArea` / `Select`
  - 覆盖 Spec：REQ-019
  - 验证：`pnpm typecheck`

- [x] T004 **EditableField 组件测试**（已由 T012 补齐渲染与交互覆盖）
  - 覆盖场景：
    - 默认渲染文本 → 点击进入编辑 → 输入文字 → 失焦保存 → onChange 被调用
    - Escape → 放弃修改，恢复原值
    - type="textarea" → 渲染 TextArea
    - type="select" → 渲染 Select
    - 空值 → 显示"点击编辑"占位符
  - 依赖：T003
  - 覆盖 Spec：REQ-019
  - 验证：`pnpm --filter @biji/frontend test`

- [x] T005 **新增 ProcessStepsEditor 组件**
  - 文件：`packages/frontend/src/components/ProcessStepsEditor.tsx`（新建）
  - 内容：
    - Props: `steps: ProcessStep[]`, `onChange: (steps: ProcessStep[]) => void`
    - 展示 4 个步骤，步骤号固定不可编辑，内容用 EditableField 渲染
    - 简洁排版，每个步骤一行（步骤号 + 内容）
  - 覆盖 Spec：REQ-017
  - 验证：`pnpm typecheck`

- [x] T006 **新增 SoftwareToolsList 组件**
  - 文件：`packages/frontend/src/components/SoftwareToolsList.tsx`（新建）
  - 内容：
    - Props: `tools: SoftwareItem[]`, `onChange: (tools: SoftwareItem[]) => void`
    - 列表展示，每个工具的版本号用 EditableField 渲染
    - 工具名称固定不可修改
  - 覆盖 Spec：REQ-017
  - 验证：`pnpm typecheck`

- [x] T007 **新增 ExtractListEditor 组件**
  - 文件：`packages/frontend/src/components/ExtractListEditor.tsx`（新建）
  - 内容：
    - Props: `tableData: TableData`, `onChange: (data: TableData) => void`
    - 使用 Ant Design Table 组件，列可编辑，行可增删
    - 默认空表格（columns/rows 为空时展示占位提示）
  - 覆盖 Spec：REQ-017
  - 验证：`pnpm typecheck`

---

## 🔵 Phase 3: Frontend Pages 层（Layer 12）

- [x] T008 **修改 RecordGeneratePage — 补齐字段**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`（修改）
  - 内容：
    - 集成 `EvidenceEditor`（已存在，路径 `../components/EvidenceEditor`）
    - 集成 `InspectorEditor`（已存在，路径 `../components/InspectorEditor`）
    - 集成 `ProcessStepsEditor` → (三) 检查过程
    - 集成 `SoftwareToolsList` → (二) 软件工具
    - 集成 `ExtractListEditor` → 附件1
    - 移除 `resultText` 拼接变量，替换为 7 个独立 `EditableField`
    - (一) 检查方法 `disabled` 属性改为可编辑
    - 保持正确的章节编号顺序：(一)~(九) 依次排列
  - 依赖：T003, T005, T006, T007
  - 覆盖 Spec：REQ-017, REQ-018
  - 验证：`pnpm typecheck`

- [x] T009 **修改 RecordGeneratePage — 替换交互模式**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`（修改）
  - 内容：
    - 将所有 `Form.Item` + `Input` / `TextArea` 替换为 `EditableField`
    - 委托单位 → `<EditableField type="text" ... />`
    - 委托人 → `<EditableField type="text" ... />`
    - 委托时间 → `<EditableField type="text" ... />`
    - 案件简要情况 → `<EditableField type="textarea" ... />`
    - 检查要求 → `<EditableField type="textarea" ... />`
    - 检查起止时间 → `<EditableField type="text" ... />`
    - 检查地点 → `<EditableField type="text" ... />`
    - 检查方法 → `<EditableField type="textarea" ... />`
    - 检查设备硬件 → `<EditableField type="select" ... />`
    - 光盘编号 → `<EditableField type="text" ... />`
    - 移除 `<Form>` 包装（不再需要 Ant Design Form 管理状态）
    - 移除 Ant Design `Input`、`TextArea`、`Select` 的直接使用
  - 依赖：T003, T008
  - 覆盖 Spec：REQ-007, REQ-019
  - 验证：`pnpm typecheck` + `pnpm dev` 手动验证页面

- [x] T010 **集成测试 — 前端构建验证**
  - 文件：无新文件
  - 内容：
    - `pnpm typecheck` — 类型检查
    - `npm run build` — 前端生产构建
    - `pnpm dev` — 手动验证：上传 → 预览 → 点击各字段 → 编辑 → 失焦 → 值更新
  - 关键检查点：
    - 所有字段可见（不含 Q1/Q2 待确认项）
    - 点击切换编辑模式，失焦保存
    - EvidenceEditor / InspectorEditor 增删改正常
    - 导出后 Word 内容反映编辑后的值
  - 依赖：T008, T009
  - 验证：手动操作 + 自动化构建验证

---

## 🟠 Phase 4: 审查整改

- [x] T011 **结构化编辑器统一 click-to-edit 交互**
  - 文件：`packages/frontend/src/components/EvidenceEditor.tsx`、`InspectorEditor.tsx`、`ExtractListEditor.tsx`
  - 内容：将检材、人员和提取清单的文本编辑入口改为复用 `EditableField`，保持添加、删除和数据回调行为不变。
  - 覆盖 Spec：REQ-007、REQ-017、REQ-019
  - 验证：`pnpm --filter @biji/frontend typecheck`

- [x] T012 **补齐 EditableField 与审核编辑区组件测试**
  - 文件：`packages/frontend/src/components/EditableField.test.tsx`、`StructuredEditors.test.tsx`、`RecordEditorForm.test.tsx`
  - 内容：覆盖文本展示、点击编辑、失焦/Enter 保存、Escape 取消、textarea/select、空值占位及各编辑区域渲染。
  - 依赖：T011
  - 覆盖 Spec：REQ-007、REQ-017、REQ-018、REQ-019、REQ-023、REQ-024
  - 验证：`pnpm --filter @biji/frontend test`

- [x] T013 **修复后端测试命令路径**
  - 文件：`packages/backend/package.json`
  - 内容：从 `packages/backend/app` 正确定位项目根目录的 `tests/`，使 pytest 能收集后端用例。
  - 覆盖 Spec：REQ-027
  - 验证：`pnpm --filter @biji/backend test`

- [x] T014 **文档漂移检查忽略 pytest 测试缓存**
  - 文件：`scripts/check-docs.ts`
  - 内容：目录扫描排除 `.pytest_cache/` 等运行时 Python 测试缓存，避免将其误报为未文档化目录。
  - 覆盖 Spec：REQ-028
  - 验证：`npm run check-docs`

- [x] T015 **验证变更包范围与工程门控**
  - 内容：确认 proposal、design、tasks 与 REQ-020~028 的实际修复一致；运行项目验证和测试门控。
  - 依赖：T014
  - 验证：`npm run pre-commit`

## 🟢 Phase 5: 检查人员卡片布局与添加入口

- [x] T016 **改造检查人员卡片布局和添加入口**
  - 文件：`packages/frontend/src/components/InspectorEditor.tsx`、`packages/frontend/src/reviewWorkspace.css`
  - 内容：检查人员卡片使用紧凑正方形网格，宽屏每行最多 3 个，窄屏自动降为 2 个或 1 个；列表末尾始终保留虚线加号卡片，点击后直接展示未添加的启用人员卡片并立即添加；保留删除和拖拽排序行为。
  - 覆盖 Spec：REQ-030
  - 验证：前端组件定向测试、类型检查和人工窄屏验收。
  - 人工验收：通过（用户确认，2026-08-03）。

- [x] T017 **补充检查人员卡片布局和添加流程测试**
  - 文件：`packages/frontend/src/components/StructuredEditors.test.tsx`、`packages/frontend/src/components/InspectorEditor.test.tsx`
  - 内容：覆盖空列表、已有人员、超过 3 人换行所需的网格标记、加号卡片持续存在、直接展示并添加未添加人员以及现有删除/拖拽回归。
  - 依赖：T016
  - 覆盖 Spec：REQ-030
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/components/StructuredEditors.test.tsx src/components/InspectorEditor.test.tsx`（2 个文件、11 个用例通过）

## 🟢 Phase 6: 检查人员保存收敛修复

- [x] T018 **修复人员修改后的重复 PATCH 保存循环**
  - 文件：`packages/frontend/src/hooks/useCaseDraftAutosave.ts`、`packages/frontend/src/hooks/useCaseDraftAutosave.test.tsx`、`packages/frontend/src/hooks/useCaseRecordSession.ts`、`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`
  - 内容：为成功保存的草稿建立可编辑内容签名；令牌变化但草稿内容未变化时清理 pending，不重复发送相同请求；真实后续修改继续串行保存。
  - 覆盖 Spec：REQ-031
  - 验证：Hook 保存并发回归、审核编辑页面人员选择保存回归；测试汇总为 2 个相关文件/10 个 Hook 用例通过及页面用例通过。

## 🟢 Phase 7: 光盘编号输入入口收敛

- [x] T019 **移除附件区重复的光盘编号输入**
  - 文件：`packages/frontend/src/components/ReviewAttachmentsSection.tsx`、`RecordEditorForm.tsx`、`ArchiveCompletionPanel.tsx`、`ArchiveCompletionPanel.test.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、`packages/frontend/src/components/RecordEditorForm.test.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`
  - 内容：删除附件区“附件3：光盘编号”编辑入口及仅为其服务的默认前缀接线；页面顶部首个光盘编号输入在压缩前和压缩中常驻并写入案件草稿，压缩完成待映射时复用同一位置提交盘号映射；保留附件日期与格式校验的只读反馈。
  - 覆盖 Spec：REQ-007
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/components/ArchiveCompletionPanel.test.tsx src/components/RecordEditorForm.test.tsx src/pages/CaseRecordGeneratePage.test.tsx` + 前端 typecheck + `lint:arch`。

## 🟢 Phase 8: 人工检材派生内容同步

- [x] T020 **修复人工检材未同步到检查过程和检查结果**
  - 文件：`packages/shared/utils/softwareProjectionUtils.ts`、`packages/frontend/src/__tests__/softwareProjectionUtils.test.ts`、`packages/frontend/src/hooks/useCaseDraftAutosave.test.tsx`、本变更包 delta spec。
  - 内容：检材列表增删、改号或排序时，统一投影（三）检查过程的检材相关步骤与（四）检查结果的检材编号；不覆盖与检材无关的环境检查步骤。
  - 覆盖 Spec：REQ-007“人工检材同步到检查过程和检查结果”。
  - 验证：增删、改号、排序、非检材步骤保持及 autosave PATCH 载荷定向 Vitest 2 files / 15 passed；完整前端测试退出码 0；临时禁用投影后精确回归 1 failed、恢复后通过；架构检查、TypeScript 类型检查及 `verify:quick` 通过。
  - code_review: [PASS] 首轮因增删改排、失配和持久化载荷覆盖不足驳回；补齐测试后第 2 轮独立复审确认 MUST FIX CLOSED，无新 MUST FIX。
  - final_gate: [PASS] 同一冻结候选以 `background-compression-archive-completion` scope 执行一次全仓 `verify:full`，预检、架构、类型、治理、资产、完整测试、生产构建和该变更严格文档全部通过；本变更另执行 scoped strict docs，13 checks / 0 drift。
  - manual_acceptance: N/A（数据投影、持久化载荷和导出门控由合成数据自动化覆盖；未改变 Word 视觉版式或桌面交互。）

## 🟢 Phase 9: 审核提示与 Word 文案格式修正

- [x] T021 **修正案件简要提示、MD5/来源/版本文案与 Word 标题格式**
  - 文件：`packages/frontend/src/components/ReviewIntroductionSection.tsx`、`ReviewInspectionSection.tsx`、`ExtractListEditor.tsx`、归档展示组件与相关测试；`packages/shared/utils/softwareProjectionUtils.ts`；`packages/backend/app/repository/archive_report_metadata_repository.py`；`packages/backend/app/services/report_parser_service.py`、`attachment_plan_service.py`、`archive_manifest_projection_service.py`、`archive_task_result_service.py`、`document_builder_service.py`、`template_filler_service.py` 及相关测试。
  - 内容：案件简要始终提示报告解析可能不准确并需人工核对，尾部空格/换行时额外警告；用户可见及 Word 中的 MD5 统一大写；固定清单来源统一为“检材内提取”；步骤 4 只在“版本号为……”中展示具体版本；Word 主标题居中加粗，固定清单标题加粗。
  - 覆盖 Spec：REQ-032。
  - 验证：前端组件/投影定向 Vitest，后端解析/附件计划/模板填充定向 pytest，DOCX XML 与 officecli 校验、人工视觉检查，架构/类型检查及当前变更 scoped full gate。
  - 证据：受影响后端测试 99 passed（核心四文件 94 + Manifest 投影 5），前端定向 3 files / 22 passed；审查整改后的 batch/兼容投影/模板路径 33 passed；架构检查、类型检查、`git diff --check` 通过。合成 DOCX 经 officecli validate 无错误，6 页缩略图确认主标题居中加粗、固定清单标题加粗、来源与 MD5 格式正确。独立 Code Review 首轮发现兼容投影和 batch 回退遗漏；整改、全仓回归修复及区分性断言补充后最终复审 PASS。
  - final_gate: [PASS] 冻结候选执行 `npm run verify:full -- --change audit-edit-enhancement`，预检、架构、类型、治理、资产、全仓测试、生产构建和 scoped strict docs 全部通过。
  - manual_acceptance: [PASS] 使用完全合成数据生成 DOCX，officecli validate 无错误；HTML 渲染 6 页缩略图确认主标题居中加粗、固定清单标题加粗，清单来源与 MD5 大小写符合要求。

## 🟢 Phase 10: 委托单位共享前缀

- [x] T022 **增加可清空的委托单位共享前缀并接入 Word 导出**
  - 文件：`packages/shared/types/`；`packages/frontend/src/components/ReviewIntroductionSection.tsx`、`packages/frontend/src/hooks/useCaseRecordSession.ts`；`packages/backend/app/repository/shared_defaults_repository.py`、`case_draft_service.py`、`canonical_*`、`template_filler_service.py`、`document_builder_service.py` 及相关测试。
  - 内容：报告识别单位保持独立；前缀作为当前案件字段和共享默认值保存并允许清空；新案件从共享默认值预填；模板与 batch 回退导出均直接拼接前缀和识别单位。
  - 覆盖 Spec：REQ-ENTRUST-UNIT-PREFIX-001。
  - 验证：共享默认值/草稿初始化后端测试、审核编辑与稀疏 patch 前端测试、两条 Word 导出路径测试、架构/类型检查、独立 Review 与 scoped full gate。
  - 证据：后端共享默认值、Canonical 与两条 Word 路径定向测试 50 passed；前端组件/Hook 2 files / 16 passed，页面集成 16 passed；核心逻辑变异校验分别得到预期 1 failed 与 2 failed，恢复后 3 passed；架构、类型和仓库资产检查通过。
  - code_review: [PASS] 首轮发现 Canonical 跨语言契约未同步及测试 fixture 合规问题；同步共享类型/契约清单、补充三类双向投影测试并替换为显式合成数据后，独立复审确认全部 MUST/SHOULD FIX CLOSED。
  - final_gate: [PASS] 冻结候选执行 `npm run verify:full -- --change audit-edit-enhancement`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。

## 🟢 Phase 12: 附件摘要与附件一表头排版修复

- [x] T025 **补齐附件摘要标识并收紧附件一短表头排版**
  - 文件：`packages/backend/app/services/template_filler_service.py`、`document_builder_service.py`、`tests/test_template_filler_service.py`、`tests/test_attachment_docx_renderer.py`、`tests/test_document_builder_service.py`、本变更包 delta spec。
  - 内容：正式模板路径更新附件摘要时保留“附件：”前缀；“电子数据”“来源”表头统一为无异常缩进、字符间距或文字缩放的居中紧凑文本；officecli batch 兼容路径同步保持摘要前缀和表头居中。
  - 覆盖 Spec：REQ-032“Word 附件摘要保留附件标识”“附件一短表头使用紧凑格式”。
  - 验证：模板与 batch 两条 Word 路径定向 pytest、合成 DOCX XML 断言、officecli validate、人工视觉检查、架构/类型、`verify:quick` 和 scoped strict docs。
  - 证据：正式模板与 batch 兼容路径定向 pytest 74 passed；新增可区分测试向两个短表头注入 `w:ind`、`w:spacing`、`w:w`、`w:fitText` 后，经 Manifest 正式渲染逐项确认清除；`lint:arch`、typecheck、`verify:quick` 与 `git diff --check` 通过；合成 DOCX 经 officecli validate 无错误。
  - code_review: [PASS] 首轮要求补充异常字符间距/缩放的 Manifest 正式路径区分性测试，并纠正人工验收记录；整改后第二轮独立复审确认全部 MUST/SHOULD FIX CLOSED。
  - final_gate: [PASS] 使用短仓库外临时目录执行 `npm run verify:full -- --change audit-edit-enhancement`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。
  - manual_acceptance: [PASS] 使用完全合成数据生成 11 页 DOCX，经 Microsoft Word 后台导出 PDF 并逐页渲染 PNG 检查；附件摘要显示“附件：1、电子数据提取固定清单”，后续编号对齐；附件一“电子数据”“来源”连续居中且无拉宽空隙；全篇未见新增裁切、重叠、分页或页脚异常。

## 🟡 Phase 13: 附件摘要条件分页

- [x] T026 **按当前页剩余空间决定附件摘要是否独立分页**
  - 文件：`packages/backend/app/services/template_filler_service.py`、`tests/test_template_filler_service.py`、本变更包 proposal/design/delta spec。
  - 内容：移除附件摘要首段的无条件分页；在检查结果后保留三个空白行；将三条摘要、摘要后留白、检查人签名、双横线及日期约束为不可跨页拆分的连续块，使完整区域在剩余空间足够时留在当前页、空间不足时整体移到下一页；独立分页时保持变更前原始版式和纵向位置；附件一及后续附件保持既有分页规则。
  - 覆盖 Spec：REQ-032“Word 附件摘要按剩余空间条件分页”。
  - 验证：使用明确合成数据新增 OOXML 区分性断言，覆盖三行留白、无固定分页符、摘要连续不可拆分、签名/横线/日期结构不变及附件一分页不变；运行模板填充定向 pytest、`verify:quick`、当前变更 scoped strict docs；分别生成“同页可容纳”和“同页不可容纳”DOCX，经 Microsoft Word 导出 PDF 后人工检查实际分页。
  - 证据：模板填充、附件渲染和 batch 文书构建定向 pytest 79 passed；架构检查、类型检查、仓库资产卫生和 `git diff --check` 通过；两份合成 DOCX 经 officecli validate 均无错误。Microsoft Word 实际分页中，共页样例的检查结果、三条摘要、签名和日期均位于第 2 页；独立页样例的检查结果位于第 2 页，三条摘要、签名和日期整体位于第 3 页。两份 Word 导出 PDF 渲染检查未见拆页、重叠或裁切。
  - code_review: [PASS] 首轮独立审查确认架构、静态分页结构和代码质量通过，但要求回填已完成的 Word/PDF 人工验收证据、补充三条摘要自身的版式属性回归，并更新过时函数说明；整改后复审确认 MUST/SHOULD FIX 全部关闭，五维审查通过。
  - final_gate: [BLOCKED] `verify:full -- --change audit-edit-enhancement` 的预检、架构、类型、治理、资产和前端 368 项测试通过；后端 1145 passed / 3 skipped，仅 `test_long_snapshot_paths_use_short_private_root_without_changing_source_tree` 因当前 pytest 临时根过长使可构造中间段为 14（测试要求至少 16）而失败。本任务定向 79 项和失败用例外的数据库权限问题均已验证与分页改动无关；另有任务开始前已存在的 39 项 agent-tooling mirror drift。达到 Harness 单任务验证循环上限后停止继续重跑。
  - manual_acceptance: [PASS] Microsoft Word/PDF 覆盖“同页可容纳”和“同页不可容纳”两个场景；独立页逐项对照变更前参考图，三条摘要、检查人签名、双横线和日期的位置及样式一致。

## 🟢 Phase 14: 附件一来源对齐修复

- [x] T027 **将附件一来源正文改为两端对齐**
  - 文件：`packages/backend/app/services/docx_attachment_xml_service.py`、`attachment_docx_renderer_service.py`、`template_filler_service.py`、`document_builder_service.py` 及相关测试、本变更包 delta spec。
  - 内容：正式模板、无 Manifest 模板兼容路径和 officecli batch 回退统一将附件一数据行“来源”列设为两端对齐；表头保持居中，逐检材换行、垂直合并及其他列版式不变。
  - 覆盖 Spec：REQ-032“附件一来源正文使用两端对齐”。
  - 验证：两条 Word 路径定向 pytest、合成 DOCX OOXML 断言、officecli validate、架构与类型检查、`git diff --check`。
  - 证据：模板正式路径、模板兼容路径与 officecli batch 回退相关测试 79 passed；合成 DOCX 的来源正文为 `w:jc=both` 且 officecli validate 0 errors；架构和类型检查通过。`pre-commit` 仅被任务开始前已有的 39 项 agent-tooling mirror drift 阻断。

## 🟡 Phase 15: 附件摘要独立页顶部留白回归

- [x] T028 **独立成页时移除三个空行，同页时保留等效间隔**
  - 文件：`packages/backend/app/services/template_filler_service.py`、`tests/test_template_filler_service.py`、本变更包 design/delta spec。
  - 内容：将摘要前的三个固定空段落转换为摘要首段的等效段前距；摘要与检查结果同页时保留三行视觉间隔，摘要块自动移到新页时使用 Word 页首段落语义抑制该间距，不在独立页顶部留下三个空行；摘要、签名、双横线、日期和附件一分页结构保持不变。
  - 覆盖 Spec：REQ-032“Word 附件摘要按剩余空间条件分页”。
  - 验证：旧实现区分性失败、模板填充定向 pytest、OOXML 精确间距与连续块断言、合成 DOCX 的 Microsoft Word/PDF 同页与独立页实际分页检查、架构/类型、人工审查与当前变更 scoped full gate。
  - 证据：旧实现定向用例以 `blank_count == 3` 精确失败；修复及有效性变异恢复后模板填充、附件渲染和 batch 文书构建 79 passed，`lint:arch`、typecheck、`verify:quick` 和 `git diff --check` 通过；两份合成 DOCX 经 officecli validate 均无错误。Microsoft Word 实际分页中，同页样例的检查结果与摘要均位于第2页且保留三行等效间隔，独立页样例的检查结果位于第2页、摘要位于第3页且从正常页首开始，不含三个空行。
  - human_review: [PASS] 2026-08-18 用户对同页与独立页两张 Word/PDF 渲染图进行人工审查，确认两种排版均符合要求；用户明确要求不启动独立 Review Agent，已停止该代理审查。
  - final_gate: [PASS] 使用 `D:\harness-temp-root` 作为短临时目录执行 `npm run verify:full -- --change audit-edit-enhancement`；预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。

## 🟡 Phase 16: 无法提取原因

- [x] T030 **在审核编辑与 Word 检材情况中支持无法提取原因**
  - 文件：`packages/shared/types/`、`packages/frontend/src/components/EvidenceEditor.tsx`、`packages/frontend/src/hooks/useReviewChecklist.ts`、`packages/backend/app/services/canonical_*`、`material_policy_service.py`、`document_builder_service.py`、`template_filler_service.py`、`packages/backend/app/repository/workbench_legacy_report.py` 及相关测试、本变更包 delta spec。
  - 内容：检材设为无法提取时显示原因输入框并保存到草稿；空原因进入待核对清单并阻止 Word 导出；检查过程步骤 1、正式模板和 officecli batch 兼容导出均使用原因替代 IMEI/序列号，存量空原因继续使用“无法提取”兜底。
  - 覆盖 Spec：REQ-034“用户填写无法提取原因”。
  - 验证：共享类型检查、审核编辑与待核对组件测试、Canonical/Legacy 持久化测试、两条 Word 生成路径定向 pytest、`verify:quick` 和 scoped strict docs。
  - manual_acceptance: N/A（字段显隐、持久化和确定性 Word 文案由合成数据自动化覆盖，不改变 Word 版式。）
  - 证据：前端原因输入、步骤 1 投影、待核对与页面导出拦截定向 Vitest 4 files / 56 passed；草稿持久化、Canonical 往返、正式模板与 officecli batch 兼容路径定向 pytest 5 passed；`lint:arch`、共享/前端 typecheck、`verify:quick`、仓库资产检查和 `git diff --check` 通过。Impeccable 机械检查仅命中 `reviewWorkspace.css` 中本任务开始前已存在的第 67、214 行告警，新增原因输入区域无命中。

---

## 任务摘要

| Phase | 层级 | 任务数 | 核心产出 |
|-------|:------:|:-----:|------|
| 🔴 P1 | Hooks (10) | 2 | useEditableState + 测试 |
| 🟣 P2 | Components (11) | 5 | EditableField + ProcessStepsEditor + SoftwareToolsList + ExtractListEditor + 测试 |
| 🔵 P3 | Pages (12) | 3 | 补齐字段 + 替换交互 + 集成验证 |
| 🟠 P4 | Components / 验证 | 5 | 审查整改、组件测试、工程门控 |
| 🟢 P5 | Components / 样式 | 2 | 检查人员卡片布局、加号添加入口与测试 |
| 🟢 P6 | Hooks (10) | 1 | 草稿保存收敛 |
| 🟢 P7 | Components / Pages (11~12) | 1 | 光盘编号统一入口 |
| 🟢 P8 | SharedUtils (2) | 1 | 人工检材派生内容同步 |
| 🟢 P9 | Components / Services | 1 | 审核提示与正式文书规范化 |
| 🟢 P10 | SharedTypes / Components / Repository / Services | 1 | 委托单位共享前缀与 Word 组合 |
| 🟢 P11 | SharedTypes / Components / Repository / Services | 2 | 软件名称、可提取状态与检材类型 Word 投影 |
| 🟢 P12 | Services | 1 | 附件摘要标识与附件一表头排版 |
| 🟡 P13 | Services | 1 | 附件摘要三行留白与条件分页 |
| 🟢 P14 | Services | 1 | 附件一来源正文两端对齐 |
| 🟡 P15 | Services | 1 | 附件摘要独立页顶部留白回归 |
| 🟡 P16 | SharedTypes / Components / Services | 1 | 无法提取原因输入、持久化与 Word 投影 |
| **合计** | **Layer 0、2、10~12、20~21** | **29** | |

> 注：后端仅包含 REQ-022、REQ-026 的既有流程修复，不新增 API 端点。

## 🟢 Phase 11: 软件名称净化与检材可提取状态

- [x] T023 **规范软件工具名称并自动判断检材是否可提取**
  - 文件：`packages/backend/app/repository/report_format_adapter.py`、`report_parser_service.py`、`material_policy_service.py`、`document_builder_service.py`、`template_filler_service.py`；`packages/shared/types/`、`packages/shared/utils/softwareProjectionUtils.ts`；`packages/frontend/src/components/EvidenceEditor.tsx` 及相关测试。
  - 内容：主软件名称保留报告识别到的软件身份，通用移除取证塔、取证设备、取证工作站等硬件括号描述并保留版本；按 IMEI1、IMEI2、序列号任一非空自动生成 `extractable`，审核页展示且允许修正；无法提取时隐藏标识，并在检材情况和检查过程追加“（无法提取）”。
  - 覆盖 Spec：REQ-034。
  - 验证：软件适配、解析、Canonical/Legacy 投影、前端组件/共享投影、模板与 batch Word 两条路径定向测试；架构检查、类型检查、`verify:quick` 和 scoped strict docs。
  - manual_acceptance: N/A（确定性字段投影和文案由合成数据自动化覆盖；不改变 Word 版式。）

## 🟢 Phase 11: 审核检材类型 Word 投影

- [x] T024 **将审核确认的检材类型追加到 Word 检材名称**
  - 文件：`packages/backend/app/services/material_policy_service.py`、`document_builder_service.py`、`template_filler_service.py` 及相关测试。
  - 内容：集中生成“设备品牌型号 + 手机/平板”的检材显示名称，供模板正式导出与 officecli batch 兼容导出共同使用；同一类型名称不重复追加。
  - 覆盖 Spec：REQ-035。
  - 验证：材料显示策略、模板填充和 batch 文书构建定向 pytest；架构、类型、`verify:quick` 和 scoped strict docs。
  - manual_acceptance: N/A（确定性文案投影由合成 DOCX 内容断言覆盖，不改变版式。）
  - 证据：受影响后端组合 88 passed；模板正式导出与 batch 兼容导出均断言“品牌型号+手机/平板+一部”，并覆盖未确认旧数据优先级、英文类型词、非类型中文子串、空设备名和仅 model/仅类型回退。
  - code_review: [PASS] 独立审查首轮发现未确认旧数据优先级、类型词边界和附件三断言截断问题；整改并补充区分性测试后复审 PASS，无剩余 MUST/SHOULD FIX。
  - final_gate: [PASS] 冻结候选执行 `npm run verify:full -- --change audit-edit-enhancement`，预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。

- [x] T029 **修复 iPhone/iPad 产品名误抑制中文检材类型**
  - 文件：`packages/backend/app/services/material_policy_service.py`、`tests/test_material_policy_service.py`、`tests/test_document_builder_service.py`、`tests/test_template_filler_service.py`。
  - 内容：产品系列名 `iPhone`/`iPad` 仍可用于检材分类，但不再视为显示名称中已有的“手机”/“平板”类型词；正式模板与 batch 兼容导出均稳定输出“产品名 + 中文检材类型 + 一部”。
  - 覆盖 Spec：REQ-035。
  - 验证：材料显示策略、模板填充和 batch 文书构建定向 pytest；架构检查、类型检查、`verify:quick` 和 scoped full gate。
  - manual_acceptance: N/A（确定性文案投影由合成 DOCX 内容断言覆盖，不改变版式。）
  - 证据：受影响材料策略、模板填充和 batch 文书构建组合 61 passed；临时恢复旧判断后 4 条关键回归用例全部失败，证明断言具有区分度；`verify:quick`、生产构建和 scoped strict docs 通过。
  - code_review: [PASS] 独立审查首轮发现重复任务号和 iPad 分类断言缺口；整改后复审 PASS，无剩余 MUST/SHOULD FIX。
  - final_gate: [BLOCKED] 两次 scoped full gate 均在无关的工作台/Shadow 全仓测试中失败（1195 passed、3 failed、7 errors）；失败 10 项在隔离可写数据库中定向复跑 10 passed，分别暴露默认数据库只读与全仓共享数据库后的 `TEMPLATE_VERSION_IMMUTABLE` 测试隔离问题。本任务源码与定向验证未失败。
