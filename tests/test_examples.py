"""The recipes in examples/receitas run, find what they are about, and say it the same way every time."""

import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tareco import i18n

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

# what each recipe is about: if one of these goes missing, the recipe stopped telling its story
FINDS = {
    "01-amigos/amigos.py": [
        "Grupo 1: Ana, Bia, Caio, Duda",
        "Iris é uma ponte entre grupos",
        "Com quem Iris mais conversa: [('João', 35)",
    ],
    "02-transacoes/transacoes.py": [
        "r1, r2, r3 e r4 formam um ciclo",
        "x01 recebe de 30 nós, 30 deles não enviam para mais ninguém",
        "Uma cadeia de 4 intermediários: x01 para x02 para y1 para y2 para y3 para exterior",
        "31 nós novos apareceram em 2026-04",
        "x01 apareceu em 2026-04 já com 30 conexões",
        "y3 -> exterior",
    ],
    "03-suprimentos/suprimentos.py": [
        "A rede entrega até 2040 unidades por semana",
        "Sem a Fabrica SP, a rede perde 740 unidades",
        "Mais barato de Fornecedor A até Loja 07 (custo 17)",
    ],
    "04-compras/compras.py": [
        "segmento: estudante em 97%", "segmento: fitness em 100%",
        "segmento: churrasco em 100%", "segmento: familia em 100%",
        "Quem compra fraldas também compra: biscoito, leite, lenco umedecido",
    ],
    "05-emails/emails.py": [
        "Financeiro    8 pessoas, 91% das conversas dentro da área",
        "Paulo Mar2 é uma ponte entre grupos",
        "Um grupo novo de 7 nós se formou em 2026-04",
        "a notícia pode ter chegado a 58 pessoas",
    ],
    "06-software/software.py": [
        "Dependência circular: config -> cache -> config",
        "Se 'utils' quebrar, 21 pacotes quebram junto",
    ],
    "07-surto/surto.py": [
        "158 pessoas podem ter sido expostas a partir de P017",
        "P077 saltou para 42 conexões em 2026-05-10",
        "Um grupo novo de 28 nós se formou em 2026-05-10",
    ],
    "08-metro/metro.py": [
        "Aeroporto -> Vila Nova -> Centro -> Catedral -> Estadio -> Lagoa (28 minutos)",
        "Estações por onde mais caminhos passam: Centro",
        "Sem a Centro não há como ir do Aeroporto à Lagoa",
    ],
}

# noise that once crept into the output
NOT = {
    "04-compras/compras.py": ["n_produto", "conectados entre si"],
    "05-emails/emails.py": ["area = ", "total de count", "se fundiram", "se dividiu"],
    "07-surto/surto.py": ["nós novos apareceram"],
}


@pytest.fixture(scope="module")
def copy(tmp_path_factory):
    """The examples folder in a temporary place, so the pages the recipes save do not land in the repository."""
    where = tmp_path_factory.mktemp("examples") / "examples"
    shutil.copytree(EXAMPLES, where, ignore=shutil.ignore_patterns("saida", "__pycache__"))
    return where


def run(path):
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            runpy.run_path(str(path), run_name="__main__")
    finally:
        i18n.set_language(None)  # the recipes switch to Portuguese
    return out.getvalue()


@pytest.mark.parametrize("recipe", sorted(FINDS))
def test_recipe_tells_its_story(copy, recipe):
    text = run(copy / "receitas" / recipe)
    for phrase in FINDS[recipe]:
        assert phrase in text, f"{recipe} no longer says: {phrase}\n\n{text}"
    for phrase in NOT.get(recipe, []):
        assert phrase not in text, f"{recipe} says: {phrase}"
    pages = list((copy / "receitas" / recipe).parent.glob("saida/*.html"))
    assert pages and all(p.stat().st_size > 10_000 for p in pages)


def test_every_recipe_has_a_readme_and_is_listed():
    index = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    folders = sorted(p for p in (EXAMPLES / "receitas").iterdir() if p.is_dir())
    assert len(folders) == len(FINDS)
    for folder in folders:
        assert (folder / "README.md").exists(), folder.name
        assert f"receitas/{folder.name}/" in index, folder.name


def test_same_output_whatever_the_hash_seed(copy):
    """Sets iterate in a different order in every Python process; the text must not depend on it."""
    recipe = copy / "receitas" / "02-transacoes" / "transacoes.py"
    outputs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
        done = subprocess.run([sys.executable, str(recipe)], env=env, capture_output=True, timeout=300)
        assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
        outputs.append(done.stdout.decode("utf-8").replace("\r\n", "\n"))
    assert outputs[0] == outputs[1]
