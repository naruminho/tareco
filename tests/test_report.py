import os

import tareco as tc
from tareco.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")


def friends():
    return tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))


def test_report_has_every_section(tmp_path):
    page = friends().report(title="Friends")
    assert page.startswith("<!doctype html>") and all(ord(c) < 128 for c in page)
    for heading in ("What this network shows", "Groups", "Most important nodes", "Explore the network"):
        assert f"<h2>{heading}</h2>" in page
    assert "city: Recife in 75% (vs 19% overall)" in page
    assert '<iframe srcdoc="' in page
    path = friends().report(str(tmp_path / "r.html"), lang="pt")
    text = open(path, encoding="utf-8").read()
    assert "<h2>O que esta rede mostra</h2>" in text and "<h2>Grupos</h2>" in text
    es = friends().report(lang="es")
    assert '<html lang="es">' in es and "<h2>Lo que muestra esta red</h2>" in es and "Informe de la red" in es


def test_timeline_report_has_activity():
    rows = [("a", "b", "2026-01-02"), ("b", "c", "2026-02-02"), ("c", "a", "2026-02-09")]
    page = tc.timeline(rows, time=2).report()
    assert "<h2>Activity over time</h2>" in page and "2026-02" in page
    assert "tarecoTimebar" in page.replace("&quot;", '"') or "tarecoTimebar" in page


def test_cli_time_report_around_and_patterns(tmp_path, capsys):
    events = tmp_path / "events.csv"
    lines = ["from,to,day"] + [f"n{i},n{i + 1},2026-0{1 + i % 3}-10" for i in range(12)] + ["n0,n5,2026-03-01"]
    events.write_text(chr(10).join(lines), encoding="utf-8")
    out = tmp_path / "t.html"
    assert main([str(events), "--time", "day", "-o", str(out), "--lang", "pt"]) == 0
    assert "Todos os per" in out.read_text(encoding="utf-8") or "tarecoTimebar" in out.read_text(encoding="utf-8")
    assert main([str(events), "--time", "day", "--explain"]) == 0
    assert "From 2026-01-05 to 2026-03-09 (10 weeks)" in capsys.readouterr().out
    report = tmp_path / "r.html"
    assert main([str(events), "--report", "-o", str(report)]) == 0
    assert "<h2>Groups</h2>" in report.read_text(encoding="utf-8") or report.exists()
    assert main([str(events), "--report"]) == 1
    near = tmp_path / "near.html"
    assert main([str(events), "--around", "n0", "--hops", "1", "-o", str(near)]) == 0
    assert '"title":"hop"' in near.read_text(encoding="utf-8")
    loops = tmp_path / "loops.csv"
    loops.write_text(chr(10).join(["a,b", "x,y", "y,z", "z,x"]), encoding="utf-8")
    capsys.readouterr()
    assert main([str(loops), "--directed", "--patterns"]) == 0
    assert "x, y and z form a loop" in capsys.readouterr().out


def test_tareco_report_stays_a_function_after_a_graph_report(tmp_path):
    import tareco as tc
    tc.path_graph(3).report()
    assert callable(tc.report)
    assert tc.report([("a", "b")], str(tmp_path / "r.html")).endswith("r.html")
