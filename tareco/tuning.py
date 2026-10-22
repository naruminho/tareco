"""How sensitive the investigation tools are: thresholds, time windows and the weights of the work list.

Every tool takes its own arguments; ``tareco.settings`` changes the defaults
they fall back on, for everything at once:

    tareco.settings(split_limit=10_000, unusual_factor=20)   # from now on
    with tareco.settings(fast_within="24 hours"):            # only inside the block
        g.review()
    print(tareco.settings())                                 # what is set, and what it means
"""

from .errors import TarecoError

DEFAULTS = {
    "split_limit": None,        # the amount people stay under (None: any round number)
    "split_within": "7 days",   # how close in time the amounts of a pile are
    "split_count": 3,           # how many amounts make a pile (at least 5 without a limit)
    "split_margin": 0.1,        # how close under the limit counts: 0.1 is within 10%
    "unusual_factor": 10,       # how many times the sender's usual amount
    "unusual_history": 5,       # transfers a sender needs before it is judged
    "unusual_top": 0.05,        # only amounts among the largest 5% of the network
    "fast_within": "3 days",    # how fast money has to go out again
    "fast_share": 0.8,          # how much of what came in has to go out
    "fast_top": 0.1,            # only amounts among the largest 10% of the network
    "misfit_factor": 10,        # how many times above or below the neighbors' median
    "misfit_neighbors": 3,      # neighbors needed to judge a node
    "fan_min": 5,               # senders or receivers that make a fan-in, fan-out or relay
    "cycle_max": 4,             # longest loop looked for
    "near_hops": 2,             # steps from a watched node that count as close
    "shared_max": 10,           # identifiers shared by more nodes than this tie nobody
    "weights": {                # how much each kind of signal weighs in the work list
        "split": 3.0, "fast_pass": 2.5, "unusual_amount": 2.0, "cycle": 2.0, "chain": 2.0,
        "pass_through": 2.0, "fan_in": 2.0, "fan_out": 1.5, "misfit": 1.5, "near": 1.5, "shared": 1.0,
    },
    "repeat": 0.25,             # added per extra signal of a kind already counted
    "repeat_cap": 0.5,          # ... up to this much per kind: twenty loops are one story
}
SPANS = ("split_within", "fast_within")
SHARES = ("split_margin", "unusual_top", "fast_share", "fast_top")
COUNTS = ("split_count", "unusual_history", "misfit_neighbors", "fan_min", "cycle_max", "near_hops", "shared_max")

_current = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}


def setting(name, given=None):
    """``given`` when the caller passed one, else the current setting."""
    return _current[name] if given is None else given


class Settings(dict):
    """The current settings. As a ``with`` block, puts back what was there before on the way out."""

    def __init__(self, before):
        super().__init__({k: (dict(v) if isinstance(v, dict) else v) for k, v in _current.items()})
        self._before = before

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        _current.clear()
        _current.update(self._before)
        return False

    def __repr__(self):
        width = max(len(k) for k in self)
        lines = []
        for k, v in self.items():
            mark = "" if v == DEFAULTS[k] else "   (changed)"
            lines.append(f"{k:<{width}}  {v!r}{mark}")
        return "\n".join(lines)


def settings(reset=False, **changes):
    """Change the defaults of the investigation tools, or see them.

    ``tareco.settings(name=value, ...)`` changes them from now on; as a ``with``
    block, only inside it. ``tareco.settings()`` shows them, ``reset=True``
    puts every one back. ``weights={"split": 5}`` changes the weight of one kind
    of signal and keeps the others. The names (see ``tareco.tuning.DEFAULTS``):

    split_limit, split_within, split_count, split_margin
                    splits: the amount to stay under, the time window, how many
                    amounts make a pile, how close under the limit counts.
    unusual_factor, unusual_history, unusual_top
                    unusual amounts: times the usual amount, transfers needed to
                    judge, share of the largest amounts that can count.
    fast_within, fast_share, fast_top
                    fast moves: time window, share that has to go out again, share
                    of the largest amounts that can count.
    misfit_factor, misfit_neighbors
                    misfits: times above or below the neighbors, neighbors needed.
    fan_min, cycle_max, near_hops, shared_max
                    patterns: smallest fan, longest loop; closeness to a watch list;
                    identifiers shared by more nodes tie nobody.
    weights, repeat, repeat_cap
                    the work list: weight per kind of signal, and what each extra
                    signal of a kind adds, up to a cap.
    """
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _current.items()}
    unknown = [k for k in changes if k not in DEFAULTS]
    if unknown:
        raise TarecoError(f"no setting {unknown[0]!r}; settings are {list(DEFAULTS)}")
    for k, v in changes.items():
        _check(k, v)
    if reset:
        _current.clear()
        _current.update({k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()})
    for k, v in changes.items():
        if k == "weights":
            _current["weights"] = {**_current["weights"], **v}
        else:
            _current[k] = v
    return Settings(before)


def _check(name, value):
    from .indicators import _is_number, parse_span
    if name == "split_limit":
        if value is not None and (not _is_number(value) or value <= 0):
            raise TarecoError("split_limit must be a positive amount, or None for any round number")
    elif name in SPANS:
        parse_span(value)
    elif name in SHARES:
        if not _is_number(value) or not 0 < value <= 1:
            raise TarecoError(f"{name} must be a share between 0 and 1, like 0.1")
    elif name in COUNTS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise TarecoError(f"{name} must be a whole number of at least 1")
    elif name == "weights":
        if not isinstance(value, dict) or not all(_is_number(w) and w >= 0 for w in value.values()):
            raise TarecoError('weights must be a dict of kind to weight, like {"split": 5}')
    elif not _is_number(value) or value < 0:
        raise TarecoError(f"{name} must be a number of at least 0")
