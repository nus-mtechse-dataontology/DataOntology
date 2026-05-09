import pytest
from rdflib import Graph, Namespace, URIRef, Literal
from graphdb.response import (
    _humanize, _fmt_rate, _normalise_safety, _strip_city_from_country,
    _fmt_month, _months_to_ranges, _normalise_policy, _fmt_dur,
    _fmt_fare, _fmt_dt, _fmt_col, _rename_row, EX, _duration_haul_label, _dest_list_header,
    format_vacation_plan, format_flight_with_destination, format_highlights,
    format_attractions, format_cheapest_month, format_airlines_on_route,
    format_visa_list, format_table, format_weather, format_country_weather,
    format_festivals, format_transport, format_cuisines, format_language,
    format_timezone, format_destination_currency, format_amenities,
    format_safety, format_neighborhoods, format_overview, format_travel_styles,
    format_best_months, format_visa_check, format_flight_count,
    format_aircraft_on_route, format_route_list, format_airports_in_city,
    format_language_destinations, format_festivals_by_month,
    format_cities_in_country, format_country_info, format_solo_female_destinations,
    format_exchange_rate, format_visa_duration, format_airports_with_amenity,
    format_safe_destinations, format_festivals_by_type, format_route_statistics,
    format_currency_list, format_departures, format_round_trip, format_transit_route,
    format_airport_info, format_destinations_by_season, format_good_weather_destinations
)

def test_duration_haul_label():
    # Both present
    assert "1–2h flight destinations from SIN" in _duration_haul_label({"max_duration_mins": 120, "min_duration_mins": 60}, "SIN", "")
    # Only min_d >= 480
    assert "Long-haul destinations from SIN" in _duration_haul_label({"min_duration_mins": 500}, "SIN", "")
    # Only max_d <= 240
    assert "Short-haul destinations from SIN" in _duration_haul_label({"max_duration_mins": 200}, "SIN", "")
    # Only max_d > 240
    assert "Medium-haul destinations from SIN" in _duration_haul_label({"max_duration_mins": 300}, "SIN", "")
    # None
    assert "Short-haul destinations from SIN" in _duration_haul_label({}, "SIN", "")
    # Invalid types
    assert "Short-haul destinations from SIN" in _duration_haul_label({"max_duration_mins": "abc"}, "SIN", "")

def test_dest_list_header():
    # Simple origin
    params = {"origin": "SIN"}
    assert "No destination specified — showing all destinations from SIN sorted by price" in _dest_list_header("all_destinations_from_origin", params)
    
    # With month
    params = {"origin": "SIN", "departure_month": "6"}
    assert "sorted by price in June 2026" in _dest_list_header("all_destinations_from_origin", params)
    
    # With invalid month (triggers except)
    params = {"origin": "SIN", "departure_month": "invalid"}
    assert "sorted by price" in _dest_list_header("all_destinations_from_origin", params)
    
    # With date
    params = {"origin": "SIN", "departure_date": "2026-06-01"}
    assert "sorted by price on 1 Jun 2026" in _dest_list_header("all_destinations_from_origin", params)
    
    # With invalid date (triggers except)
    params = {"origin": "SIN", "departure_date": "invalid-date"}
    assert "sorted by price" in _dest_list_header("all_destinations_from_origin", params)
    
    # With range
    params = {"origin": "SIN", "start_date": "2026-06-01", "end_date": "2026-06-30"}
    assert "sorted by price in June 2026" in _dest_list_header("all_destinations_from_origin", params)
    
    params = {"origin": "SIN", "start_date": "2026-06-01", "end_date": "2026-06-15"}
    assert "from 1 Jun 2026 to 15 Jun 2026" in _dest_list_header("all_destinations_from_origin", params)
    
    # With invalid range (triggers except)
    params = {"origin": "SIN", "start_date": "invalid", "end_date": "invalid"}
    assert "sorted by price" in _dest_list_header("all_destinations_from_origin", params)
    
    # With day_type
    params = {"origin": "SIN", "day_type": "weekday"}
    assert "(Weekdays only)" in _dest_list_header("all_destinations_from_origin", params)
    
    # Budget
    params = {"origin": "SIN", "budget": "500", "currency_code": "USD"}
    assert "under USD 500" in _dest_list_header("destinations_under_budget", params)
    
    # Unknown intent
    assert _dest_list_header("unknown", {}) == ""


    assert _humanize("snake_case") == "Snake Case"
    assert _humanize("camelCase") == "Camel Case"
    assert _humanize("Kebab-Case") == "Kebab Case"
    assert _humanize("") == ""
    assert _humanize(None) == ""
    assert _humanize(123) == "123"

def test_fmt_rate():
    assert _fmt_rate(17199) == "17,200"
    assert _fmt_rate(25.18) == "25"
    assert _fmt_rate(3.11) == "3.11"
    assert _fmt_rate(0.58) == "0.58"
    assert _fmt_rate(None) == ""
    assert _fmt_rate("invalid") == "invalid"

def test_normalise_safety():
    assert _normalise_safety("safe") == "Safe"
    assert _normalise_safety("moderate") == "Moderate"
    assert _normalise_safety("use_caution") == "Use Caution"
    assert _normalise_safety("high risk") == "High Risk"
    assert _normalise_safety("unknown_tier") == "Unknown Tier"
    assert _normalise_safety(None) == ""

def test_strip_city_from_country():
    assert _strip_city_from_country("Hong Kong", "Hong Kong SAR, China") == "Hong Kong SAR, China"
    assert _strip_city_from_country("Tokyo", "Japan") == "Japan"
    assert _strip_city_from_country(None, "Japan") == "Japan"
    assert _strip_city_from_country("Tokyo", None) == ""

def test_fmt_month():
    assert _fmt_month("2026-06") == "June 2026"
    assert _fmt_month("invalid") == "invalid"
    assert _fmt_month(None) is None


