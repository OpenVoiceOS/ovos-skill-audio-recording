"""Multilingual golden-utterance end-to-end coverage for
ovos-skill-audio-recording.

Extends test_intents_en_us.py (en-US only) to every locale that has a
golden_utterances_<lang>.jsonl file. Every row runs and is asserted,
including machine-generated rows that still need a native check: a row
that does not route is a failure, never a skip or an xfail.

One shared MiniCroft is booted with en-US as the primary language and
every other locale as a ``secondary_lang`` (ovoscope>=1.6.5a1 /
padacioso>=2.2.3a1, which contains the upstream fix for padacioso#77 --
cross-language intent detach scoping -- required for a single shared
MiniCroft to route more than one language correctly).

Every row here is a natural-language sample that a real speaker of the
locale would use to start a recording -- it must route to
start_recording whether or not it happens to be derivable from the
skill's own locale/<lang>/intents/start_recording.intent template via
``ovos_spec_tools.expand()``. A row failing to route is a template gap,
not a reason to drop the row.
Rows with the optional ``{name}`` slot use the connector-word wording
already present in the template, with the slot filled by the neutral,
skill-provided example title "meeting" (the same word used verbatim in
the en-US ``locale/en-US/intents/name.entity`` sample list and in
test_intents_en_us.py::test_record_audio_named_meeting) -- this is a slot
value, not translated skill content.

Capture ends at ``mycroft.skill.handler.start`` for the same reason as
test_intents_en_us.py: the handler starts a real recording session and
schedules an auto-stop event, which is not the thing under test here --
intent routing is.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"

_PIPELINE = [
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-low",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "recognizer_loop:state.set",
    "mycroft.scheduler.schedule_event",
    "mycroft.scheduler.remove_event",
]

END2END_DIR = Path(__file__).parent

# Every golden_utterances_<lang>.jsonl present runs; a new locale file is
# picked up without editing this list.
LANGS = sorted(
    p.stem[len("golden_utterances_"):]
    for p in END2END_DIR.glob("golden_utterances_*.jsonl")
)
SECONDARY_LANGS = [lang for lang in LANGS if lang != "en-US"]

# en-US is the MiniCroft primary language (get_minicroft's default), so it
# is not a secondary_lang: SECONDARY_LANGS is what the fixture boots with,
# and LANGS already names every locale that ships rows, en-US included.
ROW_LANGS = LANGS

# Cross-language negatives: an utterance from one locale's own golden slice
# must not be claimed in a session using a different, unrelated language,
# and phrasing lifted from other skills' domains must not be claimed either.
CROSS_LANG_NEGATIVES = [
    ("Audioaufnahme starten", "en-US", "german utterance in an english session"),
    ("comença a gravar", "de-DE", "catalan utterance in a german session"),
    ("démarre un enregistrement", "es-ES", "french utterance in a spanish session"),
    ("play some music", "de-DE", "other-skill (music) phrasing, german session"),
    ("what's the weather", "fr-FR", "other-skill (weather) phrasing, french session"),
    ("stop listening", "en-US", "naptime phrasing, english session"),
]


def _candidates(skill_id: str, intent_label: str) -> set:
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{intent_label}", f"{skill_id}:{base}"}


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


ALL_ROWS = []
for _lang in ROW_LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _as_param(row):
    tag = "tier2" if row.get("machine_generated") else "tier1"
    return pytest.param(row, id=f"{row['lang']}-{tag}-{row['utterance']}")


GOLDEN_ROWS = [_as_param(r) for r in ALL_ROWS]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID], secondary_langs=SECONDARY_LANGS)
    yield mc
    mc.stop()


def _types(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(_PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


def _golden_id(row):
    return f"{row['lang']}-{row['utterance']}"


@pytest.mark.timeout(300)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance_multilang(minicroft, row):
    candidates = _candidates(SKILL_ID, row["intent_label"])
    types = _types(minicroft, row["utterance"], row["lang"], f"golden-{_golden_id(row)}")
    matched = any(t in candidates for t in types)
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r}: expected one of {sorted(candidates)!r}, got {types!r}"
    )


@pytest.mark.timeout(300)
@pytest.mark.parametrize("negative", CROSS_LANG_NEGATIVES, ids=lambda n: f"{n[1]}-{n[0]}")
def test_cross_language_negative(minicroft, negative):
    text, lang, _why = negative
    types = _types(minicroft, text, lang, f"negative-{lang}-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"[{lang}] {text!r} was incorrectly claimed by {SKILL_ID}"


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = Path(__file__).parents[2] / "locale"
    shipping = {d.name for d in locale_root.iterdir()
                if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"
