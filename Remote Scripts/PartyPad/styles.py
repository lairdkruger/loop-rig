"""
PartyPad sounds: the Mic track's vocal chain, the vocal styles that set it,
and the DJ effects on the Main track.

Parameters are set by their displayed value, as in LoopPad's mix.py
(dB, Hz, ms, %, semitones). Every device here is in Live 12 Lite.
"""

# ------------------------------------------------------------ vocal chain ---

# The Mic track's chain, in order: (our name, Live device, settings applied
# once when it's built). Styles then switch devices on/off and tweak them.
VOCAL_CHAIN = [
    ("Vox Comp", "Compressor", [("Threshold", -24.0), ("Ratio", 3.0), ("Attack", 5.0),
                                ("Release", 80.0), ("Output", 4.0)]),
    # Auto Shift in audio mode: Scale Aware off, so it uses its own Root and
    # Scale, which the key pads set (and the song's scale is set to match)
    ("Tune", "Auto Shift", [("Quantizer On", True), ("Scale Aware", False), ("Latch", False),
                            ("Formant Follow", True), ("Dry/Wet", 100.0)]),
    ("Grit", "Saturator", [("Drive", 6.0), ("Output", -4.0)]),
    ("Tone", "Auto Filter", [("Filter Type", "Band"), ("Frequency", 1500.0), ("Resonance", 30.0)]),
    ("Double", "Chorus-Ensemble", [("Mode", "Ensemble"), ("Dry/Wet", 40.0)]),
    ("Crush", "Redux", [("Bit Depth", 8.0), ("Sample Rate", 8000.0), ("Dry/Wet", 40.0)]),
    ("Echo", "Delay", [("Link", True), ("Ping Pong", False), ("L Sync", True),
                       ("Feedback", 25.0), ("Dry/Wet", 18.0)]),
    ("Verb", "Reverb", [("Predelay", 20.0), ("Decay Time", 1800.0), ("Room Size", 60.0),
                        ("Dry/Wet", 15.0)]),
    ("Vox Limit", "Limiter", [("Ceiling", -1.0)]),
]

# Always on, whatever the style (Tune is switched by the TUNE button instead)
ALWAYS_ON = ("Vox Comp", "Verb", "Vox Limit")

# Second Auto Shift, straight after Tune, for styles that list it (TRAVIS):
# blends in an octave-down copy of the tuned voice. It's only on the track
# while such a style is on, as even a switched-off Auto Shift delays the vocal.
LOW_OCT = ("Low Oct", "Auto Shift", [("Quantizer On", True), ("Scale Aware", False),
                                     ("Latch", False), ("Strength", 100.0), ("Smooth On", False),
                                     ("Pitch St.", -12.0), ("Formant Follow", True),
                                     ("Dry/Wet", 30.0)])

# The Auto Shifts the key pads set
TUNERS = ("Tune", "Low Oct")

# Every style starts from these, then sets its own. ("16ths", n) sets a
# synced Delay's time in 16th notes.
STYLE_DEFAULTS = {
    "Verb": [("Decay Time", 1800.0), ("Diff. Hi On", False)],
    "Echo": [("16ths", 2), ("Feedback", 25.0)],  # 1/8
    "Double": [("Width", 100.0)],
}

HARD_TUNE = [("Strength", 100.0), ("Smooth On", False), ("Pitch St.", 0.0)]