def test_months_to_ranges():
    assert _months_to_ranges([1, 2, 3, 9, 10, 11, 12]) == "Jan–Mar · Sep–Dec"
    assert _months_to_ranges([4, 5]) == "Apr–May"
    assert _months_to_ranges([1]) == "Jan"
    assert _months_to_ranges([]) == ""


def test_normalise_policy():
    assert _normalise_policy("evisa_required") == "eVisa Required"
    assert _normalise_policy("visa_not_required") == "Visa Not Required"
    assert _normalise_policy("Unknown Policy") == "Unknown Policy"
    assert _normalise_policy("") == ""
    assert _normalise_policy(None) == ""


def test_fmt_dur():
    assert _fmt_dur(165) == "2h45m"
    assert _fmt_dur("165") == "2h45m"
    assert _fmt_dur(None) == ""
    assert _fmt_dur("") == ""
    assert _fmt_dur("invalid") == "invalid"

def test_fmt_fare():
    assert _fmt_fare(151.5, "SGD") == "SGD 151.50"
    assert _fmt_fare(151.5) == "151.50"
    assert _fmt_fare(None) == ""
    assert _fmt_fare("") == ""
    assert _fmt_fare("invalid") == "invalid"

def test_fmt_dt():
    assert _fmt_dt("2026-05-30T07:50:00") == "30 May 07:50"
    assert _fmt_dt("invalid") == "invalid"
    assert _fmt_dt(None) == ""
    assert _fmt_dt("2026-05-30") == "2026-05-30"
    assert _fmt_dt("2026-13-30T07:50:00") == "2026-13-30T07:50:00"

def test_fmt_col():
    assert _fmt_col("f_flight_duration", 165) == "2h45m"
    assert _fmt_col("f_departure_date", "2026-05-30T07:50:00") == "30 May 07:50"
    assert _fmt_col("min_fare", 151.5) == "151.50"
    assert _fmt_col("some_other_col", "some_val") == "some_val"
    assert _fmt_col("some_col", None) == ""
    assert _fmt_col("min_fare", "invalid") == "invalid"


def test_rename_row():
    row = {"f_departure_airport_code": "SIN", "unknown_col": "val"}
    expected = {"from": "SIN", "unknown_col": "val"}
    assert _rename_row(row) == expected

def _setup_mock_graph():
    g = Graph()
    # Airport
    airport = URIRef("http://dataontology.example/graph/airport/BKK")
    city = URIRef("http://dataontology.example/graph/city/Bangkok")
    country = URIRef("http://dataontology.example/graph/country/Thailand")
    
    g.add((airport, EX.prop_airportCode, Literal("BKK")))
    g.add((airport, EX.prop_airportName, Literal("Suvarnabhumi Airport")))
    g.add((airport, EX.prop_inCity, city))
    g.add((city, EX.prop_cityName, Literal("Bangkok")))
    g.add((city, EX.prop_belongsToCountry, country))
    g.add((country, EX.prop_countryName, Literal("Thailand")))
    g.add((country, EX.prop_continent, Literal("Asia")))
    g.add((city, EX.prop_safetyTier, Literal("moderate")))
    g.add((city, EX.prop_soloFemaleSafe, Literal(True)))
    
    return g, airport, city, country

def test_format_vacation_plan():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    visa_rows = [{"visaRequired": "false", "passportCountryName": "Singapore"}]
    
    res = format_vacation_plan(g, params, visa_rows)
    assert "Bangkok, Thailand" in res
    assert "Moderate" in res
    assert "No visa required" in res
    assert "Ask \"Flights to Bangkok\"" in res

def test_format_vacation_plan_airport_not_found():
    g = Graph()
    params = {"destination_airport_code": "UNKNOWN"}
    res = format_vacation_plan(g, params, [])
    assert "[ERROR] Airport not found" in res

def test_format_vacation_plan_complex_data():
    g, airport, city, country = _setup_mock_graph()
    # Add more data
    g.add((city, EX.prop_costOfLivingIndex, Literal("42.4")))
    g.add((city, EX.prop_hasTransportMode, URIRef("http://t1")))
    g.add((URIRef("http://t1"), EX.prop_transportModeName, Literal("taxi")))
    g.add((city, EX.prop_publicTransportWidelyUsedInCountry, Literal(True)))
    g.add((city, EX.prop_hasCuisine, URIRef("http://c1")))
    g.add((URIRef("http://c1"), EX.prop_cuisineType, Literal("Thai")))
    
    params = {"destination_airport_code": "BKK"}
    visa_rows = [{
        "visaRequired": "true", 
        "visaPolicyName": "evisa_required", 
        "visaDurationDays": "30",
        "passportCountryName": "Singapore"
    }]
    
    res = format_vacation_plan(g, params, visa_rows)
    assert "eVisa Required · 30 days" in res
    assert "Easy on the wallet" in res
    assert "Getting around: Taxi — widely used" in res
    assert "Eat: Thai — Pad Thai · Green Curry · Mango Sticky Rice" in res

