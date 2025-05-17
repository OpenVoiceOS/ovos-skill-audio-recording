# Audio Recording Skill

Record audio to file, requires [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener)

## About

continuously record audio to file and disables wake words/STT while active, made for [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener)

A similar skill that saves text transcriptions instead of recording audio is [OpenVoiceOS/ovos-skill-dictation](https://github.com/OpenVoiceOS/ovos-skill-dictation)

in order to avoid users accidentally locking themselves in recording mode a special kind of wake word called a *stop hotword* can be configured, these special hotwords are only used during recording mode and will restore the listener to default state if detected. By default no *stop hotword* is pre-configured

when started via this skill a audio recording will time out after 4 minutes (max_recording_seconds in skill settings) 

if a `mycroft.stop` bus message is emitted (eg, "stop" via cli) the skill will take dinkum out of recording mode if recording was initiated by this skill

**TODO**: dinkum should have a native (optional) timeout setting, using VAD to automatically stop recording after X seconds of silence


## Examples

- "new recording"
- "start recording"
- "new recording named {file_name}"

## Credits

[NeonGecko](https://github.com/NeonGeckoCom/skill-audio-recording)
