"""Plain-language text for explanations and the view, in English and Portuguese."""

import locale
import os
import re

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
        "kinds": "Links: {links}. Nodes: {nodes}.",
        "shared": "{k} {kind} nodes share {name} ({own}).",
        "unusual_amount": "{name} sent {amount} to {other}{when}, {times}x what it usually sends ({usual}).",
        "on_date": " on {date}",
        "split_out": "{name} sent {k} transfers just under {limit} within {span} ({first} to {last}), to {r} receivers, {lo} to {hi} each.",
        "split_in": "{name} received {k} transfers just under {limit} from {r} senders within {span} ({first} to {last}), {lo} to {hi} each.",
        "span_day": "1 day", "span_days": "{n} days", "span_hours": "{n} hours", "span_same_day": "a single day",
        "misfit_lower": "{name} has {attr} {value}, {times}x lower than the median of the {k} nodes it deals with ({median}).",
        "misfit_higher": "{name} has {attr} {value}, {times}x higher than the median of the {k} nodes it deals with ({median}).",
        "misfit_category": "{name} has {attr} {value}, but {pct} of the {k} nodes it deals with have {other}.",
        "near_direct": "{name} is directly linked to {targets}.",
        "near": "{name} is {d} steps from {targets}, through {via}.",
        "flows_title": "Where it goes, by {by}",
        "flows_title_from": "Where it comes from, by {by}",
        "flow_line": "{value}: {amount} ({share} of the total), {links} links from {k} nodes: {names}",
        "flow_line_from": "{value}: {amount} ({share} of the total), {links} links to {k} nodes: {names}",
        "why_title": "About {name}",
        "node_word": "node",
        "review_title": "Worth a look",
        "review_item": "{name} (score {score})",
        "review_rows": ", {k} rows behind it",
        "review_more": " (and {k} more like it)",
        "fast_pass": "{name} received {inn} and passed on {out} within {span} ({first} to {last}).",
        "trace": "{route}: {k} transfers from {first} to {last}, up to {amount} all the way.",
        "why_identity": "{name} ({kind}){attrs}.",
        "why_attrs": "{name}: {attrs}.",
        "why_flows": "It sent {out} to {k_out} nodes and received {inn} from {k_in}.",
        "why_links": "It is linked to {k} nodes.",
        "why_busy": "That is {times}x the links of a typical {kind} ({d} vs {median}).",
        "why_rank": "It is among the {pct} most important nodes.",
        "why_group": "It is in {group}{traits}.",
        "why_part_of": "Part of: {text}",
        "why_shares": "It shares {things} with {others}.",
        "why_seen": "Its rows go from {first} to {last} ({k} rows).",
        "why_nothing": "Nothing stands out about {name}.",
        "similar_title": "Most like {name}",
        "similar_line": "{name} ({score}): {reasons}",
        "similar_none": "nothing in particular",
        "sim_out_links": "sends to many nodes", "sim_in_links": "receives from many nodes",
        "sim_out_amount": "sends large amounts", "sim_in_amount": "receives large amounts",
        "sim_pass_through": "passes on about what it receives",
        "sim_only_senders": "receives from nodes that send nowhere else",
        "sim_only_receivers": "sends to nodes that hear from nobody else",
        "sim_splits": "piles amounts just under a round limit",
        "sim_unusual": "made transfers far above its usual",
        "sim_shared": "shares a {kind} with other nodes",
        "sim_cycles": "takes part in loops",
        "sim_chains": "sits in a chain of intermediaries",
        "sim_typical_amount": "its typical amount is large",
        "sim_typical_amount_low": "its typical amount is small",
        "sim_links_low": "has very few links",
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
        "kinds": "Ligações: {links}. Nós: {nodes}.",
        "shared": "{k} nós do tipo {kind} compartilham {name} ({own}).",
        "unusual_amount": "{name} enviou {amount} para {other}{when}, {times}x o que costuma enviar ({usual}).",
        "on_date": " em {date}",
        "split_out": "{name} enviou {k} transferências logo abaixo de {limit} em {span} ({first} a {last}), para {r} destinatários, de {lo} a {hi} cada.",
        "split_in": "{name} recebeu {k} transferências logo abaixo de {limit} de {r} remetentes em {span} ({first} a {last}), de {lo} a {hi} cada.",
        "span_day": "1 dia", "span_days": "{n} dias", "span_hours": "{n} horas", "span_same_day": "um só dia",
        "misfit_lower": "{name} tem {attr} {value}, {times}x menor que a mediana dos {k} nós com quem se relaciona ({median}).",
        "misfit_higher": "{name} tem {attr} {value}, {times}x maior que a mediana dos {k} nós com quem se relaciona ({median}).",
        "misfit_category": "{name} tem {attr} {value}, mas {pct} dos {k} nós com quem se relaciona têm {other}.",
        "near_direct": "{name} está ligado diretamente a {targets}.",
        "near": "{name} está a {d} passos de {targets}, passando por {via}.",
        "flows_title": "Para onde vai, por {by}",
        "flows_title_from": "De onde vem, por {by}",
        "flow_line": "{value}: {amount} ({share} do total), {links} ligações de {k} nós: {names}",
        "flow_line_from": "{value}: {amount} ({share} do total), {links} ligações para {k} nós: {names}",
        "why_title": "Sobre {name}",
        "node_word": "nó",
        "review_title": "Vale um olhar",
        "review_item": "{name} (pontos {score})",
        "review_rows": ", {k} linhas por trás",
        "review_more": " (e mais {k} parecidos)",
        "fast_pass": "{name} recebeu {inn} e repassou {out} em {span} ({first} a {last}).",
        "trace": "{route}: {k} transferências de {first} a {last}, até {amount} no caminho todo.",
        "why_identity": "{name} ({kind}){attrs}.",
        "why_attrs": "{name}: {attrs}.",
        "why_flows": "Enviou {out} para {k_out} nós e recebeu {inn} de {k_in}.",
        "why_links": "Está ligado a {k} nós.",
        "why_busy": "São {times}x as ligações de um {kind} típico ({d} contra {median}).",
        "why_rank": "Está entre os {pct} nós mais importantes.",
        "why_group": "Está no {group}{traits}.",
        "why_part_of": "Faz parte de: {text}",
        "why_shares": "Compartilha {things} com {others}.",
        "why_seen": "Suas linhas vão de {first} a {last} ({k} linhas).",
        "why_nothing": "Nada se destaca em {name}.",
        "similar_title": "Mais parecidos com {name}",
        "similar_line": "{name} ({score}): {reasons}",
        "similar_none": "nada em particular",
        "sim_out_links": "envia para muitos nós", "sim_in_links": "recebe de muitos nós",
        "sim_out_amount": "envia valores altos", "sim_in_amount": "recebe valores altos",
        "sim_pass_through": "repassa quase tudo o que recebe",
        "sim_only_senders": "recebe de nós que não enviam para mais ninguém",
        "sim_only_receivers": "envia para nós que não recebem de mais ninguém",
        "sim_splits": "acumula valores logo abaixo de um limite redondo",
        "sim_unusual": "fez transferências muito acima do seu normal",
        "sim_shared": "compartilha um {kind} com outros nós",
        "sim_cycles": "participa de ciclos",
        "sim_chains": "está numa cadeia de intermediários",
        "sim_typical_amount": "seu valor típico é alto",
        "sim_typical_amount_low": "seu valor típico é baixo",
        "sim_links_low": "tem pouquíssimas ligações",
    },
}


