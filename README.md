# 笔录自检平台（文枢）

电子数据检查笔录自动生成平台，面向民警使用。

## 当前已实现

当前唯一正式输出仍由 `InspectionReport` legacy DTO 管线生成；该管线已经消费最终 `ArchiveManifest`、`AttachmentPlan` 和 `current-template-v1` TemplateProfile。这里的“legacy”表示生产 DTO/Controller 主链，不能据此否定归档与受控渲染能力已经接入。

- 📄 **HTML/结构化报告解析**：新旧格式自动检测，案件信息/设备列表/软件版本提取
- ✏️ **InspectionReport 兼容审核**：在线预览和编辑，检查人员管理，主软件确认
- 📦 **ArchiveContext + WinRAR 规划与执行**：受控分卷归档，ArchiveManifest 生成
- 🔢 **光盘序列**：自动编号、日期校验、连续性检查
- 🖼️ **MaterialPhotoGroup**：附件2 显式检材-图片绑定，每组两张
- 📋 **AttachmentPlan**：附件1/2/3 页面计划与 current-template-v1 渲染
- 🎨 **OOXML/VML 渲染**：黑字策略、输出卫生、模板指纹验证

## 迁移中

- 🔄 **CanonicalInspectionCase**：统一内部模型（基础实现已完成，尚未生产接线）
- 🔄 **pipeline_mode**：legacy/shadow/canonical 三模式（集中读取，当前默认 legacy；canonical 正式输出未启用）
- 🔄 **影子比较**：新旧管线脱敏比较（生产旁路已接线；真实样本差异治理尚未完成）
- 🔄 **DocumentRenderPlan**：未来统一渲染合同（尚无生产类型、构造或消费）
- 🔄 **ReportProfile / 通用 TemplateProfile**：后续扩展

当前路线图：Legacy 生产稳定化基本完成；Shadow 生产接线已完成，真实样本治理未完成；Canonical 正式切换尚未开始。延期的大容量验收不阻塞 Shadow 真实样本差异治理、Canonical 代码开发、只读预览/编辑门控、候选输出隔离或回滚演练；但在补测通过或风险接受前，Canonical 不能成为默认唯一正式输出，最终人工验收和 OpenSpec 归档也未完成。Shadow 只生成脱敏诊断，不生成第二份正式产物，也不能阻塞 Legacy。

## 真实归档验收状态

- 已有部分真实证据：4GB 双卷、22GB 单卷
- 延期：22GB 双卷、45GB 真实执行、真实向上 replan（不是失败、取消或完成）
- 仍未完成：`15.1/15.1T` 完整人工验收

这些资源型验收不阻塞日常 Legacy/Shadow 功能开发、Shadow 真实样本差异治理或 Canonical 预切换开发与验证；但阻塞 Canonical 成为默认唯一正式生产输出，也阻塞本变更最终验收和 OpenSpec 归档。只有在有足够资源的验收机器上补测通过，或由发布负责人明确记录风险接受后，才可解除该正式发布门槛。若单独发布 Legacy-only 维护版本，延期项仍必须明确记录为发布风险，不能在文档中同时写成“已完成”。

## 后续规划

- 完成延期的真实归档验收
- Canonical 代码与预切换验证（只读预览、编辑门控、候选输出隔离、回滚演练）
- Canonical 默认唯一正式生产输出切换
- 更多报告/模板 Profile
- 多类文书扩展

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + TypeScript + Ant Design 5 + Vite |
| 后端 | FastAPI (Python 3.11) |
| 文档渲染 | python-docx + lxml（主路径），officecli（旧版回退） |
| HTML 解析 | BeautifulSoup4 |
| 归档压缩 | WinRAR CLI |
| 存储 | 本地文件系统 |

## 快速开始

### Windows 便携发布

正式便携包通过 `npm run build:portable` 构建。发布物包含冻结后端、生产前端、私有 Node/officecli、内置模板和 HashMyFiles，不包含 WinRAR 或任何案件数据。用户从官方渠道独立安装并按许可使用 WinRAR 后，解压 ZIP 并双击 `文枢.exe`；应用启动后驻留系统托盘，可从托盘重新打开或安全退出，持久数据统一写入 `%LOCALAPPDATA%\文枢`。发布清单和详细行为以 `openspec/changes/portable-windows-distribution/` 为准。

### 环境要求

- Node.js >= 18
- pnpm >= 9
- Python >= 3.11
- WinRAR（归档压缩依赖）

### 安装

```bash
# 安装前端依赖
pnpm install

# 安装后端 Python 依赖
cd packages/backend
pip install -r requirements.txt
```

### 开发

```bash
# 启动前端 + 后端开发服务器
pnpm dev

# 或分别启动
pnpm --filter @biji/frontend dev   # 前端 http://localhost:30000
pnpm --filter @biji/backend dev    # 后端 http://localhost:30010
```

### 验证

```bash
# 快速验证（提交前推荐）
pnpm verify:quick         # 架构约束 + 类型检查 + 文档检查（默认模式）

# 模块验证
pnpm verify:frontend      # 前端类型检查 + 测试
pnpm verify:backend       # 后端测试

# 完整验证（推送前 / CI 推荐）
pnpm verify:full          # 全部检查 + 构建 + 全部测试 + 严格文档检查

# 旧命令（保持兼容）
pnpm verify               # → 等同于 verify:full
pnpm test                 # → 运行全部测试
pnpm check-docs           # → 文档检查（严格模式，11 项）
```

## 项目结构

详见 `harness/directory.md`（目录结构唯一真相源）。

## 仓库资产

详见 `harness/repository-assets.md`。关键规则：
- 正式模板与不可变历史版本仅按 `harness/repository-assets.md` 的白名单跟踪
- 生成输出（`output/`, `packages/output/`）不进入 Git
- 所有测试数据必须是明确合成数据

## 工作流程

本项目使用 Harness 工程化 + OpenSpec 方法论，详见 `AGENTS.md` 和 `harness/iteration-guide.md`。

## 许可证

内部使用
