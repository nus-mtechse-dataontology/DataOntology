import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Tables that exist in RDS and can be synced from there.
# dim_airline_coverage is intentionally excluded: the RDS schema (f_airport_code,
# f_airline_code, f_coverage) differs from the route-pair schema (f_origin_airport_code,
# f_target_airport_code) that build_dml() needs to construct Route nodes.
_RDS_TABLES = {
    "dim_accounts",
    "dim_aircraft",
    "dim_airline",
    "dim_airport",
    "dim_city",
    "dim_country",
    "dim_currency_rate",
}


@dataclass(frozen=True)
class BuildConfig:
    tmp_root: Path
    ddl_ttl: Path
    dml_ttl: Path
    # When set, the 7 core dimension tables are fetched from this PostgreSQL URL
    # instead of the local CSV files. All other tables always come from CSV.
    # Format: postgresql://user:password@host:port/dbname
    db_url: str | None = field(default=None)
    # When set, enrichment CSVs are downloaded from s3://<s3_bucket>/enrichment/
    # and the output TTL files are uploaded to s3://<s3_bucket>/output/
    s3_bucket: str | None = field(default=None)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_rows_from_pg(db_url: str, table_name: str) -> list[dict[str, str]]:
    """Query a PostgreSQL table and return rows as string-valued dicts.

    Values are normalised to str (None becomes empty string) to match the
    csv.DictReader output so the rest of build_dml() works without changes.
    """
    import psycopg2  # lazy import — not required in CSV-only mode

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table_name}")  # noqa: S608 — table_name is a trusted internal constant
            cols = [desc[0] for desc in cur.description]
            return [
                {col: ("" if val is None else str(val)) for col, val in zip(cols, row)}
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def _load(config: BuildConfig, table_name: str) -> list[dict[str, str]]:
    """Return rows from RDS when db_url is set and the table is RDS-backed,
    otherwise fall back to the local CSV file."""
    if config.db_url and table_name in _RDS_TABLES:
        return load_rows_from_pg(config.db_url, table_name)
    return load_rows(config.tmp_root / f"{table_name}.csv")


def ttl_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def ttl_decimal(value: str) -> str:
    return f'"{value}"^^xsd:decimal'


def ttl_int(value: str) -> str:
    return f'"{value}"^^xsd:integer'


def ttl_bool_str(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1"}:
        return "true"
    if normalized in {"no", "false", "0"}:
        return "false"
    return ttl_literal(value)


def resource_id(raw: str) -> str:
    cleaned = []
    for char in raw.strip():
        if char.isalnum() or char == "_":
            cleaned.append(char)
        elif char in {" ", "-", "/", "&", ",", "(", ")", "."}:
            cleaned.append("_")
    collapsed = "".join(cleaned)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_") or "unknown"


def subject(kind: str, identifier: str) -> str:
    return f"ex:{kind}_{resource_id(identifier)}"


def emit_block(lines: list[str], subject_id: str, rdf_type: str, predicates: Iterable[str]) -> None:
    body = " ;\n    ".join(predicates)
    lines.append(f"{subject_id} a {rdf_type} ;\n    {body} .\n")


def build_ddl() -> str:
    lines = [
        "@prefix ex: <http://dataontology.example/graph/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "ex:travel-graph-ddl a owl:Ontology ;",
        '    rdfs:label "DataOntology travel graph schema" ;',
        '    rdfs:comment "Schema generated from current tmp dimensions. fact_flight_info is intentionally excluded. Account nodes store only username + passport country link — all auth/PII fields (password, email, full_name, disabled) remain in the relational database only." .',
        "",
    ]

    classes = [
        "Account",
        "Aircraft",
        "Airline",
        "Airport",
        "Attraction",
        "City",
        "CityMonthlyWeather",
        "Country",
        "CountryVisaRequirement",
        "Cuisine",
        "Currency",
        "Festival",
        "Language",
        "Route",
        "SubcityArea",
        "TransportMode",
        "TravelStyle",
        "VisaPolicy",
    ]
    for item in classes:
        lines.append(f"ex:{item} a owl:Class .")
    lines.append("")

    object_properties = [
        ("belongsToCountry", "ex:City", "ex:Country"),
        ("inCity", "ex:Airport", "ex:City"),
        ("operatedBy", "ex:Route", "ex:Airline"),
        ("hasOriginAirport", "ex:Route", "ex:Airport"),
        ("hasDestinationAirport", "ex:Route", "ex:Airport"),
        ("hasTravelStyle", "ex:City", "ex:TravelStyle"),
        ("hasWeatherObservation", "ex:City", "ex:CityMonthlyWeather"),
        ("hasSubcityArea", "ex:City", "ex:SubcityArea"),
        ("hasTransportMode", "ex:City", "ex:TransportMode"),
        ("usesPrimaryLanguage", "ex:City", "ex:Language"),
        ("passportCountry", "ex:CountryVisaRequirement", "ex:Country"),
        ("destinationCountry", "ex:CountryVisaRequirement", "ex:Country"),
        ("usesVisaPolicy", "ex:CountryVisaRequirement", "ex:VisaPolicy"),
        ("hasPassportCountry", "ex:Account", "ex:Country"),
        ("hasCurrency", "ex:Country", "ex:Currency"),
        ("capitalCity", "ex:Country", "ex:City"),
        ("hasFestival", "ex:City", "ex:Festival"),
        ("hasCuisine", "ex:City", "ex:Cuisine"),
        ("hasAttraction", "ex:City", "ex:Attraction"),
    ]
    for name, domain, rng in object_properties:
        lines.append(
            f"{subject('prop', name)} a owl:ObjectProperty ; "
            f"rdfs:domain {domain} ; rdfs:range {rng} ."
        )
    lines.append("")

    datatype_properties = [
        # Account: username is the shared key with SQL; all auth/PII fields stay in SQL only
        ("accountUsername", "ex:Account", "xsd:string"),
        ("aircraftCode", "ex:Aircraft", "xsd:string"),
        ("aircraftModel", "ex:Aircraft", "xsd:string"),
        ("aircraftSummary", "ex:Aircraft", "xsd:string"),
        ("airlineCode", "ex:Airline", "xsd:string"),
        ("airlineName", "ex:Airline", "xsd:string"),
        ("airportCode", "ex:Airport", "xsd:string"),
        ("airportName", "ex:Airport", "xsd:string"),
        ("cityCode", "ex:City", "xsd:string"),
        ("cityName", "ex:City", "xsd:string"),
        ("countryCode", "ex:Country", "xsd:string"),
        ("countryName", "ex:Country", "xsd:string"),
        ("currencyCode", "ex:Currency", "xsd:string"),
        ("exchangeRate", "ex:Currency", "xsd:decimal"),
        ("monthNum", "ex:CityMonthlyWeather", "xsd:integer"),
        ("monthName", "ex:CityMonthlyWeather", "xsd:string"),
        ("avgTempC", "ex:CityMonthlyWeather", "xsd:decimal"),
        ("avgRainfallMm", "ex:CityMonthlyWeather", "xsd:decimal"),
        ("weatherProfileCode", "ex:CityMonthlyWeather", "xsd:string"),
        ("seasonCode", "ex:CityMonthlyWeather", "xsd:string"),
        ("bestTimeToVisit", "ex:CityMonthlyWeather", "xsd:boolean"),
        ("weatherSummary", "ex:CityMonthlyWeather", "xsd:string"),
        ("researchStatus", "ex:SubcityArea", "xsd:string"),
        ("areaSummary", "ex:SubcityArea", "xsd:string"),
        ("subcityAreaName", "ex:SubcityArea", "xsd:string"),
        ("languageName", "ex:Language", "xsd:string"),
        ("travelStyleName", "ex:TravelStyle", "xsd:string"),
        ("transportModeName", "ex:TransportMode", "xsd:string"),
        ("visaPolicyName", "ex:VisaPolicy", "xsd:string"),
        ("visaPolicyDescription", "ex:VisaPolicy", "xsd:string"),
        ("publicTransportWidelyUsedInCountry", "ex:City", "xsd:boolean"),
        ("visaRequired", "ex:CountryVisaRequirement", "xsd:boolean"),
        ("onlineApplyUrl", "ex:CountryVisaRequirement", "xsd:string"),
        ("visaDurationDays", "ex:CountryVisaRequirement", "xsd:integer"),
        ("routeKey", "ex:Route", "xsd:string"),
        # Country enrichment
        ("continent", "ex:Country", "xsd:string"),
        ("region", "ex:Country", "xsd:string"),
        # City enrichment
        ("costOfLivingIndex", "ex:City", "xsd:decimal"),
        ("safetyTier", "ex:City", "xsd:string"),
        ("soloFemaleSafe", "ex:City", "xsd:boolean"),
        ("utcOffset", "ex:City", "xsd:string"),
        ("timezoneName", "ex:City", "xsd:string"),
        # Airport attributes
        ("airportType", "ex:Airport", "xsd:string"),
        ("terminalCount", "ex:Airport", "xsd:integer"),
        ("isInternational", "ex:Airport", "xsd:boolean"),
        ("hasTransitHotel", "ex:Airport", "xsd:boolean"),
        ("hasLounge", "ex:Airport", "xsd:boolean"),
        # Currency
        ("currencyName", "ex:Currency", "xsd:string"),
        # Festival
        ("festivalName", "ex:Festival", "xsd:string"),
        ("festivalMonthNum", "ex:Festival", "xsd:integer"),
        ("festivalType", "ex:Festival", "xsd:string"),
        # Cuisine
        ("cuisineType", "ex:Cuisine", "xsd:string"),
        # Attraction
        ("attractionName", "ex:Attraction", "xsd:string"),
        ("attractionType", "ex:Attraction", "xsd:string"),
        ("attractionTier", "ex:Attraction", "xsd:string"),
    ]
    for name, domain, rng in datatype_properties:
        lines.append(
            f"{subject('prop', name)} a owl:DatatypeProperty ; "
            f"rdfs:domain {domain} ; rdfs:range {rng} ."
        )

    return "\n".join(lines) + "\n"


def build_dml(config: BuildConfig) -> str:
    tmp = config.tmp_root
    # RDS-backed tables: fetched from PostgreSQL when config.db_url is set
    accounts = _load(config, "dim_accounts")
    aircraft = _load(config, "dim_aircraft")
    airlines = _load(config, "dim_airline")
    airports = _load(config, "dim_airport")
    cities = _load(config, "dim_city")
    countries = _load(config, "dim_country")
    currency_rates = _load(config, "dim_currency_rate")
    # CSV-only: schema differs from route-pair shape expected by Route node builder
    airline_coverage = load_rows(tmp / "dim_airline_coverage.csv")
    # CSV-only: enrichment tables with no RDS counterpart
    airport_attributes = load_rows(tmp / "dim_airport_attribute.csv")
    city_country_enrichment = load_rows(tmp / "dim_city_country_enrichment.csv")
    city_attractions = load_rows(tmp / "dim_city_attraction.csv")
    city_cuisines = load_rows(tmp / "dim_city_cuisine.csv")
    city_festivals = load_rows(tmp / "dim_city_festival.csv")
    city_languages = load_rows(tmp / "dim_city_language.csv")
    city_monthly_weather = load_rows(tmp / "dim_city_monthly_weather.csv")
    city_safety = load_rows(tmp / "dim_city_safety.csv")
    city_timezones = load_rows(tmp / "dim_city_timezone.csv")
    city_travel_styles = load_rows(tmp / "dim_city_travel_style.csv")
    country_visa_policy = load_rows(tmp / "dim_country_visa_policy.csv")
    currencies = load_rows(tmp / "dim_currency.csv")
    subcity_areas = load_rows(tmp / "dim_subcity_area.csv")
    transport_modes = load_rows(tmp / "dim_transport_mode.csv")
    visa_policies = load_rows(tmp / "dim_visa_policy.csv")

    airport_by_code = {row["f_airport_code"]: row for row in airports}
    airline_by_code = {row["f_airline_code"]: row for row in airlines}

    lines = [
        "@prefix ex: <http://dataontology.example/graph/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "ex:travel-graph-dml a owl:Ontology ;",
        '    rdfs:label "DataOntology travel graph data" ;',
        '    rdfs:comment "Instance data generated from tmp dimensions. fact_flight_info is excluded. Account nodes contain only username + passport country link — auth/PII fields remain in SQL." .',
        "",
        (
            f"# Source row counts: accounts={len(accounts)}, aircraft={len(aircraft)}, airlines={len(airlines)}, "
            f"coverage={len(airline_coverage)}, airports={len(airports)}, airport_attributes={len(airport_attributes)}, "
            f"cities={len(cities)}, city_attractions={len(city_attractions)}, city_enrichment={len(city_country_enrichment)}, "
            f"city_cuisines={len(city_cuisines)}, city_festivals={len(city_festivals)}, city_languages={len(city_languages)}, "
            f"city_weather={len(city_monthly_weather)}, city_safety={len(city_safety)}, city_timezones={len(city_timezones)}, "
            f"city_styles={len(city_travel_styles)}, countries={len(countries)}, visa_requirements={len(country_visa_policy)}, "
            f"currencies={len(currencies)}, currency_rates={len(currency_rates)}, "
            f"subcity_areas={len(subcity_areas)}, transport_modes={len(transport_modes)}, "
            f"visa_policies={len(visa_policies)}, fact_flight_info_excluded=true"
        ),
        "",
    ]

    for row in accounts:
        # Only emit username (shared key with SQL) + passport country link.
        # full_name, email, hashed_password, disabled are auth/PII — they stay in SQL only.
        predicates = [
            f'rdfs:label {ttl_literal(row["f_username"])}',
            f'{subject("prop", "accountUsername")} {ttl_literal(row["f_username"])}',
        ]
        emit_block(lines, subject("Account", row["f_username"]), "ex:Account", predicates)

    for row in countries:
        emit_block(
            lines,
            subject("Country", row["f_country_code"]),
            "ex:Country",
            [
                f'rdfs:label {ttl_literal(row["f_country_name"])}',
                f'{subject("prop", "countryCode")} {ttl_literal(row["f_country_code"])}',
                f'{subject("prop", "countryName")} {ttl_literal(row["f_country_name"])}',
            ],
        )

    for row in cities:
        emit_block(
            lines,
            subject("City", row["f_city_code"]),
            "ex:City",
            [
                f'rdfs:label {ttl_literal(row["f_city_name"])}',
                f'{subject("prop", "cityCode")} {ttl_literal(row["f_city_code"])}',
                f'{subject("prop", "cityName")} {ttl_literal(row["f_city_name"])}',
                f'{subject("prop", "belongsToCountry")} {subject("Country", row["f_country_code"])}',
            ],
        )

    for row in airports:
        emit_block(
            lines,
            subject("Airport", row["f_airport_code"]),
            "ex:Airport",
            [
                f'rdfs:label {ttl_literal(row["f_airport_name"])}',
                f'{subject("prop", "airportCode")} {ttl_literal(row["f_airport_code"])}',
                f'{subject("prop", "airportName")} {ttl_literal(row["f_airport_name"])}',
                f'{subject("prop", "inCity")} {subject("City", row["f_city_code"])}',
            ],
        )

    for row in airlines:
        emit_block(
            lines,
            subject("Airline", row["f_airline_code"]),
            "ex:Airline",
            [
                f'rdfs:label {ttl_literal(row["f_airline_name"])}',
                f'{subject("prop", "airlineCode")} {ttl_literal(row["f_airline_code"])}',
                f'{subject("prop", "airlineName")} {ttl_literal(row["f_airline_name"])}',
            ],
        )

    for row in airline_coverage:
        route_key = f'{row["f_airline_code"]}_{row["f_origin_airport_code"]}_{row["f_target_airport_code"]}'
        airline = airline_by_code.get(row["f_airline_code"])
        origin = airport_by_code.get(row["f_origin_airport_code"])
        destination = airport_by_code.get(row["f_target_airport_code"])
        if not airline or not origin or not destination:
            continue
        label = f'{airline["f_airline_name"]} {origin["f_airport_code"]}->{destination["f_airport_code"]}'
        emit_block(
            lines,
            subject("Route", route_key),
            "ex:Route",
            [
                f'rdfs:label {ttl_literal(label)}',
                f'{subject("prop", "routeKey")} {ttl_literal(route_key)}',
                f'{subject("prop", "operatedBy")} {subject("Airline", row["f_airline_code"])}',
                f'{subject("prop", "hasOriginAirport")} {subject("Airport", row["f_origin_airport_code"])}',
                f'{subject("prop", "hasDestinationAirport")} {subject("Airport", row["f_target_airport_code"])}',
            ],
        )

    for row in aircraft:
        emit_block(
            lines,
            subject("Aircraft", row["f_aircraft_code"]),
            "ex:Aircraft",
            [
                f'rdfs:label {ttl_literal(row["f_aircraft_model"])}',
                f'{subject("prop", "aircraftCode")} {ttl_literal(row["f_aircraft_code"])}',
                f'{subject("prop", "aircraftModel")} {ttl_literal(row["f_aircraft_model"])}',
                f'{subject("prop", "aircraftSummary")} {ttl_literal(row["f_aircraft_summary"])}',
            ],
        )

    for row in currency_rates:
        emit_block(
            lines,
            subject("Currency", row["f_currency_code"]),
            "ex:Currency",
            [
                f'rdfs:label {ttl_literal(row["f_currency_name"])}',
                f'{subject("prop", "currencyCode")} {ttl_literal(row["f_currency_code"])}',
                f'{subject("prop", "exchangeRate")} {ttl_decimal(row["f_currency_rate"])}',
            ],
        )

    travel_styles = sorted({row["f_travel_style"] for row in city_travel_styles})
    for value in travel_styles:
        emit_block(
            lines,
            subject("TravelStyle", value),
            "ex:TravelStyle",
            [
                f'rdfs:label {ttl_literal(value)}',
                f'{subject("prop", "travelStyleName")} {ttl_literal(value)}',
            ],
        )
    for row in city_travel_styles:
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasTravelStyle")} {subject("TravelStyle", row["f_travel_style"])} .\n'
        )

    languages = sorted({row["f_main_language"] for row in city_languages})
    for value in languages:
        emit_block(
            lines,
            subject("Language", value),
            "ex:Language",
            [
                f'rdfs:label {ttl_literal(value)}',
                f'{subject("prop", "languageName")} {ttl_literal(value)}',
            ],
        )
    for row in city_languages:
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "usesPrimaryLanguage")} {subject("Language", row["f_main_language"])} .\n'
        )

    transport_values = sorted({row["f_transport_mode"] for row in transport_modes})
    for value in transport_values:
        emit_block(
            lines,
            subject("TransportMode", value),
            "ex:TransportMode",
            [
                f'rdfs:label {ttl_literal(value)}',
                f'{subject("prop", "transportModeName")} {ttl_literal(value)}',
            ],
        )
    transport_city_flag: dict[str, str] = {}
    for row in transport_modes:
        transport_city_flag.setdefault(
            row["f_city_code"],
            row["f_public_transport_widely_used_in_country_flag"],
        )
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasTransportMode")} {subject("TransportMode", row["f_transport_mode"])} .\n'
        )
    for city_code, flag in sorted(transport_city_flag.items()):
        lines.append(
            f'{subject("City", city_code)} {subject("prop", "publicTransportWidelyUsedInCountry")} {ttl_bool_str(flag)} .\n'
        )

    for row in subcity_areas:
        emit_block(
            lines,
            subject("SubcityArea", row["f_subcity_area_code"]),
            "ex:SubcityArea",
            [
                f'rdfs:label {ttl_literal(row["f_subcity_area_name"])}',
                f'{subject("prop", "subcityAreaName")} {ttl_literal(row["f_subcity_area_name"])}',
                f'{subject("prop", "areaSummary")} {ttl_literal(row["f_subcity_area_summary"])}',
                f'{subject("prop", "researchStatus")} {ttl_literal(row["f_research_status"])}',
            ],
        )
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasSubcityArea")} {subject("SubcityArea", row["f_subcity_area_code"])} .\n'
        )

    for row in city_monthly_weather:
        weather_id = f'{row["f_city_code"]}_{row["f_month_num"]}'
        weather_label = f'{row["f_city_code"]} month {row["f_month_num"]}'
        emit_block(
            lines,
            subject("CityMonthlyWeather", weather_id),
            "ex:CityMonthlyWeather",
            [
                f'rdfs:label {ttl_literal(weather_label)}',
                f'{subject("prop", "monthNum")} {ttl_int(row["f_month_num"])}',
                f'{subject("prop", "monthName")} {ttl_literal(row["f_month_name"])}',
                f'{subject("prop", "avgTempC")} {ttl_decimal(row["f_avg_temp_c"])}',
                f'{subject("prop", "avgRainfallMm")} {ttl_decimal(row["f_avg_rainfall_mm"])}',
                f'{subject("prop", "weatherProfileCode")} {ttl_literal(row["f_weather_profile_code"])}',
                f'{subject("prop", "seasonCode")} {ttl_literal(row["f_season_code"])}',
                f'{subject("prop", "bestTimeToVisit")} {ttl_bool_str(row["f_best_time_to_visit_flag"])}',
                f'{subject("prop", "weatherSummary")} {ttl_literal(row["f_weather_summary"])}',
            ],
        )
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasWeatherObservation")} {subject("CityMonthlyWeather", weather_id)} .\n'
        )

    for row in visa_policies:
        emit_block(
            lines,
            subject("VisaPolicy", row["f_visa_policy_code"]),
            "ex:VisaPolicy",
            [
                f'rdfs:label {ttl_literal(row["f_visa_policy_name"])}',
                f'rdfs:comment {ttl_literal(row["f_visa_policy_description"])}',
                f'{subject("prop", "visaPolicyName")} {ttl_literal(row["f_visa_policy_name"])}',
                f'{subject("prop", "visaPolicyDescription")} {ttl_literal(row["f_visa_policy_description"])}',
            ],
        )

    # Airport attributes
    airport_attr_by_code = {row["f_airport_code"]: row for row in airport_attributes}
    for row in airports:
        attr = airport_attr_by_code.get(row["f_airport_code"])
        if attr:
            airport_subj = subject("Airport", row["f_airport_code"])
            lines.append(f'{airport_subj} {subject("prop", "airportType")} {ttl_literal(attr["f_airport_type"])} .\n')
            lines.append(f'{airport_subj} {subject("prop", "terminalCount")} {ttl_int(attr["f_terminal_count"])} .\n')
            lines.append(f'{airport_subj} {subject("prop", "isInternational")} {ttl_bool_str(attr["f_is_international"])} .\n')
            lines.append(f'{airport_subj} {subject("prop", "hasTransitHotel")} {ttl_bool_str(attr["f_has_transit_hotel"])} .\n')
            lines.append(f'{airport_subj} {subject("prop", "hasLounge")} {ttl_bool_str(attr["f_has_lounge"])} .\n')

    # Currencies (Country→Currency link)
    currency_by_code: dict[str, dict] = {}
    for row in currencies:
        c_code = row["f_currency_code"]
        if c_code not in currency_by_code:
            currency_by_code[c_code] = row
            emit_block(
                lines,
                subject("Currency", c_code),
                "ex:Currency",
                [
                    f'rdfs:label {ttl_literal(row["f_currency_name"])}',
                    f'{subject("prop", "currencyCode")} {ttl_literal(c_code)}',
                    f'{subject("prop", "currencyName")} {ttl_literal(row["f_currency_name"])}',
                ],
            )
        lines.append(
            f'{subject("Country", row["f_country_code"])} {subject("prop", "hasCurrency")} {subject("Currency", c_code)} .\n'
        )

    # City country enrichment (continent, region, capital city, cost of living)
    seen_capital: set[str] = set()
    for row in city_country_enrichment:
        city_subj = subject("City", row["f_city_code"])
        if row.get("f_cost_of_living_index"):
            lines.append(f'{city_subj} {subject("prop", "costOfLivingIndex")} {ttl_decimal(row["f_cost_of_living_index"])} .\n')
        country_subj = subject("Country", row["f_country_code"])
        if row.get("f_continent"):
            lines.append(f'{country_subj} {subject("prop", "continent")} {ttl_literal(row["f_continent"])} .\n')
        if row.get("f_region"):
            lines.append(f'{country_subj} {subject("prop", "region")} {ttl_literal(row["f_region"])} .\n')
        capital = row.get("f_capital_city_code", "").strip()
        if capital and row["f_country_code"] not in seen_capital:
            seen_capital.add(row["f_country_code"])
            lines.append(f'{country_subj} {subject("prop", "capitalCity")} {subject("City", capital)} .\n')

    # City safety
    for row in city_safety:
        city_subj = subject("City", row["f_city_code"])
        if row.get("f_safety_tier"):
            lines.append(f'{city_subj} {subject("prop", "safetyTier")} {ttl_literal(row["f_safety_tier"])} .\n')
        if row.get("f_solo_female_safe"):
            lines.append(f'{city_subj} {subject("prop", "soloFemaleSafe")} {ttl_bool_str(row["f_solo_female_safe"])} .\n')

    # City timezones
    for row in city_timezones:
        city_subj = subject("City", row["f_city_code"])
        if row.get("f_utc_offset"):
            lines.append(f'{city_subj} {subject("prop", "utcOffset")} {ttl_literal(row["f_utc_offset"])} .\n')
        if row.get("f_timezone_name"):
            lines.append(f'{city_subj} {subject("prop", "timezoneName")} {ttl_literal(row["f_timezone_name"])} .\n')

    # Cuisines
    cuisine_values = sorted({row["f_cuisine_type"] for row in city_cuisines})
    for value in cuisine_values:
        emit_block(
            lines,
            subject("Cuisine", value),
            "ex:Cuisine",
            [
                f'rdfs:label {ttl_literal(value)}',
                f'{subject("prop", "cuisineType")} {ttl_literal(value)}',
            ],
        )
    for row in city_cuisines:
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasCuisine")} {subject("Cuisine", row["f_cuisine_type"])} .\n'
        )

    # Festivals
    for row in city_festivals:
        festival_id = f'{row["f_city_code"]}_{resource_id(row["f_festival_name"])}'
        emit_block(
            lines,
            subject("Festival", festival_id),
            "ex:Festival",
            [
                f'rdfs:label {ttl_literal(row["f_festival_name"])}',
                f'{subject("prop", "festivalName")} {ttl_literal(row["f_festival_name"])}',
                f'{subject("prop", "festivalMonthNum")} {ttl_int(row["f_month_num"])}',
                f'{subject("prop", "festivalType")} {ttl_literal(row["f_festival_type"])}',
            ],
        )
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasFestival")} {subject("Festival", festival_id)} .\n'
        )

    # Attractions
    for row in city_attractions:
        attraction_id = f'{row["f_city_code"]}_{resource_id(row["f_attraction_name"])}'
        emit_block(
            lines,
            subject("Attraction", attraction_id),
            "ex:Attraction",
            [
                f'rdfs:label {ttl_literal(row["f_attraction_name"])}',
                f'{subject("prop", "attractionName")} {ttl_literal(row["f_attraction_name"])}',
                f'{subject("prop", "attractionType")} {ttl_literal(row["f_attraction_type"])}',
                f'{subject("prop", "attractionTier")} {ttl_literal(row["f_attraction_tier"])}',
            ],
        )
        lines.append(
            f'{subject("City", row["f_city_code"])} {subject("prop", "hasAttraction")} {subject("Attraction", attraction_id)} .\n'
        )

    for row in country_visa_policy:
        req_id = f'{row["f_passport_country_code"]}_{row["f_destination_country_code"]}'
        req_label = f'{row["f_passport_country_code"]} to {row["f_destination_country_code"]}'
        predicates = [
            f'rdfs:label {ttl_literal(req_label)}',
            f'{subject("prop", "passportCountry")} {subject("Country", row["f_passport_country_code"])}',
            f'{subject("prop", "destinationCountry")} {subject("Country", row["f_destination_country_code"])}',
            f'{subject("prop", "visaRequired")} {ttl_bool_str(row["f_country_visa_required"])}',
        ]
        if row.get("f_visa_policy_code"):
            predicates.append(
                f'{subject("prop", "usesVisaPolicy")} {subject("VisaPolicy", row["f_visa_policy_code"])}'
            )
        if row.get("f_online_apply_url"):
            predicates.append(
                f'{subject("prop", "onlineApplyUrl")} {ttl_literal(row["f_online_apply_url"])}'
            )
        duration = row.get("f_visa_duration_days", "").strip()
        if duration:
            predicates.append(
                f'{subject("prop", "visaDurationDays")} {ttl_int(duration)}'
            )
        emit_block(lines, subject("CountryVisaRequirement", req_id), "ex:CountryVisaRequirement", predicates)

    return "\n".join(lines) + "\n"


