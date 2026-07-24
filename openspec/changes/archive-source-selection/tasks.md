# Tasks: 归档来源选择与已有压缩包复用

> Spec：`openspec/changes/archive-source-selection/specs/electronic-inspection-record/spec.md`
> Design：`openspec/changes/archive-source-selection/design.md`
> Level：3
> 当前阶段：仅完成变更包文档；以下任务均未实施。

## 目标与验收标准

目标是让审核编辑页遵循“选择方式 → 显式执行”的归档流程：自动模式点击“开始压缩”，已有模式选择文件后点击“校验并使用”。用户提供模式必须通过本机可信选择、短 TTL 单次 token、同目录新式 RAR 卷集合校验、流式大小/MD5、Manifest 发布前复核和导出前复核完成；不得调用新的 WinRAR 压缩，不得泄露、复制、移动或删除用户原文件。

完成实现后必须满足：

- 报告进入审核编辑、光盘编号填写或修改、模式切换均不自动派发归档请求。
- 自动模式保持现有 WinRAR 规划/执行/验证/导出门控；用户提供模式绝不进入 WinRAR 压缩分支。
- 支持 `name.rar` 和 `name.part1.rar`…；可从任意一卷发现同目录完整集合；拒绝缺卷、重复卷、混合命名、额外同 base RAR 和 `.r00/.r01`。
- 用户提供模式公共 `ArchiveManifest` 与自动模式一致；`source_mode` 只在会话级内部运行时记录，首版不增加公共 Manifest `source` 字段。
- 文件删除返回 `part_missing`，文件大小或 MD5 变化返回 `part_changed`；正式导出前再次复核。
- 服务重启、token 过期、文件移动和清理解析缓存后均不会错误复用或删除用户原文件。
- 所有自动化测试只使用合成小文件、fake picker/fake runner 和临时目录，不提交真实路径、压缩包、Manifest、RAR、DOCX 或运行输出。

## Phase 0：契约和错误语义（Layer 0/1）

- [ ] T001 **定义归档模式和选择摘要 API 类型**
  - 文件：`packages/shared/types/archive.ts`、`packages/shared/constants/index.ts`
  - 内容：新增 `generated | user_provided` 模式、selection token 摘要、稳定错误码和请求字段；保持现有 `ArchiveManifest` 字段和结构不变，不加入 `source`。
  - 验证：`npm run typecheck`；检查请求/响应字段使用 camelCase，内部 Python 字段由 Controller 转换。

- [ ] T002 **增加 SharedTypes 合同测试和兼容断言**
  - 文件：packages/shared/types/__tests__/archive-source-selection.test.ts（新建）
  - 内容：覆盖模式枚举、用户提供请求要求 token、成功响应仍可赋值给既有 `ArchiveManifest`；断言不需要 `ArchiveManifest.source`。
  - 依赖：T001
  - 验证：`npm run typecheck`；前端和后端类型消费不引入跨层直接引用。

## Phase 1：本机选择、token 和卷集合（Backend Repository，Layer 20）

- [ ] T003 **实现 Windows 原生选择器和 token 运行时存储边界**
  - 文件：packages/backend/app/repository/archive_selection_repository.py（新建）、`packages/backend/app/repository/archive_authorization_repository.py`、`packages/backend/app/services/archive_authorization_service.py`
  - 内容：增加 Windows common file dialog 适配接口；token 使用不可逆摘要、默认不超过 5 分钟 TTL、会话/`archive_context_id` 绑定、原子单次消费；返回脱敏文件名；沿用现有授权根和 reparse point 拒绝规则；手工路径仅受开发/降级开关控制。
  - 约束：原始路径只保存在进程内受保护记录；不写日志、响应、Manifest 或自动归档索引；服务重启丢弃记录。
  - 验证：注入 fake picker，验证取消、签发、过期、跨上下文和重复消费；确认异步 HTTP 线程不会被原生选择器永久阻塞。

- [ ] T004 **测试选择器 token 和路径安全**
  - 文件：tests/test_archive_selection_repository.py（新建）、tests/test_archive_authorization_service.py
  - 内容：覆盖 token 单次消费、TTL、上下文绑定、服务重启空状态、原始路径不出响应/日志、目录/越界/UNC/设备路径/符号链接/reparse point 拒绝，以及开发降级路径仍需授权。
  - 依赖：T003
  - 验证：pytest tests/test_archive_selection_repository.py tests/test_archive_authorization_service.py；仅使用 `SYNTHETIC` 临时小文件或 fake path。

