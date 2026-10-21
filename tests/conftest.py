import os

# Tests check English text; the library would otherwise follow the machine's language.
os.environ.setdefault("TARECO_LANG", "en")
