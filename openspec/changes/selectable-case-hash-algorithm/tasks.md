# 新案件可选择笔录哈希算法

workflow_level: 3
spec_sync_status: pending
spec_sync_evidence: 2026-08-25 用户审计反馈将正式合同从“固定内部 MD5 + 可选业务哈希”纠正为“三算法同链、只使用案件所选文件哈希”；delta 已更新，待实现、Review 与 living spec 同步

> 规格：
> - `openspec/changes/selectable-case-hash-algorithm/specs/electronic-inspection-record/spec.md`
> - `openspec/changes/selectable-case-hash-algorithm/specs/data-model/spec.md`
> - `openspec/changes/selectable-case-hash-algorithm/proposal.md`
> - `openspec/changes/selectable-case-hash-algorithm/design.md`

## 关联与级别

- 级别：由 Level 2 升为 Level 3。用户审计反馈修改持久化 Manifest 及归档复用、恢复、下载、发布安全边界，要求移除新归档固定 MD5，并让三算法共用唯一哈希事实源，属于核心链路和安全模型调整。
- 主归属继续复用本包：本包完成但尚未归档，本次反馈直接推翻原验收范围中的“双哈希”设计，按冻结前反馈重开，不创建重复 change。
- `centralize-shared-default-settings` 是强关联候选，但其七项集中管理目标已完成；本次新增第八项正式设置并扩展归档链路，创建独立变更包。
- `background-compression-archive-completion` 是强关联候选，提供 Manifest、后台归档和统一导出底座；任务仍归本包，实施时只核对并消除该包及 living spec 中固定 MD5 的冲突表述，不复制任务。
- `metadata-fingerprint-archive-path` 是相关候选，其路径、稳定身份和同大小篡改防护继续复用；固定 MD5 结论由本包的新所选算法合同取代，非案件文件元数据/上下文指纹保持不变。

## 目标行为

- “笔录默认设置”提供“文件哈希算法”单选，候选固定为 MD5、SHA-1、SHA-256，默认 MD5，不能为空。
- 设置只影响之后新建的案件；新案件将算法快照写入 `inspection.result.hash_algorithm`，旧案件和缺失字段的存量数据按 MD5 兼容。
- 新归档分卷只持久化案件选择的 `hash_algorithm` 与 `hash_value`；MD5、SHA-1、SHA-256 经过相同链路，SHA 案件不得额外计算固定 MD5。
- 审核界面、检查结果、附件1列标题、提取方式文案、Word正文与附件3文件哈希值使用案件快照对应的算法名称和值；legacy 字段键 `md5_hash` 保留作模板兼容载体，但其值代表当前案件选择的业务哈希。
- 统一导出把 Manifest 绑定算法传给 HashMyFiles，只启用对应算法，读取 Filename、所选算法、File Size 三列，并把结构化摘要与 Manifest `hash_value` 逐项等值比较。
- 统一导出不再在复制前固定 MD5 全量重算；HashMyFiles 对 staging 最终副本的等值比较承担本次内容门控，保持原子失败回滚。
- 设置变更不回写旧案件，不批量修改既有 Manifest；缺失 `hash_algorithm/hash_value` 且含合法 `md5` 的旧 Manifest 继续按 MD5 规范化读取。
- 报告缓存、上下文绑定、发布摘要和图片资产等非案件文件哈希继续使用各自既有算法，不受案件设置影响。

## 验收标准

- [x] 设置页正确展示 MD5、SHA-1、SHA-256，默认 MD5，保存时写入共享默认值 revision 合同。
- [x] 新案件快照所选算法，旧案件和缺失字段按 MD5；修改设置不改变已创建案件。
- [ ] MD5、SHA-1、SHA-256 新归档均只计算所选算法，分别生成 32/40/64 位摘要，调用阶段、状态、Manifest 结构和错误行为一致。
- [x] 审核界面、附件1、检查结果、提取方式、Word正文和附件3使用正确算法名称和值。
- [ ] HashMyFiles 参数、结果列读取、长度校验和截图列宽随案件算法变化，结构化摘要与 Manifest 逐项完全一致，仍只展示三列。
- [ ] 无效算法、结果列缺失/重复、摘要长度错误或摘要不一致稳定失败，不产生混合导出包。
- [ ] 旧 MD5 Manifest 可兼容读取；新 Manifest 不依赖 `md5`；复用、恢复、下载和发布安全门按所选算法拒绝同大小内容篡改。
- [ ] 冻结候选后完成独立 Review、`npm run verify:full -- --change selectable-case-hash-algorithm`、真实 HashMyFiles 验收、资产与 diff 检查。

## 任务列表

### Layer 0 — 共享合同