def test_format_vacation_plan_edge_cases():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK", "month_num": "6"}
    
    # 1. Attraction with unknown tier (line 436)
    attr = URIRef("http://attr1")
    g.add((city, EX.prop_hasAttraction, attr))
    g.add((attr, EX.prop_attractionName, Literal("Unknown Place")))
    g.add((attr, EX.prop_attractionTier, Literal("unknown_tier")))
    
    # 2. Festival with month mismatch and non-digit month (lines 446-450)
    fest = URIRef("http://fest1")
    g.add((city, EX.prop_hasFestival, fest))
    g.add((fest, EX.prop_festivalName, Literal("Mismatch Fest")))
    g.add((fest, EX.prop_festivalMonthNum, Literal("12"))) # Mismatch with params month_num="6"
    
    fest2 = URIRef("http://fest2")
    g.add((city, EX.prop_hasFestival, fest2))
    g.add((fest2, EX.prop_festivalName, Literal("Invalid Month Fest")))
    g.add((fest2, EX.prop_festivalMonthNum, Literal("invalid")))
    
    # 3. Capping tests (attractions > 4, festivals > 3, hoods > 4)
    for i in range(6):
        a = URIRef(f"http://a{i}")
        g.add((city, EX.prop_hasAttraction, a))
        g.add((a, EX.prop_attractionName, Literal(f"Attr {i}")))
        g.add((a, EX.prop_attractionTier, Literal("must_see")))
        
        f = URIRef(f"http://f{i}")
        g.add((city, EX.prop_hasFestival, f))
        g.add((f, EX.prop_festivalName, Literal(f"Fest {i}")))
        g.add((f, EX.prop_festivalMonthNum, Literal("6")))
        
        h = URIRef(f"http://h{i}")
        g.add((city, EX.prop_hasSubcityArea, h))
        g.add((h, EX.prop_subcityAreaName, Literal(f"Hood {i}")))
        g.add((h, EX.prop_areaSummary, Literal("Summary")))
    
    # 4. Info line (currency, utc, language)
    curr = URIRef("http://curr1")
    g.add((country, EX.prop_hasCurrency, curr))
    g.add((curr, EX.prop_currencyCode, Literal("THB")))
    g.add((curr, EX.prop_exchangeRate, Literal("25.5")))
    g.add((city, EX.prop_utcOffset, Literal("+7")))
    lang = URIRef("http://lang1")
    g.add((city, EX.prop_usesPrimaryLanguage, lang))
    g.add((lang, EX.prop_languageName, Literal("Thai")))
    
    # 5. Visa cases (req="false", req="true" with missing data)
    visa_rows_false = [{"visaRequired": "false"}]
    res_false = format_vacation_plan(g, params, visa_rows_false)
    assert "No visa required" in res_false
    
    visa_rows_true = [{"visaRequired": "true", "visaPolicyName": None, "visaDurationDays": None}]
    res_true = format_vacation_plan(g, params, visa_rows_true)
    assert "Visa required" in res_true
    
    # 6. Cost comparison exception
    g.add((city, EX.prop_costOfLivingIndex, Literal("invalid_cost")))
    res_cost = format_vacation_plan(g, params, [])
    # Should not crash, cost label should be missing
    
    res = format_vacation_plan(g, params, [])
    assert "+2 more" in res # Attractions capping
    assert "Festivals: Fest 0 (Jun) · Fest 1 (Jun) · Fest 2 (Jun) +3 more" in res # Festivals capping
    assert "Stay: Hood 0 · Hood 1 · Hood 2 · Hood 3 +2 more" in res # Hoods capping
    assert "1 SGD ≈ 26 THB" in res # Currency
    assert "UTC+7" in res # UTC
    assert "Thai" in res # Language

def test_format_vacation_plan_best_months():
    g, airport, city, country = _setup_mock_graph()
    
    # Add weather observations
    obs1 = URIRef("http://obs1")
    g.add((city, EX.prop_hasWeatherObservation, obs1))
    g.add((obs1, EX.prop_bestTimeToVisit, Literal("true")))
    g.add((obs1, EX.prop_monthName, Literal("June")))
    g.add((obs1, EX.prop_monthNum, Literal("6")))
    
    obs2 = URIRef("http://obs2")
    g.add((city, EX.prop_hasWeatherObservation, obs2))
    g.add((obs2, EX.prop_bestTimeToVisit, Literal("true")))
    g.add((obs2, EX.prop_monthName, Literal("July")))
    g.add((obs2, EX.prop_monthNum, Literal("7")))
    
    # 1. month_filter matches best month
    params = {"destination_airport_code": "BKK", "month_num": "6"}
    res = format_vacation_plan(g, params, [])
    assert "Best time: Jun–Jul" in res
    assert "Note: Jun is outside peak season." not in res
    
    # 2. month_filter does NOT match best month
    params = {"destination_airport_code": "BKK", "month_num": "12"}
    res = format_vacation_plan(g, params, [])
    assert "Note: Dec is outside peak season." in res

def test_format_vacation_plan_minimal_data():
    g = Graph()
    # Just the bare minimum to avoid [ERROR] Airport not found
    airport = URIRef("http://BKK")
    g.add((airport, EX.prop_airportCode, Literal("BKK")))
    
    params = {"destination_airport_code": "BKK"}
    res = format_vacation_plan(g, params, [])
    
    assert "BKK" in res
    assert "Getting around: Check local transport apps on arrival" in res
    # Ensure it doesn't crash with missing safety, cost, etc.

def test_format_vacation_plan_no_visa():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    # visa_rows is empty
    res = format_vacation_plan(g, params, [])
    # No visa required/required should not be in summary_parts
    assert "visa required" not in res.lower()
    assert "No visa required" not in res



def test_format_flight_with_destination():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    rows = [{
        "f_airline_code": "SQ",
        "f_departure_date": "2026-05-30T07:50:00",
        "f_arrival_date": "2026-05-30T11:00:00",
        "f_cabin_class": "Economy",
        "cheapest_fare": 200.0,
        "f_currency_code": "SGD",
        "f_flight_duration": 130
    }]
    visa_rows = [{"visaRequired": "false"}]
    
    res = format_flight_with_destination(rows, g, params, visa_rows, "flights_on_date")
    assert "Bangkok, Thailand" in res
    assert "SQ" in res
    assert "200.00" in res

def test_format_flight_with_destination_no_flights():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    res = format_flight_with_destination([], g, params, [], "flights_on_date")
    assert "No flights found" in res

def test_format_flight_with_destination_capping():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    rows = [{"f_airline_code": f"A{i}"} for i in range(10)]
    
    # Test cheapest (CAP_3)
    res_cheapest = format_flight_with_destination(rows, g, params, [], "cheapest_flight_on_route")
    assert "Showing cheapest 3 of 10 flights" in res_cheapest
    
    # Test fastest (shortest_flight_on_route)
    res_fastest = format_flight_with_destination(rows, g, params, [], "shortest_flight_on_route")
    assert "Showing fastest 3 of 10 flights" in res_fastest
    
    # Test next (CAP_5)
    res_next = format_flight_with_destination(rows, g, params, [], "next_available_flight")
    assert "Showing next 5 of 10 flights" in res_next

