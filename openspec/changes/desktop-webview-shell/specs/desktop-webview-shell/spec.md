## ADDED Requirements

### Requirement: Windows 独立桌面窗口

Windows x64 便携版 MUST 在后端就绪后优先使用 EdgeChromium WebView2 创建标题为“文枢”的独立可缩放窗口，并在该窗口中加载现有同源 React/FastAPI 应用。桌面宿主 MUST 使用系统原生窗口边框和发布 EXE 图标，不得显示浏览器地址栏、标签页或书签栏，也不得要求重写现有业务页面。

#### Scenario: 正常打开桌面窗口

- **WHEN** 用户双击 `文枢.exe`，发布资源完整、后端就绪且系统 WebView2 Runtime 可用
- **THEN** 系统只创建一个文枢桌面窗口并加载 `http://127.0.0.1:40000` 的现有应用
- **AND** 窗口支持任务栏显示、最小化、最大化和受控最小尺寸
- **AND** 系统不得同时打开默认浏览器中的第二份文枢页面

#### Scenario: 托盘重新打开已有窗口

- **WHEN** 桌面窗口已创建且用户通过托盘选择“打开文枢”
- **THEN** 系统恢复并聚焦同一个桌面窗口
- **AND** 系统不得创建第二个 WebView2 窗口或启动第二个后端

### Requirement: 窗口与后端生命周期一致

桌面窗口、系统托盘、单实例锁和所属后端 MUST 由同一启动器生命周期协调。用户关闭窗口 MUST 隐藏到托盘并保持后端运行；只有托盘“退出文枢”、后端意外终止或启动失败才结束桌面宿主并进入现有进程树清理。

#### Scenario: 关闭窗口隐藏到托盘

- **WHEN** 用户点击桌面窗口关闭按钮且没有发起显式退出
- **THEN** 窗口隐藏且后端、桌面会话、托盘和单实例锁继续有效
- **AND** 用户可通过托盘恢复原窗口和原有审核状态

#### Scenario: 托盘显式退出

- **WHEN** 用户在托盘菜单选择“退出文枢”
- **THEN** 系统关闭桌面窗口、移除托盘图标、终止启动器拥有的后端进程树并释放单实例锁

#### Scenario: 后端意外停止

- **WHEN** 桌面窗口运行期间所属后端意外退出
- **THEN** 系统关闭桌面窗口和托盘，并显示不含敏感路径或启动秘密的稳定错误提示

### Requirement: 桌面会话安全边界

WebView2 宿主 MUST 复用现有固定 loopback 端口、一次性启动秘密和 HttpOnly 桌面会话，不得向页面新增 Python/.NET 特权桥接 API。生产态 MUST 禁用调试模式和远程调试，并限制主窗口承载文枢 loopback 页面；外部链接 MUST 交由系统默认浏览器处理。

#### Scenario: 安全建立桌面会话

- **WHEN** 启动器首次创建 WebView2 窗口
- **THEN** 窗口使用含一次性片段秘密的既有 `/desktop/bootstrap` 入口建立会话
- **AND** 引导完成后的应用地址、浏览历史、日志、localStorage 和 sessionStorage 不得记录启动秘密
- **AND** 现有 HttpOnly 桌面会话 Cookie 是唯一允许的受控持久化载体，页面 JavaScript 不得读取该值，后端重启后旧值必须失效
- **AND** 页面只能通过既有 HTTP API 使用本机能力

#### Scenario: 外部导航

- **WHEN** 文枢页面请求打开非 `http://127.0.0.1:40000` 的外部地址
- **THEN** 桌面宿主不得在具有文枢会话的主窗口中承载该地址
- **AND** 只有明确的 `http` 或 `https` 外部链接由系统默认浏览器打开
- **AND** `file:`、`data:`、`javascript:`、带用户信息的 URL 和自定义协议必须被直接拒绝

### Requirement: 受控桌面下载

