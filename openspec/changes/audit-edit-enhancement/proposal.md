# Proposal: 审核编辑界面增强

> 状态：PROPOSED
> 日期：2026-07-13

## Why

当前预览页面的编辑体验存在以下不足：

### 字段可见性问题

| 章节 | 当前状态 | 问题 |
|------|:--:|------|
| (五) 检材情况 (evidence_list) | ❌ 不可见 | 已有 `EvidenceEditor` 组件但未集成到页面 |
| (八) 检查人员 (inspectors) | ❌ 不可见 | 已有 `InspectorEditor` 组件但未集成到页面 |
| (三) 检查过程 (process_steps) | ❌ 不可见 | 4 个步骤无法审核修改 |
| (二) 软件工具列表 (software_tools) | ❌ 不可见 | 无法查看和修改工具列表 |
| (四) 检查结果 (result) | ⚠️ 只读文本 | 展示为拼接模板字符串，各子字段无法单独编辑 |
| 附件1 提取固定清单 (extract_list) | ❌ 不可见 | 表格数据无法编辑 |
| (一) 检查方法 (method) | ⚠️ disabled | 按规范应允许编辑 |

### 交互模式问题

当前所有字段以 Ant Design `Form.Item` + `Input` 的"始终可编辑"模式渲染。Spec REQ-007 要求"点击字段进入编辑"——即字段默认以纯文本展示，点击后切换为输入框。当前实现偏离了 Spec。

## What

### CAP-010: 所有字段可见

补齐当前预览页面缺失的字段区域，确保 `InspectionReport` 中所有业务字段均在页面上渲染：
- (五) 检材情况 — 集成已有的 `EvidenceEditor`
- (八) 检查人员 — 集成已有的 `InspectorEditor`
- (三) 检查过程 — 新增步骤编辑器
- (二) 软件工具 — 新增工具列表展示
- (四) 检查结果子字段 — 拆分为独立可编辑字段
- 附件1 提取固定清单 — 表格编辑器
- (一) 检查方法 — 改为可编辑

### CAP-011: 点击编辑交互

新增通用 `EditableField` 组件，实现 click-to-edit 交互模式：
- 默认渲染为纯文本（`<Text>`）
- 点击文本后切换为输入框（`<Input>` / `<TextArea>`）
- 失焦或回车后保存变更、切回文本展示
- 每个字段独立控制编辑状态

### 不需要新增的

- 除后续明确增加的“委托单位前缀”外，不新增其他业务字段
- 不新增后端 API——编辑结果仅保存在前端状态，导出时随 `exportDocx()` 提交
- 不改变导出业务流程——仅修复既有导出服务的跨环境 CLI 调用兼容性

## Non-Goals

- 不新增业务字段（如"见证人"）——若需要新字段，应在单独的变更包中扩展数据模型
- 不改变导出 Word 流程
- 不改变上传解析流程
- 不增加服务端持久化编辑状态（仍在会话中）

## Capabilities

| 编号 | 能力 | 类型 | 说明 |
|------|------|------|------|
| CAP-010 | 所有字段可见 | ADDED | 补齐预览页缺失的字段区域 |
| CAP-011 | 点击编辑交互 | ADDED | 文本→点击→编辑→失焦保存 |
| CAP-012 | 手动测试反馈修复 | ADDED | 文号、编辑器、数据映射、附件与导出兼容修复（REQ-020~026） |
| CAP-014 | 审核提示与正式文书规范化 | ADDED | 案件简要核对提示、MD5/来源/版本文案、Word 标题格式及附件摘要条件分页（REQ-032） |
| CAP-ENTRUST-UNIT-PREFIX | 委托单位共享前缀 | ADDED | 可清空的共享前缀与报告识别单位在 Word 中直接拼接 |
| CAP-003 | 全文在线编辑 | MODIFIED | REQ-007 交互模式从"始终可编辑"修正为"点击编辑" |

## ⚠️ 已确认的歧义

| 问题 | 决策 |
|------|------|
| Q1: "见证人" | 确认指"检查人员"（inspectors），使用已有 `InspectorEditor` |
| Q2: "检查情况" | 确认指 Word 中的检材列表格式（`EvidenceEditor` 已支持，builder 已有渲染逻辑） |
| Q3: 交互模式 | **方案 A：全部 click-to-edit** — 纯文本展示→点击→编辑→失焦保存 |

## Impact

按 `harness/architecture.md` 分层矩阵分析：

