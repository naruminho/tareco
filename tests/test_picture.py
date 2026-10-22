"""Still pictures for slides and e-mails: SVG with nothing installed, PNG with Pillow."""

import os

import pytest

import tareco as tc

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")


def friends():
    return tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))


def test_svg(tmp_path):
    g = friends()
    svg = g.to_svg(color="city", title="Friends <by city>")
    assert svg.startswith("<svg") and svg.count("<circle") >= 16
    assert "Friends &lt;by city&gt;" in svg and ">São Paulo</text>" in svg
    assert svg == g.to_svg(color="city", title="Friends <by city>")  # same graph, same picture
    path = g.save(tmp_path / "friends.svg", color="city")
    assert path.endswith("friends.svg") and open(path, encoding="utf-8").read().startswith("<svg")
    arrows = tc.Graph([("a", "b"), ("b", "c")], directed=True).to_svg()
    assert 'marker-end="url(#arrow)"' in arrows
    assert tc.Graph().to_svg().startswith("<svg")
    with pytest.raises(tc.TarecoError, match="theme"):
        g.to_svg(theme="pink")


def test_png(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    path = friends().save(tmp_path / "friends.png", width=800, height=500, theme="dark")
    with Image.open(path) as image:
        assert image.size == (800, 500)
        assert image.getpixel((5, 5)) == (11, 16, 32)  # the dark background


def test_png_without_pillow(tmp_path, monkeypatch):
    import builtins
    real = builtins.__import__

    def no_pil(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError(name)
        return real(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_pil)
    with pytest.raises(tc.TarecoError, match="pip install pillow"):
        friends().save(tmp_path / "x.png")