def test_format_flight_with_destination_visa_required():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    rows = [{"f_airline_code": "SQ"}]
    visa_rows = [{"visaRequired": "true", "visaDurationDays": "30"}]
    res = format_flight_with_destination(rows, g, params, visa_rows)
    assert "Visa required · 30 days" in res


def test_format_highlights():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok", "month_num": "6"}
    rows = [
        {"resultType": "attraction", "tier": "must_see", "name": "Grand Palace"},
        {"resultType": "festival", "monthNum": "6", "name": "Songkran", "festivalType": "culture"},
        {"resultType": "festival", "monthNum": "4", "name": "Other Fest", "festivalType": "culture"},
        {"resultType": "weather", "monthNum": "6", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"},
        {"resultType": "weather", "monthNum": "4", "avgTempC": "25", "avgRainfallMm": "50", "weatherSummary": "Cool"},
    ]
    res = format_highlights(rows, params)
    assert "Bangkok — Highlights in June" in res
    assert "Grand Palace" in res
    assert "Songkran" in res
    assert "Other Fest" not in res
    assert "30°C" in res
    assert "25°C" not in res


def test_format_visa_list():
    params = {"passport_country_code": "SG", "visa_policy_name": "visa_not_required"}
    rows = [
        {"destinationCountryCode": "TH", "destinationCountryName": "Thailand", "visaDurationDays": None},
        {"destinationCountryCode": "JP", "destinationCountryName": "Japan", "visaDurationDays": "90"},
        {"destinationCountryCode": "SG", "destinationCountryName": "Singapore", "visaDurationDays": None}, # Own country
    ]
    res = format_visa_list(rows, params)
    assert "Visa Not Required destinations" in res
    assert "90 days: Japan" in res
    assert "No fixed limit: Thailand" in res
    assert "Singapore" not in res



def test_format_visa_list_no_data():
    res = format_visa_list([], {})
    assert "No visa destination data found" in res

def test_format_table_destinations():
    params = {"origin": "SIN", "destination": "BKK", "day_type": "weekday"}
    rows = [{
        "destination": "Bangkok (BKK)",
        "from": 200.0,
        "currency": "SGD",
        "first_dep": "2026-05-30T07:50:00"
    }]
    res = format_table(rows, "all_destinations_from_origin", params)
    assert "No destination specified" in res
    assert "Bangkok (BKK)" in res
    assert "200.00" in res
    assert "first Weekday" in res

def test_format_table_deduplication():
    params = {"origin": "SIN"}
    rows = [
        {"destination": "Bangkok (BKK)", "from": 200.0},
        {"destination": "Bangkok (BKK)", "from": 150.0}, # cheaper
        {"destination": "Tokyo (NRT)", "from": 400.0},
    ]
    res = format_table(rows, "all_destinations_from_origin", params)
    assert "Bangkok (BKK)" in res
    assert "150.00" in res
    assert "Tokyo (NRT)" in res
    # Ensure Bangkok is only listed once
    assert res.count("Bangkok (BKK)") == 1

def test_format_table_no_results():
    res = format_table([], "some_intent", {"travel_style": "nature"})
    assert "No destinations tagged with nature found" in res
    res_generic = format_table([], "some_intent")
    assert "No results found" in res_generic

def test_format_flight_with_destination_no_visa():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    rows = [{"f_airline_code": "SQ"}]
    res = format_flight_with_destination(rows, g, params, [], "flights_on_date")
    assert "Visa required" not in res
    assert "No visa needed" not in res

def test_format_flight_with_destination_same_cabin():
    g, airport, city, country = _setup_mock_graph()
    params = {"destination_airport_code": "BKK"}
    rows = [
        {"f_airline_code": "SQ", "f_cabin_class": "Economy"},
        {"f_airline_code": "TG", "f_cabin_class": "Economy"},
    ]
    res = format_flight_with_destination(rows, g, params, [], "flights_on_date")
    assert "Economy" not in res

def test_format_table_empty_with_style():
    res = format_table([], "some_intent", {"travel_style": "nature"})
    assert "No destinations tagged with nature found" in res

def test_format_table_empty_generic():
    res = format_table([], "some_intent")
    assert "No results found" in res

def test_format_table_single_result():
    rows = [{"destination": "Bangkok (BKK)", "from": 200.0}]
    res = format_table(rows, "all_destinations_from_origin", {"origin": "SIN"})
    assert "Only 1 destination matched your filter" in res

def test_format_table_many_results():
    rows = [{"destination": f"City {i}", "from": 100.0} for i in range(15)]
    res = format_table(rows, "all_destinations_from_origin", {"origin": "SIN"})
    assert "Showing 15 destinations" in res

def test_format_table_flight_rows():
    rows = [{
        "f_departure_date": "2026-06-01T07:00:00",
        "f_arrival_date": "2026-06-01T11:00:00",
        "f_airline_code": "SQ",
        "f_cabin_class": "Economy",
        "f_currency_code": "SGD",
        "f_total_amount_fare_total": 200.0,
        "f_flight_duration": 120
    }]
    res = format_table(rows, "route_fare_options", {"origin": "SIN", "destination": "BKK"})
    assert "SQ" in res
    assert "200.00" in res
    assert "Showing 1 of 1 flights" not in res # Since cap is not exceeded


def test_format_weather():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok", "month_num": "6"}
    rows = [{"monthNum": "6", "monthName": "June", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"}]
    res = format_weather(rows, params)
    assert "Bangkok in June" in res
    assert "30°C" in res
    assert "200mm rainfall" in res
    assert "Hot" in res

def test_format_weather_no_data():
    res = format_weather([], {})
    assert "No weather data found" in res

def test_format_country_weather():
    params = {"country_name": "Thailand", "month_num": "6"}
    rows = [
        {"cityName": "Bangkok", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"},
        {"cityName": "Chiang Mai", "avgTempC": "25", "avgRainfallMm": "100", "weatherSummary": "Mild"},
        {"cityName": "Bangkok", "avgTempC": "31", "avgRainfallMm": "210", "weatherSummary": "Hotter"}, # duplicate city
    ]
    res = format_country_weather(rows, params)
    assert "Weather in Thailand in June" in res
    assert "Bangkok" in res
    assert "Chiang Mai" in res
    assert res.count("Bangkok") == 1

def test_format_weather_no_month_filter():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [
        {"monthNum": "6", "monthName": "June", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"},
        {"monthNum": "12", "monthName": "December", "avgTempC": "25", "avgRainfallMm": "50", "weatherSummary": "Cool"},
    ]
    res = format_weather(rows, params)
    assert "Bangkok in June" in res
    assert "Bangkok in December" in res

def test_format_weather_no_match_fallback():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok", "month_num": "1"}
    rows = [
        {"monthNum": "6", "monthName": "June", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"},
    ]
    res = format_weather(rows, params)
    assert "Bangkok in June" in res

def test_format_country_weather_invalid_month():
    params = {"country_name": "Thailand", "month_num": "invalid"}
    rows = [
        {"cityName": "Bangkok", "avgTempC": "30", "avgRainfallMm": "200", "weatherSummary": "Hot"},
    ]
    res = format_country_weather(rows, params)
    assert "Weather in Thailand in the selected month" in res

def test_format_festivals():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok", "month_num": "6"}
    rows = [{"festivalName": "Songkran", "monthNum": "6", "festivalType": "culture"}]
    res = format_festivals(rows, params)
    assert "Bangkok — Festivals in June" in res
    assert "Songkran" in res

def test_format_festivals_no_filtered_data():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok", "month_num": "6"}
    rows = [{"festivalName": "Songkran", "monthNum": "4", "festivalType": "culture"}]
    res = format_festivals(rows, params)
    assert "No festivals in June" in res

def test_format_transport():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"transportModeName": "Taxi"}, {"transportModeName": "Skytrain"}]
    res = format_transport(rows, params)
    assert "Bangkok — Getting Around" in res
    assert "Taxi" in res
    assert "Skytrain" in res

def test_format_festivals_no_month():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"festivalName": "Songkran", "monthNum": "4", "festivalType": "culture"}]
    res = format_festivals(rows, params)
    assert "Bangkok — Festivals" in res
    assert "Songkran (April)" in res

def test_format_transport_no_data():
    res = format_transport([], {})
    assert "No transport data found" in res

def test_format_cuisines_no_data():
    res = format_cuisines([], {})
    assert "No cuisine data found" in res

def test_format_language_no_data():
    res = format_language([], {})
    assert "No language data found" in res

def test_format_timezone_no_data():
    res = format_timezone([], {})
    assert "No timezone data found" in res

def test_format_destination_currency_no_data():
    res = format_destination_currency([], {})
    assert "No currency data found" in res



def test_format_amenities():
    params = {"destination_airport_code": "BKK"}
    rows = [{"airportName": "Suvarnabhumi", "terminalCount": "1", "hasTransitHotel": "true", "hasLounge": "true"}]
    res = format_amenities(rows, params)
    assert "Suvarnabhumi (BKK)" in res
    assert "1 terminal" in res
    assert "Lounge" in res
    assert "Transit Hotel" in res

def test_format_amenities_no_data():
    res = format_amenities([], {})
    assert "No airport data found" in res

def test_format_amenities_singular_terminal():
    params = {"destination_airport_code": "BKK"}
    rows = [{"airportName": "Suvarnabhumi", "terminalCount": "1", "hasTransitHotel": "false", "hasLounge": "false"}]
    res = format_amenities(rows, params)
    assert "1 terminal" in res

def test_format_amenities_no_facilities():
    params = {"destination_airport_code": "BKK"}
    rows = [{"airportName": "Small Airport", "terminalCount": None, "hasTransitHotel": "false", "hasLounge": "false"}]
    res = format_amenities(rows, params)
    assert "No amenity data" in res

def test_format_safety_unknown_solo():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"safetyTier": "moderate", "soloFemaleSafe": "unknown"}]
    res = format_safety(rows, params)
    assert "Solo female travel" not in res

