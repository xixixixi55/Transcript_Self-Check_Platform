# template-2026: 2026报告模板转换

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: sync applied to openspec/specs/electronic-inspection-record/spec.md REQ-009

## 目标

将业务方认可的参考文档「2026报告模板（one压缩包）最终提交.docx」转换为项目可用的 Word 模板，支持 `{{placeholder}}` 动态填充。同时升级 `entrust_person` 字段以支持多委托人场景。

## 验收标准

- [x] `entrust_person` → `entrust_persons: string[]` 类型升级，前后端 + 测试全部更新
- [x] `word_templates/template.docx` 生成，包含正确的 `{{占位符}}` 标记
- [x] 参考文档所有样式（字体、字号、行距、页边距、表格格式）完整保留
- [x] 列表字段（检材、检查人员、检查过程、提取清单）使用 `{{#list}}...{{/list}}` 标记
- [x] 软件工具保持原文档合并格式（单段落 `{{software_tools_text}}`）
- [x] `template_filler_service.py` 实现模板填充：简单占位符替换 + 列表块展开 + 表格填充
- [x] `record_generator_service.py` 优先使用模板填充，模板不存在时回退 batch 方案
- [x] lint:arch ✅ / typecheck ✅ / 前端测试 28 passed ✅ / 后端测试 35 passed ✅

## 修复记录 (2026-07-15)

| # | Bug | 级别 | 修复 |
|---|-----|:--:|------|
| 1 | 委托单位/委托人映射到 submit_unit/submit_person | L1 | `report_parser_service.py:205-206` |
| 2 | 模板字体颜色全部改为黑色 | L1 | `create_template.py`: `_normalize_colors()` |
| 3 | 页眉硬编码文号 → 动态 `{{document_number}}` | L1 | `create_template.py`: `_replace_header()` + `template_filler_service.py`: `_replace_header_footer()` |
| 4 | 附件3新增 `burning_date` 刻录时间字段 | L2 | shared types / report_parser / template / filler / 前端输入框 |
| 5 | 附件2无照片时删除模板示例图片 | L1 | `template_filler_service.py`: `_handle_photos()` |
| 6 | 附件1空表格清除占位符 + 左下→右上对角线 | L1 | `template_filler_service.py`: `_clear_row_and_draw_diagonal()` |

## 任务列表

| # | 任务 | 状态 |
|---|------|:---:|
| 1 | Phase 1: `entrust_person: string` → `entrust_persons: string[]` 类型升级 | ✅ |
| 2 | Phase 2: 基于参考文档创建 `template.docx` | ✅ |
| 3 | Phase 3: 创建 `template_filler_service.py` + 更新生成器集成 | ✅ |
| 4 | Phase 4: 验证（lint:arch + typecheck + 测试） | ✅ |

## 关键文件

| 文件 | 变更类型 |
|------|---------|
| `packages/shared/types/index.ts` | 修改：entrust_persons 类型 |
| `packages/backend/app/services/report_parser_service.py` | 修改：split 委托人 + _split_persons |
| `packages/backend/app/services/document_builder_service.py` | 修改：join 委托人 |
| `packages/backend/app/services/template_filler_service.py` | **新增**：模板填充服务 |
| `packages/backend/app/services/record_generator_service.py` | 修改：模板优先 + 回退 |
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
