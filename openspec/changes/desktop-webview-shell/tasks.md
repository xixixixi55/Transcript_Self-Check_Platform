# WebView2 桌面宿主

workflow_level: 3
lifecycle_status: in-progress

## 0. 变更包与独立审计

- [x] 0.1 在 `openspec/changes/desktop-webview-shell/` 创建 proposal、desktop-webview-shell delta spec、design 和 tasks，记录与 `portable-windows-distribution` 的依赖及按用户要求独立建包的归属决策。验证：`openspec validate desktop-webview-shell --strict`。
- [x] 0.2 启动独立 Sub-Agent 审计本变更包的需求完整性、方案正确性、安全边界、可实施性与任务覆盖；在开始应用代码前修复全部阻断问题并由同一代理复审通过，再复验 strict validate。验证：初审发现正式合同冲突、Cookie 表述、下载、初始化回退、导航接线、干净机、双消息循环及许可覆盖问题；两轮修订进一步处理 pywebview 6.2.1 内置新窗口处理器、实际 renderer 回退和首次 bootstrap 导航时序，最终复审结论 PASS（0 Blocker / 0 High）。

## 1. 依赖与发布合同

- [ ] 1.1 在 `packaging/requirements-build.txt` 锁定实际解析的 pywebview、pythonnet、CLR loader 及全部分发依赖，在 `packaging/portable-manifest.json` 单独声明 launcher 运行依赖版本，并更新 `packaging/THIRD-PARTY-NOTICES.txt` 与对应 `packaging/licenses/` 许可正文。验证：从隔离安装结果枚举 distributions，依赖解析/现有清单测试确认每个实际分发依赖版本和许可均受覆盖，且未改变后端运行依赖。
- [ ] 1.2 扩展 `packaging/launcher.spec`，只收集 pywebview EdgeChromium/WinForms 所需模块和 DLL，显式排除 Qt、GTK、CEF、Android、Cocoa、EdgeHTML 与 MSHTML 后端；新增 archive/TOC 检查拒绝无关后端、x86/ARM64 原生资产、Fixed Runtime、下载器和调试配置。验证：实际 PyInstaller archive/TOC 与冻结 EXE 导入烟雾通过。

## 2. 桌面窗口生命周期

- [ ] 2.1 新增 `packages/launcher/desktop_window.py`，实现固定 loopback 引导 URL、用户数据目录、窗口规格、三级就绪屏障和显式状态机；在同步 `window.events.initialized` 中断言实际 renderer 严格为 `edgechromium`，不匹配则在原生窗口创建前取消并回退，不传 `js_api` 或暴露 Python 函数。验证：先新增 `tests/test_desktop_window.py` 形成失败用例，再覆盖 renderer/原生 Core/最终页面各级成功、异常、超时和幂等停止；Runtime 缺失时断言 MSHTML BrowserForm 未创建且 bootstrap 未加载。
- [ ] 2.2 修改 `packages/launcher/windows_tray.py`，为后台托盘消息循环增加线程安全结果通道、幂等外部停止和退出回调，同时保持同步浏览器回退路径兼容。验证：扩展启动器托盘测试，覆盖创建失败、回调异常、初始化期退出、后端停止、关闭/退出/停止竞态、重复停止和 join 超时。
- [ ] 2.3 修改 `packages/launcher/main.py` 接入桌面宿主：WebView2 成功时不打开浏览器；任一级初始化失败时关闭宿主和旧后端、生成新秘密并有界重启一次后端，再显示一次诊断并进入既有浏览器/托盘流程。所有路径继续执行 Job Object、日志、ready 文件和单实例清理；生产入口移除继承的 `PYWEBVIEW_LOG` 调试覆盖、钳制第三方 logger 并对原始及 URL 编码秘密做统一过滤。验证：扩展 `tests/test_portable_launcher_main.py` 区分桌面成功、token 未消费/已消费失败、换密钥回退、浏览器双重失败、重启失败、GUI 意外返回和异常后端退出，断言无幽灵线程/窗口/进程。

## 3. 安全与导航