- [ ] T005 **实现同目录 RAR 卷集合发现和命名拒绝**
  - 文件：`packages/backend/app/repository/archive_validator_repository.py`、packages/backend/app/repository/archive_selection_repository.py
  - 内容：严格识别 `name.rar` 和 `name.partN.rar`；用户选择任一卷时只扫描其父目录，不递归；按数字序号排序；检测 1..M 连续、重复卷号、单卷/分卷混合、额外同 base RAR、前导零和旧式 `.r00/.r01`。
  - 内容：提供不依赖 WinRAR 的候选集合结果，错误映射到 `part_missing`、`duplicate_part`、`mixed_archive_parts`、`extra_archive_part`、`unsupported_legacy_volume_format` 等稳定错误。
  - 验证：repository 单元测试先覆盖成功单卷/连续分卷，再覆盖所有拒绝分支。

- [ ] T006 **测试合成卷集合解析**
  - 文件：tests/test_archive_provided_volume_repository.py（新建）
  - 内容：使用带 `SYNTHETIC` 标记的空或小文本文件模拟 `name.rar`、`name.part1.rar`…；覆盖从任一分卷选择、非递归边界、缺卷、重复、混合、额外同 base、旧式分卷和文件系统枚举乱序。
  - 依赖：T005
  - 验证：pytest tests/test_archive_provided_volume_repository.py；不得生成真实 RAR 内容或大文件。

## Phase 2：用户提供归档服务和运行时记录（Backend Services，Layer 21）

- [ ] T007 **实现用户提供归档选择和校验服务**
  - 文件：packages/backend/app/services/archive_provided_selection_service.py（新建）、packages/backend/app/services/archive_provided_archive_service.py（新建）
  - 内容：编排 picker/token、卷集合发现、路径授权、逐卷存在性/普通文件/可读性/reparse point 检查；以有界内存流式计算每卷大小和 MD5；不解压、不逐文件比对、不复制原文件；明确禁止调用 WinRAR 压缩执行器。
  - 内容：复用现有 Manifest 组装和连续性验证，但让来源读取通过内部 path resolver；在发布前再次 stat；成功输出与自动模式相同的 `parts[]` 字段。
  - 验证：服务测试注入 fake picker、fake hash/reader 和 fake WinRAR capability，确认用户提供模式即使能力存在也不调用压缩执行器。

- [ ] T008 **测试用户提供归档清单生成**
  - 文件：tests/test_archive_provided_archive_service.py（新建）
  - 内容：覆盖单卷、连续分卷、每卷 filename/size/MD5/part_number，以及 `disc_number`、`disc_date`、`disc_capacity_bytes` 映射；覆盖不可读、删除、读取中变化、发布前 stat 变化和可选 `t` 测试不作为前置条件。
  - 依赖：T007
  - 验证：pytest tests/test_archive_provided_archive_service.py；使用合成小文件和 fake runner，不调用真实 WinRAR。

- [ ] T009 **扩展运行时 Manifest 记录以保存来源但隔离原路径**
  - 文件：`packages/backend/app/services/archive_runtime_models_service.py`、`packages/backend/app/services/archive_manifest_service.py`、`packages/backend/app/repository/archive_manifest_repository.py`
  - 内容：为运行时记录增加 `source_mode`、内部 `source_record_id`、受保护 part path resolver 和 `user_owned_no_delete` 清理策略；用户提供记录只存在会话内，不写自动归档持久化复用索引；公共 `ArchiveManifest` 序列化结果保持不变。
  - 内容：确保新用户提供 Manifest 使用新的 manifest ID，不覆盖仍有效的正式 Manifest；生成归档继续使用现有持久化注册表和系统拥有输出目录。
  - 验证：静态检查公共类型未新增 `source`；运行时记录序列化/清理测试确认原路径不出合同且用户文件不被删除。

- [ ] T010 **实现来源感知的正式导出复核**
  - 文件：`packages/backend/app/services/archive_manifest_access_service.py`、`packages/backend/app/services/archive_runtime_service.py`
  - 内容：用户提供来源在导出前重新 stat、读取并验证大小和 MD5；缺失返回 `part_missing`，变化返回 `part_changed`；不再要求用户提供压缩包内容匹配报告目录，但仍保留当前上下文、权限和 Manifest 权威校验。清理只删除系统所有目录。
  - 验证：为生成来源和用户来源分别验证导出门控，确认旧有效 Manifest 在新尝试失败时仍可追溯且未被半成品覆盖。

