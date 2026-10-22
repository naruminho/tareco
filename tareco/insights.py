"""The business layer: what characterizes each group, and what a network shows, in plain words."""

import math
from collections import Counter

from . import i18n
from .errors import TarecoError

MIN_GROUP_FOR_TRAITS = 3
CATEGORY_LIMIT = 30         # more distinct values than this reads as an id, not a category
NUMERIC_DISTINCT = 12       # integers with more distinct values than this are treated as numbers
COUNT_PREFIXES = ("n_", "num", "qtd", "quant", "count", "total")  # counts are numbers, not categories


class Trait:
    """One thing that sets a group apart, e.g. 80% of its nodes are in Recife."""

    __slots__ = ("attribute", "kind", "value", "group_value", "overall_value", "score", "text")

    def __init__(self, attribute, kind, value, group_value, overall_value, score, text):
        self.attribute = attribute
        self.kind = kind
        self.value = value
        self.group_value = group_value
        self.overall_value = overall_value
        self.score = score
        self.text = text

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    def short(self, lang):
        """A few words for tight spots like a legend: "Recife 75%" or "age higher"."""
        if self.kind == "category":
            return f"{self.value} {i18n.percent(self.group_value, lang)}"
        key = "short_higher" if self.group_value > self.overall_value else "short_lower"
        return i18n.text(lang, key, attr=self.attribute)

    def __repr__(self):
        return self.text


class GroupProfile:
    """Who is in a group and what distinguishes it from the rest of the network."""

    def __init__(self, label, name, members, share, key_members, traits, inward, linked, lang):
        self.label = label
        self.name = name
        self.members = members
        self.size = len(members)
        self.share = share
        self.key_members = key_members
        self.traits = traits
        self.inward = inward
        self.linked = linked
        self._lang = lang

    def summary(self, limit=2):
        """Short text: the strongest traits, or nothing."""
        return "; ".join(t.text for t in self.traits[:limit])

    def to_dict(self):
        return {
            "label": self.label, "name": self.name, "size": self.size, "share": self.share,
            "key_members": list(self.key_members), "traits": [t.to_dict() for t in self.traits],
            "inward": self.inward, "linked": self.linked,
        }

    def __repr__(self):
        lang = self._lang
        lines = [f"{self.name} - " + i18n.text(lang, "profile_size", size=i18n.number(self.size, lang),
                                                 pct=i18n.percent(self.share, lang))]
        lines += [f"  {t.text}" for t in self.traits]
        if self.key_members:
            lines.append("  " + i18n.text(lang, "profile_members",
                                          members=i18n.join(self.key_members, lang)))
        if self.inward is not None:
            lines.append("  " + i18n.text(lang, "profile_inward", pct=i18n.percent(self.inward, lang)))
        if self.linked is not None:
            lines.append("  " + i18n.text(lang, "profile_link", name=self.linked))
        return "\n".join(lines)


class Profiles(list):
    """List of GroupProfile, biggest group first."""

    def __repr__(self):
        return "\n\n".join(repr(p) for p in self)

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"group": p.name, "size": p.size, "share": p.share,
                              "traits": p.summary(limit=10), "key_members": ", ".join(map(str, p.key_members)),
                              "inward": p.inward, "linked": p.linked} for p in self])


class Finding:
    """One plain-language statement, with the nodes it is about (and the rows behind it, if kept)."""

    __slots__ = ("kind", "text", "nodes", "group", "period", "rows")

    def __init__(self, kind, text, nodes=(), group=None, period=None, rows=None):
        self.kind = kind
        self.text = text
        self.nodes = list(nodes)
        self.group = group
        self.period = period
        self.rows = rows if rows is not None else []

    def to_dict(self):
        return {"kind": self.kind, "text": self.text, "nodes": self.nodes, "group": self.group,
                "period": self.period}

    def __repr__(self):
        return self.text


class Explanation:
    """What a network shows. Print it, iterate its findings, or render it in a notebook."""

    def __init__(self, findings, profiles, lang, title=None):
        self.findings = findings
        self.profiles = profiles
        self.lang = lang
        self.title = title if title is not None else i18n.text(lang, "title")

    def __iter__(self):
        return iter(self.findings)

    def __len__(self):
        return len(self.findings)

    def to_dict(self):
        return [f.to_dict() for f in self.findings]

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"kind": f.kind, "text": f.text, "group": f.group, "nodes": list(f.nodes)}
                             for f in self.findings])

    def __str__(self):
        lines = [self.title]
        lines += [f"- {f.text}" for f in self.findings]
        return "\n".join(lines)

    __repr__ = __str__

    def _repr_markdown_(self):
        lines = [f"**{self.title}**", ""]
        lines += [f"- {f.text}" for f in self.findings]
        return "\n".join(lines)


