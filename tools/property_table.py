#!/usr/bin/env python3
"""Generate the README table of every property: what it runs on, and which method.

    python3 tools/property_table.py            print the table
    python3 tools/property_table.py --write    replace the table in README.md
    python3 tools/property_table.py --check    exit 1 if README.md is out of date

Nothing here is hand-maintained, and no Jev request is made:

- "method" is the proseweave function that first returns the property, found
  by tracing a run over sample text.
- "runs on" is found by perturbation: the package runs with a stand-in Jev
  that answers deterministically, and again with the answers of one Jev caller
  at a time changed. A property whose value moves depends on that caller; a
  property that never moves is computed in Python alone.
"""
from __future__ import annotations

import hashlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "validation"))

from proseweave import source  # noqa: E402
from proseweave.analysis import Analysis  # noqa: E402

START, END = "<!-- properties:start -->", "<!-- properties:end -->"
SEEDS = 3
# Computed without Jev by definition, though produced inside a function that
# also asks Jev for other values.
LOCAL_BY_DEFINITION = {"syntactic_simplicity"}   # Flesch reading ease, clamped to 0-100
# What each Jev-calling function asks, for the table's legend.
CALLER_NOTES = {
    "tagger_classes.pos_tags": "word classes. The local tagger (syntax.py) tags every word; Jev "
                               "re-checks only the open-class words the tagger is unsure of",
    "annotate.relatedness": "how related two passages are, on a graded scale",
    "annotate.familiarity": "how familiar a word is, as a stand-in for its frequency",
    "annotate.phrase_familiarity": "how common a word or phrase is in ordinary writing",
    "annotate.demonstrative_roles": "whether this/that/these/those is a determiner, a pronoun, "
                                    "a relative or a complementiser",
    "connectives.clause_marks": "whether a word like 'before', 'since' or 'as' introduces a clause or a "
                                "noun phrase, in context",
    "judged.jobs": "reader-level judgements (a bank of questions on the whole text and on each ~300-word "
                   "part) behind the easability and quality scores",
    "connectives.senses_jev":"the sense of an ambiguous connective in context ('so', 'since', 'while', ...)",
    "analysis.easability": "reader-level judgements behind narrativity, concreteness and the cohesion "
                           "components",
}
# Word classes whose lists come from the tagger (pronouns are a closed set).
TAGGED_CLASSES = ("all", "cw", "fw", "noun", "verb", "adj", "adv", "argument")

# Written so that nouns, verbs, adjectives, adverbs and pronouns recur across
# neighbouring sentences and paragraphs: every index then has something to
# count, and a change in any input shows up in the output.
SAMPLE = [
    """The old harbour was quiet in the early morning. The harbour master walked
slowly along the quiet quay, and he counted the small boats. Each small boat had
a name painted carefully on its side, and he knew every name by heart.

He had counted the boats every morning for thirty years. The boats changed, but
the counting did not change. His daughter said the counting was a habit, not a
job; he said a habit was simply a job that nobody paid for.

This morning one boat was missing. He counted again, slowly and carefully, and
again one small boat was missing. Because the sea had been calm all night, he
was not worried at first, but the missing boat belonged to his daughter.

So he walked quickly to the end of the quay. From there he could see the whole
bay, bright and calm, and in the middle of the bay a small boat drifted slowly.
His daughter waved. She had simply gone out early, as he himself once did.""",
    """The committee met on Tuesday because the budget was late. However, nobody
had read the report, so the chair postponed the vote until the following week.
She said that this delay would cost the city money, and that it was the second
time in a year.

Meanwhile, residents who depend on the bus service waited for an answer. Many of
them had written letters; some had called. A few, frustrated, stopped paying
attention at all, since the council seemed unable to decide anything quickly.

In the end the council approved a smaller budget. It cut two routes and raised
fares slightly, although the mayor promised to restore the routes if revenue
improved. Those who had waited felt relieved, but they were not satisfied.""",
    """Salmon return to the river where they hatched. They travel upstream against
strong currents, leaping over rocks and small falls. As a result, many are
exhausted when they arrive, and most die soon after spawning.

Their bodies feed the forest. Bears carry the fish away from the water, and the
remains fertilise the soil, so trees near salmon rivers grow faster than trees
elsewhere. This connection surprised the scientists who first measured it.

Therefore, protecting the fish also protects the forest. When dams block the
river, the whole valley changes: fewer fish, fewer bears, slower trees.""",
]


