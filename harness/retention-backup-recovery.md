# 阶段 5 v11 备份、恢复与应用回滚边界

> 本文是 Phase 5 的受控运维演练计划，不新增公共备份、恢复、undelete 或
> 正式产物删除 API。所有演练输入必须是 `SYNTHETIC/TEST/FIXTURE`，不得把
> 真实案件、人员信息、路径、凭据或生成产物提交到仓库。

## 1. 目标和不可混淆的边界

- 备份是一组在写入静默窗口内取得的、可由同一份清单和摘要互相校验的
  SQLite、正式文件、Word、模板、工作 assets、policy、authority 和 audit
  事实；只备份 SQLite 或只备份文件都不构成可恢复的 Phase 5 集合。
- Git/application rollback 只回滚代码和配置版本，不回滚 SQLite 行、正式文件、
  Word 文件、模板或审计事实。数据库回滚必须使用与目标应用版本匹配的成组
  数据备份；不得用 `git checkout`、`git revert` 或手工降表代替 data restore。
- 恢复默认写入隔离的 synthetic deployment。校验完成前不得把恢复目录接回
  生产 deployment，也不得启用 `enforce`、重放 cleanup 或重新认定历史
  `publication_verified_at`。
- `.archive-manifest-index.json` 是可重建的 derived index，不进入 authority
  替代关系；恢复时先验证 SQLite publication facts，再按 durable facts 重建或
  比对 index。

## 2. 成组备份清单

| 组 | 必须包含的事实 | 成功校验 |
|---|---|---|
| SQLite | v11 database、`schema_migrations`、`user_version`、deployment owner、case shell/draft/source/task、snapshot/attempt/plan/context、retention policy/record/run、audit | 记录 schema version、deployment、UTC-Z backup time；`PRAGMA integrity_check`、`foreign_key_check` 和 schema validation 均通过 |
| 正式 publication | RAR/分卷、Manifest、MD5、正式 `archive_assets`、`archive_publish_intents`、fences 和 publication generation | 每个 durable publication identity 的 file inventory、size、SHA-256、Manifest/MD5 digest 和受控相对路径互相匹配 |
| Word | `formal_word_artifacts` 与其受控文件、publication/case identity、template identity/version、Manifest digest、size、SHA-256、verified UTC | Word row、来源 publication verified authority 和物理文件摘要全部匹配；不得只按文件名恢复 |
| Template | 已批准 template identity/version、模板治理事实和被引用的受控模板文件 | approval、identity/version、文件摘要一致；不覆盖仓库中的甲方模板 |
| Work assets | 仍被任务、snapshot、plan 或 recovery 需要的 owned work/staging/cache 资产和 ownership 事实 | 逐项有 case/task/plan ownership；不把原始授权来源目录或正式 output root 当作 work asset |
| Policy/config | `case_retention_policies`、部署配置键的脱敏记录、迁移前后的 mode/revision | 恢复后 policy 默认保持 `disabled`，配置与 durable row 的来源和 revision 可解释；凭据不入备份清单 |
| Audit | cleanup、publication、Word、policy、migration、restore 演练相关 audit facts | audit 与 SQLite 同一 backup generation；缺少关键审计事实时恢复进入人工阻断 |

备份清单本身必须记录每组的 opaque identity、相对 locator、字节数、摘要、
生成时间、schema version 和 deployment identity。任何组缺失、摘要不匹配、
跨 deployment 或时间窗口不一致，都只能报告 backup invalid，不得继续 migration
或 restore。

## 3. 取得备份的受控顺序

1. 停止新请求和后台写入，等待或安全终止 archive/Word/recovery worker；确认
   没有 active cleanup claim、lease、snapshot recovery、publication update 或
   Word export。不能取得静默窗口时中止，不复制半成品。
2. 记录 deployment、当前 schema version、policy revision、各 active run 的
   安全状态摘要和 UTC-Z generation；`enforce` 在备份窗口内保持关闭。
