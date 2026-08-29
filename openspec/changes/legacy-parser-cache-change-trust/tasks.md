## 1. 合同和可观测性基础

- [ ] 1.1 在 `packages/backend/app/repository/` 中增加内部文件变化信任状态、不透明原因码、令牌模式版本和指标 DTO，不暴露绝对路径；验证导入和架构层检查。
- [ ] 1.2 定义由 `packages/backend/app/repository/filesystem_identity_repository.py` 和 `packages/backend/app/repository/report_parse_input_metadata_repository.py` 共同使用的提供方边界；验证假提供方可以表达受信任、已变化和不受信任结果。
- [ ] 1.3 在 `tests/test_filesystem_identity_repository.py` 和 `tests/test_report_parse_input_repository.py` 增加确定性合成测试，覆盖大小/stat 相同的替换、文件标识替换、删除后重建、读取失败和成员关系变化。

## 2. Windows NTFS 变化令牌适配器

- [ ] 2.1 在 `packages/backend/app/repository/` 下新建后端 Repository 模块，实现延迟加载的 Windows 适配器，使用逐文件 USN 数据及卷和 Journal 标识；验证普通已授权合成文件返回稳定令牌。
- [ ] 2.2 将不支持的文件系统、网络/移动/云来源、权限、API、Journal 重建、Journal 缺口和文件缺失情况映射为 `untrusted`，且不记录路径；验证原因码和隐私测试。
- [ ] 2.3 增加 Windows 集成覆盖：使用恢复后的 stat 元数据原地覆盖、原子替换、删除后重建、文件增删和多依赖中一项变化；验证不需要固定休眠或重试循环。
- [ ] 2.4 增加非 Windows 或提供方不可用的测试替身，并验证完整内容回退仍可用，不会阻止解析。

## 3. TOCTOU 安全的内容验证

- [ ] 3.1 更新 `packages/backend/app/repository/filesystem_identity_repository.py` 中的内容摘要路径，以捕获并比较读取前/后的标识和变化令牌；验证变化中的文件绝不发布摘要。
- [ ] 3.2 在 Parser 缓存边界为 `input_changed_during_read` 和读取错误增加有界失败语义；验证绝不返回过时缓存的 `InspectionReport` 数据。
- [ ] 3.3 在 `packages/backend/app/repository/report_parse_input_metadata_repository.py` 增加候选和选定依赖集的目录成员关系校验；验证新增、删除、类型变化和目录缺失会安全失效。

## 4. 集成两条 Parser 缓存路径

- [ ] 4.1 将信任提供方集成到 `packages/backend/app/services/report_parser_service.py` 使用的 Legacy 动态依赖路径；验证未变化的受信任依赖避免完整内容重读。
- [ ] 4.2 将同一合同集成到 `packages/backend/app/repository/report_parse_input_metadata_repository.py` 和 `packages/backend/app/repository/report/report_parse_input_repository.py`；验证两条路径产生相同的已变化/不受信任语义。
- [ ] 4.3 保持 `packages/backend/app/services/report_parsing_cache_service.py` 与 Archive/Manifest Repository 分离；验证 Parser 缓存命中绝不执行 WinRAR 或提供归档证据。
- [ ] 4.4 在 `tests/test_report_parsing_cache.py`、`tests/test_report_parse_cache_metadata.py`、`tests/test_report_parse_cache_lifecycle.py` 和 `tests/test_report_parser_service.py` 增加端到端 Parser 缓存测试；验证来源替换后旧字段无法保留。

## 5. 缓存格式和重启边界

- [ ] 5.1 在 `packages/backend/app/repository/report_parsing_cache_models.py` 和 `packages/backend/app/repository/report_parsing_cache_repository.py` 增加 `input_trust_schema` 处理；验证缺少该字段的记录复用前要求完整验证。
- [ ] 5.2 进程本地令牌保持瞬态，服务重启后要求完整内容验证；验证重启测试不信任重启前内存状态。
- [ ] 5.3 增加格式错误、旧版本、部分写入和缓存迁移测试；验证无效缓存记录变为未命中，且解析缓存清理不删除 RAR、Manifest、DOCX 或来源文件。

## 6. 性能和打包部署验证

- [ ] 6.1 为 13,000 个以上依赖增加仓库外或被忽略的合成基准工具；验证其记录依赖数、stat 次数、令牌查询、读取文件/字节数、摘要重算、解析构建、冷/热/重启及单文件变化成本。
- [ ] 6.2 对等价合成输入运行相同 Parser/API 调用链；只有文件数和缓存状态匹配时才与既有约 366ms/450–492ms 测量比较；验证不根据直接 IOCTL 与完整 API 时序得出结论。
- [ ] 6.3 构建最终 PyInstaller/EXE 形态并运行普通 NTFS、权限拒绝、不受支持提供方和 API 失败场景；验证回退解析成功且诊断不含绝对路径。
- [ ] 6.4 运行定向 Parser、归档、Manifest、Word 安全门控、架构、类型、文档和仓库资产检查；验证 ArchiveContext、WinRAR、Manifest、Word、模板、Shadow 和 Canonical 保持不变。

## 7. 发布门控和回滚

- [ ] 7.1 增加安全配置开关，在保留完整内容验证的同时禁用快速令牌复用；验证关闭快速路径不会重新引入仅凭 stat 的缓存命中。
- [ ] 7.2 对新的 Level 3 变更执行独立代码审查，并与 Phase 1A 工作树分开检查暂存白名单；验证不包含 Phase 1A 文件或运行时产物。
- [ ] 7.3 请求必需的完整 Harness 执行确认，只在批准后运行完整 Harness，并记录全部失败和警告；验证不隐藏无关或新增失败。
- [ ] 7.4 在受支持和不受支持的部署环境完成手工验收；只有 Parser 缓存正确性和性能合同有证据时才将任务标为完成。回滚应禁用快速复用或隔离 Parser 缓存记录，绝不能删除正式归档输出。
