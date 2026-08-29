# 笔录默认设置集中管理

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: 检查要求替换提取方式的最终行为已同步到 electronic-inspection-record REQ-007 与 data-model SharedDefaults 合同

> 规格：`openspec/changes/centralize-shared-default-settings/specs/electronic-inspection-record/spec.md`

## 关联与级别

- 级别：Level 2。新增正式管理场景，并修改案件编辑更新共享默认值的既有合同；保持现有部署实例作用域、SQLite 事实源、Parser 优先级和总体架构。
- `case-shared-defaults` 是强关联候选，但其六字段持久化与新案预填目标已经完成；本次增加第七个已存在字段的集中管理页面并改变写入口，属于新的用户结果，不重开原包。
- `remove-audit-edit-template-and-defaults-display` 是强关联候选，但其目标是移除审核编辑页展示且已经完成；本次不恢复审核页展示，而是新增独立入口，不重开原包。
- `audit-edit-enhancement` 包含后来新增的委托单位前缀共享字段；本次复用其现有合同，不修改该包。

## 目标行为

- 左侧“电子数据检查笔录”子菜单在“笔录模版管理”下方提供六字入口“笔录默认设置”，路由为 `/electronic-inspection/defaults`。
- 独立页面从 `/api/v1/workbench/defaults` 读取并展示九项可配置业务默认值：委托单位前缀、文号格式、检查地点、检查方法、检查硬件设备、数据摘要、检查要求、有序检查人员和文件哈希算法；文号格式由编号前内容和编号后内容组成，不再展示或提交光盘编号前缀及附件1提取方式。
- 页面显式保存九项默认值，允许用空值清除对应默认；保存使用服务端 revision，冲突时不覆盖新值并提示重新加载。
- 检查硬件设备只能从“电子设备管理”的当前设备中下拉选择；检查人员顺序直接复用审核编辑的人员卡片、添加、删除和拖拽排序交互。
- 案件审核编辑页修改字段只保存当前案件，不再生成或提交共享默认值 patch。
- 修改只影响之后创建的新案件，不回写已有案件；检查要求按 Parser 真实值优先、共享默认值次之、系统固定值兜底初始化，附件1提取方式继续使用案件值或既有硬件与哈希算法生成逻辑，光盘完整编号生成逻辑保持不变。
- 文号格式作为新案件快照；审核编辑页对匹配该格式的案件只填写数字编号并实时形成完整文号，保留前导零；已有案件及不匹配格式的 Parser 文号继续按完整文号编辑。
- 非空数据摘要默认值在 Parser 仅返回系统固定摘要时预填后续新案件；Parser 真实非空摘要优先，已有案件不回写，空默认值继续使用既有固定摘要。
- `default_template_ref`、部署实例 ID、revision、迁移状态和更新时间只作为系统元数据，不在该页面开放编辑；模板默认版本继续由笔录模版管理维护。

## 验收标准

- [x] 导航入口名称、位置、路由与高亮正确，折叠和展开侧栏行为无回归。
- [x] 页面加载九项当前值，其中包含检查要求且不包含附件1提取方式；加载失败可重试，空状态与说明明确。
- [x] 保存单项、多项及清空值后，后端事实源按 revision 更新；未知字段仍整体拒绝。
- [x] revision 冲突不覆盖服务端值，页面提供重新加载入口；保存中避免重复提交。
- [x] 检查人员按姓名、单位、警号三段结构和显示顺序保存，非法或不完整条目不能提交。
- [x] 案件审核页修改七项字段只更新当前草稿，不携带 `shared_defaults_patch`。
- [x] 后续新案件继续按“当前案件用户修改 > Parser 真实非空值 > 非空共享默认值 > 系统默认值或空值”初始化，已有案件不变。
- [x] Level 2 定向验证、`npm run verify:quick`、scoped strict docs、资产检查与 diff 检查通过。
- [x] 检查硬件设备使用与审核编辑相同的设备下拉选择能力，选项来自“电子设备管理”，不再接受自由输入。
- [x] 检查人员使用与审核编辑相同的人员库卡片编辑器，可从“检查人员管理”添加、删除并拖拽排序，保存时保持显示顺序。
- [x] 设置页展示并保存附件1提取方式，不展示或提交光盘编号前缀；移除当前版本及指定字段下方提示。
- [x] 后续新案件固化提取方式快照，附件1预览、归档投影和正式文书优先使用该值；空值保持既有自动生成语义，已有案件不回写。
- [x] 笔录默认设置将文号改为“编号前内容 + 编号后内容”，后续新案件固化格式快照，审核编辑只填数字编号并生成完整文号；旧案件和不匹配 Parser 文号保持兼容。
- [x] 设置页展示并保存数据摘要默认值；新案件按 Parser 真实值 > 非空共享默认值 > 固定系统摘要初始化，已有案件不回写。
- [x] 设置页展示并保存检查要求默认值，不展示或提交附件1提取方式；新案件按 Parser 真实值 > 非空共享默认值 > 固定系统检查要求初始化，已有案件不回写。

