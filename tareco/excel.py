"""Reading .xlsx files with the standard library: an Excel file is a zip of XML."""

import datetime as dt
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from .errors import TarecoError

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DATE_FORMATS = set(range(14, 23)) | {45, 46, 47}  # Excel's built-in date and time formats
EPOCH = dt.datetime(1899, 12, 30)


def read_excel(path, sheet=None):
    """Rows of one sheet as dicts keyed by the header row (the first non-empty row).

    ``sheet`` is a sheet name or position (default: the first sheet). Dates
    come back as datetimes, whole numbers as ints.
    """
    try:
        book = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise TarecoError(f"cannot open {path} as an Excel .xlsx file ({e})") from None
    with book:
        names = set(book.namelist())
        sheets = _sheets(book)
        if not sheets:
            raise TarecoError(f"{path} has no sheets")
        if sheet is None:
            title, target = sheets[0]
        elif isinstance(sheet, int):
            try:
                title, target = sheets[sheet]
            except IndexError:
                raise TarecoError(f"{path} has {len(sheets)} sheets; there is no sheet {sheet}") from None
        else:
            match = [s for s in sheets if s[0] == sheet]
            if not match:
                raise TarecoError(f"no sheet {sheet!r} in {path}; sheets are {[s[0] for s in sheets]}")
            title, target = match[0]
        shared = _shared_strings(book) if "xl/sharedStrings.xml" in names else []
        dates = _date_styles(book) if "xl/styles.xml" in names else set()
        grid = _cells(book.read(target), shared, dates)
    rows = [r for r in grid if any(v is not None for v in r)]
    if not rows:
        return []
    header = [str(h).strip() if h is not None else f"column{i + 1}" for i, h in enumerate(rows[0])]
    out = []
    for r in rows[1:]:
        r = list(r) + [None] * (len(header) - len(r))
        out.append(dict(zip(header, r)))
    return out


def _sheets(book):
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(PKG + "Relationship")}
    out = []
    for s in workbook.iter(MAIN + "sheet"):
        target = targets.get(s.get(REL + "id"), "")
        target = target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
        out.append((s.get("name"), posixpath.normpath(target)))
    return out


def _shared_strings(book):
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(MAIN + "t")) for si in root.iter(MAIN + "si")]


def _date_styles(book):
    """Indexes of cell styles that display a date or time."""
    root = ET.fromstring(book.read("xl/styles.xml"))
    custom = {}
    fmts = root.find(MAIN + "numFmts")
    if fmts is not None:
        for f in fmts.iter(MAIN + "numFmt"):
            code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", f.get("formatCode", "")).lower()
            custom[int(f.get("numFmtId"))] = bool(re.search(r"[dmyhs]", code)) and "0" not in code
    xfs = root.find(MAIN + "cellXfs")
    out = set()
    if xfs is not None:
        for i, xf in enumerate(xfs.iter(MAIN + "xf")):
            fid = int(xf.get("numFmtId", 0))
            if fid in DATE_FORMATS or custom.get(fid):
                out.add(i)
    return out


def _cells(xml, shared, dates):
    root = ET.fromstring(xml)
    grid = []
    for row in root.iter(MAIN + "row"):
        values = {}
        for c in row.iter(MAIN + "c"):
            col = _column(c.get("r", ""), len(values))
            values[col] = _value(c, shared, dates)
        width = max(values) + 1 if values else 0
        grid.append([values.get(i) for i in range(width)])
    return grid


def _column(ref, fallback):
    letters = re.match(r"[A-Z]+", ref or "")
    if not letters:
        return fallback
    n = 0
    for ch in letters.group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _value(c, shared, dates):
    kind = c.get("t", "n")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in c.iter(MAIN + "t")) or None
    v = c.find(MAIN + "v")
    if v is None or v.text is None:
        return None
    text = v.text
    if kind == "s":
        value = shared[int(text)]
        return value if value != "" else None
    if kind == "b":
        return text == "1"
    if kind in ("str", "e"):
        return None if kind == "e" else text
    number = float(text)
    if c.get("s") is not None and int(c.get("s")) in dates:
        moment = EPOCH + dt.timedelta(days=number)
        return moment.replace(microsecond=0)
    return int(number) if number.is_integer() else number
