workflow_level: 3

## 1. 发布基础设施与依赖锁定

- [x] 1.1 在 `packages/backend/requirements-runtime.txt`、`packaging/requirements-build.txt` 和根 `package.json` 定义发布期Python/PyInstaller及Node/officecli构建入口，固定实际发布版本且不改变开发命令。验证：解析依赖文件，运行现有`typecheck`和一个后端最小测试。
- [x] 1.2 新增 `packaging/portable-manifest.json`、`packaging/THIRD-PARTY-NOTICES.txt` 与发布资产白名单，明确Windows x64目录、必需资源、禁止资产和WinRAR非捆绑边界。验证：清单schema测试覆盖缺失、额外文件、数据库/RAR/日志拒绝场景（发布内容 Requirement）。

## 2. Layer 20 — 运行时路径与工具解析

- [x] 2.1 新增 `packages/backend/app/repository/runtime_paths.py`，统一解析开发/冻结资源根和 `%LOCALAPPDATA%\文枢` 下的数据、工作、日志、备份目录；修改 `packages/backend/app/config.py` 只投影该结果。验证：新增 `tests/test_runtime_paths.py` 覆盖源码态、发布态、环境覆盖、缺失LOCALAPPDATA和程序目录只读边界（数据分离 Requirement）。
- [x] 2.2 修改 `packages/backend/app/repository/hashmyfiles_repository.py`、`workbench_database.py` 及相关文件资源Repository，改用注入或统一运行时路径，不再通过固定仓库层级定位发布资源。验证：定向pytest覆盖环境覆盖优先、包内默认和用户数据不落发布目录。
- [x] 2.3 新增 `packages/backend/app/repository/officecli_runtime_repository.py`，以显式参数数组解析并调用包内`node.exe + officecli入口`，开发态兼容显式/全局入口，发布态禁止全局回退和联网。验证：Repository单元测试覆盖包内成功、缺失、非零退出、含空格中文路径及发布态不调用PATH（私有officecli Requirement）。

## 3. Layer 21 — 组合根和文档生成接线

- [x] 3.1 修改 `packages/backend/app/services/workbench_factory_service.py`、`record_generator_service.py` 及相关Service，把模板、上传、输出、HashMyFiles和officecli路径从统一RuntimePaths注入，保持正式模板与officecli回退语义。验证：现有模板/导出pytest加发布布局回归，临时破坏包内officecli解析时测试必须失败（私有officecli、数据分离 Requirements）。
- [x] 3.2 扩展运行就绪服务以分别报告包内资源和外部WinRAR状态；WinRAR缺失不得阻止应用启动，但继续门控RAR相关能力。文件：`packages/backend/app/services/demo_readiness_service.py`及现有相关测试。验证：pytest覆盖WinRAR存在/缺失与非RAR能力不受影响（WinRAR Requirement）。

## 4. Layer 23 — 生产同源服务和会话边界

- [x] 4.1 修改 `packages/backend/app/main.py`并新增不含业务逻辑的发布bootstrap模块，生产态从RuntimePaths提供Vite静态文件和SPA fallback，开发态保留当前CORS/Vite代理。验证：FastAPI TestClient覆盖首页、静态资产、未知SPA路由、API不被fallback吞掉（便携包与本地服务 Requirements）。
- [x] 4.2 增加loopback桌面会话鉴权和一次性浏览器引导，API/下载拒绝无会话请求，开发态不启用；秘密不得写日志或最终地址。文件：`packages/backend/app/main.py`及同层辅助模块。验证：集成测试覆盖合法引导、重放、未授权API、健康检查和开发兼容；对鉴权判断做可区分有效性验证（本地服务 Requirement）。
- [x] 4.3 新增 `packages/backend/app/portable_entry.py`，仅接受loopback端口、发布资源根、数据根和启动秘密，输出机器可读就绪握手并支持有界关闭。验证：子进程烟雾测试覆盖正常就绪、端口冲突、资源缺失和无秘密拒绝。

## 5. Windows启动器与发布构建