METRIC_NAMES = {
    "en": {"count": "occurrences"},
    "pt": {"count": "ocorrências", "community": "comunidade", "degree": "grau", "betweenness": "intermediação",
           "closeness": "proximidade", "clustering": "agrupamento", "core": "núcleo",
           "component": "componente", "pagerank": "pagerank", "in": "entrada", "out": "saída"},
}


def metric_name(name, lang):
    """Display name of a built-in metric ("community" -> "comunidade" in Portuguese)."""
    return METRIC_NAMES.get(lang, {}).get(name, name)


SINGULAR = {
    "en": {"nodes": "node", "senders": "sender", "receivers": "receiver", "rows": "row", "links": "link",
           "transfers": "transfer", "connections": "connection", "days": "day", "hours": "hour",
           "groups": "group", "periods": "period", "intermediaries": "intermediary", "steps": "step",
           "accounts": "account", "people": "person", "times": "time", "members": "member"},
    "pt": {"nós": "nó", "remetentes": "remetente", "destinatários": "destinatário", "linhas": "linha",
           "ligações": "ligação", "transferências": "transferência", "conexões": "conexão", "dias": "dia",
           "horas": "hora", "grupos": "grupo", "períodos": "período", "intermediários": "intermediário",
           "passos": "passo", "contas": "conta", "pessoas": "pessoa", "vezes": "vez", "membros": "membro"},
}
_ONE = {lang: re.compile(r"(?<![\d.,])1 (" + "|".join(map(re.escape, words)) + r")\b")
        for lang, words in SINGULAR.items()}


def text(lang, key, **values):
    out = TEXT[lang][key].format(**values)
    return _ONE[lang].sub(lambda m: "1 " + SINGULAR[lang][m.group(1)], out)  # "1 nodes" -> "1 node"
