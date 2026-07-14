# AGENTS.md — 笔录自检平台（文枢）

> Agent 工作导航。所有规则均可通过 npm run pre-commit 自动检查。

## 项目上下文

详见 `openspec/config.yaml`（技术栈、开发约定、需求规则）。

## 架构 — 分层依赖规则

```
共享基础层:
  SharedTypes (0) → SharedConstants (1) → SharedUtils (2)
                                              ↓
前端分支 (10-12):                         后端分支 (20-23):
  FE_Hooks (10)                            BE_Repository (20)
    ↓                                        ↓
  FE_Components (11)                       BE_Services (21)
    ↓                                        ↓
  FE_Pages (12)                            BE_Controllers (22)
                                              ↓
                                           BE_Routes (23)
```

**MUST**: 依赖方向严格单向，高层可引用低层，反之禁止。
**MUST**: 前端和后端只能通过 SharedTypes 中定义的 API 契约通信，不能直接引用对方的层。

详见 `harness/architecture.md`（依赖矩阵、横切关注点规则）。

## 目录结构

详见 `harness/directory.md`（目录结构）。

| 目录路径 | 层级 | 允许的文件类型 |
|---------|------|-------------|
| `packages/shared/types/` | Layer 0 (SharedTypes) | `.ts` |
| `packages/shared/constants/` | Layer 1 (SharedConstants) | `.ts` |
| `packages/shared/utils/` | Layer 2 (SharedUtils) | `.ts` |
| `packages/frontend/src/hooks/` | Layer 10 (FE_Hooks) | `.ts`, `.tsx` |
| `packages/frontend/src/components/` | Layer 11 (FE_Components) | `.tsx` |
| `packages/frontend/src/pages/` | Layer 12 (FE_Pages) | `.tsx` |
| `packages/backend/app/repository/` | Layer 20 (BE_Repository) | `.py` |
| `packages/backend/app/services/` | Layer 21 (BE_Services) | `.py` |
| `packages/backend/app/controllers/` | Layer 22 (BE_Controllers) | `.py` |
| `packages/backend/app/routes/` | Layer 23 (BE_Routes) | `.py` |

## 命名约定

