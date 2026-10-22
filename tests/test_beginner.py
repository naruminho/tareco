"""The first five minutes: the obvious thing a newcomer tries should just work."""

import warnings
import zipfile

import pytest

import tareco as tc
from tareco import i18n
from tareco.io import GuessWarning
from tareco.viz import build_payload

ROWS = [{"origem": "ana", "destino": "bia", "valor": 900.0}, {"origem": "bia", "destino": "caio", "valor": 10.0},
        {"origem": "caio", "destino": "ana", "valor": 10.0}, {"origem": "caio", "destino": "davi", "valor": 5.0}]


# ------------------------------------------------------------------- weight

def test_an_obvious_amount_column_becomes_the_weight():
    g = tc.Graph(ROWS)
    assert g.attrs["weight"] == "valor"
    assert g.degree("ana", weight="weight") == 910
    assert g.pagerank() == tc.Graph(ROWS, weight="valor").pagerank()
    assert g.pagerank() != g.pagerank(weight=None)
    assert "The strongest connection is ana and bia (900)." in str(g.explain())
    widths = {(l["source"], l["target"]): l["w"] for l in build_payload(g)["links"]}
    assert widths[(0, 1)] > widths[(1, 2)]


def test_weight_can_be_named_or_left_alone():
    g = tc.Graph([{"from": "a", "to": "b", "km": 3}], weight="km")
    assert g.attrs["weight"] == "km" and g.shortest_path("a", "b", weight="weight") == ["a", "b"]
    with pytest.raises(tc.TarecoError, match="no edge column 'kg'"):
        tc.Graph([{"from": "a", "to": "b", "km": 3}], weight="kg")
    two = tc.Graph([{"from": "a", "to": "b", "valor": 1, "quantidade": 2}])
    assert "weight" not in two.attrs  # two candidates: do not guess
    text = tc.Graph([{"from": "a", "to": "b", "valor": "high"}])
    assert "weight" not in text.attrs  # not a number
    assert tc.Graph([("a", "b", 2.0)]).attrs == {}  # a real weight column needs nothing


def test_weight_survives_copies_and_files(tmp_path):
    g = tc.Graph(ROWS)
    assert g.copy().attrs["weight"] == "valor" and g.subgraph(["ana", "bia"]).attrs["weight"] == "valor"
    path = tmp_path / "g.json"
    g.to_json(str(path))
    assert tc.read_json(str(path)).attrs["weight"] == "valor"


def test_a_lone_number_column_is_the_weight():
    rows = [{"from": "a", "to": "b", "messages": 3}, {"from": "b", "to": "c", "messages": 9},
            {"from": "a", "to": "b", "messages": 2}]
    g = tc.Graph(rows)
    assert g.attrs["weight"] == "messages"  # not the count tareco added for the repeated pair
    assert g.edges["a", "b"] == {"messages": 5, "count": 2}
    assert tc.Graph([{"from": "a", "to": "b", "minutes": 4}]).attrs["weight"] == "minutes"
    for name in ("year", "account_id", "accountId", "zip_code", "date"):  # numbers, but not strengths
        assert "weight" not in tc.Graph([{"from": "a", "to": "b", name: 2019}]).attrs
    both = tc.Graph([{"from": "a", "to": "b", "messages": 3, "calls": 1}])
    assert "weight" not in both.attrs  # two candidates: do not guess


# --------------------------------------------------------------------- Excel

def xlsx(path):
    """A small workbook written by hand: two sheets, a shared string table and a date column."""
    sheet1 = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c><c r="C2"><v>150.5</v></c>'
        '<c r="D2" s="1"><v>46082.4375</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>bia</t></is></c><c r="B3" t="s"><v>6</v></c>'
        '<c r="C3"><v>80</v></c><c r="D3" s="1"><v>46083</v></c></row>'
        '</sheetData></worksheet>')
    sheet2 = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>nome</t></is></c><c r="B1" t="inlineStr"><is><t>ativo</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>ana</t></is></c><c r="B2" t="b"><v>1</v></c></row>'
        '</sheetData></worksheet>')
    shared = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              + "".join(f"<si><t>{w}</t></si>" for w in ["origem", "destino", "valor", "data", "ana", "bia", "caio"])
              + "</sst>")
    styles = ('<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<cellXfs><xf numFmtId="0"/><xf numFmtId="22"/></cellXfs></styleSheet>')
    workbook = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                '<sheet name="moves" sheetId="1" r:id="rId1"/><sheet name="people" sheetId="2" r:id="rId2"/>'
                '</sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet1)
        z.writestr("xl/worksheets/sheet2.xml", sheet2)
        z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/styles.xml", styles)
    return str(path)


