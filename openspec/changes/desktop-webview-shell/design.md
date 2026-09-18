## Context

当前 `文枢.exe` 是 PyInstaller 单文件 Python 启动器：校验发布清单、取得单实例锁、启动冻结 FastAPI 后端、等待固定端口 40000 的带证明握手、用一次性片段秘密打开默认浏览器，随后由原生 Win32 托盘维持生命周期。React 页面与 API 已同源，且桌面会话使用 HttpOnly Cookie，不需要为了桌面化改造业务前后端。

本变更按用户明确要求独立于仍在进行的 `portable-windows-distribution` 建包。后者是稳定前置能力与回滚基线；本包只负责把其浏览器展示方式替换为桌面窗口，并隔离审计新增渲染依赖与安全面。项目当前只发布 Windows x64，构建机安装 Python/PyInstaller但没有 .NET SDK。

## Goals / Non-Goals

**Goals:**

- 复用现有 React/FastAPI，实现没有地址栏和标签页的 Windows 桌面窗口。
- 保持一次性会话引导、固定端口、单实例、托盘和后端进程清理合同。
- 使用受安全更新的系统 Evergreen WebView2 Runtime，缺失时保持默认浏览器可用。
- 使新增依赖、PyInstaller 收集范围、许可和真实 Windows 行为可自动验证与审计。

**Non-Goals:**

- 不重写业务 UI，不新增前后端业务 API 或桌面特权桥。
- 不引入 Electron/Tauri，不增加 .NET SDK 构建前置，不支持非 Windows 平台。
- 不捆绑会显著扩大便携包体积的 Fixed Version WebView2，不静默联网安装 Evergreen Runtime。
- 不改变数据库、模板、报告解析、RAR 或目录选择授权模型。

## Decisions

### D1. 复用 Python 启动器并以 pywebview EdgeChromium 承载 WebView2

锁定 `pywebview==6.2.1` 与经验证的 Python 3.11 Windows 依赖，在新的高内聚 `packages/launcher/desktop_window.py` 中延迟导入 `webview`。启动器显式调用 `webview.start(gui="edgechromium", debug=False, private_mode=False, storage_path=<用户数据目录>)`，并在 `window.events.initialized` 的同步回调中检查 pywebview 实际选择的 renderer 严格等于 `edgechromium`；任何其他值立即返回 `False` 取消窗口创建并进入换密钥回退。`gui` 参数只表达首选项，不作为禁止 MSHTML 的安全保证。窗口使用系统标题栏和 EXE 图标，默认尺寸以常见桌面分辨率为基线并设置可用的最小尺寸。

理由：现有启动器已经由 Python/PyInstaller 发布，pywebview 官方支持 Windows EdgeChromium 与 PyInstaller，可在不增加 .NET SDK 和第二套浏览器运行时的情况下接入 WebView2。

备选方案：C# WinForms/WPF WebView2 需要新增 .NET SDK、项目与自包含运行时策略；原生 C++ WebView2 会引入较大的 COM/构建复杂度；Electron 会重复捆绑 Chromium 并显著扩大包体和安全面；Edge `--app` 模式无法提供同等级窗口生命周期控制。因此本轮拒绝。

### D2. 系统 Evergreen WebView2 优先，初始化失败时显式回退默认浏览器

发布包不携带 Fixed Version Runtime，也不在运行时下载或静默安装。桌面宿主以“实际 renderer 已确认为 EdgeChromium、原生 WebView2 Core 已完成初始化且安全钩子全部安装、最终 URL 已到达精确应用 origin”作为三级就绪屏障；任何一级异常或超时都由协调器请求取消初始化或销毁窗口并使 GUI 主循环有界返回。失败后先关闭旧托盘并终止原所属后端，再生成新的启动秘密、清理 ready 文件、启动并验证一个新后端，最后复用既有 `open_desktop_browser` 和同步托盘循环。回退最多重启一次，失败即进入统一清理。

无论原引导秘密是否已经换取 Cookie，回退都不复用旧 bootstrap URL。这样无需从 WebView 内部推断 token 是否消费，也不会触发一次性引导重放。桌面初始化错误只投影为稳定错误码和用户提示，不记录异常 URL、Cookie 或秘密。

理由：Microsoft 推荐多数应用使用自动安全更新的 Evergreen Runtime；绝大多数 Windows 10/11 已安装。Fixed Version 会显著扩大便携包体积，且 Windows 10 解压式应用还涉及 AppContainer ACL，违背当前轻量便携与不写安装状态的边界。换密钥重启后的显式浏览器回退既保留可用性，也避开一次性 token 的未知消费状态。

备选方案：将 Evergreen 离线安装器放入 ZIP 会扩大包体并引入安装/权限状态；缺失时直接拒绝启动会回退现有可用性；允许 pywebview 自动退到 MSHTML 会带来不受支持的旧 Web 平台与安全风险。因此本轮拒绝。

### D3. 桌面窗口和原生托盘通过有界协调器共享一个生命周期

