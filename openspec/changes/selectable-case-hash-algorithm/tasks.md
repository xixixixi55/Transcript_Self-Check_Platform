# 新案件可选择笔录哈希算法

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: openspec/specs/electronic-inspection-record/spec.md REQ-007/REQ-015 与统一导出场景、openspec/specs/data-model.md HashAlgorithm/InspectionResult/ArchiveManifest 已同步

> Specs:
> - `openspec/changes/selectable-case-hash-algorithm/specs/electronic-inspection-record/spec.md`
> - `openspec/changes/selectable-case-hash-algorithm/specs/data-model/spec.md`

## 关联与级别

- 级别：Level 2。新增共享默认值字段并修改案件、归档业务摘要、Word/附件投影和 HashMyFiles 截图的正式合同；沿用现有 JSON 默认值存储、案件草稿、ArchiveManifest、统一导出和平台页面架构。
- `centralize-shared-default-settings` 是强关联候选，但其七项集中管理目标已完成；本次新增第八项正式设置并扩展归档链路，创建独立变更包。
- `background-compression-archive-completion` 是强关联候选，但其固定 MD5 与三列截图目标已完成；本次复用链路并新增可选业务哈希，不重开原包。
- `metadata-fingerprint-archive-path` 只约束内部归档完整性 MD5 和性能；本次明确保留该安全合同，不重开原包。

## 目标行为

- “笔录默认设置”提供“文件哈希算法”单选，候选固定为 MD5、SHA-1、SHA-256，默认 MD5，不能为空。
- 设置只影响之后新建的案件；新案件将算法快照写入 `inspection.result.hash_algorithm`，旧案件和缺失字段的存量数据按 MD5 兼容。
- 每个归档分卷继续持久化内部完整性 `md5`，同时持久化案件选择的 `hash_algorithm` 与 `hash_value`；选择 MD5 时复用内部 MD5，选择 SHA-1/SHA-256 时额外流式计算一次业务摘要。
- 审核界面、检查结果、附件1列标题、提取方式文案、Word正文与附件3文件哈希值使用案件快照对应的算法名称和值；legacy 字段键 `md5_hash` 保留作模板兼容载体，但其值代表当前案件选择的业务哈希。
- 统一导出把案件算法传给 HashMyFiles，只启用对应算法，读取和校验对应列，并截取 Filename、所选算法、File Size 三列；不得误截 MD5 列或接受长度不匹配的摘要。
- 设置变更不回写旧案件，不修改既有 Manifest；缺失 `hash_algorithm/hash_value` 的旧 Manifest 继续按 `md5` 解释。

## 验收标准

- [x] 设置页正确展示 MD5、SHA-1、SHA-256，默认 MD5，保存时写入共享默认值 revision 合同。
- [x] 新案件快照所选算法，旧案件和缺失字段按 MD5；修改设置不改变已创建案件。
- [x] SHA-1/SHA-256 归档保留内部 MD5，并生成长度分别为 40/64 的业务哈希；MD5 不重复读取归档文件。
- [x] 审核界面、附件1、检查结果、提取方式、Word正文和附件3使用正确算法名称和值。
- [x] HashMyFiles 参数、结果列读取、长度校验和截图列宽随案件算法变化，仍只展示三列。
- [x] 无效算法、结果列缺失或摘要长度错误稳定失败，不产生混合导出包。
- [x] Level 2 定向测试、`verify:quick`、scoped strict docs、资产与 diff 检查通过。

## 任务列表

### Layer 0 — 共享合同

- [x] 修改 `packages/shared/types/workbench.ts`、`packages/shared/types/index.ts` 和 `packages/shared/types/archive.ts`：新增 `HashAlgorithm`、共享默认算法、案件算法快照与 Manifest 业务哈希字段；保留 legacy MD5 字段兼容。
  - 验证：前端和 shared typecheck；现有测试 fixture 补齐或验证可选兼容字段。

### Layer 20 — 持久化与 HashMyFiles

- [x] 修改 `packages/backend/app/repository/shared_defaults_repository.py`：默认 `md5`，只接受 `md5`/`sha1`/`sha256`，显式设置不得清空。
  - 验证：扩展 `tests/test_case_shared_defaults.py` 的默认值、合法更新和非法值拒绝。
- [x] 修改 `packages/backend/app/repository/archive_hash_repository.py` 与 `hashmyfiles_repository.py`：提供受控业务摘要计算；按算法生成 HashMyFiles 参数、列索引、摘要校验和三列截图。
  - 验证：扩展 `tests/test_hashmyfiles_service.py`，覆盖三种算法、错误长度、参数与列选择。

### Layer 21 — 案件、归档与文书投影

- [x] 修改 `packages/backend/app/services/case_draft_service.py` 和 legacy 规范化链路：新案件写入默认算法快照，存量案件缺失时投影为 MD5。
  - 验证：扩展 `tests/test_case_shared_defaults.py` 与工作台详情测试，区分新案快照和旧案兼容。
- [x] 修改 `archive_manifest_service.py`、`archive_execution_service.py` 及 Manifest 校验/投影：保留内部 MD5，生成并消费所选业务哈希。
  - 验证：扩展归档 Manifest、执行与完成投影测试，断言 MD5 安全门不变且 SHA 摘要正确。
- [x] 修改附件计划、审核投影和 Word 生成相关服务：动态输出算法名称和值，legacy `md5_hash` 键只作为兼容载体。
  - 验证：复用附件计划、document builder、template filler 和 Word 定向测试，覆盖 SHA-1/SHA-256 文案与值。
- [x] 修改 `hashmyfiles_service.py`、`unified_export_service.py` 及导出接线：从案件快照传递算法，生成匹配截图且维持原子发布。
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

## 非目标

- 不移除或替换内部 Manifest/RAR 完整性 MD5，不改变归档复用、下载和发布安全门。
- 不回写已创建案件或既有 Manifest，不让全局设置在导出时覆盖案件快照。
- 不支持 CRC32、SHA-384、SHA-512 或自定义算法，不允许多选。
- 不重命名现有模板占位符和 legacy `md5_hash` JSON 键，不进行破坏性数据库迁移。
- 不归档其他变更包，不提交用户现有未提交修改。