def test_format_neighborhoods_no_summary():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"areaName": "Siam", "areaSummary": None}]
    res = format_neighborhoods(rows, params)
    assert "  Siam" in res
    assert "  Siam — " not in res

def test_format_overview_no_data():
    res = format_overview([], {})
    assert "No destination data found" in res

def test_format_safety():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"safetyTier": "moderate", "soloFemaleSafe": "true"}]
    res = format_safety(rows, params)
    assert "Bangkok — Safety" in res
    assert "Moderate" in res
    assert "Solo female travel: safe" in res

def test_format_safety_no_data():
    res = format_safety([], {})
    assert "No safety data found" in res

def test_format_safety_caution():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"safetyTier": "moderate", "soloFemaleSafe": "false"}]
    res = format_safety(rows, params)
    assert "Solo female travel: exercise caution" in res

def test_format_neighborhoods():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"areaName": "Siam", "areaSummary": "Shopping hub"}]
    res = format_neighborhoods(rows, params)
    assert "Bangkok — Neighbourhoods" in res
    assert "Siam — Shopping hub" in res

def test_format_neighborhoods_no_data():
    res = format_neighborhoods([], {})
    assert "No neighbourhood data found" in res

def test_format_overview():
    rows = [{
        "cityName": "Bangkok", "countryName": "Thailand", "continent": "Asia", "region": "SE Asia",
        "safetyTier": "moderate", "soloFemaleSafe": "true", "costOfLivingIndex": "42.4"
    }]
    params = {"destination_airport_code": "BKK"}
    res = format_overview(rows, params)
    assert "Bangkok, Thailand" in res
    assert "SE Asia" in res
    assert "Asia" in res
    assert "Moderate" in res
    assert "Easy on the wallet" in res

