from pathlib import Path

import graphdb.build_graphdb_ttl as ttl


def test_ttl_helper_functions_and_subject_generation():
    assert ttl.ttl_literal('a"b\\c') == '"a\\\"b\\\\c"'
    assert ttl.ttl_decimal("12.5") == '"12.5"^^xsd:decimal'
    assert ttl.ttl_int("7") == '"7"^^xsd:integer'
    assert ttl.ttl_bool_str("yes") == "true"
    assert ttl.ttl_bool_str("no") == "false"
    assert ttl.ttl_bool_str("maybe") == '"maybe"'
    assert ttl.resource_id(" Singapore / Changi Airport ") == "Singapore_Changi_Airport"
    assert ttl.subject("City", "Singapore") == "ex:City_Singapore"


def test_emit_block_appends_expected_turtle():
    lines = []
    ttl.emit_block(lines, "ex:City_Singapore", "ex:City", ['rdfs:label "Singapore"'])

    assert lines == ['ex:City_Singapore a ex:City ;\n    rdfs:label "Singapore" .\n']


def test_load_rows_and_build_ddl(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("col1,col2\na,b\n", encoding="utf-8")

    rows = ttl.load_rows(csv_path)
    ddl = ttl.build_ddl()

    assert rows == [{"col1": "a", "col2": "b"}]
    assert "ex:travel-graph-ddl a owl:Ontology" in ddl
    assert "ex:City a owl:Class" in ddl
    assert "ex:Route a owl:Class" in ddl
