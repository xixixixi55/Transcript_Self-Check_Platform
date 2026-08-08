"""Safe public messages for workbench persistence errors."""

from __future__ import annotations

_MESSAGES = {
    "SOURCE_REQUIRED": "请登记报告目录路径。",
    "SOURCE_DIRECTORY_REQUIRED": "案件来源必须是报告目录，不接受文件或压缩包。",
    "SOURCE_ARCHIVE_NOT_ALLOWED": "案件来源不接受 ZIP、RAR 或其他压缩包。",
    "SOURCE_STRUCTURE_INVALID": "所选目录不包含可识别的报告结构。",
    "SOURCE_ACCESS_DENIED": "所选目录当前无法访问。",
    "ARCHIVE_INPUT_PATH_INVALID": "所选报告目录不存在或无效。",
    "ARCHIVE_INPUT_ROOT_NOT_ALLOWED": "所选报告目录未获授权。",
    "ARCHIVE_INPUT_LINK_NOT_ALLOWED": "所选报告目录包含不支持的链接或特殊路径。",
    "ARCHIVE_INPUT_OUTPUT_OVERLAP": "所选报告目录与系统输出区域冲突。",
    "ARCHIVE_AUTHORIZATION_INVALID": "所选报告目录授权无效。",
    "ARCHIVE_AUTHORIZATION_EXPIRED": "所选报告目录授权已过期。",
    "REVISION_CONFLICT": "案件已被其他会话修改，请重新读取后再保存。",
    "LEASE_CONFLICT": "案件当前由其他编辑会话占用。",
    "LEASE_TAKEOVER_REQUIRED": "编辑租约已过期但需要确认接管。",
    "SOURCE_RESELECTION_REQUIRED": "报告来源已失效，请重新选择来源。",
    "SOURCE_REVALIDATION_PENDING": "报告来源正在等待复核，请稍后重试。",
    "ARCHIVE_ATTEMPT_NOT_ALLOWED": "当前案件不能开始新的归档尝试。",
    "ARCHIVE_ATTEMPT_REQUIRED": "归档必须通过受控准备流程创建归档尝试。",
    "ARCHIVE_ATTEMPT_BINDING_MISMATCH": "归档上下文绑定不一致，请重新确认来源和草稿。",
    "ARCHIVE_ATTEMPT_BINDING_STALE": "草稿或来源已变化，请重新确认归档。",
    "ARCHIVE_REPORT_MISMATCH": "归档报告与服务端草稿不一致，请重新读取案件。",
    "UNKNOWN_SHARED_DEFAULT_FIELD": "共享默认值字段不在允许范围内。",
    "INVALID_SHARED_DEFAULTS": "共享默认值内容无效。",
    "UNAUTHENTICATED_IDENTITY_REQUIRED": "客户端身份必须由服务端当前部署实例确认。",
    "INVALID_ARCHIVE_DECISION": "压缩决策无效，请重新选择。",
    "CASE_DELETE_FAILED": "案件删除未完成，请刷新后重试。",
    "DIRECTORY_PICKER_UNAVAILABLE": "本机文件夹选择器暂不可用，请在 Windows 桌面环境中重试。",
    "DIRECTORY_PICKER_FAILED": "本机文件夹选择未完成，请稍后重试。",
    "HASHMYFILES_NO_PARTS": "没有可供 HashMyFiles 校验的 RAR 文件。",
    "HASHMYFILES_UNAVAILABLE": "HashMyFiles 工具不可用，无法生成校验截图。",
    "HASHMYFILES_LAUNCH_FAILED": "HashMyFiles 无法启动，请检查工具配置后重试。",
    "HASHMYFILES_TIMEOUT": "HashMyFiles 校验超时，请重试。",
    "HASHMYFILES_RUN_FAILED": "HashMyFiles 校验执行失败，请重试。",
    "HASHMYFILES_OUTPUT_MISSING": "HashMyFiles 校验结果未生成，请重试。",
    "HASHMYFILES_RESULT_INVALID": "HashMyFiles 校验结果缺失或不完整，请重试。",
    "HASHMYFILES_SCREENSHOT_FAILED": "HashMyFiles 校验截图生成失败，请重试。",
    "HASHMYFILES_SCREENSHOT_MISSING": "HashMyFiles 校验截图未生成，请重试。",
    "HASHMYFILES_SCREENSHOT_INVALID": "HashMyFiles 校验截图无效，请重试。",
    "EXPORT_PUBLISH_FAILED": "统一导出文件发布失败，已保留上一版导出，请重试。",
    "EXPORT_PATH_NOT_AUTHORIZED": "导出目录授权已失效，请重新选择导出目录。",
    "EXPORT_PATH_INVALID": "导出目录不存在或不可用，请重新选择。",
    "ARCHIVE_RESULT_NOT_AVAILABLE": "归档结果尚不可导出，请刷新归档状态后重试。",
    "EXPORT_LIFECYCLE_FAILED": "文件已导出，但案件状态更新失败，请刷新后核对导出目录。",
}


def message_for_workbench_error(code: str) -> str:
    return _MESSAGES.get(code, "工作台请求未完成，请稍后重试。")
