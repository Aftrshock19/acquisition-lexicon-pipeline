# Spanish Verb Morphology & Explanation Pipeline (v1)

A reviewable TypeScript pipeline that reads [spa-eng.csv](spa-eng.csv),
classifies Spanish verb lemmas into learner-facing grammar categories,
generates full pedagogical paradigms, and emits two app-ready tables plus
review artifacts and Postgres-compatible SQL.

## What this system produces

Two app-facing data layers, plus review/audit files.

### Layer 1: `verb_lemmas`

One row per canonical verb lemma. Support metadata for the app and for
driving lesson/topic filtering. Fields: `lemma`, `original_lemma`, `rank`,
`translation`, `english_definition`, `primary_topic_key`,
`secondary_topic_keys`, `irregularity_tags`, `base_lemma`, `is_pronominal`,
`review_required`, `confidence`, `notes`, `evidence`, `manual_override`,
`source`.

### Layer 2: `verb_form_analyses`

**The main app-facing table.** One row per possible analysis of a
conjugated surface form — so a single `surface_norm` may appear in multiple
rows when forms are ambiguous (e.g. `fue` → `ser` preterite 3sg and `ir`
preterite 3sg). Fields: `surface_form`, `surface_norm`, `lemma`,
`original_lemma`, `rank_hint`, `primary_topic_key`, `secondary_topic_keys`,
`irregularity_tags`, `mood`, `tense`, `person`, `number`, `nonfinite_type`,
`polarity`, `is_pronominal`, `explanation_short`, `explanation_long`,
`why_note`, `review_required`, `confidence`, `evidence`, `source`.

The app is intended to normalize a tapped token (lowercase+trim) and query
`verb_form_analyses` by `surface_norm`. If one analysis is returned, show
it. If several are returned, order by `rank_hint` and show alternatives.
Explanations are pre-generated — the app does no morphological work.

## Primary taxonomy (learner-facing, intentionally small)

`regular_ar`, `regular_er`, `regular_ir`, `stem_changing`, `orthographic`,
`irregular`, `pronominal`, `gustar_type`, `defective_impersonal`,
`multiword_expression`.

Fine detail (stem change direction, yo-go, past-participle irregularity,
mixed-irregular, spelling-change kind, etc.) lives in `irregularity_tags`
rather than as extra primary categories. See
[docs/verb_morphology_research_note.md](docs/verb_morphology_research_note.md)
for the design rationale.

## Morphology scope (v1)

**Non-finite:** infinitive, gerund, past participle.
**Finite indicative:** present, preterite, imperfect, future, conditional.
**Finite subjunctive:** present.
**Imperative:** affirmative only — tú, usted, nosotros, vosotros, ustedes.

Total: 44 slots per conjugatable verb. **Out of scope for v1:** imperfect
subjunctive, future subjunctive, compound tenses, negative imperative,
clitic-attached forms. Multi-word expressions produce no generated forms. Base-shared pronominal
lemmas (e.g. `hablarse`) emit only the 3 non-finite lookup rows
(infinitive, gerund with attached `se`, past participle) — see
"Pronominal handling" below.

### Conjugation engine

Three layers, in precedence order:

1. **Form override** — per-slot manual override from `src/overrides/overrides.json`.
2. **Curated irregular paradigm** — explicit paradigm tables for
   `ser, ir, haber, estar, dar, tener, venir, decir, hacer, poner` and their
   productive compounds (mantener, detener, obtener, contener, sostener,
   entretener, convenir, intervenir, prevenir, componer, proponer, suponer,
   imponer, oponer, deshacer, rehacer).
3. **Regular template + rule transforms** — for everything else: regular
   -ar/-er/-ir endings, stem-change rules (e→ie, o→ue, e→i, u→ue), spelling
   preservation rules (c/qu, g/gu, z/c, gü, c/zc, g/j, gu→g), and
   y-insertion for -uir verbs. Pronominal lemmas are conjugated from their
   non-pronominal base (`quejarse` → forms of `quejar`) and flagged
   `is_pronominal = true`.

### Pronominal handling (final v1)

Pronominal lemmas are split into two cases for app lookup:

* **Pronominal-only** (base verb is *not* a standalone lemma in the dataset,
  e.g. `quejarse`): full 44-slot paradigm is retained under the pronominal
  lemma so that bare finite forms like `quejo` resolve somewhere. The
  infinitive surface is the `-se` form (`quejarse`) and the gerund attaches
  `se` with the required written accent (`quejándose`).
