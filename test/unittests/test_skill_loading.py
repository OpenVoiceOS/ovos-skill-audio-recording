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

        # ovos-workshop>=9.3.12a1 / OVOS-INTENT-2 registers the intent under
        # the bare basename (no ".intent" suffix) -- same naming fix
        # documented in this repo's e2e suite (test_intents_en_us.py).
        registrations = [m for m in captured
                         if m.data.get("name", "").endswith(":start_recording")]
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


class TestNameEntityRegistration(unittest.TestCase):
    """Unit-level, no-MiniCroft proof that ``name.entity`` reaches the
    padatious pipeline with NO manual ``register_entity_file()`` call
    anywhere in this skill.

    ovos-workshop>=9.5.0a1 auto-registers every ``.entity`` file shipped
    under a skill's locale resources the first time that language's
    resources are loaded (during ``_startup()``) -- no skill-authored
    wiring required. This test boots the skill via ``_startup()`` alone
    and asserts the ``padatious:register_entity`` message for "name"
    landed on the bus with the expected sample values.

    Mutation tripwire: delete/rename
    ``locale/en-US/intents/name.entity`` and this test goes red -- there
    is nothing left in the skill to register it, since discovery walks
    the on-disk locale/ directory.

    NOTE: an ``*.entity`` file is training-data bias for a padatious
    ``{slot}``, not an admission-control allowlist -- an unlisted value
    remains capturable by the slot. This test only proves the entity
    reaches the engine, not that unknown values get rejected.
    """

    def test_name_entity_reaches_padatious_on_startup(self):
        bus = FakeBus()
        captured = []
        bus.on("padatious:register_entity", captured.append)

        skill = AudioRecordingSkill()
        skill._startup(bus, SKILL_ID)

        registrations = [m for m in captured
                         if m.data.get("name", "").endswith(":name")]
        self.assertEqual(len(registrations), 1,
                         "name.entity must be registered exactly once with the intent engine")
        samples = registrations[0].data.get("samples") or []
        # sample titles drawn straight from locale/en-US/intents/name.entity
        self.assertIn("meeting", samples)
        self.assertIn("podcast episode", samples)


if __name__ == "__main__":
    unittest.main()
