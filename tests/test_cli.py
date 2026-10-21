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
