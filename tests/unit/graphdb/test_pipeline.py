import pytest
from unittest.mock import MagicMock, patch
from contextlib import ExitStack
from graphdb.pipeline import GraphDbPipeline
from dao import FactFlightInfoDAO

@pytest.fixture
def mock_dao():
    return MagicMock(spec=FactFlightInfoDAO)

@pytest.fixture
def pipeline(mock_dao):
    return GraphDbPipeline(mock_dao)

def test_friendly_columns(pipeline):
    rows = [
        {"f_currency_code": "USD", "other": "val1"},
        {"min_duration_mins": 120, "flight_count": 5},
        {"first_departure": "2026-01-01", "unknown": "test"}
    ]
    expected = [
        {"currency": "USD", "other": "val1"},
        {"min_duration": 120, "flights": 5},
        {"first_dep": "2026-01-01", "unknown": "test"}
    ]
    assert pipeline._friendly_columns(rows) == expected

def test_friendly_columns_empty(pipeline):
    assert pipeline._friendly_columns([]) == []
    assert pipeline._friendly_columns(None) is None # Actually it should return rows if not rows, which is None if rows is None

def test_humanise_follow_up_dates(pipeline):
    # Test ISO date replacement
    text = "Flight on 2026-06-15 from SIN to BKK"
    assert pipeline._humanise_follow_up_dates(text) == "Flight on June 15, 2026 from SIN to BKK"
    
    # Test date keyword hint
    text = "What is the date?"
    assert " (e.g. June, or a specific date like 15 June 2026)" in pipeline._humanise_follow_up_dates(text)
    
    # Test date keyword hint with existing hint
    text = "What is the date? (e.g. June)"
    assert pipeline._humanise_follow_up_dates(text) == text

    # Test exception in _replace (e.g. month > 12)
    text = "2026-13-01"
    assert pipeline._humanise_follow_up_dates(text) == text

def test_is_date_out_of_range(pipeline):
    # In range
    assert pipeline._is_date_out_of_range({"departure_date": "2026-01-01"}) is False
    assert pipeline._is_date_out_of_range({"start_date": "2026-08-31"}) is False
    
    # Out of range
    assert pipeline._is_date_out_of_range({"departure_date": "2026-09-01"}) is True
    assert pipeline._is_date_out_of_range({"end_date": "2027-01-01"}) is True
    
    # Invalid date
    assert pipeline._is_date_out_of_range({"departure_date": "invalid"}) is False
    assert pipeline._is_date_out_of_range({"departure_date": "2026"}) is False

def test_run_sql_success(pipeline, mock_dao):
    intent_def = {"sql_template": "SELECT * FROM flights WHERE origin = :origin"}
    params = {"origin": "SIN"}
    mock_dao.execute_raw_query.return_value = [{"flight_id": "flight1"}, {"flight_id": "flight2"}]
    
    with patch("graphdb.pipeline.compile_sql") as mock_compile:
        mock_compile.return_value = ("SELECT * FROM flights WHERE origin = ?", ["SIN"])
        rows = pipeline._run_sql(intent_def, params, "test_intent")
        assert len(rows) == 2
        assert rows[0] == {"flight_id": "flight1"}

def test_run_sql_compile_error(pipeline):
    intent_def = {}
    params = {}
    with patch("graphdb.pipeline.compile_sql", side_effect=ValueError("Compile Error")):
        rows = pipeline._run_sql(intent_def, params, "test_intent")
        assert rows is None

def test_run_sql_execute_error(pipeline, mock_dao):
    intent_def = {"sql_template": "SELECT * FROM flights"}
    params = {}
    mock_dao.execute_raw_query.side_effect = Exception("DB Error")
    with patch("graphdb.pipeline.compile_sql", return_value=("SELECT * FROM flights", [])):
        rows = pipeline._run_sql(intent_def, params, "test_intent")
        assert rows is None

def test_run_sql_binding_error(pipeline, mock_dao):
    intent_def = {"sql_template": "SELECT * FROM flights"}
    params = {}
    mock_dao.execute_raw_query.side_effect = Exception("binding parameter missing")
    with patch("graphdb.pipeline.compile_sql", return_value=("SELECT * FROM flights", [])):
        rows = pipeline._run_sql(intent_def, params, "test_intent")
        assert rows is None

