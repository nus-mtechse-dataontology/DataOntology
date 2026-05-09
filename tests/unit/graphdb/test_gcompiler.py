import pytest
from graphdb.gcompiler import compile_sparql, compile_sql

# ==============================================================================
# SPARQL Compiler Tests
# ==============================================================================

class TestCompileSparql:
    def test_basic_substitution(self):
        template = "SELECT * WHERE { ?s :name :name_param . ?s :age :age_param . ?s :active :active_param . ?s :score :score_param . }"
        params = {
            "name_param": "John Doe",
            "age_param": 30,
            "active_param": True,
            "score_param": 95.5
        }
        expected = 'SELECT * WHERE { ?s :name "John Doe" . ?s :age 30 . ?s :active true . ?s :score 95.5 . }'
        assert compile_sparql(template, params) == expected

    def test_unreplaced_parameters(self):
        template = "SELECT * WHERE { ?s :name :name_param . ?s :city :city_param . }"
        params = {"name_param": "John Doe"}
        # :city_param should remain as is
        expected = 'SELECT * WHERE { ?s :name "John Doe" . ?s :city :city_param . }'
        assert compile_sparql(template, params) == expected

    def test_union_branch_stripping_both_resolved(self):
        template = "SELECT * WHERE { { ?s <http://ex/p1> :v1 } UNION { ?s <http://ex/p2> :v2 } }"
        params = {"v1": "val1", "v2": "val2"}
        expected = 'SELECT * WHERE { { ?s <http://ex/p1> "val1" } UNION { ?s <http://ex/p2> "val2" } }'
        assert compile_sparql(template, params) == expected

    def test_union_branch_stripping_left_unresolved(self):
        template = "SELECT * WHERE { { ?s <http://ex/p1> :v1 } UNION { ?s <http://ex/p2> :v2 } }"
        params = {"v2": "val2"}
        # Left branch has :v1 (unresolved), should be stripped
        expected = 'SELECT * WHERE { { ?s <http://ex/p2> "val2" } }'
        assert compile_sparql(template, params) == expected

    def test_union_branch_stripping_right_unresolved(self):
        template = "SELECT * WHERE { { ?s <http://ex/p1> :v1 } UNION { ?s <http://ex/p2> :v2 } }"
        params = {"v1": "val1"}
        # Right branch has :v2 (unresolved), should be stripped
        expected = 'SELECT * WHERE { { ?s <http://ex/p1> "val1" } }'
        assert compile_sparql(template, params) == expected

    def test_union_branch_stripping_both_unresolved(self):
        template = "SELECT * WHERE { { ?s :p1 :v1 } UNION { ?s :p2 :v2 } }"
        params = {}
        # Both branches unresolved, UNION and branches should be removed
        # The current implementation does re.sub(..., _pick_branch, sparql).strip()
        # if both bad, it returns "". 
        # Let's check exactly what happens.
        # Template: "SELECT * WHERE { { ?s :p1 :v1 } UNION { ?s :p2 :v2 } }"
        # result: "SELECT * WHERE {  }"
        # Wait, the regex is r"\{([^{}]*)\}\s*UNION\s*\{([^{}]*)\}"
        # It matches "{ ?s :p1 :v1 } UNION { ?s :p2 :v2 }"
        # If both bad, returns "". 
        # So result is "SELECT * WHERE {  }"
        result = compile_sparql(template, params)
        assert "UNION" not in result
        assert ":v1" not in result
        assert ":v2" not in result

    def test_union_branch_stripping_nested_braces(self):
        # The docstring says "Works for flat branches only (no nested braces inside the branch)"
        # So if there are nested braces, the regex r"\{([^{}]*)\}\s*UNION\s*\{([^{}]*)\}" won't match.
        template = "SELECT * WHERE { { ?s :p1 { ?x :p2 :v1 } } UNION { ?s :p2 :v2 } }"
        params = {"v2": "val2"}
        # It should NOT strip the left branch because it's nested.
        result = compile_sparql(template, params)
        assert "UNION" in result
        assert ":v1" in result
        assert '"val2"' in result

    def test_empty_params(self):
        template = "SELECT * WHERE { ?s :p :v }"
        params = {}
        assert compile_sparql(template, params) == "SELECT * WHERE { ?s :p :v }"

# ==============================================================================
# SQL Compiler Tests
# ==============================================================================

