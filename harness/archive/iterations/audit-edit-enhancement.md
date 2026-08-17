# 迭代记录：审核编辑界面增强

> 日期：2026-07-13
> 变更包：`openspec/changes/audit-edit-enhancement/`
> Spec：`openspec/changes/audit-edit-enhancement/specs/electronic-inspection-record/spec.md`

## 📋 迭代概览

- 新增文件：6（EditableField, ProcessStepsEditor, SoftwareToolsList, ExtractListEditor, RecordEditorForm, useEditableState）
- 修改文件：8（RecordGeneratePage, EvidenceEditor, InspectorEditor, ImageUploader, useRecordExport, types/index.ts, utils/index.ts, report_parser_service.py）
- 涉及层级：L0, L2, L10, L11, L12, L21
- REQ 数量：10（REQ-007 MODIFIED + REQ-017~025 ADDED）

## ⚠️ 遇到的问题

### 问题：Agent 收到测试反馈后直接修改代码，未先更新 Spec

- **现象**：用户手动测试发现 9 个问题。Agent 直接在代码中逐一修复，跳过了 OpenSpec 文档更新步骤。
- **根因**：`AGENTS.md` 中"不能跳过 spec 直接改代码"的规则描述不够醒目；Agent 在"修 Bug"心态下忽略了流程约束。
- **修复方式**：事后补充 proposal.md（新增 CAP-012 章节 + 9 项修复说明）和 spec.md（新增 REQ-020~025），然后走完验证流程。
- **耗时**：额外 2 轮对话（用户指出问题 + 补充文档 + 重新验证）。

## 💡 沉淀的经验

1. **"先文档后代码"不是可选项**——即使是对已实现功能的快速修复，也必须先更新变更包文档再改代码。Agent 在处理用户反馈时容易进入"直接修"模式，这是最需要警惕的陷阱。
2. **区分"快速修复"和"功能修改"**——`/harness:fix` 适用于单行/单文件 Bug，9 个跨层修改显然不符合"快速修复"的定义。

## ✅ 已反哺到 Harness

| 反哺位置 | 变更内容 |
|------|------|
| `AGENTS.md` 文档规则 | 新增：**MUST** 任何代码变更前先更新 OpenSpec proposal.md 和 spec.md |
| `harness/iteration-guide.md` 常见陷阱 | 扩展"跳过 Spec 直接写代码"条目，增加 Agent 违规模式描述和正确流程 |

## 🔼 可反哺到模板

- [ ] 教训描述：Agent 在收到用户测试反馈时容易跳过文档直接改代码
- [ ] 建议写入模板的哪个文件：`harness/iteration-guide.md` 中增加单独章节"收到测试反馈后的正确处理流程"
- [ ] 状态：pending

## 2026-08-17：附件摘要条件分页测试介入

- **现象**：T026 新增的签名与日期版式回归测试连续三轮未通过；最终 29/30 用例通过，仅整段 `w:pPr` 字节比较失败。
- **根因**：测试断言范围过宽，把占位符替换产生的无关默认运行属性变化也当作版式回归；属于 DOCX 测试知识边界未沉淀。
- **处理**：人工确认继续后，将断言收窄为需求指定的缩进、行距、对齐、VML 双横线和段落相对位置，并以 Microsoft Word 实际分页及 PDF 渲染验证最终视觉结果。
- **反哺位置**：`harness/verification-strategy.md`“Word/DOCX 版式断言范围”。
- **TEMPLATE_CANDIDATE**：是；该规则适用于其他基于 OOXML 模板和运行时占位符替换的项目。
