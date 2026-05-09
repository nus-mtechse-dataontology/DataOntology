import pytest
from unittest.mock import MagicMock, patch
import json
from graphdb.sparql_exec import execute_select, execute_construct, check_graphdb

@patch("src.graphdb.sparql_exec.urllib.request.urlopen")
def test_execute_select_success(mock_urlopen):
    # Mock response for SELECT query
    mock_response = MagicMock()
    mock_response.__enter__.return_value.read.return_value = json.dumps({
        "head": {"vars": ["name", "code"]},
        "results": {
            "bindings": [
                {"name": {"value": "Changi Airport"}, "code": {"value": "SIN"}},
                {"name": {"value": "Suvarnabhumi Airport"}, "code": {"value": "BKK"}},
            ]
        }
    }).encode()
    mock_urlopen.return_value = mock_response

    results = execute_select("SELECT * WHERE { ?name ?code }")
    
    assert len(results) == 2
    assert results[0]["name"] == "Changi Airport"
    assert results[1]["code"] == "BKK"

@patch("src.graphdb.sparql_exec.urllib.request.urlopen")
def test_execute_construct_success(mock_urlopen):
    # Mock response for CONSTRUCT query (Turtle format)
    mock_response = MagicMock()
    mock_response.__enter__.return_value.read.return_value = b"<http://ex/A> <http://ex/P> 'Val' ."
    mock_urlopen.return_value = mock_response

    graph = execute_construct("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")
    
    assert graph.triples((None, None, None))
    # Verify it's an rdflib Graph
    from rdflib import Graph
    assert isinstance(graph, Graph)

@patch("src.graphdb.sparql_exec.urllib.request.urlopen")
def test_check_graphdb_success(mock_urlopen):
    mock_response = MagicMock()
    mock_urlopen.return_value = mock_response
    
    assert check_graphdb() is True

@patch("src.graphdb.sparql_exec.urllib.request.urlopen")
def test_check_graphdb_failure(mock_urlopen):
    mock_urlopen.side_effect = Exception("Connection error")
    
    assert check_graphdb() is False
