import json
import locale
import os
import sys

import requests

WEATHERAPI_URL = "http://api.weatherapi.com/v1/current.json"
WEATHER_PATH   = "weather.json"

# Maps ISO country codes (from system locale) to country names.
# WeatherAPI.com accepts country names and resolves them automatically.
# Used when IP geolocation is unavailable (offline, rate-limited, etc.).
# To add a country: find its ISO 3166-1 alpha-2 code and add a row here.
LOCALE_COUNTRIES = {
    "CN": "China",
    "US": "United States",
    "GB": "United Kingdom",
    "JP": "Japan",
    "KR": "South Korea",
    "DE": "Germany",
    "FR": "France",
    "AU": "Australia",
    "CA": "Canada",
    "IN": "India",
    "BR": "Brazil",
    "MX": "Mexico",
    "SG": "Singapore",
    "HK": "Hong Kong",
    "TW": "Taiwan",
    "RU": "Russia",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "CH": "Switzerland",
    "AT": "Austria",
    "BE": "Belgium",
    "PL": "Poland",
    "PT": "Portugal",
    "TH": "Thailand",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "PH": "Philippines",
    "VN": "Vietnam",
    "NZ": "New Zealand",
    "ZA": "South Africa",
    "EG": "Egypt",
    "TR": "Turkey",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "IL": "Israel",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
}


def detect_city_from_ip() -> str | None:
    """
    Auto-detect the user's city from their IP address using ip-api.com.
    Free, no API key required, rate limit: 45 requests/minute.
    Returns a city name string, or None if detection fails for any reason.
    """
    try:
        response = requests.get("http://ip-api.com/json", timeout=5)
        data = response.json()
        if data.get("status") == "success":
            return data.get("city")
    except Exception:
        pass
    return None


def detect_city_from_locale() -> str | None:
    """
    Detect a representative city from the system locale setting.

    Reads the country code embedded in the locale string (e.g. 'zh_CN' → 'CN'),
    then looks it up in LOCALE_CITIES. Works completely offline — no network needed.
    Returns None if the locale is unavailable or the country isn't in the table.
    """
    try:
        lang, _ = locale.getlocale()           # e.g. 'zh_CN', 'en_US', 'ja_JP'
        if not lang:
            lang, _ = locale.getdefaultlocale()  # fallback for older Python / unset locale
        if lang and "_" in lang:
            country_code = lang.split("_")[1].upper()   # 'CN', 'US', 'JP'
            return LOCALE_COUNTRIES.get(country_code)
    except Exception:
        pass
    return None


def read_city(path: str = WEATHER_PATH) -> str | None:
    """
    Determine which city to fetch weather for.

    Priority:
      1. 'location' field in weather.json  — explicit user choice
      2. IP-based geolocation              — auto-detect when no city is saved
      3. System locale                     — country fallback when offline
                                             (e.g. zh_CN → Beijing, en_US → New York)
      4. None                              — all sources failed; caller should skip fetch
    """
    # 1. Saved city in weather.json
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            city = data.get("location", "").strip()
            if city:
                return city
    except FileNotFoundError:
        pass

    # 2. IP geolocation
    city = detect_city_from_ip()
    if city:
        print(f"  Auto-detected city from IP: {city}")
        return city

    # 3. System locale → country → representative city
    city = detect_city_from_locale()
    if city:
        print(f"  Auto-detected country from system locale: {city}")
        return city

    # All sources exhausted
    return None


def fetch_weather(city: str, api_key: str) -> dict:
    """
    Call the WeatherAPI.com API and return a dict that matches our weather.json format.

    Raises exceptions on failure — the caller is responsible for handling them:
      requests.exceptions.ConnectionError  — no internet
      requests.exceptions.Timeout          — API too slow
      requests.exceptions.HTTPError        — bad key (403), city not found (400), etc.
      KeyError                             — unexpected API response shape
    """
    params = {
        "key": api_key,
        "q":   city,
    }

    response = requests.get(WEATHERAPI_URL, params=params, timeout=10)
    response.raise_for_status()   # raises HTTPError for 4xx / 5xx responses

    data = response.json()

    return {
        "location":    data["location"]["name"],                    # city name from API
        "condition":   data["current"]["condition"]["text"].lower(), # e.g. "partly cloudy"
        "temperature": round(data["current"]["temp_c"]),            # integer °C
        "unit":        "C",
    }


def save_weather(weather: dict, path: str = WEATHER_PATH) -> None:
    """Write the weather dict to weather.json, overwriting the previous file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(weather, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    # ── API key ───────────────────────────────────────────────────────────────
    api_key = os.environ.get("WEATHERAPI_KEY", "").strip()
    if not api_key:
        print("Error: WEATHERAPI_KEY environment variable is not set.")
        print("Run:  export WEATHERAPI_KEY=your-key-here")
        print("Get a free key at: https://www.weatherapi.com/signup.aspx")
        sys.exit(1)

    # ── Detect city ───────────────────────────────────────────────────────────
    city = read_city()
    if city is None:
        print("Error: Could not determine a city from weather.json, IP, or system locale.")
        sys.exit(1)
    print(f"Fetching weather for {city}...")

    try:
        weather = fetch_weather(city, api_key)

    except requests.exceptions.ConnectionError:
        print("Error: Network connection failed. Check your internet connection.")
        sys.exit(1)

    except requests.exceptions.Timeout:
        print("Error: Request timed out. The API may be slow — try again.")
        sys.exit(1)

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code
        if code == 403:
            print("Error: Invalid API key. Check your WEATHERAPI_KEY.")
        elif code == 400:
            print(f"Error: City '{city}' not found.")
            print("Edit the 'location' field in weather.json to fix this.")
        else:
            print(f"Error: WeatherAPI returned HTTP {code}.")
        sys.exit(1)

    except KeyError:
        print("Error: Unexpected response format from WeatherAPI.")
        sys.exit(1)

    # ── Save ──────────────────────────────────────────────────────────────────
    save_weather(weather)
    print(f"  {weather['location']} · {weather['condition']} · {weather['temperature']}°C")
    print(f"Saved to {WEATHER_PATH}")


if __name__ == "__main__":
    main()
