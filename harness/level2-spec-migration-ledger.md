# Level 2 Living Spec 迁移台账

本台账只记录历史活跃 Level 2 变更包的迁移状态，不改变已完成的分级结论。新建 Level 2 不得以本台账代替 delta spec。

迁移顺序统一为：`delta spec → 核对实现 → sync → 检查 living spec`。只有已完整同步的历史包才允许记录 `reconciled` 例外；不会为了通过门控伪造可重复同步的 delta。

| 变更包 | 历史分类 | 处理 | 当前状态与证据 |
|---|---|---|---|
| `case-shared-defaults` | 已完整同步 | 不新增同义 delta；核对主规格和数据模型 | `reconciled`：`electronic-inspection-record` REQ-007、`data-model.md` SharedDefaults |
| `report-parsing-cache-management` | 已完整同步 | 保留 T9 living spec 同步记录；不重复写入 Requirement | `reconciled`：`electronic-inspection-record` REQ-011/REQ-012 |
| `export-name-and-datetime-controls` | 历史未同步 | 以 MODIFIED delta 补日期精度、闰年校验、时间先后约束，再 sync | `reconciled`：`electronic-inspection-record` REQ-009 |
| `demo-readiness-and-source-guidance` | 历史未同步 | 以 MODIFIED delta 补最终 readiness 行为，再 sync | `reconciled`：`electronic-inspection-record` REQ-029 |
| `docx-vml-pagination` | 历史未同步 | 以 MODIFIED delta 补 VML 宿主树和分页行为，再 sync | `reconciled`：`electronic-inspection-record` REQ-009 |
| `harness-workflow-alignment` | 历史未同步 | 以 ADDED delta 固化 Level 2 工件、门控和双目录镜像规则，再 sync | `reconciled`：`harness-workflow` Level 2 workflow requirements |
| `report-request-liveness-fix` | 历史未同步 | 以 MODIFIED delta 补请求 liveness 和失败恢复行为，再 sync | `reconciled`：`electronic-inspection-record` REQ-011 |
| `review-page-modern-government-ui` | 历史未同步 | 以 MODIFIED delta 补 shell、路由和交互语义，再 sync | `reconciled`：`electronic-inspection-record` REQ-029 |
| `support-legacy-and-new-report-formats` | 历史未同步 | 以 MODIFIED delta 补格式归一化和 IMEI 优先级，再 sync | `reconciled`：`electronic-inspection-record` REQ-002/REQ-003 |
| `template-2026` | 历史未同步 | 以 MODIFIED delta 补正式模板列表和失败行为，再 sync | `reconciled`：`electronic-inspection-record` REQ-009 |

`check-docs.ts` 只检查上述状态字段、delta 工件和格式；代码与规格的完整语义一致性仍由实现核对、测试和人工 review 负责。