| 类型 | 规则 | 示例 |
|------|------|------|
| 文件名（通用） | kebab-case / snake_case | `record-service.ts` / `record_service.py` |
| React 组件文件 | PascalCase | `RecordEditor.tsx` |
| Hook 文件 | use 前缀 + camelCase | `useRecordGenerate.ts` |
| Python Controller 文件 | snake_case + _controller 后缀 | `record_controller.py` |
| Python Service 文件 | snake_case + _service 后缀 | `record_service.py` |
| TypeScript 函数/方法 | camelCase | `fetchRecordData` |
| Python 函数/方法 | snake_case | `generate_record` |
| 类型/接口 | PascalCase | `InspectionRecord` |
| 常量 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE` |

## 规则

### 代码
- 详见 `harness/architecture.md`（文件大小限制、导出规则等）
- **MUST**: 依赖方向严格单向，高层可引用低层，反之禁止
- **MUST**: React 组件使用函数式组件 + Hooks，每个组件文件只导出一个组件
- **MUST**: FastAPI Controller 每个函数处理一个端点，参数使用 Pydantic 模型校验
- **MUST**: Python Service 不直接接触 HTTP 请求/响应对象，通过 Controller 传入纯数据
- **MUST**: officecli 调用统一封装在 BE_Services 层，其他层不直接调用 CLI

### 文档
- **MUST**: 修改代码后运行 npm run pre-commit，不通过不能提交
- **MUST**: 新增**目录**后更新 `harness/directory.md`（目录结构唯一真相源，文件级别无需逐一列出）
- **MUST**: 新增 type/interface 后更新 `openspec/specs/data-model.md`
- **MUST**: 任何代码变更前，先更新对应的 OpenSpec proposal.md 和 spec.md——不经 Spec 直接改代码是违规操作
- **MUST NOT**: 文档中硬编码会变的数字——写完后自检：这个数字将来会变吗？会 → 删掉
- **MUST NOT**: 多个文件中复制同一信息——用"详见 xxx"代替

### 测试
- **MUST**: 新增/修改的代码必须有配套测试
- **MUST**: 测试覆盖范围由 Spec 场景驱动（E2E/组件），底层测试由 Agent 自主补充
- **MUST**: 冲突时以 Spec 为仲裁——代码不符合 Spec 改代码，测试不符合 Spec 改测试
- 测试框架：pytest（后端单元测试）+ Vitest（前端单元测试）+ React Testing Library（组件测试）+ Playwright（E2E 测试）

### 验证硬限制
- **MUST**: 单步连续失败达到上限 → 停止，报告问题，请求人类介入
- **MUST**: 单 Task 总验证循环达到上限 → 立即停止并生成问题摘要
- 具体阈值和升级策略详见 `harness/iteration-guide.md`（④开发节奏 — 硬性终止条件）

## 工作协议

**每次对话开始时** MUST 阅读本文件了解项目上下文和约束。
**开始新功能/迭代时** MUST 先阅读 `harness/iteration-guide.md`，按 6 步迭代闭环执行。

### Harness 命令

| 命令 | 阶段 | 做什么 | 核心约束 |
|------|------|--------|---------|
| `/harness:propose "描述"` | ① ② ③ | 需求定义 + 影响分析 + 任务拆解 | tasks 按架构层级排序；影响分析按分层矩阵 |
| `/harness:apply` | ④ | 按任务开发 | 开发节奏：写码→验证→测试→有效性；失败 3 次停止 |
| `/harness:verify` | ⑤-工程 | 运行门控脚本 | npm run verify + npm run test + npm run check-docs |
| `/harness:review` | ⑤-需求 | 三维度验证 | 完整性 + 正确性 + 一致性；CRITICAL 阻断归档 |
| `/harness:archive` | ⑥ | 归档同步 | 自动化门控（E-A1~A6）→ Agent 自治修复（E-M1/M3/M4）→ 人工确认（E-M2/M5）→ 迭代记录 |
| `/harness:status` | — | 展示项目状态 | — |
| `/harness:continue` | — | 从中断恢复 | — |
| `/harness:fix "描述"` | 快捷 | 快速修 Bug | 简化流程，仍 MUST 有测试 |
| `/harness:code-review` | ④-审查 | 独立 Sub-Agent 代码审查 | 独立上下文，5 维度审查，最多 2 轮修复-重审 |

详细执行协议见 `.claude/commands/harness/` 下对应文件（如命令不可用，按上表核心约束 + `harness/iteration-guide.md` 执行）。

## 工程命令

```bash
npm run dev         # 启动开发服务器（前端 + 后端）
npm run build       # 构建前端生产版本
npm run lint:arch   # 架构约束检查
npm run verify      # 综合验证（lint:arch + typecheck + build）
npm run test        # 运行全部测试（前端 + 后端）
npm run check-docs  # 文档一致性检查
npm run pre-commit  # 提交前门控（verify + test + check-docs）
```

## 文档索引

### Harness 运营文档（流程 + 约束 + 验证）

| 类型 | 路径 | 描述 |
|------|------|------|
| 🔄 迭代指南 | `harness/iteration-guide.md` | **迭代时首先阅读** |
| 📐 架构约束 | `harness/architecture.md` | 分层规则、依赖矩阵 |
| 💾 数据建模约束 | `harness/data-model.md` | 数据建模规则（具体模型详见 OpenSpec） |
| ✅ 任务管理规则 | `harness/tasks.md` | 任务流程约束 + 模板 |
| 🗂️ 目录结构 | `harness/directory.md` | 目录结构（目录维度） |
| 🧹 熵治理 | `harness/entropy-rules.md` | 文档一致性、规则冲突、教训沉淀 |
| 🔒 上下文管理 | `harness/context-management.md` | 上下文架构（信息分层 + 延迟加载）+ 上下文隔离（任务级边界） |
| 🔎 Code Review Agent | `harness/code-review-agent.md` | 独立 Sub-Agent 代码审查（生成者与评估者分离） |

### OpenSpec 需求文档（需求 + 设计 + 任务）

| 类型 | 路径 | 描述 |
|------|------|------|
| 🔧 项目配置 | `openspec/config.yaml` | 技术栈、开发约定、需求规则 |
| 📋 需求规格 | `openspec/specs/` | **能力 spec（单一真相源）** |
| 💾 数据模型 | `openspec/specs/data-model.md` | 实体定义、数据结构 |

### 信息查找指引

| 想找什么 | 去哪里 |
|---------|-------|
| 某次迭代的变更包（proposal/specs/design/tasks） | `openspec/changes/archive/<日期-功能名>/` |
| 某次迭代的经验教训和问题复盘 | `harness/archive/iterations/<功能名>.md` |
| 当前生效的需求规格 | `openspec/specs/<能力>/spec.md` |
| 当前的架构规则和约束 | `harness/architecture.md` |
| 当前的数据模型定义 | `openspec/specs/data-model.md` |

> 归档文件中的路径以归档时为准，可能与当前目录结构不一致。Agent 不应信赖归档中的路径引用。
