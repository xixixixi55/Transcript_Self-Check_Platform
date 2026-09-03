# Design: 审核编辑界面增强

> 变更包：`openspec/changes/audit-edit-enhancement`

---

## 架构决策

### AD-001: 前端审核编辑增强，附带既有后端缺陷修复

**决策**：审核编辑能力位于前端 Layer 10~12；本次同时在 Layer 21 修复解析字段映射和 officecli 跨环境调用。不会新增 API 端点或服务端持久化状态。

**理由**：
- 编辑结果仅保存在前端 `useState` 中
- 导出时通过已有的 `POST /records/export` 一次性提交完整 `InspectionReport`
- 导出端点已接收完整 JSON，无需新增"保存编辑"端点
- 手动测试发现的字段映射和 CLI 启动问题属于既有流程修复，详见 proposal.md 的 F3-F5、F9

### AD-002：全部点击编辑（与规格 REQ-007 对齐）

**决策**：预览页中的文本字段统一使用点击编辑交互模式；检材、人员、软件工具与提取清单中的可编辑文本同样复用 `EditableField`。新增通用组件封装状态机。

**理由**：
- Spec REQ-007 明确要求"点击字段进入编辑"，当前 always-Input 模式已偏离 Spec
- 检查笔录是正式法律文书——纯文本展示更接近"审阅纸质笔录"的体验，满屏输入框边框是视觉噪音
- 统一交互降低认知负担——工作人员只需学一种操作模式
- `EditableField` 封装点击编辑状态机（展示 → 编辑 → 保存/取消）后，15+ 字段只需一行组件声明
- 组件签名：`<EditableField type="text|textarea|select" value={v} onChange={fn} options={[]} />`

**备选方案**：使用 Ant Design `Typography.Paragraph` 的 `editable` 属性
- 拒绝理由：不支持 Select 类型，失焦保存行为不可定制

**备选方案**：混合模式（部分始终显示输入框，部分点击编辑）
- 拒绝理由：交互不一致，增加认知负担

**实现注记**：EditableField 使用内置 `useState` 管理编辑态，每个字段独立控制。`useEditableState` Hook 作为页面级协调预留（例如全局"保存全部"按钮），当前页面未使用——每个 EditableField 自管理编辑态更简洁，且允许多字段同时编辑。

### AD-003: 复用已有组件

**决策**：`EvidenceEditor` 和 `InspectorEditor` 已在第一迭代构建（T023/T024），直接集成到 `RecordGeneratePage`。

**理由**：
- 两个组件接口完整（`items` + `onChange`），与 `updateReport` 模式兼容
- 避免重复开发
- 组件已有类型安全保证

### AD-004: 检查结果字段拆分

**决策**：将 `resultText`（拼接模板字符串）替换为 7 个独立的 `EditableField`。

**理由**：
- 拼接字符串中各字段不可单独编辑
- 独立字段更符合审核场景（工作人员只需修改某个子字段）
- 导出时 `packages/backend/app/services/document/document_builder_service.py` 仍从 `report.inspection.result` 取各字段值生成最终文本

---

## 组件树

```
RecordGeneratePage (L12)
├── EditableField × N       (L11, 新增) — 点击编辑通用组件（内置独立编辑状态）
├── EvidenceEditor           (L11, 已有) — (五) 检材情况
├── InspectorEditor          (L11, 已有) — (八) 检查人员
├── FileInfoCard             (L11, 已有) — 文件信息
├── RecordEditorForm         (L11, 编排组件) — 审核编辑区与附件区
└── useEditableState         (L10, 新增) — 页面级编辑协调（预留，EditableField 各有独立状态）
```

---

## EditableField 状态机

```
         ┌──────────────────┐
         │   display mode   │  ← 默认：纯文本
         │  <Text>value</>  │
         └──────┬───────────┘
                │ onClick
                ▼
         ┌──────────────────┐
         │    edit mode     │  ← Input / TextArea 自动聚焦
         │  <Input value /> │
         └──────┬───────────┘
           ╱        ╲
     onBlur/Enter   onEscape
         ╱            ╲
        ▼              ▼
  ┌──────────┐   ┌──────────┐
  │ onChange │   │  revert  │
  │ (save)   │   │ (cancel) │
  └────┬─────┘   └────┬─────┘
       │              │
       ▼              ▼
   display mode    display mode
```

