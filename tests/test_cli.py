from tareco.cli import main


def test_cli_writes_html(tmp_path, capsys):
    edges = tmp_path / "e.csv"
    edges.write_text("de,para\nana,bia\nbia,caio\n", encoding="utf-8")
    out = tmp_path / "g.html"
    assert main([str(edges), "-o", str(out), "--title", "Amigos", "--color", "degree"]) == 0
    assert out.exists() and "Amigos" in out.read_text(encoding="utf-8")
    assert str(out.resolve()) in capsys.readouterr().out


def test_cli_summary(tmp_path, capsys):
    edges = tmp_path / "e.csv"
    edges.write_text("source,target\na,b\nb,c\n", encoding="utf-8")
    assert main([str(edges), "--summary", "--directed"]) == 0
    out = capsys.readouterr().out
    assert "nodes" in out and "directed            True" in out


def test_cli_reports_errors(tmp_path, capsys):
    assert main([str(tmp_path / "missing.csv")]) == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_big_graph_options(tmp_path):
    edges = tmp_path / "e.csv"
    lines = ["source,target"] + [f"n{i},n{i + 1}" for i in range(50)]
    edges.write_text(chr(10).join(lines), encoding="utf-8")
    out = tmp_path / "g.html"
    assert main([str(edges), "-o", str(out), "--renderer", "webgl", "--max-nodes", "20"]) == 0
    page = out.read_text(encoding="utf-8")
    assert '"renderer":"webgl"' in page and '"counts":{"nodes":20' in page
