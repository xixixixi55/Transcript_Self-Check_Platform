## Context

开发态由 Vite `localhost:30000` 代理到 Uvicorn `localhost:30010`，后端资源通过源码层级和全局 PATH 定位。SQLite 已默认进入 `%LOCALAPPDATA%\文枢\data`，但上传、输出、模板和第三方工具仍混合了源码相对路径。目标发布物必须在干净 Windows 10/11 x64 上离线启动，保留 officecli，且 WinRAR 由用户按官方许可独立安装。

本变更跨越发布工具、Layer 20/21/23 和进程安全边界，属于重大部署变化。业务 API、报告模型、RAR 格式和模板语法保持不变。

## Goals / Non-Goals

**Goals:**

- 生成一个解压即用的 Windows x64 ZIP；安装 WinRAR 后双击 `文枢.exe` 可使用全部正式能力。
- 包内提供 Python 后端、Node/officecli、生产前端、模板和 HashMyFiles，不读取全局开发工具。
- 程序目录只读，用户数据、工作文件、日志和备份进入 `%LOCALAPPDATA%\文枢`。
- 启动器托管单个后端实例，等待健康检查后打开浏览器，并在退出/失败时安全清理。
- 生产页面与 API 同源且只监听 loopback，以启动秘密拒绝其他本地浏览器/进程的未授权 API。
- 发布流水线可重复、可校验，拒绝把案件或生成输出带入 ZIP。

**Non-Goals:**

- 不捆绑 WinRAR，不替换 RAR 格式。
- 不实现 Electron、在线更新、系统服务或管理员级安装。
- 不改变业务数据库 schema 或把用户数据放回程序目录。
- 不支持 Windows x86、macOS 或 Linux 发布。

## Decisions

### D1. 使用 ZIP + 原生启动器，而不是安装器或 Electron

发布物为版本化 ZIP，顶层 `文枢.exe` 启动冻结后端并打开系统默认浏览器。这样满足用户“解压、安装 WinRAR、双击 EXE”的操作合同，并保留当前浏览器 UI。

备选方案：NSIS 安装器会写安装状态且不符合最终解压口径；Electron会引入第二套浏览器运行时和新的安全面，因此本轮拒绝。

### D2. 后端采用 PyInstaller onedir，启动器采用独立 windowed EXE

FastAPI 后端使用 onedir，避免 onefile 每次启动解压大量依赖。启动器负责选取端口、生成秘密、设置运行环境、读取就绪握手和打开浏览器；构建时可由 PyInstaller分别生成 launcher和backend。

备选方案：依赖系统 Python无法满足干净电脑；单个巨型 onefile会增加启动延迟、临时目录和杀毒误报风险，因此拒绝。

### D3. 引入中立 RuntimePaths 作为所有文件系统根的唯一来源

Layer 20 的运行时路径模块按显式环境覆盖、冻结包资源根、源码开发根的顺序解析只读资源；数据根按显式覆盖或 `%LOCALAPPDATA%\文枢` 解析。组合根把路径注入 Repository/Service，业务模块不自行推导仓库层级。

程序资源包括 `web`、`word_templates`、`tools/hashmyfiles`、`runtime/node` 和 `tools/officecli`。持久目录包括 `data`、`workspace/uploads`、`workspace/output`、`logs` 和 `backups`。

备选方案：继续依赖 `__file__.parents[n]` 在 PyInstaller布局中脆弱；以当前工作目录为根会把数据写入只读/可删除的程序目录，因此拒绝。

### D4. officecli作为包内私有Node工具保留

发布脚本复制固定版本的官方 Node Windows x64 运行时和锁定的 officecli 包及其生产依赖。后端使用显式的 `node.exe + officecli入口` 参数数组调用，不修改系统 PATH、不访问网络、不执行全局npm命令。开发态允许显式覆盖或全局发现作为兼容路径。

备选方案：删除回退能力不符合用户要求；要求用户安装Node/officecli不符合干净电脑合同，因此拒绝。

### D5. FastAPI生产态同源托管SPA并要求桌面会话秘密

启动器先保留loopback端口、生成高熵秘密并通过继承环境启动后端。后端仅绑定 `127.0.0.1`，对 `/api` 和受保护下载校验秘密；启动器用秘密完成就绪探测并通过带一次性引导片段的本地入口建立HttpOnly会话，随后打开普通SPA地址。开发态未设置桌面发布标志时保持现有Vite/CORS行为。

备选方案：固定端口易冲突；仅loopback仍允许本机其他进程调用API；把秘密永久放入URL会进入浏览历史，因此拒绝。

### D6. WinRAR仅作外部前置条件，缺失时安全降级

发布包不包含WinRAR。启动和非RAR功能不因缺失而失败；现有 readiness 与归档门控返回稳定不可用状态，界面说明需独立安装。重启后按配置、环境、PATH和标准安装位置重新发现。

备选方案：捆绑 `rar.exe` 或试用安装包不满足其再分发许可；改用7-Zip会改变正式归档格式，因此拒绝。

