# template-2026: 2026报告模板转换

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: 已同步到 openspec/specs/electronic-inspection-record/spec.md REQ-007 和 REQ-009，包括在解析、审核编辑和 Word 导出间统一多委托人分隔符

## 目标

将业务方认可的参考文档「2026报告模板（one压缩包）最终提交.docx」转换为项目可用的 Word 模板，支持 `{{placeholder}}` 动态填充。同时升级 `entrust_person` 字段以支持多委托人场景。

## 验收标准

- [x] `entrust_person` → `entrust_persons: string[]` 类型升级，前后端 + 测试全部更新
- [x] `word_templates/template.docx` 生成，包含正确的 `{{占位符}}` 标记
- [x] 参考文档所有样式（字体、字号、行距、页边距、表格格式）完整保留
- [x] 列表字段（检材、检查人员、检查过程、提取清单）使用 `{{#list}}...{{/list}}` 标记
- [x] 软件工具保持原文档合并格式（单段落 `{{software_tools_text}}`）
- [x] `packages/backend/app/services/template/template_filler_service.py` 实现模板填充：简单占位符替换 + 列表块展开 + 表格填充
- [x] `packages/backend/app/services/document/record_generator_service.py` 优先使用模板填充，模板不存在时回退 batch 方案
- [x] lint:arch ✅ / typecheck ✅ / 前端测试 28 passed ✅ / 后端测试 35 passed ✅

## 修复记录 (2026-07-15)

| # | Bug | 级别 | 修复 |
|---|-----|:--:|------|
| 1 | 委托单位/委托人映射到 submit_unit/submit_person | L1 | `report_parser_service.py:205-206` |
| 2 | 模板字体颜色全部改为黑色 | L1 | `create_template.py`: `_normalize_colors()` |
| 3 | 页眉硬编码文号 → 动态 `{{document_number}}` | L1 | `create_template.py`: `_replace_header()` + `packages/backend/app/services/template/template_filler_service.py`: `_replace_header_footer()` |
| 4 | 附件3新增 `burning_date` 刻录时间字段 | L2 | shared types / report_parser / template / filler / 前端输入框 |
| 5 | 附件2无照片时删除模板示例图片 | L1 | `packages/backend/app/services/template/template_filler_service.py`: `_handle_photos()` |
| 6 | 附件1空表格清除占位符 + 左下→右上对角线 | L1 | `packages/backend/app/services/template/template_filler_service.py`: `_clear_row_and_draw_diagonal()` |
| 7 | 附件1空表格斜线的 `tcBorders` 节点顺序不符合 OOXML | L1 | 保留斜线样式，将 `tcBorders` 插入 `vAlign` 之前 |

## 任务列表

| # | 任务 | 状态 |
|---|------|:---:|
| 1 | Phase 1: `entrust_person: string` → `entrust_persons: string[]` 类型升级 | ✅ |
| 2 | Phase 2: 基于参考文档创建 `template.docx` | ✅ |
| 3 | Phase 3: 创建 `packages/backend/app/services/template/template_filler_service.py` + 更新生成器集成 | ✅ |
| 4 | Phase 4: 验证（lint:arch + typecheck + 测试） | ✅ |
| 5 | Phase 5: 委托人常见分隔符规范化，并统一审核编辑与 Word 展示 | ✅ |

## Phase 5：委托人分隔符规范化（2026-08-13）

- [x] T005 **解析与 Word 导出统一委托人分隔符**
  - 文件：`packages/backend/app/services/inspection/entrust_person_service.py`、`report_parser_service.py`、`packages/backend/app/services/document/document_builder_service.py`、`packages/backend/app/services/template/template_filler_service.py`
  - 内容：将顿号、中英文逗号/分号、斜杠、竖线和换行识别为多委托人分隔符，过滤空项；正式模板与兼容 Word 路径统一以顿号连接。
  - 覆盖 Spec：REQ-007、REQ-009
  - 验证：`python -m pytest tests/test_report_parser_service.py tests/test_document_builder_service.py tests/test_template_filler_service.py -q --tb=short`

- [x] T006 **审核编辑界面显示并保存规范化后的委托人**
  - 文件：`packages/frontend/src/components/ReviewIntroductionSection.tsx`、`RecordEditorForm.test.tsx`
  - 内容：历史数组项或人工输入含常见非顿号分隔符时，审核字段直接显示为顿号，并以拆分后的 `string[]` 提交。
  - 依赖：T005
  - 覆盖 Spec：REQ-007、REQ-009
  - 验证：`pnpm --filter @biji/frontend exec vitest run src/components/RecordEditorForm.test.tsx`