- [ ] T011 **测试运行时生命周期和导出前复核**
  - 文件：`tests/test_archive_manifest_authority.py`、`tests/test_archive_runtime_service.py`、tests/test_archive_provided_manifest_access.py（新建）
  - 内容：覆盖服务重启/token 过期/文件移动要求重新选择、缓存清空不删除原文件、文件删除/大小变化/MD5 变化阻止导出、用户来源不进入自动索引、旧有效 Manifest 不被覆盖。
  - 依赖：T009、T010
  - 验证：pytest tests/test_archive_manifest_authority.py tests/test_archive_runtime_service.py tests/test_archive_provided_manifest_access.py。

## Phase 3：Controller API 和自动分支隔离（Layer 22/23）

- [ ] T012 **增加选择接口并显式分发归档模式**
  - 文件：`packages/backend/app/controllers/archive_controller.py`
  - 内容：增加 `POST /records/archive/selections/pick`；扩展现有归档执行请求读取 `archive_mode` 和 `selection_token`；`generated` 只进入现有 `execute_archive`，`user_provided` 只进入用户提供服务；错误统一转换为脱敏稳定错误码。
  - 内容：拒绝缺少模式、用户提供模式缺 token、自动模式携带 token、无效上下文和重复提交；成功响应继续返回公共 Manifest。
  - 验证：Controller 集成测试断言两条分支的调用边界和错误响应，不写入原路径。

- [ ] T013 **测试 API token 和 WinRAR 分支隔离**
  - 文件：tests/test_archive_controller.py（新建）、`tests/test_record_controller.py`、`tests/test_archive_execution_service.py`
  - 内容：覆盖选择取消/不可用/token 无效/过期、用户提供成功和失败、用户提供模式不调用 WinRAR 压缩、自动模式仍调用原 executor、公共 Manifest 响应结构兼容。
  - 依赖：T012
  - 验证：pytest tests/test_archive_controller.py tests/test_record_controller.py tests/test_archive_execution_service.py。

## Phase 4：Frontend Hook 和归档区交互（Layer 10/11）

- [ ] T014 **将 `useArchivePreparation` 改为显式状态机**
  - 文件：`packages/frontend/src/hooks/useArchivePreparation.ts`
  - 内容：移除报告/光盘编号变化触发归档的 effect；提供选择模式、打开文件选择器、保存 token、`prepareGenerated`、`prepareProvided`、取消/废弃 attempt、重新准备确认和导出前状态查询；使用 attempt ID/AbortController 丢弃迟到响应。
  - 内容：未选择模式、仅修改光盘编号和切换模式均不派发归档；成功结果投影仍来自公共 Manifest，不读取用户路径或 `rar_info`。
  - 验证：先用测试证明旧自动 effect 不再发送请求，再实现显式按钮调用。

- [ ] T015 **补充 Hook 状态机测试**
  - 文件：`packages/frontend/src/hooks/useArchivePreparation.test.tsx`
  - 内容：覆盖初始 idle 无请求、模式选择无请求、自动模式点击后请求、用户提供选择/校验后请求、用户提供分支不调用压缩 API、光盘编号修改无请求、切换模式废弃旧 attempt、迟到响应隔离、有效 Manifest 不被普通切换覆盖。
  - 依赖：T014
  - 验证：`npm run test:frontend -- useArchivePreparation.test.tsx` 或项目等价 Vitest 定向命令。

- [ ] T016 **增加归档方式选择和已有文件操作组件**
  - 文件：`packages/frontend/src/components/ArchiveStatusCard.tsx`、packages/frontend/src/components/ArchiveModeSelector.tsx（新建）、必要时 packages/frontend/src/components/ProvidedArchiveSelection.tsx（新建）
  - 内容：在现有归档状态区上方显示两种模式；自动模式显示“开始压缩”；用户提供模式显示“选择文件”与“校验并使用”；展示脱敏文件名、卷顺序、大小、MD5 和稳定错误；提供重新准备确认，不显示真实绝对路径。
  - 约束：不把浏览器 `File` 上传到后端、不把路径写入 DOM/日志，不改变其他附件编辑区。
  - 验证：组件测试检查按钮可用条件、错误提示、loading/取消和有效 Manifest 保护。

- [ ] T017 **测试归档区交互和可访问提示**
  - 文件：`packages/frontend/src/components/ArchiveStatusCard.test.tsx`、packages/frontend/src/components/ArchiveModeSelector.test.tsx（新建）、`packages/frontend/src/components/RecordEditorForm.test.tsx`
  - 内容：覆盖未选择、自动、已有、token 过期、缺卷/变化错误、模式切换和重新准备确认；确认页面从不渲染绝对路径。
  - 依赖：T016
  - 验证：`npm run test:frontend -- ArchiveStatusCard RecordEditorForm` 或项目等价 Vitest 定向命令。

