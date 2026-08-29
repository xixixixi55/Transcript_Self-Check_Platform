# 预览字段映射与 Word 导出修复

## 原因

手动测试发现，报告解析结果没有完整进入预览页面，设备名称、IMEI、序列号和检材编号等关键字段为空或语义错误；软件工具缺少默认的 Python hash 库，附件 1 表头也与实际 Word 模板不一致。导出接口虽然返回了 `.docx` 文件，但生成文档需要可验证地包含当前预览内容，避免出现空白文档。

## 变更内容

修复“报告解析 → InspectionReport → 预览编辑 → Word 生成”的字段映射和文档构建链路：

1. 从设备列表/Base 数据中稳定提取检材、设备名称、IMEI1、IMEI2 和序列号，并在预览中默认填充。
2. 将预览中的设备字段按报告“设备名称”语义展示，检材编号与报告检材名称保持一致。
3. 默认追加用于计算 hash 的 Python 标准库工具。
4. 将附件 1 固定清单表头统一为“序号、电子数据、来源、提取方式、文件MD5哈希值”。
5. 导出 Word 时写入完整正文和附件表格，并增加非空文档验证。

## 非目标

- 不改变上传格式、解析接口路径或文件存储目录。
- 不新增数据库表或异步任务。
- 不重新设计预览页面的编辑交互。

## 能力

- CAP-013：设备/检材字段可靠映射
- CAP-014：默认 hash 工具与附件 1 模板
- CAP-015：Word 导出内容完整性

## 影响

| 层级 | 文件/目录 | 影响 |
|---|---|---|
| Layer 0 | `packages/shared/types/` | 保持现有 `EvidenceItem`/`TableData` 契约，修正字段语义注释 |
| Layer 11 | `packages/frontend/src/components/` | 设备名称标签、附件 1 默认表头 |
| Layer 20 | `packages/backend/app/repository/report/html_parser.py` | 设备/Base 字段解析与兼容回退 |
| Layer 21 | `packages/backend/app/services/report/report_parser_service.py`、`document_builder_service.py`、`record_generator_service.py` | 默认工具、附件表格、Word 内容与非空校验 |
| Layer 22 | `packages/backend/app/controllers/record_controller.py` | 保持导出响应契约，透传生成失败 |

## 验证

- 后端：pytest 覆盖设备字段、软件工具、附件表格和导出文档 XML 内容。
- 前端：Vitest/React Testing Library 覆盖预览默认值与附件表头。
- 门控：`npm run pre-commit`。