def test_format_overview_no_data():
    res = format_overview([], {})
    assert "No destination data found" in res

def test_format_travel_styles():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"travelStyleName": "Adventure"}]
    res = format_travel_styles(rows, params)
    assert "Bangkok — Travel Styles" in res
    assert "Adventure" in res

def test_format_travel_styles_no_data():
    res = format_travel_styles([], {})
    assert "No travel style data found" in res

def test_format_best_months():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"monthNum": "6", "avgTempC": "30", "weatherSummary": "Great"}]
    res = format_best_months(rows, params)
    assert "Bangkok — Best time to visit" in res
    assert "Jun" in res
    assert "30°C" in res
    assert "great" in res

def test_format_best_months_no_temps():
    params = {"destination_airport_code": "BKK", "city_name": "Bangkok"}
    rows = [{"monthNum": "6", "weatherSummary": "Great"}]
    res = format_best_months(rows, params)
    assert "Jun" in res
    assert "great" in res
    assert "°C" not in res

def test_format_visa_check_no_data():
    res = format_visa_check([], {})
    assert "No visa information found" in res

def test_format_flight_count_with_date():
    rows = [{
        "f_departure_airport_code": "SIN", "f_destination_airport_code": "BKK",
        "f_currency_code": "SGD", "total_flights": "100", "airline_count": "5", "min_fare": 200.0
    }]
    params = {"start_date": "2026-06-01", "end_date": "2026-06-30"}
    res = format_flight_count(rows, params)
    assert "SIN → BKK — June 2026" in res

def test_format_aircraft_on_route_multiple_airlines():
    rows = [
        {"airlineCode": "SQ", "aircraftCode": "A350"},
        {"airlineCode": "TG", "aircraftCode": "B777"},
    ]
    params = {"origin": "SIN", "destination": "BKK"}
    res = format_aircraft_on_route(rows, params)
    assert "Aircraft on SIN → BKK:" in res
    assert "A350" in res
    assert "B777" in res


def test_format_visa_check():
    rows = [{
        "visaRequired": "true", "visaPolicyName": "eVisa Required", 
        "visaDurationDays": "30", "passportCountryName": "Singapore", "destinationCountryName": "Thailand"
    }]
    params = {}
    res = format_visa_check(rows, params)
    assert "Thailand — Visa required for Singapore passport" in res
    assert "eVisa Required" in res
    assert "Stay up to 30 days" in res

def test_format_visa_check_no_data():
    res = format_visa_check([], {})
    assert "No visa information found" in res

def test_format_visa_check_no_visa():
    rows = [{"visaRequired": "false", "passportCountryName": "Singapore", "destinationCountryName": "Thailand"}]
    res = format_visa_check(rows, {})
    assert "Thailand — No visa required for Singapore passport" in res

def test_format_flight_count():
    rows = [{
        "f_departure_airport_code": "SIN", "f_destination_airport_code": "BKK",
        "f_currency_code": "SGD", "total_flights": "100", "airline_count": "5", "min_fare": 200.0
    }]
    params = {"departure_month": "6"}
    res = format_flight_count(rows, params)
    assert "SIN → BKK — June" in res
    assert "100 flights" in res
    assert "5 airlines" in res
    assert "from SGD 200" in res

def test_format_flight_count_no_data():
    res = format_flight_count([], {})
    assert "No flight count data found" in res

def test_format_aircraft_on_route():
    rows = [{
        "airlineCode": "SQ", "aircraftCode": "A350"
    }, {
        "airlineCode": "SQ", "aircraftCode": "B787"
    }]
    params = {"origin": "SIN", "destination": "BKK"}
    res = format_aircraft_on_route(rows, params)
    assert "Aircraft on SIN → BKK (SQ):" in res
    assert "A350" in res
    assert "B787" in res

def test_format_aircraft_on_route_no_data():
    res = format_aircraft_on_route([], {})
    assert "No aircraft data found" in res

def test_format_route_list():
    rows = [{
        "countryName": "Thailand", "cityName": "Bangkok", "airlineName": "SQ"
    }, {
        "countryName": "Thailand", "cityName": "Phuket", "airlineName": "SQ"
    }]
    params = {"origin": "SIN"}
    res = format_route_list(rows, params, "routes_by_airline")
    assert "SQ flies from SIN to:" in res
    assert "Thailand: Bangkok · Phuket" in res

def test_format_route_list_no_data():
    res = format_route_list([], {})
    assert "No routes found" in res

def test_format_route_list_singapore_only():
    rows = [{"countryName": "Singapore", "cityName": "Singapore"}]
    params = {"origin": "BKK"}
    res = format_route_list(rows, params)
    assert "Our route data covers flights from Singapore (SIN)" in res

def test_format_airports_in_city():
    rows = [{
        "airportCode": "BKK", "airportName": "Suvarnabhumi", "countryName": "Thailand"
    }]
    params = {"city_name": "Bangkok"}
    res = format_airports_in_city(rows, params)
    assert "Airports in Bangkok, Thailand" in res
    assert "Suvarnabhumi (BKK)" in res

def test_format_route_list_many_countries():
    rows = [{"countryName": f"Country {i}", "cityName": "City"} for i in range(15)]
    params = {"origin": "SIN"}
    res = format_route_list(rows, params)
    assert "Includes:" in res
    assert "and more" in res

def test_format_route_list_singapore_only_non_sin_origin():
    rows = [{"countryName": "Singapore", "cityName": "Singapore"}]
    params = {"origin": "BKK"}
    res = format_route_list(rows, params)
    assert "Our route data covers flights from Singapore (SIN)" in res

