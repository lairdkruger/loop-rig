"""
Phrase finder for SLICE: reads a WAV file and splits it into phrases, the
stretches of sound between gaps of silence, for vocals and other sustained
material where drum-style transient detection gives sub-syllable slivers.

Plain Python (Live's Python has no audioop or numpy), so it only looks at a
short block of frames every few milliseconds to build a loudness envelope.
"""

import struct

WINDOW_MS = 10       # envelope resolution
BLOCK_FRAMES = 96    # frames read per window to estimate its loudness
SILENCE_DB = -36.0   # quieter than this below the file's peak counts as silence
MIN_GAPS_MS = [600, 400, 250, 150, 100, 60]  # tried longest first: whole phrases before words
MIN_SOUND_MS = 150   # shorter bursts (clicks, breaths) are dropped
PRE_ROLL_MS = 15     # start this much before the sound, so its attack isn't clipped
TAIL_MS = 60         # and run on this long after it, for the decay


def _read_wav_header(f):
    """(channels, sample_rate, bits, is_float, data_offset, frame_count) or None."""
    if f.read(4) != b"RIFF":
        return None
    f.read(4)
    if f.read(4) != b"WAVE":
        return None
    fmt = None
    while True:
        head = f.read(8)
        if len(head) < 8:
            return None
        chunk, size = struct.unpack("<4sI", head)
        if chunk == b"fmt ":
            body = f.read(size)
            tag, channels, rate = struct.unpack("<HHI", body[:8])
            bits = struct.unpack("<H", body[14:16])[0]
            if tag == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = (channels, rate, bits, tag == 3)
        elif chunk == b"data":
            if fmt is None:
                return None
            channels, rate, bits, is_float = fmt
            return channels, rate, bits, is_float, f.tell(), size // (channels * bits // 8)
        else:
            f.seek(size + (size & 1), 1)


def _block_peak(raw, channels, bits, is_float):
    """Peak level (0..1) of a block of interleaved frames, first channel only."""
    width = bits // 8
    step = channels * width
    peak = 0.0
    for i in range(0, len(raw) - step + 1, step):
        if is_float and bits == 32:
            v = abs(struct.unpack_from("<f", raw, i)[0])
        elif bits == 16:
            v = abs(struct.unpack_from("<h", raw, i)[0]) / 32768.0
        elif bits == 24:
            v = abs(struct.unpack_from("<i", b"\0" + raw[i:i + 3])[0]) / 2147483648.0
        elif bits == 32:
            v = abs(struct.unpack_from("<i", raw, i)[0]) / 2147483648.0
        else:
            return None
        if v > peak:
            peak = v
    return peak


def envelope(path):
    """(sample_rate, frame_count, window_frames, [peak per window]) or None."""
    try:
        with open(path, "rb") as f:
            header = _read_wav_header(f)
            if header is None:
                return None
            channels, rate, bits, is_float, offset, frames = header
            window = max(1, int(rate * WINDOW_MS / 1000))
            frame_bytes = channels * bits // 8
            env = []
            for start in range(0, frames, window):
                f.seek(offset + start * frame_bytes)
                peak = _block_peak(f.read(min(BLOCK_FRAMES, window) * frame_bytes),
                                   channels, bits, is_float)
                if peak is None:
                    return None
                env.append(peak)
            return rate, frames, window, env
    except (IOError, OSError, struct.error):
        return None


def _runs(loud, min_gap, min_sound):
    """[(first, last+1)] windows of sound, merging across gaps under min_gap
    windows and dropping bursts under min_sound windows."""
    runs = []
    start = None
    quiet = 0
    for i, on in enumerate(loud + [False] * (min_gap + 1)):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= min_gap:
                end = i - quiet + 1
                if end - start >= min_sound:
                    runs.append((start, min(end, len(loud))))
                start = None
                quiet = 0
    return runs


def _split_longest(runs, env, count):
    """Split the longest runs at their quietest window until there are count."""
    runs = list(runs)
    while len(runs) < count:
        i = max(range(len(runs)), key=lambda k: runs[k][1] - runs[k][0])
        a, b = runs[i]
        margin = max(1, (b - a) // 5)  # don't cut right by either end
        if b - a < 4:
            break
        cut = min(range(a + margin, b - margin), key=lambda k: env[k])
        runs[i:i + 1] = [(a, cut), (cut, b)]
    return runs


def find_phrases(path, count):
    """count (start, end) frame ranges, one phrase each, in order, or None if
    the file can't be read (not a WAV) or is silent."""
    result = envelope(path)
    if result is None:
        return None
    rate, frames, window, env = result
    top = max(env) if env else 0.0
    if top <= 0.0:
        return None
    threshold = top * 10 ** (SILENCE_DB / 20.0)
    loud = [v >= threshold for v in env]
    ms = lambda n: max(1, int(n / WINDOW_MS))
    runs = []
    # Longest gaps first: whole phrases. Fall back to shorter gaps (words)
    # until there are enough; then cut the longest phrases at their quietest.
    for gap in MIN_GAPS_MS:
        runs = _runs(loud, ms(gap), ms(MIN_SOUND_MS))
        if len(runs) >= count:
            break
    if not runs:
        return None
    if len(runs) < count:
        runs = _split_longest(runs, env, count)
        if len(runs) < count:
            return None  # too little sound to make count chops
    if len(runs) > count:  # spread the picks across the whole file
        runs = [runs[int(round(i * (len(runs) - 1) / float(count - 1)))] for i in range(count)]
    pre, tail = ms(PRE_ROLL_MS), ms(TAIL_MS)
    ranges = []
    for a, b in runs:
        start = max(0, (a - pre) * window)
        end = min(frames - 1, (b + tail) * window)
        ranges.append((start, max(end, start + 1)))
    return ranges
