"""
Format pipeline results for terminal/Telegram output.

All formatters produce plain-text output suitable for narrow mobile screens:
- No ASCII table borders or fixed-width padding
- No raw SQL column names
- No internal slugs (snake_case, IANA tz IDs, etc.)
- No row-count footers
- Flight/destination lists as bullet lines
"""

from __future__ import annotations

import re
from collections import defaultdict
from rdflib import Graph, Namespace

EX = Namespace("http://dataontology.example/graph/")

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SHORT = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Canonical display labels for visa policy slugs (M13)
POLICY_DISPLAY = {
    "evisa_required":              "eVisa Required",
    "e_visa_required":             "eVisa Required",
    "eta_required":                "ETA Required",
    "e_t_a_required":              "ETA Required",
    "visa_on_arrival":             "Visa On Arrival",
    "visa_not_required":           "Visa Not Required",
    "visa_required":               "Visa Required",
    "evisa_or_visa_on_arrival":    "eVisa or Visa On Arrival",
    "e_visa_or_visa_on_arrival":   "eVisa or Visa On Arrival",
    "unverified":                  "Visa status unverified",
}

# Display labels for internal column names (SQL and SPARQL)
_COL_LABELS: dict[str, str] = {
    "f_departure_airport_code":   "from",
    "f_destination_airport_code": "to",
    "f_airline_code":             "airline",
    "f_aircraft_code":            "aircraft",
    "f_currency_code":            "currency",
    "f_departure_date":           "departure",
    "f_arrival_date":             "arrival",
    "f_cabin_class":              "cabin",
    "f_trip_type":                "trip",
    "f_flight_duration":          "duration",
    "f_total_amount_fare_total":  "fare",
    "f_flight_combination":       "id",
    "avg_duration_mins":          "avg duration",
    "min_duration_mins":          "min duration",
    "flight_count":               "flights",
    "first_departure":            "first dep",
    "first_dep":                  "first dep",
    "routeKey":                   "route",
    "monthNum":                   "month",
    "transportModeName":          "transport",
    "visaRequired":               "visa req",
    "bestTimeToVisit":            "best time",
    "publicTransportWidelyUsed":  "public transport",
    "departure_month":            "month",
    "min_fare":                   "from",
    "cheapest_fare":              "from",
    # Already renamed by _friendly_columns in pipeline.py
    "currency":                   "currency",
    "min_duration":               "min duration",
    "flights":                    "flights",
}

# Intents capped at 3 results ("best single answer" queries)
_CAP_3 = {
    "cheapest_flight_on_route",
    "shortest_flight_on_route",
    "cheapest_flight_by_airline",
    "cheapest_flight_by_cabin",
}
# M6: cuisine type → 2-3 representative must-try dishes
_CUISINE_DISHES: dict[str, str] = {
    "Thai":                   "Pad Thai · Green Curry · Mango Sticky Rice",
    "Japanese":               "Sushi · Ramen · Tempura",
    "Cantonese":              "Dim Sum · Roast Duck · Wonton Noodles",
    "Hawker":                 "Hainanese Chicken Rice · Laksa · Char Kway Teow",
    "Balinese":               "Babi Guling · Nasi Campur · Satay Lilit",
    "Indonesian":             "Nasi Goreng · Rendang · Gado-Gado",
    "Javanese":               "Gudeg · Nasi Pecel · Soto Ayam",
    "Korean":                 "Korean BBQ · Bibimbap · Kimchi Jjigae",
    "Vietnamese":             "Pho · Banh Mi · Bun Bo Hue",
    "Southern Vietnamese":    "Pho · Banh Mi · Hu Tieu",
    "Mandarin":               "Peking Duck · Dumplings · Hot Pot",
    "Shanghainese":           "Xiaolongbao · Red Braised Pork · Sheng Jian Bao",
    "Beijing":                "Peking Duck · Zhajiangmian · Jiaozi",
    "Indian":                 "Butter Chicken · Biryani · Masala Dosa",
    "Maharashtrian":          "Vada Pav · Misal Pav · Pav Bhaji",
    "Malay":                  "Nasi Lemak · Satay · Rendang",
    "British":                "Fish and Chips · Full English Breakfast · Afternoon Tea",
    "Modern Australian":      "Grilled Barramundi · Pavlova · Flat White",
    "Arabic":                 "Shawarma · Kabsa · Meze Platter",
    "Turkish":                "Kebab · Baklava · Meze Platter",
    "Thai":                   "Pad Thai · Green Curry · Mango Sticky Rice",
    "German":                 "Bratwurst · Schnitzel · Pretzels",
    "French":                 "Croissant · Coq au Vin · Crème Brûlée",
    "Italian":                "Pizza · Pasta · Tiramisu",
    "Greek":                  "Moussaka · Souvlaki · Spanakopita",
    "Spanish":                "Paella · Tapas · Tortilla Española",
}


def _cuisine_with_dishes(cuisine_type: str) -> str:
    """Return 'CuisineType — Dish1 · Dish2 · Dish3' or just 'CuisineType' if no mapping."""
    dishes = _CUISINE_DISHES.get(cuisine_type)
    return f"{cuisine_type} — {dishes}" if dishes else cuisine_type


# Intents capped at 5 results
_CAP_5 = {"next_available_flight", "route_fare_options", "flights_on_date"}

def _duration_haul_label(params: dict, origin: str, date_suffix: str) -> str:
    """Return 'Short/Medium/Long-haul destinations from X' based on duration params."""
    max_d = params.get("max_duration_mins")
    min_d = params.get("min_duration_mins")
    try:
        max_d = int(max_d) if max_d is not None else None
        min_d = int(min_d) if min_d is not None else None
    except (ValueError, TypeError):
        max_d = min_d = None

    if max_d is not None and min_d is not None:
        label = f"{min_d // 60}–{max_d // 60}h flight"
    elif min_d is not None and min_d >= 480:
        label = "Long-haul"
    elif max_d is not None and max_d <= 240:
        label = "Short-haul"
    elif max_d is not None:
        label = "Medium-haul"
    else:
        label = "Short-haul"
    return f"{label} destinations from {origin}{date_suffix}"


# H1: Header templates for destination-list intents
def _dest_list_header(intent_name: str, params: dict) -> str:
    """Build a context header for destination list responses."""
    origin = params.get("origin", "")
    month = params.get("departure_month") or params.get("month_num")
    date  = params.get("departure_date") or params.get("date")
    budget = params.get("max_budget") or params.get("budget")
    curr   = params.get("currency_code", "SGD")

    date_suffix = ""
    if month:
        try:
            date_suffix = f" in {MONTH_NAMES[int(month) - 1]} 2026"
        except (ValueError, TypeError):
            pass
    elif date:
        try:
            parts = str(date).split("T")[0].split("-")
            date_suffix = f" on {int(parts[2])} {MONTH_SHORT[int(parts[1]) - 1]} {parts[0]}"
        except Exception:
            pass

    templates = {
        "all_destinations_from_origin":      f"No destination specified — showing all destinations from {origin} sorted by price{date_suffix}",
        "shortest_flight_from_origin":       f"Shortest flights from {origin}{date_suffix}",
        "destinations_by_safety_tier":       f"{_humanize(params.get('safety_tier',''))} destinations from {origin}{date_suffix}",
        "destinations_by_attraction_type":   f"{_humanize(params.get('attraction_type',''))} destinations from {origin}{date_suffix}",
        "destinations_by_travel_style":      f"{_humanize(params.get('travel_style',''))} travel from {origin}{date_suffix}",
        "flights_by_travel_style":           f"{_humanize(params.get('travel_style',''))} travel from {origin}{date_suffix}",
        "destinations_by_weather_profile":   f"Destinations from {origin} matching weather filter{date_suffix}",
        "destinations_under_budget":         f"Destinations from {origin} under {curr} {budget}{date_suffix}" if budget else f"Destinations from {origin}{date_suffix}",
        "destinations_by_budget":            f"Destinations from {origin} under {curr} {budget}{date_suffix}" if budget else f"Destinations from {origin}{date_suffix}",
        "destinations_by_continent":         f"Destinations in {_humanize(params.get('continent',''))} from {origin}{date_suffix}",
        "destinations_by_region":            f"Destinations in {_humanize(params.get('region',''))} from {origin}{date_suffix}",
        "destinations_by_duration":          _duration_haul_label(params, origin, date_suffix),
        "route_fare_options":                f"Flights from {origin} to {params.get('destination','')}{date_suffix}",
        "destinations_by_country_from_origin": f"Destinations in {_humanize(params.get('country',''))} from {origin}{date_suffix}",
        "destinations_by_festival_type":     f"{_humanize(params.get('festival_type',''))} festival destinations from {origin}{date_suffix}",
        "destinations_by_transport_mode":    f"Destinations from {origin} with {_humanize(params.get('transport_mode',''))}{date_suffix}",
        "visa_free_flights_from_origin":     f"Visa-free destinations from {origin} ({params.get('passport_country_code', '')} passport){date_suffix}",
    }
    return templates.get(intent_name, "")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _humanize(slug: str) -> str:
    """Convert snake_case / camelCase → Title Case display string."""
    if not slug:
        return ""
    s = re.sub(r"([A-Z])", r" \1", str(slug)).strip()
    s = s.replace("_", " ").replace("-", " ")
    return " ".join(w.capitalize() for w in s.split())


def _fmt_rate(rate_str) -> str:
    """
    Round exchange rate for human readability:
      > 1000 : round to nearest 10  (17199 → 17,200)
      > 10   : round to integer     (25.18 → 25)
      1–10   : 2 decimal places     (3.11)
      < 1    : 2 decimal places     (0.58)
    """
    if not rate_str:
        return ""
    try:
        r = float(rate_str)
        if r > 1000:
            rounded = round(r / 10) * 10
            return f"{rounded:,}"
        if r > 10:
            return str(round(r))
        if r >= 1:
            return f"{r:.2f}"
        return f"{r:.2f}"
    except (ValueError, TypeError):
        return str(rate_str)


def _normalise_safety(tier: str | None) -> str:
    """Capitalise safety tier consistently."""
    if not tier:
        return ""
    mapping = {
        "safe": "Safe",
        "moderate": "Moderate",
        "use caution": "Use Caution",
        "use_caution": "Use Caution",
        "high risk": "High Risk",
        "high_risk": "High Risk",
    }
    return mapping.get(tier.lower(), _humanize(tier))


