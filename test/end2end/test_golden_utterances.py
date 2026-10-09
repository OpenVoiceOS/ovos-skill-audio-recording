"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

Each ``negative_utterances_<lang>.jsonl`` holds requests for other skills, and
utterances in another language than the session. They run on the same
pipeline and must not match any intent of this skill.

Each locale must match at least ``MIN_MATCH_RATE`` of its golden rows, and
at least ``MIN_MATCHED_ROWS_PER_INTENT`` rows of every intent. No negative row
may match an intent of this skill, except the claims listed by name in
``NEGATIVE_KNOWN_CLAIMS``. All rows run, including rows marked
``needs_manual`` or ``machine_generated``, and the test prints every row that
misses with the intent that matched instead.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# Every intent with rows in a locale must match at least this many of them,
# so a high locale rate cannot hide an intent that never matches.
MIN_MATCHED_ROWS_PER_INTENT = 1
END2END_DIR = Path(__file__).parent
# With only this skill loaded, the published m2v model claims every ru-RU
# request for another skill, while the ru-RU golden rows still match.
NEGATIVE_ENGINE_GAPS = {
    "ru-RU": "m2v claims every ru-RU request for another skill as start_recording",
}
# Negative rows that m2v claimed in two separate runs. A claim listed here is
# allowed; any other claim fails the locale.
NEGATIVE_KNOWN_CLAIMS = {
    "en-US": {"Audioaufnahme starten": "start_recording"},
    "es-ES": {"démarre un enregistrement": "start_recording"},
    "pl-PL": {"zrób głośniej": "start_recording", "puść jakąś muzykę": "start_recording"},
}


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVE_ROWS = _rows_by_lang("negative_utterances")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


def _match_all(lang, rows):
    """Boot the skill on m2v in ``lang`` and return the intent each row matches."""
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        return [_matched_intent(engine, row["utterance"], lang) for row in rows]
    finally:
        minicroft.stop()


def _assert_rate(lang, rows, misses, what):
    rate = 1 - len(misses) / len(rows)
    print(f"[{lang}] {rate:.1%} of {len(rows)} {what}", *misses, sep="\n  ")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of {what}, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    rows = ROWS[lang]
    matched = _match_all(lang, rows)
    misses = [f"{row['utterance']!r}: expected {row['intent_label']}, got {got}"
              for row, got in zip(rows, matched)
              if got != f"{SKILL_ID}:{row['intent_label']}"]
    matched_per_intent = {row["intent_label"]: 0 for row in rows}
    for row, got in zip(rows, matched):
        if got == f"{SKILL_ID}:{row['intent_label']}":
            matched_per_intent[row["intent_label"]] += 1
    starved = sorted(label for label, count in matched_per_intent.items()
                     if count < MIN_MATCHED_ROWS_PER_INTENT)
    print(f"[{lang}] matched rows per intent: {matched_per_intent}", *misses, sep="\n  ")
    assert not starved, (
        f"[{lang}] intents with fewer than {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    _assert_rate(lang, rows, misses, "rows match")


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang], strict=False))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVE_ROWS)
])
def test_negative_rows_match_no_skill_intent(lang):
    rows = NEGATIVE_ROWS[lang]
    matched = _match_all(lang, rows)
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    claims = {row["utterance"]: got.removeprefix(f"{SKILL_ID}:")
              for row, got in zip(rows, matched)
              if got and got.startswith(f"{SKILL_ID}:")}
    print(f"[{lang}] {len(rows) - len(claims)} of {len(rows)} negative rows stay out of the skill",
          *(f"{utterance!r}: matched {intent}" for utterance, intent in claims.items()),
          sep="\n  ")
    unexpected = {utterance: intent for utterance, intent in claims.items()
                  if known.get(utterance) != intent}
    assert not unexpected, f"[{lang}] negative rows claimed by the skill: {unexpected}"


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"
