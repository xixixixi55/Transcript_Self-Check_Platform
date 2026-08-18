## Why

当前项目依赖开发机上的 Python、Node、全局 officecli 和源码相对目录，无法作为可审计的发布物交付到干净电脑。需要提供一个全量 Windows x64 便携 ZIP，使用户只需解压、独立安装 WinRAR 并双击 `文枢.exe` 即可使用，同时让程序升级不覆盖案件数据。

## What Changes

- 新增 Windows x64 全量便携发布流水线，生成包含启动器、冻结后端、生产前端、内置模板、私有 Node/officecli 运行时和完整 HashMyFiles 分发文件的 ZIP。
- 新增 `文枢.exe` 启动入口，负责单实例、后端生命周期、健康检查、浏览器打开、失败诊断和退出清理。
- 将程序只读资源、持久数据、大文件工作区、日志和备份路径显式分离；案件数据统一保存在 `%LOCALAPPDATA%\文枢`，不写入解压目录。
- 生产后端从同一随机 loopback 地址提供前端和 API，并使用每次启动的桌面会话秘密限制本地 API 访问。
- 保留 officecli 正式能力，但发布版只调用包内固定 Node/officecli，不依赖全局 PATH 或联网安装。
- WinRAR 继续作为用户独立安装的外部前置条件；缺失时应用可启动并明确阻止 RAR/统一导出能力，安装后重启即可恢复完整功能。
- 新增发布清单、文件哈希、第三方许可和干净 Windows 环境验收入口，发布包不得包含案件、数据库、生成输出或开发配置。

## Non-Goals

- 不捆绑、静默安装或重新分发 WinRAR。
- 不引入 Electron/Tauri 桌面渲染壳；界面继续由默认浏览器承载。
- 不实现在线自动更新、遥测、云同步或跨平台发布。
- 不改变 RAR 正式归档格式、现有报告业务模型或 Word 模板语法。
- 不把用户数据做成随 ZIP 移动的相对目录模式。

## Capabilities

### New Capabilities

- `portable-windows-distribution`: 定义 Windows x64 全量便携包、启动器、运行时资源、数据隔离、WinRAR 前置检查和发布验证合同。

### Modified Capabilities

- 无。现有电子检查笔录、Word 和 RAR 业务行为保持不变；本变更只提供这些能力的可部署运行容器。

## Impact

- 发布/工具层：新增 `packages/launcher/`、`packaging/` 和发布构建脚本；引入 PyInstaller 构建依赖及固定版本的私有 Node/officecli 运行时采集。
- Layer 20：新增统一运行时路径与第三方工具解析，修改 HashMyFiles 及持久目录定位。
- Layer 21：修改组合根、officecli 调用和运行就绪投影以消费统一路径，不绕过 Repository。
- Layer 23：生产模式增加静态前端、loopback 会话鉴权、就绪握手和 SPA fallback；开发模式保持既有 Vite 代理。
- 数据：不改变 SQLite 业务 schema；默认数据根继续使用 `%LOCALAPPDATA%\文枢\data`，上传/输出/日志/备份从程序目录迁出。
- 第三方：包内包含 Python 运行时、Node、officecli 与 HashMyFiles；WinRAR仅检测外部安装。发布前必须完成许可清单和资产白名单检查。
- 回滚风险：程序版本可并存，但新旧版本不得同时运行；若未来业务 schema 迁移，仍遵守现有数据库兼容和备份规则。
