# 架构约束文档

> 本文档是 AGENTS.md 中"架构 — 分层依赖规则"的详细说明。
> Agent 和人类开发者在修改代码结构时 MUST 参考本文档。

## 分层架构

### 层级定义

| 层号 | 层名 | 目录 | 说明 |
|------|------|------|------|
| 0 | SharedTypes | `packages/shared/types/` | 前后端共享的类型定义（实体、DTO、API 契约） |
| 1 | SharedConstants | `packages/shared/constants/` | 前后端共享的常量（错误码、文书类型枚举等） |
| 2 | SharedUtils | `packages/shared/utils/` | 前后端共享的纯函数工具（校验、格式化等） |
| 10 | FE_Hooks | `packages/frontend/src/hooks/` | 前端状态管理与业务逻辑封装 |
| 11 | FE_Components | `packages/frontend/src/components/` | 前端 UI 组件 |
| 12 | FE_Pages | `packages/frontend/src/pages/` | 前端页面路由 |
| 20 | BE_Repository | `packages/backend/app/repository/` | 后端数据访问层（文件读写、模板管理、HTML 解析） |
| 21 | BE_Services | `packages/backend/app/services/` | 后端业务逻辑层（文书生成编排、officecli 调用） |
| 22 | BE_Controllers | `packages/backend/app/controllers/` | 后端请求处理层（参数校验、调用 Service、构造响应） |
| 23 | BE_Routes | `packages/backend/app/routes/` | 后端路由定义与中间件编排 |

### 依赖规则矩阵

| 引用方 ↓ \ 被引用方 → | Types(0) | Constants(1) | Utils(2) | Hooks(10) | Comps(11) | Pages(12) | Repo(20) | Svcs(21) | Ctrl(22) | Routes(23) |
|----------------------|----------|-------------|---------|----------|----------|----------|---------|---------|---------|----------|
| **SharedTypes (0)** | - | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SharedConstants (1)** | ✅ | - | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SharedUtils (2)** | ✅ | ✅ | - | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **FE_Hooks (10)** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **FE_Components (11)** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **FE_Pages (12)** | ✅ | ✅ | ❌ | ✅ | ✅ | - | ❌ | ❌ | ❌ | ❌ |
| **BE_Repository (20)** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | - | ❌ | ❌ | ❌ |
| **BE_Services (21)** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | - | ❌ | ❌ |
| **BE_Controllers (22)** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | - | ❌ |
| **BE_Routes (23)** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | - |

> ✅ = 允许引用 | ❌ = 禁止引用
> 跨边界规则：前端层（10-12）和后端层（20-23）**禁止互相引用**。通信只能通过 SharedTypes 定义的 API 契约 + HTTP RESTful 调用。

### 为什么高层不能跳过中间层直接引用底层工具？

1. **可测试性**：高层可以独立测试，只需 mock 中间层接口
2. **业务逻辑集中**：业务规则集中在 Service 层，避免散落在 Controller 和 Routes 中
3. **并行开发**：Agent 可以并行开发不同层级，接口约定好即可
4. **变更隔离**：底层工具修改只影响直接引用它的中间层，不会级联到所有高层

### 横切关注点的处理

如果某个能力需要跨层使用（如：错误处理、日志记录），MUST 通过以下方式之一：
- SharedTypes 定义 API 契约接口，前后端各自实现
- 中间件注入（错误处理、认证、日志）

---

## 文件组织规则

### 目录对应关系

| 目录路径 | 层级 | 允许的文件类型 |
|---------|------|-------------|
| `packages/shared/types/` | Layer 0 | `.ts`（纯类型定义） |
| `packages/shared/constants/` | Layer 1 | `.ts`（纯常量） |
| `packages/shared/utils/` | Layer 2 | `.ts`（纯函数） |
| `packages/frontend/src/hooks/` | Layer 10 | `.ts`, `.tsx` |
| `packages/frontend/src/components/` | Layer 11 | `.tsx` |
| `packages/frontend/src/pages/` | Layer 12 | `.tsx` |
| `packages/backend/app/repository/` | Layer 20 | `.py` |
| `packages/backend/app/services/` | Layer 21 | `.py` |
| `packages/backend/app/controllers/` | Layer 22 | `.py` |
| `packages/backend/app/routes/` | Layer 23 | `.py` |

### 文件大小限制

- 每个文件 **MUST** 不超过 400 行
- 超过 200 行时 **SHOULD** 考虑拆分
- `scripts/lint-arch.ts` 当前以 `MAX_LINES = 400` 检查源码目录；超限文件只有在 `FILE_SIZE_EXCEPTIONS` 中显式列出时才会放行。
- 项目约定超限文件同时在文件头部说明原因；该说明属于治理要求，脚本本身只按例外列表判定。当前例外为 `report_parser_service.py`、`document_builder_service.py`、`template_filler_service.py` 和 `html_parser.py`。

### 导出规则

- **MUST** 使用命名导出（`export function` / `export const`），不使用默认导出
- index 文件 **MAY** 用于聚合导出，但 **MUST NOT** 包含逻辑代码
- Python 层使用 `__init__.py` 聚合导出，同样不得包含业务逻辑

### 测试文件组织

- 测试文件与源码**同目录**，命名为 `<name>.test.ts(x)` / `test_<name>.py`
- 测试文件**不受**源码命名约定约束（测试文件遵循测试框架的命名约定，不继承所在目录的源码命名规则）
- E2E 测试放在 `tests/e2e/` 目录
- 新增、替换测试基础设施或现有链路不可用时，先验证 DOM 环境、框架插件、setup 和运行时 mock；既有链路正常时不得为每次迭代重复配置。
- 常用测试落点如下；是否新增测试以 `harness/verification-strategy.md` 的风险与覆盖缺口判断为准：

| 源码层级 | 常用验证 | 工具 | 选择依据 |
|---------|---------|------|---------|
| Layer 0-1 (SharedTypes / SharedConstants) | 不需要测试 | tsc 覆盖 | — |
| Layer 2 (SharedUtils) | 单元测试 | Vitest | 新增纯逻辑风险或现有覆盖缺口 |
| Layer 10 (FE_Hooks) | Hook 测试 | Vitest + React Testing Library | 状态或副作用行为风险 |
| Layer 11 (FE_Components) | 组件测试 | React Testing Library | 用户交互与可访问合同风险 |
| Layer 12 (FE_Pages) | E2E | Playwright（规划中，当前未启用） | Spec 场景驱动 |
| Layer 20 (BE_Repository) | 单元测试 | pytest | IO、持久化和安全边界风险 |
| Layer 21 (BE_Services) | 单元测试 | pytest | 核心业务规则风险 |
| Layer 22 (BE_Controllers) | 集成测试 | pytest + httpx | API 合同和跨层接线风险 |
| Layer 23 (BE_Routes) | E2E | Playwright / pytest（规划中，当前未启用） | Spec 场景驱动 |

### 任务执行约束

- **MUST**: 按架构层级从低到高排列任务（Layer 0 → Layer 23）
- 行为变化的任务清单必须说明验证证据；先复用、修改或合并现有测试，只在覆盖缺口存在时新增用例。
- 测试可标注其覆盖的关键 Spec 场景，但不要求 Scenario 与用例一一对应。
- 核心合同、安全、持久化和关键转换覆盖必要边界；低风险展示不因所在层级被迫新增测试。
