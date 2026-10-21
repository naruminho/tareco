import warnings

import pytest

import tareco as tc
from tareco.bipartite import ProjectionWarning

PURCHASES = [
    ("ana", "rice"), ("bia", "rice"), ("caio", "rice"),
    ("ana", "beans"), ("bia", "beans"),
    ("bia", "coffee"), ("caio", "coffee"),
    ("davi", "tea"),
]


def test_count_projection():
    g = tc.project(PURCHASES)
    assert list(g.nodes) == ["ana", "bia", "caio", "davi"]
    assert g.edges["ana", "bia"] == {"weight": 2, "shared": 2, "examples": "rice, beans"}
    assert g.edges["bia", "caio"]["weight"] == 2 and g.edges["ana", "caio"]["weight"] == 1
    assert g.degree("davi") == 0
    assert g.nodes["bia"] == {"n_1": 3}
    assert g.attrs["projected_on"] == 1 and g.attrs["method"] == "count"


def test_jaccard_and_newman():
    j = tc.project(PURCHASES, method="jaccard")
    assert j.edges["ana", "bia"]["weight"] == pytest.approx(2 / 3)
    assert j.edges["ana", "caio"]["weight"] == pytest.approx(1 / 3)
    nw = tc.project(PURCHASES, method="newman")
    # rice is shared by 3 people (counts 1/2), beans by 2 (counts 1)
    assert nw.edges["ana", "bia"]["weight"] == pytest.approx(1.5)
    assert nw.edges["ana", "caio"]["weight"] == pytest.approx(0.5)
    with pytest.raises(tc.TarecoError):
        tc.project(PURCHASES, method="cosine")


def test_min_shared_and_popular_items():
    assert set(tc.project(PURCHASES, min_shared=2).edges) == {("ana", "bia"), ("bia", "caio")}
    rows = [(f"c{i}", "water") for i in range(50)] + [("c1", "wine"), ("c2", "wine")]
    with pytest.warns(ProjectionWarning, match="1 items shared by more than 10"):
        g = tc.project(rows, max_item_size=10)
    assert set(g.edges) == {("c1", "c2")} and g.attrs["skipped_items"] == 1
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert tc.project(rows, max_item_size=None).edge_count == 50 * 49 // 2


def test_named_columns_and_node_attributes():
    rows = [
        {"cliente": "ana", "produto": "arroz", "segmento": "varejo", "valor": 10.0},
        {"cliente": "ana", "produto": "feijao", "segmento": "varejo", "valor": 5.0},
        {"cliente": "bia", "produto": "arroz", "segmento": "atacado", "valor": 30.0},
        {"cliente": "bia", "produto": "arroz", "segmento": "atacado", "valor": 30.0},
    ]
    g = tc.project(rows, nodes="cliente", via="produto")
    assert g.nodes["ana"] == {"segmento": "varejo", "valor_total": 15.0, "n_produto": 2}
    assert g.nodes["bia"] == {"segmento": "atacado", "valor_total": 60.0, "n_produto": 1}
    assert g.edges["ana", "bia"]["shared"] == 1  # a repeated purchase counts once
    flipped = tc.project(rows, nodes="produto", via="cliente")
    assert flipped.has_edge("arroz", "feijao")
    with pytest.raises(tc.TarecoError, match="no column 'loja'"):
        tc.project(rows, nodes="cliente", via="loja")


def test_tables_of_every_kind(tmp_path):
    path = tmp_path / "compras.csv"
    path.write_text(chr(10).join(["cliente;produto", "ana;arroz", "bia;arroz"]), encoding="utf-8")
    assert tc.project(str(path)).has_edge("ana", "bia")
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"cliente": ["ana", "bia", None], "produto": ["arroz", "arroz", "arroz"]})
    assert set(tc.project(df).edges) == {("ana", "bia")}
    with pytest.raises(tc.TarecoError):
        tc.project([("only-one-column",)])
    assert len(tc.project([])) == 0


def test_spark_like_table():
    class Row(tuple):
        def __new__(cls, **kw):
            r = super().__new__(cls, kw.values())
            r._f = list(kw)
            return r

        def asDict(self, recursive=False):
            return dict(zip(self._f, self))

    class SparkDF:
        schema = object()
        columns = ["account", "device"]

        def limit(self, n):
            return self

        def toLocalIterator(self):
            return iter([Row(account="a1", device="phone"), Row(account="a2", device="phone")])

    assert tc.project(SparkDF()).has_edge("a1", "a2")


def test_project_an_existing_two_sided_graph():
    g = tc.Graph()
    for person, item in PURCHASES:
        g.add_node(person, kind="person")
        g.add_node(item, kind="item")
        g.add_edge(person, item)
    people = g.project(lambda n, attrs: attrs["kind"] == "person")
    assert set(people.nodes) == {"ana", "bia", "caio", "davi"}
    assert people.edges["ana", "bia"]["weight"] == 2 and people.nodes["bia"]["n_items"] == 3
    assert people.nodes["ana"]["kind"] == "person"
    items = g.project(["rice", "beans", "coffee", "tea"], method="jaccard")
    assert items.has_edge("rice", "beans") and not items.has_edge("tea", "rice")


def test_projection_feeds_the_business_layer():
    rows = []
    for i in range(30):
        basket = ["bread", "milk", "eggs"] if i < 15 else ["beer", "chips", "salsa"]
        rows += [{"client": f"c{i}", "product": p, "region": "south" if i < 15 else "north"} for p in basket]
    g = tc.project(rows, nodes="client", via="product")
    text = str(g.explain())
    assert "It forms 2 groups" in text and "region: south in 100%" in text
