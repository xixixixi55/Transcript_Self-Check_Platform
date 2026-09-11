# 任务清单

workflow_level: 3
status: superseded
superseded_by: report-parsing-cache-management
spec_sync_status: reconciled
spec_sync_evidence: 当前 REQ-011 已取消持久化解析结果缓存和 compress 模式缓存，本包旧 delta 不得重新写入 living spec。

- [x] 1. 更新 `parse_report` 的缓存命名和命中逻辑，按 `compress` 模式隔离缓存；验证源文件变更仍会使缓存失效。
  - 文件：`packages/backend/app/services/report/report_parser_service.py`
  - 验证：同一目录先后以 `compress=true/false` 解析时，两个结果的 `rar_info` 分别符合模式。
- [x] 2. 增加缓存模式切换回归测试，并保留已有压缩开关测试。
  - 文件：`tests/test_report_parser_service.py`
  - 验证：`python -m pytest tests/test_report_parser_service.py -q`
- [x] 3. 运行项目门禁并检查文档一致性。
  - 验证：`npm run pre-commit`、`npm run check-docs`
