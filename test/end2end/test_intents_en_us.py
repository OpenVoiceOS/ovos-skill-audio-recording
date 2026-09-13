"""End-to-end intent-routing coverage for ovos-skill-audio-recording (en-US).

The skill registers a single Padatious intent, ``start_recording.intent``.
Routing alone (utterance -> activate -> intent -> handler start/complete ->
handled) is satisfied by a handler that raises before doing any work, so the
skeleton below also asserts the recording EFFECT: the exact
``recognizer_loop:state.set`` payload the handler emits to start the
recording (``state`` and ``recording_name``, checked by value, not just
presence), and the exact ``recognizer_loop:record_stop`` emission plus the
internal session flip when a later ``mycroft.stop`` ends it. The skill never
calls ``self.speak`` (there is no dialog file under ``locale/en-US``), so
there is no spoken confirmation to assert here -- the bus messages are the
only externally observable effect.

The optional ``{name}`` slot titles the recording; a connector word
(``named``/``called``/``as`` ...) always precedes it. The sibling
``name.blacklist`` guard vocabulary that keeps fillers out of the ``{name}``
title is asserted at registration level in ``test/unittests``.
"""
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovos_utils.log import LOG

from ovoscope import End2EndTest, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"
LANG = "en-US"
HANDLER = "AudioRecordingSkill.handle_start_recording"

# frozen instant used in place of ``now_local()`` so the unnamed-recording
# title (derived from the current time) is a value we compute independently
# rather than a value we captured from a run and wrote down.
FROZEN_NOW = datetime(2024, 1, 1, 12, 0, 0)


class TestStartRecordingIntent(TestCase):

    def setUp(self):
        LOG.set_level("CRITICAL")
        self.minicroft = get_minicroft([SKILL_ID])
        self.skill = self.minicroft.plugin_skills[SKILL_ID].instance
        # spoken text and the scheduler bookkeeping are not part of the
        # routing skeleton or the recording effect under test; everything
        # else -- including recognizer_loop:state.set and
        # recognizer_loop:record_stop -- is captured and asserted on value.
        self.ignore_messages = [
            "speak",
            "ovos.utterance.speak",
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

    def _expected(self, message, recording_name):
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
            # the recording-start effect: state flips to "recording" and the
            # title carries the value derived from the utterance (or, when
            # unnamed, the frozen clock reading below) -- both checked by
            # exact value, so a handler that emits the wrong state or drops
            # the title fails here even though routing still succeeded.
            Message("recognizer_loop:state.set",
                    {"state": "recording", "recording_name": recording_name}),
            Message("mycroft.skill.handler.complete", {"name": HANDLER}),
            Message("ovos.intent.handler.complete",
                    {"skill_id": SKILL_ID, "intent_name": intent_name}),
            Message("ovos.utterance.handled", {}),
        ]

    def _run(self, message, recording_name):
        test = End2EndTest(
            minicroft=self.minicroft,
            skill_ids=[],
            eof_msgs=["ovos.utterance.handled"],
            flip_points=["recognizer_loop:utterance"],
            ignore_messages=self.ignore_messages,
            source_message=message,
            expected_messages=self._expected(message, recording_name),
        )
        test.execute()

    def test_bare_start_recording(self):
        """`start recording` -> start_recording.intent (unnamed recording).

        The unnamed title is ``str(now_local())``; ``now_local`` is frozen so
        the expected title is computed independently rather than read back
        from a live run.
        """
        message = self._utterance("start recording")
        with patch("ovos_skill_audio_recording.now_local", return_value=FROZEN_NOW):
            self._run(message, recording_name=str(FROZEN_NOW))

    def test_record_audio_named_meeting(self):
        """`record audio named meeting` extracts the {name} title `meeting`."""
        self.skill.recording_sessions.clear()
        message = self._utterance("record audio named meeting")
        self._run(message, recording_name="meeting")
        # exactly one recording session was opened, titled by the {name} slot
        sessions = list(self.skill.recording_sessions.values())
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["file_name"], "meeting")

    def test_stop_recording_emits_record_stop(self):
        """A later `mycroft.stop` on the same session ends an open recording:
        `recognizer_loop:record_stop` is emitted and the internal session
        flips out of the recording state -- the effect side of `stop_session`,
        not just that some stop message was accepted.
        """
        self.skill.recording_sessions.clear()
        start_message = self._utterance("record audio named meeting")
        self._run(start_message, recording_name="meeting")
        session_id = Session.deserialize(
            start_message.context["session"]).session_id
        self.assertTrue(
            self.skill.recording_sessions[session_id]["recording"])

        stop_message = Message(
            "mycroft.stop", {}, {"session": start_message.context["session"]})
        received = []
        self.minicroft.bus.on("recognizer_loop:record_stop",
                               lambda m: received.append(m))
        self.minicroft.bus.emit(stop_message)
        # mycroft.stop is handled synchronously on the same bus thread, so no
        # polling wait is needed before inspecting the effect.
        self.assertEqual(len(received), 1)
        self.assertFalse(
            self.skill.recording_sessions[session_id]["recording"])