pywebview GUI 循环必须运行在主线程。协调器使用锁保护的显式状态 `starting → gui_running ↔ hidden → exiting → stopped`，并允许 `starting/gui_running → fallback_pending → browser_running → exiting` 与任意运行态 `→ backend_stopped → stopped`。WebView2 初始化成功后，原生托盘消息循环在一个受控后台线程运行：

1. 窗口关闭事件在非显式退出状态下取消销毁并隐藏窗口。
2. 托盘“打开文枢”调用恢复/显示/聚焦同一窗口，不重新加载引导秘密。
3. 托盘“退出文枢”设置显式退出状态并销毁窗口，使 GUI 主循环返回。
4. 托盘检测后端停止时设置 `backend_stopped`，销毁窗口并由主线程显示稳定错误。
5. GUI 意外返回而托盘未请求退出时，协调器请求托盘停止；所有线程有界 join 后进入现有 finally 清理。
6. `initialized` 先验证实际 renderer；窗口以无业务 URL 的空白隐藏状态创建，`before_show` 记录原生控件建立。原生 WebView2 Core 初始化完成且安全钩子全部安装后记录 core-ready并主动加载 bootstrap；最终根页面 loaded 后记录 app-ready并显示窗口。watchdog 对每级使用单调时钟和总上限，超时后通过幂等 `request_stop(fallback_pending)` 取消或销毁窗口。
7. 托盘线程创建失败、回调抛错和消息循环异常通过线程安全结果通道回传；初始化过程中发生托盘退出或后端停止时，同一个幂等 stop 赢得状态转换，其余请求只等待清理。
8. 托盘线程有界 join 超时时记录不含路径的稳定诊断，继续执行窗口、后端、Job Object、ready 文件和锁清理，不让后台线程异常阻止进程退出。

理由：这保留现有“关闭界面但后台继续、托盘显式退出”的用户合同，同时满足 pywebview 主线程限制。协调状态集中在桌面宿主模块，`main.py` 只做启动编排。

备选方案：删除托盘并让关闭窗口直接退出会破坏已验收行为；在后台线程运行 pywebview 违反其 GUI 线程约束；运行两个互不协调的消息循环会产生幽灵托盘或无法退出。因此拒绝。

### D4. 不向 React 页面暴露 Python API，并限制窗口导航边界

创建窗口时不传 `js_api`、不调用 `window.expose`，生产态关闭 debug/remote-debugging。启动器在延迟导入 pywebview 前移除继承的 `PYWEBVIEW_LOG` 调试覆盖并把第三方 logger 钳制到非调试级别；launcher 与 pywebview 的日志、异常和用户提示统一经过秘密过滤器，覆盖原始值与 URL 编码值，且自有错误文本不拼接 bootstrap URL。首次 URL 仍为 `http://127.0.0.1:40000/desktop/bootstrap#token=...`，秘密先从浏览历史移除，再由既有页面换取 HttpOnly Cookie。桌面宿主持久数据目录位于 `%LOCALAPPDATA%\文枢\webview`，用于保持应用偏好与正常站点状态。现有 HttpOnly 会话 Cookie 是启动秘密唯一允许的受控持久化载体，页面 JavaScript不可读取；秘密不得进入应用地址、历史、日志、localStorage 或 sessionStorage，后端重启后旧 Cookie 因随机秘密变化而失效。

pywebview 的公开外链设置不足以约束同窗口导航。宿主先以无业务 URL 的空白隐藏窗口建立原生 WebView2 控件；Core ready 后、加载 bootstrap 前直接注册可取消的 `NavigationStarting` 与 `NewWindowRequested` 事件。pywebview 6.2.1 会注册其内置 `on_new_window_request`；宿主必须通过 `window.native.browser` 精确注销该处理器，确认不存在框架处理器后再安装唯一的宿主 `NewWindowRequested` 处理器。注销、确认或自有钩子安装任一步失败均视为初始化失败，不允许两个处理器并存。全部钩子安装成功后，宿主才主动加载 bootstrap URL，因此首次请求、30x 重定向和后续导航使用同一边界。主窗口只允许解析后 scheme=`http`、host=`127.0.0.1`、无 userinfo、显式 port=`40000` 的 URL。相同 origin 导航正常继续；不同 origin 的普通 `http/https` 请求取消内嵌导航后交给系统默认浏览器；`file:`、`data:`、`javascript:` 和自定义协议直接取消且不外调。重定向和新窗口使用相同判定。

全局设置显式设为 `ALLOW_FILE_URLS=False`、`OPEN_EXTERNAL_LINKS_IN_BROWSER=False`；该设置本身不作为安全边界，安全性来自对框架内置新窗口处理器的精确替换和宿主唯一处理器。只有上述原生钩子允许的外链才能调用浏览器。纯 URL 函数测试之外，冻结候选必须实际验证同窗导航、重定向和新窗口事件；每个新窗口请求只能外开一次且主窗口 URL 保持不变。

理由：现有 HTTP API 已覆盖本机能力，不需要高权限 JS 桥。限制 origin 可避免携带 pywebview 注入对象和文枢会话的窗口浏览不可信页面。