## 任务列表

### Layer 20 — 后端持久化

- [x] 修改 `packages/backend/app/repository/case/shared_defaults_repository.py`，让七项用户可配置字段在显式默认值 PUT 中接受空字符串/空数组清除，同时保持未知字段拒绝、`default_template_ref` 独立和 revision CAS。
  - 验证：更新并运行 `tests/test_case_shared_defaults.py` 的稀疏更新、清空、未知字段和冲突用例。

### Layer 10 — 前端状态

- [x] 修改 `packages/frontend/src/hooks/useCaseRecordSession.ts`，停止从案件字段编辑生成共享默认值 patch，草稿保存仅提交当前案件内容。
  - 验证：更新 `packages/frontend/src/hooks/useCaseRecordSession.test.ts` 与页面集成测试，证明共享字段编辑不会提交默认值 patch。
- [x] 新增 `packages/frontend/src/hooks/useSharedDefaultsSettings.ts`，封装加载、revision 保存、冲突/错误和重新加载状态。
  - 验证：新增同目录 Hook 测试覆盖加载、保存、清空与冲突。

### Layer 11 — 前端组件与外壳

- [x] 新增 `packages/frontend/src/components/SharedDefaultsSettingsForm.tsx`，提供七项字段、检查人员有序编辑、用途说明、保存与重载交互。
  - 验证：新增同目录组件测试覆盖展示、校验、保存和可访问名称。
- [x] 修改 `packages/frontend/src/components/PlatformSidebar.tsx` 与 `packages/frontend/src/pages/platformShell.test.tsx`，增加“笔录默认设置”入口、高亮和布局回归。
  - 验证：运行平台外壳定向 Vitest。
- [x] 修改 `packages/frontend/src/platformShell.css`，复用现有平台视觉语言并补充设置页响应式布局。
  - 验证：桌面与窄屏截图检查；运行 Impeccable detector。

### Layer 12 — 页面与路由

- [x] 新增 `packages/frontend/src/pages/SharedDefaultsSettingsPage.tsx`，并修改 `packages/frontend/src/App.tsx` 接入正式路由与 `/defaults` 兼容重定向。
  - 验证：页面/路由定向测试和前端 typecheck。

### 文档同步与门控