---

## 页面布局变更

Step 1（审核编辑）的 Form 区域重新组织：

```
一、绪论
  (一) 委托单位      [EditableField]
  (二) 委托人        [EditableField]
  (三) 委托时间      [EditableField]
  (四) 案件简要情况  [EditableField type=textarea]
  (五) 检材情况      [EvidenceEditor]
  (六) 检查要求      [EditableField type=textarea]
  (七) 检查起止时间  [EditableField]
  (八) 检查人员      [InspectorEditor]
  (九) 检查地点      [EditableField]

二、检查
  (一) 检查方法      [EditableField type=textarea]  ← 不再 disabled
  (二) 检查设备
       硬件          [EditableField type=select]
       软件工具       [SoftwareToolsList]  ← 新增
  (三) 检查过程      [ProcessStepsEditor] ← 新增
  (四) 检查结果      [EditableField × 7]   ← 替换拼接文本

附件
  附件1 提取固定清单 [ExtractListEditor]   ← 新增
  附件2 检材照片     [ImageUploader]       ← 已有组件集成
  附件3 日期/校验摘要 [只读；光盘编号统一由页面顶部常驻入口填写]
```

页面顶部 `ArchiveCompletionPanel` 是首个光盘编号的唯一编辑入口：审核阶段和压缩过程中直接更新案件草稿；压缩完成且盘号待映射时保持同一输入位置并提交全序列映射。归档已完成后改为展示导出动作，不再允许改写已验证 Manifest 的盘号。

---

## AD-005：检查人员卡片布局与添加入口

检查人员区域使用 CSS Grid 渲染紧凑的正方形卡片，宽屏固定最多三列，在 760px 和 480px 断点分别降为两列和一列。添加入口不再占用审核页面顶部的常驻多选框，而是作为列表末尾始终存在的虚线加号卡片；点击后打开人员选择面板，直接展示尚未选择的启用人员卡片，不再嵌套下拉框。点击人员卡片立即追加到当前快照，删除和拖拽排序继续由卡片直接提供。

## AD-006：草稿保存请求收敛

自动保存 Hook 以可编辑草稿内容、共享默认值补丁和对应 revision 形成请求签名。成功保存后，若后续只发生了令牌变化但内容签名未变化，不重复发送相同 PATCH，而是清理 pending 状态并结束手动保存等待；真实内容变化仍按 revision 顺序排队保存。保存成功后页面同步服务端草稿，避免保存按钮长期保持 loading。

## AD-007：在用户可见投影和 DOCX 渲染边界规范化文案

MD5 的密码学事实值保持不变，不改写既有 Manifest 或持久化摘要；在解析结果、审核编辑、归档结果投影和 DOCX 渲染边界统一转为大写。固定清单来源由附件计划集中生成“检材内提取”。检查步骤 4 使用主软件名称与独立版本字段组合，不把版本提前拼入名称。DOCX 标题样式在模板完成动态附件渲染后统一施加，以同时覆盖无 Manifest 兼容导出和正式 Manifest 导出。

备选方案是直接修改二进制模板样式；不采用，因为运行时规范化能覆盖历史模板内容并由 XML 测试稳定验证。案件简要提示仅影响审核 UI，不自动裁剪用户输入，以免在未确认时改写正式文书内容。

## AD-008：废止委托单位前缀并在兼容边界丢弃旧值

`introduction.entrust_unit` 是委托单位的唯一业务字段。共享类型、规范模型、共享默认值白名单和新案件初始化均不再提供 `entrust_unit_prefix`；旧案件或持久化默认值中残留的同名键只作为可安全读取的未知旧数据被忽略，并在规范投影或后续持久化时丢弃。

