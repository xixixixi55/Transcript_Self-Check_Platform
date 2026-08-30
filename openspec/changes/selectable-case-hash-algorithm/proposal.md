# Proposal: 统一案件所选哈希算法的归档链路

## 原因

现有实现把 MD5 作为固定的内部完整性算法，再把案件选择的 SHA-1 或 SHA-256 作为附加业务摘要。结果是 MD5 案件与 SHA 案件经过不同链路：SHA 案件会额外完整读取 RAR 计算 MD5，归档复用、恢复、下载和发布前安全门仍硬编码依赖 `ArchivePart.md5`。

正式需求是：用户选择 MD5、SHA-1 或 SHA-256 中任意一种后，三种算法必须经过相同的归档、持久化、复用、恢复、下载和发布链路；唯一差异只能是算法参数、摘要长度和显示名称，不得为 SHA 案件额外计算固定 MD5。检查笔录统一导出保持现行 Word + RAR 合同，不运行 HashMyFiles、不生成截图；已有 HashMyFiles 三算法能力保留，等待鉴定文书模块接入。

## 变更内容

- 将 `hash_algorithm + hash_value` 提升为新 `ArchivePart` 唯一正式文件哈希事实源；新 Manifest 不再要求或生成固定 `md5`。
- MD5、SHA-1、SHA-256 共用同一套计算、校验、Manifest、复用、恢复、下载、发布和错误处理流程。
- 旧 Manifest 缺少 `hash_algorithm/hash_value` 时，继续把合法 `md5` 兼容投影为 `md5 + 原值`，不批量改写存量数据。
- 检查笔录统一导出继续通过既有 Manifest 内容授权后原子发布 Word + RAR，明确不启动 HashMyFiles、不生成或发布 PNG；再次导出继续清理历史校验截图。
- 保留 HashMyFiles 三算法参数、完整摘要与三列截图能力作为内部未接线能力，供后续鉴定文书模块复用。
- 更新遗留 `md5_hash` 兼容载体、进度文案和软件工具描述，禁止字段名或历史工具名称把用户可见语义固定为 MD5。
- 保留报告缓存指纹、上下文绑定、发布记录、图片资产等非案件文件哈希使用的内部 SHA-256；它们不受案件算法选择影响。

## 能力

### Modified: 受控案件哈希算法合同

- 新案件继续固化 `md5 | sha1 | sha256` 算法快照。
- 新归档仅计算并持久化所选算法；三种算法的状态转换和安全门完全一致。
- 旧 MD5 Manifest 通过单向兼容读取层进入统一规范模型。

### Modified: 归档完整性与产物访问

- Manifest 验证、持久化恢复、安全复用、下载和发布按每个 part 的规范算法和值校验。
- 同名、同大小但内容变化的 RAR 在三种算法下均被拒绝。

### Preserved: 检查笔录统一导出边界

- 只发布最新 Word 与全部已验证 RAR，不运行 HashMyFiles、不生成截图。
- 继续由进入统一导出前的 Manifest 所选算法内容授权拒绝同大小篡改。
- staging、回滚和“不产生混合包”的原子发布合同保持不变。

## 影响

- **Level**：Level 3。该变更修改持久化 Manifest 合同及归档复用、恢复、下载、发布安全边界，回滚风险高，需要完整 proposal/spec/design/tasks、独立 Review 与 scoped full gate。
- **主关联**：重开 `selectable-case-hash-algorithm`。本需求直接推翻该未归档变更中“固定内部 MD5 + 可选业务哈希”的设计，属于冻结前反馈，不新建重复 change。
- **相关但不归属**：`background-compression-archive-completion` 提供 Manifest、后台归档和统一导出底座；本包会核对并消除其 delta 中固定 MD5 的冲突表述，但不复制其任务。`metadata-fingerprint-archive-path` 的文件元数据稳定性和路径安全继续复用，固定 MD5 结论由本包的新正式合同取代。
- **SharedTypes**：`packages/shared/types/archive.ts` 中新旧 Manifest 表达与兼容边界。
- **Backend Repository**：哈希计算、Manifest 规范化及保留的 HashMyFiles 三算法结果能力。
- **Backend Services**：归档生成、发布、完成、复用、恢复、下载与单独 Word；统一导出只核对不接入 HashMyFiles。
- **Frontend**：只需修正残留的固定 MD5 进度/展示文案；接口路径和用户操作不变。
- **Storage/API**：不做破坏性数据库迁移，不新增外部端点；存量 JSON 按读取时兼容。
- **Dependencies**：不新增第三方依赖，继续使用 Python `hashlib`、WinRAR 和 HashMyFiles 2.51。

## 非目标

- 不在解析报告阶段生成最终 RAR 哈希；正式哈希仍以 WinRAR 最终产物为对象。
- 不用 HashMyFiles 替代后台归档的 `hashlib`，也不把它接入检查笔录统一导出；GUI 能力等待鉴定文书模块使用。
- 不支持 CRC32、SHA-384、SHA-512、自定义算法或多算法同时选择。
- 不批量重写旧 Manifest、案件草稿或审计记录。
- 不改变缓存指纹、上下文哈希、发布摘要和图片资产指纹等非案件文件哈希算法。
- 不在本变更中改变默认算法值；是否把新案件默认值从 MD5 调整为 SHA-256另行决策。
- 不把统一导出迁移为新的 durable 后台任务。