- [x] 修改 `packages/shared/types/workbench.ts`、`packages/shared/types/index.ts` 和 `packages/shared/types/archive.ts`：新增 `HashAlgorithm`、共享默认算法、案件算法快照与 Manifest 业务哈希字段；保留 legacy MD5 字段兼容。
  - 验证：前端和 shared typecheck；现有测试 fixture 补齐或验证可选兼容字段。

### Layer 20 — 持久化与 HashMyFiles

- [x] 修改 `packages/backend/app/repository/case/shared_defaults_repository.py`：默认 `md5`，只接受 `md5`/`sha1`/`sha256`，显式设置不得清空。
  - 验证：扩展 `tests/test_case_shared_defaults.py` 的默认值、合法更新和非法值拒绝。
- [x] 修改 `packages/backend/app/repository/archive/archive_hash_repository.py` 与 `packages/backend/app/repository/integrity/hashmyfiles_repository.py`：提供受控业务摘要计算；按算法生成 HashMyFiles 参数、列索引、摘要校验和三列截图。
  - 验证：扩展 `tests/test_hashmyfiles_service.py`，覆盖三种算法、错误长度、参数与列选择。

### Layer 21 — 案件、归档与文书投影

- [x] 修改 `packages/backend/app/services/case/case_draft_service.py` 和 legacy 规范化链路：新案件写入默认算法快照，存量案件缺失时投影为 MD5。
  - 验证：扩展 `tests/test_case_shared_defaults.py` 与工作台详情测试，区分新案快照和旧案兼容。
- [x] 修改 `archive_manifest_service.py`、`archive_execution_service.py` 及 Manifest 校验/投影：保留内部 MD5，生成并消费所选业务哈希。
  - 验证：扩展归档 Manifest、执行与完成投影测试，断言 MD5 安全门不变且 SHA 摘要正确。
- [x] 修改附件计划、审核投影和 Word 生成相关服务：动态输出算法名称和值，legacy `md5_hash` 键只作为兼容载体。
  - 验证：复用附件计划、document builder、template filler 和 Word 定向测试，覆盖 SHA-1/SHA-256 文案与值。
- [x] 修改 `packages/backend/app/services/integrity/hashmyfiles_service.py`、`packages/backend/app/services/export/unified_export_service.py` 及导出接线：从案件快照传递算法，生成匹配截图且维持原子发布。
  - 验证：扩展 HashMyFiles 与统一导出测试，覆盖三算法和失败回滚。

### Layer 10/11 — 设置与审核界面

- [x] 修改 `useSharedDefaultsSettings.ts` 与测试：加载/保存 `hash_algorithm`。
  - 验证：Hook 测试覆盖 MD5 默认值和 SHA-1/SHA-256 序列化。
- [x] 修改 `SharedDefaultsSettingsForm.tsx` 与测试：新增“文件哈希算法”选择器和“只影响之后新建案件”的说明，沿用现有设置页视觉与响应式合同。
  - 验证：组件测试覆盖候选、选择、保存、可访问名称；桌面/窄屏视觉检查与 Impeccable detector。
- [x] 修改审核结果与附件编辑组件：根据案件快照显示动态算法标签和提取方式，旧案显示 MD5。
  - 验证：更新现有组件测试，覆盖 SHA-1/SHA-256 标签、大写值和 legacy MD5。

### 文档同步与门控

