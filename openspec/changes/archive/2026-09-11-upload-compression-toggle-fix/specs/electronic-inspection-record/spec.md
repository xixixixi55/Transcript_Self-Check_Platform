## MODIFIED: REQ-011 — 解析缓存

**Scenario: 按压缩模式复用缓存**

- WHEN 再次请求解析相同的报告目录
- AND 缓存文件存在且对应相同的 `compress` 模式
- THEN 直接返回该模式的缓存解析结果
- AND 跳过 JSON 读取和解析

**Scenario: 压缩模式变化时不复用旧缓存**

- WHEN 同一报告目录先以 `compress=true` 解析，再以 `compress=false` 解析
- THEN 第二次请求使用不压缩模式缓存或重新解析
- AND 不返回第一次解析生成的 RAR 文件信息

## MODIFIED: REQ-012 — 避免重复压缩

**Scenario: 压缩开关关闭时跳过（缓存场景）**

- WHEN `compress=false`
- AND 同一目录存在压缩模式的历史缓存或 RAR 文件
- THEN 仍跳过压缩步骤
- AND `rar_info` 返回 null