def download_csvs_from_s3(config: BuildConfig) -> None:
    """Download all CSVs from s3://<bucket>/enrichment/ into config.tmp_root."""
    import boto3  # lazy import — only needed when s3_bucket is set

    config.tmp_root.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=config.s3_bucket, Prefix="enrichment/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            if not filename.endswith(".csv"):
                continue
            dest = config.tmp_root / filename
            s3.download_file(config.s3_bucket, key, str(dest))
            print(f"Downloaded {key} → {dest}")


def upload_ttl_to_s3(config: BuildConfig) -> None:
    """Upload the generated TTL files to s3://<bucket>/output/."""
    import boto3  # lazy import — only needed when s3_bucket is set

    s3 = boto3.client("s3")
    for ttl_path in (config.ddl_ttl, config.dml_ttl):
        key = f"output/{ttl_path.name}"
        s3.upload_file(str(ttl_path), config.s3_bucket, key)
        print(f"Uploaded {ttl_path.name} → s3://{config.s3_bucket}/{key}")


def default_config(repo_root: Path, db_url: str | None = None, s3_bucket: str | None = None) -> BuildConfig:
    return BuildConfig(
        tmp_root=repo_root / "graphdb" / "csv_files",
        ddl_ttl=repo_root / "graphdb" / "data_ontology_ddl.ttl",
        dml_ttl=repo_root / "graphdb" / "data_ontology_dml.ttl",
        db_url=db_url,
        s3_bucket=s3_bucket,
    )


