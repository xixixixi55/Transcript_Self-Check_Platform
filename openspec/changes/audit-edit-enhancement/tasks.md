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

---

## 任务摘要

| Phase | 层级 | 任务数 | 核心产出 |
|-------|:------:|:-----:|------|
| 🔴 P1 | Hooks (10) | 2 | useEditableState + 测试 |
| 🟣 P2 | Components (11) | 5 | EditableField + ProcessStepsEditor + SoftwareToolsList + ExtractListEditor + 测试 |
| 🔵 P3 | Pages (12) | 3 | 补齐字段 + 替换交互 + 集成验证 |
| 🟠 P4 | Components / 验证 | 5 | 审查整改、组件测试、工程门控 |
| 🟢 P5 | Components / 样式 | 2 | 检查人员卡片布局、加号添加入口与测试 |
| **合计** | **Layer 2、10~12、21** | **19** | |

> 注：后端仅包含 REQ-022、REQ-026 的既有流程修复，不新增 API 端点。
