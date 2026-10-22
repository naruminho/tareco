"""Back from the graph to your own records: the rows behind a link, the rows about a node."""

from .errors import TarecoError
from .io import (MAX_ROWS, SOURCE_COLUMNS, TARGET_COLUMNS, _is_dataframe, _is_polars, _is_spark,
                 _pick_column, iter_table)

JOIN_ABOVE = 2_000   # Spark: match more ids than this with a broadcast join instead of isin


class Rows(list):
    """Rows of a table, as dicts. ``to_pandas()`` makes a DataFrame of them."""

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame(list(self))

    def column(self, name):
        """The values of one column, like the transaction ids."""
        return [r.get(name) for r in self]

    def __repr__(self):
        if not self:
            return "(no rows)"
        shown = "\n".join(repr(r) for r in self[:10])
        return shown + (f"\n... {len(self) - 10:,} more" if len(self) > 10 else "")


def records(data, nodes, columns=None, max_rows=MAX_ROWS):
    """The rows of ``data`` that mention any of ``nodes``, in the table's own format.

    data        Spark DataFrame (filtered in the cluster, nothing is collected),
                pandas or polars DataFrame, CSV/Excel path or rows.
    nodes       one node or several: what ``similar_to``, ``near`` or any finding
                pointed at.
    columns     the columns to look in (default: the source and target columns,
                found as when loading a graph).

    >>> tareco.records(spark.table("statements"), found.nodes, columns=["account", "counterparty"])
    """
    wanted = list(nodes) if isinstance(nodes, (list, tuple, set, frozenset)) else [nodes]
    if _is_spark(data):
        return _spark_records(data, wanted, _columns(list(data.columns), columns))
    if _is_polars(data):
        import polars as pl
        cond = None
        for c in _columns(list(data.columns), columns):
            here = pl.col(c).is_in(wanted)
            cond = here if cond is None else (cond | here)
        return data.filter(cond)
    if _is_dataframe(data):
        mask = None
        for c in _columns(list(data.columns), columns):
            here = data[c].isin(wanted)
            mask = here if mask is None else (mask | here)
        return data[mask]
    found, rows = iter_table(data, max_rows)
    look = _columns(found, columns)
    keys = set(wanted)
    return Rows(r for r in rows if any(r.get(c) in keys for c in look))


def _columns(found, columns):
    if columns is not None:
        columns = [columns] if isinstance(columns, str) else list(columns)
        missing = [c for c in columns if c not in found]
        if missing:
            raise TarecoError(f"no column {missing[0]!r}; columns are {found}")
        return columns
    s = _pick_column(found, None, SOURCE_COLUMNS, "source")
    t = _pick_column(found, None, TARGET_COLUMNS, "target", exclude=s)
    return [s, t]


def _spark_records(df, wanted, columns):
    from pyspark.sql import functions as F
    if len(wanted) <= JOIN_ABOVE:
        cond = None
        for c in columns:
            here = F.col(c).isin(wanted)
            cond = here if cond is None else (cond | here)
        return df.filter(cond)
    ids = df.sparkSession.createDataFrame([(v,) for v in wanted], ["__tareco_node"])
    parts = [df.join(F.broadcast(ids), df[c] == ids["__tareco_node"], "left_semi") for c in columns]
    out = parts[0]
    for part in parts[1:]:
        out = out.unionByName(part)
    return out.distinct() if len(parts) > 1 else out
