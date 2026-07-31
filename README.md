# Audio Recording Skill

This skill records audio to a file. It needs [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener).

## About

The skill records audio to a file and disables wake words and speech-to-text while it is active. It needs [ovos-dinkum-listener](https://github.com/OpenVoiceOS/ovos-dinkum-listener).

A similar skill, [OpenVoiceOS/ovos-skill-dictation](https://github.com/OpenVoiceOS/ovos-skill-dictation), saves text transcriptions instead of audio.

To avoid trapping a user in recording mode, you can configure a *stop hotword*. This special wake word only works during recording mode. When detected, it restores the listener to its default state. By default, no *stop hotword* is set.

A recording started by this skill times out after 4 minutes. Change this limit with the `max_recording_seconds` setting.

If a `mycroft.stop` bus message arrives (for example, "stop" on the CLI), the skill takes dinkum out of recording mode, but only if this skill started the recording.

Dinkum does not yet have a native, optional timeout that uses voice activity detection to stop a recording after a period of silence.

## Examples

- "new recording"
- "start recording"
- "new recording named {file_name}"

## Credits

[NeonGecko](https://github.com/NeonGeckoCom/skill-audio-recording)
