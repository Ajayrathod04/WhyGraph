"""Deterministic question understanding (no LLM needed).

1. detect_intents(): which jobs does the question ask for, in the order they appear?
2. resolve(): which decision / system does it talk about? (token overlap + alias phrases)
"""
import re

STOP = set(
    """a an the and or but if of to in on off at by for from with without about into onto over under is are was were be been
    being do does did done we our us you your i me my it its this that these those there here what which who whom whose when
    where why how can could should would will shall may might must not no yes so as than then too very just also any some
    all more most other such only own same up down out again further once back now new old why""".split()
)

INTENT_PATTERNS = [
    ("why", r"\bwhy\b|\breasons?\b|\brationale\b|\bwho decided\b|\bhow come\b|\bbased on\b|\bsources?\b|\bevidence\b|\btrace\b|\bhistory\b"),
    ("who", r"\bwho\b(?! decided)|\bowners?\b|\bexperts?\b|\bask\b|\bknows?\b|\bcontact\b"),
    ("impact", r"\bbreaks?\b|\bimpacts?\b|\baffects?\b|\bblast\b|\bundo\b|\brevers\w*|\broll ?back\b|\bdepend\w*|\bdownstream\b|\bgoes down\b|\bis down\b|\bfails?\b"),
    ("stale", r"\bstale\b|\boutdated\b|\bstill valid\b|\bout of date\b|\bobsolete\b|\bexpired\b|\bneeds? (?:review|update)\b|\bstill hold"),
    ("plan", r"\bplan\b|\bdraft\b|\bpropose\b|\bchange request\b|\bnotify\b"),
]


def _stem(token):
    return token[:-1] if len(token) > 4 and token.endswith("s") else token


def tokens(text):
    out = []
    for t in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if t in STOP:
            continue
        if len(t) < 3 and not t.isdigit():
            continue
        out.append(_stem(t))
    return out


def detect_intents(question):
    q = question.lower()
    found = []
    for name, pattern in INTENT_PATTERNS:
        m = re.search(pattern, q)
        if m:
            found.append((m.start(), name))
    found.sort()
    intents = [name for _, name in found]
    if "plan" in intents and "impact" in intents:
        intents.remove("impact")  # the plan playbook already runs the impact steps
    return intents


def _phrases(row_name, aliases):
    items = [row_name or ""]
    items += [a.strip() for a in (aliases or "").split(",")]
    return [i.lower() for i in items if len(i.strip()) >= 3]


def score(question, name, aliases, usage=0):
    q = question.lower()
    s = 0.0
    for i, phrase in enumerate(_phrases(name, aliases)):
        if re.search(r"\b" + re.escape(phrase) + r"\b", q):
            s += 6 if i == 0 else 4
    s += len(set(tokens(question)) & set(tokens(name)))
    if s:
        s += min(usage, 5) * 0.1  # episodic memory: frequently consulted decisions win ties
    return s


def resolve(question, decisions, systems, usage=None):
    """decisions: [{id,title,aliases}], systems: [{id,name,aliases}]. Returns (decision|None, system|None)."""
    usage = usage or {}
    best_d, best_ds = None, 0.0
    for d in decisions:
        s = score(question, d["title"], d.get("aliases"), usage.get(d["id"], 0))
        if s > best_ds:
            best_d, best_ds = d, s
    best_s, best_ss = None, 0.0
    for sy in systems:
        s = score(question, sy["name"], sy.get("aliases"))
        if s > best_ss:
            best_s, best_ss = sy, s
    decision = best_d if best_ds >= 3 else None
    system = best_s if best_ss >= 3 else None
    return decision, system


def suggest_steps(intents, decision, system):
    """Choose which playbooks (intents) to run for what was understood. Returns (intents, note)."""
    if not intents:
        if decision:
            intents = ["why"]
        elif system:
            intents = ["who", "impact"]
        else:
            return [], "I could not tell which decision or system you mean."
    fixed = []
    for intent in intents:
        if intent == "stale" and decision:
            intent = "why"  # 'is this decision still valid' = trace + stale check
        if intent not in fixed:
            fixed.append(intent)
    return fixed, ""