def test_format_airports_in_city_no_data():
    res = format_airports_in_city([], {"city_name": "Bangkok"})
    assert "No airports found for Bangkok" in res

def test_format_language_destinations():
    rows = [{
        "countryName": "Thailand", "cityName": "Bangkok"
    }]
    params = {"language_name": "Thai"}
    res = format_language_destinations(rows, params)
    assert "Destinations where Thai is spoken:" in res
    assert "Thailand: Bangkok" in res

def test_format_language_destinations_no_data():
    res = format_language_destinations([], {"language_name": "Thai"})
    assert "No destinations found where Thai is spoken" in res

def test_format_festivals_by_month():
    rows = [{
        "cityName": "Bangkok", "countryName": "Thailand", "festivalName": "Songkran", 
        "festivalType": "culture", "monthNum": "4"
    }]
    params = {"month_num": "4"}
    res = format_festivals_by_month(rows, params)
    assert "Festivals in April:" in res
    assert "Bangkok, Thailand — Songkran (culture)" in res

def test_format_festivals_by_month_no_data():
    res = format_festivals_by_month([], {"month_num": "4"})
    assert "No festivals found in April" in res


def test_format_cities_in_country():
    rows = [{
        "cityName": "Bangkok", "airportCode": "BKK", "airportName": "Suvarnabhumi"
    }]
    params = {"country_name": "Thailand"}
    res = format_cities_in_country(rows, params)
    assert "Cities in Thailand" in res
    assert "Bangkok" in res
    assert "Suvarnabhumi (BKK)" in res

def test_format_cities_in_country_no_data():
    res = format_cities_in_country([], {"country_name": "Thailand"})
    assert "No cities found for Thailand" in res

def test_format_country_info():
    rows = [{
        "countryName": "Thailand", "countryCode": "TH", "continent": "Asia",
        "region": "SE Asia", "capitalCityName": "Bangkok", "currencyCode": "THB"
    }]
    params = {"country_name": "Thailand"}
    res = format_country_info(rows, params)
    assert "Thailand (TH)" in res
    assert "Continent : Asia" in res
    assert "Capital   : Bangkok" in res

def test_format_country_info_no_data():
    res = format_country_info([], {"country_name": "Thailand"})
    assert "No information found for Thailand" in res

def test_format_solo_female_destinations():
    rows = [{
        "countryName": "Thailand", "cityName": "Bangkok", "safetyTier": "safe"
    }]
    res = format_solo_female_destinations(rows, {})
    assert "Solo Female-Friendly Destinations" in res
    assert "Thailand" in res
    assert "Bangkok — Safe" in res

def test_format_solo_female_destinations_no_data():
    res = format_solo_female_destinations([], {})
    assert "No solo female-friendly destinations found" in res

def test_format_exchange_rate_sgd_base():
    rows = [{"currencyCode": "SGD", "currencyName": "Singapore Dollar", "exchangeRate": "1.0"}]
    res = format_exchange_rate(rows, {"currency_code": "SGD"})
    assert "base currency" in res

def test_format_exchange_rate_low_value():
    rows = [{"currencyCode": "GBP", "currencyName": "British Pound", "exchangeRate": "0.6"}]
    res = format_exchange_rate(rows, {"currency_code": "GBP"})
    assert "0.6000 GBP" in res


def test_format_exchange_rate_invalid():
    rows = [{"currencyCode": "THB", "currencyName": "Thai Baht", "exchangeRate": "invalid"}]
    res = format_exchange_rate(rows, {"currency_code": "THB"})
    assert "Exchange rate for THB is not available" in res

def test_format_visa_duration():
    rows = [{
        "countryName": "Thailand", "visaRequired": "true", "visaDurationDays": "30", "policyName": "Tourist"
    }]
    params = {"destination_country_name": "Thailand"}
    res = format_visa_duration(rows, params)
    assert "Thailand — SG Passport" in res
    assert "Entry type : Tourist" in res
    assert "Max stay   : 30 days" in res

def test_format_visa_duration_no_data():
    res = format_visa_duration([], {"destination_country_name": "Thailand"})
    assert "No visa information found for Thailand" in res

def test_format_airports_with_amenity():
    rows = [{
        "airportCode": "BKK", "airportName": "Suvarnabhumi", "countryName": "Thailand",
        "hasLounge": "true", "hasTransitHotel": "false"
    }]
    params = {"amenity_type": "lounge"}
    res = format_airports_with_amenity(rows, params)
    assert "Airports with Airport Lounge" in res
    assert "Thailand" in res
    assert "Suvarnabhumi (BKK)" in res

def test_format_airports_with_amenity_no_data():
    res = format_airports_with_amenity([], {"amenity_type": "lounge"})
    assert "No airports found with airport lounge" in res

def test_format_airports_with_amenity_transit():
    rows = [{
        "airportCode": "BKK", "airportName": "Suvarnabhumi", "countryName": "Thailand",
        "hasLounge": "false", "hasTransitHotel": "true"
    }]
    params = {"amenity_type": "transit hotel"}
    res = format_airports_with_amenity(rows, params)
    assert "Airports with Transit Hotel" in res
    assert "Suvarnabhumi (BKK)" in res

def test_format_safe_destinations():
    rows = [{
        "countryName": "Thailand", "cityName": "Bangkok"
    }]
    params = {"safety_tier": "safe"}
    res = format_safe_destinations(rows, params)
    assert "Safe Destinations" in res
    assert "Thailand: Bangkok" in res

def test_format_safe_destinations_no_data():
    res = format_safe_destinations([], {"safety_tier": "safe"})
    assert "No Safe destinations found" in res

def test_format_festivals_by_type():
    rows = [{
        "festivalName": "Songkran", "cityName": "Bangkok", "countryName": "Thailand", 
        "monthNum": "4"
    }]
    params = {"festival_type": "culture"}
    res = format_festivals_by_type(rows, params)
    assert "Culture Festivals" in res
    assert "Songkran — Bangkok, Thailand (April)" in res

