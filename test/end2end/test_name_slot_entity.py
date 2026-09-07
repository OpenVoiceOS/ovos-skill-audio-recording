"""E2e coverage for the ``{name}`` slot in ``start_recording.intent`` after
wiring ``self.register_entity_file("name.entity")`` into ``initialize()``
(requires ovos-workshop>=9.3.12a1).

Registering ``name.entity`` is a scoring HINT, not a closed vocabulary
(INTENT-1 §5.4): an out-of-list slot value still matches
``start_recording.intent`` via the fuzzy ``ovos-padacioso-pipeline-plugin``
match, and the ``{name}`` slot fills with the literal utterance value;
in-list values match as well, typically at the ``-high`` band.

The registration-wiring proof itself (independent of the fuzzy-matching
behavior) is
``test/unittests/test_skill_loading.py::TestNameEntityRegistration``.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"
LANG = "en-US"

PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
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
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=300, wait_for_trained=False)

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
        """Registering name.entity is a scoring HINT, not a closed
        vocabulary. A natural, unlisted title ("homework") must still
        match start_recording.intent, and the {name} slot must fill with
        the literal utterance value.
        """
        messages = self._capture("start a new recording named homework", "name-slot-hint-homework")
        matches = [m for m in messages if m.msg_type == f"{SKILL_ID}:start_recording"]
        self.assertTrue(
            matches,
            "out-of-list slot value did not route -- name.entity hint "
            "semantics may have regressed"
        )
        self.assertEqual(matches[0].data.get("name"), "homework")


if __name__ == "__main__":
    unittest.main()
