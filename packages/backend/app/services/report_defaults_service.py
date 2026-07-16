"""报告字段的跨入口默认值与规范化规则。"""

DEFAULT_DATA_SUMMARY = "即时通讯、手机信息"


def normalize_data_summary(value) -> str:
    """空值统一使用甲方要求的默认摘要，非空值保留并去除首尾空格。"""
    if value is None:
        return DEFAULT_DATA_SUMMARY
    normalized = str(value).strip()
    return normalized or DEFAULT_DATA_SUMMARY
