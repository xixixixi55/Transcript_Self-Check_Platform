"""报告字段的跨入口默认值与规范化规则。"""

DEFAULT_DATA_SUMMARY = "即时通讯、手机信息"
DEFAULT_DOCUMENT_NUMBER = "SYN-TEST〔2026〕000号"
DEFAULT_INSPECTION_PLACE = "合成检验鉴定中心"
DEFAULT_INSPECTION_METHOD = "采用 GA/T 1069-2021《法庭科学电子物证手机检验技术规范》进行检查。"
DEFAULT_HARDWARE_DEVICE = "美亚FL-901手机取证塔"
DEFAULT_INSPECTION_REQUIREMENT = "上述检材内电子数据的提取、固定和恢复"


def normalize_data_summary(value) -> str:
    """空值统一使用甲方要求的默认摘要，非空值保留并去除首尾空格。"""
    if value is None:
        return DEFAULT_DATA_SUMMARY
    normalized = str(value).strip()
    return normalized or DEFAULT_DATA_SUMMARY
