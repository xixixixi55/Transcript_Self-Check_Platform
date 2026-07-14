"""
Layer 22: BE_Controllers — 请求处理层

每个 Controller 处理一个资源的 HTTP 请求：
- 参数校验（Pydantic 模型）
- 调用 Service 层执行业务逻辑
- 构造 HTTP 响应
"""