* **Base-shared pronominal** (non-pronominal base also exists as a
  standalone lemma, e.g. `hablarse` whose base `hablar` is its own lemma):
  bare finite forms are deliberately **not** duplicated under the
  pronominal lemma. Exactly three non-finite rows are emitted — the
  infinitive (`hablarse`), the gerund with attached `se` (`hablándose`),
  and the past participle (`hablado`, unchanged — Spanish does not attach
  clitics to past participles). Tapping a bare finite form (`hablo`)
  resolves to the non-pronominal lemma; tapping the pronominal infinitive
  or attached-clitic gerund resolves to the pronominal lemma.

This deliberately trims pronominal-duplication ambiguity — the
`ambiguous_forms_review.csv` count drops roughly in half between the naive
"duplicate everything" approach and this v1.

## Overrides

`src/overrides/overrides.json` has three sections:

* `lemma_overrides` — override the lemma profile (primary topic, tags,
  base_lemma, review flag, notes). Manual overrides always win.
* `form_overrides` — patch fields on a specific generated form
  (`{ lemma, slot_id, surface_form?, explanation_short?, explanation_long?, why_note? }`).
  Each field is independent — a `why_note` override replaces only the
  `why_note`, never the `explanation_short`.
* `form_suppressions` — drop a specific generated form.

Reruns preserve all manual curation. Output rows carry `source` = `override`
where applicable. The Postgres upsert templates refuse to overwrite
`manual_override = true` lemma rows or `source = 'override'` form rows.

## How to run

```bash
npm install
npm run generate:verb-profiles     # build all artifacts
npm test                           # run morphology + pipeline + golden tests
npm run classify -- --lemma hablar # preview a single lemma classification
```

## Generated artifacts

```
output/generated/
  grammar_topics.json
  verb_lemmas.json
  verb_lemmas.csv
  verb_form_analyses.json
  verb_form_analyses.csv
output/review/
  high_frequency_verb_audit.csv   # top-500 lemmas by rank, with assigned class
  ambiguous_forms_review.csv      # every surface_norm with ≥2 analyses
  review_required.csv             # lemmas flagged for human review
  summary.json                    # counts by primary topic / irregularity tag
```

## SQL (Supabase / Postgres)

```
sql/001_grammar_topics.sql
sql/002_verb_lemmas.sql
sql/003_verb_form_analyses.sql
sql/004_seed_grammar_topics.sql
sql/005_upsert_verb_lemmas.sql
sql/006_upsert_verb_form_analyses.sql
```

Both upsert templates preserve manual curation on reimport.

## Project layout

```
src/
  classifier/      normalize, detect, classify, curated lists, precedence
  morphology/      slot model, endings, transforms, irregular paradigms,
                   conjugator, explanation generator, shared types
  data/            CSV loader, grammar topics
  overrides/       overrides.json + loader (lemma + form + suppression)
  types/           shared TS types
  utils/           CSV writer
scripts/           generate.ts, classifyOne.ts
sql/               schema, seed, upsert templates
output/            generated + review artifacts
tests/             vitest: golden classifier tests, morphology tests,
                   pipeline smoke tests (loads generated artifacts)
docs/              research notes
```

## App consumption

1. App normalizes the tapped token (`trim().toLowerCase()`).
2. App queries `verb_form_analyses` by `surface_norm`.
3. If 1 row: show `explanation_short` + `why_note`; show `explanation_long`
   on expansion.
4. If >1 row: order by `rank_hint`, show the top analysis first, offer
   alternatives. Forms intentionally duplicate across rows so that
   context-aware ranking happens in the app, not the generator.
5. `is_pronominal = true` tells the UI to render the reflexive-pronoun hint
   alongside the form.

## Limitations (v1)

1. Scope is intentionally reduced — no imperfect/future subjunctive, no
   compound tenses, no negative imperative, no clitic-attached forms.
2. Long-tail irregulars (outside the curated paradigm list) use regular
   templates with rule transforms and may be incorrect for some slots.
   Correct them via `form_overrides` in `src/overrides/overrides.json`.
3. Multi-word verbal expressions are held in `verb_lemmas` only; no
   generated form paradigm is produced for them in v1.
4. No live Supabase integration in this workspace; SQL upsert templates are
   the supported import path (CSV → staging → upsert).
5. Browsing was unavailable during design, so
   [docs/verb_morphology_research_note.md](docs/verb_morphology_research_note.md)
   cites no external sources; see that file for the items to verify later.