- [x] 核对 delta 与实现，sync 到 `openspec/specs/electronic-inspection-record/spec.md`，将 `spec_sync_status` 更新为 `reconciled`。
- [x] 运行受影响前后端测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change centralize-shared-default-settings` 和 `git diff --check`，记录证据。
- [x] 完成桌面/窄屏视觉检查和独立界面复核；人工真实业务验收不在本轮自动环境内执行时记录 N/A。

### 反馈迭代 — 资源库选择器复用

- [x] 新增 `packages/frontend/src/hooks/useRecordEditorCatalogs.ts`，统一加载审核编辑与笔录默认设置使用的电子设备、检查人员资源库；修改 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 复用该 Hook。
  - 验证：运行默认设置组件与案件审核页现有定向 Vitest，确认两处请求相同资源库并保留加载/失败状态。
- [x] 新增 `packages/frontend/src/components/HardwareDeviceSelect.tsx`，并修改 `EditableField.tsx` 与 `SharedDefaultsSettingsForm.tsx`，让审核编辑和默认设置复用同一设备下拉控件。
  - 验证：组件测试证明默认设置只能选择电子设备管理返回的设备，且仍可显式清空默认值。
- [x] 修改 `SharedDefaultsSettingsForm.tsx` 与 `useSharedDefaultsSettings.ts`，移除默认设置自建的检查人员输入/上下移实现，直接接入 `InspectorEditor` 的人员库添加、删除和拖拽排序。
  - 验证：组件测试覆盖已有默认人员展示、人员库添加、删除、拖拽排序及保存顺序。
- [x] 核对 delta 与实现，sync living spec，并执行 `npm run verify:quick`、受影响前端测试、`npm run verify:docs:strict -- --change centralize-shared-default-settings`、Impeccable detector 与 `git diff --check`。

### 反馈迭代 — 附件1提取方式默认值与页面精简

- [x] 修改共享默认值合同、持久化与新案初始化：新增 `extraction_method`，将非空值固化到后续新案件附件快照；保留旧 `disc_number_prefix` 数据兼容但不再由独立设置页提交。
  - 验证：更新并运行共享默认值持久化、新案初始化及既有案件不回写测试。
- [x] 修改附件1预览与后端 Manifest 投影：案件快照非空时优先使用，空值继续按检查硬件设备和案件哈希算法生成。
  - 验证：更新并运行附件计划、归档投影与前端附件编辑回归。
- [x] 修改 `SharedDefaultsSettingsForm.tsx` 与 Hook：新增“提取方式”，移除“光盘编号前缀”、当前版本、案件基础信息说明、文件哈希算法说明和检查人员顺序说明。
  - 验证：组件测试覆盖字段展示、隐藏项、提示移除及保存请求；运行 Impeccable detector。
- [x] 核对 delta 与实现，sync living spec，并执行 `npm run verify:quick`、受影响模块测试、`npm run verify:docs:strict -- --change centralize-shared-default-settings` 与 `git diff --check`。

### 反馈迭代 — 文号格式与编号输入

- [x] 修改共享默认值与案件 DTO 合同：新增文号格式对象，保留完整 `document_number` 作为 Word、预览和导出事实值；旧完整文号默认字段仅用于兼容。
  - 验证：类型检查及共享默认值持久化测试覆盖格式保存、清空和非法结构拒绝。
- [x] 修改新案件初始化：非空文号格式固化为案件快照，Parser 仅返回系统默认文号时等待用户填写编号，Parser 真实文号保持优先；已有案件不回写。
  - 验证：后端测试覆盖新案快照、Parser 优先级、默认格式后续修改不影响既有案件。
- [x] 修改默认设置和审核编辑界面：设置页编辑编号前后内容并展示合成示例；匹配快照时审核页只接受数字字符串、保留前导零并提交完整文号，不匹配或无快照时回退完整文号编辑。
  - 验证：前端 Hook/组件测试覆盖保存格式、输入 `142`/`00142`、清空和旧案件回退；运行 Impeccable detector，不执行视觉检查。
- [x] 核对 delta 与实现，sync living spec，并执行 `npm run verify:quick`、受影响模块测试、`npm run verify:docs:strict -- --change centralize-shared-default-settings` 与 scoped `git diff --check`。

### 反馈迭代 — 数据摘要默认值

- [x] 修改共享默认值合同和持久化：新增可显式保存、清空的 `data_summary`，继续拒绝未知字段并保持 revision CAS。
  - 验证：共享默认值测试覆盖默认值、保存、清空和其他字段不变。
- [x] 修改新案件初始化：Parser 真实非空数据摘要优先；Parser 固定系统摘要、空值或缺失时使用非空共享默认值；共享值为空时回到固定系统摘要。
  - 验证：后端测试覆盖优先级、系统默认让位及默认值变更只影响后来新案件。
- [x] 修改默认设置 Hook 和表单，展示、保存并清空数据摘要，不改变审核编辑页的数据摘要编辑和 Word 消费字段。
  - 验证：前端 Hook/组件测试覆盖加载、提交和清空；运行 Impeccable detector，不执行视觉检查。
- [x] 核对 delta 与实现，sync living specs，并执行 `npm run verify:quick`、受影响模块测试、`npm run verify:docs:strict -- --change centralize-shared-default-settings` 与 scoped `git diff --check`。

### 反馈迭代 — 检查要求替换提取方式

- [x] 修改共享默认值合同与持久化：新增可保存、清空的 `inspection_requirement`；保留旧 `extraction_method` 数据读取兼容，但独立设置页不再展示或提交该字段。
  - 验证：共享默认值持久化测试覆盖检查要求的默认值、保存、清空与未知字段拒绝。
- [x] 修改新案件初始化：Parser 真实非空检查要求优先；Parser 固定系统检查要求、空值或缺失时使用非空共享默认值；共享值为空时回到固定系统检查要求。附件1提取方式不再读取共享默认值。
  - 验证：后端测试覆盖检查要求优先级、已有案件不回写，以及遗留提取方式默认值不再影响新案件。
- [x] 修改默认设置 Hook 与表单：用“检查要求”替换“提取方式”，保存请求包含 `inspection_requirement` 且不包含 `extraction_method`。
  - 验证：前端 Hook/组件测试覆盖加载、提交、清空、字段可访问名称及提取方式隐藏；运行 Impeccable detector。
- [x] 核对 delta 与实现，sync living specs，并执行 `npm run verify:quick`、受影响模块测试、`npm run verify:docs:strict -- --change centralize-shared-default-settings` 与 scoped `git diff --check`。

## 验证证据

- 前端定向 Vitest：49 项通过；界面复核修正后 Hook/表单 5 项通过。
- 后端定向 Pytest：52 项通过；仅有既存 `ARCHIVE_CONFIGURED_ROOT_INVALID` 测试环境警告。
- `npm run verify:quick`：通过，包含架构、类型、文档、治理测试与仓库资产检查。
- 本次变更文件 scoped `git diff --check` 与新增文件尾随空白扫描：通过。全局命令仅命中用户既存 `AGENTS.md` 末尾空行，未修改该文件。
- 桌面展开侧栏实测 `body scrollWidth/clientWidth = 1440/1440`、`main = 1185/1185`；窄屏折叠侧栏实测 `body = 420/420`、`main = 325/325`。
- 独立 Impeccable 交付复核：无剩余 P0/P1，结论可交付。
- 人工真实业务数据验收：N/A；自动浏览器使用 `SYNTHETIC-VISUAL-DOC` 与临时部署数据完成加载、保存和 revision 递增验证。
- 本轮反馈前端定向 Vitest：6 个测试文件、55 项通过，覆盖默认设备选择、人员库添加/删除/拖拽排序、保存顺序及审核页回归。
- 本轮 `npm run verify:quick`：通过；架构、共享/前端类型、治理、文档与仓库资产检查全部通过。
- 本轮 `npm run verify:docs:strict -- --change centralize-shared-default-settings`：通过，14 项检查、0 drift。
- 本轮 scoped `git diff --check` 与新增文件尾随空白检查：通过；全局检查仅命中用户既存 `AGENTS.md:116` 文件末空行，未修改该文件。
- 本轮视觉验收：按用户明确要求不执行；Impeccable 静态检测仅报告 `platformShell.css:67` 的既存布局动画警告，本次未引入新的检测项。
- 本轮反馈前端定向 Vitest：2 个测试文件、6 项通过；后端定向 Pytest：3 个测试文件、63 项通过。
- 本轮 `npm run verify:quick`：通过；架构、共享/前端类型、治理、文档和仓库资产检查全部通过。
- 本轮 Impeccable detector：本次两个界面目标 0 项发现；人工真实业务数据验收 N/A。
- 本轮 scoped strict docs 与 scoped `git diff --check`：通过；全局 diff 检查仅命中用户既存 `AGENTS.md:116` 文件末空行。
- 文号格式反馈定向验证：前端 4 个文件 39 项通过；后端共享默认值、新案初始化和草稿合同 17 项通过；typecheck 与架构检查通过。
- 文号格式反馈门控：`npm run verify:quick` 通过；scoped strict docs 14 项、0 drift；scoped `git diff --check` 通过。
- 文号格式反馈界面检查：Impeccable detector 仅报告两个样式文件中的 3 项既存告警，本次新增组件与样式无新增发现；按用户要求不执行视觉检查。
- 数据摘要反馈定向验证：前端 Hook/表单 2 个测试文件、7 项通过；后端共享默认值与新案初始化 17 项通过；typecheck 通过。
- 数据摘要反馈界面检查：Impeccable detector 0 项发现；按用户要求不执行视觉检查。
- 数据摘要反馈门控：`npm run verify:quick` 通过；scoped strict docs 14 项、0 drift；scoped `git diff --check` 通过。
- 检查要求反馈定向验证：前端 Hook/表单 2 个测试文件、7 项通过；后端共享默认值与新案初始化 17 项通过；Python 编译检查与前端 typecheck 通过。
- 检查要求反馈界面检查：Impeccable detector 0 项发现；字段沿用现有表单布局，无新增视觉结构，人工真实业务数据验收 N/A。
- 检查要求反馈门控：`npm run verify:quick` 通过；scoped strict docs 14 项、0 drift；living specs 已同步；scoped `git diff --check` 通过。

## 非目标

- 除文号格式、数据摘要和检查要求外不新增共享默认值字段，不把案件、来源、附件、路径、归档或运行时状态纳入默认值。
- 不修改笔录模板默认版本的管理入口，不开放 `default_template_ref` 编辑。
- 不修改 Parser、Word/VML、分页、Manifest、RAR 或完整光盘编号生成合同。
- 不建立用户账户或多用户权限体系；继续使用部署实例/本地操作者作用域。
- 不回写任何已有案件，不归档其他变更包，不 commit、不 push。
