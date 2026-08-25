# Proposal: 统一案件所选哈希算法的归档与导出链路

## Why

现有实现把 MD5 作为固定的内部完整性算法，再把案件选择的 SHA-1 或 SHA-256 作为附加业务摘要。结果是 MD5 案件与 SHA 案件经过不同链路：SHA 案件会额外完整读取 RAR 计算 MD5，归档复用、恢复、下载和统一导出前安全门仍硬编码依赖 `ArchivePart.md5`。统一导出中的 HashMyFiles 结果又只校验格式、长度、文件名和大小，没有与 Manifest 的业务摘要逐项等值比较。

正式需求是：用户选择 MD5、SHA-1 或 SHA-256 中任意一种后，三种算法必须经过相同的归档、持久化、复用、恢复、下载和统一导出链路；唯一差异只能是算法参数、摘要长度、显示名称和截图列宽。系统仍应在归档与最终副本两个信任边界独立计算，但不得为 SHA 案件额外计算固定 MD5。

## What Changes

- 将 `hash_algorithm + hash_value` 提升为新 `ArchivePart` 唯一正式文件哈希事实源；新 Manifest 不再要求或生成固定 `md5`。
- MD5、SHA-1、SHA-256 共用同一套计算、校验、Manifest、复用、恢复、下载、发布和错误处理流程。
- 旧 Manifest 缺少 `hash_algorithm/hash_value` 时，继续把合法 `md5` 兼容投影为 `md5 + 原值`，不批量改写存量数据。
- 统一导出不再先固定 MD5 全量复核再复制；先验证发布身份、路径、文件集合和精确大小，复制到同卷 staging 后由 HashMyFiles 计算所选算法，并与 Manifest `hash_value` 逐项等值比较。
- HashMyFiles 返回路径无关的结构化行结果；摘要不一致、算法列错误、行缺失/重复、文件名或大小不一致均阻止原子发布并保留上一版完整导出。
- 更新遗留 `md5_hash` 兼容载体、进度文案和软件工具描述，禁止字段名或历史工具名称把用户可见语义固定为 MD5。
- 保留报告缓存指纹、上下文绑定、发布记录、图片资产等非案件文件哈希使用的内部 SHA-256；它们不受案件算法选择影响。

## Capabilities

### Modified: 受控案件哈希算法合同

- 新案件继续固化 `md5 | sha1 | sha256` 算法快照。
- 新归档仅计算并持久化所选算法；三种算法的状态转换和安全门完全一致。
- 旧 MD5 Manifest 通过单向兼容读取层进入统一规范模型。

### Modified: 归档完整性与产物访问

- Manifest 验证、持久化恢复、安全复用、下载和发布按每个 part 的规范算法和值校验。
- 同名、同大小但内容变化的 RAR 在三种算法下均被拒绝。

### Modified: 统一导出完整产物包

- HashMyFiles 校验待发布副本，且结果必须与 Manifest 完全一致。
- 三种算法只改变 HashMyFiles 参数、摘要长度、标题和列宽，不改变导出编排。
- 失败继续遵守 staging、回滚和“不产生混合包”的原子发布合同。

## Impact

- **Level**：Level 3。该变更修改持久化 Manifest 合同及归档复用、恢复、下载、发布安全边界，回滚风险高，需要完整 proposal/spec/design/tasks、独立 Review 与 scoped full gate。
- **主关联**：重开 `selectable-case-hash-algorithm`。本需求直接推翻该未归档变更中“固定内部 MD5 + 可选业务哈希”的设计，属于冻结前反馈，不新建重复 change。
- **相关但不归属**：`background-compression-archive-completion` 提供 Manifest、后台归档和统一导出底座；本包会核对并消除其 delta 中固定 MD5 的冲突表述，但不复制其任务。`metadata-fingerprint-archive-path` 的文件元数据稳定性和路径安全继续复用，固定 MD5 结论由本包的新正式合同取代。
- **SharedTypes**：`packages/shared/types/archive.ts` 中新旧 Manifest 表达与兼容边界。
- **Backend Repository**：哈希计算、Manifest 规范化、HashMyFiles 结构化结果及文件边界校验。
- **Backend Services**：归档生成、发布、完成、复用、恢复、下载、单独 Word 与统一导出编排。
- **Frontend**：只需修正残留的固定 MD5 进度/展示文案；接口路径和用户操作不变。
- **Storage/API**：不做破坏性数据库迁移，不新增外部端点；存量 JSON 按读取时兼容。
- **Dependencies**：不新增第三方依赖，继续使用 Python `hashlib`、WinRAR 和 HashMyFiles 2.51。

## Non-Goals

- 不在解析报告阶段生成最终 RAR 哈希；正式哈希仍以 WinRAR 最终产物为对象。
- 不用 HashMyFiles 替代后台归档的 `hashlib`；GUI 工具只负责待发布副本的独立复核和截图。
- 不支持 CRC32、SHA-384、SHA-512、自定义算法或多算法同时选择。
- 不批量重写旧 Manifest、案件草稿或审计记录。
- 不改变缓存指纹、上下文哈希、发布摘要和图片资产指纹等非案件文件哈希算法。
- 不在本变更中改变默认算法值；是否把新案件默认值从 MD5 调整为 SHA-256另行决策。
- 不把统一导出迁移为新的 durable 后台任务。
