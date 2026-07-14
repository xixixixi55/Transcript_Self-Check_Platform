# 设计：按压缩模式隔离解析缓存

## 决策

`parse_report` 为同一报告目录分别使用压缩和不压缩两份缓存：

- `output/parsed/[报告目录名].compress.json`
- `output/parsed/[报告目录名].nocompress.json`

缓存命中前仍使用源 JSON 修改时间校验。这样缓存结果天然与 `rar_info`、软件工具列表等压缩相关字段保持一致，不需要在返回前修改缓存对象。

## 备选方案

- 在单一缓存 JSON 中增加模式字段：需要兼容旧缓存并处理模式不一致时的重建，容易把压缩结果泄漏到另一种模式，故不采用。
- 每次命中缓存后重新执行压缩判断：会增加分支和状态同步，且无法解决缓存中的 WinRAR 工具列表，故不采用。

## 影响范围

- `packages/backend/app/services/report_parser_service.py`
- `tests/test_report_parser_service.py`
