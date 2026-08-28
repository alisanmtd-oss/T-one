from __future__ import annotations

from typing import Any


MARKET_DEFAULTS: dict[str, dict[str, Any]] = {
    "US": {"country": "United States", "currency": "USD", "language": "en-US", "timezone": "America/New_York"},
    "CA": {"country": "Canada", "currency": "CAD", "language": "en-CA", "timezone": "America/Toronto"},
    "MX": {"country": "Mexico", "currency": "MXN", "language": "es-MX", "timezone": "America/Mexico_City"},
    "GB": {"country": "United Kingdom", "currency": "GBP", "language": "en-GB", "timezone": "Europe/London"},
    "DE": {"country": "Germany", "currency": "EUR", "language": "de-DE", "timezone": "Europe/Berlin"},
    "FR": {"country": "France", "currency": "EUR", "language": "fr-FR", "timezone": "Europe/Paris"},
    "AU": {"country": "Australia", "currency": "AUD", "language": "en-AU", "timezone": "Australia/Sydney"},
    "SG": {"country": "Singapore", "currency": "SGD", "language": "en-SG", "timezone": "Asia/Singapore"},
    "MY": {"country": "Malaysia", "currency": "MYR", "language": "ms-MY", "timezone": "Asia/Kuala_Lumpur"},
    "TH": {"country": "Thailand", "currency": "THB", "language": "th-TH", "timezone": "Asia/Bangkok"},
    "VN": {"country": "Vietnam", "currency": "VND", "language": "vi-VN", "timezone": "Asia/Ho_Chi_Minh"},
    "PH": {"country": "Philippines", "currency": "PHP", "language": "en-PH", "timezone": "Asia/Manila"},
    "ID": {"country": "Indonesia", "currency": "IDR", "language": "id-ID", "timezone": "Asia/Jakarta"},
    "AE": {"country": "United Arab Emirates", "currency": "AED", "language": "ar-AE", "timezone": "Asia/Dubai"},
    "SA": {"country": "Saudi Arabia", "currency": "SAR", "language": "ar-SA", "timezone": "Asia/Riyadh"},
    "ZA": {"country": "South Africa", "currency": "ZAR", "language": "en-ZA", "timezone": "Africa/Johannesburg"},
    "BR": {"country": "Brazil", "currency": "BRL", "language": "pt-BR", "timezone": "America/Sao_Paulo"},
}


COUNTRY_ALIASES = {
    "美国": "US",
    "美区": "US",
    "usa": "US",
    "united states": "US",
    "加拿大": "CA",
    "canada": "CA",
    "墨西哥": "MX",
    "mexico": "MX",
    "英国": "GB",
    "uk": "GB",
    "united kingdom": "GB",
    "德国": "DE",
    "germany": "DE",
    "法国": "FR",
    "france": "FR",
    "澳大利亚": "AU",
    "australia": "AU",
    "新加坡": "SG",
    "singapore": "SG",
    "马来西亚": "MY",
    "malaysia": "MY",
    "泰国": "TH",
    "thailand": "TH",
    "菲律宾": "PH",
    "philippines": "PH",
    "越南": "VN",
    "vietnam": "VN",
    "印尼": "ID",
    "indonesia": "ID",
    "阿联酋": "AE",
    "uae": "AE",
    "沙特": "SA",
    "saudi": "SA",
    "南非": "ZA",
    "south africa": "ZA",
    "巴西": "BR",
    "brazil": "BR",
}


def normalize_country_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if upper in MARKET_DEFAULTS:
        return upper
    return COUNTRY_ALIASES.get(text.lower(), text)


def market_defaults(country_code: str) -> dict[str, Any]:
    code = normalize_country_code(country_code)
    defaults = MARKET_DEFAULTS.get(code, {})
    return {"country_code": code, **defaults} if defaults else {"country_code": code}