def test_format_festivals_by_type_no_data():
    res = format_festivals_by_type([], {"festival_type": "culture"})
    assert "No Culture festivals found" in res

def test_format_route_statistics():
    rows = [{
        "f_departure_airport_code": "SIN", "f_destination_airport_code": "BKK",
        "f_currency_code": "SGD", "min_fare": 200.0, "avg_fare": 250.0, 
        "max_fare": 300.0, "avg_duration_mins": 120, "flight_count": "50"
    }]
    params = {"departure_month": "6"}
    res = format_route_statistics(rows, params)
    assert "SIN → BKK — June 2026" in res
    assert "Fares: from SGD 200 · avg SGD 250 · up to SGD 300" in res
    assert "Flight time: 2h00m · 50 flights available" in res

def test_format_route_statistics_no_data():
    res = format_route_statistics([], {})
    assert "No statistics found for this route" in res

def test_format_currency_list():
    rows = [{
        "countryName": "Thailand", "currencyCode": "THB", "currencyName": "Thai Baht", "exchangeRate": "25.5"
    }]
    params = {"region": "se_asia", "base_currency_code": "SGD"}
    res = format_currency_list(rows, params)
    assert "Currencies in Se Asia (1 SGD ≈):" in res
    assert "Thailand: 26 THB (Thai Baht)" in res

def test_format_currency_list_no_data():
    res = format_currency_list([], {})
    assert "No currency data found" in res

def test_format_currency_list_base():
    rows = [{
        "countryName": "Singapore", "currencyCode": "SGD", "currencyName": "Singapore Dollar", "exchangeRate": "1.0"
    }]
    params = {"region": "se_asia", "base_currency_code": "SGD"}
    res = format_currency_list(rows, params)
    assert "Singapore: SGD — base currency (Singapore Dollar)" in res

def test_format_departures():
    rows = [{
        "destination": "Bangkok", "f_departure_date": "2026-06-01T07:00:00",
        "f_arrival_date": "2026-06-01T11:00:00", "f_airline_code": "SQ",
        "f_flight_duration": "120", "f_total_amount_fare_total": "200",
        "f_currency_code": "SGD", "f_cabin_class": "Economy"
    }]
    params = {"origin": "SIN", "departure_date": "2026-06-01"}
    res = format_departures(rows, params)
    assert "Departures from SIN on 1 Jun 2026" in res
    assert "Bangkok — 07:00 · 2h00m · SGD 200 · SQ" in res

def test_format_departures_no_data():
    res = format_departures([], {"origin": "SIN"})
    assert "No departures found" in res

def test_format_departures_capped():
    rows = [{"destination": f"Dest {i}", "f_departure_date": "2026-06-01T07:00:00"} for i in range(15)]
    res = format_departures(rows, {"origin": "SIN"})
    assert "Showing 10 of 15 departures" in res

def test_format_round_trip():
    outbound = [{"f_departure_date": "2026-06-01T07:00:00", "f_arrival_date": "2026-06-01T11:00:00", "f_airline_code": "SQ", "f_total_amount_fare_total": "200", "f_currency_code": "SGD", "f_flight_duration": "120"}]
    return_rows = [{"f_departure_date": "2026-06-03T15:00:00", "f_arrival_date": "2026-06-03T19:00:00", "f_airline_code": "SQ", "f_total_amount_fare_total": "200", "f_currency_code": "SGD", "f_flight_duration": "120"}]
    params = {"origin": "SIN", "destination": "BKK", "departure_date": "2026-06-01", "return_date": "2026-06-03"}
    res = format_round_trip(outbound, return_rows, params)
    assert "SIN ↔ BKK — Round Trip" in res
    assert "Outbound (1 Jun)" in res
    assert "Return (3 Jun)" in res

def test_format_round_trip_no_flights():
    res = format_round_trip([], [], {"origin": "SIN", "destination": "BKK"})
    assert "No flights found" in res

def test_format_transit_route():
    rows = [{
        "transit_hub": "HKG", "leg1_departs": "2026-06-01T07:00:00", "leg1_arrives": "2026-06-01T11:00:00",
        "leg2_departs": "2026-06-01T13:00:00", "leg2_arrives": "2026-06-01T15:00:00",
        "leg1_airline": "SQ", "leg2_airline": "CX", "leg1_fare": 100, "leg2_fare": 100,
        "leg1_currency": "SGD", "leg2_currency": "SGD", "leg1_duration_mins": 60, "leg2_duration_mins": 60, "layover_mins": 120
    }]
    params = {"origin": "SIN", "destination": "BKK"}
    res = format_transit_route(rows, params)
    assert "No direct flights from SIN to BKK" in res
    assert "SIN → HKG → BKK" in res
    assert "Layover : HKG — 2h00m" in res

def test_format_transit_route_no_data():
    res = format_transit_route([], {"origin": "SIN", "destination": "BKK"})
    assert "No connecting flights found from SIN to BKK" in res

def test_format_airport_info_no_data():
    res = format_airport_info([], {"airport_code": "BKK"})
    assert "No airport data found for BKK" in res

def test_format_destinations_by_season_no_data():
    res = format_destinations_by_season([], {"season_keyword": "summer"})
    assert "No destinations found with summer season" in res

def test_format_good_weather_destinations_no_data():
    res = format_good_weather_destinations([], {"month_num": "6"})
    assert "No destinations with great weather in June found" in res


def test_cost_comparison_helper():
    from src.graphdb.response import _cost_comparison
    assert "Super budget-friendly" in _cost_comparison(20.0)
    assert "Easy on the wallet" in _cost_comparison(40.0)
    assert "Mid-range in cost" in _cost_comparison(60.0)
    assert "On the pricier side" in _cost_comparison(80.0)
    assert "Premium destination" in _cost_comparison(110.0)