def _strip_city_from_country(city: str, country: str) -> str:
    """
    Return country as-is unless it starts with the city name (e.g. 'Hong Kong SAR, China'
    for city 'Hong Kong'). In that case return the country without repetition.
    """
    if not city or not country:
        return country or ""
    if country.lower().startswith(city.lower()):
        return country  # keep full name — 'Hong Kong SAR, China' is informative
    return country


def _fmt_month(ym: str) -> str:
    """Convert 'YYYY-MM' to 'Month YYYY' (e.g. '2026-06' → 'June 2026')."""
    try:
        year, m = ym.split("-")
        return f"{MONTH_NAMES[int(m) - 1]} {year}"
    except Exception:
        return ym


def _months_to_ranges(month_nums: list[int]) -> str:
    """
    Compress sorted month numbers into compact range notation.
    [1,2,3,9,10,11,12] → 'Jan–Mar · Sep–Dec'
    [4,5] → 'Apr · May'
    """
    if not month_nums:
        return ""
    sorted_nums = sorted(set(month_nums))
    ranges: list[tuple[int, int]] = []
    start = end = sorted_nums[0]
    for m in sorted_nums[1:]:
        if m == end + 1:
            end = m
        else:
            ranges.append((start, end))
            start = end = m
    ranges.append((start, end))

    parts = []
    for s, e in ranges:
        if s == e:
            parts.append(MONTH_SHORT[s - 1])
        else:
            parts.append(f"{MONTH_SHORT[s - 1]}–{MONTH_SHORT[e - 1]}")
    return " · ".join(parts)


def _normalise_policy(slug: str) -> str:
    """Return canonical display label for a visa policy slug (M13)."""
    if not slug:
        return ""
    key = slug.lower().replace(" ", "_")
    return POLICY_DISPLAY.get(key, _humanize(slug))


def _fmt_dur(minutes) -> str:
    """Format integer minutes → '2h45m'."""
    if minutes is None or minutes == "":
        return ""
    try:
        m = int(minutes)
        return f"{m // 60}h{m % 60:02d}m"
    except (ValueError, TypeError):
        return str(minutes)


def _fmt_fare(amount, currency: str = "") -> str:
    """Format fare → 'SGD 151.50'."""
    if amount is None or amount == "":
        return ""
    try:
        prefix = f"{currency} " if currency else ""
        return f"{prefix}{float(amount):.2f}"
    except (ValueError, TypeError):
        return str(amount)


def _fmt_dt(dt_str: str) -> str:
    """Format ISO datetime '2026-05-30T07:50:00' → '30 May 07:50'."""
    if not dt_str or "T" not in str(dt_str):
        return str(dt_str) if dt_str else ""
    date_part, time_part = str(dt_str).split("T", 1)
    try:
        _, m, d = date_part.split("-")
        return f"{int(d)} {MONTH_SHORT[int(m) - 1]} {time_part[:5]}"
    except Exception:
        return str(dt_str)


def _fmt_col(key: str, value) -> str:
    """Format a column value based on its internal key name."""
    if value is None or value == "":
        return ""
    s = str(value)
    if "duration" in key.lower():
        return _fmt_dur(value)
    if key in ("f_departure_date", "f_arrival_date", "first_departure",
               "first_dep", "departure", "arrival"):
        return _fmt_dt(s)
    if key in ("f_total_amount_fare_total", "min_fare", "cheapest_fare",
               "avg_fare", "fare", "from"):
        try:
            return f"{float(s):.2f}"
        except (ValueError, TypeError):
            return s
    return s


def _rename_row(row: dict) -> dict:
    return {_COL_LABELS.get(k, k): v for k, v in row.items()}


# ---------------------------------------------------------------------------
# vacation_plan — walk the rdflib CONSTRUCT graph
# ---------------------------------------------------------------------------

