## ADDED Requirements

### Requirement: Windows全量便携发布包

系统 MUST 生成一个Windows 10/11 x64全量便携ZIP；目标电脑除独立安装WinRAR外，不得要求安装Python、Node、pnpm、全局officecli、Git或项目源码。

#### Scenario: 干净电脑启动
- **WHEN** 用户在干净的Windows x64电脑解压发布ZIP、独立安装WinRAR并双击`文枢.exe`
- **THEN** 系统使用包内后端、Node、officecli、前端、模板和HashMyFiles启动完整应用
- **AND** 启动过程不得联网安装运行依赖或打开命令行窗口要求用户操作

#### Scenario: 发布包缺失必需文件
- **WHEN** 启动器发现发布清单内的后端、前端、模板、Node、officecli或HashMyFiles缺失或哈希不匹配
- **THEN** 系统拒绝启动并显示不泄露敏感路径的明确修复提示

#### Scenario: 发布目录包含清单外普通文件
- **WHEN** 启动器发现发布目录包含清单外普通文件，且清单内全部必需文件存在并通过哈希校验
- **THEN** 系统继续启动并在用户数据日志中记录不含文件名和绝对路径的脱敏告警及文件数量
- **AND** 程序目录中的符号链接仍须拒绝，清单外文件不得成为正式运行时配置或持久数据位置

### Requirement: 程序和用户数据分离

系统 MUST 将发布目录视为只读程序资源，并将数据库、案件资产、自定义模板、工作文件、日志和备份写入显式用户数据根；默认用户数据根 MUST 位于`%LOCALAPPDATA%\文枢`。

#### Scenario: 首次运行初始化数据
- **WHEN** 用户第一次从任意可读目录运行`文枢.exe`
- **THEN** 系统在用户数据根创建所需目录和SQLite数据库
- **AND** 解压目录中不得生成案件数据库、上传、归档、导出或日志

#### Scenario: 初始化和迁移硬件设备配置
- **WHEN** 用户数据根尚无`hardware_devices.json`
- **THEN** 系统在用户数据根的`data`目录初始化硬件设备配置
- **AND** 若当前程序目录存在旧版本遗留的有效设备配置，则系统一次性规范化迁移该配置；迁移后所有读写只使用用户数据根

#### Scenario: 并排升级
- **WHEN** 用户关闭旧版本并从新的解压目录启动新版本
- **THEN** 新版本读取同一用户数据根中的兼容案件数据和自定义模板
- **AND** 删除旧程序目录不得删除用户数据

### Requirement: 受控桌面启动生命周期

`文枢.exe` MUST 实施单实例控制、启动后端、等待有界健康检查、打开默认浏览器并在退出或启动失败时清理其拥有的后端进程；不得允许同一用户数据根被两个文枢版本同时运行。

#### Scenario: 正常启动
- **WHEN** 运行时资源完整且后端在时限内返回就绪
- **THEN** 启动器只打开一个文枢浏览器入口并通过系统托盘保持后端运行
- **AND** 正常运行期间不得保留要求用户一直保留的阻塞式窗口

#### Scenario: 托盘重新打开与退出
- **WHEN** 文枢已启动且用户通过托盘菜单选择打开或退出
- **THEN** “打开文枢”使用现有桌面会话重新打开应用地址，不启动第二个后端
- **AND** 只有“退出文枢”才移除托盘图标、终止启动器拥有的后端进程树并释放单实例锁

#### Scenario: 重复启动
- **WHEN** 同一用户数据根已经由一个文枢实例持有部署锁
- **THEN** 后续启动器不得启动第二个后端，并将用户引导到现有实例或显示明确提示

#### Scenario: 后端启动失败
- **WHEN** 后端退出或在健康检查时限内未就绪
- **THEN** 启动器终止其拥有的进程树、保留脱敏日志并显示启动失败提示