备选方案：新增 JS→Python 文件/进程桥会绕过现有 Controller/API 审计；允许任意导航会扩大桌面宿主攻击面。因此拒绝。

### D5. 显式启用并验收现有制品下载

在创建窗口前设置 `webview.settings['ALLOW_DOWNLOADS']=True`，由 EdgeChromium 下载处理显示用户可见的保存流程。Word Blob 下载和 RAR anchor 下载继续使用现有前端实现，不增加 Python 文件桥；下载路径由用户选择，不以程序目录或 `%LOCALAPPDATA%\文枢\webview` 作为静默默认输出。用户取消或下载失败不得改变案件/归档状态，候选使用 SYNTHETIC Word 与 RAR 文件验证内容、建议文件名、取消和同名冲突。

理由：pywebview 默认禁止下载，而现有核心导出依赖浏览器下载；显式启用是保持当前业务能力的必要兼容设置，继续使用浏览器安全模型也避免增加桌面特权桥。

备选方案：将所有下载改成后端原生目录写入会改变现有 API 与路径授权合同；通过 JS→Python 桥保存文件会扩大安全面。因此拒绝。

### D6. 构建显式审计冻结内容并记录全部实际依赖许可

`packaging/requirements-build.txt` 锁定 pywebview、pythonnet、CLR loader 及解析后全部实际分发依赖；`launcher.spec` 只收集 pywebview 的 EdgeChromium/WinForms 路径并显式排除 Qt、GTK、CEF、Android、Cocoa和旧 Windows 引擎。由于官方 PyInstaller hook 会收集 `webview/lib`，构建不能只依赖模块 excludes：必须解析 PyInstaller archive/TOC，核对进入 EXE 的 WebView2 interop/native loader 架构，拒绝 Qt、GTK、CEF、MSHTML/EdgeHTML、x86/ARM64 非目标资产、Fixed Runtime、下载器和调试配置。便携清单新增 launcher 运行依赖版本字段，第三方声明与许可目录覆盖 pywebview、pythonnet、CLR loader 和每个实际进入 EXE 的分发依赖。

理由：pywebview 官方说明 PyInstaller 可能收集构建环境中已安装但未使用的 GUI 框架，显式排除能控制体积、许可和攻击面。

备选方案：依赖 PyInstaller 自动分析会让构建机环境影响发布内容；为启动器建立全新虚拟环境可进一步隔离，但会扩大当前构建脚本与工具链管理，留作后续优化。因此本轮先采用显式收集/排除与产物检查。

## Risks / Trade-offs

- [部分 Windows 机器缺少 Evergreen WebView2 Runtime] → 显式提示并回退默认浏览器；真实候选分别验证可用与模拟缺失路径。
- [pywebview/pythonnet 与 PyInstaller 的冻结兼容性] → 锁定版本、审计官方 PyInstaller hook 输出，在无 Python、无 .NET SDK 和无开发依赖的 Windows 10/11 x64 环境运行冻结 EXE；CLR/pythonnet 失败走同一回退。
- [双消息循环造成竞态或幽灵托盘] → 单一协调状态、幂等退出、后台线程异常回传、有界 join，单元测试覆盖窗口关闭/托盘打开/退出/后端停止。
- [持久 WebView 数据包含会话 Cookie] → 仅位于用户数据根；Cookie仍绑定每次随机后端秘密，后端重启后旧值失效；不复制进发布包。
- [第三方依赖扩大 EXE] → 接受合理增长以获得桌面体验；显式排除无关 GUI 后端并对构建内容做清单检查。
- [外部导航钩子在不同 WebView2 版本表现有差异] → 原生可取消事件安装是 desktop-ready 前置，以固定 origin 判定和真实 Windows 同窗/重定向/新窗口冒烟验证；不依赖业务页面传入特权数据。
- [WebView2 改变目录选择框的前台 HWND 与 Z-order] → 保持既有目录授权模型，并在真实候选中验证上传报告与统一导出的选择框始终位于当前 WebView2 窗口之前。
- [默认下载关闭导致 Word/RAR 无响应] → 启动前显式启用下载，以 SYNTHETIC Word/RAR 验证保存、取消、同名冲突和文件完整性。

## Migration Plan

1. 在新分支锁定构建依赖并实现独立桌面窗口模块，不修改业务前后端。
2. 接入启动器后运行合成生命周期测试和实际 PyInstaller 构建。
3. 在当前 Windows 环境和无 Python/.NET SDK/开发依赖的干净 Windows 10/11 x64 环境验证独立窗口；通过可注入 Core/CLR 失败及真实宿主超时验证换密钥浏览器回退。
4. 新版继续使用 `%LOCALAPPDATA%\文枢` 业务数据，并新增其下 `webview` 站点数据目录；不执行数据库迁移。
5. 若候选失败，回滚桌面宿主提交或使用上一版 ZIP，即恢复默认浏览器启动；用户业务数据不受影响。

## Open Questions

- 代码签名证书仍沿用便携发布变更中的待决事项，不阻塞测试版。
- 是否未来改为安装器并随附 Evergreen Runtime，由后续独立部署决策处理；本变更保持 ZIP 和浏览器回退。
