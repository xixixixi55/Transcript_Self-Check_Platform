# 设备所属公司与报告软件名称前缀

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: `openspec/specs/electronic-inspection-record/spec.md` REQ-010/REQ-016 与 `openspec/specs/data-model.md` HardwareDevice

## 目标

在电子设备管理中为每台取证硬件设备维护“所属公司”，并在新案件完成报告解析、进入审核编辑草稿时，使用当前选中硬件设备的所属公司为报告可靠识别出的主取证软件名称添加一次无分隔符前缀。例如，设备所属公司为“美亚柏科”、报告识别软件为“手机大师NEXT”时，审核编辑、检查过程、检查结果和最终 Word 使用“美亚柏科手机大师NEXT”。

行为要求以 `specs/electronic-inspection-record/spec.md` 为准。

## 活跃变更包关联结论

- `audit-edit-enhancement` 已实现主取证软件编辑和名称清洗，但其目标不包含设备配置新增业务字段；本变更只复用其 `inspection.primary_software` 唯一编辑结构，不改写其点击编辑交互。
- `extensible-report-template-platform` 维护未来 Canonical/Shadow 管线；本变更不得切换正式输出管线，并须保证公司前缀是明确设备配置驱动的投影，而不是从报告文本猜测厂商。
- `case-shared-defaults` 只保存 `inspection.hardware_device` 字符串；本变更在该默认值选定最终硬件后解析所属公司，不扩大共享默认值白名单。
- 其余活跃变更包不同时覆盖“设备所属公司 CRUD”和“报告软件名称前缀”完整目标，因此创建独立 Level 2 变更包。

## 范围与边界

- 设备所属公司属于硬件设备配置，不写入报告解析缓存，也不从报告正文、软件名称或设备型号猜测。
- 公司前缀只应用于报告可靠识别的主取证软件；WinRAR、HashMyFiles 等运行时工具及人工新增工具保持原名。
- 新案件草稿先应用现有检查硬件共享默认值，再按规范化后的设备名称唯一匹配设备配置并添加前缀。
- 公司与软件名称直接拼接，不自动插入空格、短横线或括号；软件名称已包含同一公司前缀时不得重复添加。
- 设备未匹配、匹配不唯一、所属公司为空或主软件尚未可靠识别时保持原值，不猜测、不阻断审核。
- 前缀同步到 `inspection.primary_software`、兼容 `result.software_name`、主软件工具条目和检查步骤 4；报告来源候选及 provenance 保持原始证据语义。
- 既有案件草稿和人工编辑的软件名称不做批量追溯改写；修改设备配置只影响之后初始化的新案件草稿。
- 不新增数据库、路由、第三方依赖，不改变归档、Manifest、图片、模板和导出门控。

## 验收标准

- [x] 设备管理列表和新增/编辑表单显示“所属公司”，新建设备必须填写，保存后刷新仍保留。
- [x] 旧配置记录缺少 `company` 时仍可读取并显示为待补充；补充公司后可正常保存，不破坏既有名称、型号和描述。
- [x] 新案件使用唯一匹配且公司为“美亚柏科”的硬件设备时，报告主软件“手机大师NEXT”在审核编辑界面显示为“美亚柏科手机大师NEXT”。
- [x] 同一前缀只添加一次，并同步到主软件、软件工具列表、检查步骤 4、检查结果和 Word 消费的兼容字段。
- [x] WinRAR、HashMyFiles、人工新增工具和原始报告候选不被添加公司前缀。
- [x] 无公司、无可靠主软件、设备未匹配或匹配不唯一时保留报告识别值，不选择任意设备公司。
- [x] 已存在案件、用户手工编辑的软件名称和设备配置变更前生成的正式数据不被静默重写。
- [x] 所有新增测试仅使用带 `SYNTHETIC`、`TEST` 或 `FIXTURE` 标记的合成数据。

## 任务列表

任务按架构层级从低到高排列。

### Layer 0 — SharedTypes

- [x] 在 `packages/shared/types/index.ts` 的 `HardwareDevice` 契约中增加必有字符串字段 `company`；设备列表 API 对旧持久化记录也返回规范化后的空字符串，避免前端出现不稳定的 `undefined` 分支。验证：运行 shared/frontend typecheck。

### Layer 11 — FE Components

