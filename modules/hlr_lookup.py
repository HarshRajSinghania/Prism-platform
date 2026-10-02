import os
import requests
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from typing import Dict, Any, Optional
import sys
sys.path.append('..')
from config import Colors, NUMVERIFY_API_KEY, USER_AGENT
from modules import get_proxies


class HLRLookup:

    def __init__(self):
        self.api_key = NUMVERIFY_API_KEY
        self.numverify_url = "https://apilayer.net/api/validate"

    def validate_phone(self, phone: str, country_code: str = None) -> Dict[str, Any]:
        result = {
            "phone": phone,
            "valid": False,
            "carrier": None,
            "country": None,
            "region": None,
            "timezones": [],
            "line_type": None,
            "formatted": None,
            "error": None
        }

        try:
            if country_code:
                parsed = phonenumbers.parse(phone, country_code)
            else:
                if not phone.startswith('+'):
                    phone = '+' + phone
                parsed = phonenumbers.parse(phone)

            result["valid"] = phonenumbers.is_valid_number(parsed)
            result["formatted"] = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )

            result["carrier"] = carrier.name_for_number(parsed, "en")

            region_code = phonenumbers.region_code_for_number(parsed)
            result["country_code"] = region_code
            result["region"] = geocoder.description_for_number(parsed, "en")

            from phonenumbers import PhoneMetadata
            _country_names = {
                "US": "United States", "GB": "United Kingdom", "DE": "Germany",
                "FR": "France", "RU": "Russia", "CN": "China", "JP": "Japan",
                "IN": "India", "BR": "Brazil", "AU": "Australia", "CA": "Canada",
                "IT": "Italy", "ES": "Spain", "NL": "Netherlands", "SE": "Sweden",
                "NO": "Norway", "DK": "Denmark", "FI": "Finland", "PL": "Poland",
                "AT": "Austria", "CH": "Switzerland", "BE": "Belgium", "PT": "Portugal",
                "IE": "Ireland", "CZ": "Czech Republic", "GR": "Greece", "TR": "Turkey",
                "KR": "South Korea", "MX": "Mexico", "AR": "Argentina", "CO": "Colombia",
                "ZA": "South Africa", "UA": "Ukraine", "KZ": "Kazakhstan", "IL": "Israel",
                "AE": "United Arab Emirates", "SA": "Saudi Arabia", "TH": "Thailand",
                "VN": "Vietnam", "PH": "Philippines", "ID": "Indonesia", "MY": "Malaysia",
                "SG": "Singapore", "NZ": "New Zealand", "HK": "Hong Kong", "TW": "Taiwan",
            }
            result["country"] = _country_names.get(region_code, region_code or geocoder.description_for_number(parsed, "en"))

            result["timezones"] = list(timezone.time_zones_for_number(parsed))

            number_type = phonenumbers.number_type(parsed)
            type_map = {
                phonenumbers.PhoneNumberType.MOBILE: "Mobile",
                phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
                phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line or Mobile",
                phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
                phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
                phonenumbers.PhoneNumberType.VOIP: "VoIP",
                phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal",
                phonenumbers.PhoneNumberType.UNKNOWN: "Unknown"
            }
            result["line_type"] = type_map.get(number_type, "Unknown")

            if self.api_key:
                api_result = self._numverify_lookup(phone)
                if api_result:
                    result.update(api_result)

        except phonenumbers.NumberParseException as e:
            result["error"] = f"Parse error: {str(e)}"
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _http_fallback_allowed() -> bool:
        return os.getenv("NUMVERIFY_ALLOW_HTTP", "").strip().lower() in {"1", "true", "yes", "on"}

    def _numverify_lookup(self, phone: str) -> Optional[Dict]:
        params = {
            "access_key": self.api_key,
            "number": phone.replace("+", "").replace(" ", ""),
            "format": 1
        }
        urls = [self.numverify_url]
        if self._http_fallback_allowed():
            fallback = self.numverify_url.replace("https://", "http://", 1)
            if fallback not in urls:
                urls.append(fallback)

        last_error = "request failed"
        used_http = False
        for url in urls:
            transport = "http" if url.startswith("http://") else "https"
            if transport == "http":
                used_http = True
            try:
                proxies = get_proxies()
                response = requests.get(
                    url,
                    params=params,
                    timeout=10,
                    proxies=proxies,
                )
            except requests.Timeout:
                last_error = "timeout"
                continue
            except requests.RequestException as exc:
                last_error = type(exc).__name__
                continue
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue
            try:
                data = response.json()
            except ValueError:
                last_error = "invalid JSON"
                continue
            err = data.get("error") or {}
            if isinstance(err, dict) and err.get("code") == 105:
                last_error = "HTTPS not available on this plan"
                continue
            if isinstance(err, dict) and err:
                info = err.get("info") or err.get("type") or err.get("code") or "request failed"
                return self._numverify_failure(str(info), used_http)
            if data.get("valid"):
                result = {
                    "country_code": data.get("country_code"),
                    "country_name": data.get("country_name"),
                    "location": data.get("location"),
                    "carrier": data.get("carrier") or None,
                    "line_type": data.get("line_type"),
                }
                if used_http:
                    result["transport"] = "http"
                return result
            last_error = "number reported invalid"
            return self._numverify_failure(last_error, used_http)
        return self._numverify_failure(last_error, used_http)

    @staticmethod
    def _numverify_failure(reason: str, used_http: bool) -> Dict[str, Any]:
        result: Dict[str, Any] = {"numverify_error": reason}
        if used_http:
            result["transport"] = "http"
        return result