class TestCompileSql:
    def test_missing_sql_template(self):
        intent_def = {"note": "some note"}
        params = {}
        with pytest.raises(ValueError, match="Intent has no sql_template"):
            compile_sql(intent_def, params)

    def test_default_limit_injection(self):
        # Case 1: destinations_by_country_from_origin -> limit 50
        intent_def = {"sql_template": "SELECT * FROM table LIMIT :limit"}
        params = {}
        sql, bound = compile_sql(intent_def, params, intent_name="destinations_by_country_from_origin")
        assert bound["limit"] == 50
        
        # Case 2: Other intent -> DEFAULT_LIMIT
        # I don't know DEFAULT_LIMIT value, but it should be consistent
        from src.graphdb.config import DEFAULT_LIMIT
        sql, bound = compile_sql(intent_def, params, intent_name="some_other_intent")
        assert bound["limit"] == DEFAULT_LIMIT

        # Case 3: Limit provided in params
        params = {"limit": 100}
        sql, bound = compile_sql(intent_def, params, intent_name="some_other_intent")
        assert bound["limit"] == 100

    def test_optional_clause_appending_trip_type(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 ORDER BY f.price",
            "note": "Supports trip_type"
        }
        params = {"trip_type": "one_way"}
        sql, bound = compile_sql(intent_def, params)
        assert "AND f.f_trip_type = :trip_type" in sql
        assert "ORDER BY" in sql
        assert sql.find("AND f.f_trip_type = :trip_type") < sql.find("ORDER BY")
        assert bound["trip_type"] == "one_way"

    def test_optional_clause_appending_currency_code(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 GROUP BY f.id",
            "note": "Supports currency_code"
        }
        params = {"currency_code": "USD"}
        sql, bound = compile_sql(intent_def, params)
        assert "AND f.f_currency_code = :currency_code" in sql
        assert "GROUP BY" in sql
        assert sql.find("AND f.f_currency_code = :currency_code") < sql.find("GROUP BY")
        assert bound["currency_code"] == "USD"

    def test_optional_clause_appending_cabin_class(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 LIMIT :limit",
            "note": "Supports cabin_class"
        }
        params = {"cabin_class": "business"}
        sql, bound = compile_sql(intent_def, params)
        assert "AND f.f_cabin_class = :cabin_class" in sql
        assert "LIMIT" in sql
        assert sql.find("AND f.f_cabin_class = :cabin_class") < sql.find("LIMIT")
        assert bound["cabin_class"] == "business"

    def test_optional_clause_appending_max_price(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 ORDER BY f.price",
            "note": "Supports max_price"
        }
        params = {"max_price": 1000}
        sql, bound = compile_sql(intent_def, params)
        assert "HAVING MIN(f.f_total_amount_fare_total) * 2 <= :max_price" in sql
        assert "ORDER BY" in sql
        assert sql.find("HAVING") < sql.find("ORDER BY")
        assert bound["max_price"] == 1000

    def test_optional_clause_appending_day_type(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 LIMIT :limit",
            "note": "Supports day_type"
        }
        
        day_types = {
            "weekend": "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) IN (6, 7)",
            "weekday": "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) BETWEEN 1 AND 5",
            "friday": "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) = 5",
            "sunday": "AND EXTRACT(ISODOW FROM CAST(f.f_departure_date AS timestamp)) = 7",
        }
        
        for dt, expected_clause in day_types.items():
            params = {"day_type": dt}
            sql, bound = compile_sql(intent_def, params)
            assert expected_clause in sql
            assert sql.find(expected_clause) < sql.find("LIMIT")

    def test_destinations_by_duration_dynamic_having(self):
        intent_def = {
            "sql_template": "SELECT * FROM flights f WHERE 1=1 HAVING some_old_condition ORDER BY f.price",
            "note": ""
        }
        
        # Case 1: max_duration_mins only
        params = {"max_duration_mins": 120}
        sql, bound = compile_sql(intent_def, params, intent_name="destinations_by_duration")
        assert "HAVING MIN(f.f_flight_duration) <= :max_duration_mins" in sql
        assert "some_old_condition" not in sql
        assert bound["max_duration_mins"] == 120

        # Case 2: min_duration_mins only
        params = {"min_duration_mins": 60}
        sql, bound = compile_sql(intent_def, params, intent_name="destinations_by_duration")
        assert "HAVING MIN(f.f_flight_duration) >= :min_duration_mins" in sql
        assert bound["min_duration_mins"] == 60

        # Case 3: both
        params = {"max_duration_mins": 120, "min_duration_mins": 60}
        sql, bound = compile_sql(intent_def, params, intent_name="destinations_by_duration")
        assert "HAVING MIN(f.f_flight_duration) <= :max_duration_mins AND MIN(f.f_flight_duration) >= :min_duration_mins" in sql
        assert bound["max_duration_mins"] == 120
        assert bound["min_duration_mins"] == 60

        # Case 4: neither
        params = {}
        sql, bound = compile_sql(intent_def, params, intent_name="destinations_by_duration")
        assert "HAVING" not in sql

    def test_in_clause_expansion_destination_airport_codes(self):
        intent_def = {"sql_template": "SELECT * FROM flights WHERE origin_code IN :destination_airport_codes"}
        params = {"destination_airport_codes": ["SFO", "LAX", "JFK"]}
        sql, bound = compile_sql(intent_def, params)
        assert "IN (:code_0, :code_1, :code_2)" in sql
        assert bound["code_0"] == "SFO"
        assert bound["code_1"] == "LAX"
        assert bound["code_2"] == "JFK"
        assert "destination_airport_codes" not in bound

    def test_in_clause_expansion_aircraft_codes(self):
        intent_def = {"sql_template": "SELECT * FROM flights WHERE ac_code IN (:aircraft_codes)"}
        params = {"aircraft_codes": ["A320", "B737"]}
        sql, bound = compile_sql(intent_def, params)
        assert "IN (:ac_0, :ac_1)" in sql
        assert bound["ac_0"] == "A320"
        assert bound["ac_1"] == "B737"
        assert "aircraft_codes" not in bound

    def test_in_clause_expansion_non_list(self):
        intent_def = {"sql_template": "SELECT * FROM flights WHERE origin_code IN :destination_airport_codes"}
        params = {"destination_airport_codes": "SFO"}
        sql, bound = compile_sql(intent_def, params)
        assert "IN :destination_airport_codes" in sql
        assert bound["destination_airport_codes"] == "SFO"
