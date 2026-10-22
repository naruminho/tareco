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


def test_cli_explain_in_portuguese(tmp_path, capsys):
    edges = tmp_path / "e.csv"
    edges.write_text(chr(10).join(["de,para", "ana,bia", "bia,caio", "caio,ana"]), encoding="utf-8")
    assert main([str(edges), "--explain", "--lang", "pt"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("O que esta rede mostra") and "Tudo est" in out


def test_cli_projects_two_sided_tables(tmp_path, capsys):
    rows = tmp_path / "compras.csv"
    rows.write_text(chr(10).join(["cliente,produto", "ana,arroz", "bia,arroz", "caio,cafe"]), encoding="utf-8")
    out = tmp_path / "g.html"
    assert main([str(rows), "--project", "cliente", "produto", "-o", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert '"counts":{"nodes":3,"edges":1}' in page


def transfers_csv(tmp_path):
    lines = ["tid,from,to,amount,date"]
    lines += [f"T{k},p,q{k % 2},{9500 + k},2026-01-0{k + 1}" for k in range(6)]
    lines += [f"S{k},c{k},shop{k % 3},{20 + k},2026-01-02" for k in range(30)]
    path = tmp_path / "transfers.csv"
    path.write_text(chr(10).join(lines), encoding="utf-8")
    return path


def test_cli_checks_a_table(tmp_path, capsys):
    path = transfers_csv(tmp_path)
    assert main([str(path), "--check"]) == 0
    assert capsys.readouterr().out.startswith("Nothing to fix in 36 rows.")
    bad = tmp_path / "bad.csv"
    bad.write_text(chr(10).join(["from,to", "a,N/A", "b,N/A", "c,d"]), encoding="utf-8")
    assert main([str(bad), "--check"]) == 1
    assert "Rows with a placeholder in to ('N/A'): 2." in capsys.readouterr().out


def test_cli_review_why_and_since(tmp_path, capsys):
    path = transfers_csv(tmp_path)
    assert main([str(path), "-d", "--review", "--limit", "10000"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Worth a look\n1. p (score ") and "just under 10,000" in out
    listed = tmp_path / "list.csv"
    assert main([str(path), "-d", "--review", "--limit", "10000", "-o", str(listed)]) == 0
    assert str(listed.resolve()) in capsys.readouterr().out
    assert listed.read_text(encoding="utf-8").startswith("node,score,signals,reasons,rows,ids")
    assert main([str(path), "-d", "--review", "--limit", "10000", "--since", str(listed)]) == 0
    assert capsys.readouterr().out.strip() == "Nothing changed since the last review."
    assert main([str(path), "-d", "--why", "p", "--lang", "pt"]) == 0
    assert capsys.readouterr().out.startswith("Sobre p")
    assert main([str(path), "-d", "--why", "nobody"]) == 1
    assert "node 'nobody' is not in the graph" in capsys.readouterr().err
    assert main([str(path), "-d", "--review", "-o", str(tmp_path / "list.html")]) == 1
    assert "-o list.csv" in capsys.readouterr().err


def test_cli_statements_and_case_files(tmp_path, capsys):
    rows = ["id,account,date,counterparty,amount"]
    rows += [f"T{k},acc1,2026-01-0{k + 1},acc{2 + k % 2},-{9500 + k}" for k in range(6)]
    rows += [f"R{k},acc{2 + k % 2},2026-01-0{k + 1},acc1,{9500 + k}" for k in range(6)]
    path = tmp_path / "statements.csv"
    path.write_text(chr(10).join(rows), encoding="utf-8")
    case = tmp_path / "case.tareco"
    assert main([str(path), "--account", "account", "--counterparty", "counterparty", "--kind", "transfer",
                 "-o", str(case)]) == 0
    assert str(case.resolve()) in capsys.readouterr().out
    assert main([str(case), "--summary"]) == 0
    assert "edges               2" in capsys.readouterr().out   # each transfer counted once
    assert main([str(case), "--review", "--limit", "10000"]) == 0
    assert "acc1 sent 6 transfers just under 10,000" in capsys.readouterr().out
