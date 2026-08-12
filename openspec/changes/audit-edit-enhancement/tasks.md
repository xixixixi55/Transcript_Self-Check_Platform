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
  - manual_acceptance: N/A（仅新增独立文本字段与确定性字符串拼接；模板和 batch 两条 DOCX 路径均由合成数据自动化读取实际输出验证，不改变版式。）

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
| **合计** | **Layer 0、2、10~12、20~21** | **22** | |

> 注：后端仅包含 REQ-022、REQ-026 的既有流程修复，不新增 API 端点。

## 🟢 Phase 11: 软件名称净化与检材可提取状态

- [x] T023 **规范软件工具名称并自动判断检材是否可提取**
  - 文件：`packages/backend/app/repository/report_format_adapter.py`、`report_parser_service.py`、`material_policy_service.py`、`document_builder_service.py`、`template_filler_service.py`；`packages/shared/types/`、`packages/shared/utils/softwareProjectionUtils.ts`；`packages/frontend/src/components/EvidenceEditor.tsx` 及相关测试。
  - 内容：主软件名称保留报告识别到的软件身份，通用移除取证塔、取证设备、取证工作站等硬件括号描述并保留版本；按 IMEI1、IMEI2、序列号任一非空自动生成 `extractable`，审核页展示且允许修正；无法提取时隐藏标识，并在检材情况和检查过程追加“（无法提取）”。
  - 覆盖 Spec：REQ-034。
  - 验证：软件适配、解析、Canonical/Legacy 投影、前端组件/共享投影、模板与 batch Word 两条路径定向测试；架构检查、类型检查、`verify:quick` 和 scoped strict docs。
  - manual_acceptance: N/A（确定性字段投影和文案由合成数据自动化覆盖；不改变 Word 版式。）
