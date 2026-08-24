## Why

现有Legacy解析缓存只在文件大小、stat时间和文件身份发生变化时重新计算内容digest。Windows上同路径、同大小且stat元数据保持不变的内容替换可能继续命中旧digest，导致审核和后续Legacy Word输出使用旧的`InspectionReport`。这在大型报告场景中必须修复，同时不能取消已有的解析缓存命中性能。

## What Changes

- 为解析输入建立文件变化可信度模型，区分可信快速复用、已确认变化和无法证明状态。
- 在Windows NTFS且USN per-file令牌可信时，允许不重读未变化文件内容而复用已有digest。
- 在USN、Journal、权限、文件系统、平台或读取前后状态无法证明未变化时，安全降级为完整内容digest复核。
- 让Legacy动态依赖指纹路径和报告输入快照路径使用一致的可信度合同。
- 覆盖原地覆盖、原子替换、删除重建、新增/删除、路径集合变化以及TOCTOU竞态。
- 明确进程内digest缓存、磁盘解析缓存和服务重启后的首次复核边界；不提前引入不需要的跨重启令牌持久化。
- 对旧解析缓存格式实施版本失效策略，避免旧缓存被当作具备新可信度证明的记录。
- 增加Windows集成测试、非支持环境降级测试、打包EXE验证和按依赖数量/令牌查询/读取字节数统计的性能验收。
- 保持Legacy仍是唯一正式输出；不修改ArchiveContext、WinRAR、Manifest、Word、正式模板、Shadow或Canonical。

## Capabilities

### New Capabilities

- `parser-input-change-trust`: 为报告解析缓存提供平台适配的文件变化令牌、可信度判断和安全降级。

### Modified Capabilities

- `electronic-inspection-record`: 修改REQ-011解析缓存的失效和命中条件，使缓存不得因同路径同大小且stat不变的内容替换而返回旧解析结果，并补充重启、TOCTOU和不支持来源的安全语义。

## Impact

- 影响后端解析输入指纹、解析缓存校验和缓存格式版本；预计不改变解析响应DTO或正式归档DTO。
- 需要Windows API适配，优先使用标准运行时能力，不引入甲方额外安装的系统组件。
- 需要在PyInstaller/最终EXE环境验证普通授权文件、USN不可用和权限不足时的行为。
- 需要新增合成数据测试和性能基准，不使用真实案件、人员信息、设备号、绝对路径或运行产物。
- 变更独立于未提交的Phase 1A实现，必须单独审阅、验证和提交。

## Non-Goals

- 不实现解析缓存以外的通用文件监控平台。
- 不要求跨服务、跨机器或网络共享目录提供快速缓存命中。
- 不为尚不存在的需求新增长期后台监听、断点续读或复杂持久化Journal游标。
- 不修改正式ArchiveContext、WinRAR、Manifest、Word或模板链路。
- 不恢复Shadow真实样本差异治理，不进入Canonical。