# Dependence is probed on real, openly licensed texts when they are present:
# made-up samples saturate some indices (a paragraph-level binary overlap that is
# 1 everywhere cannot move), which would hide a dependence.
_OPEN = ROOT / "validation" / "open" / "texts"
PROBE_FILES = ["000.txt", "027.txt", "054.txt", "081.txt"]
PROBES = ([(_OPEN / f).read_text(encoding="utf-8") for f in PROBE_FILES]
          if all((_OPEN / f).exists() for f in PROBE_FILES) else SAMPLE)


class StubJev:
    """Stands in for jev.Jev: deterministic answers, optionally perturbed for one caller."""

    input_tokens = 0
    requests = 0

    def __init__(self, perturb: str | None = None, seed: int = 0):
        self.perturb = perturb
        self.seed = seed
        self.callers: set[str] = set()

    @staticmethod
    def _caller() -> str:
        for fr in inspect.stack()[2:]:
            mod = fr.frame.f_globals.get("__name__", "")
            if mod.startswith("proseweave") and mod != "proseweave.jev":
                return f"{mod.split('.', 1)[1]}.{fr.function}"
        return "?"

    def _answer(self, q: dict, salt: str) -> dict:
        h = int(hashlib.sha256((salt + q.get("instructions", "")).encode()).hexdigest(), 16)
        t, crit = q.get("type"), q.get("criteria")
        if t == "choice":
            # Unperturbed, a choice question gets no answer, so the package keeps
            # its local decision (the tagger's own tag, the default sense) and the
            # baseline stays realistic. Perturbed, it gets an arbitrary option.
            if salt == "a":
                return {"choice": None}
            keys = list(crit) if isinstance(crit, (dict, list)) else []
            return {"choice": keys[h % len(keys)] if keys else None}
        if t == "score":
            n = len(crit) if isinstance(crit, (dict, list)) and crit else 5
            return {"probabilities": {str(h % n): 1.0}, "score": h % n}
        return {"noul": (h % 1000) / 1000}

    def _note(self, caller):
        self.callers.add(caller)
        for active in _ACTIVE:          # every proseweave function currently running
            active.add(caller)

    def ask(self, state, questions):
        caller = self._caller()
        self._note(caller)
        salt = f"b{self.seed}" if caller == self.perturb else "a"
        return {k: self._answer(q, salt) for k, q in questions.items()}

    def ask_many(self, jobs):
        caller = self._caller()
        self._note(caller)
        salt = f"b{self.seed}" if caller == self.perturb else "a"
        return [{k: self._answer(q, salt) for k, q in qs.items()} for _, qs in jobs]


def _run(j, texts=None):
    """Properties of the first text, and the source comparison of the first two."""
    texts = texts or SAMPLE
    a = [Analysis(t, j) for t in texts[:2]]
    return a[0].properties(), source.compare(j, a[0], a[1])


def _runs(j):
    """The same, over every probe text (text i against text i+1), keyed by probe."""
    out = []
    for i in range(len(PROBES)):
        out.append(_run(j, [PROBES[i], PROBES[(i + 1) % len(PROBES)]]))
    return out


_ACTIVE: list[set] = []   # Jev callers seen during each running proseweave function


def _trace_methods() -> tuple[dict, dict, dict]:
    """Property -> the proseweave function that first returned it, and the Jev
    callers that ran while that function was running."""
    first: dict[str, str] = {}
    during: dict[str, set] = {}

    def ours(frame):
        mod = frame.f_globals.get("__name__", "")
        return mod.startswith("proseweave.") and mod != "proseweave.jev"

    def prof(frame, event, arg):
        if event == "call" and ours(frame):
            _ACTIVE.append(set())
        elif event == "return" and ours(frame):
            seen = _ACTIVE.pop() if _ACTIVE else set()
            if isinstance(arg, dict):
                mod = frame.f_globals["__name__"].split(".", 1)[1]
                name = getattr(frame.f_code, "co_qualname", frame.f_code.co_name).split(".<locals>")[0]
                for k in arg:
                    if isinstance(k, str) and k not in first:
                        first[k] = f"{mod}.{name}"
                        during[k] = set(seen)

    sys.setprofile(prof)
    try:
        single, pair = _run(StubJev(), PROBES[:2])
    finally:
        sys.setprofile(None)
        _ACTIVE.clear()
    return ({p: first.get(p, "?") for p in single}, {p: first.get(p, "?") for p in pair}, during)


def _moved(a: dict, b: dict) -> set:
    out = set()
    for p in a:
        x, y = a.get(p), b.get(p)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if abs(x - y) > 1e-12:
                out.add(p)
        elif x != y:
            out.add(p)
    return out