3. 先取得 SQLite 一致副本，再取得与该 generation 绑定的正式 RAR/Manifest/MD5、
   Word、template 和 owned work asset 文件集合；对每个文件计算摘要和 size。
4. 取得 policy、authority、Word、template 和 audit 的清单后生成总 manifest；
   总 manifest 与 SQLite/publication facts 不一致时丢弃整组备份。
5. 将备份存放在仓库外的受控位置，执行读取校验后再允许应用启动。备份过程不
   改写正式文件，不删除原始来源，不生成或提交 DOCX/RAR/Manifest/MD5。

## 4. 恢复和升级演练

演练使用隔离临时 deployment 和合成 fixture，按以下顺序执行：

1. 校验总 manifest、每组摘要、相对 locator、deployment identity 和 schema
   version；任一失败立即停止。
2. 恢复 SQLite、正式输出、Word、批准模板和仍有 ownership 的 work assets，
   保持原始相对层级；恢复路径必须是新的受控根，不能指向原始来源目录、正式
   output root 或共享父目录。
3. 用 v11 应用只读打开恢复集合，确认 `PRAGMA foreign_keys=ON`、
   `integrity_check`、`foreign_key_check`、模式验证、部署所有者、
   publication/Word identity 和文件摘要均通过。
4. 从 SQLite durable publication facts 重建或验证 derived Manifest index；读取
   RAR、Manifest、MD5、Word 时必须分别经过 publication/Word authority 和摘要
   复验，不得使用 report payload、runtime context、mtime 或 index 时间补事实。
5. 确认恢复后的 policy mode 仍为 `disabled`，不存在自动 cleanup run；只有在
   负责人确认所有组完整后，才允许另行改变 policy。演练不执行真实删除。
6. 用旧应用版本尝试打开 v11 数据库，预期明确失败并保持数据库不变；不得执行
   “降级迁移”或删除 v11 表。旧应用只能打开其匹配的 v10 成组备份。
7. 保存演练摘要、命令、schema/row-count/digest 结果和失败日志到受控外部记录；
   清理隔离临时目录，确认仓库工作树没有数据库、日志、coverage 或生成文件。

## 5. 应用回滚决策

- v10→v11 migration 仍在单事务内；迁移中失败必须整体 rollback，保留可由旧
  应用读取的 v10 数据。迁移提交后发现应用问题，不通过逆向 SQL 修复，而是
  停止写入、选择匹配 generation 的 v10 成组备份恢复，并重新走 owner/FK/authority
  校验。
- v11 应用已写入 retention、publication verification 或 cleanup facts 后，不能
  通过 Git 回滚抹掉这些 durable facts；若没有匹配的可恢复 backup，进入人工
  阻断，不启动旧应用。
- 恢复只恢复已存在的 durable facts，不把文件 mtime、index 时间、下载时间或
  report JSON 推断为 publication/Word verification 时间，不自动生成
  `publication_id`、`word_artifact_id` 或 `publication_verified_at`。
- 任何正式 RAR、Manifest、MD5、Word、原始授权来源或 ownership 不明文件可能
  被覆盖、丢失或误连时，演练立即失败并停止，不以“部分恢复”作为生产通过。

## 6. 通过标准和暂停条件

演练只有在以下条件全部满足时才算 PASS：schema/owner/FK 完整；所有七组备份
摘要一致；正式 publication 与 Word 可按 durable identity 读取并复验；模板
identity/version 不漂移；policy 保持 disabled；audit 可追溯；旧应用拒绝 v11；
工作树和 synthetic 临时环境无未授权产物。

出现下列任一情况必须标记 `HUMAN ACCEPTANCE REQUIRED` 或 `BLOCKED`：需要真实
生产文件/凭据；SQLite 与正式文件 generation 不一致；需要关闭 FK；需要删除或
覆盖正式产物/原始来源；无法证明 asset ownership；旧应用未拒绝 v11；或恢复后
authority、Word、audit 事实无法闭合。不得用重试、手工改库或放宽校验将其改写为
通过。