def test_excel_files(tmp_path):
    import datetime as dt
    path = xlsx(tmp_path / "book.xlsx")
    rows = tc.read_excel(path)
    assert rows[0] == {"origem": "ana", "destino": "bia", "valor": 150.5, "data": dt.datetime(2026, 3, 1, 10, 30)}
    assert rows[1]["origem"] == "bia" and rows[1]["valor"] == 80
    assert tc.read_excel(path, sheet="people") == [{"nome": "ana", "ativo": True}]
    assert tc.read_excel(path, sheet=1) == tc.read_excel(path, sheet="people")
    g = tc.Graph(path, nodes=tc.read_excel(path, "people"))
    assert g.edges["ana", "bia"]["valor"] == 150.5 and g.attrs["weight"] == "valor"
    assert g.nodes["ana"] == {"ativo": True}
    t = tc.timeline(path, time="data", freq="day")
    assert t.periods == ["2026-03-01", "2026-03-02"]
    with pytest.raises(tc.TarecoError, match="no sheet 'nope'"):
        tc.read_excel(path, sheet="nope")
    old = tmp_path / "old.xls"
    old.write_bytes(b"not really")
    with pytest.raises(tc.TarecoError, match="save it as .xlsx"):
        tc.Graph(str(old))
    broken = tmp_path / "broken.xlsx"
    broken.write_bytes(b"not a zip")
    with pytest.raises(tc.TarecoError, match="cannot open"):
        tc.Graph(str(broken))


# ----------------------------------------------------------------- shortcuts

def test_top_level_explain_and_report(tmp_path):
    path = tmp_path / "e.csv"
    path.write_text(chr(10).join(["origem,destino,valor", "ana,bia,3", "bia,caio,1", "caio,ana,2"]), encoding="utf-8")
    e = tc.explain(str(path), lang="pt")
    assert str(e).startswith("O que esta rede mostra")
    out = tc.report(str(path), str(tmp_path / "r.html"), title="Teste")
    assert out.endswith("r.html") and "<h1>Teste</h1>" in open(out, encoding="utf-8").read()
    assert str(tc.explain(str(path), directed=True)).count("directed links") == 1


# ------------------------------------------------------------------- language

def test_language_follows_the_computer(monkeypatch):
    monkeypatch.setattr(i18n, "_default", None)
    monkeypatch.delenv("TARECO_LANG", raising=False)
    for var in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    assert i18n.get_language() == "pt"
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert i18n.get_language() == "en"
    monkeypatch.delenv("LANG")
    monkeypatch.setattr(i18n.locale, "getlocale", lambda *a: ("Portuguese_Brazil", "1252"))
    assert i18n.get_language() == "pt"
    monkeypatch.setattr(i18n.locale, "getlocale", lambda *a: ("Spanish_Mexico", "1252"))
    assert i18n.get_language() == "es"
    monkeypatch.setenv("LANG", "es_AR.UTF-8")
    assert i18n.get_language() == "es"
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert i18n.get_language() == "en"
    monkeypatch.delenv("LANG")
    monkeypatch.setenv("TARECO_LANG", "en")
    assert i18n.get_language() == "en"  # an explicit choice wins


# -------------------------------------------------------------------- guesses

def test_guessed_columns_come_with_a_warning():
    with pytest.warns(GuessWarning, match="'x' was used; pass source="):
        g = tc.Graph([{"x": "a", "y": "b"}])
    assert g.has_edge("a", "b")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tc.Graph([("a", "b")])                              # pairs are positional by nature
        tc.Graph([{"origem": "a", "destino": "b"}])         # recognized names
        tc.Graph([{"x": "a", "y": "b"}], source="x", target="y")


def test_top_neighbors_and_projection_attributes():
    g = tc.Graph(ROWS, directed=True)
    assert g.top_neighbors("bia") == [("ana", 900.0), ("caio", 10.0)]
    assert g.top_neighbors("caio", n=1) == [("bia", 10.0)] or g.top_neighbors("caio", n=1) == [("ana", 10.0)]
    rows = [("ana", "arroz"), ("bia", "arroz"), ("bia", "cafe")]
    p = tc.project(rows, attrs=[{"id": "ana", "segmento": "familia"}])
    assert p.nodes["ana"]["segmento"] == "familia" and "segmento" not in p.nodes["bia"]


def test_repeated_pairs_add_up():
    rows = [{"origem": "ana", "destino": "bia", "valor": 100, "data": "2026-01-02"},
            {"origem": "ana", "destino": "bia", "valor": 50, "data": "2026-01-09"},
            {"origem": "bia", "destino": "ana", "valor": 7, "data": "2026-01-10"},
            {"origem": "bia", "destino": "caio", "valor": 1, "data": "2026-01-11"}]
    g = tc.Graph(rows)  # undirected: bia -> ana joins ana - bia
    assert g.edges["ana", "bia"] == {"valor": 157, "data": "2026-01-02", "count": 3}
    assert g.edges["bia", "caio"]["count"] == 1
    assert g.attrs["weight"] == "valor"  # count does not compete with a real amount
    d = tc.Graph(rows, directed=True)
    assert d.edges["ana", "bia"]["valor"] == 150 and d.edges["bia", "ana"]["count"] == 1
    assert "count" not in tc.Graph(rows[2:]).edges["bia", "ana"]  # no repeats, no extra column
    near = tc.neighborhood(rows + [{"origem": "caio", "destino": "davi", "valor": 2, "data": "x", "tags": [1]}],
                           start="ana", hops=3, directed=True)
    assert near.edges["ana", "bia"]["valor"] == 150 and near.edges["ana", "bia"]["count"] == 2
