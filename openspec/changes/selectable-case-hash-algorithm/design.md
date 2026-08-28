# Design: 三算法同链与最终副本哈希闭环

## 背景

当前 `ArchivePart` 同时保存固定 `md5` 和案件业务 `hash_algorithm/hash_value`。MD5 案件复用一次计算，SHA-1/SHA-256 案件则先计算 MD5、再额外读取文件计算业务摘要。归档完成后的多个安全门仍固定读取 `md5`；统一导出又对 RAR 重新计算 MD5、复制文件，再由 HashMyFiles 计算业务算法，但 HashMyFiles 行结果没有与 Manifest 摘要比较。

本设计把“算法策略”和“业务编排”分离：所有编排只消费规范的 `algorithm + digest`，MD5、SHA-1、SHA-256 只是同一接口的不同参数。

## D1. 新 Manifest 只保留一个正式文件哈希

**决策**：新 `ArchivePart` 必须保存 `hash_algorithm` 与 `hash_value`，不再要求生成 `md5`。所有新代码以该二元组为唯一文件内容事实源。

**理由**：用户选择的是案件全链路算法。继续保留固定 MD5 会造成 SHA 案件额外 I/O、双重事实源和安全门语义分裂。

**兼容性**：规范化读取层接受旧 `{md5}` part，并投影为 `{hash_algorithm: "md5", hash_value: md5}`。若新字段存在，则必须完整、合法且算法与摘要长度匹配；不得因同时存在旧 `md5` 而覆盖新值。旧字段只允许作为 legacy 输入，不再由新 Manifest 写出。

**备选方案及拒绝理由**：

- 保留固定 MD5并把 SHA 作为附加摘要：延续当前链路不对称和重复读取，拒绝。
- 内部固定 SHA-256、业务使用所选算法：安全强度更高，但仍违反“用户选择哪种算法就全链路使用哪种算法”的正式需求，拒绝。
- 破坏性迁移全部旧 Manifest：会增加离线迁移与回滚风险，读取时兼容足够，拒绝。

## D2. 一个规范哈希模型贯穿全部安全门

**决策**：Repository 层提供唯一的算法规范化、摘要验证、legacy part 投影和受控路径流式计算能力；Service 层的归档生成、Manifest 验证、复用、恢复、下载、发布和完成投影只消费该规范模型。

**理由**：消除 `part["md5"]`、`verified_md5s` 和算法分支散落在多个 Service 中的风险，保证三算法只在 Repository 策略参数处存在差异。

**约束**：

- 同一 Manifest 的全部 part 必须使用同一算法。
- Manifest 算法必须与案件不可变快照一致；不一致时阻止正式完成或导出。
- 案件算法进入归档复用指纹；算法变化不得复用旧产物。
- 摘要比较大小写不敏感，持久化与用户投影保持既有大写展示规则。
- `md5_hash` 只作为 legacy DTO/模板键，任何逻辑不得从键名推断算法。

**备选方案及拒绝理由**：各调用点自行判断新旧字段会产生不一致回退和绕过安全门，拒绝。

## D3. 归档阶段每个 RAR 只计算所选算法

**决策**：WinRAR 正常退出并通过 `rar t` 完整性测试后，Python `hashlib` 对每个实际 RAR 流式读取一次，只计算案件选择的算法并写入 Manifest。发布重试复用同一批已验证摘要，不因草稿发布 CAS 重试重复读取。

**理由**：`rar t` 证明压缩结构可读取；所选摘要建立内容身份。两者职责不同，但无需再为 SHA 案件计算固定 MD5。

**备选方案及拒绝理由**：

- 归档阶段直接启动 HashMyFiles：GUI、桌面会话和窗口自动化不适合作为后台归档成功的核心依赖，拒绝。
- 在 WinRAR 写入过程中读取未完成分卷：会产生不稳定摘要和文件竞争，拒绝。

## D4. 统一导出使用 HashMyFiles 完成最终内容复核

**决策**：统一导出取得已验证发布身份后，只在复制前执行路径、普通文件、文件集合、顺序和精确大小等低成本门控；将 RAR 复制到目标目录同卷 staging 后，HashMyFiles 对待发布副本计算案件所选算法。Repository 返回路径无关的结构化结果，Service 按文件名把每行摘要和大小与 Manifest 逐项等值比较，全部一致后才发布 Word、RAR 和 PNG。

**理由**：HashMyFiles 已经必须完整读取最终副本以生成业务要求的截图。让这次读取同时承担统一导出的内容安全门，可以删除“先固定 MD5 全量读取、再复制、再 HashMyFiles”的冗余读取；校验对象也更接近最终交付物。

