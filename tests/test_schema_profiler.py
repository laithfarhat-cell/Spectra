from backend.intelligence.schema_profiler import profile
from backend.intelligence.element_synthesizer import recommend


def test_infers_time_series_and_percentiles():
    result=profile([{"timestamp":"2026-11-20T12:00:00Z","service":"api","request_latency_ms":v} for v in [10,20,30,40,100]])
    semantics={c["name"]:c["semantic"] for c in result["columns"]}
    assert semantics["timestamp"]=="timestamp"
    assert semantics["request_latency_ms"]=="latency"
    latency=next(c for c in result["columns"] if c["name"]=="request_latency_ms")
    assert latency["statistics"]["p50"]==30
    assert latency["statistics"]["p99"]==40
    assert any(p["type"]=="timeseries" for p in recommend(result))


def test_recognizes_network_security_entities_and_edges():
    rows=[{"source":"10.0.0.1","target":"10.0.0.2","cve":"CVE-2024-12345","severity":"critical","trace_id":"123e4567-e89b-12d3-a456-426614174000"}]
    result=profile(rows); sem={c["name"]:c["semantic"] for c in result["columns"]}
    assert sem["source"]=="ipv4" and sem["target"]=="ipv4"
    assert sem["cve"]=="cve" and sem["severity"]=="severity" and sem["trace_id"]=="trace_id"
    assert result["relationships"][0]["type"]=="directed_edge"
    assert any(p["type"]=="topology" for p in recommend(result))


def test_empty_data_is_safe_and_bounded():
    assert profile([])["row_count"]==0
    data=[{"host":f"n{i}","value":i} for i in range(50)]
    assert profile(data,sample_size=10)["sampled_rows"]==10


def test_geospatial_pair():
    result=profile([{"latitude":37.7,"longitude":-122.4}])
    assert result["relationships"][0]["type"]=="geospatial_pair"
    assert any(p["type"]=="geo" for p in recommend(result))
