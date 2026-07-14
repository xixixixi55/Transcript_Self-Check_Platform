# 迭代记录：优化上传流程

> 日期：2026-07-13
> 变更包：`openspec/changes/archive/2026-07-13-optimize-upload-flow/`
> Spec：`openspec/specs/electronic-inspection-record/spec.md`

## 📋 迭代概览

| 指标 | 数值 |
|------|:--:|
| 新增能力 | 4 (CAP-006~009) |
| 修改能力 | 2 (CAP-001, CAP-004) |
| 新增文件 | 5（含 3 个测试文件） |
| 修改文件 | 7 |
| 涉及层级 | L0, L1, L10, L11, L12, L20, L21, L22 |
| 后端测试 | 18 个新增（累计 29 个） |
| 前端构建 | ✅ 成功 |
| 架构检查 | ✅ 通过（无违规） |
| 类型检查 | ✅ 通过 |
| 未完成任务 | T016（E2E 测试，待 Playwright 基础设施） |

## ⚠️ 遇到的问题

### 1. 测试假数据格式不匹配 html_parser
- **现象**：`test_report_parser_service.py` 集成测试使用普通 JSON 格式，但 html_parser 期望美亚 JS-JSON 格式（`contents` 数组、`tp`/`ct`/`c2`/`c3` 字段）
- **根因**：对美亚报告数据结构理解不足
- **修复方式**：改用 mock 方式测试 Service 层核心逻辑，不依赖真实 parser 数据格式
- **耗时**：1 轮验证

### 2. shared 包 dist 过期导致 typecheck 失败
- **现象**：`RarInfo` 和 `SUPPORTED_ARCHIVE_FORMATS` 已添加到源文件，但 `pnpm typecheck` 报"no exported member"
- **根因**：shared 包使用 `composite: true`，前端 typecheck 依赖 dist 中的 `.d.ts` 声明文件
- **修复方式**：运行 `npx tsc --build` 重新生成声明文件
- **耗时**：1 轮验证

### 3. document_builder_service 硬编码未覆盖检查
- **现象**：review 阶段发现 builder 中 Hash 特殊分支和 WinRAR 硬编码拼接问题
- **根因**：propose 阶段未注意到此已有代码的硬编码
- **修复方式**：在 apply 阶段新增 T007a，移除所有硬编码渲染逻辑
- **耗时**：在 Service 层完成时一并修复

## 💡 沉淀的经验

1. **变更包 propose 时应全面扫描已有代码的硬编码**：本次在 propose 阶段遗漏了 `document_builder_service.py` 的硬编码问题，导致 apply 中需要新增任务。改进：propose 时搜索相关文件中是否有版本号、工具名等硬编码值。
2. **mock 优于假数据**：当被测代码深度依赖复杂数据格式时，mock 比构造假数据更可靠、更易维护。
3. **composite TypeScript 项目需要主动 rebuild**：修改 shared 包后必须运行 `tsc --build` 或等效命令刷新 dist，否则引用该包的前端项目 typecheck 会失败。

## ✅ 已反哺到 Harness（第 2 层 — 项目级）

- 无新增 Harness 规则 — 本次变更的核心约束通过 OpenSpec Spec（REQ-016）和代码实现固化
- 修复后的 `document_builder_service.py` 和 `report_parser_service.py` 中的动态 software_tools 逻辑作为后续类似场景的参考实现

## 🔼 可反哺到模板（第 1 层 — 通用级）

- [ ] 教训描述：propose 阶段应扫描已有代码中的硬编码值，避免 apply 阶段新增任务
- [ ] 建议写入模板的哪个文件：`harness/iteration-guide.md` 常见陷阱
- [ ] 状态：pending

## 📊 与上次迭代的对比

| 指标 | 上次（电子数据检查笔录） | 本次（优化上传流程） |
|------|:--:|:--:|
| 任务数 | 31 | 17 |
| 测试数 | 11 → | 29 (+18) |
| 发现的新问题 | officecli subprocess 编码 | 假数据格式、dist 过期、硬编码遗漏 |
| 反哺的规则 | — | — |