- [x] 核对 delta 与实现，sync `openspec/specs/electronic-inspection-record/spec.md` 和 `openspec/specs/data-model.md`，将 `spec_sync_status` 更新为 `reconciled` 并记录证据。
- [x] 运行受影响前后端测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change selectable-case-hash-algorithm` 和 scoped `git diff --check`。
- [x] 完成设置页桌面/窄屏验收和独立界面复核；真实 HashMyFiles.exe 已用 SYNTHETIC/TEST 小文件完成 MD5、SHA-1、SHA-256 三算法原生截图验收。

### 反馈修正（2026-08-24）

- [x] 按摘要长度扩展 HashMyFiles 哈希列和截图窗口，确保 SHA-1、SHA-256 摘要不以省略号截断，同时保持 Filename、所选算法、File Size 三列。验证：Repository 定向测试区分三种算法的列宽与窗口宽度，并核对原生截图脚本使用动态值。
- [x] 核对 delta 与实现，sync living spec，运行受影响测试、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。

### 反馈修正验证证据（2026-08-24）

- HashMyFiles Repository/Service 定向测试：`19 passed`；受影响的 Word、环境和 HashMyFiles 四个测试文件合计 `65 passed`。
- `npm run verify:quick` 与 scoped `git diff --check` 通过；scoped strict docs 在任务勾选前仅报告本反馈任务未完成，勾选后复跑通过。
- 真实 HashMyFiles 2.51 使用 `SYNTHETIC` 测试文件生成 SHA-1、SHA-256 原生 PNG；40 位与 64 位摘要均完整显示且无省略号，截图保持三列。

### 反馈修正 — 附件3长哈希换行（2026-08-24）

- [x] 仅为附件3各页的“文件哈希”段落启用西文字符级换行，使 SHA-1、SHA-256 完整摘要在 VML 文本框内自然折行，不改变相邻元数据段落。验证：真实模板生成的 SHA-256 多页 DOCX XML 中，哈希段落设置 `w:wordWrap w:val="off"`，其他段落不设置。
- [x] 运行附件 DOCX 与 officecli 要求的定向验证、`npm run pre-commit`、scoped strict docs 和 `git diff --check`，并校验真实 DOCX 包。

### 附件3长哈希换行验证证据（2026-08-24）

- 附件 DOCX 完整回归 `33 passed`，officecli 要求的 document builder 回归 `16 passed`；失败先行用例由缺少 `w:wordWrap` 转为通过。
- 真实模板生成两页 SHA-256 附件3，officecli `validate` 无错误、原生 Word 渲染共 6 页；第 5、6 页的 64 位摘要均在哈希段落内自然折行，相邻元数据布局未改变。
- `npm run pre-commit` 通过，包含架构、类型、治理文档和仓库资产检查；scoped strict docs 与 `git diff --check` 复跑通过。

## 审计反馈重开 — 三算法同链与重复计算治理（2026-08-25）

> 本节任务推翻原实现中“新 Manifest 固定内部 MD5 + 可选业务摘要”的设计。上方已完成项保留为历史实现证据，不表示双哈希合同继续有效。

### Layer 0 — 新旧 Manifest 共享合同

- [ ] 修改 `packages/shared/types/archive.ts`、`packages/shared/types/index.ts`：把 `hash_algorithm/hash_value` 定义为新 `ArchivePart` 的正式哈希合同，将 `md5` 限定为旧 Manifest 兼容输入；外部工作台结果继续投影所选算法和值，不新增固定 MD5 要求。
  - 验证：运行 shared、frontend typecheck；更新现有 Manifest fixture，分别覆盖新三算法结构与 legacy `{md5}` 结构。

### Layer 20 — 规范哈希、存量兼容与 HashMyFiles 结果

- [ ] 修改 `packages/backend/app/repository/integrity/hash_algorithm_repository.py` 与 `archive_hash_repository.py`：提供唯一的 part 哈希规范化、legacy MD5 单向投影、算法/长度校验和受控路径流式计算；删除新链路对固定 `md5`、32 位正则和 `verified_md5s` 的依赖。
  - 验证：扩展现有 Repository/Manifest 测试，参数化覆盖 MD5/SHA-1/SHA-256、无效长度、混用算法、新字段无效不得回退、旧 MD5 可兼容；通过可注入 reader/hasher 证明 SHA 案件只计算所选算法。
- [ ] 修改 `packages/backend/app/repository/integrity/hashmyfiles_result_repository.py`、`packages/backend/app/repository/integrity/hashmyfiles_repository.py` 与 `packages/backend/app/repository/integrity/hashmyfiles_capture_script.py`：保留 path-free rows，返回算法、文件名、精确字节数和完整摘要；按文件名拒绝缺失、重复、多出或错误算法列。
  - 验证：扩展 `tests/test_hashmyfiles_service.py`，覆盖三算法结构化结果、32/40/64 位摘要、重复行和列错误；测试数据全部标记 SYNTHETIC/TEST。
- [ ] 修改 `packages/backend/app/repository/archive/archive_report_metadata_repository.py` 及直接读取 Manifest 哈希的 Repository：统一通过规范 part 哈希投影 legacy `md5_hash`，禁止从兼容键名推断算法。
  - 验证：复用归档完成草稿回填测试，覆盖新 SHA Manifest、旧 MD5 Manifest 和混合算法拒绝。

### Layer 21 — 归档、所有安全门与统一导出

- [ ] 修改 `packages/backend/app/services/archive/archive_manifest_service.py`、`archive_execution_service.py`：WinRAR 完整性通过后，每个 RAR 只流式计算案件所选算法并写入 `hash_algorithm/hash_value`；发布 CAS 重试复用已计算摘要，新 Manifest 不再写固定 `md5`。
  - 验证：扩展 `tests/test_archive_execution_service.py`、`tests/test_archive_execution_milestones.py` 与 Manifest 测试，三算法使用同一状态序列和结构；SHA-1/SHA-256 不调用 MD5；发布重试不重复读取。
- [ ] 修改 `packages/backend/app/services/archive/archive_manifest_access_service.py`、`archive_task_result_service.py`、`archive_manifest_reuse_service.py`、`archive_attempt_completion_service.py`、`archive_publish_service.py` 及其持久化恢复调用链：复用、恢复、结果授权、下载和发布全部按规范 `hash_algorithm/hash_value` 校验；归档复用指纹显式绑定算法。
  - 验证：扩展 `tests/test_archive_manifest_authority.py`、`tests/test_archive_manifest_repository.py` 及现有恢复/下载测试，三算法均拒绝同名同大小内容篡改，旧 MD5 Manifest 继续可用，算法改变不得复用。
- [ ] 修改 `packages/backend/app/services/integrity/hashmyfiles_service.py` 与 `packages/backend/app/services/export/unified_export_service.py`：统一导出复制前只执行发布身份、受控路径、普通文件、集合、顺序和精确大小门控；HashMyFiles 对 staging 副本计算所选算法后，与 Manifest 按文件名逐项比较摘要和大小，再进入原子发布。
  - 验证：扩展 `tests/test_unified_export_service.py` 与 `tests/test_hashmyfiles_service.py`，覆盖三算法成功、格式合法但摘要不同、行缺失/重复、复制期间源变化、工具失败和上一版回滚；断言统一导出不再触发固定 MD5 内容复核。
- [ ] 修改单独 Word、归档下载和其他不运行 HashMyFiles 的正式访问编排，确保它们仍在自身授权边界使用所选算法完成内容验证，不因统一导出优化而降级为仅检查大小。
  - 验证：复用对应 Word、下载、恢复测试，区分统一导出最终副本门控和非统一导出的内容授权门控。
- [ ] 修改 `packages/backend/app/services/inspection/software_policy_service.py`、归档进度模型及错误映射：把残留“固定 MD5 校验”语义改为所选文件哈希；新增稳定的 HashMyFiles 与 Manifest 摘要不一致错误，审计不记录绝对路径或摘要正文。
  - 验证：复用软件工具投影、归档任务状态和统一导出错误映射测试。

### Layer 10/11 — 状态和展示语义核对

- [ ] 搜索并修改 `packages/frontend/src/hooks/`、`packages/frontend/src/components/reviewWorkspaceTypes.ts`、`ReviewSaveStatus.tsx` 及受影响测试中的固定 MD5 状态/标签；所有用户可见算法名称来自案件快照或 Manifest，三算法交互路径不分叉。
  - 验证：运行受影响 Hook/组件测试与 frontend typecheck；纯文案位置不重复新增同义测试。

### 一致性、真实工具验收与 Level 3 门控

- [ ] 核对 `background-compression-archive-completion` 相关 delta、`openspec/specs/data-model.md` 与 `openspec/specs/electronic-inspection-record/spec.md`，消除“固定内部 MD5”与新正式合同冲突；实现核对完成后 sync living specs，并把本文件 `spec_sync_status` 更新为 `reconciled`、记录证据。
  - 验证：`npm run verify:docs:strict -- --change selectable-case-hash-algorithm`。
- [ ] 使用 HashMyFiles 2.51 对 SYNTHETIC 小 RAR 分别完成 MD5、SHA-1、SHA-256 真实验收：截图保持 Filename、所选算法、File Size 三列，摘要完整显示且逐项等于 Manifest；人为注入摘要不一致时不得发布。
  - 验证：记录真实工具版本、三算法结果和失败回滚证据，不保存真实案件哈希或绝对路径。
- [ ] 必选任务与人工验收收敛后冻结候选，按 `harness/code-review-agent.md` 启动独立 Review，覆盖 Manifest 兼容、安全门无固定 MD5 遗漏、统一导出等值闭环和原子回滚；审查发现的核心修改须解冻并在下一次收敛后复审。
  - 验证：Review 无未解决阻断项。
- [ ] 冻结候选运行 `npm run verify:full -- --change selectable-case-hash-algorithm`、scoped `git diff --check` 与仓库资产检查；核对 Git diff 仅含本变更预期内容。
  - 验证：scoped full gate、资产检查和 diff 检查全部通过。

## 非目标

- 不保留新 Manifest 的第二套固定内部 MD5；案件选择的算法是 RAR 内容校验唯一事实源。
- 不回写已创建案件或既有 Manifest，不让全局设置在导出时覆盖案件快照。
- 不支持 CRC32、SHA-384、SHA-512 或自定义算法，不允许多选。
- 不重命名现有模板占位符和 legacy `md5_hash` JSON 键，不进行破坏性数据库迁移。
- 不修改报告缓存、上下文绑定、发布记录、图片资产等非案件文件哈希使用的内部 SHA-256。
- 不用 HashMyFiles 替代后台归档 `hashlib`，不把统一导出迁移为新的 durable 后台任务。
- 不归档其他变更包，不提交用户现有未提交修改。
