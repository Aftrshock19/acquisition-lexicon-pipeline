"""
rewrite_templates.py

Deterministic template-based rewrite for long Spanish sentences when
compression has failed. No network. No LLM.

Each template is a paired (Spanish, English) pattern. The English side is
produced for free, which is the whole point: a template rewrite never needs
MT.

Selection is **form-aware**: it inspects the lemma surface (e.g. "hayan",
"llevando", "papás") and the POS hint together to pick a template whose slot
fits the actual conjugated form. If no template fits, the function fails
cleanly so the row goes to manual review instead of producing nonsense like
"Yo hayan mucho".

Public API:
    rewrite(lemma: str, pos: str, original_sentence: str,
            english_gloss: str | None = None) -> RewriteResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Hand-built one-offs for fragile lemmas
# ---------------------------------------------------------------------------

FIXED: dict[str, tuple[str, str, str]] = {
    "tan":     ("fixed_tan",    "No está tan mal.",                   "It's not so bad."),
    "aun":     ("fixed_aun",    "Aun así, siguió adelante.",          "Even so, he kept going."),
    "ello":    ("fixed_ello",   "No quiero hablar de ello.",          "I don't want to talk about it."),
    "uno":     ("fixed_uno",    "Solo uno faltaba.",                  "Only one was missing."),
    "cuya":    ("fixed_cuya",   "Conocí a una mujer cuya hija vive aquí.",
                                "I met a woman whose daughter lives here."),
    "cuyo":    ("fixed_cuyo",   "Conocí a un hombre cuyo hijo vive aquí.",
                                "I met a man whose son lives here."),
    "porque":  ("fixed_porque", "No fui porque llovía.",              "I didn't go because it was raining."),
    "aunque":  ("fixed_aunque", "Aunque estaba cansado, siguió.",     "Although he was tired, he kept going."),
    "ces":     ("fixed_ces",    "El CES publicó su dictamen.",        "The CES published its opinion."),
    # Common fragile auxiliaries — surface forms drop straight in.
    "hayan":   ("fixed_hayan",  "Espero que hayan llegado bien.",     "I hope they have arrived safely."),
    "haya":    ("fixed_haya",   "Espero que haya llegado bien.",      "I hope he has arrived safely."),
    "hubiera": ("fixed_hubiera","Ojalá hubiera una salida.",          "I wish there were a way out."),
    "hubieran":("fixed_hubieran","Ojalá hubieran venido.",            "I wish they had come."),
}


# ---------------------------------------------------------------------------
# Form detection from the lemma surface
# ---------------------------------------------------------------------------
#
# We rely mainly on suffixes. The lemma column in the source is sometimes a
# conjugated surface form (e.g. "hayan", "llevando", "ganaba"), which is
# exactly what makes form-aware templating work without any morphology engine.
#

def detect_verb_form(surface: str) -> str | None:
    s = surface.lower()
    # gerund: -ando / -iendo / -yendo
    if re.search(r"(ando|iendo|yendo)$", s):
        return "verb_gerund"
    # past participle: -ado / -ido (be conservative; nouns end in -ado too)
    if re.search(r"(ado|ido)$", s) and len(s) >= 5:
        return "verb_participle"
    # future: -aré -arás -ará -aremos -aréis -arán (and -er/-ir variants)
    if re.search(r"(aré|arás|ará|aremos|aréis|arán|eré|erás|erá|eremos|eréis|erán|iré|irás|irá|iremos|iréis|irán)$", s):
        return "verb_future"
    # conditional: -aría/-ería/-iría and plurals
    if re.search(r"(aría|ería|iría|aríamos|eríamos|iríamos|arían|erían|irían)$", s):
        return "verb_conditional"
    # imperfect indicative: -aba/-ía and family
    if re.search(r"(aba|abas|ábamos|abais|aban|ía|ías|íamos|íais|ían)$", s):
        return "verb_imperfect"
    # preterite (regular): -é/-aste/-ó/-amos/-asteis/-aron and -er/-ir variants
    if re.search(r"(é|aste|ó|amos|asteis|aron|í|iste|ió|imos|isteis|ieron)$", s):
        return "verb_preterite"
    # present perfect subjunctive auxiliaries are caught in FIXED above.
    # imperfect subjunctive: -ara/-iera/-ase/-iese
    if re.search(r"(ara|aras|áramos|arais|aran|iera|ieras|iéramos|ierais|ieran|ase|ases|ásemos|aseis|asen|iese|ieses|iésemos|ieseis|iesen)$", s):
        return "verb_imp_subj"
    # present subjunctive (heuristic): -e/-es/-emos/-éis/-en for -ar verbs,
    # -a/-as/-amos/-áis/-an for -er/-ir verbs. Too ambiguous with indicative
    # without a paradigm; we leave it to the POS hint.
    return None


def coarse_pos(pos_field: str, surface: str) -> str:
    """Return a coarse POS family. Surface-based detection wins over the
    text hint when it's confident."""
    surf_form = detect_verb_form(surface)
    if surf_form:
        return surf_form

    s = (pos_field or "").lower()
    if "subjunctive" in s or "subjuntivo" in s:
        if "perfect" in s or "perfecto" in s:
            return "verb_pres_perf_subj"
        if "imperfect" in s or "imperfecto" in s:
            return "verb_imp_subj"
        return "verb_pres_subj"
    if "gerund" in s or "gerundio" in s:
        return "verb_gerund"
    if "participle" in s or "participio" in s:
        return "verb_participle"
    if "imperfect" in s or "imperfecto" in s:
        return "verb_imperfect"
    if "preterite" in s or "pretérito" in s or "preterito" in s:
        return "verb_preterite"
    if "future" in s or "futuro" in s:
        return "verb_future"
    if "conditional" in s or "condicional" in s:
        return "verb_conditional"
    if "adjective" in s:
        return "adjective"
    if "adverb" in s:
        return "adverb"
    if "noun" in s:
        return "noun"
    if "verb" in s or "present" in s:
        return "verb_present"
    return "unknown"