- [x] T007 **完成 Level 2 收尾验证与规格同步**
  - 依赖：T005、T006
  - 内容：核对 delta 与实现，运行轻量门控和受影响模块测试，将最终行为同步到 living spec。
  - 验证：`npm run verify:quick`、`npm run verify:docs:strict -- --change template-2026`

- [x] T008 **附件1检查人员落款跟随检查地点**
  - 文件：`packages/backend/app/services/template/template_filler_service.py`、`packages/backend/app/services/attachment/attachment_docx_renderer_service.py`、现有模板/附件渲染测试。
  - 内容：把正式模板附件1最后签名行中跨 Run 写死的鉴定中心名称替换为当前报告 `introduction.inspection_place`；保持签名、盖章、分页和 Manifest 多页结构不变，不修改模板二进制及其他 Word 内容。
  - 覆盖 Spec：REQ-009。
  - 验证：先以现有 SYNTHETIC/TEST 报告证明兼容填充与 Manifest 多页路径失败，实施后运行定向后端测试、生成合成 DOCX 并用 officecli 校验文本与文件结构。
  - 证据：定向回归 `3 passed`；受影响后端测试 `75 passed`。合成 DOCX 可由 officecli 读取；officecli 的既有 `tcBorders` 顺序告警在禁用本次替换的基线输出中同样存在，本次仅替换文本节点且未新增结构差异。

- [x] T009 **完成本次 Level 2 规格同步与门控**
  - 依赖：T008。
  - 内容：核对 delta 与实现、同步 living spec，运行 `verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
  - 证据：`npm run verify:quick` 通过；`npx openspec validate template-2026 --type change --strict --no-interactive` 通过；scoped strict docs 与最终 diff 检查在任务勾选后复跑。

- [x] T010 **修复附件1空清单斜线的 OOXML 属性顺序**
  - 文件：`packages/backend/app/services/template/template_filler_service.py`、`tests/test_template_filler_service.py`。
  - 内容：保留空白数据区域的左下至右上斜线，只将 `w:tcBorders` 插入到 OOXML 规定的 `w:vAlign` 之前，消除 officecli 严格结构告警。
  - 级别：Level 1 既有行为缺陷修复，不新增或修改 Requirement/Scenario。
  - 验证：定向回归同时断言 `w:tr2bl` 仍存在且属性顺序合法；生成 SYNTHETIC 空清单 DOCX 后运行 `officecli validate`，并执行受影响后端测试与项目快速门控。
  - 证据：失败用例先确认旧顺序为 `tcW → vAlign → tcBorders`；修复后定向用例通过且 `officecli validate` 零错误；模板与 Word 构建测试 `42 passed`，`npm run pre-commit` 通过。

## 关键文件

| 文件 | 变更类型 |
|------|---------|
| `packages/shared/types/index.ts` | 修改：entrust_persons 类型 |
| `packages/backend/app/services/report/report_parser_service.py` | 修改：split 委托人 + _split_persons |
| `packages/backend/app/services/document/document_builder_service.py` | 修改：join 委托人 |
| `packages/backend/app/services/template/template_filler_service.py` | **新增**：模板填充服务 |
| `packages/backend/app/services/document/record_generator_service.py` | 修改：模板优先 + 回退 |
| `packages/frontend/src/components/RecordEditorForm.tsx` | 修改：entrust_persons 输入 |
| `word_templates/template.docx` | **新增**：Word 模板 |
| `scripts/create_template.py` | **新增**：模板生成脚本（一次性） |
| `scripts/lint-arch.ts` | 修改：文件大小例外 |
| `tests/test_*.py` / `*.test.tsx` | 修改：适配 entrust_persons |

## 设计说明

- **委托人升级**：用户输入仍为顿号/逗号分隔的文本框（改动最小），存储为 `string[]`，展示时用 `、` 连接
- **模板填充优先级**：模板存在 → 用 python-docx 填充；模板不存在 → 回退 officecli batch 方案
- **软件工具**：保持参考文档的合并格式，后端将 `SoftwareItem[]` 拼接为 `software_tools_text` 字符串
- **列表展开**：使用 lxml deepcopy 段落元素实现，保留原始格式（字体/字号/缩进等）
