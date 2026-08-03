# 任务管理规则（Harness）

> 本文件定义任务管理的**流程约束**（Harness 骨架）。
> 具体的任务内容由 OpenSpec 变更包管理：`openspec/changes/<功能名>/tasks.md`

---

## 任务管理流程

任务级别遵循 `AGENTS.md` 治理规则：

- **Level 1**：小修改（局部 Bug 修复、文档修正、仓库卫生），无需 OpenSpec change。直接修改、验证、提交。
- **Level 2**：普通功能，通常维护对应变更包内的 `tasks.md`。
- **Level 3**：公共合同或架构变化，完整 OpenSpec 流程（propose → spec → tasks → apply → archive）。

Bug/回归任务先按根目录 `AGENTS.md` §3 的规则检查是否属于已有活跃变更包；匹配时沿用原变更包，不匹配时再创建新的修复任务。

无法判断级别时默认采用较轻级别。安全约束和事实源修复优先。living spec 修正必须有明确代码或测试证据。活动 Level 3 变更中允许按治理规则同步合同。

任务来源通过 `/harness:propose` 生成到 `openspec/changes/<功能名>/tasks.md`。执行顺序遵循 `harness/architecture.md` 的分层架构。完成标记在变更包内的 tasks.md 中标记 `[x]`。变更完成后通过 `/harness:archive` 归档。

### 任务是否必选

- 普通 checklist 任务（`- [ ] ...`）默认是必选任务。
- 只有在同一任务行末尾明确写出 `[OPTIONAL]`、`[DEFERRED]` 或 `[N/A]` 时，未勾选才不会阻塞严格检查。
- 脚本只读取 checklist 状态和上述显式标记，不根据任务标题、文件是否存在或自然语言推断完成度。
- Level 2 收尾使用 `npm run verify:docs:strict -- --change <变更包名称>`，只检查当前变更包；Level 3 当前变更使用 `npm run verify:full -- --change <变更包名称>` 执行全仓库自动化工程检查，但严格任务状态只检查指定变更包；全局发布/集中归档使用 `npm run verify:full:all` 或 `npm run verify:docs:strict:all`。

---

## 任务格式参考

> 以下为 OpenSpec 变更包内 `tasks.md` 的参考示例。
> 格式约束详见 `openspec/config.yaml` 的 `rules.tasks`；此处仅提供结构参考，Agent 按此格式生成任务清单。

```markdown
## Phase N: USXX — 功能名称

> Spec: `openspec/specs/<能力>/spec.md`

### 影响矩阵

| 层级 | 新增 | 修改 |
|------|------|------|
| Layer 0-N | ... | ... |

### 任务清单

- [ ] TXXX [P] [USXX] **任务描述**
  - 文件：`src/path/to/file.ts`（新建/修改）
  - 内容：具体实现内容
  - 依赖：TXXX
  - 验证：验证命令
```
