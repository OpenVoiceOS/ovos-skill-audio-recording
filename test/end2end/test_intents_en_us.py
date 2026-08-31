"""End-to-end intent-routing coverage for ovos-skill-audio-recording (en-US).

The skill registers a single Padatious intent, ``start_recording.intent``. Its
handler starts a recording session and emits ``recognizer_loop:state.set`` with
the recording title, but speaks nothing, so the assertions below drive the
padatious pipeline with representative utterances and check the deterministic
message skeleton (utterance -> activate -> intent -> handler start/complete ->
handled).

The optional ``{name}`` slot titles the recording; a connector word
(``named``/``called``/``as`` ...) always precedes it. The sibling
``name.blacklist`` guard vocabulary that keeps fillers out of the ``{name}``
title is asserted at registration level in ``test/unittests``.
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_utils.log import LOG

from ovoscope import End2EndTest, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"
LANG = "en-US"
HANDLER = "AudioRecordingSkill.handle_start_recording"


class TestStartRecordingIntent(TestCase):

    def setUp(self):
        LOG.set_level("CRITICAL")
        self.minicroft = get_minicroft([SKILL_ID])
        self.skill = self.minicroft.plugin_skills[SKILL_ID].instance
        # the scheduled auto-stop event and the state.set broadcast are not part
        # of the routing skeleton under test; ignore anything non-deterministic
        self.ignore_messages = [
            "speak",
            "ovos.utterance.speak",
            "recognizer_loop:state.set",
            "mycroft.scheduler.schedule_event",
            "mycroft.scheduler.remove_event",
        ]

    def tearDown(self):
        if self.minicroft:
            self.minicroft.stop()

    def _utterance(self, text):
        session = Session(f"e2e-{abs(hash(text))}")
        session.lang = LANG
        session.pipeline = ["ovos-padatious-pipeline-plugin-high"]
        return Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": LANG},
            {"session": session.serialize()},
        )

    def _expected(self, message):
        # PIPELINE-1 migration: the dispatched ovos.intent.matched intent_name
        # (and the handler.start/complete payload) drops the ".intent" suffix
        # from the source filename (same fix as ovos-skill-volume#127).
        intent_name = "start_recording"
        return [
            message,
            Message(f"{SKILL_ID}.activate", {}),
            Message("ovos.intent.matched",
                    {"skill_id": SKILL_ID,
                     "intent_name": f"{SKILL_ID}:{intent_name}"}),
            Message("ovos.intent.handler.start",
                    {"skill_id": SKILL_ID, "intent_name": intent_name}),
            Message(f"{SKILL_ID}:{intent_name}", {}),
            Message("mycroft.skill.handler.start", {"name": HANDLER}),
            Message("mycroft.skill.handler.complete", {"name": HANDLER}),
            Message("ovos.intent.handler.complete",
                    {"skill_id": SKILL_ID, "intent_name": intent_name}),
            Message("ovos.utterance.handled", {}),
        ]

    def _run(self, message):
        test = End2EndTest(
            minicroft=self.minicroft,
            skill_ids=[],
            eof_msgs=["ovos.utterance.handled"],
            flip_points=["recognizer_loop:utterance"],
            ignore_messages=self.ignore_messages,
            source_message=message,
            expected_messages=self._expected(message),
        )
        test.execute()

    def test_bare_start_recording(self):
        """`start recording` -> start_recording.intent (unnamed recording)."""
        self._run(self._utterance("start recording"))

    def test_record_audio_named_meeting(self):
        """`record audio named meeting` extracts the {name} title `meeting`."""
        self.skill.recording_sessions.clear()
        message = self._utterance("record audio named meeting")
        self._run(message)
        # exactly one recording session was opened, titled by the {name} slot
        sessions = list(self.skill.recording_sessions.values())
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["file_name"], "meeting")
