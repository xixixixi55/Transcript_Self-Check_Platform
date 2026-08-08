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

### AD-002: 全部 click-to-edit（与 Spec REQ-007 对齐）

**决策**：预览页中的文本字段统一使用 click-to-edit 交互模式；检材、人员、软件工具与提取清单中的可编辑文本同样复用 `EditableField`。新增通用组件封装状态机。

**理由**：
- Spec REQ-007 明确要求"点击字段进入编辑"，当前 always-Input 模式已偏离 Spec
- 检查笔录是正式法律文书——纯文本展示更接近"审阅纸质笔录"的体验，满屏输入框边框是视觉噪音
- 统一交互降低认知负担——民警只需学一种操作模式
- `EditableField` 封装 click-to-edit 状态机（展示 → 编辑 → 保存/取消）后，15+ 字段只需一行组件声明
- 组件签名：`<EditableField type="text|textarea|select" value={v} onChange={fn} options={[]} />`

**备选方案**：使用 Ant Design `Typography.Paragraph` 的 `editable` 属性
- 拒绝理由：不支持 Select 类型，失焦保存行为不可定制

**备选方案**：混合模式（部分 always-Input，部分 click-to-edit）
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
- 独立字段更符合审核场景（民警只需修改某个子字段）
- 导出时 `document_builder_service.py` 仍从 `report.inspection.result` 取各字段值生成最终文本

---

## 组件树

```
RecordGeneratePage (L12)
├── EditableField × N       (L11, 新增) — click-to-edit 通用组件（内置独立编辑状态）
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

---

## 文件变更清单

| 文件 | 层级 | 操作 | 说明 |
|------|:----:|:----:|------|
| `packages/frontend/src/hooks/useEditableState.ts` | L10 | **新增** | 页面级编辑协调 Hook（预留）；EditableField 使用内置 `useState` 管理各自编辑态 |
| `packages/frontend/src/components/EditableField.tsx` | L11 | **新增** | click-to-edit 通用组件 |
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
| `packages/backend/app/services/report_parser_service.py` | L21 | 修改 | 数据字段映射与默认检查地点修正 |
| `packages/backend/app/services/record_generator_service.py` | L21 | 修改 | officecli 跨环境调用兼容 |
| `packages/backend/package.json` | 工程配置 | 修改 | 后端 pytest 测试目录指向项目根目录 `tests/` |
| `scripts/check-docs.ts` | 工程验证 | 修改 | 目录漂移扫描忽略 pytest 运行时缓存 |