if __name__ == "__main__":
    # To run on EC2 (SSMBridgeInstance), set these env vars before executing:
    #
    #   export DB_HOST=<RDSEndpoint from CloudFormation Outputs>
    #   export DB_USER=dbadmin
    #   export DB_PASSWORD=<MasterDBPassword used during sam deploy>
    #   export DB_NAME=data_ontology
    #   export DB_PORT=5432
    #   export S3_BUCKET=<your S3 bucket name>
    #
    # Then run: python build_graphdb_ttl.py
    #
    # Accept either a full DB_URL or the individual vars above
    db_url = os.environ.get("DB_URL")
    if not db_url:
        host = os.environ.get("DB_HOST")
        port = os.environ.get("DB_PORT", "5432")
        user = os.environ.get("DB_USER")
        password = os.environ.get("DB_PASSWORD")
        name = os.environ.get("DB_NAME")
        if host and user and password and name:
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode=require"
    s3_bucket = os.environ.get("S3_BUCKET")

    if s3_bucket:
        # Running on EC2/Lambda — use /tmp so the script works without the full repo
        tmp_root = Path("/tmp/graphdb_csv")
        config = BuildConfig(
            tmp_root=tmp_root,
            ddl_ttl=Path("/tmp/data_ontology_ddl.ttl"),
            dml_ttl=Path("/tmp/data_ontology_dml.ttl"),
            db_url=db_url,
            s3_bucket=s3_bucket,
        )
    else:
        # Running locally inside the repo — paths relative to repo root
        repo_root = Path(__file__).resolve().parents[1]
        config = default_config(repo_root, db_url=db_url)

    if config.s3_bucket:
        download_csvs_from_s3(config)

    config.ddl_ttl.write_text(build_ddl(), encoding="utf-8")
    config.dml_ttl.write_text(build_dml(config), encoding="utf-8")
    print(f"Wrote {config.ddl_ttl}")
    print(f"Wrote {config.dml_ttl}")

    if config.s3_bucket:
        upload_ttl_to_s3(config)
