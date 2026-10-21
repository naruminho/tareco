"""Runs a real Jupyter kernel and checks what tareco puts in the cell outputs."""

import os

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*sources):
    nb = nbformat.v4.new_notebook()
    setup = f"import sys; sys.path.insert(0, {ROOT!r})\nimport tareco"
    nb.cells = [nbformat.v4.new_code_cell(setup)] + [nbformat.v4.new_code_cell(s) for s in sources]
    nbclient.NotebookClient(nb, timeout=120, kernel_name="python3",
                            resources={"metadata": {"path": ROOT}}).execute()
    return nb.cells[1:]


def html_outputs(cell):
    return [o["data"]["text/html"] for o in cell.outputs if "text/html" in o.get("data", {})]


def test_show_and_repr_render_inline_without_noise():
    show, last_line, big, spark_like = run(
        'g = tareco.Graph([("ana", "bia"), ("bia", "caio")])\ng.show(title="inline")',
        "g",
        "tareco.scale_free_graph(3000, 2, seed=1)",
        'tareco.show([{"origem": "a", "destino": "b"}])',
    )
    for cell in (show, last_line, big, spark_like):
        outputs = html_outputs(cell)
        assert len(outputs) == 1 and "<iframe srcdoc=" in outputs[0]
        assert not [o for o in cell.outputs if o.get("name") == "stderr"]
    assert "force-graph" in html_outputs(show)[0]
    assert "sigma" in html_outputs(big)[0]
    assert len(html_outputs(big)[0]) < 25e6
