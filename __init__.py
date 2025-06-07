from datetime import timedelta

from ovos_bus_client.session import SessionManager, Session
from ovos_bus_client.message import Message, dig_for_message
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.time import now_local
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill


class AudioRecordingSkill(OVOSSkill):
    def initialize(self):
        self.recording_sessions = {}
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
        sess = SessionManager.get(message)
        self.recording_sessions[sess.session_id] = dict(
            file_name=recording_name,
            recording=True
        )

        self.bus.emit(message.forward("recognizer_loop:state.set",
                                      {"state": "recording",
                                       "recording_name": recording_name}))

        def maybe_stop(message):
            sess = SessionManager.get(message)
            if self.recording_sessions.get(sess.session_id, {}).get("recording"):
                self.bus.emit(message.forward("recognizer_loop:record_stop"))
                self.recording_sessions[sess.session_id]["recording"] = False

        # force a way out of recording mode after timeout
        self.schedule_event(maybe_stop, now_local() + timedelta(seconds=self.max_recording_time))

    def handle_recording_stop(self, message):
        # keep track of any external (non skill initiated) stops
        sess_id = SessionManager.get(message).session_id
        if self.recording_sessions.get(sess_id, {}).get("recording"):
            self.recording_sessions[sess_id]["recording"] = False

    def stop_session(self, session: Session) -> bool:
        if session.session_id in self.recording_sessions and \
                self.recording_sessions[session.session_id]["recording"]:
            self.recording_sessions[session.session_id]["recording"] = False
            message = dig_for_message()
            self.bus.emit(message.forward("recognizer_loop:record_stop"))
            return True
        return False

    def can_stop(self, message: Message) -> bool:
        sess_id = SessionManager.get(message).session_id
        return self.recording_sessions.get(sess_id, {}).get("recording")

    def stop(self):
        """global stop called"""
        self.bus.emit(Message("recognizer_loop:record_stop"))
