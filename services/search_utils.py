"""Search utilities for country and product filtering.

This module provides strict validation for country search inputs,
only matching valid country names, ISO codes, and phone country codes.
"""

import re
import logging


# Country data with ISO codes, phone codes, and names in zh/en
COUNTRY_DATA = {
    # ISO code -> (phone_code, zh_name, en_name, aliases_zh, aliases_en)
    'AR': ('54', '阿根廷', 'Argentina', ['阿根廷'], ['argentina', 'arg']),
    'US': ('1', '美国', 'United States', ['美国', '美利坚'], ['usa', 'united states', 'us', 'america']),
    'GB': ('44', '英国', 'United Kingdom', ['英国'], ['uk', 'united kingdom', 'britain', 'great britain']),
    'CN': ('86', '中国', 'China', ['中国'], ['china', 'cn', 'prc']),
    'JP': ('81', '日本', 'Japan', ['日本'], ['japan', 'jp']),
    'KR': ('82', '韩国', 'South Korea', ['韩国', '南韩'], ['korea', 'south korea', 'sk', 'rok']),
    'DE': ('49', '德国', 'Germany', ['德国'], ['germany', 'de']),
    'FR': ('33', '法国', 'France', ['法国'], ['france', 'fr']),
    'IT': ('39', '意大利', 'Italy', ['意大利'], ['italy', 'it']),
    'ES': ('34', '西班牙', 'Spain', ['西班牙'], ['spain', 'es']),
    'CA': ('1', '加拿大', 'Canada', ['加拿大'], ['canada', 'ca']),
    'AU': ('61', '澳大利亚', 'Australia', ['澳大利亚', '澳洲'], ['australia', 'aus', 'oz']),
    'BR': ('55', '巴西', 'Brazil', ['巴西'], ['brazil', 'br']),
    'MX': ('52', '墨西哥', 'Mexico', ['墨西哥'], ['mexico', 'mx']),
    'IN': ('91', '印度', 'India', ['印度'], ['india', 'in']),
    'RU': ('7', '俄罗斯', 'Russia', ['俄罗斯'], ['russia', 'ru']),
    'ZA': ('27', '南非', 'South Africa', ['南非'], ['south africa', 'za']),
    'NL': ('31', '荷兰', 'Netherlands', ['荷兰'], ['netherlands', 'nl', 'holland']),
    'SE': ('46', '瑞典', 'Sweden', ['瑞典'], ['sweden', 'se']),
    'NO': ('47', '挪威', 'Norway', ['挪威'], ['norway', 'no']),
    'PL': ('48', '波兰', 'Poland', ['波兰'], ['poland', 'pl']),
    'TR': ('90', '土耳其', 'Turkey', ['土耳其'], ['turkey', 'tr']),
    'SA': ('966', '沙特阿拉伯', 'Saudi Arabia', ['沙特', '沙特阿拉伯'], ['saudi arabia', 'saudi', 'sa', 'ksa']),
    'AE': ('971', '阿联酋', 'United Arab Emirates', ['阿联酋', '阿拉伯联合酋长国'], ['uae', 'united arab emirates', 'emirates']),
    'SG': ('65', '新加坡', 'Singapore', ['新加坡'], ['singapore', 'sg']),
    'MY': ('60', '马来西亚', 'Malaysia', ['马来西亚'], ['malaysia', 'my']),
    'TH': ('66', '泰国', 'Thailand', ['泰国'], ['thailand', 'th']),
    'VN': ('84', '越南', 'Vietnam', ['越南'], ['vietnam', 'vn']),
    'PH': ('63', '菲律宾', 'Philippines', ['菲律宾'], ['philippines', 'ph']),
    'ID': ('62', '印度尼西亚', 'Indonesia', ['印尼', '印度尼西亚'], ['indonesia', 'id']),
    'PK': ('92', '巴基斯坦', 'Pakistan', ['巴基斯坦'], ['pakistan', 'pk']),
    'BD': ('880', '孟加拉国', 'Bangladesh', ['孟加拉', '孟加拉国'], ['bangladesh', 'bd']),
    'EG': ('20', '埃及', 'Egypt', ['埃及'], ['egypt', 'eg']),
    'NG': ('234', '尼日利亚', 'Nigeria', ['尼日利亚'], ['nigeria', 'ng']),
    'IL': ('972', '以色列', 'Israel', ['以色列'], ['israel', 'il']),
    'GR': ('30', '希腊', 'Greece', ['希腊'], ['greece', 'gr']),
    'PT': ('351', '葡萄牙', 'Portugal', ['葡萄牙'], ['portugal', 'pt']),
    'CZ': ('420', '捷克', 'Czech Republic', ['捷克'], ['czech', 'czech republic', 'cz']),
    'AT': ('43', '奥地利', 'Austria', ['奥地利'], ['austria', 'at']),
    'CH': ('41', '瑞士', 'Switzerland', ['瑞士'], ['switzerland', 'ch']),
    'BE': ('32', '比利时', 'Belgium', ['比利时'], ['belgium', 'be']),
    'DK': ('45', '丹麦', 'Denmark', ['丹麦'], ['denmark', 'dk']),
    'FI': ('358', '芬兰', 'Finland', ['芬兰'], ['finland', 'fi']),
    'IE': ('353', '爱尔兰', 'Ireland', ['爱尔兰'], ['ireland', 'ie']),
    'NZ': ('64', '新西兰', 'New Zealand', ['新西兰'], ['new zealand', 'nz']),
    'LK': ('94', '斯里兰卡', 'Sri Lanka', ['斯里兰卡'], ['sri lanka', 'lk']),
    'HK': ('852', '香港', 'Hong Kong', ['香港'], ['hong kong', 'hk']),
    'TW': ('886', '台湾', 'Taiwan', ['台湾'], ['taiwan', 'tw']),
    'MO': ('853', '澳门', 'Macau', ['澳门'], ['macau', 'mo']),
}


