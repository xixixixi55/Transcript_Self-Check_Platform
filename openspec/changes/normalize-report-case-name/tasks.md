workflow_level: 2

# 任务

- [x] T001 更新报告案件名称解析行为。
  - 文件：`packages/backend/app/services/report/report_parser_service.py`
  - 内容：清理报告识别案件名称末尾 `案（...）` / `案(...)` 标记，并移除案件简要情况自动补“案”的逻辑；递增解析缓存版本。
  - 验证：`pytest tests/test_report_parser_service.py -q --tb=short`
- [x] T002 补充案件名称归一化回归测试。
  - 文件：`tests/test_report_parser_service.py`
  - 内容：覆盖括号后缀清理、不以“案”结尾时不自动补“案”、已以“案”结尾时保持原样，以及集成解析元数据同步。
  - 验证：`pytest tests/test_report_parser_service.py -q --tb=short`
- [x] T003 同步规格并执行 Level 2 门控。
  - 文件：`openspec/changes/normalize-report-case-name/specs/electronic-inspection-record/spec.md`、`openspec/specs/electronic-inspection-record/spec.md`
  - 内容：记录并同步 REQ-002 的案件名称清洗与不补“案”行为。
  - 验证：`npm run verify:quick`、`npm run verify:docs:strict -- --change normalize-report-case-name`、受影响后端测试
