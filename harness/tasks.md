# 任务管理规则（Harness）

> 本文件定义任务管理的**流程约束**（Harness 骨架）。
> 具体的任务内容由 OpenSpec 变更包管理：`openspec/changes/<功能名>/tasks.md`

---

## 任务管理流程

1. **任务来源**：所有任务 MUST 通过 `/harness:propose` 生成到 `openspec/changes/<功能名>/tasks.md`
2. **执行顺序**：遵循 `harness/architecture.md` 的分层架构，按层级从低到高执行
3. **完成标记**：在变更包内的 tasks.md 中标记 `[x]`
4. **归档**：变更完成后通过 `/harness:archive` 归档到 `openspec/changes/archive/`

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