def test_resolve_airport_names_success(pipeline):
    with patch("graphdb.pipeline.execute_select") as mock_select:
        mock_select.return_value = [
            {"airportCode": "SIN", "cityName": "Singapore", "countryName": "Singapore"},
            {"airportCode": "BKK", "cityName": "Bangkok", "countryName": "Thailand"}
        ]
        res = pipeline._resolve_airport_names(["SIN", "BKK"])
        assert res == {"SIN": "Singapore, Singapore", "BKK": "Bangkok, Thailand"}

def test_resolve_airport_names_empty(pipeline):
    assert pipeline._resolve_airport_names([]) == {}

def test_resolve_airport_names_error(pipeline):
    with patch("graphdb.pipeline.execute_select", side_effect=Exception("SPARQL Error")):
        res = pipeline._resolve_airport_names(["SIN"])
        assert res == {}

def test_enrich_destination_names(pipeline):
    rows = [{"destination": "SIN", "price": 100}, {"destination": "BKK", "price": 200}]
    with patch.object(pipeline, "_resolve_airport_names") as mock_resolve:
        mock_resolve.return_value = {"SIN": "Singapore, Singapore", "BKK": "Bangkok, Thailand"}
        pipeline._enrich_destination_names(rows)
        assert rows[0]["destination"] == "Singapore, Singapore (SIN)"
        assert rows[1]["destination"] == "Bangkok, Thailand (BKK)"

def test_enrich_destination_names_no_dest(pipeline):
    rows = [{"price": 100}]
    pipeline._enrich_destination_names(rows)
    assert rows == [{"price": 100}]

def test_enrich_destination_names_empty_rows(pipeline):
    pipeline._enrich_destination_names([])
    # Should not raise

def test_enrich_destination_names_resolution_fail(pipeline):
    rows = [{"destination": "SIN"}]
    with patch.object(pipeline, "_resolve_airport_names", return_value={}):
        pipeline._enrich_destination_names(rows)
        assert rows[0]["destination"] == "SIN"

def test_inject_city_name(pipeline):
    params = {"destination_airport_code": "SIN"}
    with patch.object(pipeline, "_resolve_airport_names") as mock_resolve:
        mock_resolve.return_value = {"SIN": "Singapore, Singapore"}
        new_params = pipeline._inject_city_name(params)
        assert new_params["city_name"] == "Singapore"

def test_inject_city_name_no_code(pipeline):
    params = {}
    assert pipeline._inject_city_name(params) == params

def test_inject_city_name_already_exists(pipeline):
    params = {"destination_airport_code": "SIN", "city_name": "Existing"}
    assert pipeline._inject_city_name(params) == params

def test_extract_country_code(pipeline):
    mock_graph = MagicMock()
    # Mock Namespace
    with patch("rdflib.Namespace") as mock_ns:
        EX = mock_ns.return_value
        # Mock subjects(EX.prop_airportCode, None)
        mock_graph.subjects.return_value = ["airport1"]
        # Mock value(airport, EX.prop_airportCode)
        mock_graph.value.side_effect = lambda s, p: {
            ("airport1", EX.prop_airportCode): "SIN",
            ("airport1", EX.prop_inCity): "city1",
            ("city1", EX.prop_belongsToCountry): "country1",
            ("country1", EX.prop_countryCode): "SG"
        }.get((s, p))
        
        res = pipeline._extract_country_code(mock_graph, "SIN")
        assert res == "SG"

def test_extract_country_code_not_found(pipeline):
    mock_graph = MagicMock()
    with patch("rdflib.Namespace"):
        mock_graph.subjects.return_value = []
        res = pipeline._extract_country_code(mock_graph, "XXX")
        assert res is None

def test_run_once_prefilled_plan(pipeline):
    prefilled_plan = {"intent": "test_intent", "parameters": {}}
    semantics = {"intents": {"test_intent": {"execution_phase": "sql_first"}}}
    
    with patch("graphdb.pipeline.validate", return_value=(True, "")):
        with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
            with patch("graphdb.pipeline.format_table", return_value="table"):
                res = pipeline.run_once("question", semantics, "intents", "schema", prefilled_plan=prefilled_plan)
                assert res == prefilled_plan

def test_run_once_llm_error_value(pipeline):
    semantics = {"intents": {}}
    with patch("graphdb.pipeline.call_gemini", side_effect=ValueError("LLM Error")):
        res = pipeline.run_once("question", semantics, "intents", "schema")
        assert res is None

def test_run_once_llm_exception(pipeline):
    semantics = {"intents": {}}
    with patch("graphdb.pipeline.call_gemini", side_effect=Exception("Unexpected Error")):
        res = pipeline.run_once("question", semantics, "intents", "schema")
        assert res is None

