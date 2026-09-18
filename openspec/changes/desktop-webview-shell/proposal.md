## Why

当前 Windows 便携版会在系统默认浏览器中打开本地 React 页面，用户仍会看到地址栏、标签页和浏览器生命周期，产品体验不像独立桌面软件。现有 React、FastAPI、桌面会话鉴权、单实例和托盘能力已经稳定，适合在不重写业务界面的前提下增加 Windows WebView2 桌面宿主。

## What Changes

- 将便携版首次打开和托盘重新打开从系统默认浏览器改为文枢独立桌面窗口，继续加载同源的本地 React/FastAPI 应用。
- 使用 pywebview 的 Windows EdgeChromium 后端承载 WebView2，保留原生标题栏、任务栏图标、最小化/最大化、窗口尺寸与持久化浏览器存储。
- WebView2 Runtime 不可用或桌面宿主初始化失败时提供明确诊断，并显式回退到既有默认浏览器入口，保证现有便携版可用性。
- 启用受控浏览器下载，使现有 Word Blob 下载和 RAR 分卷下载继续显示保存流程；取消下载不得产生残留文件。
- 复用当前一次性引导秘密、HttpOnly 会话、固定 loopback 端口、单实例、后端 Job Object 和托盘退出清理，不向 JavaScript 暴露新的 Python 桥接 API。
- 关闭桌面窗口时隐藏到托盘而非终止后端；托盘“打开文枢”恢复同一窗口，“退出文枢”才结束桌面宿主和后端。
- 锁定并声明新增的 pywebview/pythonnet 依赖，限制 PyInstaller 只收集 Windows WebView2 所需后端，并更新便携构建及发布验证。

## Non-Goals

- 不重写 React 页面为 WPF、WinForms、Qt 或其他原生控件。
- 不引入 Electron、Tauri、在线更新、安装器、管理员权限或跨平台发布。
- 不捆绑固定版 WebView2 Runtime，也不在应用启动期间静默下载或安装运行时。
- 不新增 JavaScript 到 Python 的桌面特权桥接，不改变业务 API、数据库、Word、RAR 或报告解析合同。
- 不在本变更内改变现有原生目录选择器的授权模型。

## Capabilities

### New Capabilities

- `desktop-webview-shell`: 定义 Windows WebView2 独立窗口、浏览器安全边界、托盘/窗口生命周期和缺失运行时回退行为。

### Modified Capabilities

- `portable-windows-distribution`: 修改“受控桌面启动生命周期”，将默认浏览器主路径改为优先 WebView2 独立窗口、失败时默认浏览器回退，并使托盘恢复当前活动宿主。原活动变更包仍作为稳定实现基线，不在其中追加本次任务。

## Impact

- Windows 启动器：`packages/launcher/main.py`、`packages/launcher/windows_tray.py`，并新增高内聚桌面窗口宿主模块。
- 发布依赖与构建：`packaging/requirements-build.txt`、`packaging/launcher.spec`、`packaging/portable-manifest.json`、第三方许可声明和 `scripts/build-portable.ps1`。
- 验证：扩展启动器、托盘和便携构建测试；真实 Windows 冒烟覆盖 WebView2 窗口、回退和退出清理。
- 运行时：优先使用系统 Evergreen WebView2 Runtime；固定版运行时不进入发布 ZIP，缺失时以新启动秘密重启所属后端后回退到系统默认浏览器。
- 回滚：移除桌面宿主接线和新增依赖即可恢复当前默认浏览器启动路径，不涉及数据迁移。

## 关联结论

活动变更 `portable-windows-distribution` 与本需求共享便携启动链路，是主要关联候选；按照用户明确要求，本次仍建立独立变更包，以便将已稳定的浏览器便携版作为可回滚基线，并把 WebView2 依赖、窗口生命周期和新增安全面隔离审计。其他活动变更不涉及桌面窗口或发布宿主，因此排除。