# ---------------------------------------------------------------------------
# Templates by family
# ---------------------------------------------------------------------------
#
# {form} = the lemma surface as it appears in the row.
# {form_en} = optional English gloss; when missing the template must NOT
#             produce a placeholder, so we filter such templates out.
#

# Verb templates per form-family. The slot must accept the conjugated surface.
VERB_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "verb_gerund": [
        ("verb_gerund_esta",  "Está {form}.",                 "He is doing it now."),
        ("verb_gerund_sigue", "Sigue {form}.",                "He keeps going."),
    ],
    "verb_participle": [
        ("verb_part_esta",    "Está {form}.",                 "It is done."),
        ("verb_part_fue",     "Fue {form} ayer.",             "It was done yesterday."),
    ],
    "verb_imperfect": [
        ("verb_imp_antes",    "Antes {form} mucho.",          "He used to do that a lot."),
        ("verb_imp_nino",     "De niño {form} aquí.",         "As a child he was here."),
    ],
    "verb_preterite": [
        ("verb_pret_ayer",    "Ayer {form} solo.",            "Yesterday he did it alone."),
        ("verb_pret_pf",      "Por fin {form}.",              "Finally it happened."),
    ],
    "verb_future": [
        ("verb_fut_manana",   "Mañana {form}.",               "It will happen tomorrow."),
        ("verb_fut_pronto",   "Pronto {form} más.",           "Soon there will be more."),
    ],
    "verb_conditional": [
        ("verb_cond_si",      "Si pudiera, {form} hoy.",      "If I could, I would do it today."),
    ],
    "verb_imp_subj": [
        ("verb_impsubj_si",   "Si {form}, yo iría.",          "If they did, I would go."),
        ("verb_impsubj_oja",  "Ojalá {form}.",                "I wish that were so."),
    ],
    "verb_pres_subj": [
        ("verb_pressubj_esp", "Espero que {form}.",           "I hope they do."),
        ("verb_pressubj_qui", "Quiero que {form}.",           "I want them to."),
    ],
    "verb_pres_perf_subj": [
        ("verb_perfsubj_pos", "Es posible que {form} ido.",   "They may have gone."),
    ],
}

# Non-verb templates accept the lemma surface directly into a noun/adj/adv slot.
NONVERB_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "noun": [
        ("noun_hay",      "Hay {form} aquí.",      "There are some here."),
        ("noun_tengo",    "Tengo {form}.",         "I have some."),
        ("noun_nec",      "Necesitamos {form}.",   "We need them."),
    ],
    "adjective": [
        ("adj_es",        "Es {form}.",            "It is like that."),
        ("adj_son",       "Son {form}.",           "They are like that."),
    ],
    "adverb": [
        ("adv_habla",     "Habla {form}.",         "He speaks that way."),
        ("adv_lleg",      "Llegó {form}.",         "He arrived that way."),
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class RewriteResult:
    success: bool
    final_sentence: str = ""
    final_english_sentence: str = ""
    template_id: str = ""
    pos_family: str = ""
    reason: str = ""


def rewrite(lemma: str, pos: str, original_sentence: str,
            english_gloss: str | None = None) -> RewriteResult:
    if not lemma:
        return RewriteResult(success=False, reason="empty lemma")

    key = lemma.lower().strip()

    # 1. Hand-built one-offs win.
    if key in FIXED:
        tid, sp, en = FIXED[key]
        return RewriteResult(
            success=True,
            final_sentence=sp,
            final_english_sentence=en,
            template_id=tid,
            pos_family="fixed",
        )

    family = coarse_pos(pos, lemma)

    # 2. Verb templates - the slot must fit the conjugated surface.
    if family in VERB_TEMPLATES:
        tid, sp_pat, en_pat = VERB_TEMPLATES[family][0]
        return RewriteResult(
            success=True,
            final_sentence=sp_pat.format(form=lemma),
            final_english_sentence=en_pat,
            template_id=tid,
            pos_family=family,
        )

    # 3. Non-verb templates.
    if family in NONVERB_TEMPLATES:
        tid, sp_pat, en_pat = NONVERB_TEMPLATES[family][0]
        return RewriteResult(
            success=True,
            final_sentence=sp_pat.format(form=lemma),
            final_english_sentence=en_pat,
            template_id=tid,
            pos_family=family,
        )

    # 4. Refuse rather than produce nonsense - row goes to manual review.
    return RewriteResult(
        success=False,
        pos_family=family,
        reason=f"no template for family={family} surface={lemma!r}",
    )
