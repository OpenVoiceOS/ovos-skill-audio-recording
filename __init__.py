from datetime import timedelta

from ovos_bus_client.message import Message
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.time import now_local
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill


class AudioRecordingSkill(OVOSSkill):
    def initialize(self):
        self.recording = False
        self.add_event("recognizer_loop:record_stop", self.handle_recording_stop)

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=False,
            network_before_load=False,
            gui_before_load=False,
            requires_internet=False,
            requires_network=False,
            requires_gui=False,
            no_internet_fallback=True,
            no_network_fallback=True,
            no_gui_fallback=True,
        )

    @property
    def max_recording_time(self):
        return self.settings.get("max_recording_seconds", 240)

    @intent_handler("start_recording.intent")
    def handle_start_recording(self, message):
        recording_name = message.data.get("name", str(now_local()))
        self.recording = True
        self.bus.emit(message.forward("recognizer_loop:state.set",
                                      {"state": "recording",
                                       "recording_name": recording_name}))

        def maybe_stop(message):
            if self.recording:
                self.bus.emit(message.forward("recognizer_loop:record_stop"))
                self.recording = False

        # force a way out of recording mode after timeout
        self.schedule_event(maybe_stop, now_local() + timedelta(seconds=self.max_recording_time))

    @intent_handler("start_recording.intent")
    def handle_captains_log(self, message):
        message.data["name"] = message.data.get("name", "captains_log_" + str(now_local()))
        self.handle_start_recording(message)

    def handle_recording_stop(self, message):
        self.recording = False

    def stop(self):
        """Optional action to take when "stop" is requested by the user.
        This method should return True if it stopped something or
        False (or None) otherwise.
        If not relevant to your skill, feel free to remove.
        """
        if self.recording:
            self.recording = False
            self.bus.emit(Message("recognizer_loop:record_stop"))
            return True
        return False
