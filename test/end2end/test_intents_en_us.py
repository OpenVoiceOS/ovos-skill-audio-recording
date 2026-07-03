"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the padatious ``start_recording.intent`` handler and run it to
completion. The handler starts a recording session rather than speaking, so
assertions cover the intent binding and handler lifecycle, not dialog content.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"


class TestAudioRecordingIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _run(self, text):
        session = Session("test-session")
        session.pipeline = [
            "ovos-adapt-pipeline-plugin-high",
            "ovos-padatious-pipeline-plugin-high",
            "ovos-adapt-pipeline-plugin-medium",
            "ovos-adapt-pipeline-plugin-low",
        ]
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": "en-US"},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft)
        capture.capture(utterance, timeout=30)
        return capture.finish()

    def _assert_start_recording(self, text):
        messages = self._run(text)
        types = [m.msg_type for m in messages]
        self.assertIn(f"{SKILL_ID}:start_recording.intent", types)
        self.assertIn("mycroft.skill.handler.complete", types)

    def test_start_recording_plain(self):
        self._assert_start_recording("start recording")

    def test_begin_audio_capture(self):
        self._assert_start_recording("begin audio capture")

    def test_initiate_audio_recording(self):
        self._assert_start_recording("initiate audio recording")

    def test_record_audio_now(self):
        self._assert_start_recording("record audio now")

    def test_start_recording_named_slot(self):
        self._assert_start_recording("start a new recording named holiday")

    def test_activate_audio_recording_titled_slot(self):
        self._assert_start_recording("activate audio recording under the title meeting")
