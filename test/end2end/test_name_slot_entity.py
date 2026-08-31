"""E2e coverage for the ``{name}`` slot in ``start_recording.intent`` after
wiring ``self.register_entity_file("name.entity")`` into ``initialize()``
(requires ovos-workshop>=9.3.12a1 + ovos-padatious>=2.0.3a1).

Fixed upstream: ovos-padatious 2.0.3a1 (PyPI) corrected a bug where a
registered ``.entity`` file made a slot an effectively closed vocabulary
instead of the scoring hint it is documented to be (INTENT-1 §5.4). Under
2.0.3a1, an out-of-list slot value still matches, floored into the
padatious-medium confidence band (~[0.8, 0.92]); in-list values are
unaffected. This hint-not-allowlist behavior only fires when the active
pipeline includes ``ovos-padatious-pipeline-plugin-medium`` (this is why
the e2e ``PIPELINE`` below explicitly sets both ``-high`` and ``-medium``).

Empirically re-verified against ovos-padatious==2.0.3a1 with this skill's
real pipeline: "start a new recording named homework" (an unlisted but
natural title, not in ``locale/en-US/intents/name.entity``) now matches
``start_recording.intent`` and the ``{name}`` slot fills with the literal
utterance value ("homework"), landing on the
``ovos-padatious-pipeline-plugin-medium`` match rather than ``-high``.
Listed samples ("meeting", "podcast episode") keep matching, typically at
``-high``.

NOTE: ovos-padatious training has documented non-determinism, so band
edges may be less than 100% stable run-to-run for a given word; pick
stable utterances rather than loosening assertions if flakiness shows up.

The registration-wiring proof itself (independent of the padatious
matching behavior) is
``test/unittests/test_skill_loading.py::TestNameEntityRegistration``.
"""
import unittest

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


class TestNameSlotKnownValuesRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=300)

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _capture(self, text, session_id):
        session = Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        session.blacklisted_intents = []
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft, ignore_messages=_IGNORE)
        capture.capture(utterance, timeout=30)
        return capture.finish()

    def _types(self, text, session_id):
        return [m.msg_type for m in self._capture(text, session_id)]

    def test_known_title_meeting_matches(self):
        """"meeting" is a sample value in
        locale/en-US/intents/name.entity."""
        types = self._types("start a new recording named meeting", "name-slot-pos-meeting")
        self.assertIn(f"{SKILL_ID}:start_recording", types)

    def test_known_title_podcast_episode_matches(self):
        """"podcast episode" -- another real sample value from name.entity."""
        types = self._types("start a new recording named podcast episode", "name-slot-pos-podcast")
        self.assertIn(f"{SKILL_ID}:start_recording", types)

    def test_out_of_list_value_still_routes_as_hint(self):
        """Post ovos-padatious>=2.0.3a1: registering name.entity is a
        scoring HINT, not a closed vocabulary. A natural, unlisted title
        ("homework") must still match start_recording.intent, and the
        {name} slot must fill with the literal utterance value -- proving
        this isn't an accidental adapt/padacioso fallback match but a real
        padatious hint-band match (pipeline is padatious-only, see
        PIPELINE above).
        """
        messages = self._capture("start a new recording named homework", "name-slot-hint-homework")
        matches = [m for m in messages if m.msg_type == f"{SKILL_ID}:start_recording"]
        self.assertTrue(
            matches,
            "out-of-list slot value did not route -- ovos-padatious hint "
            "semantics (2.0.3a1+) may have regressed"
        )
        self.assertEqual(matches[0].data.get("name"), "homework")


if __name__ == "__main__":
    unittest.main()