#### Scenario: 浏览器触发本机文件夹选择
- **WHEN** 用户从文枢浏览器页面选择报告目录或统一导出目录
- **THEN** 原生文件夹选择框以触发操作时的前台窗口为 owner 并显示在浏览器之前
- **AND** 无法取得前台 owner 时使用隐藏本机 owner 与置顶兜底，同时记录可诊断但不泄露路径的状态

### Requirement: 私有officecli运行时

发布版 MUST 通过包内固定Node运行时和锁定的officecli入口执行officecli，不得依赖系统PATH、全局npm目录或运行时下载；officecli失败 MUST 保持现有明确文档生成错误语义。

#### Scenario: 无全局Node和officecli
- **WHEN** 目标电脑未安装Node且PATH中不存在officecli
- **THEN** 包内officecli的create、batch和save烟雾操作仍成功

#### Scenario: 包内officecli损坏
- **WHEN** 包内Node或officecli入口缺失、哈希不匹配或执行失败
- **THEN** 发布预检或运行时明确失败，不得静默调用目标电脑上的未知全局版本

### Requirement: WinRAR外部前置与受控降级

发布包 MUST NOT 包含WinRAR或RAR二进制；应用 MUST 在每次启动发现用户独立安装的WinRAR。WinRAR缺失时应用仍须启动非RAR能力，但归档、完整性校验和依赖RAR的统一导出 MUST 被稳定门控。

#### Scenario: 已安装WinRAR
- **WHEN** 用户独立安装的WinRAR通过版本与分卷能力探测
- **THEN** 系统启用现有RAR归档、校验和统一导出能力

#### Scenario: 未安装WinRAR
- **WHEN** 系统未发现可用WinRAR
- **THEN** 报告解析、审核编辑、案件保存、模板管理和Word导出仍可使用
- **AND** RAR相关操作返回明确不可用状态并提示用户独立安装WinRAR后重启

### Requirement: 本地生产服务隔离

生产后端 MUST 只监听loopback随机端口，前端与API MUST 同源，API及受保护下载 MUST 拒绝没有本次桌面启动授权的请求；开发模式 MUST 保持现有Vite代理工作流。

#### Scenario: 桌面会话访问
- **WHEN** 启动器使用本次启动秘密建立受保护浏览器会话
- **THEN** SPA和API可正常访问且秘密不持久暴露在最终地址中

#### Scenario: 未授权本地请求
- **WHEN** 其他浏览器或本机进程直接请求生产API但没有有效桌面会话
- **THEN** 后端拒绝请求且不返回案件、路径或文件内容

### Requirement: 可审计发布内容

构建系统 MUST 从白名单组装发布staging并生成版本、SHA-256清单和第三方许可通知；ZIP MUST NOT 包含数据库、案件资产、上传、日志、生成输出、测试缓存、开发秘密或WinRAR。

#### Scenario: 合法发布构建
- **WHEN** 所有声明资源存在、许可材料完整且资产扫描通过
- **THEN** 构建系统生成版本化ZIP及可独立校验的SHA-256清单

#### Scenario: 禁止资产进入发布包
- **WHEN** staging包含数据库、RAR、生成DOCX、日志、环境文件或非白名单路径
- **THEN** 构建必须失败并删除或隔离未完成候选，不得发布该ZIP

### Requirement: 干净Windows候选验收

正式候选 MUST 在未安装Python、Node、pnpm、officecli和旧版文枢的Windows 10/11 x64环境验证；完整验收前由用户独立安装WinRAR，并覆盖中文用户/路径、重启、Word生成、officecli回退、RAR和统一导出。

#### Scenario: 候选完整验收通过
- **WHEN** 干净环境完成解压、WinRAR独立安装、首次启动、重启和核心业务烟雾流程
- **THEN** 发布记录包含通过结果、发布ZIP哈希和第三方版本

#### Scenario: 仅开发机验证
- **WHEN** 候选只在包含开发环境的构建机运行过
- **THEN** 系统不得将其标记为干净电脑正式发布通过
