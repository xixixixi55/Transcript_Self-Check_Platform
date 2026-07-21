# 任务管理规则（Harness）

> 本文件定义任务管理的**流程约束**（Harness 骨架）。
> 具体的任务内容由 OpenSpec 变更包管理：`openspec/changes/<功能名>/tasks.md`

---

## 任务管理流程

任务级别遵循 `AGENTS.md` 治理规则：

- **Level 1**：小修改（局部 Bug 修复、文档修正、仓库卫生），无需 OpenSpec change。直接修改、验证、提交。
- **Level 2**：普通功能，通常维护对应变更包内的 `tasks.md`。
- **Level 3**：公共合同或架构变化，完整 OpenSpec 流程（propose → spec → tasks → apply → archive）。

无法判断级别时默认采用较轻级别。安全约束和事实源修复优先。living spec 修正必须有明确代码或测试证据。活动 Level 3 变更中允许按治理规则同步合同。

任务来源通过 `/harness:propose` 生成到 `openspec/changes/<功能名>/tasks.md`。执行顺序遵循 `harness/architecture.md` 的分层架构。完成标记在变更包内的 tasks.md 中标记 `[x]`。变更完成后通过 `/harness:archive` 归档。

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
