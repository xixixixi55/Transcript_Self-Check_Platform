# Design：预览字段映射与 Word 导出修复

## AD-001：解析层先规范化设备字段

`parse_device_base` 负责读取 Base 目录，具体键值/文本兼容逻辑放在同层 `device_field_parser.py`，兼容 `device_name/name/model`、`IMEI/IMEI1/IMEI2`、`serial_number/序列号/Serial` 等命名；`parse_device_lists` 负责提供检材编号，并在列表字段缺失时回退到 `data/<检材编号>/` 目录名。`_build_report` 将设备名称写入 `EvidenceItem.device_type`，同时保留 `model` 作为旧数据兼容字段。

## AD-002：预览只消费规范化后的 InspectionReport

不在 React 页面中重新猜测原始 JSON。`EvidenceEditor` 将第一字段展示为“设备名称”，优先显示 `device_type`，旧缓存才回退到 `model`；IMEI1、IMEI2、序列号和检材编号直接使用解析结果。

## AD-003：默认值集中在服务层

`report_parser_service` 始终将 Python hash 标准库作为默认软件工具；压缩流程仍按原有条件添加 WinRAR。这样目录上传、ZIP 上传和 RAR 上传产生一致的 hash 工具记录。

## AD-004：附件表格使用固定五列表头并写入单元格

前端空表默认展示五列：序号、电子数据、来源、提取方式、文件MD5哈希值。后端导出时对空列配置使用同一组默认列，并通过 officecli batch 命令创建表格、表头和每个数据单元格；没有数据时仍输出一行空白记录。

## AD-005：导出结果必须可观测且非空

`generate_docx` 在 `create` 与 `batch` 成功后显式调用 `officecli save` 将 resident 内容落盘，再检查文件存在且大小大于零；控制器继续以 `FileResponse` 返回。测试直接解压 docx 并检查 `word/document.xml` 至少包含标题、设备/检材内容和附件表头，避免只验证 HTTP 200。

## 已拒绝的替代方案

- 在前端根据字符串正则再次解析原始报告：会造成上传目录模式和压缩包模式行为分叉。
- 仅增大 docx 文件或返回固定占位文本：无法证明预览内容已进入导出文档。
- 删除附件表格：与 Word 模板和用户手测要求不符。

## 文件计划

- `packages/backend/app/repository/html_parser.py`
- `packages/backend/app/repository/json_loader.py`
- `packages/backend/app/repository/device_field_parser.py`
- `packages/backend/app/repository/navigation_parser.py`
- `packages/backend/app/services/report_parser_service.py`
- `packages/backend/app/services/document_builder_service.py`
- `packages/backend/app/services/record_generator_service.py`
- `packages/frontend/src/components/EvidenceEditor.tsx`
- `packages/frontend/src/components/ExtractListEditor.tsx`
- `tests/test_html_parser.py`
- `tests/test_report_parser_service.py`
- `tests/test_document_builder_service.py`
- `packages/frontend/src/components/StructuredEditors.test.tsx`
- `openspec/changes/preview-export-correction/specs/electronic-inspection-record/spec.md`
