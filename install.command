#!/bin/bash
# Installs the Loop Rig scripts (LoopPad, LoopKeys, LoopPitch, PartyPad) and
# the genre presets into this Mac's Ableton User Library.
# Double-click it in Finder, or run: ./install.command ["/path/to/User Library"]
set -e
cd "$(dirname "$0")"

TARGET="${1:-$HOME/Music/Ableton/User Library}"
if [ ! -d "$TARGET" ]; then
    echo "No User Library at: $TARGET"
    echo "Find yours in Live: Settings > Library > Location of User Library,"
    echo "then run:  ./install.command \"/path/to/User Library\""
    exit 1
fi

if [ "$(cd "$TARGET" && pwd -P)" = "$(pwd -P)" ]; then
    echo "This is already the User Library - nothing to copy."
    exit 0
fi

echo "Installing into: $TARGET"
mkdir -p "$TARGET/Remote Scripts"
for script in LoopPad LoopKeys LoopPitch PartyPad; do
    rm -rf "$TARGET/Remote Scripts/$script"
    cp -R "Remote Scripts/$script" "$TARGET/Remote Scripts/$script"
    find "$TARGET/Remote Scripts/$script" -name __pycache__ -prune -exec rm -rf {} +
    echo "  script  $script"
done

# Genre presets ("1-kit", "2-keys-1"...), into the same folders
find Presets -type f \( -name '[1-4]-*.adg' -o -name '[1-4]-*.adv' \) | while read -r preset; do
    mkdir -p "$TARGET/$(dirname "$preset")"
    cp "$preset" "$TARGET/$preset"
    echo "  preset  $(basename "$preset")"
done

cat <<'DONE'

Done. Now in Ableton Live:
  1. Plug in the Launchpad X.
  2. Settings > Link, Tempo & MIDI > a free Control Surface slot:
       Control Surface: PartyPad   Input: LPX MIDI   Output: LPX MIDI
  3. In the MIDI Ports list below, LPX MIDI Input: switch Track On.
  4. Restart Live, open a set (his project or a new one), and hold the
     Launchpad's top-right round button for 2 seconds to build the tracks.
DONE
