"""Plain-language text for explanations and the view, in English and Portuguese."""

import os

from .errors import TarecoError

LANGUAGES = ("en", "pt")
_default = None


def set_language(lang):
    """Language for explanations and the interactive view: "en" or "pt"."""
    global _default
    _default = _check(lang)


def get_language(lang=None):
    if lang is not None:
        return _check(lang)
    if _default is not None:
        return _default
    env = os.environ.get("TARECO_LANG", "").lower()[:2]
    return env if env in LANGUAGES else "en"


def _check(lang):
    code = str(lang).lower().replace("_", "-").split("-")[0]
    if code not in LANGUAGES:
        raise TarecoError(f"language must be one of {LANGUAGES}, not {lang!r}")
    return code


def number(value, lang, digits=1):
    """1234.5 -> '1,234.5' (en) or '1.234,5' (pt); integers keep no decimals."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, float) and value.is_integer() and abs(value) >= 100:
        value = int(value)
    if isinstance(value, int):
        text = f"{value:,}"
    elif abs(value) >= 100:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.{digits if abs(value) >= 1 else max(digits, 2)}f}".rstrip("0").rstrip(".")
    if lang == "pt":
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return text


def percent(share, lang):
    pct = share * 100
    text = f"{pct:.0f}%" if pct >= 10 or pct == 0 else f"{pct:.1f}%"
    return text.replace(".", ",") if lang == "pt" else text


def join(items, lang):
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    word = " and " if lang == "en" else " e "
    return ", ".join(items[:-1]) + word + items[-1]


TEXT = {
    "en": {
        "group": "Group",
        "overview": "{n} nodes and {m} connections; on average each node connects to {avg} others.",
        "overview_directed": "{n} nodes and {m} directed links; on average each node takes part in {avg} links.",
        "connected": "Everything is connected in a single network.",
        "parts": "It is split into {c} separate parts; the largest holds {pct} of the nodes.",
        "isolated": "{k} nodes have no connections at all.",
        "isolated_one": "1 node has no connections at all.",
        "small_parts": "{k} small islands of 2 or 3 nodes are cut off from the rest.",
        "small_parts_one": "1 small island of 2 or 3 nodes is cut off from the rest.",
        "groups": "It forms {k} groups that mostly connect among themselves: {pct} of the connections stay inside a group.",
        "groups_loose": "It forms {k} groups, but most connections ({pct}) cross from one group to another.",
        "no_groups": "There are no clear groups: connections spread across the whole network.",
        "group_line": "{name} ({size} nodes, {pct}){traits}. Key members: {members}.",
        "group_inward": "{pct} of its connections stay inside",
        "central": "The most important nodes are {names}.",
        "broker": "{name} is a bridge between groups: it links {groups}.",
        "hub": "{name} has {times}x more connections than a typical node ({d} vs {median}).",
        "collector": "{name} receives from {k} nodes but sends to {out}.",
        "distributor": "{name} sends to {k} nodes but receives from {inn}.",
        "nobody": "none",
        "reciprocity": "{pct} of the links go both ways.",
        "concentration": "The heaviest 10% of the connections carry {pct} of the total {weight}.",
        "strongest": "The strongest connection is {a} and {b} ({w}).",
        "trait_category": "{attr}: {value} in {share} (vs {overall} overall)",
        "trait_higher": "{attr} higher: median {group} vs {overall}",
        "trait_lower": "{attr} lower: median {group} vs {overall}",
        "profile_size": "{size} nodes ({pct})",
        "profile_members": "key members: {members}",
        "profile_inward": "connections inside the group: {pct}",
        "profile_link": "most linked to: {name}",
        "title": "What this network shows",
        "short_higher": "{attr} higher",
        "smaller_groups": "{k} smaller groups",
        "short_lower": "{attr} lower",
    },
    "pt": {
        "group": "Grupo",
        "overview": "{n} nós e {m} conexões; em média cada nó se conecta a {avg} outros.",
        "overview_directed": "{n} nós e {m} ligações com direção; em média cada nó participa de {avg} ligações.",
        "connected": "Tudo está conectado numa única rede.",
        "parts": "A rede está dividida em {c} partes separadas; a maior reúne {pct} dos nós.",
        "isolated": "{k} nós não têm nenhuma conexão.",
        "isolated_one": "1 nó não tem nenhuma conexão.",
        "small_parts": "{k} ilhas pequenas, de 2 ou 3 nós, estão isoladas do resto.",
        "small_parts_one": "1 ilha pequena, de 2 ou 3 nós, está isolada do resto.",
        "groups": "Formam-se {k} grupos que se conectam principalmente entre si: {pct} das conexões ficam dentro de um grupo.",
        "groups_loose": "Formam-se {k} grupos, mas a maioria das conexões ({pct}) cruza de um grupo para outro.",
        "no_groups": "Não há grupos claros: as conexões se espalham pela rede inteira.",
        "group_line": "{name} ({size} nós, {pct}){traits}. Principais membros: {members}.",
        "group_inward": "{pct} das conexões ficam dentro do grupo",
        "central": "Os nós mais importantes são {names}.",
        "broker": "{name} é uma ponte entre grupos: liga {groups}.",
        "hub": "{name} tem {times}x mais conexões que um nó típico ({d} contra {median}).",
        "collector": "{name} recebe de {k} nós mas envia para {out}.",
        "distributor": "{name} envia para {k} nós mas recebe de {inn}.",
        "nobody": "nenhum",
        "reciprocity": "{pct} das ligações são de mão dupla.",
        "concentration": "Os 10% de conexões mais fortes concentram {pct} do total de {weight}.",
        "strongest": "A conexão mais forte é entre {a} e {b} ({w}).",
        "trait_category": "{attr}: {value} em {share} (contra {overall} no geral)",
        "trait_higher": "{attr} mais alto: mediana {group} contra {overall}",
        "trait_lower": "{attr} mais baixo: mediana {group} contra {overall}",
        "profile_size": "{size} nós ({pct})",
        "profile_members": "principais membros: {members}",
        "profile_inward": "conexões dentro do grupo: {pct}",
        "profile_link": "mais ligado a: {name}",
        "title": "O que esta rede mostra",
        "short_higher": "{attr} mais alto",
        "smaller_groups": "{k} grupos menores",
        "short_lower": "{attr} mais baixo",
    },
}


METRIC_NAMES = {
    "pt": {"community": "comunidade", "degree": "grau", "betweenness": "intermediação",
           "closeness": "proximidade", "clustering": "agrupamento", "core": "núcleo",
           "component": "componente", "pagerank": "pagerank", "in": "entrada", "out": "saída"},
}


def metric_name(name, lang):
    """Display name of a built-in metric ("community" -> "comunidade" in Portuguese)."""
    return METRIC_NAMES.get(lang, {}).get(name, name)


def text(lang, key, **values):
    return TEXT[lang][key].format(**values)