# ------------------------------------------------------------------ partitions

def partition(g, groups=None, lang="en", communities=None):
    """``[(label, name, members)]``, biggest first, for the ways a user can say "groups"."""
    word = i18n.text(lang, "group")
    if groups is None:
        comms = communities if communities is not None else g.communities()
        return [(str(i + 1), f"{word} {i + 1}", set(c)) for i, c in enumerate(comms)]
    if isinstance(groups, str):
        buckets = {}
        for n, attrs in g.nodes.items():
            value = attrs.get(groups)
            if value is not None:
                buckets.setdefault(str(value), set()).add(n)
        ordered = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        return [(label, label, members) for label, members in ordered]
    if isinstance(groups, dict):
        buckets = {}
        for n, label in groups.items():
            if n in g and label is not None:
                buckets.setdefault(str(label), set()).add(n)
        ordered = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        return [(label, f"{word} {label}", members) for label, members in ordered]
    ordered = sorted((set(c) for c in groups), key=len, reverse=True)
    return [(str(i + 1), f"{word} {i + 1}", members) for i, members in enumerate(ordered)]


# -------------------------------------------------------------------- profiles

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _describe_attributes(g, attrs, skip=()):
    """For each usable attribute: its kind and the network-wide baseline."""
    nodes = list(g)
    names = attrs if attrs is not None else list(dict.fromkeys(k for n in nodes for k in g.nodes[n]))
    out = {}
    for name in names:
        if name in skip or name == "kind":
            continue
        values = [g.nodes[n].get(name) for n in nodes]
        present = [v for v in values if v is not None and not (isinstance(v, float) and v != v)]
        # with several kinds of node, only the kinds that have the attribute count (accounts
        # have an income, devices do not)
        carriers = {g.nodes[n].get("kind") for n, v in zip(nodes, values)
                    if v is not None and not (isinstance(v, float) and v != v)}
        pool = len(nodes) if carriers == {None} else sum(1 for n in nodes if g.nodes[n].get("kind") in carriers)
        if len(present) < max(3, 0.5 * pool):
            continue
        countish = str(name).lower().startswith(COUNT_PREFIXES)
        if all(_is_number(v) for v in present) and (
                countish or any(isinstance(v, float) for v in present) or len(set(present)) > NUMERIC_DISTINCT):
            ordered = sorted(present)
            mean = sum(ordered) / len(ordered)
            var = sum((v - mean) ** 2 for v in ordered) / len(ordered)
            out[name] = ("number", {"median": _median(ordered), "mean": mean, "std": math.sqrt(var)})
            continue
        keys = [_key(v) for v in present]
        counts = Counter(keys)
        if len(counts) < 2 or len(counts) > CATEGORY_LIMIT or len(counts) > 0.6 * len(present):
            continue
        out[name] = ("category", {k: c / len(keys) for k, c in counts.items()})
    return out


