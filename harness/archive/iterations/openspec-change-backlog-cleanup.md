# 迭代记录：OpenSpec 完成变更积压治理

> 日期：2026-09-11
> 变更包：`openspec/changes/archive/2026-09-11-*`
> Spec：`openspec/specs/`

## 📋 迭代概览

- 对活动区中状态为 `complete` 的变更逐包执行 scoped 严格文档检查，并归档至 `openspec/changes/archive/`。
- 归档前补齐已有 living spec reconciliation 证据，修正后续组件拆分造成的历史文件引用漂移。
- 对已被后续合同取代的解析缓存和归档快照方案显式记录 superseded 边界；归档统一跳过再次写入 specs，避免旧 delta 覆盖当前合同。
- 产品源码、测试数据和生成输出均未修改；用户已有的 `packaging/portable-manifest.json` 修改保持不变。

## ⚠️ 遇到的问题

### 问题：已完成 change 长期留在活动区

- **现象**：活动 change 列表混有大量 `complete` 包，少数 `tasks.md` 逐日追加反馈后接近千行，活动范围难以辨认。
- **根因**：实现收敛后未及时执行 reconciliation 核验和归档，导致 change 同时承担当前计划与历史日志职责。
- **修复方式**：按状态筛选完成包，逐包通过 scoped strict docs，确认 living spec 证据后归档；进行中的 change 保持原位。

### 问题：历史 delta 可能回退 living spec

- **现象**：部分完成包描述的持久化解析缓存、压缩模式缓存和输入快照方案已被后续正式合同取代。
- **根因**：变更完成状态只反映 checklist，不表示其中 delta 仍是最新合同。
- **修复方式**：归档前区分 `reconciled` 与 `superseded` 语义，为被取代包记录后继 change 和现行合同证据，并使用不重复更新 specs 的归档路径。

## 💡 沉淀的经验

1. 批量归档不能只看任务完成率；必须先确认 delta 已进入 living spec，或已被更晚合同明确取代。
2. `tasks.md` 应服务当前可执行工作。变更完成后及时归档，避免把活动包演化成长期反馈流水账。
3. 后续重构删除历史文件时，历史任务应标注“后续已拆分/移除”，不能保留会被文档门控误判为当前实现引用的路径。

## ✅ 已反哺到 Harness

- `AGENTS.md` 第 3、4、8 节已规定：已归档包不可改写，Level 2/3 归档前必须完成 delta、实现和 living spec 核对。
- `harness/iteration-guide.md` 的归档同步和常见陷阱已规定：不得跳过 sync，也不得把活动变更积压到统一验证阶段。
- `harness/entropy-rules.md` E-A7/E-A8 已提供任务完成和 reconciliation 结构门控；本次无需复制新增项目规则。

## 🔼 可反哺到模板

- [ ] 教训描述：归档前应显式区分“delta 已同步”和“delta 已被后续合同取代”，后者必须禁止重新写回 living spec。
- [ ] 建议写入模板的哪个文件：归档工作流的 delta sync/reconciliation 决策章节。
- [ ] 状态：pending

## 📊 与上次迭代的对比

- 活动区恢复为只包含真正进行中的变更；已完成历史仍可从归档目录追溯。
- 文档门控中的历史文件引用漂移已清零；剩余严格任务提示均来自真实未完成工作。

## 后续校正（2026-09-11）

- 后续生命周期审计证明，仅依据“无必选未完成 checklist”仍会把保留延期验收或未冻结反馈的 change 误判为完成；上面的“只包含真正进行中”结论只描述首轮清理结果，不再作为当前状态判断依据。
- 当前归档意图改由 `lifecycle_status` 明确表达；checkbox 继续只表示任务义务。该规则已反哺到 `AGENTS.md`、`harness/entropy-rules.md`、OpenSpec living spec 和双端 Harness 入口。
