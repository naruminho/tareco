"""The recipes in examples/recipes run, find what they are about, and say it the same way every time."""

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
    "01-friends/friends.py": [
        "Group 1: Ana, Bia, Caio, Duda",
        "Iris is a bridge between groups",
        "The strongest connection is Ana and Bia (42)",  # messages became the weight on its own
        "Who Iris talks to most: [('João', 35)",
    ],
    "02-transfers/transfers.py": [
        "r1, r2, r3 and r4 form a loop",
        "x01 receives from 30 nodes, 30 of which send to nobody else",
        "A chain of 4 intermediaries: x01 to x02 to y1 to y2 to y3 to abroad",
        "31 new nodes showed up in 2026-04",
        "x01 appeared in 2026-04 with 30 connections at once",
        "A new group of 6 nodes formed in 2026-05",
        "y3 -> abroad",
    ],
    "03-supply-chain/supply_chain.py": [
        "The network delivers up to 2040 units a week",
        "Without Factory East, the network loses 740 units",
        "Cheapest from Supplier A to Store 07 (cost 17)",
    ],
    "04-shopping/shopping.py": [
        "segment: student in 97%", "segment: fitness in 100%",
        "segment: barbecue in 100%", "segment: family in 100%",
        "Who buys diapers also buys: cookies, milk, wet wipes",
    ],
    "05-email/emails.py": [
        "Finance       8 people, 91% of conversations inside",
        "Paulo Mar2 is a bridge between groups",
        "A new group of 7 nodes formed in 2026-04",
        "the news could have reached 58 people",
        "What changed\n- From 52 to 59 nodes (+7)",
    ],
    "06-dependencies/dependencies.py": [
        "Circular dependency: config -> cache -> config",
        "If 'utils' breaks, 21 packages break with it",
    ],
    "07-outbreak/outbreak.py": [
        "158 people may have been exposed, starting from P017",
        "P077 jumped to 42 connections in 2026-05-10",
        "A new group of 28 nodes formed in 2026-05-10",
    ],
    "09-statements/statements.py": [
        "Links: 7,303 transfer and 342 uses.",
        "4 account nodes share dev-77 (device).",
        "a017 sent 8 transfers just under 10,000 within 5 days",
        "a142 sent 7 transfers just under 10,000 within 3 days",
        "a055 sent 85,000 to ART-DEALER-W on 2026-03-14",
        "Worth a look\n1. a023 (score ",
        "a023 received 40,493 and passed on 41,746 within 3 days",
        "a181 to a023 to PI-ACC-8: 2 transfers from 2026-02-20 to 2026-02-23",
        "a017, a023, a142, a199 (through dev-77)",
        "1. E1 (score ",
        "a023 has occupation cleaner, but 100% of the 5 nodes it deals with have executive.",
        "a142 is 2 steps from a017, through dev-77 (device).",
        "It shares dev-77 (device) with a017, a142 and a199.",
        "Most like a017\n- a142 (",
        "Sent to Palm Isles by: a023, a017, a142, a120",
        "Transactions to review: T009037, T009038",
    ],
    "08-subway/subway.py": [
        "Airport -> New Town -> Central -> Cathedral -> Stadium -> Lake (28 minutes)",
        "Stations most paths go through: Central",
        "Without Central there is no way from Airport to Lake",
    ],
}

# noise that once crept into the output
NOT = {
    "04-shopping/shopping.py": ["n_product", "all connected to each other"],
    "05-email/emails.py": ["department = ", "total count", "merged", "split"],
    "07-outbreak/outbreak.py": ["new nodes showed up", "A new group of 5", "A new group of 6", "A new group of 7"],
    "09-statements/statements.py": ["SHOP-04 has", "receives from 171 nodes", "and and", "a185 ("],
}


@pytest.fixture(scope="module")
def copy(tmp_path_factory):
    """The examples folder in a temporary place, so the pages the recipes save do not land in the repository."""
    where = tmp_path_factory.mktemp("examples") / "examples"
    shutil.copytree(EXAMPLES, where, ignore=shutil.ignore_patterns("out", "__pycache__"))
    return where


def run(path):
    out = io.StringIO()
    i18n.set_language("en")
    try:
        with contextlib.redirect_stdout(out):
            runpy.run_path(str(path), run_name="__main__")
    finally:
        i18n.set_language(None)
    return out.getvalue()


@pytest.mark.parametrize("recipe", sorted(FINDS))
def test_recipe_tells_its_story(copy, recipe):
    text = run(copy / "recipes" / recipe)
    for phrase in FINDS[recipe]:
        assert phrase in text, f"{recipe} no longer says: {phrase}\n\n{text}"
    for phrase in NOT.get(recipe, []):
        assert phrase not in text, f"{recipe} says: {phrase}"
    pages = list((copy / "recipes" / recipe).parent.glob("out/*.html"))
    assert pages and all(p.stat().st_size > 10_000 for p in pages)
    for picture in (copy / "recipes" / recipe).parent.glob("out/*.svg"):
        assert picture.read_text(encoding="utf-8").startswith("<svg")


def test_every_recipe_has_a_readme_and_is_listed():
    index = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    folders = sorted(p for p in (EXAMPLES / "recipes").iterdir() if p.is_dir() and p.name[0].isdigit())
    assert len(folders) == len(FINDS)
    for folder in folders:
        assert (folder / "README.md").exists(), folder.name
        assert f"recipes/{folder.name}/" in index, folder.name


def test_the_data_is_what_make_data_makes(tmp_path):
    """make_data.py really is how the data was made (the Excel file needs openpyxl, so it is left out)."""
    pytest.importorskip("openpyxl")
    script = tmp_path / "make_data.py"
    shutil.copy(EXAMPLES / "recipes" / "make_data.py", script)
    done = subprocess.run([sys.executable, str(script)], capture_output=True, timeout=300)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    made = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.csv"))
    assert len(made) == 11
    for path in made:
        # git may turn the line endings into the local ones
        same = [p.read_bytes().replace(b"\r\n", b"\n") for p in (tmp_path / path, EXAMPLES / "recipes" / path)]
        assert same[0] == same[1], path


def test_same_output_whatever_the_hash_seed(copy):
    """Sets iterate in a different order in every Python process; the text must not depend on it."""
    outputs = []
    for seed, recipe in (("1", "02-transfers/transfers.py"), ("2", "02-transfers/transfers.py"),
                         ("1", "09-statements/statements.py"), ("2", "09-statements/statements.py")):
        recipe = copy / "recipes" / recipe
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8",
                   TARECO_LANG="en")
        done = subprocess.run([sys.executable, str(recipe)], env=env, capture_output=True, timeout=300)
        assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
        outputs.append(done.stdout.decode("utf-8").replace("\r\n", "\n"))
    assert outputs[0] == outputs[1] and outputs[2] == outputs[3]