**安全边界**：

- 源 RAR 在复制前或复制期间被替换，最终 staging 副本摘要将与 Manifest 不一致，导出失败。
- HashMyFiles 行缺失、重复、多出、算法列错误、摘要格式错误或等值比较失败，均不得进入发布。
- Word 和 RAR 即使已在 staging 生成，失败时也只删除 staging，上一版正式导出保持完整。
- 单独 Word、下载、复用和恢复没有 HashMyFiles 最终副本复核，继续在各自授权边界使用所选算法执行内容验证。

**备选方案及拒绝理由**：

- 保留统一导出前全量哈希：安全但重复读取源 RAR，且 HashMyFiles 结果仍未形成闭环，拒绝。
- 复制时由 Python 同时计算、之后再运行 HashMyFiles：可以形成双实现复核，但对同一次导出增加一次额外摘要计算；既然 HashMyFiles 已直接与持久化 Manifest 比较，本轮不采用。
- 只生成截图、不读取结构化结果：无法证明截图与 Manifest 一致，拒绝。

## D5. HashMyFiles 返回结构化、可比较的结果

**决策**：HashMyFiles Service 返回 `image_filename`、`hash_algorithm` 和 path-free rows；每行包含 `filename`、`size_bytes`、`hash_value`。截图仍只显示 Filename、所选算法和 File Size 三列。

**理由**：PowerShell 捕获脚本已经产出这些行，当前丢弃它们导致统一导出只能验证“像一个哈希”，不能验证“是 Manifest 中的哈希”。结构化返回使等值校验位于可测试的 Service 边界。

**API影响**：该结果是后端内部合同；外部统一导出响应继续只返回 PNG 文件名，不暴露摘要或绝对路径。

## D6. 非案件文件哈希保持独立

**决策**：报告缓存、来源/上下文绑定、发布记录、图片资产等内部 SHA-256 不随案件算法变化。

**理由**：这些值用于系统身份、缓存或防篡改，而不是用户选择的 RAR 文件哈希。把它们改为 MD5/SHA-1 会降低系统内部安全性，也会错误扩大案件设置的作用域。

## D7. 失败语义与可观察性

**决策**：新增稳定的 HashMyFiles 摘要不一致错误；进度阶段和用户文案使用“哈希”或案件算法名称，不再写死 MD5。审计只记录算法、验证通过状态和产物文件名，不新增绝对路径或摘要正文。

**理由**：错误必须能区分工具不可用、结果不完整和摘要与 Manifest 不一致，同时遵守仓库及审计的路径/案件数据最小化要求。

## 数据流

```text
CaseDraft.inspection.result.hash_algorithm
                 │
                 ▼
       WinRAR + rar t integrity
                 │
                 ▼
  hashlib(selected algorithm, one pass)
                 │
                 ▼
 ArchivePart.hash_algorithm/hash_value
                 │
        ┌────────┴────────┐
        ▼                 ▼
 reuse/recovery/       unified export
 download validation      │
        │                 ▼
 selected algorithm    copy to staging
                          │
                          ▼
                 HashMyFiles(selected)
                          │
                          ▼
                 exact Manifest compare
                          │
                          ▼
                    atomic publish
```

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 旧 Manifest 只有 `md5` | 单一规范化读取层和 legacy fixture 覆盖，不批量迁移 |
| 某个安全门仍硬编码 `md5` | 全仓搜索 `part.md5`、`verified_md5s`、32位正则并增加三算法同参矩阵测试 |
| HashMyFiles 格式合法但摘要错误 | 强制逐项与 Manifest 等值比较并覆盖原子回滚 |
| 复制期间源文件变化 | 校验最终 staging 副本；任何不一致均不发布 |
| MD5 本身抗碰撞较弱 | 这是用户可选算法的产品权衡；本变更不偷偷增加第二算法，建议业务优先选择 SHA-256 |
| 变更破坏恢复/下载路径 | 对复用、恢复、下载、单独 Word和统一导出分别提供自动化回归 |

## 验证策略

- Repository：三算法规范化、长度、legacy 投影、受控路径流式计算、HashMyFiles 行解析与等值比较。
- Service：三算法参数化归档矩阵；同名同大小篡改；复用、恢复、下载和发布；统一导出成功、摘要不一致和回滚。
- Shared/Frontend：可选 legacy `md5` 类型兼容及固定 MD5 文案清理。
- 人工：使用 SYNTHETIC 小文件运行真实 HashMyFiles 2.51，逐项核对 32/40/64 位摘要和 PNG 三列布局。
- 收敛后执行独立 Code Review 与 `npm run verify:full -- --change selectable-case-hash-algorithm`。
