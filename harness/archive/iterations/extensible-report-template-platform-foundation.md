# 迭代记录：可扩展报告与模板平台基础层

> 日期：2026-07-18
> 变更包：`openspec/changes/extensible-report-template-platform/`
> 范围：阶段一第一批基础实现；未归档变更包，未开始压缩、人员库或 Word 模板实现

## 完成范围

- 集中 `pipeline_mode`、运行版本和模式隔离缓存命名空间，默认 `legacy`
- 纯 Export Gate 结果模型及稳定阻断码
- `CanonicalInspectionCase`、通用 identifiers、来源与置信信息、人员快照、软件工具模型
- `CanonicalInspectionCase → InspectionReport` 兼容投影和受限旧 DTO 迁移入口
- Shadow 内存比较结果和脱敏人员顺序令牌
- 合成测试；未使用真实案件、人员、设备标识或本地绝对路径

## 验证结果

| 检查 | 结果 |
|------|------|
| 精确基础测试 | 12 passed |
| 后端全量测试 | 94 passed |
| `lint:arch` | 通过 |
| TypeScript shared/frontend typecheck | 通过 |
| `verify:docs` | 通过 |
| `verify:quick` | 通过 |
| OpenSpec strict validate | 通过 |
| `git diff --check` | 通过（仅有换行格式提示） |

## 验证中处理的问题

1. 后端服务文件名按架构命名规则调整为 `*_service.py`。
2. Shadow 比较的人员顺序改为脱敏稳定令牌，比较结果不保留人员明文。
3. 数据模型索引同步到 `openspec/specs/data-model.md`，消除文档漂移。
4. 沙箱首次运行 `verify:quick` 时 Node 访问用户目录被拒绝；按受限权限重跑后通过。
5. 临时破坏 Export Gate 的核心计算后测试按预期失败，恢复后测试通过，确认测试有效性。

## 未执行范围

阶段一剩余任务、WinRAR 执行与 `ArchiveManifest`、检查人员 Repository、照片与附件页面计划、`current-template-v1` 渲染、模板资产、前端公共契约迁移、阶段二/三能力均未实现。未执行 `git add`、commit、push 或 OpenSpec 归档。
