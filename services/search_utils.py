"""Search utilities for country and product filtering.

This module provides strict validation for country search inputs,
only matching valid country names, ISO codes, and phone country codes.
Loads comprehensive country data from data/countries.json (ISO 3166-1).
"""

import os
import json
import logging

# Load country data from JSON file
_COUNTRIES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'countries.json')

COUNTRY_DATA = {}  # iso2 -> dict with full country info
_ISO3_TO_ISO2 = {}  # iso3 -> iso2
_PHONE_TO_ISO = {}  # dial_code -> list of iso2 codes
_ZH_NAME_TO_ISO = {}  # zh name -> iso2
_EN_NAME_TO_ISO = {}  # en name -> iso2
_ZH_ALIAS_TO_ISO = {}  # zh alias -> iso2
_EN_ALIAS_TO_ISO = {}  # en alias -> iso2


def _load_country_data():
    """Load country data from JSON file and build indexes."""
    global COUNTRY_DATA, _ISO3_TO_ISO2, _PHONE_TO_ISO
    global _ZH_NAME_TO_ISO, _EN_NAME_TO_ISO, _ZH_ALIAS_TO_ISO, _EN_ALIAS_TO_ISO
    
    try:
        with open(_COUNTRIES_JSON_PATH, 'r', encoding='utf-8') as f:
            countries = json.load(f)
        
        for country in countries:
            iso2 = country['iso2']
            iso3 = country['iso3']
            dial_code = country['dial_code']
            name_en = country['name_en']
            name_zh = country['name_zh']
            aliases_en = country.get('aliases_en', [])
            aliases_zh = country.get('aliases_zh', [])
            
            # Store full country data
            COUNTRY_DATA[iso2] = country
            
            # Build ISO3 index
            _ISO3_TO_ISO2[iso3] = iso2
            
            # Build phone code index (handle multiple countries with same code)
            if dial_code not in _PHONE_TO_ISO:
                _PHONE_TO_ISO[dial_code] = []
            _PHONE_TO_ISO[dial_code].append(iso2)
            
            # Build name indexes
            _ZH_NAME_TO_ISO[name_zh.lower()] = iso2
            _EN_NAME_TO_ISO[name_en.lower()] = iso2
            
            # Build alias indexes
            for alias in aliases_zh:
                _ZH_ALIAS_TO_ISO[alias.lower()] = iso2
            for alias in aliases_en:
                _EN_ALIAS_TO_ISO[alias.lower()] = iso2
        
        logging.info(f"Loaded {len(COUNTRY_DATA)} countries from {_COUNTRIES_JSON_PATH}")
        
    except Exception as e:
        logging.error(f"Failed to load country data from {_COUNTRIES_JSON_PATH}: {e}")
        logging.error("Country search functionality will be limited")


# Load data on module import
_load_country_data()


def is_valid_iso_code(text: str) -> bool:
    """Check if text is a valid ISO 3166-1 alpha-2 or alpha-3 country code.
    
    Args:
        text: Input text
    
    Returns:
        bool: True if valid ISO code
    """
    normalized = text.strip().upper()
    if len(normalized) == 2:
        return normalized in COUNTRY_DATA
    elif len(normalized) == 3:
        return normalized in _ISO3_TO_ISO2
    return False


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
        normalized = text.upper()
        # Convert ISO3 to ISO2 if needed
        if len(normalized) == 3 and normalized in _ISO3_TO_ISO2:
            return _ISO3_TO_ISO2[normalized]
        return normalized
    
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
        dict: Country info with keys: iso2, iso3, dial_code, name_zh, name_en
              Returns None if not found
    """
    if not is_valid_country_query(text):
        return None
    
    normalized = normalize_country_query(text)
    iso_code = None
    
    # Try ISO2 code
    if normalized.upper() in COUNTRY_DATA:
        iso_code = normalized.upper()
    # Try ISO3 code
    elif len(normalized) == 3 and normalized.upper() in _ISO3_TO_ISO2:
        iso_code = _ISO3_TO_ISO2[normalized.upper()]
    # Try phone code - now returns first matching country from the list
    elif normalized in _PHONE_TO_ISO:
        iso_codes = _PHONE_TO_ISO[normalized]
        # Return first country with this phone code
        iso_code = iso_codes[0] if iso_codes else None
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
        country = COUNTRY_DATA[iso_code]
        return {
            'iso': iso_code,
            'iso2': country['iso2'],
            'iso3': country['iso3'],
            'phone': country['dial_code'],
            'zh_name': country['name_zh'],
            'en_name': country['name_en']
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
