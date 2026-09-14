# Spec: 共享数据模型

## Purpose

定义前后端共享业务数据的现行语义和兼容默认值，确保解析、审核、预览与正式文书投影使用一致的数据合同。

## Requirements

### Requirement: EvidenceItem 可提取状态推导

从原始报告解析得到的检材 MUST 默认标记为可提取，不得根据 `imei1`、`imei2` 或 `serial_number` 是否存在来决定可提取状态。缺少 `EvidenceItem.extractable` 的兼容数据 MUST 同样默认按可提取处理；用户显式保存的 `extractable` 布尔值 MUST 保持有效。IMEI 缺失、单一、重复等既有异常核对规则，以及显式无法提取状态的原因校验和文书投影 MUST 保持不变。

#### Scenario: 原始报告检材没有 IMEI 时仍默认可提取

- **WHEN** 系统从原始报告解析出一项检材，且该检材的 IMEI1、IMEI2 均为空
- **THEN** 解析结果仍将该检材标记为可提取
- **AND** 系统继续按既有规则提示 IMEI 缺失、单一或重复等异常，不因默认可提取而跳过异常核对

#### Scenario: 缺少可提取字段的兼容数据默认可提取

- **WHEN** 系统读取一项缺少显式 `extractable` 布尔值的兼容检材数据
- **THEN** 系统默认将该检材视为可提取
- **AND** 系统不得根据 IMEI 或序列号内容重新推导该状态

#### Scenario: 用户显式设为无法提取

- **WHEN** 检材已经保存显式的 `extractable: false`
- **THEN** 系统保持无法提取状态，不因 IMEI 或序列号内容重新覆盖用户选择
- **AND** 无法提取原因留空时继续进入既有待核对和导出阻止流程，填写原因后继续使用既有文书投影规则

### Requirement: 陌生报告候选与已确认 Profile 使用共享合同

前后端 MUST 使用 `ReportFieldCandidate` 表达只读发现候选，使用 `ReportProfileMapping` 表达用户确认后的相对文件、数据路径与集合锚点映射，并使用版本化 `ReportProfile` 表达可复用配置。`ReportProfileDiscovery` MUST 只包含发现会话令牌、结构指纹、候选和公开预算，不得包含报告根目录绝对路径。客户端 MUST 通过 `ReportProfileConfirmationRequest` 显式提交所选候选；未确认发现结果不得作为案件解析结果或正式导出输入。创建案件的 `SourceRecord` MUST 同时绑定 Profile ID 与精确版本。

#### Scenario: 发现响应不等于已确认配置

- **WHEN** 后端对陌生 JSON/JSONP 报告返回 `ReportProfileDiscovery`
- **THEN** 客户端只展示 `ReportFieldCandidate` 供用户选择，不自动形成 `ReportProfileMapping`
- **AND** 只有有效 `ReportProfileConfirmationRequest` 成功后才保存 confirmed `ReportProfile` 并创建案件
- **AND** 后续解析按来源记录的 Profile ID 与版本读取，不隐式选择最新版本
