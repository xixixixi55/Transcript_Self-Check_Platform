# Tasks: 检查过程步骤3动态匹配本机环境

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: Windows 展示顺序已同步到 electronic-inspection-record REQ-006，并由环境服务定向测试覆盖

## 目标

新案件生成“（三）检查过程”步骤3时，以案件最终选中的检查硬件设备、本机 Windows 系统信息和本机火绒安全软件安装信息生成内容，不再写死 FL-901、Windows 10 或火绒版本。识别不到的事实显示“待确认”，不得伪造软件、版本或杀毒结论。

## 验收标准

- [x] 步骤3中的设备名称来自新案件最终选中的 `inspection.hardware_device`，为空时显示“检查硬件设备待确认”。
- [x] Windows 名称/版本、版本类型和位数从运行文枢的本机读取并形成稳定显示；读取异常时显示“操作系统信息待确认”，不得回退到写死的 Windows 10。
- [x] 自动识别本机火绒安全软件及版本；已识别软件但版本未知时显示“火绒安全软件（版本号待确认）”，未识别到火绒时显示“安全软件待确认（版本号待确认）”并把杀毒结果写为“待确认”。
- [x] 环境识别只读取本机元数据，不自动启动火绒、不执行杀毒、不声称系统已自动验证杀毒结果。
- [x] 环境快照随新案件草稿持久化，使审核编辑、自动保存和最终 Word 使用同一事实；审核页修改硬件设备时只按快照重投影步骤3，不重新探测本机环境。
- [x] 既有案件不因应用升级或本机环境变化被批量重写；缺少环境快照的旧案件仍可保留并人工编辑原步骤。
- [x] 所有测试数据使用 `SYNTHETIC`、`TEST` 或 `FIXTURE` 标记，不写入真实本机软件清单或案件信息。

## 影响范围与任务

任务按架构层级从低到高排列。

### Layer 0——共享类型

- [x] 在 `packages/shared/types/index.ts` 及必要的规范化类型中增加可选的检查环境快照契约，记录操作系统显示值、火绒名称/版本和识别状态；缺少字段的旧草稿保持兼容。验证：shared/frontend typecheck 与旧草稿 fixture 测试。

### Layer 2——共享工具

- [x] 在 `packages/shared/utils/` 增加步骤3的确定性文本投影函数，并让 `softwareProjectionUtils.ts` 在 `inspection.hardware_device` 修改时使用已保存环境快照重投影步骤3；步骤1、2、4及用户其他字段保持现状。验证：扩展 `packages/frontend/src/__tests__/softwareProjectionUtils.test.ts`，覆盖正常识别、各类“待确认”、硬件切换、旧草稿兼容与非目标步骤不变。
- [x] 移除 `packages/shared/constants/index.ts` 中写死 FL-901、Windows 10 与火绒 6.0.6.1 的步骤3常量，改由动态投影函数承担正式文本生成。验证：全仓搜索不再存在该写死完整句。

### Layer 20——后端 Repository

- [x] 新增 `packages/backend/app/repository/local_inspection_environment_repository.py`，通过可注入的 Windows 原生信息源读取系统版本/版本类型/位数，并从本机安装信息与可验证文件版本中识别火绒；非 Windows、键缺失、访问异常或值损坏均返回结构化未识别结果，不抛出原始路径或本机软件清单。验证：新增 `tests/test_local_inspection_environment_repository.py`，使用合成注册表/文件版本适配器覆盖 Windows 10/11、32/64 位、火绒已安装、版本未知、未安装和异常分支。

### Layer 21——后端 Service

- [x] 新增 `packages/backend/app/services/inspection_environment_service.py`，把 Repository 结果规范化为环境快照并生成步骤3；只使用检测事实和显式“待确认”文案，不启动安全软件或扫描。验证：新增 `tests/test_inspection_environment_service.py` 覆盖所有验收文案与无虚假“未发现病毒”边界。
- [x] 修改 `packages/backend/app/services/case_draft_service.py` 及 `workbench_factory_service.py`，在新案件完成共享默认硬件选择后采集一次环境快照并覆盖 Parser 的步骤3占位内容；既有草稿加载/保存不重新探测。验证：扩展 `tests/test_case_shared_defaults.py` 与 `tests/test_workbench_services.py`，覆盖最终硬件优先、快照持久化、旧案件不重写和依赖注入。
- [x] 修改 `packages/backend/app/services/report/report_parser_service.py`，删除写死的步骤3环境事实，仅产生明确待初始化占位内容；新案件正式草稿必须由上述初始化链替换。验证：扩展解析服务定向测试，断言 Parser 输出不含 FL-901、Windows 10 或固定火绒版本，草稿初始化后使用合成环境快照。

## 验证方式