# Vocal styles, row 6 left to right: (label, palette colour, {device: params}).
# A device listed is switched on and set; any other (outside ALWAYS_ON) is off.
STYLES = [
    ("Clean", 3, {  # light, natural correction
        "Tune": [("Strength", 55.0), ("Smooth On", True), ("Smooth Time", 80.0),
                 ("Pitch St.", 0.0)],
        "Verb": [("Dry/Wet", 15.0)]}),
    ("Auto-Tune", 21, {  # hard, robotic snap between notes (T-Pain)
        "Tune": HARD_TUNE,
        "Verb": [("Dry/Wet", 15.0)]}),
    ("Travis", 9, {  # Travis Scott: hard tune with an octave-down layer, wide double,
        # some drive, a long 1/4 echo and a big dark reverb
        "Tune": [("Strength", 100.0), ("Smooth On", True), ("Smooth Time", 20.0),
                 ("Pitch St.", 0.0)],
        "Low Oct": [("Dry/Wet", 30.0)],
        "Double": [("Mode", "Ensemble"), ("Width", 150.0), ("Dry/Wet", 45.0)],
        "Grit": [("Drive", 8.0), ("Output", -5.0)],
        "Echo": [("16ths", 4), ("Feedback", 45.0), ("Dry/Wet", 22.0)],
        "Verb": [("Decay Time", 3500.0), ("Diff. Hi On", True), ("Diff. Hi Freq", 2500.0),
                 ("Dry/Wet", 30.0)]}),
    ("Chipmunk", 13, {  # octave up, formants follow (that's the chipmunk)
        "Tune": [("Strength", 80.0), ("Smooth On", False), ("Pitch St.", 12.0),
                 ("Formant Follow", True)],
        "Verb": [("Dry/Wet", 12.0)]}),
    ("Monster", 5, {  # octave down, driven
        "Tune": [("Strength", 80.0), ("Smooth On", False), ("Pitch St.", -12.0),
                 ("Formant Follow", True)],
        "Grit": [("Drive", 9.0), ("Output", -5.0)],
        "Verb": [("Dry/Wet", 20.0)]}),
    ("Robot", 37, {  # hard tune into a short resonant comb and a bitcrush
        "Tune": HARD_TUNE,
        "Double": [("Mode", "Classic"), ("Rate", 0.1), ("Amount", 0.0), ("Delay Time", 5.0),
                   ("Feedback", 85.0), ("Dry/Wet", 50.0)],
        "Crush": [("Bit Depth", 8.0), ("Sample Rate", 8000.0), ("Dry/Wet", 35.0)],
        "Verb": [("Dry/Wet", 10.0)]}),
    ("Radio", 45, {  # telephone/radio band, driven
        "Tune": [("Strength", 55.0), ("Smooth On", True), ("Pitch St.", 0.0)],
        "Tone": [("Filter Type", "Band"), ("Frequency", 1500.0), ("Resonance", 30.0)],
        "Grit": [("Drive", 10.0), ("Output", -6.0)],
        "Verb": [("Dry/Wet", 8.0)]}),
]

# BIG VERB (row 6, col 8): laid over whichever style is on
BIG_VERB = [("Decay Time", 4500.0), ("Dry/Wet", 40.0)]

# ------------------------------------------------------------- DJ effects ---

# On the Main track, before anything already there. All sit at no effect
# until their pad is held.
DJ_CHAIN = [
    # Stutter: a Delay heard 100% wet with Freeze on loops the last 1/4 or 1/8
    ("DJ Stutter", "Delay", [("Link", True), ("Ping Pong", False), ("L Sync", True),
                             ("Feedback", 0.0), ("Freeze", False), ("Dry/Wet", 0.0)]),
    ("DJ Echo", "Delay", [("Link", True), ("Ping Pong", True), ("L Sync", True),
                          ("Feedback", 55.0), ("Freeze", False), ("Dry/Wet", 0.0)]),
    ("DJ LPF", "Auto Filter", [("Filter Type", "Low"), ("Frequency", 20000.0),
                               ("Resonance", 30.0)]),
    ("DJ HPF", "Auto Filter", [("Filter Type", "High"), ("Frequency", 20.0),
                               ("Resonance", 30.0)]),
    ("DJ Wash", "Reverb", [("Predelay", 10.0), ("Decay Time", 6000.0), ("Room Size", 100.0),
                           ("Dry/Wet", 0.0)]),
]

ECHO_DJ_SIXTEENTHS = 3       # dotted 1/8
ECHO_WET = 35.0              # while ECHO is held
WASH_WET = 55.0              # while WASH is held
FILTER_SWEEP_TICKS = 20      # ~2 s from open to closed while held
LPF_RANGE = (20000.0, 250.0)  # Hz: open -> fully swept
HPF_RANGE = (20.0, 2500.0)
TAIL_TICKS = 20              # ECHO and WASH fade out over ~2 s after release