def _key(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        return ", ".join(map(str, value))
    return str(value)


def _median(ordered):
    k = len(ordered)
    return ordered[k // 2] if k % 2 else (ordered[k // 2 - 1] + ordered[k // 2]) / 2


def _traits(g, members, described, lang, top):
    traits = []
    for name, (kind, base) in described.items():
        values = [g.nodes[n].get(name) for n in members]
        present = [v for v in values if v is not None and not (isinstance(v, float) and v != v)]
        if len(present) < MIN_GROUP_FOR_TRAITS:
            continue
        if kind == "category":
            counts = Counter(_key(v) for v in present)
            best = None
            for value, c in counts.items():
                share = c / len(present)
                overall = base.get(value, 0.0)
                if c < 2 or overall <= 0:
                    continue
                lift = share / overall
                if lift < 1.25 or not (share >= 0.5 or (share >= 0.3 and lift >= 2)):
                    continue
                score = share * math.log2(lift)
                if best is None or score > best[0]:
                    best = (score, value, share, overall)
            if best:
                score, value, share, overall = best
                text = i18n.text(lang, "trait_category", attr=name, value=value,
                                 share=i18n.percent(share, lang), overall=i18n.percent(overall, lang))
                traits.append(Trait(name, "category", value, share, overall, score, text))
        else:
            ordered = sorted(present)
            med, overall = _median(ordered), base["median"]
            mean = sum(ordered) / len(ordered)
            score = 0.0
            key = None
            if med > 0 and overall > 0:
                ratio = med / overall
                if ratio >= 1.5:
                    key, score = "trait_higher", math.log2(ratio) * 0.8
                elif ratio <= 1 / 1.5:
                    key, score = "trait_lower", math.log2(1 / ratio) * 0.8
            if key is None and base["std"] > 0:
                d = (mean - base["mean"]) / base["std"]
                if abs(d) >= 0.8:
                    key, score = ("trait_higher" if d > 0 else "trait_lower"), abs(d) / 2
            if key:
                text = i18n.text(lang, key, attr=name, group=i18n.number(med, lang),
                                 overall=i18n.number(overall, lang))
                traits.append(Trait(name, "number", None, med, overall, score, text))
    traits.sort(key=lambda t: -t.score)
    return traits[:top]


def _edge_mix(g, group_of):
    """Per group: share of its connections that stay inside, and the group it links to most."""
    inside, total, links = Counter(), Counter(), Counter()
    for u, v, _ in g._edge_triples():
        if u == v:
            continue
        a, b = group_of.get(u), group_of.get(v)
        if a is None or b is None:
            continue
        total[a] += 1
        total[b] += 1
        if a == b:
            inside[a] += 2
        else:
            links[(a, b)] += 1
            links[(b, a)] += 1
    linked = {}
    for (a, b), c in links.items():
        if a not in linked or c > linked[a][1]:
            linked[a] = (b, c)
    return inside, total, linked


def profile(g, groups=None, attrs=None, top=3, lang=None, label=None, communities=None, pagerank=None):
    """What characterizes each group of nodes, compared with the whole network.

    groups      None (communities), an attribute name, a {node: group} dict or
                a list of node sets.
    attrs       attributes to consider (default: every node attribute that looks
                like a category or a number; ids and names are skipped).
    top         most traits per group.
    label       attribute used to name nodes in the text.
    """
    lang = i18n.get_language(lang)
    parts = partition(g, groups, lang, communities)
    described = _describe_attributes(g, attrs, skip=(groups,) if isinstance(groups, str) else ())
    rank = pagerank if pagerank is not None else (g.pagerank() if len(g) else {})
    group_of = {n: label_ for label_, _, members in parts for n in members}
    names = {label_: name for label_, name, _ in parts}
    inside, total, linked = _edge_mix(g, group_of)
    n_all = len(g) or 1
    result = Profiles()
    for label_, name, members in parts:
        key_members = sorted(members, key=lambda x: -rank.get(x, 0))[:3]
        traits = _traits(g, members, described, lang, top) if len(members) >= MIN_GROUP_FOR_TRAITS else []
        inward = inside[label_] / total[label_] if total[label_] else None
        other = linked.get(label_)
        result.append(GroupProfile(label_, name, members, len(members) / n_all,
                                   [_name(g, x, label) for x in key_members], traits, inward,
                                   names[other[0]] if other else None, lang))
    return result


def _name(g, node, label):
    if label is not None:
        value = g.nodes[node].get(label)
        if value is not None:
            return str(value)
    return str(node)


# --------------------------------------------------------------------- explain

def explain(g, groups=None, lang=None, top=5, label=None, weight="weight",
            communities=None, pagerank=None):
    """The main facts about a network, in plain language.

    Returns an Explanation: print it, iterate its findings (each has ``text``
    and the ``nodes`` it is about) or let a notebook render it.
    """
    lang = i18n.get_language(lang)
    T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
    num = lambda v: i18n.number(v, lang)  # noqa: E731
    pct = lambda s: i18n.percent(s, lang)  # noqa: E731
    name = lambda node: _name(g, node, label)  # noqa: E731
    findings = []
    n, m = len(g), g.edge_count
    if n == 0:
        return Explanation(findings, Profiles(), lang)

    degree = g.degree()
    avg = sum(degree.values()) / n
    findings.append(Finding("overview", T("overview_directed" if g.directed else "overview",
                                          n=num(n), m=num(m), avg=num(avg))))
    kinds = g.kinds()
    if len(kinds["links"]) >= 2 or len(kinds["nodes"]) >= 2:
        def listed(counts):
            return i18n.join([f"{num(c)} {k}" for k, c in sorted(counts.items(), key=lambda kv: -kv[1])], lang)
        findings.append(Finding("kinds", T("kinds", links=listed(kinds["links"]) or num(m),
                                           nodes=listed(kinds["nodes"]) or num(n))))

    comps = g.components()
    isolated = [x for x in g if degree[x] == 0]
    if len(comps) == 1:
        findings.append(Finding("connected", T("connected")))
    else:
        findings.append(Finding("parts", T("parts", c=num(len(comps)), pct=pct(len(comps[0]) / n))))
        if isolated:
            key = "isolated_one" if len(isolated) == 1 else "isolated"
            findings.append(Finding("isolated", T(key, k=num(len(isolated))), isolated))
        small = [c for c in comps[1:] if 2 <= len(c) <= 3]
        if small:
            key = "small_parts_one" if len(small) == 1 else "small_parts"
            findings.append(Finding("small_parts", T(key, k=num(len(small))),
                                    [x for c in small for x in c]))

    rank = pagerank if pagerank is not None else g.pagerank()
    if groups is None and communities is None and m:
        communities = g.communities()
    profiles = profile(g, groups, top=3, lang=lang, label=label, communities=communities, pagerank=rank) \
        if m or groups is not None else Profiles()
    sized = [p for p in profiles if p.size >= 2]
    group_of = {x: p.label for p in profiles for x in p.members}
    names = {p.label: p.name for p in profiles}

    clear = False
    if len(sized) >= 2:
        if groups is None:
            clear = g.modularity([p.members for p in profiles]) >= 0.3
        else:
            clear = True
    if clear:
        kept = sum(1 for u, v, _ in g._edge_triples()
                   if u != v and group_of.get(u) is not None and group_of.get(u) == group_of.get(v))
        loops = sum(1 for u, v, _ in g._edge_triples() if u == v)
        inside = kept / max(1, m - loops)
        if inside >= 0.5:
            findings.append(Finding("groups", T("groups", k=num(len(sized)), pct=pct(inside))))
        else:
            findings.append(Finding("groups", T("groups_loose", k=num(len(sized)), pct=pct(1 - inside))))
        for p in [p for p in profiles if p.size >= MIN_GROUP_FOR_TRAITS][:top]:
            traits = p.summary()
            findings.append(Finding("group", T("group_line", name=p.name, size=num(p.size),
                                               pct=pct(p.share), traits=(": " + traits) if traits else "",
                                               members=i18n.join(p.key_members, lang)),
                                    sorted(p.members, key=lambda x: -rank.get(x, 0)), p.label))
    elif m:
        findings.append(Finding("no_groups", T("no_groups")))

    if m:
        central = sorted(g, key=lambda x: -rank.get(x, 0))[:3]
        findings.append(Finding("central", T("central", names=i18n.join([name(x) for x in central], lang)),
                                central))

    if clear:
        findings += _brokers(g, group_of, names, degree, lang, name)
    findings += _hubs(g, degree, lang, name)
    if m:
        findings += _pattern_findings(g, lang, label, weight)
        findings += _behavior_findings(g, lang, label)
    if g.directed and m:
        findings += _reciprocity(g, lang)
    findings += _weights(g, weight, lang, name)
    return Explanation(findings, profiles, lang)


# most telling first; explain() keeps a few, patterns() has them all
PATTERN_PRIORITY = ("cycle", "pass_through", "fan_in", "fan_out", "chain", "shared", "back_and_forth",
                    "clique", "star")


def _behavior_findings(g, lang, label):
    """Amounts piling under a limit, transfers far above the usual, nodes far unlike their neighbors."""
    from .indicators import attribute_kinds, fast_moves, misfits, splits, unusual_amounts
    out = []
    if g.attrs.get("kept"):
        for look in (splits, fast_moves, unusual_amounts):
            try:
                found = look(g, lang=lang, label=label)
            except TarecoError:
                continue  # no dates, or no amounts
            out += [Finding(p.kind, p.text, p.nodes, rows=p.rows) for p in found[:2]]
    numbers = [a for a, k in attribute_kinds(g).items() if k == "number"]
    if numbers:
        out += [Finding(p.kind, p.text, p.nodes)
                for p in misfits(g, attrs=numbers, factor=20, lang=lang, label=label, limit=2)]
    return out


def density(g):
    from .algorithms.structure import density as d
    return d(g)


def found_weight(g, weight):
    from .graph import _resolve_weight
    return _resolve_weight(g, weight)


def _pattern_findings(g, lang, label, weight, per_kind=2, total=6):
    from .patterns import Patterns, find_patterns
    every = find_patterns(g, lang=lang, limit=200, weight=weight, label=label)  # shared with review()
    found = Patterns(p for kind in dict.fromkeys(p.kind for p in every) for p in every.of(kind)[:per_kind])
    w = found_weight(g, weight)
    weights = sorted(d.get(w, 0) for _, _, d in g._edge_triples() if isinstance(d.get(w), (int, float)))
    typical = weights[len(weights) // 2] if weights else 0
    dense = density(g) >= 0.15  # in dense networks cliques are everywhere and say little
    out = []
    for kind in PATTERN_PRIORITY:
        same = found.of(kind)
        if kind == "clique":
            kept = []
            for p in ([] if dense else same):
                if all(len(set(p.nodes) & set(q.nodes)) <= 0.5 * len(p.nodes) for q in kept):
                    kept.append(p)
            same = kept
        if kind == "back_and_forth" and typical:
            same = [p for p in same if p.score >= 5 * typical]  # small change going back and forth is everyday
        if kind in ("fan_in", "fan_out"):
            from .investigate import _exclusive
            same = [p for p in same if _exclusive(p)]  # a shop's customers or a payroll are everyday
        best = same[0].score if same else 0
        for p in same:
            if kind == "clique" and len(p.nodes) < 5:
                continue  # small cliques are everywhere in social data
            if best and p.score < 0.25 * best:
                continue  # a summary keeps the ones that stand out; patterns() has them all
            out.append(Finding(kind, p.text, p.nodes))
    return out[:total]


def _brokers(g, group_of, names, degree, lang, name):
    scored = []
    for x in g:
        own = group_of.get(x)
        counts = Counter(group_of.get(y) for y in g._all_neighbors(x) if y != x)
        counts.pop(None, None)
        others = [k for k in counts if k != own]
        if len(others) < 2 and not (len(others) == 1 and counts[others[0]] >= 3):
            continue
        k = sum(counts.values())
        participation = 1 - sum((c / k) ** 2 for c in counts.values())
        scored.append((degree[x] * participation, x, own, sorted(counts, key=lambda c: -counts[c])))
    scored.sort(key=lambda t: -t[0])
    out = []
    for _, x, own, touched in scored[:2]:
        linked = [own] + [c for c in touched if c != own]
        labels = [names[c] for c in linked[:4] if c in names]
        out.append(Finding("broker", i18n.text(lang, "broker", name=name(x), groups=i18n.join(labels, lang)),
                           [x] + [y for y in g._all_neighbors(x) if y != x]))
    return out


def _hubs(g, degree, lang, name):
    by_kind = {}
    for x in g:  # a shop is compared with other shops' counterparts, not with devices
        by_kind.setdefault(g.nodes[x].get("kind"), []).append(x)
    found = []
    for members in by_kind.values():
        active = sorted(degree[x] for x in members if degree[x] > 0)
        if len(active) < 10:
            continue
        median = _median(active)
        cut = max(10, 5 * median)
        found += [(degree[x], x, median) for x in members if degree[x] >= cut]
    found.sort(key=lambda f: (-f[0], str(f[1])))
    return [Finding("hub", i18n.text(lang, "hub", name=name(x), times=i18n.number(d / median, lang),
                                     d=i18n.number(d, lang), median=i18n.number(median, lang)),
                    [x] + list(g._all_neighbors(x)))
            for d, x, median in found[:3]]


def _reciprocity(g, lang):
    links = [(u, v) for u, v, _ in g._edge_triples() if u != v]
    if not links:
        return []
    both = sum(1 for u, v in links if g.has_edge(v, u))
    return [Finding("reciprocity", i18n.text(lang, "reciprocity", pct=i18n.percent(both / len(links), lang)))]


def _weights(g, weight, lang, name):
    from .graph import _resolve_weight
    weight = _resolve_weight(g, weight)
    if not weight:
        return []
    weighted = [(d[weight], u, v) for u, v, d in g._edge_triples()
                if _is_number(d.get(weight)) and d[weight] > 0]
    if len(weighted) < 2 or len(weighted) < 0.5 * g.edge_count:
        return []
    weighted.sort(key=lambda t: -t[0])
    out = []
    total = sum(w for w, _, _ in weighted)
    if len(weighted) >= 10:
        top = weighted[:max(1, math.ceil(len(weighted) * 0.1))]
        share = sum(w for w, _, _ in top) / total
    if len(weighted) >= 10 and share >= 0.3:  # evenly spread weights are not worth a line
        out.append(Finding("concentration", i18n.text(lang, "concentration", pct=i18n.percent(share, lang),
                                                      weight=i18n.metric_name(weight, lang)),
                           list(dict.fromkeys(x for _, u, v in top for x in (u, v)))))
    w, u, v = weighted[0]
    out.append(Finding("strongest", i18n.text(lang, "strongest", a=name(u), b=name(v), w=i18n.number(w, lang)),
                       [u, v]))
    return out
