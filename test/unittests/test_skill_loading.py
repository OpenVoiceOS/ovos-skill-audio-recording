"""Lightweight (no e2e stack) unit coverage for ovos-skill-audio-recording.

Covers skill instantiation through every loader entry point and asserts the
sibling ``name.blacklist`` guard vocabulary is picked up and forwarded to the
Padatious intent registration, so filler words like "usual" can never bind the
``{name}`` recording title.
"""
import unittest
from os.path import dirname

from ovos_bus_client.message import Message
from ovos_plugin_manager.skills import find_skill_plugins
from ovos_utils.messagebus import FakeBus
from ovos_workshop.skill_launcher import PluginSkillLoader, SkillLoader

import ovos_skill_audio_recording as skill_module
from ovos_skill_audio_recording import AudioRecordingSkill

SKILL_ID = "ovos-skill-audio-recording.openvoiceos"


class TestSkillLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_id = SKILL_ID
        cls.path = dirname(dirname(dirname(__file__)))

    def test_from_class(self):
        bus = FakeBus()
        skill = AudioRecordingSkill()
        skill._startup(bus, self.skill_id)
        self.assertEqual(skill.bus, bus)
        self.assertEqual(skill.skill_id, self.skill_id)

    def test_from_plugin(self):
        bus = FakeBus()
        for skill_id, plug in find_skill_plugins().items():
            if skill_id == self.skill_id:
                skill = plug()
                skill._startup(bus, self.skill_id)
                self.assertEqual(skill.bus, bus)
                self.assertEqual(skill.skill_id, self.skill_id)
                break
        else:
            raise RuntimeError("plugin not found")

    def test_from_loader(self):
        bus = FakeBus()
        loader = SkillLoader(bus, self.path)
        loader.load()
        self.assertEqual(loader.instance.bus, bus)
        self.assertEqual(loader.instance.root_dir, self.path)

    def test_from_plugin_loader(self):
        bus = FakeBus()
        loader = PluginSkillLoader(bus, self.skill_id)
        for skill_id, plug in find_skill_plugins().items():
            if skill_id == self.skill_id:
                loader.load(plug)
                break
        else:
            raise RuntimeError("plugin not found")
        self.assertEqual(loader.skill_id, self.skill_id)
        self.assertEqual(loader.instance.bus, bus)
        self.assertEqual(loader.instance.skill_id, self.skill_id)


class TestNameBlacklist(unittest.TestCase):
    """The `name.blacklist` locale file must reach the intent registration so
    the engine keeps blacklisted fillers out of the free-form `{name}` title.
    """

    def test_blacklist_forwarded_on_registration(self):
        bus = FakeBus()
        captured = []
        bus.on("padatious:register_intent", captured.append)

        skill = AudioRecordingSkill()
        skill._startup(bus, SKILL_ID)

        registrations = [m for m in captured
                         if m.data.get("name", "").endswith("start_recording.intent")]
        self.assertEqual(len(registrations), 1)

        # the blacklist vocabulary (name.blacklist) is surfaced to the engine
        # either as slot-scoped exclusions for `{name}` or as intent-level
        # blacklisted words, depending on the installed engine capabilities
        data = registrations[0].data
        surfaced = set(data.get("blacklisted_words") or [])
        for phrases in (data.get("slot_blacklist") or {}).values():
            surfaced.update(phrases)

        for filler in ("usual", "normal", "it", "that"):
            self.assertIn(filler, surfaced)


if __name__ == "__main__":
    unittest.main()
