---
name: officecli
description: "在本项目中创建、编辑、校验 DOCX 时使用 officecli 工作流；适用于 officecli create、batch、save 调用，Word 导出故障排查，以及 officecli 的 Windows PATH、.cmd 和编码兼容问题。"
---

# OfficeCLI 项目技能

## 适用范围

将此技能用于本项目的 Word 检查笔录生成、预览内容导出、DOCX 内容校验和 officecli 调用故障排查。先阅读当前任务对应的 OpenSpec 文档和直接相关源文件，再修改实现。

官方通用技能说明见 [officecli 官方 SKILL.md](https://officecli.ai/SKILL.md)。本项目只采用其中与 DOCX 相关的规则，并叠加下方的项目架构约束。

## 官方能力基线

- 支持 `.docx`、`.xlsx`、`.pptx`；本项目当前只生成和校验 `.docx`。
- 不确定属性名、路径或参数格式时，先运行 `officecli help` 或 `officecli help docx <element>`，不要猜命令。
- 按 L1（读取/检查）→ L2（DOM 编辑）→ L3（原始 XML）的顺序选择能力；优先使用 L1/L2。
- 可使用 `--json` 获取机器可读结果；修改后用 `validate` 或 `view issues` 校验。
- resident 模式下，只有在非 officecli 程序读取文件前才需要 `save` 或 `close`；本项目通过 `FileResponse` 返回前必须显式 `save`。
- 需要格式专用规则时，按官方说明加载一个最具体的 skill，不要叠加多个格式 skill。

## 架构边界

- 只允许 `packages/backend/app/services/` 调用 officecli。
- `document_builder_service.py` 只负责把 `InspectionReport` 转换为 batch 命令数组。
- `record_generator_service.py` 负责 CLI 调用、临时 JSON、保存和输出文件校验。
- Controller、Repository、前端不得直接执行 officecli 或 `subprocess`。

## 标准生成流程

按以下顺序执行，不能省略 `save`：

1. 调用 `build_record_document(report, photo_paths)` 生成命令数组。
2. 调用 `officecli create <output.docx>` 创建目标文档。
3. 将命令数组以 UTF-8 JSON 写入临时文件。
4. 调用 `officecli batch <output.docx> --input <commands.json>` 写入内容。
5. 调用 `officecli save <output.docx>` 将 resident 文档落盘。
6. 检查目标文件存在且大小大于零；必要时解压 DOCX，检查 `word/document.xml` 中的关键文本和表格。

不要只用 HTTP 200 或文件存在作为成功判据；batch 后缺少 save 可能产生空白 DOCX。

## Windows 调用约束

- 使用 `shutil.which("officecli")` 或 `shutil.which("officecli.cmd")` 定位 CLI，不要硬编码 npm 全局目录。
- 子进程 PATH 必须包含 `C:\Windows\System32`，以便执行 `.cmd` 包装器。
- 使用 UTF-8 捕获 stdout/stderr；错误信息必须带上 return code 或 stdout/stderr。
- 导出前先检查 officecli 是否可用：`Get-Command officecli,officecli.cmd` 或 `where.exe officecli`。
- 未经用户授权，不要自动全局安装或升级 officecli。

## 命令数据规范

- 段落命令使用 `parent: "/body"`、`type: "paragraph"` 和 `props.text`。
- 表格先添加 `type: "table"`，再用 `set` 写入 `/body/tbl[1]/tr[n]/tc[m]` 的单元格。
- 图片使用 `type: "image"`，`props.file` 必须是已存在的安全路径。
- 附件清单为空时仍生成默认表头和一行空记录，保持导出结构稳定。
- 用户在预览页修改后的报告对象是唯一输入来源，不要在服务层重新猜测或覆盖编辑值。

## 验证与排错

修改文档生成逻辑后，至少运行：

```powershell
python -m pytest tests/test_document_builder_service.py -q
npm.cmd run pre-commit
```

遇到空白文档时依次检查：`create` 是否成功、batch JSON 是否有效、batch 是否返回非零、是否执行 `save`、最终 `document.xml` 是否包含预期内容。遇到“找不到 officecli”时检查 uvicorn 的 PATH 与 `.cmd` 定位，不要在前端增加绕过服务层的调用。