def build() -> str:
    # Probe runs send every open-class word to Jev (normally only the ones the
    # local tagger is unsure of), so a property's dependence on Jev's word
    # classes shows up however confident the tagger is on this sample.
    margin = getattr(Analysis, "TAG_MARGIN", None)
    if margin is not None:
        Analysis.TAG_MARGIN = 10 ** 12
    try:
        methods_s, methods_p, during = _trace_methods()
        probe = StubJev()
        base = _runs(probe)
        deps: dict[str, list] = {p: [] for p in list(base[0][0]) + list(base[0][1])}
        for caller in sorted(probe.callers):
            moved = set()
            for seed in range(SEEDS):   # several perturbations, so no dependence hides by chance
                for (bs, bp), (s, p) in zip(base, _runs(StubJev(perturb=caller, seed=seed))):
                    moved |= _moved(bs, s) | _moved(bp, p)
            for prop in moved:
                deps[prop].append(caller)
        # A value can fail to move by chance (a maximum pinned at the top of the
        # scale); if the function that produced it asked Jev while it ran, count
        # that dependence too.
        def siblings(prop):
            stem = prop.rsplit("_", 1)[0]
            return {c for q, cs in deps.items() if q != prop and q.rsplit("_", 1)[0] == stem for c in cs}

        for prop, d in list(deps.items()):
            if not d and during.get(prop) and prop not in LOCAL_BY_DEFINITION:
                # Keep only the callers that move this property's siblings
                # (semantic_cohesion_min follows semantic_cohesion_mean), when any do.
                sib = siblings(prop) & during[prop]
                d.extend(sorted(sib or during[prop]))
            # Overlap indices over tagged word classes depend on the tagger by
            # construction; some (paragraph-level binary variants) are pinned at
            # 0 or 1 on real prose, so perturbation alone cannot show it.
            if not d and methods_s.get(prop) == "cohesion.overlap_family" and \
                    any(f"_{c}_" in prop for c in TAGGED_CLASSES):
                d.append("tagger_classes.pos_tags")
    finally:
        if margin is not None:
            Analysis.TAG_MARGIN = margin
    no_key = set(Analysis(SAMPLE[0], None).properties())

    try:
        from catalog import all_props
        family = {p: v[1] for p, v in all_props().items()}
    except Exception:  # noqa: BLE001 - catalog is optional
        family = {}

    def row(p, method, group):
        d = deps.get(p) or []
        runs = "Python" if not d else "Jev: " + ", ".join(f"`{c}`" for c in d)
        key = " (no key needed)" if p in no_key else ""
        return f"| `{p}` | {group} | {runs}{key} | `{method}` |"

    callers = sorted({c for d in deps.values() for c in d})
    legend = [f"- `{c}`: {CALLER_NOTES.get(c, 'asks Jev')}" for c in callers]
    lines = [START, "",
             "Generated by `tools/property_table.py`; don't edit it by hand.", "",
             "- **Python** means the value is computed locally, with no Jev request.",
             "- **Jev: …** names the proseweave function whose Jev answers the value depends on.",
             "- **(no key needed)** means the value is still produced without a Jev key, using",
             "  the local fallback.", "",
             "Jev is used by:", "", *legend, "",
             "| property | group | runs on | method |", "|---|---|---|---|"]
    for p in sorted(methods_s, key=lambda x: (family.get(x, "~"), x)):
        lines.append(row(p, methods_s[p], family.get(p, "other")))
    for p in sorted(methods_p):
        lines.append(row(p, methods_p[p], "source comparison"))
    counts = {"python": 0, "jev": 0}
    for p in list(methods_s) + list(methods_p):
        counts["jev" if deps.get(p) else "python"] += 1
    lines += ["", f"{len(methods_s)} single-text and {len(methods_p)} source-comparison properties: "
              f"{counts['python']} computed in Python alone, {counts['jev']} using Jev.", "", END]
    return "\n".join(lines)


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    table = build()
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if START in text and END in text:
        cur = text[text.index(START):text.index(END) + len(END)]
        new = text.replace(cur, table)
    else:
        new = text.rstrip("\n") + "\n\n## Every property\n\n" + table + "\n"
    if "--check" in a:
        if new != text:
            print("README.md property table is out of date: run tools/property_table.py --write")
            return 1
        print("README.md property table is current")
        return 0
    if "--write" in a:
        readme.write_text(new, encoding="utf-8")
        print("README.md updated")
        return 0
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
