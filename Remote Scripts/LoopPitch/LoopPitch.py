"""
LoopPitch - steers the Sampler chops' pitch from the Launchkey keys, for
Ableton Live 12 Lite. Companion to LoopPad and LoopKeys.

Runs on the "Launchkey MIDI" port (the keys), with no output. While PITCH is
on (LoopPad's PITCH pad), this script takes the keys away from the Keys track:
the key you hold sets the pitch the chops play at, and the Launchpad chop pads
pick which chop plays. C3 is the sample's own pitch; with no key held the
chops play at their own pitch. Holding several keys, the last one wins, and
letting it go falls back to the one before.

While PITCH is off it takes nothing, so the keys play the Keys track as normal.
"""

import Live
from _Framework.ControlSurface import ControlSurface
from LoopPad import shared


class LoopPitch(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._tick = 0
        self._held = []  # notes held, oldest first
        self._pitch_on = self._read_pitch()
        self.log_message("LoopPitch: init")

    def disconnect(self):
        self._held = []
        self._apply()
        ControlSurface.disconnect(self)

    def _read_pitch(self):
        return bool(self.song().get_data(shared.PITCH_KEY, False))

    def build_midi_map(self, midi_map_handle):
        if not self._pitch_on:
            return  # leave the keys to the Keys track
        handle = self._c_instance.handle()
        for channel in range(16):
            for note in range(128):
                Live.MidiMap.forward_midi_note(handle, midi_map_handle, channel, note)

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) != 3:
            return
        status, note, velocity = midi_bytes
        kind = status & 0xF0
        if kind not in (0x80, 0x90):
            return
        if note in self._held:
            self._held.remove(note)
        if kind == 0x90 and velocity > 0:
            self._held.append(note)
        self._apply()

    def _apply(self):
        try:
            semitones = self._held[-1] - shared.PITCH_ROOT_NOTE if self._held else 0
            shared.set_chop_transpose(self.song(), semitones)
        except Exception as e:
            self.log_message("LoopPitch: error: %r" % (e,))

    def update_display(self):
        ControlSurface.update_display(self)
        self._tick += 1
        if self._tick % 3 == 0:
            on = self._read_pitch()
            if on != self._pitch_on:
                self._pitch_on = on
                self._held = []
                self._apply()
                self.request_rebuild_midi_map()

