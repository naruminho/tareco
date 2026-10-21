"""Plain-language text for explanations and the view, in English and Portuguese."""

import locale
import os

from .errors import TarecoError

LANGUAGES = ("en", "pt")
_default = None


def set_language(lang):
    """Language for explanations and the interactive view: "en" or "pt"; None goes back to automatic."""
    global _default
    _default = None if lang is None else _check(lang)


def get_language(lang=None):
    if lang is not None:
        return _check(lang)
    if _default is not None:
        return _default
    env = os.environ.get("TARECO_LANG", "").lower()[:2]
    if env in LANGUAGES:
        return env
    return _system_language() or "en"


def _system_language():
    """Portuguese when the computer is set to Portuguese, so nobody has to ask for it."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "").lower()
        if value and value not in ("c", "posix", "c.utf-8"):
            return "pt" if value.startswith("pt") else None
    try:
        code = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):
        code = ""
    return "pt" if code.startswith(("pt", "portuguese")) else None


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
        "collector_only": "{name} receives from {k} nodes, {only} of which send to nobody else, and sends to {out}.",
        "distributor": "{name} sends to {k} nodes but receives from {inn}.",
        "distributor_only": "{name} sends to {k} nodes, {only} of which hear from nobody else, and receives from {inn}.",
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
        "route_sep": " to ",
        "cycle": "{nodes} form a loop: {route}.",
        "cycle_amount": "Up to {amount} can go all the way around.",
        "pass_through": "{name} receives from {k_in} nodes and passes on to {k_out}.",
        "pass_through_amount": "{name} receives from {k_in} nodes and passes almost all of it on to {k_out} ({got} in, {gave} out).",
        "chain": "A chain of {k} intermediaries: {route}.",
        "back_and_forth": "{a} and {b} send each other similar amounts ({x} and {y}).",
        "star": "{name} is the only connection of {k} nodes.",
        "clique": "{k} nodes are all connected to each other: {names}.",
        "and_more": " and {k} more",
        "unit_day": "days", "unit_week": "weeks", "unit_month": "months", "unit_quarter": "quarters",
        "unit_year": "years", "unit_period": "periods",
        "time_span": "From {first} to {last} ({k} {unit}): {n} nodes and {m} connections in total.",
        "busiest": "The busiest period was {period}, with {m} connections.",
        "quiet": "Nothing happened in {k} of the periods.",
        "activity_up": "Activity grew {pct} in {period} ({a} to {b} connections).",
        "activity_down": "Activity fell {pct} in {period} ({a} to {b} connections).",
        "newcomers": "{k} new nodes showed up in {period}.",
        "surge": "{name} jumped to {d} connections in {period} (about {avg} per period before).",
        "debut": "{name} appeared in {period} with {d} connections at once.",
        "new_group": "A new group of {k} nodes formed in {period}, around {names}.",
        "merge": "Two groups merged in {period}: the one around {a} and the one around {b}.",
        "split": "A group split in {period}: the one around {a} broke into parts around {names}.",
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
        "collector_only": "{name} recebe de {k} nós, {only} deles não enviam para mais ninguém, e envia para {out}.",
        "distributor": "{name} envia para {k} nós mas recebe de {inn}.",
        "distributor_only": "{name} envia para {k} nós, {only} deles não recebem de mais ninguém, e recebe de {inn}.",
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
        "route_sep": " para ",
        "cycle": "{nodes} formam um ciclo: {route}.",
        "cycle_amount": "Até {amount} pode dar a volta completa.",
        "pass_through": "{name} recebe de {k_in} nós e repassa para {k_out}.",
        "pass_through_amount": "{name} recebe de {k_in} nós e repassa quase tudo para {k_out} ({got} entram, {gave} saem).",
        "chain": "Uma cadeia de {k} intermediários: {route}.",
        "back_and_forth": "{a} e {b} enviam quantias parecidas um ao outro ({x} e {y}).",
        "star": "{name} é a única conexão de {k} nós.",
        "clique": "{k} nós estão todos conectados entre si: {names}.",
        "and_more": " e mais {k}",
        "unit_day": "dias", "unit_week": "semanas", "unit_month": "meses", "unit_quarter": "trimestres",
        "unit_year": "anos", "unit_period": "períodos",
        "time_span": "De {first} a {last} ({k} {unit}): {n} nós e {m} conexões no total.",
        "busiest": "O período mais movimentado foi {period}, com {m} conexões.",
        "quiet": "Nada aconteceu em {k} dos períodos.",
        "activity_up": "A atividade cresceu {pct} em {period} (de {a} para {b} conexões).",
        "activity_down": "A atividade caiu {pct} em {period} (de {a} para {b} conexões).",
        "newcomers": "{k} nós novos apareceram em {period}.",
        "surge": "{name} saltou para {d} conexões em {period} (cerca de {avg} por período antes).",
        "debut": "{name} apareceu em {period} já com {d} conexões.",
        "new_group": "Um grupo novo de {k} nós se formou em {period}, em torno de {names}.",
        "merge": "Dois grupos se fundiram em {period}: o de {a} e o de {b}.",
        "split": "Um grupo se dividiu em {period}: o de {a} se partiu em grupos em torno de {names}.",
        "short_lower": "{attr} mais baixo",
    },
}


METRIC_NAMES = {
    "en": {"count": "occurrences"},
    "pt": {"count": "ocorrências","community": "comunidade", "degree": "grau", "betweenness": "intermediação",
           "closeness": "proximidade", "clustering": "agrupamento", "core": "núcleo",
           "component": "componente", "pagerank": "pagerank", "in": "entrada", "out": "saída"},
}


def metric_name(name, lang):
    """Display name of a built-in metric ("community" -> "comunidade" in Portuguese)."""
    return METRIC_NAMES.get(lang, {}).get(name, name)


def text(lang, key, **values):
    return TEXT[lang][key].format(**values)