def test_run_once_multi_leg_query(pipeline):
    semantics = {"intents": {}}
    with patch("graphdb.pipeline.call_gemini", return_value=[{"intent": "i1"}, {"intent": "i2"}]):
        res = pipeline.run_once("question", semantics, "intents", "schema")
        assert res is None

def test_run_once_missing_params(pipeline):
    semantics = {"intents": {}}
    with patch("graphdb.pipeline.call_gemini", return_value={"intent": "i1", "missing_params": ["origin"]}):
        res = pipeline.run_once("question", semantics, "intents", "schema")
        assert res is None

def test_run_once_validation_fail_unknown_intent(pipeline):
    semantics = {"intents": {}}
    query_plan = {"intent": "unknown"}
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(False, "Unknown intent")):
            res = pipeline.run_once("question", semantics, "intents", "schema")
            assert res is None

def test_run_once_validation_fail_other(pipeline):
    semantics = {"intents": {}}
    query_plan = {"intent": "i1"}
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(False, "Other error")):
            res = pipeline.run_once("question", semantics, "intents", "schema")
            assert res is None

def test_run_once_hybrid_success(pipeline):
    semantics = {
        "intents": {
            "hybrid_intent": {
                "execution_phase": "sparql_then_sql",
                "sparql_template": "SELECT ?airportCode WHERE { ... }",
                "sql_template": "SELECT * FROM flights WHERE destination = :destination_airport_codes",
                "sparql_result_binding": {"variable": "airportCode", "inject_as": "destination_airport_codes"}
            }
        }
    }
    query_plan = {"intent": "hybrid_intent", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_select", return_value=[{"airportCode": "BKK"}]):
                    with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                        with patch("graphdb.pipeline.format_table", return_value="table"):
                            res = pipeline.run_once("question", semantics, "intents", "schema")
                            assert res == query_plan

def test_run_once_hybrid_missing_origin(pipeline):
    semantics = {
        "intents": {
            "hybrid_intent": {
                "execution_phase": "sparql_then_sql",
                "sql_template": "SELECT * FROM flights WHERE origin = :origin",
            }
        }
    }
    query_plan = {"intent": "hybrid_intent", "parameters": {}} # Missing origin
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            res = pipeline.run_once("question", semantics, "intents", "schema")
            assert res is None

def test_run_once_hybrid_no_codes(pipeline):
    semantics = {
        "intents": {
            "hybrid_intent": {
                "execution_phase": "sparql_then_sql",
                "sparql_template": "...",
                "sparql_result_binding": {"variable": "airportCode", "inject_as": "destination_airport_codes"}
            }
        }
    }
    query_plan = {"intent": "hybrid_intent", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_select", return_value=[]):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_hybrid_sparql_error(pipeline):
    semantics = {
        "intents": {
            "hybrid_intent": {
                "execution_phase": "sparql_then_sql",
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "hybrid_intent", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_select", side_effect=ConnectionError("Conn Error")):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res is None

def test_run_once_round_trip(pipeline):
    semantics = {
        "intents": {
            "round_trip_on_route": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "round_trip_on_route", "parameters": {
        "origin": "SIN", "destination": "BKK", "departure_date": "2026-06-01", "return_date": "2026-06-10"
    }}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                with patch("graphdb.pipeline.format_round_trip", return_value="rt_table"):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_round_trip_no_dates(pipeline):
    semantics = {
        "intents": {
            "round_trip_on_route": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "round_trip_on_route", "parameters": {
        "origin": "SIN", "destination": "BKK"
    }}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                with patch("graphdb.pipeline.format_round_trip", return_value="rt_table"):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_sql_first_success(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                with patch("graphdb.pipeline.format_table", return_value="table"):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_sql_first_no_rows_trip_r(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {"trip_type": "R"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[]):
                res = pipeline.run_once("question", semantics, "intents", "schema")
                assert res == query_plan

def test_run_once_sql_first_date_out_of_range(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {"departure_date": "2026-12-01"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[]):
                res = pipeline.run_once("question", semantics, "intents", "schema")
                assert res == query_plan

def test_run_once_sql_first_transit_success(pipeline):
    semantics = {
        "intents": {
            "cheapest_flight_on_route": {
                "execution_phase": "sql_first",
            },
            "cheapest_transit_route": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "cheapest_flight_on_route", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            # first call returns [], second call (transit) returns rows
            with patch.object(pipeline, "_run_sql", side_effect=[[], [{"id": "transit1"}]]):
                with patch("graphdb.pipeline.format_transit_route", return_value="transit_table"):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_sql_first_no_results(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {"origin": "SIN"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[]):
                res = pipeline.run_once("question", semantics, "intents", "schema")
                assert res == query_plan

def test_run_once_sql_aggregate_intent(pipeline):
    semantics = {
        "intents": {
            "cheapest_month_for_route": {
                "execution_phase": "sql_first",
            }
        }
    }
    query_plan = {"intent": "cheapest_month_for_route", "parameters": {}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"month": "June"}]):
                with patch("graphdb.pipeline.format_cheapest_month", return_value="month_res"):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res == query_plan

def test_run_once_sql_enrichment_success(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
                "enrichment_triggers": True
            },
            "destination_vacation_plan": {
                "sparql_template": "CONSTRUCT { ... }",
                "visa_enrichment_trigger": "visa_check"
            },
            "visa_check": {
                "sparql_template": "SELECT ...",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {
        "destination": "BKK", "passport_country_code": "SG"
    }}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                    with patch("graphdb.pipeline.execute_construct", return_value=[("s", "p", "o")]):
                        with patch("graphdb.pipeline.execute_select", return_value=[{"visa": "OK"}]):
                            with patch("graphdb.pipeline.format_flight_with_destination", return_value="enriched_res"):
                                with patch.object(pipeline, "_extract_country_code", return_value="TH"):
                                    res = pipeline.run_once("question", semantics, "intents", "schema")
                                    assert res == query_plan

def test_run_once_sql_enrichment_conn_error(pipeline):
    semantics = {
        "intents": {
            "sql_intent": {
                "execution_phase": "sql_first",
                "enrichment_triggers": True
            },
            "destination_vacation_plan": {
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "sql_intent", "parameters": {"destination": "BKK"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch.object(pipeline, "_run_sql", return_value=[{"id": 1}]):
                with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                    with patch("graphdb.pipeline.execute_construct", side_effect=ConnectionError("Conn Error")):
                        with patch("graphdb.pipeline.format_table", return_value="table"):
                            res = pipeline.run_once("question", semantics, "intents", "schema")
                            assert res is None # Note: in code it returns, but doesn't return query_plan

def test_run_once_sparql_only_construct_success(pipeline):
    semantics = {
        "intents": {
            "vacation_plan": {
                "execution_phase": "sparql_only",
                "sparql_type": "construct",
                "sparql_template": "...",
                "visa_enrichment_trigger": "visa_check"
            },
            "visa_check": {
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "vacation_plan", "parameters": {"destination_airport_code": "BKK", "passport_country_code": "SG"}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_construct", return_value=[("s", "p", "o")]):
                    with patch("graphdb.pipeline.execute_select", return_value=[{"visa": "OK"}]):
                        with patch("graphdb.pipeline.format_vacation_plan", return_value="vacation_res"):
                            with patch.object(pipeline, "_extract_country_code", return_value="TH"):
                                res = pipeline.run_once("question", semantics, "intents", "schema")
                                assert res == query_plan

def test_run_once_sparql_only_select_success(pipeline):
    semantics = {
        "intents": {
            "sparql_intent": {
                "execution_phase": "sparql_only",
                "sparql_type": "select",
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "sparql_intent", "parameters": {}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_select", return_value=[{"res": 1}]):
                    with patch("graphdb.pipeline.format_table", return_value="table"):
                        res = pipeline.run_once("question", semantics, "intents", "schema")
                        assert res == query_plan

def test_run_once_sparql_select_various_intents(pipeline):
    intents_to_test = [
        "destination_highlights", "destination_attractions", "visa_destinations_by_policy",
        "destination_weather_by_month", "country_weather_by_month", "destination_festivals",
        "destination_transport", "destination_cuisines", "destination_language",
        "destination_timezone", "destination_currency", "airport_amenities",
        "destination_safety", "destination_neighborhoods", "destination_overview",
        "destination_travel_styles", "best_months_to_visit", "all_routes_from_origin",
        "routes_by_airline", "airlines_covering_route", "routes_from_origin_by_country",
        "currencies_by_region", "visa_check_for_destination", "visa_required_destinations",
        "airports_in_city", "destinations_by_language", "destinations_with_festivals_in_month",
        "cities_in_country", "country_info", "destinations_solo_female_friendly",
        "currency_exchange_rate", "visa_duration_check", "airports_with_amenity",
        "safe_destinations_list", "festivals_by_type_global", "airport_info",
        "destinations_by_season", "destinations_good_weather_in_month"
    ]
    
    formatters = [
        "format_highlights", "format_attractions", "format_visa_list", "format_weather",
        "format_country_weather", "format_festivals", "format_transport", "format_cuisines",
        "format_language", "format_timezone", "format_destination_currency", "format_amenities",
        "format_safety", "format_neighborhoods", "format_overview", "format_travel_styles",
        "format_best_months", "format_route_list", "format_currency_list", "format_visa_check",
        "format_airports_in_city", "format_language_destinations", "format_festivals_by_month",
        "format_cities_in_country", "format_country_info", "format_solo_female_destinations",
        "format_exchange_rate", "format_visa_duration", "format_airports_with_amenity",
        "format_safe_destinations", "format_festivals_by_type", "format_airport_info",
        "format_destinations_by_season", "format_good_weather_destinations"
    ]
    
    for intent in intents_to_test:
        semantics = {
            "intents": {
                intent: {
                    "execution_phase": "sparql_only",
                    "sparql_type": "select",
                    "sparql_template": "...",
                }
            }
        }
        query_plan = {"intent": intent, "parameters": {"destination_airport_code": "SIN"}}
        
        with patch("graphdb.pipeline.call_gemini", return_value=query_plan), \
             patch("graphdb.pipeline.validate", return_value=(True, "")), \
             patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"), \
             patch("graphdb.pipeline.execute_select", return_value=[{"res": 1}]), \
             patch("graphdb.pipeline.format_table", return_value="table"):
            
            # Patch all formatters
            patches = [patch(f"graphdb.pipeline.{f}", return_value="res") for f in formatters]
            with ExitStack():
                for p in patches:
                    p.start()
                res = pipeline.run_once("question", semantics, "intents", "schema")
                assert res == query_plan

def test_run_once_sparql_construct_error(pipeline):
    semantics = {
        "intents": {
            "vacation_plan": {
                "execution_phase": "sparql_only",
                "sparql_type": "construct",
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "vacation_plan", "parameters": {}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_construct", side_effect=ConnectionError("Conn Error")):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res is None

def test_run_once_unknown_phase(pipeline):
    semantics = {
        "intents": {
            "unknown_phase_intent": {
                "execution_phase": "unknown_phase",
            }
        }
    }
    query_plan = {"intent": "unknown_phase_intent", "parameters": {}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            res = pipeline.run_once("question", semantics, "intents", "schema")
            assert res is None

def test_run_once_sparql_select_conn_error(pipeline):
    semantics = {
        "intents": {
            "sparql_intent": {
                "execution_phase": "sparql_only",
                "sparql_type": "select",
                "sparql_template": "...",
            }
        }
    }
    query_plan = {"intent": "sparql_intent", "parameters": {}}
    
    with patch("graphdb.pipeline.call_gemini", return_value=query_plan):
        with patch("graphdb.pipeline.validate", return_value=(True, "")):
            with patch("graphdb.pipeline.compile_sparql", return_value="SPARQL"):
                with patch("graphdb.pipeline.execute_select", side_effect=ConnectionError("Conn Error")):
                    res = pipeline.run_once("question", semantics, "intents", "schema")
                    assert res is None

def test_main_empty_question(pipeline, mock_dao):
    pipeline.get_connection = MagicMock()
    with patch("graphdb.pipeline.load_semantics", return_value={"intents": {}}):
        with patch("graphdb.pipeline.build_prompt_context", return_value=("intents", "schema")):
            with patch("graphdb.pipeline.check_graphdb", return_value=True):
                with patch("builtins.input", side_effect=["", "quit"]):
                    with patch.object(pipeline, "run_once", return_value={"intent": "i1"}):
                        pipeline.main()

def test_main_keyboard_interrupt(pipeline, mock_dao):
    pipeline.get_connection = MagicMock()
    with patch("graphdb.pipeline.load_semantics", return_value={"intents": {}}):
        with patch("graphdb.pipeline.build_prompt_context", return_value=("intents", "schema")):
            with patch("graphdb.pipeline.check_graphdb", return_value=True):
                with patch("builtins.input", side_effect=KeyboardInterrupt):
                    with pytest.raises(SystemExit):
                        pipeline.main()

def test_main_startup_graphdb_fail(pipeline, mock_dao):
    pipeline.get_connection = MagicMock()
    with patch("graphdb.pipeline.load_semantics", return_value={"intents": {}}):
        with patch("graphdb.pipeline.build_prompt_context", return_value=("intents", "schema")):
            with patch("graphdb.pipeline.check_graphdb", return_value=False):
                with patch("builtins.input", side_effect=["quit"]):
                    pipeline.main()
                            # If it doesn't raise and exits, it's a success for a basic test