- [x] 运行 SharedUtils/前端定向 Vitest 与新增后端 Repository/Service/草稿初始化 pytest（pytest 使用 `-q --tb=short`）。
- [x] 运行 `npm run verify:quick`；若仍仅受工作区既有 Agent 工具镜像漂移阻断，单独记录，不把其误归因于本变更。
- [x] 对照 delta spec 核对最终实现，完成 `delta spec → 实现核对 → sync → living spec 检查`，并运行 `npm run verify:docs:strict -- --change dynamic-process-step-environment` 与 `git diff --check`。
- [x] 人工验收：在纯合成案件中选择一台合成硬件设备，确认审核页与 Word 的步骤3显示当前机器识别结果；火绒未安装或版本不可读场景可使用受控适配器/测试构建验收，不采集或提交真实软件清单。

## 反馈修正（2026-08-20）

- [x] 检查过程中的 Windows 系统展示名称不再拼接 `DisplayVersion` 发布版本号；例如“Windows 10 21H2 企业版”规范为“Windows 10 企业版”，Windows 10/11 均保留系统代际、版本类型和位数。验证：更新环境服务定向测试，覆盖 Windows 10 `21H2` 与 Windows 11 `24H2` 均不进入展示名称。

## 反馈修正（2026-08-24）

- [x] 将 Windows 系统展示顺序统一为“系统代际 + 位数 + 版本类型”，例如“Windows 10 64位 家庭版”，并同步 delta 与 living spec。验证：环境服务定向测试覆盖 Windows 10 家庭版、Windows 10 企业版和 Windows 11 专业版。
- [x] 将位数与版本类型连续显示，例如“Windows 10 64位家庭版”，不在“64位”与“家庭版”之间插入空格；同步 delta 与 living spec。验证：环境服务定向测试覆盖 Windows 10 家庭版、Windows 10 企业版和 Windows 11 专业版。

## 反馈修正（2026-08-25）

- [x] 步骤3在已识别的 Windows 展示名称后明确补充“操作系统”，例如“Windows 10 64位家庭版操作系统启动正常”；操作系统信息待确认文案保持原状。同步 delta 与 living spec，并验证后端与共享前端两条步骤3投影路径。

## 反馈修正（2026-08-26）

- [x] 本机同时安装火绒安全软件和火绒应用商店时，只选择火绒安全软件的版本；仅安装火绒应用商店时不得误报已识别到安全软件。保留标准 `HipsMain.exe` 的文件版本兜底。

## 验证证据（2026-08-17）

- 后端定向测试：`89 passed`。
- 前端定向 Vitest：`1 file / 9 tests passed`。
- `lint:arch`、shared/frontend typecheck、OpenSpec strict validate 均通过。
- `verify:quick` 与 scoped strict docs 已执行；本变更 type drift 修复后，仅剩工作区既有 Agent 工具镜像漂移需由其所有者处理。
- 本机只读 smoke：操作系统识别状态为 `detected`，火绒识别状态为 `not_found`，因此本机新案件会显示安全软件及杀毒结果“待确认”；未输出或保存本机软件清单与版本详情。
- living spec 与 `openspec/specs/data-model.md` 已同步动态步骤3和可选环境快照契约。

## 反馈修正验证证据（2026-08-20）

- 环境服务、Repository、共享默认与工作台定向测试：`45 passed`。
- `npm run verify:quick`、`npm run verify:docs:strict -- --change dynamic-process-step-environment` 与 `git diff --check` 通过。

## 反馈修正验证证据（2026-08-24）

- 环境服务定向测试：`5 passed`；受影响的 Word、环境和 HashMyFiles 四个测试文件合计 `65 passed`。
- `npm run verify:quick`、`npm run verify:docs:strict -- --change dynamic-process-step-environment` 与 scoped `git diff --check` 通过。
- 位数与版本类型连续显示反馈：环境服务、本机环境 Repository、附件渲染与兼容填充四个受影响测试文件合计 `68 passed`；`verify:quick` 与本变更包 scoped strict docs 通过。

## 反馈修正验证证据（2026-08-25）

- 后端环境服务定向测试 `5 passed`，共享前端步骤投影定向 Vitest `11 passed`；已覆盖 Windows 10 家庭版与 Windows 11 专业版的“操作系统启动正常”表述，以及操作系统信息待确认分支。
- delta 与 living spec 已同步；`npm run verify:quick`、`npm run verify:docs:strict -- --change dynamic-process-step-environment` 和 `git diff --check` 均通过。

## 反馈修正验证证据（2026-08-26）

- 本机环境 Repository 定向测试 `7 passed`；与环境 Service 联合定向测试 `12 passed`。新增合成用例覆盖“应用商店在前”和“仅安装应用商店”两个回归边界；scoped `git diff --check` 通过。

## 边界

- 不新增前端环境配置表单或系统信息 API。
- 不自动安装、启动或控制火绒，不执行病毒扫描。
- 不追溯重写既有案件、已导出 Word 或用户已人工编辑的历史步骤。
- 不修改硬件设备 CRUD、主取证软件公司前缀、步骤4或检查结果生成规则。
