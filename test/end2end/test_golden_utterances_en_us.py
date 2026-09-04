"""En-US golden-utterance end-to-end coverage for
ovos-skill-audio-recording, following the OVOS golden-utterance standard
(skills-qa-golden-utterance-standard).

The skill exposes a single Padatious intent, ``start_recording.intent``.
Every row in ``golden_utterances_en-US.jsonl`` is a natural phrasing a real
speaker would use to ask the skill to start capturing audio -- it must route
to ``start_recording`` whether or not it happens to be one of the literal
expansions of the skill's own template. A row that fails to route is a
template gap to close in the ``.intent`` file, never a reason to drop or
water down the row.

The negatives below are sibling-confusion checks: phrasings that belong to a
neighbouring skill/intent (dictation's "start recording text", naptime's
"stop listening" wake-word-style stop -- see the module docstring in
``test_intents_en_us.py`` for why "stop recording" is deliberately excluded
from the positive side) or an unrelated domain, and must NOT be claimed by
this skill.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"
LANG = "en-US"

PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "recognizer_loop:state.set",
    "mycroft.scheduler.schedule_event",
    "mycroft.scheduler.remove_event",
]

END2END_DIR = Path(__file__).parent

# Sibling-confusion / out-of-domain negatives: none of these should be
# claimed by ovos-skill-audio-recording.
NEGATIVE_UTTERANCES = [
    ("start recording text", "dictation skill's own intent phrasing"),
    ("start recording words", "dictation skill's own intent phrasing"),
    ("stop recording", "recording-stop is a wake-word-style stop, not an intent"),
    ("stop listening", "naptime phrasing"),
    ("play the recording", "playback, not starting a new one"),
    ("delete the recording", "deletion, not starting a new one"),
    ("play some music", "unrelated skill domain"),
    ("what's the weather", "unrelated skill domain"),
    ("set a timer for ten minutes", "unrelated skill domain"),
    ("take a note", "note-taking skill, not audio recording"),
]


def _load_rows():
    path = END2END_DIR / "golden_utterances_en-US.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _candidates(intent_label):
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{SKILL_ID}:{intent_label}", f"{SKILL_ID}:{base}"}


GOLDEN_ROWS = [pytest.param(r, id=r["utterance"]) for r in _load_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _types(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


# No real routing defects remain after the template fixes in this pass; kept
# as the landing spot for any genuine future regression, per the
# ovos-skill-volume / multilang-suite precedent in this repo.
KNOWN_BUGS = {}


@pytest.mark.timeout(300)
@pytest.mark.parametrize("row", GOLDEN_ROWS)
def test_golden_utterance_en_us(minicroft, row):
    candidates = _candidates(row["intent_label"])
    types = _types(minicroft, row["utterance"], f"golden-{row['utterance']}")
    matched = any(t in candidates for t in types)
    if row["utterance"] in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[row['utterance']]}")
    assert matched, (
        f"{row['utterance']!r}: expected one of {sorted(candidates)!r}, got {types!r}"
    )


@pytest.mark.timeout(300)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_sibling_confusion_negative(minicroft, negative):
    text, _why = negative
    types = _types(minicroft, text, f"negative-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} was incorrectly claimed by {SKILL_ID} ({_why})"