- [ ] 3.1 在 `packages/launcher/desktop_window.py` 关闭 file URL并先以无业务 URL 的空白隐藏窗口创建原生控件；Core ready 后、主动加载 bootstrap 前，通过 `window.native.browser` 精确注销并确认移除 pywebview 6.2.1 内置 `on_new_window_request`，再安装唯一的原生 WebView2 `NavigationStarting`/`NewWindowRequested` 可取消处理器。只允许解析后的精确 loopback origin，普通 http/https 外链取消后交给默认浏览器，危险 scheme 直接拒绝，任何处理器替换失败均进入初始化回退。验证：SYNTHETIC URL 测试覆盖相似主机、userinfo、端口、scheme、片段和外部地址，并用真实 WebView2 冒烟验证首次 bootstrap 跨源 30x、同窗口导航、后续重定向、新窗口、钩子安装/替换失败；断言外部内容从未进入主窗口，每个新窗口请求只外开一次且主窗口 URL 不变。
- [ ] 3.2 复用现有桌面 bootstrap/API 鉴权集成测试，确认 WebView2 接线未改变一次性秘密、HttpOnly Cookie、重放拒绝和后端重启失效行为。验证：运行 `tests/test_portable_web.py` 与桌面窗口安全定向测试；以 SYNTHETIC secret 捕获 launcher 与 pywebview 的全部日志、异常和用户提示，在继承 `PYWEBVIEW_LOG=DEBUG` 时仍断言秘密原值及 URL 编码值零出现；临时破坏过滤、origin 或秘密传递时至少一个断言失败。
- [ ] 3.3 在 `packages/launcher/desktop_window.py` 显式启用 EdgeChromium 下载但不新增 Python 文件桥，保持下载路径由用户选择。验证：使用 SYNTHETIC Word Blob 与 RAR anchor 在真实 WebView2 中覆盖建议文件名、保存内容、取消、同名冲突与失败，不得向程序目录或 WebView 数据目录静默写制品。

## 4. 构建与使用说明

- [ ] 4.1 修改 `scripts/build-portable.ps1` 和 `tests/test_verify_portable_package.py`，在发布构建中检查桌面宿主依赖、PyInstaller archive/TOC、x64 WebView2 loader、许可覆盖和无关 GUI 资产排除，保留白名单资产边界，并确保 WebView 用户数据只写 `%LOCALAPPDATA%\文枢\webview`。验证：便携构建脚本合同测试和合成 staging 正反例通过。
- [ ] 4.2 更新 `README.md` 与 `packaging/PORTABLE-README.txt`，说明默认独立窗口、关闭到托盘、显式退出和 WebView2 不可用时的默认浏览器回退；不承诺捆绑或静默安装 WebView2。验证：scoped strict docs 与 `git diff --check`。

## 5. 候选验证与收敛

- [ ] 5.1 运行启动器、托盘、桌面安全、便携 Web 与构建脚本的受影响测试，以及 `lint:arch`、`typecheck` 和 `verify:quick`；修复只由本分支引入的失败并记录现有基线漂移。验证：命令退出码、通过数量和 `git diff --check`。
- [ ] 5.2 执行真实 `npm run build:portable`，在当前 Windows x64 + Evergreen WebView2 环境运行 `文枢.exe`，验证独立窗口、下载、外部导航、无默认浏览器副本、目录选择框前台归属、关闭隐藏、托盘恢复、初始化竞态、单实例和显式退出；通过可注入方式验证 WebView2/CLR 缺失、各级超时和换密钥回退。不得使用真实案件数据。验证：候选 ZIP 哈希、SYNTHETIC/TEST 冒烟记录和进程清理结果。
- [ ] 5.3 在没有 Python、.NET SDK 和开发依赖的干净 Windows 10/11 x64 环境运行冻结候选；分别验证 Evergreen WebView2 可用的完整桌面流程，以及 WebView2/CLR/pythonnet 不可用时的有界默认浏览器回退。验证：目标机版本、候选哈希、窗口/下载/目录选择/退出结果与无残留进程记录。
- [ ] 5.4 核对最终实现与两个 delta spec，将新增能力同步到 `openspec/specs/desktop-webview-shell/spec.md`，并将修改后的启动生命周期同步到 `openspec/specs/portable-windows-distribution/spec.md`；冻结候选后启动独立代码审查并修复有效发现，最终运行 `npm run verify:full -- --change desktop-webview-shell`。验证：两份 living spec 证据、Review 结论、scoped full gate 与预期 diff。
