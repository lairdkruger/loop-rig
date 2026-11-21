# Loop Rig

Ableton Live 12 Lite control surface scripts for a Launchpad X (and a Launchkey MK2):

- **LoopPad / LoopKeys / LoopPitch** – the home live-looping rig.
- **PartyPad** – karaoke/party mode for the Launchpad X alone: auto-tune to the song's key, vocal styles, DJ effects, genre drum kits and hold-to-record vocal chops.

This repo *is* an Ableton User Library. Only the scripts and the genre presets (`1-kit`, `2-keys-1`…) are tracked.

## Setting up on another Mac

1. Get the code (no git? use **Code > Download ZIP** on GitHub and unzip it):
   ```
   git clone https://github.com/lairdkruger/loop-rig.git ~/loop-rig
   ```
2. Double-click `install.command` (or run `~/loop-rig/install.command`). It copies the scripts and presets into `~/Music/Ableton/User Library`. If Live's User Library is somewhere else (Settings > Library), pass that path instead: `./install.command "/path/to/User Library"`.
3. Plug in the Launchpad X. In Live: **Settings > Link, Tempo & MIDI**:
   - Control Surface: **PartyPad**, Input: **LPX MIDI**, Output: **LPX MIDI**
   - MIDI Ports: **LPX MIDI** input: **Track** On
4. In **Settings > Audio**: pick the mic's interface as the input device, a buffer of **128 samples**, and wired speakers or headphones (Bluetooth adds a lot of delay).
5. Restart Live. Open his project (or a new set) and **hold the top-right round button for 2 s**. This adds the Song, Mic, Chop Rec, Pads and Chops tracks, and leaves every other track alone. Lite allows 8 tracks, so the project can have at most 3 others.

Needs Live **12.1 or newer** (Auto Shift).

## Party flow

1. Download the song's audio, ideally a karaoke/instrumental version (e.g. `yt-dlp -x --audio-format wav <url>`), and drag it into a clip slot on **Song**. Live warps it and PartyPad sets the tempo from it.
2. Look up the key (tunebat.com, songbpm.com) and tap it on the Launchpad's keys: row 7 is the white keys from A, row 8 the sharps, and the right-hand pad switches **major (yellow) / minor (purple)**.
3. Pick a vocal style, press **SONG**, and sing.
4. If the mic is silent, tap **MIC IN** to step through the inputs (it lights with the level).

## PartyPad layout

```
round:  GENRE1 GENRE2 GENRE3 GENRE4  SONG▶■   MIC IN  TUNE   BUILD(hold)
row 8   A#     ·      C#     D#      ·        F#      G#     ·          CHOP REC (hold + pad)
row 7   A      B      C      D       E        F       G      MAJ/MIN    CHOP CLEAR (hold + pad)
row 6   CLEAN  AUTO   TRAVIS CHIPMNK MONSTER  ROBOT   RADIO  BIG VERB   TAP TEMPO
row 5   STUT¼  STUT⅛  ECHO   LPF     HPF      WASH    DROP   RESET      TEMPO +1
rows 1-4  [ 4x4 drums: genre kit ]  [ 4x4 vocal chops ]                 TEMPO -1 / SONG TEMPO
```

- **Styles**: one at a time. **TUNE** switches the auto-tune off and on.
- **DJ effects**: hold the pad. They affect the whole mix, vocal included. **DROP** mutes the song while held.
- **Chops**: hold an empty (dim pink) pad and sing to record into it. Press a full (bright pink) pad to play it. Hold **CHOP REC** + a pad to re-record it, **CHOP CLEAR** + a pad to empty it, or hold **CHOP CLEAR** alone for 2 s to empty them all.
- **Genres**: 1 House/DnB, 2 Hip Hop, 3 Jazz, 4 Surf. These load the drum kit only (your saved `N-kit` presets win over the built-ins).

Vocal chain and style settings are in `Remote Scripts/PartyPad/styles.py`.