模板填充和 officecli batch 回退两条 DOCX 路径均只使用 `trim(entrust_unit)`，不得读取或拼接旧前缀。这样无需批量改写历史案件，也能保证历史数据重新预览或导出时前缀不再进入 Word。

## AD-009：使用 Word 段落约束实现附件摘要条件分页

附件摘要不再携带无条件分页符。模板填充边界将模板中的三个固定空段落折算为摘要首段的等效段前距，并将三条摘要、摘要后的留白、检查人签名区、双横线和日期共同设置为连续的不可拆分页块：同页剩余空间能够同时容纳三行前置留白和完整摘要区域时，该区域紧随检查结果留白后排版；空间不足时，Word 将完整摘要区域移动到下一页页首，并按页首段落语义抑制段前距，使独立页不携带三个空白行或等效顶部留白。独立分页时不重建或压缩摘要、签名、横线和日期元素，确保其缩进、行距和对齐与变更前一致。附件摘要后的附件一继续使用既有分页规则，不与摘要区域绑定为同一不可拆块。

该方案只表达标准 DOCX 分页语义，不引入页面高度估算或依赖特定文本长度的硬编码。OOXML 自动化测试负责验证三个空段落已转换为精确等效段前距、摘要段落约束、无固定分页符以及签名区和日期结构未被改写；Microsoft Word 导出 PDF 的人工验收分别覆盖“同页可容纳”和“同页不可容纳”两个分页场景，其中独立页必须确认摘要从正常页首位置开始且没有三个空白行。

---

## 文件变更清单

| 文件 | 层级 | 操作 | 说明 |
|------|:----:|:----:|------|
| `packages/frontend/src/hooks/useEditableState.ts` | L10 | **新增** | 页面级编辑协调 Hook（预留）；EditableField 使用内置 `useState` 管理各自编辑态 |
| `packages/frontend/src/components/EditableField.tsx` | L11 | **新增** | 点击编辑通用组件 |
| `packages/frontend/src/components/RecordEditorForm.tsx` | L11 | 新增 | 审核编辑区编排与组件集成 |
| `packages/frontend/src/components/InspectorEditor.tsx` | L11 | 修改 | 紧凑正方形卡片、加号添加入口和直接人员选择面板 |
| `packages/frontend/src/reviewWorkspace.css` | L11 | 修改 | 紧凑卡片、三列/两列/一列响应式布局和人员选择面板样式 |
| `packages/frontend/src/hooks/useCaseDraftAutosave.ts` | L10 | 修改 | 成功草稿签名去重，防止重复 PATCH 保存循环 |
| `packages/frontend/src/hooks/useCaseRecordSession.ts` | L10 | 修改 | 保存成功且无后续修改时同步服务端规范化草稿 |
| `packages/frontend/src/hooks/useCaseDraftAutosave.test.tsx` | L10 | 修改 | 保存成功、并发修改和相同内容令牌变化回归测试 |
| `packages/frontend/src/components/InspectorEditor.test.tsx` | L11 | 新增 | 加号面板、直接添加、删除和拖拽排序测试 |
| `packages/frontend/src/pages/RecordGeneratePage.tsx` | L12 | 修改 | 上传、导出与页面状态编排 |
| `packages/shared/types/` | L0 | — | 无变更 |
| `packages/shared/constants/` | L1 | — | 无变更 |
| `packages/backend/app/services/report/report_parser_service.py` | L21 | 修改 | 数据字段映射与默认检查地点修正 |
| `packages/backend/app/services/document/record_generator_service.py` | L21 | 修改 | officecli 跨环境调用兼容 |
| `packages/backend/app/services/template/template_filler_service.py` | L21 | 修改 | 附件摘要三行留白、不可拆分段落约束及条件分页 |
| `tests/test_template_filler_service.py` | 测试 | 修改 | 条件分页 OOXML 回归及可容纳/不可容纳场景 |
| `packages/backend/package.json` | 工程配置 | 修改 | 后端 pytest 测试目录指向项目根目录 `tests/` |
| `scripts/check-docs.ts` | 工程验证 | 修改 | 目录漂移扫描忽略 pytest 运行时缓存 |
