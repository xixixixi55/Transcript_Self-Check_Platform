# 支持新旧电子数据检查报告格式

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: 已同步到 openspec/specs/electronic-inspection-record/spec.md REQ-002/REQ-003

## 目标

在不改变现有 `InspectionReport` 公共模型、审核页面和 Word 导出流程的前提下，
将旧格式和新格式报告归一化为同一套标准数据。实现以文件夹上传为本轮验收入口；
现有 ZIP/RAR 路径继续保持，不扩展新格式压缩包专项验收。

## 已确认业务规则

- `data_case_info.json` 的“创建时间”和“报告时间”分别是标准检查开始、结束时间；不使用 `tb2` 的“取证时间段”猜测检查时间。
- `data_device_lists.json` 的 `tb2` 中合法非空 IMEI1/IMEI2 优先；仅在首选值缺失时，才使用结构明确的设备基本信息表补充。
- 设备基本信息表必须通过多个强字段组合识别，不能依赖具体文件名，也不能扫描普通 Base JSON 或任意 15 位数字。
- 已识别的键值表允许受控使用 `tt → 字段名`、`ct → 字段值`，并继续支持既有别名、`信息/内容` 和 `c1/c2`。
- 旧格式继续读取明确的“产品版本”；新格式只从语义明确且同时包含软件名称和版本结构的主取证软件/报告生成软件记录中读取版本。
- `software_tools` 只包含已可靠识别的主取证软件、WinRAR 和 Python hashlib。
- 网安案件编号、检材来源/状态、持有人及其他新增业务字段本轮忽略；照片和附件二继续人工上传。

## 明确非目标

- 不纳入网安案件编号、持有人等新增字段，也不扩展公共标准模型。
- 不自动导入图片，不扫描 `Base/attachments/` 或 `Base/records/pictures/`。
- 不为新格式新增 ZIP/RAR 解压或大型目录压缩专项兼容逻辑。
- 不修改前端审核逻辑、Word 模板、Word 导出排版或照片/附件二上传流程。
- 不提交真实甲方报告、照片、附件、解析缓存或本地绝对路径。
- 本轮不执行 OpenSpec 归档。

## 实施任务

### 格式检测和归一化

- [x] 在 `packages/backend/app/repository/report_format_adapter.py` 集中定义格式枚举、核心结构检测、旧/新/混合格式确定行为和受控字段归一化入口。
- [x] 在 `packages/backend/app/repository/html_parser.py` 接入新格式的 `tb2`、`tt/ct` 和设备信息表解析，同时保持 `Base/`、`Phone/` 旧路径行为。
- [x] 在 `tests/test_html_parser.py` 使用脱敏合成 fixture 覆盖旧格式、新格式、混合格式、不支持格式和旧字段回归。

### 标准字段来源和优先级

- [x] 在 `packages/backend/app/services/report_parser_service.py` 使用案件 JSON 的创建/报告时间生成标准检查时间，应用 IMEI 优先级、设备表字段和软件工具规则。
- [x] 将 `packages/backend/app/services/report_parser_service.py` 的解析缓存版本从 4 提升到 5，并覆盖旧缓存失效及 `compress/nocompress` 隔离。
- [x] 在 `tests/test_report_parser_service.py` 覆盖时间、IMEI 冲突、序列号、软件版本可靠性、工具列表和缓存行为。

### 验证和真实样例核对

- [x] 清理 `tests/test_html_parser.py` 对本地绝对旧报告路径的正式测试依赖，所有自动化 fixture 可在任意环境重复运行。
- [x] 运行精准后端测试、`npm.cmd run test:backend`、`npm.cmd run verify:quick` 和 `git diff --check`。
- [x] 在真实新旧报告的临时副本上完成脱敏自动化核对，只汇报格式识别、字段来源、优先级和是否生成完整标准报告，不输出案件敏感值。

### 兼容解析正确性加固

- [x] 在 `packages/backend/app/repository/report_format_adapter.py` 收紧有效 `tb2`/`c3` 检测、缺失核心文件错误和主软件名称-版本绑定。
- [x] 在 `tests/test_html_parser.py` 覆盖空/错误 `tb2`、陌生键值结构、日期有效性、软件候选歧义和设备候选评分边界。
- [x] 在 `packages/backend/app/repository/device_field_parser.py` 与 `packages/backend/app/repository/html_parser.py` 实现单一最佳设备表候选、合法 IMEI 和稳定冲突处理。
- [x] 在 `tests/test_html_parser.py` 覆盖跨文件不拼接、同分冲突、遍历顺序、IMEI 备用值和多检材目录隔离。
- [x] 在 `packages/backend/app/services/report_parser_service.py` 删除不安全的单检材目录回退，并保持多检材主设备限制明确。
- [x] 在 `tests/test_report_parser_service.py` 覆盖目录不匹配、旧格式完整标准模型、缓存边界和日期反向范围。
- [x] 在 `packages/backend/app/controllers/record_controller.py` 增加结构错误的 HTTP 422 集成测试，不改变 Controller 业务范围。
- [x] 在 `tests/test_document_builder_service.py` 增加旧格式合成标准模型进入 Word 导出的最小回归测试，不修改模板。

### 待人工验收（保持未完成）

- [x] 旧格式前端上传验收。
- [x] 新格式前端上传验收。
- [x] 新旧格式 Word 导出对比。
- [x] 真实样例字段人工核对。

### 新格式检材与设备目录绑定修复

- [x] 在 `packages/backend/app/repository/html_parser.py` 与 `packages/backend/app/repository/report_parse_input_repository.py` 使用每个 `tb2` 行内明确的 `data/<设备目录>/Base/` 路径绑定检材编号和设备型号，避免分别排序后按下标错配；无明确路径的兼容变体继续使用一对一保守回退。
- [x] 在 `tests/test_report_parse_input_repository.py` 使用显式合成数据覆盖检材行顺序、设备目录字母序不一致时仍保持编号—型号对应关系，并运行解析仓库与报告解析定向测试（73 passed）及完整后端回归（1048 passed、3 skipped）。
- [x] 将解析缓存版本递增，使用用户提供的实际报告只核对检材编号—设备型号映射，并通过 `verify:quick`、受影响后端测试与 scoped strict docs（13 checks、0 drift）。
- [x] 在 `packages/backend/app/services/report_parser_service.py` 对完整检材记录执行自然升序，再由该数组生成检查过程、检查结果和审核/Word 共用数据；脱敏样例验证为 `SYN-JC0001 → SYNTHETIC DEVICE A`、`SYN-JC0002 → SYNTHETIC DEVICE B`，定向测试 45 passed，`verify:quick` 通过。

## 验收

- [x] 旧格式解析结果和标准模型归一化自动化测试通过。
- [x] 前端审核、旧/新格式 Word 导出对比和人工版式验收完成。
- [x] 所有新增测试使用合成数据；工作区已有输出删除、模板、照片、IDE 文件和其他未跟踪资产保持未触碰。
- [x] 兼容解析正确性加固：格式检测、设备候选隔离与冲突保护、IMEI/日期/software 规则、错误边界和标准模型回归自动化测试。
- [x] 真实新旧样例临时副本脱敏复核：格式、时间来源、IMEI、序列号、设备目录隔离、完整模型和 Word 生成结果已核对；主软件版本无法可靠绑定的样例保持空值。