def format_vacation_plan(g: Graph, params: dict, visa_rows: list[dict]) -> str:
    airport_uri = _find_airport(g, params["destination_airport_code"])
    if airport_uri is None:
        return "[ERROR] Airport not found in CONSTRUCT result — check GraphDB data."

    city_uri = g.value(airport_uri, EX.prop_inCity)
    country_uri = g.value(city_uri, EX.prop_belongsToCountry) if city_uri else None

    airport_name    = _str(g, airport_uri, EX.prop_airportName)
    airport_code    = params["destination_airport_code"]
    city_name       = _str(g, city_uri, EX.prop_cityName)
    country_name    = _str(g, country_uri, EX.prop_countryName)
    continent       = _str(g, country_uri, EX.prop_continent)
    region          = _str(g, country_uri, EX.prop_region)
    safety_tier     = _str(g, city_uri, EX.prop_safetyTier)
    solo_safe       = _bool(g, city_uri, EX.prop_soloFemaleSafe)
    cost_idx        = _str(g, city_uri, EX.prop_costOfLivingIndex)
    capital_uri     = g.value(country_uri, EX.prop_capitalCity) if country_uri else None
    capital_name    = _str(g, capital_uri, EX.prop_cityName) if capital_uri else None

    terminal_count  = _str(g, airport_uri, EX.prop_terminalCount)
    is_intl         = _bool(g, airport_uri, EX.prop_isInternational)
    has_lounge      = _bool(g, airport_uri, EX.prop_hasLounge)
    has_transit     = _bool(g, airport_uri, EX.prop_hasTransitHotel)

    lang_uri        = g.value(city_uri, EX.prop_usesPrimaryLanguage)
    language        = _str(g, lang_uri, EX.prop_languageName)
    utc_offset      = _str(g, city_uri, EX.prop_utcOffset)
    currency_uri    = g.value(country_uri, EX.prop_hasCurrency) if country_uri else None
    currency_code   = _str(g, currency_uri, EX.prop_currencyCode)
    currency_name   = _str(g, currency_uri, EX.prop_currencyName)
    exchange_rate   = _str(g, currency_uri, EX.prop_exchangeRate)

    month_filter = params.get("month_num")
    best_months, is_travel_month_best = _best_months(g, city_uri, month_filter)

    transport_modes = sorted({
        _humanize(str(g.value(t, EX.prop_transportModeName)))
        for t in g.objects(city_uri, EX.prop_hasTransportMode)
        if g.value(t, EX.prop_transportModeName)
    })
    public_transport = _bool(g, city_uri, EX.prop_publicTransportWidelyUsedInCountry)

    neighbourhoods = [
        (_str(g, a, EX.prop_subcityAreaName), _str(g, a, EX.prop_areaSummary))
        for a in g.objects(city_uri, EX.prop_hasSubcityArea)
        if g.value(a, EX.prop_subcityAreaName)
    ]
    neighbourhoods.sort(key=lambda x: x[0] or "")

    cuisines = sorted({
        _humanize(str(g.value(c, EX.prop_cuisineType)))
        for c in g.objects(city_uri, EX.prop_hasCuisine)
        if g.value(c, EX.prop_cuisineType)
    })

    attractions: dict[str, list[str]] = {"must_see": [], "popular": [], "local_gem": []}
    for a in g.objects(city_uri, EX.prop_hasAttraction):
        name = _str(g, a, EX.prop_attractionName)
        tier = _str(g, a, EX.prop_attractionTier)
        if name and tier in attractions:
            attractions[tier].append(name)
    for tier in attractions:
        attractions[tier].sort()

    festivals = []
    for f in g.objects(city_uri, EX.prop_hasFestival):
        fname   = _str(g, f, EX.prop_festivalName)
        fmonth  = _str(g, f, EX.prop_festivalMonthNum)
        ftype   = _str(g, f, EX.prop_festivalType)
        if month_filter and fmonth and str(month_filter) != fmonth:
            continue
        fmonth_label = (MONTH_NAMES[int(fmonth) - 1]
                        if fmonth and fmonth.isdigit() else fmonth)
        festivals.append((fname, fmonth_label, ftype))
    festivals.sort(key=lambda x: (x[1] or "", x[0] or ""))

    styles = sorted({
        _humanize(str(g.value(s, EX.prop_travelStyleName)))
        for s in g.objects(city_uri, EX.prop_hasTravelStyle)
        if g.value(s, EX.prop_travelStyleName)
    })

    # --- Compact assembly (LEN1: ~12 lines target) ---
    lines: list[str] = []

    dest_header = f"{city_name}, {country_name}" if city_name and country_name else (city_name or airport_code)
    lines.append(f"\n{dest_header}\n")

    # One-liner: safety · cost · visa (most important facts first)
    summary_parts: list[str] = []
    safety_label = _normalise_safety(safety_tier) or ("Safe" if solo_safe is True else "")
    if safety_label:
        solo_tag = " · Solo-female friendly" if solo_safe is True else ""
        summary_parts.append(f"{safety_label}{solo_tag}")
    if cost_idx:
        try:
            cost_label = _cost_comparison(float(cost_idx)).split(" —")[0]
            summary_parts.append(cost_label)
        except (ValueError, TypeError):
            pass
    if visa_rows:
        v     = visa_rows[0]
        req   = str(v.get("visaRequired", "")).lower()
        dur   = v.get("visaDurationDays", "")
        passp = v.get("passportCountryName", "")
        url   = v.get("onlineApplyUrl", "")
        if req == "false":
            summary_parts.append("No visa required")
        else:
            pol_s = _normalise_policy(v.get("visaPolicyName", ""))
            dur_s = f" · {dur} days" if dur else ""
            summary_parts.append(f"{pol_s or 'Visa required'}{dur_s}")
    if summary_parts:
        lines.append("  " + " · ".join(summary_parts))
        lines.append("")

    # Best time (compact range notation — TG6)
    if best_months:
        month_nums = []
        for m in best_months:
            try:
                month_nums.append(MONTH_NAMES.index(m) + 1)
            except ValueError:
                pass
        range_str = _months_to_ranges(month_nums) if month_nums else " · ".join(m[:3] for m in best_months)
        lines.append(f"  Best time: {range_str}")
        if is_travel_month_best is False and month_filter:
            tmn = MONTH_SHORT[int(month_filter) - 1]
            lines.append(f"  Note: {tmn} is outside peak season.")
        lines.append("")

    # Attractions (inline top 4)
    all_attrs = attractions.get("must_see", []) + attractions.get("popular", [])
    if all_attrs:
        top       = all_attrs[:4]
        extra_str = f" +{len(all_attrs) - 4} more" if len(all_attrs) > 4 else ""
        lines.append(f"  Top: {' · '.join(top)}{extra_str}")

    # Festivals (inline)
    if festivals:
        fest_parts: list[str] = []
        for fname, fmonth, ftype in festivals[:3]:
            ms = (fmonth or "")[:3]
            fest_parts.append(f"{fname} ({ms})" if ms else fname)
        extra_f = len(festivals) - 3
        extra_str = f" +{extra_f} more" if extra_f > 0 else ""
        lines.append(f"  Festivals: {' · '.join(fest_parts)}{extra_str}")

    # Travel styles (inline up to 4)
    if styles:
        lines.append(f"  Good for: {' · '.join(styles[:4])}")

    # Cuisine (M6: show dishes, not one-word label)
    if cuisines:
        cuisine_str = " · ".join(_cuisine_with_dishes(c) for c in cuisines[:2])
        lines.append(f"  Eat: {cuisine_str}")

    # Neighbourhoods inline (LEN4: names only, saves ~N lines)
    if neighbourhoods:
        hood_names = [n[0] for n in neighbourhoods[:4]]
        extra_n    = len(neighbourhoods) - 4
        extra_str  = f" +{extra_n} more" if extra_n > 0 else ""
        lines.append(f"  Stay: {' · '.join(hood_names)}{extra_str}")

    # Transport (TG13: always render — fallback if no data)
    if transport_modes:
        widely_str = " — widely used" if public_transport is True else ""
        lines.append(f"  Getting around: {' · '.join(transport_modes[:3])}{widely_str}")
    else:
        lines.append("  Getting around: Check local transport apps on arrival")

    # Currency + timezone + language on one line
    info: list[str] = []
    if currency_code and exchange_rate:
        info.append(f"1 SGD ≈ {_fmt_rate(exchange_rate)} {currency_code}")
    if utc_offset:
        info.append(f"UTC{utc_offset}")
    if language:
        info.append(language)
    if info:
        lines.append(f"  {' · '.join(info)}")

    # Visa apply URL if needed
    if visa_rows:
        v   = visa_rows[0]
        req = str(v.get("visaRequired", "")).lower()
        url = v.get("onlineApplyUrl", "")

    city_label = city_name or airport_code
    lines.append("")
    lines.append(
        f'  Ask "Flights to {city_label}", "Things to do in {city_label}",'
        f' "Neighbourhoods {city_label}" or "Safety {city_label}" for details.'
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flight result + compact destination summary
# ---------------------------------------------------------------------------

def format_flight_with_destination(
    rows: list[dict],
    g: Graph,
    params: dict,
    visa_rows: list[dict],
    intent_name: str = "",
) -> str:
    """
    Compact one-line destination summary followed by a flight bullet list.
    The full destination card is omitted — use format_vacation_plan for that.
    """
    airport_code = params.get("destination_airport_code", "")
    airport_uri  = _find_airport(g, airport_code)

    city_uri    = g.value(airport_uri, EX.prop_inCity) if airport_uri else None
    country_uri = g.value(city_uri, EX.prop_belongsToCountry) if city_uri else None

    city_name    = _str(g, city_uri, EX.prop_cityName) or airport_code
    country_name = _str(g, country_uri, EX.prop_countryName) or ""

    # Safety (L4 — consistent capitalisation)
    safety_tier = _str(g, city_uri, EX.prop_safetyTier)
    solo_safe   = _bool(g, city_uri, EX.prop_soloFemaleSafe)
    safety_str  = _normalise_safety(safety_tier) or ("Safe" if solo_safe is True else "")

    # Visa summary
    visa_str = ""
    if visa_rows:
        v        = visa_rows[0]
        required = str(v.get("visaRequired", "")).lower()
        dur_days = v.get("visaDurationDays", "")
        if required == "false":
            visa_str = "No visa needed"
        elif required == "true":
            visa_str = "Visa required" + (f" · {dur_days} days" if dur_days else "")

    # Exchange rate
    currency_uri  = g.value(country_uri, EX.prop_hasCurrency) if country_uri else None
    currency_code = _str(g, currency_uri, EX.prop_currencyCode) or ""
    exchange_rate = _str(g, currency_uri, EX.prop_exchangeRate)
    rate_str = (
        f"≈ {_fmt_rate(exchange_rate)} {currency_code}/SGD"
        if exchange_rate and currency_code else ""
    )

    summary_parts = [p for p in [safety_str, visa_str, rate_str] if p]
    dest_label    = f"{city_name}, {country_name}".strip(", ")
    summary_line  = dest_label + (" — " + " · ".join(summary_parts) if summary_parts else "")

    # Apply result cap
    cap          = 3 if intent_name in _CAP_3 else (5 if intent_name in _CAP_5 else None)
    display_rows = rows[:cap] if cap else rows
    total        = len(rows)

    lines = [f"\n{summary_line}", ""]

    # M5: only show cabin class if multiple classes exist in result set
    unique_cabins = {r.get("f_cabin_class", "") for r in rows if r.get("f_cabin_class", "")}
    show_cabin    = len(unique_cabins) > 1

    if not display_rows:
        lines.append("  No flights found for these dates.")
    else:
        for r in display_rows:
            dep      = _fmt_dt(r.get("f_departure_date", ""))
            arr      = _fmt_dt(r.get("f_arrival_date", ""))
            airline  = r.get("f_airline_code", "")
            cabin    = r.get("f_cabin_class", "") if show_cabin else ""
            fare_raw = r.get("cheapest_fare") or r.get("f_total_amount_fare_total", "")
            curr     = r.get("f_currency_code", "")
            duration = r.get("f_flight_duration", "")
            dur_str  = f" · {_fmt_dur(duration)}" if duration else ""
            fare_str = _fmt_fare(fare_raw, curr)
            parts    = [airline, f"{dep} → {arr}{dur_str}", cabin, fare_str]
            lines.append(f"  • {' | '.join(p for p in parts if p)}")

    if cap and total > cap:
        if intent_name == "shortest_flight_on_route":
            sort_label = "fastest"
        elif intent_name in _CAP_3:
            sort_label = "cheapest"
        else:
            sort_label = "next"
        lines.append(
            f"\n  Showing {sort_label} {cap} of {total} flights."
            " Ask for a specific date or more options to narrow down."
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Highlights — attractions + festivals this month + weather (compact)
# ---------------------------------------------------------------------------

def format_highlights(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No highlights data found.\n"

    airport_code = params.get("destination_airport_code", "")
    month_num    = params.get("month_num")
    month_label  = f" in {MONTH_NAMES[int(month_num) - 1]}" if month_num else ""

    attractions: dict[str, list[str]] = {"must_see": [], "popular": [], "local_gem": []}
    festivals: list[tuple[str, str]] = []
    weather: dict = {}

    for r in rows:
        rt = r.get("resultType", "")
        if rt == "attraction":
            tier = r.get("tier", "")
            name = r.get("name", "")
            if tier in attractions and name:
                attractions[tier].append(name)
        elif rt == "festival":
            row_month = r.get("monthNum", "")
            if month_num and row_month and str(month_num) != str(row_month):
                continue
            name  = r.get("name", "")
            ftype = r.get("festivalType", "")
            if name:
                festivals.append((name, ftype))
        elif rt == "weather":
            row_month = r.get("monthNum", "")
            if month_num and str(month_num) == str(row_month):
                weather = r

    display_name = params.get("city_name") or airport_code
    lines = [f"\n{display_name} — Highlights{month_label}", ""]

    if weather:
        temp    = weather.get("avgTempC", "")
        rain    = weather.get("avgRainfallMm", "")
        summary = weather.get("weatherSummary", "")
        parts   = []
        if temp:
            parts.append(f"~{temp}°C")
        if rain:
            parts.append(f"{rain}mm rain")
        if summary:
            parts.append(summary)
        if parts:
            lines.append(f"  Weather: {' · '.join(parts)}")
            lines.append("")

    if any(attractions.values()):
        lines.append("  What to do:")
        for tier_key, label in [("must_see", "Must-see"), ("popular", "Popular"), ("local_gem", "Local gem")]:
            items = sorted(attractions[tier_key])
            if items:
                lines.append(f"    {label}: {' · '.join(items)}")
        lines.append("")

    if festivals:
        lines.append(f"  Festivals{month_label}:")
        for fname, ftype in sorted(festivals):
            type_str = f" ({_humanize(ftype)})" if ftype else ""
            lines.append(f"    · {fname}{type_str}")
        lines.append("")
    # TG7: omit "No festivals in [month]." — silence is better than a false negative

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Attractions — grouped by tier
# ---------------------------------------------------------------------------

def format_attractions(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No attraction data found.\n"

    airport_code   = params.get("destination_airport_code", "")
    city_label     = params.get("city_name") or airport_code   # H2/L8
    month_num      = params.get("month_num")
    month_label    = f" in {MONTH_SHORT[int(month_num) - 1]}" if month_num else ""
    filter_type    = params.get("attraction_type", "")

    # TG9: filter to requested attraction type; if none match, warn and show all
    filtered_notice = ""
    display_rows = rows
    if filter_type:
        matched = [r for r in rows if (r.get("attractionType") or "").lower() == filter_type.lower()]
        if matched:
            display_rows = matched
        else:
            filtered_notice = (
                f"\n  No {filter_type} attractions found for {city_label} in our data."
                f" Showing top attractions instead.\n"
            )
            display_rows = rows

    tiers: dict[str, list[str]] = {"must_see": [], "popular": [], "local_gem": []}
    other: list[str] = []
    for r in display_rows:
        name = r.get("attractionName", "")
        tier = r.get("attractionTier", "")
        if tier in tiers:
            tiers[tier].append(name)
        elif name:
            other.append(name)

    lines = [f"\n{city_label} — Things to Do{month_label}", ""]
    if filtered_notice:
        lines.insert(1, filtered_notice)
    for tier_key, label in [("must_see", "Must-see"), ("popular", "Popular"), ("local_gem", "Local gem")]:
        items = sorted(tiers[tier_key])
        if items:
            lines.append(f"  {label}: {' · '.join(items)}")
    if other:
        lines.append(f"  Other: {' · '.join(sorted(other))}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cheapest_month_for_route — monthly fare aggregate
# ---------------------------------------------------------------------------

def format_cheapest_month(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No monthly fare data found.\n"

    origin      = params.get("origin", "")
    destination = params.get("destination", "")
    currency    = rows[0].get("f_currency_code", "SGD")

    lines = [f"\n{origin} → {destination} — Cheapest months to fly\n"]
    for r in rows:
        raw_month = str(r.get("departure_month", ""))
        month     = _fmt_month(raw_month)   # H9: 2026-06 → June 2026
        min_fare  = r.get("min_fare")
        avg_fare  = r.get("avg_fare")
        count     = r.get("flight_count", "")
        # H9: round fares to whole numbers
        min_str  = f"{currency} {int(round(float(min_fare)))}" if min_fare is not None else ""
        avg_str  = f"avg {currency} {int(round(float(avg_fare)))}" if avg_fare is not None else ""
        cnt_str  = f"{count} flights" if count else ""
        detail   = " · ".join(p for p in [avg_str, cnt_str] if p)
        lines.append(f"  • {month} — from {min_str}" + (f" · {detail}" if detail else ""))

    best = min(rows, key=lambda r: r.get("min_fare") or float("inf"))
    best_raw   = best.get("departure_month", "")
    best_month = _fmt_month(best_raw)
    best_fare  = best.get("min_fare")
    if best_month and best_fare is not None:
        lines.append(f"\n  Cheapest: {best_month} — from {currency} {int(round(float(best_fare)))}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# airlines_on_route — airline aggregate
# ---------------------------------------------------------------------------

def format_airlines_on_route(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No airline data found for this route.\n"

    origin      = params.get("origin", "")
    destination = params.get("destination", "")
    currency    = rows[0].get("f_currency_code", "")

    lines = [f"\nAirlines on {origin} → {destination}\n"]
    for r in rows:
        airline  = str(r.get("f_airline_code", ""))
        min_fare = r.get("min_fare")
        avg_mins = r.get("avg_duration_mins")
        count    = r.get("flight_count", "")
        fare_str = _fmt_fare(min_fare, currency) if min_fare is not None else ""
        dur_str  = _fmt_dur(avg_mins) if avg_mins is not None else ""
        cnt_str  = f"{count} flights" if count else ""
        parts    = [p for p in [fare_str, dur_str, cnt_str] if p]
        lines.append(f"  • {airline}" + (" — " + " · ".join(parts) if parts else ""))
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# visa_destinations_by_policy — grouped by duration, own country filtered
# ---------------------------------------------------------------------------

def format_visa_list(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No visa destination data found.\n"

    passport_code  = (params.get("passport_country_code") or "").upper()
    policy_name    = params.get("visa_policy_name", "")

    # Get passport country name from first matching row
    passport_name = ""
    for r in rows:
        if r.get("passportCountryName"):
            passport_name = r["passportCountryName"]
            break

    # Group by visaDurationDays, filtering own country
    groups: dict = defaultdict(list)
    for r in rows:
        dest_code = (r.get("destinationCountryCode") or "").upper()
        dest_name = r.get("destinationCountryName", "")
        if not dest_name:
            continue
        if passport_code and dest_code == passport_code:
            continue
        duration = r.get("visaDurationDays")
        groups[duration].append(dest_name)

    def _dur_sort_key(k):
        if k is None:
            return -1
        try:
            return int(k)
        except (ValueError, TypeError):
            return 0

    sorted_groups = sorted(groups.items(), key=lambda x: _dur_sort_key(x[0]), reverse=True)

    policy_label = _normalise_policy(policy_name) if policy_name else "Visa"
    header = policy_label + " destinations"
    if passport_name:
        header += f" — {passport_name} passport"

    lines = [f"\n{header}\n"]
    max_show = 6
    for duration, countries in sorted_groups:
        countries_sorted = sorted(countries)
        dur_label = f"{duration} days" if duration else "No fixed limit"
        if len(countries_sorted) <= max_show:
            lines.append(f"  {dur_label}: {' · '.join(countries_sorted)}")
        else:
            shown = countries_sorted[:max_show]
            extra = len(countries_sorted) - max_show
            lines.append(f"  {dur_label}: {' · '.join(shown)} (+{extra} more)")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generic — plain bullet list from list[dict]
# ---------------------------------------------------------------------------

def format_table(rows: list[dict], intent_name: str = "", params: dict | None = None) -> str:
    if not rows:
        p = params or {}
        travel_style = p.get("travel_style", "")
        if travel_style:
            return (
                f"\nNo destinations tagged with {travel_style} found."
                " Try nature or adventure destinations instead.\n"
            )
        return "\nNo results found.\n"

    cap   = 3 if intent_name in _CAP_3 else (5 if intent_name in _CAP_5 else None)
    total = len(rows)

    lines = [""]

    # ── Destination list (has 'destination' column) ───────────────
    if "destination" in rows[0]:
        # H1: context header
        if params:
            header = _dest_list_header(intent_name, params)
            if header:
                lines[0] = f"\n{header}\n"

        # H3/H4: deduplicate by city — keep cheapest fare per city name
        seen: dict[str, tuple] = {}   # city_key → (row, fare_float)
        for r in rows:
            dest     = r.get("destination", "")
            city_key = re.sub(r"\s*\([A-Z]{3}\)\s*$", "", dest).strip()
            fare_raw = r.get("from") or r.get("min_fare") or r.get("cheapest_fare", "")
            try:
                fare_val = float(fare_raw) if fare_raw else float("inf")
            except (ValueError, TypeError):
                fare_val = float("inf")
            if city_key not in seen or fare_val < seen[city_key][1]:
                seen[city_key] = (r, fare_val)

        deduped    = list(seen.values())  # (row, fare_val) pairs, insertion order
        total      = len(deduped)
        show_rows  = deduped[:cap] if cap else deduped

        for r, _ in show_rows:
            dest     = r.get("destination", "")
            curr     = r.get("currency") or r.get("f_currency_code", "")
            fare_raw = r.get("from") or r.get("min_fare") or r.get("cheapest_fare", "")
            if fare_raw:
                lines.append(f"  • {dest} — from {_fmt_fare(fare_raw, curr)}")
            else:
                lines.append(f"  • {dest}")

        if cap and total > cap:
            lines.append(f"\n  Showing top {cap} of {total} destinations.")
        elif total > 10:
            lines.append(f"\n  Showing {total} destinations. Ask for a specific date or filter to narrow down.")
        elif total == 1:
            # M10: single result — note it's narrow, not a failure
            lines.append("\n  Only 1 destination matched your filter."
                         " Try broadening your search for more options.")

    # ── Flight rows (has departure date column) ───────────────────
    elif "f_departure_date" in rows[0] or "departure" in rows[0]:
        display_rows = rows[:cap] if cap else rows
        unique_cabins = {r.get("f_cabin_class") or r.get("cabin", "") for r in rows}
        show_cabin    = len(unique_cabins) > 1
        for r in display_rows:
            dep      = _fmt_dt(r.get("f_departure_date") or r.get("departure") or "")
            arr      = _fmt_dt(r.get("f_arrival_date") or r.get("arrival") or "")
            airline  = r.get("f_airline_code") or r.get("airline", "")
            cabin    = (r.get("f_cabin_class") or r.get("cabin", "")) if show_cabin else ""
            curr     = r.get("f_currency_code") or r.get("currency", "")
            fare_raw = (r.get("f_total_amount_fare_total") or r.get("cheapest_fare")
                        or r.get("min_fare", ""))
            duration = r.get("f_flight_duration") or r.get("duration")
            dur_str  = f" · {_fmt_dur(duration)}" if duration else ""
            fare_str = _fmt_fare(fare_raw, curr)
            parts    = [airline, f"{dep} → {arr}{dur_str}", cabin, fare_str]
            lines.append(f"  • {' | '.join(p for p in parts if p)}")

        if cap and total > cap:
            # L3/LEN5: route_fare_options-specific footer
            if intent_name == "route_fare_options":
                lines.append(
                    f"\n  Showing {cap} of {total} flights."
                    " Ask for a specific date to narrow down."
                )
            else:
                lines.append(
                    f"\n  Showing {cap} of {total} flights."
                    " Ask for a specific date or more options to narrow down."
                )

    # ── Generic SPARQL/SQL rows ───────────────────────────────────
    else:
        display_rows = rows[:cap] if cap else rows
        _skip_keys = {"id", "trip", "pub_transport", "best_time", "visa_req",
                      "route", "f_flight_combination"}
        for r in display_rows:
            renamed = _rename_row(r)
            parts   = []
            for k, v in renamed.items():
                if k in _skip_keys or not v:
                    continue
                label = _COL_LABELS.get(k, k).replace("_", " ").title()
                val   = _fmt_col(k, v)
                parts.append(f"{label}: {val}")
            if parts:
                lines.append(f"  • {' · '.join(parts)}")

        if cap and total > cap:
            lines.append(f"\n  Showing top {cap} results. Ask for a specific date or destination to narrow down.")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# C3 — Weather by month
# ---------------------------------------------------------------------------

def format_weather(rows: list[dict], params: dict) -> str:
    """destination_weather_by_month — show only the requested month."""
    if not rows:
        return "\n  No weather data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # L1
    month_num    = params.get("month_num")

    # Filter to requested month; if none specified show all best months
    if month_num:
        target = [r for r in rows if str(r.get("monthNum", "")) == str(month_num)]
        if not target:
            target = rows  # fallback: show all if filter returns nothing
    else:
        target = rows

    lines = []
    for r in target:
        mn    = r.get("monthNum", "")
        mname = r.get("monthName", "") or (MONTH_NAMES[int(mn) - 1] if mn and str(mn).isdigit() else "")
        temp  = r.get("avgTempC", "")
        rain  = r.get("avgRainfallMm", "")
        summary = r.get("weatherSummary", "")

        header = f"{city_label} in {mname}" if mname else city_label
        lines.append(f"\n{header}\n")
        parts = []
        if temp:
            parts.append(f"~{temp}°C")
        if rain:
            parts.append(f"{rain}mm rainfall")
        if parts:
            lines.append(f"  {' · '.join(parts)}")
        if summary:
            lines.append(f"  {summary.capitalize()}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H2 — Enrichment intent formatters
# ---------------------------------------------------------------------------

def format_festivals(rows: list[dict], params: dict) -> str:
    """destination_festivals — one line per festival, filtered by month when requested (C3)."""
    airport_code = params.get("destination_airport_code", "")
    month_num    = params.get("month_num")
    month_label  = f" in {MONTH_NAMES[int(month_num) - 1]}" if month_num else ""

    # C3: filter rows to the requested month — never show wrong-month festivals
    if month_num:
        filtered = [r for r in rows if str(r.get("monthNum", "")) == str(month_num)]
    else:
        filtered = rows

    if not filtered:
        city_label = params.get("city_name") or airport_code
        month_name = MONTH_NAMES[int(month_num) - 1] if month_num else ""
        if month_num:
            return f"\n{city_label} — Festivals{month_label}\n\n  No festivals in {month_name}.\n"
        return "\n  No festival data found.\n"

    city_label = params.get("city_name") or airport_code   # H2
    lines = [f"\n{city_label} — Festivals{month_label}\n"]
    for r in filtered:
        name  = r.get("festivalName", "")
        mnum  = str(r.get("monthNum", ""))
        ftype = r.get("festivalType", "")
        if not name:
            continue
        mname = MONTH_NAMES[int(mnum) - 1] if mnum.isdigit() else mnum
        # L2: skip month in body when it's already in the header
        month_tag = "" if month_num else (f" ({mname})" if mname else "")
        tstr  = f" — {_humanize(ftype)}" if ftype else ""
        lines.append(f"  {name}{month_tag}{tstr}")
    lines.append("")
    return "\n".join(lines)


def format_transport(rows: list[dict], params: dict) -> str:
    """destination_transport — clean list of modes, drop boolean column."""
    if not rows:
        return "\nNo transport data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    modes = sorted({_humanize(r.get("transportModeName", "")) for r in rows if r.get("transportModeName")})
    lines = [f"\n{city_label} — Getting Around\n"]
    if modes:
        lines.append(f"  {' · '.join(modes)}")
    lines.append("")
    return "\n".join(lines)


def format_cuisines(rows: list[dict], params: dict) -> str:
    """destination_cuisines — comma list only."""
    if not rows:
        return "\n  No cuisine data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    cuisines = sorted({_humanize(r.get("cuisineType", "")) for r in rows if r.get("cuisineType")})
    lines = [f"\n{city_label} — Local Food\n"]
    if cuisines:
        for c in cuisines:
            lines.append(f"  {_cuisine_with_dishes(c)}")
    else:
        lines.append("  No cuisine data.")
    lines.append("")
    return "\n".join(lines)


def format_language(rows: list[dict], params: dict) -> str:
    """destination_language — single value."""
    if not rows:
        return "\n  No language data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    lang = rows[0].get("languageName", "") if rows else ""
    lines = [f"\n{city_label} — Language\n", f"  {lang or 'No data available.'}", ""]
    return "\n".join(lines)


def format_timezone(rows: list[dict], params: dict) -> str:
    """destination_timezone — UTC offset only, no IANA ID."""
    if not rows:
        return "\n  No timezone data found.\n"

    airport_code = params.get("destination_airport_code", "")
    r = rows[0]
    city    = params.get("city_name") or r.get("cityName") or airport_code   # H2
    offset  = r.get("utcOffset", "")
    utc_str = f"UTC{offset}" if offset else "unknown"
    lines   = [f"\n{city} — Timezone\n", f"  {utc_str}", ""]
    return "\n".join(lines)


def format_destination_currency(rows: list[dict], params: dict) -> str:
    """destination_currency — name, code, rounded rate."""
    if not rows:
        return "\n  No currency data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    r = rows[0]
    code     = r.get("currencyCode", "")
    name     = r.get("currencyName", "")
    rate     = r.get("exchangeRate", "")
    rate_str = f" · ≈ {_fmt_rate(rate)} {code} per SGD" if rate and code else ""
    lines = [f"\n{city_label} — Currency\n", f"  {name} ({code}){rate_str}", ""]
    return "\n".join(lines)


def format_amenities(rows: list[dict], params: dict) -> str:
    """airport_amenities — name, terminals, amenity flags."""
    if not rows:
        return "\n  No airport data found.\n"

    airport_code = params.get("destination_airport_code", "")
    r = rows[0]
    name     = r.get("airportName", airport_code)
    terms    = r.get("terminalCount", "")
    transit  = str(r.get("hasTransitHotel", "")).lower() == "true"
    lounge   = str(r.get("hasLounge", "")).lower() == "true"

    parts = []
    if terms:
        parts.append(f"{terms} terminal{'s' if int(terms) != 1 else ''}")
    if lounge:
        parts.append("Lounge")
    if transit:
        parts.append("Transit Hotel")

    detail = " · ".join(parts) if parts else "No amenity data"
    lines = [f"\n{name} ({airport_code})\n", f"  {detail}", ""]
    return "\n".join(lines)


def format_safety(rows: list[dict], params: dict) -> str:
    """destination_safety — tier + solo-female indicator."""
    if not rows:
        return "\n  No safety data found.\n"

    airport_code = params.get("destination_airport_code", "")
    r = rows[0]
    city     = params.get("city_name") or r.get("cityName") or airport_code   # H2
    tier     = _normalise_safety(r.get("safetyTier", ""))
    solo     = str(r.get("soloFemaleSafe", "")).lower()
    solo_str = " · Solo female travel: safe" if solo == "true" else (" · Solo female travel: exercise caution" if solo == "false" else "")

    lines = [f"\n{city} — Safety\n", f"  {tier or 'No data'}{solo_str}", ""]
    return "\n".join(lines)


def format_neighborhoods(rows: list[dict], params: dict) -> str:
    """destination_neighborhoods — inline name + summary (LEN4: one line per area)."""
    if not rows:
        return "\n  No neighbourhood data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    lines = [f"\n{city_label} — Neighbourhoods\n"]
    for r in rows:
        name    = r.get("areaName", "")
        summary = r.get("areaSummary", "")
        if not name:
            continue
        # LEN4: inline — saves one line per neighbourhood
        if summary:
            lines.append(f"  {name} — {summary}")
        else:
            lines.append(f"  {name}")
    lines.append("")
    return "\n".join(lines)


def format_overview(rows: list[dict], params: dict) -> str:
    """destination_overview — city/country/safety/cost one-card."""
    if not rows:
        return "\n  No destination data found.\n"

    airport_code = params.get("destination_airport_code", "")
    r = rows[0]
    city     = r.get("cityName", airport_code)
    country  = r.get("countryName", "")
    continent= r.get("continent", "")
    region   = r.get("region", "")
    tier     = _normalise_safety(r.get("safetyTier", ""))
    solo     = str(r.get("soloFemaleSafe", "")).lower()
    cost_raw = r.get("costOfLivingIndex", "")

    loc_parts = [p for p in [region, continent] if p]
    loc_str   = " | ".join(loc_parts)

    lines = [f"\n{city}, {country}\n"]
    if loc_str:
        lines.append(f"  {loc_str}")
    if tier:
        solo_str = " · Solo female travel: safe" if solo == "true" else ""
        lines.append(f"  Safety: {tier}{solo_str}")
    if cost_raw:
        try:
            lines.append(f"  Cost: {_cost_comparison(float(cost_raw))}")
        except (ValueError, TypeError):
            pass
    lines.append("")
    return "\n".join(lines)


def format_travel_styles(rows: list[dict], params: dict) -> str:
    """destination_travel_styles — humanised list."""
    if not rows:
        return "\n  No travel style data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2
    styles = sorted({_humanize(r.get("travelStyleName", "")) for r in rows if r.get("travelStyleName")})
    lines = [f"\n{city_label} — Travel Styles\n"]
    lines.append(f"  {' · '.join(styles)}" if styles else "  No data available.")
    lines.append("")
    return "\n".join(lines)


def format_best_months(rows: list[dict], params: dict) -> str:
    """best_months_to_visit — compact one-line summary (LEN3)."""
    if not rows:
        return "\n  No best-month data found.\n"

    airport_code = params.get("destination_airport_code", "")
    city_label   = params.get("city_name") or airport_code   # H2

    sorted_rows = sorted(rows, key=lambda x: int(x.get("monthNum", 0) or 0))

    # Collect month abbreviations, temp range, first summary
    month_shorts = []
    temps = []
    summaries = []
    for r in sorted_rows:
        mn = r.get("monthNum", "")
        try:
            month_shorts.append(MONTH_SHORT[int(mn) - 1])
        except (ValueError, TypeError, IndexError):
            nm = r.get("monthName", "")
            if nm:
                month_shorts.append(nm[:3])
        t = r.get("avgTempC")
        if t:
            try:
                temps.append(float(t))
            except (ValueError, TypeError):
                pass
        s = r.get("weatherSummary", "")
        if s and s not in summaries:
            summaries.append(s.lower())

    detail_parts = []
    if temps:
        lo, hi = int(min(temps)), int(max(temps))
        detail_parts.append(f"{lo}–{hi}°C" if lo != hi else f"~{lo}°C")
    if summaries:
        detail_parts.append(summaries[0])
    detail_str = f" ({', '.join(detail_parts)})" if detail_parts else ""

    # TG6: compress to range notation
    month_nums_list = []
    for r in sorted_rows:
        mn = r.get("monthNum", "")
        try:
            month_nums_list.append(int(mn))
        except (ValueError, TypeError):
            pass
    range_str = _months_to_ranges(month_nums_list) if month_nums_list else " · ".join(month_shorts)

    lines = [
        f"\n{city_label} — Best time to visit\n",
        f"  Best: {range_str}{detail_str}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H8 — visa_check_for_destination — clean two-line format
# ---------------------------------------------------------------------------

def format_visa_check(rows: list[dict], params: dict) -> str:
    """
    visa_check_for_destination — show visa status, duration in days (not minutes),
    policy name, and application URL. Never pass duration through _fmt_dur.
    """
    if not rows:
        return "\n  No visa information found for this route.\n"

    v = rows[0]
    required      = str(v.get("visaRequired", "")).lower()
    policy_raw    = v.get("visaPolicyName", "")
    duration_days = v.get("visaDurationDays", "")  # raw integer days from SPARQL
    passport      = v.get("passportCountryName", "")
    dest          = v.get("destinationCountryName", "")

    lines = []
    if required == "false":
        lines.append(f"\n{dest} — No visa required for {passport} passport")
    else:
        policy_str = f"{_normalise_policy(policy_raw)} · " if policy_raw else ""
        lines.append(f"\n{dest} — Visa required for {passport} passport")
        if policy_raw:
            lines.append(f"  {_normalise_policy(policy_raw)}")

    if duration_days:
        try:
            lines.append(f"  Stay up to {int(duration_days)} days")
        except (ValueError, TypeError):
            lines.append(f"  Stay up to {duration_days} days")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# M9 — flight_count_on_route — clean route summary
# ---------------------------------------------------------------------------

def format_flight_count(rows: list[dict], params: dict) -> str:
    """flight_count_on_route — clean summary: route, month, count, fares."""
    if not rows:
        return "\n  No flight count data found.\n"

    r        = rows[0]
    origin   = r.get("f_departure_airport_code", params.get("origin", ""))
    dest_raw = r.get("f_destination_airport_code", params.get("destination", ""))
    # dest may have been enriched to "City, Country (CODE)" by pipeline
    dest     = dest_raw
    currency = r.get("f_currency_code", "SGD")
    total    = r.get("total_flights", "")
    airlines = r.get("airline_count", "")
    min_fare = r.get("min_fare")

    start = params.get("start_date", "")
    end   = params.get("end_date", "")
    month = params.get("departure_month") or params.get("month_num", "")

    # Build date label
    date_label = ""
    if month:
        try:
            date_label = MONTH_NAMES[int(month) - 1]
        except (ValueError, TypeError):
            date_label = str(month)
    elif start:
        try:
            parts = str(start).split("-")
            date_label = f"{MONTH_NAMES[int(parts[1]) - 1]} {parts[0]}"
        except Exception:
            date_label = start

    header = f"{origin} → {dest}"
    if date_label:
        header += f" — {date_label}"

    lines = [f"\n{header}\n"]
    detail_parts = []
    if total:
        detail_parts.append(f"{total} flights")
    if airlines:
        detail_parts.append(f"{airlines} airline{'s' if int(airlines) != 1 else ''}")
    if min_fare is not None:
        detail_parts.append(f"from {currency} {int(round(float(min_fare)))}")
    lines.append(f"  {' · '.join(detail_parts)}" if detail_parts else "  No data available.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# M13 — Aircraft on route
# ---------------------------------------------------------------------------

def format_aircraft_on_route(rows: list[dict], params: dict) -> str:
    """
    aircraft_on_route — grouped header 'Aircraft on SIN → NRT (SQ):' then
    list aircraft models. Repeating airline per row is suppressed when uniform.
    """
    if not rows:
        return "\n  No aircraft data found for this route.\n"

    origin  = params.get("origin", "")
    dest    = params.get("destination", "") or params.get("destination_airport_code", "")

    # Detect uniform airline
    airlines = {str(r.get("airlineCode", "") or r.get("f_airline_code", "")).strip() for r in rows}
    airline_str = f" ({next(iter(airlines))})" if len(airlines) == 1 and next(iter(airlines)) else ""

    aircraft_models = sorted({
        str(r.get("aircraftCode", "") or r.get("f_aircraft_code", "")).strip()
        for r in rows
        if r.get("aircraftCode") or r.get("f_aircraft_code")
    })

    header = f"Aircraft on {origin} → {dest}{airline_str}"
    lines = [f"\n{header}:\n"]
    if aircraft_models:
        lines.append(f"  {' · '.join(aircraft_models)}")
    else:
        lines.append("  No aircraft model data.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H1 — Route list (all_routes_from_origin / routes_by_airline / airlines_covering_route)
# ---------------------------------------------------------------------------

def format_route_list(rows: list[dict], params: dict, intent_name: str = "") -> str:
    """
    Group destinations by country. Show city names only — no airport codes or names.
    Suppress airline name when it's uniform across all rows.
    """
    if not rows:
        return "\n  No routes found.\n"

    origin   = params.get("origin", "")
    airline  = params.get("airline_code", "") or params.get("airline_name", "")

    # Detect if all rows share the same airline
    all_airlines = {r.get("airlineName", "") or r.get("airlineCode", "") for r in rows}
    single_airline = next(iter(all_airlines)) if len(all_airlines) == 1 else None

    if intent_name == "airlines_covering_route":
        dest = params.get("destination", "") or params.get("destination_airport_code", "")
        lines = [f"\nAirlines flying {origin} → {dest}\n"]
        for r in rows:
            al_code = r.get("airlineCode", "")
            al_name = r.get("airlineName", "")
            label   = f"{al_name} ({al_code})" if al_name and al_code else al_name or al_code
            lines.append(f"  • {label}")
        lines.append("")
        return "\n".join(lines)

    # Group by country → list of city names
    country_cities: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        country = r.get("countryName", "Unknown")
        city    = r.get("cityName", r.get("airportCode", ""))
        if city and city not in country_cities[country]:
            country_cities[country].append(city)

    for country in country_cities:
        country_cities[country].sort()

    # H10: detect SIN-centric data returning only Singapore for non-SIN origins
    all_cities = [c for cities in country_cities.values() for c in cities]
    all_countries = list(country_cities.keys())
    is_singapore_only = (
        len(all_cities) == 1
        and all_cities[0].lower() == "singapore"
    ) or (
        len(all_countries) == 1
        and "singapore" in all_countries[0].lower()
    )
    if is_singapore_only and origin and origin.upper() != "SIN":
        airport_label = f"{origin}"
        return (
            f"\nOur route data covers flights from Singapore (SIN). "
            f"{airport_label} to Singapore is the only route we have on file.\n\n"
            f"  Ask about flights from SIN for full coverage.\n"
        )

    if single_airline:
        header = f"{single_airline} flies from {origin} to:"
    elif airline:
        header = f"Routes from {origin} ({airline}):"
    else:
        header = f"Routes from {origin}:"

    # LEN2: for large lists, show a summary instead of dumping every city
    total_cities = sum(len(v) for v in country_cities.values())
    if len(country_cities) > 10:
        top_countries = sorted(country_cities.keys())[:6]
        sample = " · ".join(top_countries)
        lines = [f"\n{header}\n"]
        lines.append(f"  {len(country_cities)} countries · {total_cities}+ destinations")
        lines.append(f"  Includes: {sample} and more")
        lines.append("")
        lines.append("  Ask about a specific country or region to narrow down.")
        lines.append("")
        return "\n".join(lines)

    lines = [f"\n{header}\n"]
    for country in sorted(country_cities):
        cities = country_cities[country]
        lines.append(f"  {country}: {' · '.join(cities)}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# airports_in_city
# ---------------------------------------------------------------------------

def format_airports_in_city(rows: list[dict], params: dict) -> str:
    city_name = params.get("city_name", "")
    if not rows:
        return f"\n  No airports found for {city_name} in our data.\n"

    country = rows[0].get("countryName", "")
    header = f"\nAirports in {city_name}"
    if country:
        header += f", {country}"

    lines = [header, ""]
    for r in rows:
        code = r.get("airportCode", "")
        name = r.get("airportName", "")
        label = f"{name} ({code})" if name and name != code else code
        lines.append(f"  • {label}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# destinations_by_language
# ---------------------------------------------------------------------------

def format_language_destinations(rows: list[dict], params: dict) -> str:
    language = params.get("language_name", "")
    if not rows:
        return f"\n  No destinations found where {language} is spoken in our data.\n"

    # Group by country
    from collections import defaultdict
    country_cities: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        country = r.get("countryName", "Unknown")
        city = r.get("cityName", r.get("airportCode", ""))
        if city and city not in country_cities[country]:
            country_cities[country].append(city)

    lines = [f"\nDestinations where {language} is spoken:\n"]
    for country in sorted(country_cities):
        cities = sorted(country_cities[country])
        lines.append(f"  {country}: {' · '.join(cities)}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# destinations_with_festivals_in_month
# ---------------------------------------------------------------------------

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_festivals_by_month(rows: list[dict], params: dict) -> str:
    month_num = params.get("month_num", 0)
    try:
        month_label = _MONTH_NAMES[int(month_num)]
    except (ValueError, IndexError, TypeError):
        month_label = str(month_num)

    if not rows:
        return f"\n  No festivals found in {month_label} in our data.\n"

    # Group by city
    from collections import defaultdict
    city_festivals: dict[str, list[str]] = defaultdict(list)
    city_country: dict[str, str] = {}
    for r in rows:
        city = r.get("cityName", "Unknown")
        country = r.get("countryName", "")
        festival = r.get("festivalName", "")
        f_type = r.get("festivalType", "")
        label = f"{festival} ({f_type})" if f_type else festival
        if label and label not in city_festivals[city]:
            city_festivals[city].append(label)
        if country:
            city_country[city] = country

    lines = [f"\nFestivals in {month_label}:\n"]
    for city in sorted(city_festivals):
        country = city_country.get(city, "")
        loc = f"{city}, {country}" if country else city
        for fest in city_festivals[city]:
            lines.append(f"  • {loc} — {fest}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cities_in_country
# ---------------------------------------------------------------------------

def format_cities_in_country(rows: list[dict], params: dict) -> str:
    country_name = params.get("country_name", "")
    if not rows:
        return f"\n  No cities found for {country_name} in our data.\n"

    # Group airports by city
    by_city: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        city = r.get("cityName", "")
        code = r.get("airportCode", "")
        name = r.get("airportName", "")
        entry = f"{name} ({code})" if name and name != code else code
        if city and entry:
            by_city[city].append(entry)

    lines = [f"\nCities in {country_name.title()}\n"]
    for city in sorted(by_city):
        airports = sorted(by_city[city])
        lines.append(f"  {city}")
        for ap in airports:
            lines.append(f"    • {ap}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# country_info
# ---------------------------------------------------------------------------

def format_country_info(rows: list[dict], params: dict) -> str:
    country_name = params.get("country_name", "")
    if not rows:
        return f"\n  No information found for {country_name} in our data.\n"

    r = rows[0]
    name = r.get("countryName", country_name)
    code = r.get("countryCode", "")
    continent = r.get("continent", "")
    region = r.get("region", "")
    capital = r.get("capitalCityName", "")
    currency = r.get("currencyCode", "")

    lines = [f"\n{name}" + (f" ({code})" if code else ""), ""]
    if continent:
        lines.append(f"  Continent : {continent}")
    if region:
        lines.append(f"  Region    : {region}")
    if capital:
        lines.append(f"  Capital   : {capital}")
    if currency:
        lines.append(f"  Currency  : {currency}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# destinations_solo_female_friendly
# ---------------------------------------------------------------------------

def format_solo_female_destinations(rows: list[dict], params: dict) -> str:
    if not rows:
        return "\n  No solo female-friendly destinations found in our data.\n"

    # Group by country
    by_country: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in rows:
        by_country[r.get("countryName", "")].append(
            (r.get("cityName", ""), r.get("safetyTier", ""))
        )

    _TIER_LABEL = {
        "very_safe": "Very Safe",
        "safe":      "Safe",
    }

    lines = ["\nSolo Female-Friendly Destinations\n"]
    for country in sorted(by_country):
        lines.append(f"  {country}")
        for city, tier in sorted(by_country[country]):
            label = _TIER_LABEL.get(tier, tier.replace("_", " ").title())
            lines.append(f"    • {city} — {label}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# currency_exchange_rate
# ---------------------------------------------------------------------------

def format_exchange_rate(rows: list[dict], params: dict) -> str:
    currency_code = params.get("currency_code", "").upper()
    if not rows:
        return f"\n  No exchange rate data found for {currency_code}.\n"

    r = rows[0]
    code = r.get("currencyCode", currency_code).upper()
    name = r.get("currencyName", "")
    rate_raw = r.get("exchangeRate")

    try:
        rate = float(rate_raw)
    except (TypeError, ValueError):
        return f"\n  Exchange rate for {code} is not available.\n"

    # SGD is the base (rate=1 means 1 SGD = 1 SGD)
    if rate == 1.0 and code == "SGD":
        return f"\n  {code} ({name}) is the base currency — all rates are quoted in SGD.\n"

    if rate > 1:
        # More of foreign currency per 1 SGD (e.g. JPY)
        rate_str = f"{rate:,.2f} {code}"
        reverse = f"1 {code} = SGD {1/rate:.4f}"
    else:
        # Less foreign currency per SGD (e.g. GBP)
        rate_str = f"{rate:.4f} {code}"
        reverse = f"1 {code} = SGD {1/rate:.2f}"

    header = f"\n{name} ({code})" if name and name != code else f"\n{code}"
    lines = [header, "", f"  1 SGD = {rate_str}", f"  {reverse}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# visa_duration_check
# ---------------------------------------------------------------------------

def format_visa_duration(rows: list[dict], params: dict) -> str:
    country_name = params.get("destination_country_name", "")
    if not rows:
        return f"\n  No visa information found for {country_name}.\n"

    r = rows[0]
    name = r.get("countryName", country_name)
    required_raw = str(r.get("visaRequired", "")).lower()
    visa_required = required_raw not in ("false", "0", "no")
    duration = r.get("visaDurationDays")
    policy = r.get("policyName", "")

    lines = [f"\n{name} — SG Passport\n"]
    if policy:
        lines.append(f"  Entry type : {policy}")
    else:
        lines.append(f"  Visa required : {'Yes' if visa_required else 'No'}")
    if duration:
        lines.append(f"  Max stay   : {duration} days")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# airports_with_amenity
# ---------------------------------------------------------------------------

def format_airports_with_amenity(rows: list[dict], params: dict) -> str:
    amenity_type = params.get("amenity_type", "lounge").lower().replace(" ", "_")

    # Filter rows by requested amenity
    if "transit" in amenity_type or "hotel" in amenity_type:
        filtered = [r for r in rows if str(r.get("hasTransitHotel", "")).lower() in ("true", "1")]
        label = "Transit Hotel"
    else:
        filtered = [r for r in rows if str(r.get("hasLounge", "")).lower() in ("true", "1")]
        label = "Airport Lounge"

    if not filtered:
        return f"\n  No airports found with {label.lower()} in our data.\n"

    by_country: dict[str, list[str]] = defaultdict(list)
    for r in filtered:
        country = r.get("countryName", "")
        code = r.get("airportCode", "")
        name = r.get("airportName", "")
        entry = f"{name} ({code})" if name and name != code else code
        by_country[country].append(entry)

    lines = [f"\nAirports with {label}\n"]
    for country in sorted(by_country):
        lines.append(f"  {country}")
        for airport in sorted(by_country[country]):
            lines.append(f"    • {airport}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# safe_destinations_list
# ---------------------------------------------------------------------------

def format_safe_destinations(rows: list[dict], params: dict) -> str:
    safety_tier = params.get("safety_tier", "")
    if not rows:
        tier_label = safety_tier.replace("_", " ").title()
        return f"\n  No {tier_label} destinations found in our data.\n"

    _TIER_HEADER = {
        "very_safe": "Very Safe Destinations",
        "safe":      "Safe Destinations",
        "moderate":  "Moderate-Safety Destinations",
        "caution":   "Caution — These destinations carry elevated risk",
    }
    tier_key = safety_tier.lower()
    header = _TIER_HEADER.get(tier_key, f"{safety_tier.replace('_',' ').title()} Destinations")

    by_country: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_country[r.get("countryName", "")].append(r.get("cityName", ""))

    lines = [f"\n{header}\n"]
    for country in sorted(by_country):
        cities = sorted(by_country[country])
        lines.append(f"  {country}: {', '.join(cities)}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# festivals_by_type_global
# ---------------------------------------------------------------------------

def format_festivals_by_type(rows: list[dict], params: dict) -> str:
    festival_type = params.get("festival_type", "")
    if not rows:
        type_label = festival_type.replace("_", " ").title()
        return f"\n  No {type_label} festivals found in our data.\n"

    type_label = festival_type.replace("_", " ").title()
    # Sort by month then city
    sorted_rows = sorted(rows, key=lambda r: (int(r.get("monthNum", 0) or 0), r.get("cityName", "")))

    lines = [f"\n{type_label} Festivals\n"]
    for r in sorted_rows:
        name = r.get("festivalName", "")
        city = r.get("cityName", "")
        country = r.get("countryName", "")
        month_num = r.get("monthNum")
        try:
            month_label = MONTH_NAMES[int(month_num) - 1]
        except (TypeError, ValueError, IndexError):
            month_label = str(month_num or "")
        loc = f"{city}, {country}" if country else city
        lines.append(f"  • {name} — {loc} ({month_label})")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H3 — Route statistics
# ---------------------------------------------------------------------------

def format_route_statistics(rows: list[dict], params: dict) -> str:
    """route_statistics — clean fare + duration summary."""
    if not rows:
        return "\n  No statistics found for this route.\n"

    r        = rows[0]
    origin   = r.get("f_departure_airport_code", params.get("origin", ""))
    dest     = r.get("f_destination_airport_code", params.get("destination", ""))
    currency = r.get("f_currency_code", "SGD")
    min_fare = r.get("min_fare")
    avg_fare = r.get("avg_fare")
    max_fare = r.get("max_fare")
    avg_dur  = r.get("avg_duration_mins")
    count    = r.get("flight_count", "")
    month    = params.get("departure_month", "") or params.get("month_num", "")

    month_label = ""
    if month:
        try:
            month_label = f" — {MONTH_NAMES[int(month) - 1]} 2026"
        except (ValueError, TypeError, IndexError):
            month_label = f" — {month}"

    dest_label = dest  # enrichment could have resolved this, but we only have the code here
    lines = [f"\n{origin} → {dest_label}{month_label}\n"]

    fare_parts = []
    if min_fare is not None:
        fare_parts.append(f"from {currency} {float(min_fare):.0f}")
    if avg_fare is not None:
        fare_parts.append(f"avg {currency} {float(avg_fare):.0f}")
    if max_fare is not None:
        fare_parts.append(f"up to {currency} {float(max_fare):.0f}")
    if fare_parts:
        lines.append(f"  Fares: {' · '.join(fare_parts)}")

    dur_parts = []
    if avg_dur is not None:
        dur_parts.append(f"{_fmt_dur(avg_dur)}")
    if count:
        dur_parts.append(f"{count} flights available")
    if dur_parts:
        lines.append(f"  Flight time: {' · '.join(dur_parts)}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H4 — Currency list (currencies_by_region)
# ---------------------------------------------------------------------------

def format_currency_list(rows: list[dict], params: dict) -> str:
    """currencies_by_region — one line per country, rounded rate, filter base currency."""
    if not rows:
        return "\n  No currency data found.\n"

    region        = params.get("region", "")
    base_currency = params.get("base_currency_code", "SGD")
    header        = f"Currencies in {_humanize(region)} (1 {base_currency} ≈):" if region else f"Currencies (1 {base_currency} ≈):"

    lines = [f"\n{header}\n"]
    for r in sorted(rows, key=lambda x: x.get("countryName", "")):
        country  = r.get("countryName", "")
        code     = r.get("currencyCode", "")
        name     = r.get("currencyName", "")
        rate_raw = r.get("exchangeRate", "")
        if not country:
            continue
        # L9: show base currency as reference point rather than skipping it
        if code and code.upper() == base_currency.upper():
            lines.append(f"  {country}: {code} — base currency ({name})")
            continue
        rate_str = f"{_fmt_rate(rate_raw)} {code}" if rate_raw else code
        lines.append(f"  {country}: {rate_str} ({name})")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H7 — All departures on a date (all_flights_on_date)
# ---------------------------------------------------------------------------

def format_departures(rows: list[dict], params: dict) -> str:
    """
    all_flights_on_date — departure board style.
    Destination must already be enriched to 'City, Country (CODE)' by pipeline.
    """
    if not rows:
        return "\n  No departures found.\n"

    origin   = params.get("origin", "")
    date_str = params.get("departure_date", "") or params.get("date", "")
    date_label = _fmt_dt(date_str + "T00:00:00") if date_str and "T" not in str(date_str) else _fmt_dt(str(date_str))
    # Simplify to just "10 Jun 2026" — strip time portion
    if date_str:
        try:
            parts = str(date_str).split("T")[0].split("-")
            date_label = f"{int(parts[2])} {MONTH_SHORT[int(parts[1]) - 1]} {parts[0]}"
        except Exception:
            date_label = str(date_str)

    total = len(rows)
    _DEP_CAP = 10
    display_rows = rows[:_DEP_CAP]

    lines = [f"\nDepartures from {origin}" + (f" on {date_label}" if date_label else "") + "\n"]

    # Detect if all cabin classes are the same (M5)
    cabins = {r.get("f_cabin_class", "") for r in rows if r.get("f_cabin_class", "")}
    show_cabin = len(cabins) > 1

    for r in display_rows:
        dest     = r.get("destination", r.get("f_destination_airport_code", ""))
        dep_raw  = r.get("f_departure_date", "")
        duration = r.get("f_flight_duration", "")
        fare_raw = r.get("f_total_amount_fare_total", "")
        currency = r.get("f_currency_code", "SGD")
        airline  = r.get("f_airline_code", "")
        cabin    = r.get("f_cabin_class", "")

        dep_time = ""
        if dep_raw and "T" in str(dep_raw):
            dep_time = str(dep_raw).split("T")[1][:5]

        # LEN9: use · separator consistent with rest of product
        sub = []
        if dep_time:
            sub.append(dep_time)
        if duration:
            sub.append(_fmt_dur(duration))
        if fare_raw:
            sub.append(f"{currency} {float(fare_raw):.0f}")
        if show_cabin and cabin:
            sub.append(cabin.title())
        if airline:
            sub.append(airline)

        detail = " · ".join(sub)
        lines.append(f"  • {dest}" + (f" — {detail}" if detail else ""))

    # TG3: always show count footer so user knows if results are capped
    shown = min(total, _DEP_CAP)
    if total > shown:
        lines.append(
            f"\n  Showing {shown} of {total} departures."
            " Ask for a specific destination to narrow down."
        )
    else:
        lines.append(f"\n  Showing {total} departure{'s' if total != 1 else ''}.")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Reference cities for cost-of-living comparison
_COST_REFS = [
    (18.7, "Trivandrum"),
    (25.5, "Dhaka"),
    (28.3, "Ho Chi Minh City"),
    (29.3, "Jakarta"),
    (38.9, "Kuala Lumpur"),
    (42.4, "Bangkok"),
    (57.8, "Tokyo"),
    (65.4, "Seoul"),
    (73.8, "Hong Kong"),
    (80.1, "Sydney"),
    (88.7, "Singapore"),
    (89.5, "London"),
    (100.0, "New York"),
    (118.6, "Geneva"),
    (123.7, "Zurich"),
]


def _cost_comparison(idx: float) -> str:
    cheaper = [city for v, city in _COST_REFS if v < idx]
    pricier = [city for v, city in _COST_REFS if v > idx]
    ref_cheaper = cheaper[-2:] if len(cheaper) >= 2 else cheaper[-1:]
    ref_pricier = pricier[:1]

    if idx < 35:
        base = "Super budget-friendly"
    elif idx < 55:
        base = "Easy on the wallet"
    elif idx < 75:
        base = "Mid-range in cost"
    elif idx < 95:
        base = "On the pricier side"
    else:
        base = "Premium destination, budget accordingly"

    parts = []
    if ref_cheaper:
        parts.append(f"pricier than {' and '.join(ref_cheaper)}")
    if ref_pricier:
        parts.append(f"still cheaper than {ref_pricier[0]}")

    return f"{base} — {', '.join(parts)}." if parts else f"{base}."


def _find_airport(g: Graph, code: str):
    for s in g.subjects(EX.prop_airportCode, None):
        val = g.value(s, EX.prop_airportCode)
        if val and str(val) == code:
            return s
    return None


def _str(g, subject, predicate) -> str | None:
    if subject is None:
        return None
    val = g.value(subject, predicate)
    return str(val) if val is not None else None


def _bool(g, subject, predicate) -> bool | None:
    val = _str(g, subject, predicate)
    if val is None:
        return None
    return val.lower() in ("true", "1")


# ---------------------------------------------------------------------------
# airport_info
# ---------------------------------------------------------------------------

def format_airport_info(rows: list[dict], params: dict) -> str:
    """airport_info — full airport card: name, city, country, type, terminals, facilities."""
    if not rows:
        code = params.get("airport_code", "")
        return f"\n  No airport data found for {code}.\n"

    r = rows[0]
    code    = r.get("airportCode", params.get("airport_code", ""))
    name    = r.get("airportName", code)
    city    = r.get("cityName", "")
    country = r.get("countryName", "")
    a_type  = r.get("airportType", "")
    terms   = r.get("terminalCount", "")
    intl    = str(r.get("isInternational", "")).lower()
    lounge  = str(r.get("hasLounge", "")).lower() == "true"
    transit = str(r.get("hasTransitHotel", "")).lower() == "true"

    loc = f"{city}, {country}" if city and country else city or country
    type_label = a_type.replace("_", " ").title() if a_type else ""

    lines = [f"\n{name} ({code})\n"]
    if loc:
        lines.append(f"  Location  : {loc}")
    if type_label:
        lines.append(f"  Type      : {type_label}")
    if intl in ("true", "1"):
        lines.append("  Status    : International")
    if terms:
        lines.append(f"  Terminals : {terms}")

    facilities = []
    if lounge:
        facilities.append("Lounge")
    if transit:
        facilities.append("Transit Hotel")
    if facilities:
        lines.append(f"  Facilities: {' · '.join(facilities)}")
    elif terms or type_label:
        lines.append("  Facilities: None on record")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# destinations_by_season
# ---------------------------------------------------------------------------

def format_destinations_by_season(rows: list[dict], params: dict) -> str:
    """destinations_by_season — list of destinations with flight fares grouped by country."""
    if not rows:
        season = params.get("season_keyword", "")
        return f"\n  No destinations found with {season} season in our data.\n"

    origin  = params.get("origin", "SIN")
    season  = params.get("season_keyword", "")
    header  = f"Destinations from {origin} — {season.title()} Season"

    by_country: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        country = r.get("countryName", "")
        city    = r.get("cityName", "")
        code    = r.get("destination", r.get("airportCode", ""))
        fare    = r.get("min_fare")
        currency = r.get("f_currency_code", r.get("currency_code", "SGD"))
        label   = city or code
        if fare is not None:
            label += f" ({code}) — from {currency} {float(fare):.0f}"
        elif code and city:
            label += f" ({code})"
        if label:
            by_country[country].append(label)

    lines = [f"\n{header}\n"]
    for country in sorted(by_country):
        lines.append(f"  {country}")
        for entry in sorted(by_country[country]):
            lines.append(f"    • {entry}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# destinations_good_weather_in_month
# ---------------------------------------------------------------------------

def format_good_weather_destinations(rows: list[dict], params: dict) -> str:
    """destinations_good_weather_in_month — destinations with best-time flag for the given month."""
    if not rows:
        month_num = params.get("month_num")
        try:
            month_label = MONTH_NAMES[int(month_num) - 1]
        except (TypeError, ValueError, IndexError):
            month_label = str(month_num or "")
        return f"\n  No destinations with great weather in {month_label} found in our data.\n"

    origin    = params.get("origin", "SIN")
    month_num = params.get("month_num")
    try:
        month_label = MONTH_NAMES[int(month_num) - 1]
    except (TypeError, ValueError, IndexError):
        month_label = str(month_num or "")

    header = f"Best weather destinations from {origin} in {month_label}"

    by_country: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        country  = r.get("countryName", "")
        city     = r.get("cityName", "")
        code     = r.get("destination", r.get("airportCode", ""))
        fare     = r.get("min_fare")
        currency = r.get("f_currency_code", r.get("currency_code", "SGD"))
        label    = city or code
        if fare is not None:
            label += f" ({code}) — from {currency} {float(fare):.0f}"
        elif code and city:
            label += f" ({code})"
        if label:
            by_country[country].append(label)

    lines = [f"\n{header}\n"]
    for country in sorted(by_country):
        lines.append(f"  {country}")
        for entry in sorted(by_country[country]):
            lines.append(f"    • {entry}")
    lines.append("")
    return "\n".join(lines)


def format_transit_route(rows: list[dict], params: dict) -> str:
    """cheapest_transit_route — two-leg connecting itinerary."""
    origin = params.get("origin", "")
    destination = params.get("destination", "")

    if not rows:
        return (
            f"\n  No connecting flights found from {origin} to {destination}.\n"
            "  Try a different date range or check if the route exists.\n"
        )

    lines = [f"\nNo direct flights from {origin} to {destination} — showing connecting options\n"]

    seen: set = set()
    count = 0
    for r in rows:
        hub          = r.get("transit_hub", "")
        leg1_dep     = r.get("leg1_departs", "")
        leg1_arr     = r.get("leg1_arrives", "")
        leg2_dep     = r.get("leg2_departs", "")
        leg2_arr     = r.get("leg2_arrives", "")
        leg1_airline = r.get("leg1_airline", "")
        leg2_airline = r.get("leg2_airline", "")
        leg1_fare    = r.get("leg1_fare")
        leg2_fare    = r.get("leg2_fare")
        leg1_cur     = r.get("leg1_currency", "")
        leg2_cur     = r.get("leg2_currency", "")
        leg1_dur     = r.get("leg1_duration_mins")
        leg2_dur     = r.get("leg2_duration_mins")
        layover      = r.get("layover_mins")

        key = (leg1_dep, leg2_dep)
        if key in seen:
            continue
        seen.add(key)
        count += 1
        if count > 5:
            break

        dep1 = _fmt_dt(leg1_dep)
        arr1 = _fmt_dt(leg1_arr)
        dep2 = _fmt_dt(leg2_dep)
        arr2 = _fmt_dt(leg2_arr)
        fare1 = f"{leg1_cur} {float(leg1_fare):.2f}" if leg1_fare is not None else ""
        fare2 = f"{leg2_cur} {float(leg2_fare):.2f}" if leg2_fare is not None else ""
        dur1  = _fmt_dur(leg1_dur) if leg1_dur else ""
        dur2  = _fmt_dur(leg2_dur) if leg2_dur else ""
        lay   = _fmt_dur(layover) if layover else ""

        lines.append(f"  {origin} → {hub} → {destination}")
        leg1_parts = [x for x in [dep1, arr1, leg1_airline, dur1, fare1] if x]
        lines.append(f"    Leg 1 : {origin} → {hub}  ·  {' · '.join(leg1_parts)}")
        if lay:
            lines.append(f"    Layover : {hub} — {lay}")
        leg2_parts = [x for x in [dep2, arr2, leg2_airline, dur2, fare2] if x]
        lines.append(f"    Leg 2 : {hub} → {destination}  ·  {' · '.join(leg2_parts)}")
        lines.append("")

    return "\n".join(lines)


def _best_months(g: Graph, city_uri, month_filter) -> tuple[list[str], bool | None]:
    """
    Returns (best_month_names, is_travel_month_best).
    Always returns all best months; is_travel_month_best is True/False when
    month_filter is set, else None.
    """
    best_month_nums: set[str] = set()
    months = []
    for obs in g.objects(city_uri, EX.prop_hasWeatherObservation):
        best       = _str(g, obs, EX.prop_bestTimeToVisit)
        month_name = _str(g, obs, EX.prop_monthName)
        month_num  = _str(g, obs, EX.prop_monthNum)
        if best and best.lower() == "true" and month_name:
            months.append((int(month_num) if month_num else 99, month_name))
            if month_num:
                best_month_nums.add(month_num)
    months.sort()
    is_best = (str(month_filter) in best_month_nums) if month_filter else None
    return [m[1] for m in months], is_best