| 层级 | 目录 | 变更类型 | 说明 |
|------|------|:------:|------|
| Layer 0: SharedTypes | `packages/shared/types/` | 修改 | `InspectionReport` 新增 `case_number` 可选字段；新增 `RarInfo` 导出类型 |
| Layer 1: SharedConstants | `packages/shared/constants/` | — | 无变更 |
| Layer 2: SharedUtils | `packages/shared/utils/` | 修改 | `generateDocumentNumber` 新增 `prefix` 参数 |
| Layer 10: FE_Hooks | `packages/frontend/src/hooks/` | 修改 | `useEditableState` 新增；`useRecordExport` 支持图片文件 |
| Layer 11: FE_Components | `packages/frontend/src/components/` | 新增+修改 | `EditableField` 新增；`EvidenceEditor`/`InspectorEditor`/`SoftwareToolsList`/`ExtractListEditor`/`ImageUploader` 修改；`RecordEditorForm` 新增 |
| Layer 12: FE_Pages | `packages/frontend/src/pages/` | 修改 | `RecordGeneratePage` 重构为轻薄编排层 |
| Layer 21: BE_Services | `packages/backend/app/services/` | 修改 | 数据映射修正；Word 模板填充边界增加附件摘要三行留白与不可拆分条件分页 |
| Layer 20~23 | `packages/backend/` | 修改 | 数据映射修正（委托单位/人 → 采集单位/人） |
| Layer 20: BE_Repository | `file_storage.py` | — | 无新增变更 |
| Layer 21: BE_Services | `report_parser_service.py` | 修改 | 数据字段映射、默认值修正 |
| Layer 22: BE_Controllers | `record_controller.py` | — | 无变更 |
| Layer 23: BE_Routes | `routes/` | — | 无变更 |

---

## 🔧 手动测试反馈修复（2026-07-13）

用户在手动测试中发现 9 个问题，已在本次变更包中修复：

### F1: 文号格式修正（REQ-020）

**问题**：文号生成为 `xx电检〔2026〕SYNTHETIC案件名称号`，格式不符合规范。
**修复**：
- `generateDocumentNumber()` 增加 `prefix` 参数，从委托单位提取区域前缀（如测试值"测试公"）
- 文号来源从 `case_summary` 改为解析出的 `case_number`
- 页面文号旁添加 `Alert` 警告提示："注意修改文号！"

### F2: 检材/检查人员删除按钮（REQ-021）

**问题**：`EvidenceEditor` 和 `InspectorEditor` 仅有 1 条记录时不显示删除按钮。
**修复**：移除 `items.length > 1` 条件判断，删除按钮始终可见。

### F3-F5: 数据字段映射修正（REQ-022）

**问题**：
- (F3) 委托单位错误映射为 `submit_unit`（送检单位），应为 `collect_unit`（采集单位）
- (F4) 委托人错误映射为 `submit_person`（送检人），应为 `collector`（采集人）
- (F5) 检查地点无默认值
**修复**：
- `report_parser_service.py` 中 `entrust_unit` → `case.get("collect_unit")`
- `entrust_person` → `case.get("collector")`
- `inspection_place` → `"合成检验鉴定中心"`（默认值）

### F6: 软件工具名称可编辑（REQ-023）

**问题**：`SoftwareToolsList` 仅版本号可编辑，工具名称不可修改；Hash 工具未彻底移除。
**修复**：名称和版本号均改为 `EditableField` 渲染，支持添加/删除工具行。

### F7: 提取固定清单默认表头（REQ-024）

**问题**：附件1 提取固定清单初始为空，无标准表头。
**修复**：`ExtractListEditor` 默认 6 列标准表头：序号/文件名称/文件路径/文件大小/MD5哈希值/备注。

### F8: 附件2 图片上传缺失（REQ-025）

**问题**：预览页无图片上传入口。
**修复**：集成 `ImageUploader` 组件到附件2区域，`useRecordExport` 支持传递图片文件到后端。

### F9: 导出 500 错误（REQ-026）

**问题**：点击导出返回 500，错误消息 `[WinError 2] 系统找不到指定的文件。`
**根因**：
1. `subprocess.run(["officecli", ...])` 在 uvicorn 子进程环境中找不到 `officecli.cmd`——npm 全局目录不在 uvicorn 的 PATH 中
2. `shell=True` 同样失败——`cmd.exe` 也未在 uvicorn 的 PATH 中（COMSPEC 不可用）
**修复**（`record_generator_service.py`）：
- `shutil.which("officecli")` 查找 officecli 绝对路径（含 `.CMD` 扩展名）
- `C:\Windows\System32\cmd.exe` 绝对路径替代 `shell=True` / `cmd.exe` 短名
- 新增 `_run_officecli(*args)` 封装，Windows 路径下用 `[cmd.exe绝对路径, "/d", "/c", cmd_str]` 调用
- `capture_output=True, encoding="utf-8"` 处理中文输出

### F10: 后端测试命令路径修正（REQ-027）

**问题**：`@biji/backend` 的 test script 从 `packages/backend/app` 执行 `../tests/`，该目录不存在，导致项目门控无法收集后端测试。

**修复**：将测试目录解析为项目根目录的 `tests/`，使 `npm run test` 和 `npm run pre-commit` 能执行后端 pytest 用例。

### F11: 文档漂移检查忽略测试缓存（REQ-028）

**问题**：pytest 在后端应用目录生成 `.pytest_cache/`，文档漂移检查把该运行时缓存误判为需要记录的项目目录。

**修复**：将 Python 测试缓存排除在目录漂移扫描之外，保留对实际源码目录的检查。
