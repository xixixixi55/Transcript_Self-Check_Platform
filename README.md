# 笔录自检平台（文枢）

电子数据检查笔录自动生成平台，面向民警使用。

## 功能

- 📄 **电子数据检查笔录自动生成**：基于 HTML 取证报告 + Word 模板，自动生成 .docx 格式检查笔录
- ✏️ **人工调节修改**：支持在线预览和编辑生成的文书
- 📋 **6 类文书扩展**：预留专业化勘查报告、电子数据鉴定文书、传统现场三录、现场检查笔录、法医鉴定文书

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + TypeScript + Ant Design 5 + Vite |
| 后端 | FastAPI (Python 3.11) |
| 文档操作 | officecli (模板 merge + DOM 编辑) |
| HTML 解析 | BeautifulSoup4 |
| 异步任务 | Celery + Redis |
| 存储 | 本地文件系统 |

## 快速开始

### 环境要求

- Node.js >= 18
- pnpm >= 9
- Python >= 3.11
- Redis（Celery 异步任务依赖）

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

## 工作流程

本项目使用 Harness Engineering + OpenSpec 方法论，详见 `AGENTS.md` 和 `harness/iteration-guide.md`。

## License

内部使用
