# Tasks：预览字段映射与 Word 导出修复

workflow_level: 3

## Phase 1 — 文档与解析（Layer 20/21）

- [x] T001 [P0] 在 `html_parser.py` 增加设备名称、IMEI1/2、序列号的键值/文本兼容解析，并为检材编号提供目录回退；验证：新增/更新 `tests/test_html_parser.py`。
- [x] T002 [P0] 在 `report_parser_service.py` 将规范化设备字段写入 `EvidenceItem`，并默认加入 Python hash 工具；验证：`tests/test_report_parser_service.py`。

## Phase 2 — 预览与附件（Layer 11）

- [x] T003 [P1] 在 `EvidenceEditor.tsx` 将设备型号语义改为设备名称，保留旧数据回退；验证：`StructuredEditors.test.tsx`。
- [x] T004 [P1] 在 `ExtractListEditor.tsx` 使用标准五列表头和默认空行；验证：组件渲染测试。

## Phase 3 — Word 构建（Layer 21/22）

- [x] T005 [P0] 在 `document_builder_service.py` 写入附件 1 表头、数据单元格和完整设备字段；验证：新增 `tests/test_document_builder_service.py`。
- [x] T006 [P0] 在 `record_generator_service.py` 对生成文件做非空校验，并确保 batch 错误向上抛出；验证：导出服务测试和 docx XML 检查。

## Phase 4 — 综合验证

- [x] T007 [P1] 补齐前端/后端回归测试，覆盖 8 条手测问题；验证：前端 Vitest、后端 pytest。
- [x] T008 [P0] 运行 `npm run pre-commit`，确认 architecture、typecheck、build、test、check-docs 全部通过。