- [x] 在 `packages/frontend/src/components/DeviceManager.tsx` 增加“所属公司”表格列和新增/编辑表单项；新建或编辑提交时要求非空并保持现有 CRUD、错误提示和表单重置行为。验证：新增 `packages/frontend/src/components/DeviceManager.test.tsx`，覆盖列表展示、新增提交、编辑回填、旧记录待补充和空值校验（REQ-010 场景）。

### Layer 20 — BE Repository

- [x] 在 `packages/backend/app/repository/device_config.py` 为默认设备和新增记录持久化 `company`，读取缺少该字段的旧 JSON 时规范化为 `company: ""`，并让更新操作区分“未提交公司字段”和“提交有效公司值”。验证：扩展 `tests/test_device_config.py` 覆盖旧记录兼容、创建、更新和其余字段不丢失。
- [x] 在 `packages/backend/app/data/hardware_devices.json` 为默认 FL-901 设备补充 `company: "美亚柏科"`；保留工作区中已有的设备名称修改及其他用户配置，不回退或重写无关记录。验证：JSON 可解析、资产检查通过、`git diff` 仅含预期字段。

### Layer 21 — BE Services

- [x] 在 `packages/backend/app/services/device_config_service.py` 接收、清洗并验证公司字段，提供按规范化设备名称唯一解析所属公司的只读能力；名称匹配忽略大小写和空白差异，多个候选时返回未匹配而不是任取一条。验证：扩展 `tests/test_device_config.py` 覆盖空白、唯一匹配、未匹配和歧义边界。
- [x] 在 `packages/backend/app/services/software_policy_service.py` 增加幂等的公司前缀投影：只修改报告可靠主软件及其派生字段，保持运行时工具、候选和 provenance 不变，并更新检查步骤 4 的主软件显示。验证：扩展 `tests/test_software_policy_service.py` 覆盖正常拼接、已带前缀、空公司、未确认主软件、运行时工具隔离及四处投影一致性（REQ-016 场景）。
- [x] 在 `packages/backend/app/services/case_draft_service.py` 的新草稿初始化链中，先完成现有共享默认硬件选择，再解析该设备公司并调用软件前缀投影；既有草稿加载、Parser 缓存和重新保存不得触发追溯改写。验证：扩展 `tests/test_case_shared_defaults.py` 与 `tests/test_workbench_services.py`，覆盖共享默认设备优先、初始化一次、设备缺失/歧义降级及既有案件不变。

### Layer 22 — BE Controllers

- [x] 在 `packages/backend/app/controllers/device_controller.py` 扩展设备新增/更新请求模型：新建设备要求非空公司，更新请求兼容未携带 `company` 的旧客户端，但显式空白公司不得覆盖有效值；响应始终返回规范化 `company`。验证：新增 `tests/test_device_controller.py` 的 pytest/httpx 集成测试，覆盖 2xx、422、旧更新请求和 404。

## 验证方式

- [x] 运行前端定向测试，覆盖 `packages/frontend/src/components/DeviceManager.test.tsx`。
- [x] 运行后端定向测试，覆盖 `tests/test_device_config.py`、`tests/test_device_controller.py`、`tests/test_software_policy_service.py`、`tests/test_case_shared_defaults.py` 与 `tests/test_workbench_services.py`。
- [x] 运行 `npm run verify:quick`。
- [x] 对照本变更 delta spec 逐项核验实现，并运行 `npm run verify:docs:strict -- --change device-company-software-prefix` 与 `git diff --check`。
- [ ] 人工验收：使用纯合成报告，在设备公司为“美亚柏科”时确认审核编辑和生成 Word 均显示“美亚柏科手机大师NEXT”，且 WinRAR/HashMyFiles 不带该前缀；不得把真实案件或生成文件提交到仓库。 [DEFERRED]

## 验证证据

- 前端定向：1 个文件、3 项测试通过。
- 后端定向：65 项测试通过。
- 前端完整模块：退出码 0，无失败用例。
- 后端完整模块：1125 项通过、3 项跳过；36 条既有环境/fixture 警告。
- `npm run verify:quick`：架构、类型、治理测试、文档和仓库资产检查全部通过。
- Word 消费链：后端集成测试将初始化后的草稿送入 `build_record_document`，断言公司前缀进入文书文本且 HashMyFiles 不加前缀。
