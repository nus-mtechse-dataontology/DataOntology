"""
Format pipeline results for terminal output.

vacation_plan  → rich markdown narrative from rdflib Graph
generic        → aligned table from list[dict]
"""

from __future__ import annotations

from rdflib import Graph, Namespace

EX = Namespace("http://dataontology.example/graph/")


# ---------------------------------------------------------------------------
# vacation_plan — walk the rdflib CONSTRUCT graph
# ---------------------------------------------------------------------------

def format_vacation_plan(g: Graph, params: dict, visa_rows: list[dict]) -> str:
    airport_uri = _find_airport(g, params["destination_airport_code"])
    if airport_uri is None:
        return "[ERROR] Airport not found in CONSTRUCT result — check GraphDB data."

    city_uri = g.value(airport_uri, EX.prop_inCity)
    country_uri = g.value(city_uri, EX.prop_belongsToCountry) if city_uri else None

    # Core facts
    airport_name = _str(g, airport_uri, EX.prop_airportName)
    airport_code = params["destination_airport_code"]
    city_name = _str(g, city_uri, EX.prop_cityName)
    country_name = _str(g, country_uri, EX.prop_countryName)
    continent = _str(g, country_uri, EX.prop_continent)
    region = _str(g, country_uri, EX.prop_region)
    safety_tier = _str(g, city_uri, EX.prop_safetyTier)
    solo_safe = _bool(g, city_uri, EX.prop_soloFemaleSafe)
    cost_idx = _str(g, city_uri, EX.prop_costOfLivingIndex)
    capital_uri = g.value(country_uri, EX.prop_capitalCity) if country_uri else None
    capital_name = _str(g, capital_uri, EX.prop_cityName) if capital_uri else None

    # Airport amenities
    terminal_count = _str(g, airport_uri, EX.prop_terminalCount)
    is_intl = _bool(g, airport_uri, EX.prop_isInternational)
    has_lounge = _bool(g, airport_uri, EX.prop_hasLounge)
    has_transit = _bool(g, airport_uri, EX.prop_hasTransitHotel)

    # Language, timezone, currency
    lang_uri = g.value(city_uri, EX.prop_usesPrimaryLanguage)
    language = _str(g, lang_uri, EX.prop_languageName)
    timezone = _str(g, city_uri, EX.prop_timezoneName)
    utc_offset = _str(g, city_uri, EX.prop_utcOffset)
    currency_uri = g.value(country_uri, EX.prop_hasCurrency) if country_uri else None
    currency_code = _str(g, currency_uri, EX.prop_currencyCode)
    currency_name = _str(g, currency_uri, EX.prop_currencyName)
    exchange_rate = _str(g, currency_uri, EX.prop_exchangeRate)

    # Best months
    month_filter = params.get("month_num")
    best_months, is_travel_month_best = _best_months(g, city_uri, month_filter)

    # Transport
    transport_modes = sorted({
        str(g.value(t, EX.prop_transportModeName))
        for t in g.objects(city_uri, EX.prop_hasTransportMode)
        if g.value(t, EX.prop_transportModeName)
    })
    public_transport = _bool(g, city_uri, EX.prop_publicTransportWidelyUsedInCountry)

    # Neighbourhoods
    neighbourhoods = [
        (_str(g, a, EX.prop_subcityAreaName), _str(g, a, EX.prop_areaSummary))
        for a in g.objects(city_uri, EX.prop_hasSubcityArea)
        if g.value(a, EX.prop_subcityAreaName)
    ]
    neighbourhoods.sort(key=lambda x: x[0] or "")

    # Cuisines
    cuisines = sorted({
        str(g.value(c, EX.prop_cuisineType))
        for c in g.objects(city_uri, EX.prop_hasCuisine)
        if g.value(c, EX.prop_cuisineType)
    })

    # Attractions by tier
    attractions = {"must_see": [], "popular": [], "local_gem": []}
    for a in g.objects(city_uri, EX.prop_hasAttraction):
        name = _str(g, a, EX.prop_attractionName)
        tier = _str(g, a, EX.prop_attractionTier)
        if name and tier in attractions:
            attractions[tier].append(name)
    for tier in attractions:
        attractions[tier].sort()

    # Festivals (optionally filtered by month)
    festivals = []
    for f in g.objects(city_uri, EX.prop_hasFestival):
        fname = _str(g, f, EX.prop_festivalName)
        fmonth = _str(g, f, EX.prop_festivalMonthNum)
        ftype = _str(g, f, EX.prop_festivalType)
        if month_filter and fmonth and str(month_filter) != fmonth:
            continue
        festivals.append((fname, fmonth, ftype))
    festivals.sort(key=lambda x: (x[1] or "0", x[0] or ""))

    # Travel styles
    styles = sorted({
        str(g.value(s, EX.prop_travelStyleName))
        for s in g.objects(city_uri, EX.prop_hasTravelStyle)
        if g.value(s, EX.prop_travelStyleName)
    })

    # --- Assemble markdown ---
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  {city_name}, {country_name} — Vacation Guide")
    lines.append(f"{'='*60}\n")

    # Overview
    lines.append("OVERVIEW")
    loc_parts = [p for p in [region, continent] if p]
    lines.append("  " + " | ".join(loc_parts) + (f" | Capital: {capital_name}" if capital_name else ""))
    if solo_safe is True:
        safety_label = "Safe"
    elif solo_safe is False:
        safety_label = safety_tier or "Not safe"
    else:
        safety_label = safety_tier or "unknown"
    cost_str = _cost_comparison(float(cost_idx)) if cost_idx else ""
    lines.append(f"  Safety: {safety_label}" +
                 (f"\n  Cost: {cost_str}" if cost_str else ""))
    lines.append("")

    # Best time
    lines.append("BEST TIME TO VISIT")
    if best_months:
        lines.append("  " + " · ".join(best_months))
        if is_travel_month_best is True:
            lines.append("  Great timing — you're visiting during peak season!")
        elif is_travel_month_best is False:
            month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            travel_month_name = month_names[int(month_filter) - 1] if month_filter else ""
            lines.append(f"  Note: {travel_month_name} is not peak season — expect more crowds or rain.")
    else:
        lines.append("  No best-month data available.")
    lines.append("")

    # Airport
    lines.append("AIRPORT")
    intl_str = "International" if is_intl else "Domestic"
    term_str = f"{terminal_count} terminal(s)" if terminal_count else ""
    lines.append(f"  {airport_name} ({airport_code}) · {intl_str}" + (f" · {term_str}" if term_str else ""))
    amenities = []
    if has_lounge:
        amenities.append("Lounge")
    if has_transit:
        amenities.append("Transit hotel")
    if amenities:
        lines.append("  Amenities: " + " | ".join(amenities))
    lines.append("")

    # Getting around
    lines.append("GETTING AROUND")
    if transport_modes:
        lines.append("  " + " · ".join(transport_modes))
    pt_str = "widely used" if public_transport else ("not widely used" if public_transport is False else "")
    if pt_str and country_name:
        lines.append(f"  Public transport {pt_str} in {country_name}")
    lines.append("")

    # Neighbourhoods
    lines.append("NEIGHBOURHOODS")
    if neighbourhoods:
        for name, summary in neighbourhoods:
            summary_short = (summary[:60] + "...") if summary and len(summary) > 60 else (summary or "")
            lines.append(f"  {name:<20} {summary_short}")
    else:
        lines.append("  No neighbourhood data available.")
    lines.append("")

    # Food
    lines.append("FOOD")
    lines.append("  " + (" · ".join(cuisines) if cuisines else "No cuisine data available."))
    lines.append("")

    # Attractions
    lines.append("ATTRACTIONS")
    for tier_key, label in [("must_see", "Must-see"), ("popular", "Popular"), ("local_gem", "Local gem")]:
        items = attractions[tier_key]
        if items:
            lines.append(f"  {label:<12}: {' · '.join(items)}")
    if not any(attractions.values()):
        lines.append("  No attraction data available.")
    lines.append("")

    # Festivals
    lines.append("FESTIVALS" + (f" (month {month_filter})" if month_filter else ""))
    if festivals:
        for fname, fmonth, ftype in festivals:
            lines.append(f"  {fname} — {ftype} · month {fmonth}")
    else:
        lines.append("  No festival data" + (" for this month." if month_filter else " available."))
    lines.append("")

    # Travel styles
    lines.append("TRAVEL STYLES")
    lines.append("  " + (" · ".join(styles) if styles else "No data available."))
    lines.append("")

    # Visa
    lines.append("VISA")
    if visa_rows:
        v = visa_rows[0]
        required = v.get("visaRequired", "").lower()
        policy = v.get("visaPolicyName", "")
        duration = v.get("visaDurationDays", "")
        url = v.get("onlineApplyUrl", "")
        passport = v.get("passportCountryName", "")
        dest = v.get("destinationCountryName", "")
        vis_str = "Required" if required == "true" else "Not required"
        lines.append(f"  {vis_str} for {passport} passport to {dest}")
        if policy:
            lines.append(f"  Policy: {policy}")
        if duration:
            lines.append(f"  Stay up to {duration} days")
        if url:
            lines.append(f"  Apply: {url}")
    else:
        lines.append("  Visa info not available (no passport_country_code provided).")
    lines.append("")

    # Currency
    lines.append("CURRENCY")
    if currency_code:
        rate_str = f" · 1 SGD ≈ {exchange_rate} {currency_code}" if exchange_rate else ""
        lines.append(f"  {currency_name} ({currency_code}){rate_str}")
    else:
        lines.append("  No currency data available.")
    lines.append("")

    # Timezone
    lines.append("TIMEZONE")
    tz_str = timezone or "unknown"
    utc_str = f" · UTC{utc_offset}" if utc_offset else ""
    lines.append(f"  {tz_str}{utc_str}")
    lines.append("")

    # Language
    lines.append("LANGUAGE")
    lines.append(f"  {language or 'No data available.'}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flight result + destination enrichment — narrative format
# ---------------------------------------------------------------------------

def format_flight_with_destination(
    rows: list[dict],
    g: Graph,
    params: dict,
    visa_rows: list[dict],
) -> str:
    airport_code = params.get("destination_airport_code", "")
    airport_uri = _find_airport(g, airport_code)

    city_uri = g.value(airport_uri, EX.prop_inCity) if airport_uri else None
    country_uri = g.value(city_uri, EX.prop_belongsToCountry) if city_uri else None

    city_name = _str(g, city_uri, EX.prop_cityName) or airport_code
    country_name = _str(g, country_uri, EX.prop_countryName) or ""
    airport_name = _str(g, airport_uri, EX.prop_airportName) or airport_code

    lines = []

    # ── Flight summary ────────────────────────────────────────────
    dest_label = f"{city_name}, {country_name}".strip(", ")
    lines.append(f"\n{'='*60}")
    lines.append(f"  Flights to {dest_label}")
    lines.append(f"{'='*60}")

    if not rows:
        lines.append("\n  No flights found for these dates.")
    else:
        lines.append("")
        for r in rows:
            dep = _fmt_dt(r.get("f_departure_date", ""))
            arr = _fmt_dt(r.get("f_arrival_date", ""))
            airline = r.get("f_airline_code", "")
            cabin = r.get("f_cabin_class", "")
            fare_raw = r.get("cheapest_fare") or r.get("f_total_amount_fare_total", "")
            fare = f"{float(fare_raw):.2f}" if fare_raw else ""
            currency = r.get("f_currency_code", "")
            duration = r.get("f_flight_duration", "")
            dur_str = f" · {int(duration)//60}h{int(duration)%60:02d}m" if duration else ""
            lines.append(f"  • {airline} | {dep} → {arr}{dur_str} | {cabin} | {currency} {fare}")
        lines.append("")

    # ── Destination brief ─────────────────────────────────────────
    lines.append(f"About {city_name}" + (f", {country_name}" if country_name else ""))
    lines.append("")

    # Airport
    lines.append(f"  Airport    : {airport_name} ({airport_code})")

    # Safety
    safety_tier = _str(g, city_uri, EX.prop_safetyTier)
    solo_safe = _bool(g, city_uri, EX.prop_soloFemaleSafe)
    cost_idx = _str(g, city_uri, EX.prop_costOfLivingIndex)
    if solo_safe is True:
        safety_label = "Safe"
    elif solo_safe is False:
        safety_label = safety_tier or "Not safe"
    else:
        safety_label = safety_tier or None
    if safety_label:
        lines.append(f"  Safety     : {safety_label}")
    if cost_idx:
        lines.append(f"  Cost       : {_cost_comparison(float(cost_idx))}")

    # Best months
    month_filter = params.get("month_num")
    best_months, is_travel_month_best = _best_months(g, city_uri, month_filter)
    if best_months:
        month_line = f"  Best time  : {' · '.join(best_months)}"
        if is_travel_month_best is True:
            month_line += " ✓ (you're going at the right time!)"
        elif is_travel_month_best is False:
            month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            travel_name = month_names[int(month_filter) - 1] if month_filter else ""
            month_line += f" (heads up — {travel_name} is off-peak)"
        lines.append(month_line)

    # Weather for travel month if known
    month_num = params.get("month_num")
    if month_num:
        for obs in g.objects(city_uri, EX.prop_hasWeatherObservation):
            if _str(g, obs, EX.prop_monthNum) == str(month_num):
                temp = _str(g, obs, EX.prop_avgTempC)
                rain = _str(g, obs, EX.prop_avgRainfallMm)
                summary = _str(g, obs, EX.prop_weatherSummary)
                weather_parts = []
                if temp:
                    weather_parts.append(f"~{temp}°C")
                if rain:
                    weather_parts.append(f"{rain}mm rain")
                if summary:
                    weather_parts.append(summary)
                if weather_parts:
                    lines.append(f"  Weather    : {' · '.join(weather_parts)}")
                break

    # Attractions
    must_see = sorted([
        _str(g, a, EX.prop_attractionName)
        for a in g.objects(city_uri, EX.prop_hasAttraction)
        if _str(g, a, EX.prop_attractionTier) == "must_see"
        and _str(g, a, EX.prop_attractionName)
    ])
    if must_see:
        lines.append(f"  Must-see   : {' · '.join(must_see[:4])}")

    # Cuisine
    cuisines = sorted({
        str(g.value(c, EX.prop_cuisineType))
        for c in g.objects(city_uri, EX.prop_hasCuisine)
        if g.value(c, EX.prop_cuisineType)
    })
    if cuisines:
        lines.append(f"  Cuisine    : {' · '.join(cuisines[:5])}")

    # Currency
    currency_uri = g.value(country_uri, EX.prop_hasCurrency) if country_uri else None
    currency_code = _str(g, currency_uri, EX.prop_currencyCode)
    exchange_rate = _str(g, currency_uri, EX.prop_exchangeRate)
    if currency_code:
        rate_str = f" · 1 SGD ≈ {exchange_rate} {currency_code}" if exchange_rate else ""
        lines.append(f"  Currency   : {currency_code}{rate_str}")

    # Visa
    if visa_rows:
        v = visa_rows[0]
        required = v.get("visaRequired", "").lower()
        policy = v.get("visaPolicyName", "")
        duration_days = v.get("visaDurationDays", "")
        vis_str = "Required" if required == "true" else "Not required"
        visa_line = f"  Visa       : {vis_str} for Singapore passport"
        if policy:
            visa_line += f" ({policy})"
        if duration_days:
            visa_line += f" · Stay up to {duration_days} days"
        lines.append(visa_line)
    else:
        lines.append("  Visa       : Provide passport country for visa info")

    # Timezone
    tz = _str(g, city_uri, EX.prop_timezoneName)
    utc = _str(g, city_uri, EX.prop_utcOffset)
    if tz:
        lines.append(f"  Timezone   : {tz}" + (f" (UTC{utc})" if utc else ""))

    lines.append("")
    return "\n".join(lines)


def _fmt_dt(dt_str: str) -> str:
    """Format ISO datetime '2026-05-30T07:50:00' → '30 May 07:50'."""
    if not dt_str or "T" not in dt_str:
        return dt_str
    date_part, time_part = dt_str.split("T", 1)
    try:
        _, m, d = date_part.split("-")
        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        mon = month_names[int(m) - 1]
        return f"{int(d)} {mon} {time_part[:5]}"
    except Exception:
        return dt_str


# ---------------------------------------------------------------------------
# Highlights — attractions + festivals this month + weather (compact)
# ---------------------------------------------------------------------------

def format_highlights(rows: list[dict], params: dict) -> str:
    """Format destination_highlights SELECT results: weather + attractions + festivals."""
    if not rows:
        return "\n  No highlights data found.\n"

    airport_code = params.get("destination_airport_code", "")
    month_num = params.get("month_num")
    month_names = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    month_label = f" in {month_names[int(month_num)-1]}" if month_num else ""

    # Partition rows by type
    attractions: dict[str, list[str]] = {"must_see": [], "popular": [], "local_gem": []}
    festivals: list[tuple[str, str]] = []   # (name, type)
    weather: dict = {}

    for r in rows:
        rt = r.get("resultType", "")
        if rt == "attraction":
            tier = r.get("tier", "")
            name = r.get("name", "")
            if tier in attractions and name:
                attractions[tier].append(name)
        elif rt == "festival":
            # Filter to requested month if specified
            row_month = r.get("monthNum", "")
            if month_num and row_month and str(month_num) != str(row_month):
                continue
            name = r.get("name", "")
            ftype = r.get("festivalType", "")
            if name:
                festivals.append((name, ftype))
        elif rt == "weather":
            # Pick only the row matching the requested month
            row_month = r.get("monthNum", "")
            if month_num and str(month_num) == str(row_month):
                weather = r

    lines = [f"\n  {airport_code} — Highlights{month_label}", ""]

    # Weather strip (only if month requested)
    if weather:
        temp = weather.get("avgTempC", "")
        rain = weather.get("avgRainfallMm", "")
        summary = weather.get("weatherSummary", "")
        parts = []
        if temp:
            parts.append(f"~{temp}°C")
        if rain:
            parts.append(f"{rain}mm rain")
        if summary:
            parts.append(summary)
        if parts:
            lines.append(f"  Weather   : {' · '.join(parts)}")
            lines.append("")

    # Attractions
    any_attractions = any(attractions.values())
    if any_attractions:
        lines.append("  What to do:")
        for tier_key, label in [("must_see", "Must-see"), ("popular", "Popular"), ("local_gem", "Local gem")]:
            items = sorted(attractions[tier_key])
            if items:
                lines.append(f"    {label:<12}: {' · '.join(items)}")
        lines.append("")

    # Festivals
    if festivals:
        label = f"Festivals{month_label}:" if month_num else "Festivals:"
        lines.append(f"  {label}")
        for fname, ftype in sorted(festivals):
            type_str = f" ({ftype})" if ftype else ""
            lines.append(f"    · {fname}{type_str}")
        lines.append("")
    elif month_num:
        lines.append(f"  No festivals in {month_names[int(month_num)-1]}.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Attractions — grouped by tier
# ---------------------------------------------------------------------------

def format_attractions(rows: list[dict], params: dict) -> str:
    """Format destination_attractions SELECT results grouped by tier."""
    if not rows:
        return "\n  No attraction data found.\n"

    tiers = {"must_see": [], "popular": [], "local_gem": []}
    other = []
    for r in rows:
        name = r.get("attractionName", "")
        tier = r.get("attractionTier", "")
        if tier in tiers:
            tiers[tier].append(name)
        elif name:
            other.append(name)

    airport_code = params.get("destination_airport_code", "")
    month_num = params.get("month_num")
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    month_label = f" in {month_names[int(month_num)-1]}" if month_num else ""

    lines = [f"\n  {airport_code} — Things to Do{month_label}", ""]
    for tier_key, label in [("must_see", "Must-see"), ("popular", "Popular"), ("local_gem", "Local gem")]:
        items = sorted(tiers[tier_key])
        if items:
            lines.append(f"  {label:<12}: {' · '.join(items)}")
    if other:
        lines.append(f"  {'Other':<12}: {' · '.join(sorted(other))}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generic — print list[dict] as aligned table
# ---------------------------------------------------------------------------

def format_table(rows: list[dict], intent_name: str = "") -> str:
    if not rows:
        return f"\n  No results returned for '{intent_name}'.\n"

    headers = list(rows[0].keys())
    col_widths = {h: max(len(h), max((len(str(r.get(h, "") or "")) for r in rows), default=0)) for h in headers}

    sep = "  " + "  ".join("-" * col_widths[h] for h in headers)
    header_line = "  " + "  ".join(h.ljust(col_widths[h]) for h in headers)

    lines = [f"\n  Results — {intent_name}", sep, header_line, sep]
    for row in rows:
        lines.append("  " + "  ".join(str(row.get(h, "") or "").ljust(col_widths[h]) for h in headers))
    lines.append(sep)
    lines.append(f"  {len(rows)} row(s)\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Reference cities — values sourced directly from dim_city_country_enrichment.csv
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
    """Return a friendly tour-guide sentence describing cost of living."""
    cheaper = [city for v, city in _COST_REFS if v < idx]
    pricier = [city for v, city in _COST_REFS if v > idx]

    # Pick 2 closest cheaper refs and 1 closest pricier ref
    ref_cheaper = cheaper[-2:] if len(cheaper) >= 2 else cheaper[-1:] if cheaper else []
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

    if parts:
        return f"{base} — {', '.join(parts)}."
    return f"{base}."


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


def _best_months(g: Graph, city_uri, month_filter) -> tuple[list[str], bool | None]:
    """
    Returns (best_month_names, is_travel_month_best).
    Always returns all best months regardless of month_filter.
    is_travel_month_best is True/False if month_filter is set, else None.
    """
    best_month_nums = set()
    months = []
    for obs in g.objects(city_uri, EX.prop_hasWeatherObservation):
        best = _str(g, obs, EX.prop_bestTimeToVisit)
        month_name = _str(g, obs, EX.prop_monthName)
        month_num = _str(g, obs, EX.prop_monthNum)
        if best and best.lower() == "true" and month_name:
            months.append((int(month_num) if month_num else 99, month_name))
            if month_num:
                best_month_nums.add(month_num)
    months.sort()
    is_best = (str(month_filter) in best_month_nums) if month_filter else None
    return [m[1] for m in months], is_best