## Phase 5：审核页接线和 Legacy Word 回归（Layer 12 / existing output）

- [ ] T018 **在审核编辑页接入显式归档状态**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`、`packages/frontend/src/components/RecordEditorForm.tsx`
  - 内容：把归档模式/attempt/active Manifest 传入归档区；报告载入后只初始化状态；移除自动准备依赖；光盘编号修改仅更新报告；导出仍以有效公共 Manifest 为唯一归档输入。
  - 约束：不修改 Legacy 解析、不改 Word 模板、VML、分页、Shadow 或 Canonical。
  - 验证：页面级测试或 Playwright 流程覆盖“进入页面 → 选择模式 → 显式执行 → 导出”。

- [ ] T019 **测试自动归档回归和竞争请求**
  - 文件：packages/frontend/src/pages/RecordGeneratePage.test.tsx（新建）、必要时现有页面测试文件
  - 内容：覆盖自动模式与现有请求/轮询/导出行为一致、用户提供模式没有自动压缩、快速切换和重复点击只保留当前 attempt、有效 Manifest 不被隐式覆盖。
  - 依赖：T018
  - 验证：前端定向测试和最小 Playwright/E2E 流程；不连接真实 WinRAR 或真实文件。

- [ ] T020 **增加 Word Manifest 字段回归测试**
  - 文件：现有 `tests/test_attachment_plan_service.py`、`tests/test_template_filler_service.py`，必要时新增 tests/fixtures/archive_source_selection_manifest.py
  - 内容：使用同一份合成公共 Manifest 分别标记自动/用户来源，断言 Word 附件计划继续按 `filename`、`size_bytes`、`md5`、`part_number`、`disc_number`、`disc_date`、`disc_capacity_bytes` 顺序读取；不修改模板、VML、分页和主渲染实现。
  - 依赖：T009、T018
  - 验证：pytest tests/test_attachment_plan_service.py tests/test_template_filler_service.py；不提交 DOCX 输出。

## Phase 6：Level 3 门控和发布前检查

- [ ] T021 **运行定向架构、类型、文档和测试门控**
  - 文件：无生产文件；核对本变更全部任务和测试证据
  - 内容：确认新增依赖遵循 SharedTypes → FE Hooks → Components → Pages、Repository → Services → Controller → Routes；确认文件行数、命名导出、错误码和路径脱敏规则符合 `harness/architecture.md`。
  - 验证：`npm run lint:arch`、`npm run typecheck`、后端/前端定向测试、`npm run check-docs`、`git diff --check`；Level 3 实施完成后再由人类决定是否运行完整 Harness 门控。

- [ ] T022 **独立安全和合同审查**
  - 文件：`openspec/changes/archive-source-selection/proposal.md`、`openspec/changes/archive-source-selection/specs/electronic-inspection-record/spec.md`、`openspec/changes/archive-source-selection/design.md`、本 `tasks.md`
  - 内容：审查 token 是否单次/短 TTL/绑定上下文，原路径是否只在后端内存，清理是否永不触碰用户文件，自动/用户提供分支是否严格隔离，公共 `ArchiveManifest` 是否未被无必要扩展，Word/Legacy/Shadow/Canonical 边界是否保持。
  - 依赖：T001–T021
  - 验证：Level 3 独立 Code Review Agent；按审查结果补充任务，不以“文档存在”替代实现测试。

- [ ] T023 **归档变更包并回写迭代记录**
  - 文件：实现完成后的 Harness 归档路径和迭代记录（本轮不创建）
  - 内容：只有实现、完整 verify、独立 review、人工 Word/本机选择器验收和发布负责人确认均完成后，才执行归档；本轮保持变更包为 `PROPOSED`，不提交、不推送。
  - 依赖：T021、T022
  - 验证：按 Level 3 archive 流程执行，不能在本轮提前勾选完成。

## 实施批次建议

1. **Batch A：契约和后端安全基础**：T001–T006，先使选择器、token、路径授权和卷解析可单测。
2. **Batch B：用户提供归档和导出复核**：T007–T013，完成 Manifest 兼容、来源隔离和 Controller 分支门控。
3. **Batch C：前端显式流程**：T014–T019，切断自动 effect，接入选择/校验按钮和 attempt 竞争保护。
4. **Batch D：Word 回归与 Level 3 门控**：T020–T023，确认输出合同未变，再进行完整 verify/review/archive。

若 Batch A 证明当前后端部署没有交互式 Windows 桌面，应暂停实现并单独评估桌面桥接；在该结论前不得扩大为浏览器上传或完整桌面应用。