# Build reverse lookup indexes
_PHONE_TO_ISO = {}
_ZH_NAME_TO_ISO = {}
_EN_NAME_TO_ISO = {}
_ZH_ALIAS_TO_ISO = {}
_EN_ALIAS_TO_ISO = {}

for iso, (phone, zh_name, en_name, zh_aliases, en_aliases) in COUNTRY_DATA.items():
    _PHONE_TO_ISO[phone] = iso
    _ZH_NAME_TO_ISO[zh_name.lower()] = iso
    _EN_NAME_TO_ISO[en_name.lower()] = iso
    for alias in zh_aliases:
        _ZH_ALIAS_TO_ISO[alias.lower()] = iso
    for alias in en_aliases:
        _EN_ALIAS_TO_ISO[alias.lower()] = iso


def is_valid_iso_code(text: str) -> bool:
    """Check if text is a valid ISO 3166-1 alpha-2 country code.
    
    Args:
        text: Input text
    
    Returns:
        bool: True if valid ISO code
    """
    normalized = text.strip().upper()
    return len(normalized) == 2 and normalized in COUNTRY_DATA


def is_valid_phone_code(text: str) -> bool:
    """Check if text is a valid phone country code.
    
    Accepts formats: +54, 54, +1, 1, etc.
    
    Args:
        text: Input text
    
    Returns:
        bool: True if valid phone code
    """
    normalized = text.strip().lstrip('+')
    return normalized.isdigit() and normalized in _PHONE_TO_ISO


def is_valid_country_name(text: str) -> bool:
    """Check if text matches a country name (zh or en) or alias.
    
    Args:
        text: Input text
    
    Returns:
        bool: True if matches a country name
    """
    normalized = text.strip().lower()
    return (normalized in _ZH_NAME_TO_ISO or 
            normalized in _EN_NAME_TO_ISO or 
            normalized in _ZH_ALIAS_TO_ISO or 
            normalized in _EN_ALIAS_TO_ISO)


def is_valid_country_query(text: str) -> bool:
    """Check if text is a valid country search query.
    
    Valid queries:
    - Country name (zh/en): "阿根廷", "Argentina"
    - ISO code: "AR", "US"
    - Phone country code: "+54", "54", "+1", "1"
    
    Args:
        text: Input text to validate
    
    Returns:
        bool: True if valid country query
    """
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    
    # Check length constraints
    if len(text) == 0 or len(text) > 30:
        return False
    
    # Check each validation type
    return (is_valid_iso_code(text) or 
            is_valid_phone_code(text) or 
            is_valid_country_name(text))


def normalize_country_query(text: str) -> str:
    """Normalize a country query for searching.
    
    Returns the normalized form that can be used for matching.
    
    Args:
        text: Input text
    
    Returns:
        str: Normalized query text
    """
    text = text.strip()
    
    # For ISO codes, return uppercase
    if is_valid_iso_code(text):
        return text.upper()
    
    # For phone codes, remove leading +
    if is_valid_phone_code(text):
        return text.lstrip('+')
    
    # For names, return lowercase
    return text.lower()


def get_country_info(text: str) -> dict:
    """Get country information from a query.
    
    Args:
        text: Country query (name, ISO code, or phone code)
    
    Returns:
        dict: Country info with keys: iso, phone, zh_name, en_name
              Returns None if not found
    """
    if not is_valid_country_query(text):
        return None
    
    normalized = normalize_country_query(text)
    iso_code = None
    
    # Try ISO code
    if normalized.upper() in COUNTRY_DATA:
        iso_code = normalized.upper()
    # Try phone code
    elif normalized in _PHONE_TO_ISO:
        iso_code = _PHONE_TO_ISO[normalized]
    # Try names and aliases
    elif normalized in _ZH_NAME_TO_ISO:
        iso_code = _ZH_NAME_TO_ISO[normalized]
    elif normalized in _EN_NAME_TO_ISO:
        iso_code = _EN_NAME_TO_ISO[normalized]
    elif normalized in _ZH_ALIAS_TO_ISO:
        iso_code = _ZH_ALIAS_TO_ISO[normalized]
    elif normalized in _EN_ALIAS_TO_ISO:
        iso_code = _EN_ALIAS_TO_ISO[normalized]
    
    if iso_code and iso_code in COUNTRY_DATA:
        phone, zh_name, en_name, _, _ = COUNTRY_DATA[iso_code]
        return {
            'iso': iso_code,
            'phone': phone,
            'zh_name': zh_name,
            'en_name': en_name
        }
    
    return None


def should_trigger_search(text: str) -> bool:
    """Determine if a text message should trigger product search.
    
    This is the main entry point for filtering search triggers.
    Only returns True for valid country queries.
    
    Args:
        text: User input text
    
    Returns:
        bool: True if should trigger search, False otherwise
    """
    result = is_valid_country_query(text)
    
    if not result:
        # Log at debug level for rejected inputs
        logging.debug(f"Search rejected for input: '{text}' (not a valid country query)")
    
    return result