- [x] 5.1 新增 `packages/launcher/` 的Python启动器，实施同一数据根单实例、随机端口、秘密生成、隐藏后端、健康检查、浏览器打开、日志和进程树清理。验证：启动器单元测试覆盖正常、重复启动、超时、后端早退和退出清理（启动生命周期 Requirement）。
- [x] 5.2 新增 `packaging/backend.spec`、`packaging/launcher.spec` 和 `scripts/build-portable.ps1`，构建PyInstaller onedir后端/windowed启动器、Vite前端、私有Node/officecli、模板和完整HashMyFiles分发文件。验证：构建脚本在staging验证所有必需入口，目标机PATH清空时officecli烟雾成功（便携包、私有officecli Requirements）。
- [x] 5.3 新增 `scripts/verify-portable-package.py`，按白名单验证staging、生成文件SHA-256/版本/第三方清单并拒绝数据库、RAR、生成DOCX、日志、环境文件、测试缓存和WinRAR，最后生成版本化ZIP。验证：合成staging正反例测试及仓库资产门控（发布内容 Requirement）。
- [x] 5.4 更新 `harness/directory.md`、`.gitignore` 和 `README.md`，只引用发布脚本与数据目录真相源，发布产物保持git忽略。验证：默认和scoped strict docs、`git diff --check`。

## 6. 候选验证与发布证据

- [x] 6.1 运行后端/启动器/发布脚本定向测试、`lint:arch`、`typecheck`、`verify:quick`，并构建本机候选ZIP；记录通过/失败统计，不提交候选二进制。验证：命令退出码和ZIP清单哈希。
- [ ] 6.2 在无全局Python、Node、pnpm、officecli和旧版文枢的Windows 10/11 x64环境执行解压启动、中文路径、重启、Word、officecli回退、WinRAR和统一导出验收，证据写入本变更包；仅开发机验证不得勾选。 [DEFERRED]
- [x] 6.3 冻结候选后执行一次独立Code Review，修复源码/行为后复审；通过后运行`npm run verify:full -- --change portable-windows-distribution`并记录人工验收适用性。验证：Review结论、scoped full gate和`git diff`仅含预期变更。

## 7. 部署反馈：托盘启动生命周期

- [x] 7.1 设计并生成无文字、多尺寸的文枢 Windows 图标，接入 PyInstaller EXE 图标资源；验证 ICO 包含 16/20/24/32/40/48/64/128/256 像素帧且发布构建可读取。
- [x] 7.2 新增原生 Win32 托盘消息循环，将启动器的阻塞式运行提示替换为“打开文枢/退出文枢”菜单，并在后端意外结束时撤销托盘；验证启动器单元测试覆盖打开、显式退出、异常退出和清理。
- [x] 7.3 运行启动器测试、真实 Win32 托盘烟雾、PyInstaller EXE 图标构建和工程增量门控，并记录验证结果。
- [ ] 7.4 按 `manual-acceptance.md` 在目标 Windows 10/11 电脑验收托盘显示、重新打开、浏览器关闭后继续运行及显式退出；反馈收敛后重新冻结候选，再统一 Review 与 scoped full gate。 [DEFERRED]

## 8. 部署反馈：原生目录选择框前台归属

- [x] 8.1 修改 `local_directory_picker_service.py`，捕获触发时的前台窗口并作为 `FolderBrowserDialog` owner；保留隐藏 owner/置顶兜底并记录前台确认状态。
- [x] 8.2 更新现有目录选择器测试，区分浏览器 owner、兜底 owner、持续提升和诊断日志合同；运行定向 pytest、真实 PowerShell 类型编译及工程增量门控。
- [ ] 8.3 按 `manual-acceptance.md` 在部署电脑分别验证上传报告和统一导出的选择框始终位于浏览器之前。 [DEFERRED]

## 9. 部署反馈：Windows PowerShell WinForms 编译引用兼容

- [x] 9.1 记录部署失败：目标 Windows PowerShell 执行 `Add-Type -TypeDefinition` 时未自动引用 `System.Windows.Forms`，导致 `IWin32Window` owner 包装类编译失败，上传报告与统一导出均无法打开目录选择器。
- [x] 9.2 将 owner C# 源码保存为独立 PowerShell 变量，并为 `Add-Type` 显式传入 `System.dll` 与 `System.Windows.Forms.dll`；不改变浏览器 owner、置顶兜底、目录授权或历史目录合同。
- [x] 9.3 更新脚本合同测试并运行真实 Windows PowerShell 5.1 显式引用编译、目录选择器定向 pytest、`verify:quick`、scoped strict docs 与 `git diff --check`。
- [ ] 9.4 重新构建便携 ZIP，并在部署电脑复测上传报告和统一导出目录选择器。 [DEFERRED]

验证记录：目录选择器与工作台控制器定向 Pytest 50 项通过，其中生成脚本在 Windows PowerShell 5.1 中真实编译；`verify:quick` 与 `git diff --check` 通过。部署电脑复测随下一版便携 ZIP 进行。

## 10. 部署反馈：当前内置模板跨解压目录启动迁移