### D7. 发布包由白名单清单生成并在干净目录验收

构建脚本只从声明的构建输出和正式资源组装 staging，生成 `manifest.json`、SHA-256和第三方通知，再压缩。脚本拒绝数据库、日志、上传、输出、测试缓存和真实案件模式。真实发布 ZIP 保持git忽略。

备选方案：直接压缩仓库会携带源码、node_modules、测试和本机数据，违反资产政策，因此拒绝。

### D8. 使用原生 Windows 托盘承载启动器生命周期

启动器在后端就绪并首次打开浏览器后创建通知区域图标，通过原生 Win32 消息循环提供“打开文枢”和“退出文枢”。托盘复用 PyInstaller EXE 内嵌的多尺寸图标，不增加运行时图像依赖；“打开文枢”只访问当前 loopback 应用地址，“退出文枢”才结束消息循环并进入既有进程树清理。后端意外退出时托盘同步撤销并显示明确失败提示。

备选方案：继续用模态 MessageBox 会长期占用桌面且关闭即退出；引入 pystray/Pillow 会扩大冻结依赖和发布面；无退出入口的纯后台进程会让用户难以安全释放单实例锁，因此均拒绝。

### D9. 原生文件夹选择框绑定触发时的前台窗口

报告目录和导出目录仍由后端启动 Windows `FolderBrowserDialog`，以保持本地路径授权且不经浏览器复制大文件。PowerShell STA 进程在显示对话框前捕获当前前台 HWND，通过 `IWin32Window` 包装器将该窗口作为跨进程 owner；对话框因此进入触发浏览器的 owned-window Z-order。既有 HWND 枚举和置顶提升保留为兜底，并分别记录 owner 捕获、置顶和前台激活结果。

备选方案：浏览器目录上传无法返回可授权的绝对本机路径，不能支撑大报告目录和导出目录；只调用 `SetForegroundWindow` 受 Windows 前台激活限制且目标窗口没有浏览器 owner，已在部署机出现高概率被覆盖，因此拒绝。

### D10. 运行时完整性校验采用“必需文件强校验、额外文件脱敏告警”

启动器继续使用内嵌 SHA-256 清单逐项校验全部正式文件：清单不可用、必需文件缺失、清单文件被修改或程序目录含符号链接时保持 fail-closed。清单外普通文件不再进入启动拒绝条件；启动器只在 `%LOCALAPPDATA%\文枢\logs\launcher.log` 追加稳定告警码和额外文件数量，不记录文件名或绝对路径。

放宽额外文件不改变程序目录只读合同。硬件设备配置改用 `RuntimePaths.data_root`，用户数据配置缺失时初始化默认值；仅为修复旧版本错误落盘，允许在目标配置尚不存在时一次性读取并规范化迁移旧程序目录中的 `app/data/hardware_devices.json`。之后所有增删改只写用户数据根。

备选方案：彻底移除清单会失去缺失、损坏和意外替换诊断；只为 `hardware_devices.json` 增加程序目录例外会继续依赖可写解压目录并在并排升级时丢失配置，因此均拒绝。

## Risks / Trade-offs

- [PyInstaller/Node/HashMyFiles可能触发杀毒误报] → 使用固定供应链、哈希清单、代码签名和干净VM Defender验收；不压缩自有二进制。
- [便携包体积增大] → 接受以换取零Python/Node前置；on-dir内容由外层ZIP统一压缩。
- [WinRAR未安装导致功能不完整] → 首启明确诊断，非RAR能力继续可用；完整验收要求先独立安装WinRAR。
- [本地HTTP仍有本机攻击面] → 随机端口、loopback、短期引导秘密、HttpOnly会话、严格CSP和单实例锁。
- [大容量工作区占满系统盘] → 默认进入LocalAppData但复用现有资源准入；后续可在独立变更中提供工作区设置UI。
- [旧数据被新版迁移后难以回退] → 当前变更不新增schema；启动器仍在版本变化前记录备份入口，未来迁移沿用数据库版本门控。
- [officecli私有依赖许可或入口变化] → 发布前冻结确切版本、保留许可、执行真实create/batch/save烟雾测试。

## Migration Plan

1. 发布脚本在开发机生成全量ZIP，不修改现有部署数据。
2. 用户关闭旧版，将新ZIP解压到新的版本目录，不覆盖旧程序。
3. 首次启动取得部署锁，使用同一 `%LOCALAPPDATA%\文枢` 数据根并验证数据库兼容性。
4. 健康检查成功后进入新版；失败时关闭新版并继续使用旧目录。
5. 只有在确认新版未执行不兼容数据库迁移时才允许回到旧版；本变更本身不产生schema迁移。

## Open Questions

- 代码签名证书和正式发布者名称由发布负责人在候选冻结前提供；无证书时测试版必须明确标记未知发布者风险。
- WinRAR许可证采购和目标机器授权由使用方负责，不进入文枢发布包。