WebView2 宿主 MUST 显式启用下载，使现有前端触发的 Word Blob 和 RAR 分卷下载进入用户可见的保存流程。下载不得静默写入程序目录或 WebView 数据目录；用户取消、同名冲突或下载失败 MUST 保持明确且不得留下被误认为完整制品的文件。

#### Scenario: 保存 Word 与 RAR 制品

- **WHEN** 用户在桌面窗口中下载已生成的 Word 文书或 RAR 分卷
- **THEN** WebView2 显示受控保存流程并按现有文件名建议保存到用户选择的位置
- **AND** 保存后的文件内容与后端响应一致且可由现有校验方式读取

#### Scenario: 用户取消下载

- **WHEN** 用户在保存流程中取消 Word 或 RAR 下载
- **THEN** 桌面应用继续运行且不产生完整文件名对应的残缺制品

### Requirement: WebView2 不可用时保持可用

桌面宿主 MUST 显式请求 EdgeChromium 渲染器，不得静默降级到 IE/MSHTML 等旧引擎。系统 WebView2 Runtime 缺失或桌面宿主初始化失败时，启动器 MUST 显示明确诊断并回退到既有默认浏览器入口，同时保留托盘、单实例、会话鉴权和后端清理合同。

#### Scenario: WebView2 Runtime 缺失

- **WHEN** 后端已经就绪但 EdgeChromium WebView2 无法初始化
- **THEN** 系统提示桌面窗口不可用并说明已改用默认浏览器
- **AND** 系统关闭失败的窗口与托盘、终止原所属后端，并以新的启动秘密有界重启一次后端
- **AND** 系统通过新后端的一次性引导入口只打开一个浏览器页面，无论原秘密是否已被消费都不得重放
- **AND** 系统不得启动旧版嵌入式浏览器引擎或泄露启动秘密

#### Scenario: 浏览器回退也失败

- **WHEN** WebView2 初始化失败且系统默认浏览器也无法打开
- **THEN** 启动器按既有启动失败语义停止并清理其拥有的后端、托盘状态和单实例锁

#### Scenario: WebView2 初始化超时

- **WHEN** 原生窗口已创建但 WebView2 Core 或最终应用页未在时限内就绪
- **THEN** 协调器销毁空白窗口并使 GUI 主循环有界返回
- **AND** 系统不得遗留幽灵窗口、托盘线程或继续占用旧启动秘密的后端

### Requirement: 可审计的桌面宿主发布

便携构建 MUST 锁定桌面宿主及其 Windows 运行依赖，PyInstaller MUST 排除未选用的 Qt、GTK、CEF 和旧浏览器后端，并在第三方声明中记录新增组件。发布 ZIP MUST NOT 捆绑固定版 WebView2 Runtime、运行时下载器、开发工具、调试配置或用户 WebView 数据。

#### Scenario: 桌面宿主构建

- **WHEN** 构建 Windows x64 便携候选
- **THEN** `文枢.exe` 包含运行 EdgeChromium 宿主所需的锁定依赖和发布图标
- **AND** 构建检查通过 PyInstaller archive/TOC 确认未收集未使用的 GUI/浏览器后端、非 x64 原生资产、固定版 Runtime、下载器或调试配置，且发布白名单仍通过

#### Scenario: 真实 Windows 冒烟

- **WHEN** 在装有 Evergreen WebView2 Runtime 的 Windows 10/11 x64 环境运行候选
- **THEN** 独立窗口完成启动、关闭隐藏、托盘恢复和显式退出流程
- **AND** 在模拟 WebView2 不可用时默认浏览器回退及清理流程通过

#### Scenario: 干净目标机兼容

- **WHEN** 冻结候选在没有 Python、.NET SDK 和开发依赖的干净 Windows 10/11 x64 环境运行
- **THEN** 已安装 Evergreen WebView2 Runtime 时桌面窗口正常启动
- **AND** WebView2、CLR 或 pythonnet 初始化不可用时进入同一有界浏览器回退，不得卡在空白窗口
