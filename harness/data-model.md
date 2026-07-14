# 数据建模约束（Harness）

> 本文件定义数据模型的**约束规则**（Harness 骨架）。
> 具体的实体定义和数据结构详见 OpenSpec 数据模型 Spec（路径见 AGENTS.md 索引）。

## 约束规则

### 类型一致性
- **MUST**: 类型定义文件与 OpenSpec 数据模型 Spec 保持一致
- **MUST**: 新增 type/interface 后同步更新 OpenSpec 数据模型 Spec
- **MUST**: npx tsx scripts/check-docs.ts 自动检查一致性

#### 一致性检查清单

`check-docs` 脚本 MUST 验证以下项目：
- [ ] 类型定义文件中的每个 `interface` / `type` 在 OpenSpec 数据模型 Spec 中有对应定义
- [ ] 两处的字段名、字段类型完全匹配
- [ ] 新增类型不在类型定义文件中出现但缺失于 Spec（或反之）

### 命名规范
- **MUST**: 实体接口使用 PascalCase
- **MUST**: 类型别名使用 PascalCase
- **MUST**: 常量使用 UPPER_SNAKE_CASE

### 数据存储规范
- **MUST**: 所有时间字段使用 ISO 8601 格式的 string 类型
- **MUST**: 所有实体必须有唯一标识字段（`id`）
- **MUST**: 模板文件按文书类型分目录存储，生成的文书按日期+案件编号归档
- **MUST NOT**: 存储重复数据，HTML 解析结果缓存为 JSON，避免重复解析

### 变更流程
- **MUST**: 数据模型变更通过变更包（`/harness:propose`）管理
- **MUST**: 变更归档后（`/harness:archive`）同步更新 OpenSpec 数据模型 Spec