- [x] 10.1 记录部署失败：已有数据根中的当前内置模板 `1.0.3` 保存了旧程序目录定位，新便携包从不同目录启动时只迁移历史 `1.0.0`～`1.0.2`，当前版本注册因定位不同触发 `TEMPLATE_VERSION_IMMUTABLE`。
- [x] 10.2 在注册当前 `1.0.3` 前复用既有 `relocate_builtin_asset`，仅当版本、包指纹与资产 ID 均匹配时更新受控定位；内容或身份不一致时继续 fail-closed。
- [x] 10.3 增加 SYNTHETIC 旧便携目录定位回归，运行模板定向 pytest、`verify:quick`、scoped strict docs、`git diff --check` 并重新构建便携 ZIP。
- [ ] 10.4 在保留 `%LOCALAPPDATA%\文枢` 数据根的情况下更换解压目录，确认启动成功且既有案件与模板引用可继续读取。 [DEFERRED]

验证记录：失败回归先稳定复现 `TEMPLATE_VERSION_IMMUTABLE`，修复后当前模板跨目录迁移、内置模板重命名重启和历史模板升级 3 项通过；模板控制器/仓库模块 20 项通过，`verify:quick`、`git diff --check` 和便携包完整构建通过。目标电脑保留数据根的真实换目录验收保持延期。

## 11. 构建反馈：项目内锁定工具链自动发现

- [x] 11.1 记录构建失败：新 PowerShell 会话未保留 `BIJI_NODE_DIST_DIR` 与 `BIJI_OFFICECLI_PACKAGE_DIR`，构建回退到缺少官方 `LICENSE` 的系统 Node，导致每次手工设置三行命令。
- [x] 11.2 调整 `build-portable.ps1` 的解析顺序为显式环境覆盖、`dist/toolchain` 中清单锁定版本、系统安装；本地目录不存在或内容/版本无效时继续明确失败，不自动下载、不放宽许可证和版本校验。
- [x] 11.3 增加构建脚本优先级合同测试，清空两个环境变量后仅运行 `npm.cmd run build:portable` 完成真实构建，并执行 `verify:quick`、scoped strict docs 与 `git diff --check`。

验证记录：便携构建脚本测试 11 项通过；在同一 PowerShell 进程清空两个工具链环境变量后，仅执行 `npm.cmd run build:portable` 成功生成版本化 ZIP；`verify:quick`、scoped strict docs 与 `git diff --check` 均通过。

## 12. 部署反馈：额外文件宽容与设备配置数据根迁移

- [x] 12.1 调整启动器运行时完整性校验：清单不可用、必需文件缺失、哈希变化和符号链接继续阻断；清单外普通文件只返回稳定结果，并在用户数据日志写入不含文件名/路径的告警数量。验证：启动器测试分别覆盖缺失、篡改、额外文件、脱敏日志和符号链接。
- [x] 12.2 将 `hardware_devices.json` 读写迁入 `RuntimePaths.data_root`；目标文件不存在时初始化默认设备，并兼容一次性规范化迁移旧程序目录遗留配置，之后不得再写冻结程序目录。验证：设备配置测试覆盖默认初始化、旧配置迁移、用户数据优先及增删改不触碰遗留文件。
- [x] 12.3 运行启动器、RuntimePaths、设备配置及便携构建定向测试，执行适用架构/类型/工程门控并重新构建覆盖便携 ZIP。
- [x] 12.4 使用实际 `文枢.exe` 验收：清单外文件可启动且日志脱敏，缺失/篡改清单文件仍拒绝，干净解压首次与第二次启动均成功，指定真实报告完成解析、审核、分卷压缩和统一导出。Word 视觉验收按用户要求标记 N/A。

验证记录：启动器、RuntimePaths、设备配置与便携包校验定向 Pytest 45 项通过，`lint:arch`、`typecheck`、`verify:quick` 通过；实际重新构建覆盖 `文枢-v0.2.0-portable-x64.zip`，SHA-256 为 `a413c87a660afb9710d19905e0c977f26008a12d8a8be9074382e6b619797ce4`。实际 EXE 缺失与篡改场景分别显示稳定拒绝提示；单个清单外普通文件连续两次启动成功，用户数据日志仅记录 `count=1`，旧设备配置一次性规范化迁入用户数据根且程序目录内容未被回写。指定报告目录完成解析、审核、4 张 SYNTHETIC/TEST 图片绑定、约 4.90GB 数据压缩为 2 个 RAR 分卷并统一导出 1 个 DOCX、2 个 RAR 和 1 个校验 PNG；DOCX 必需 ZIP 项、PNG 可读取且 RAR 全卷测试退出码为 0。Word 视觉验收：N/A（用户明确要求不执行）。
