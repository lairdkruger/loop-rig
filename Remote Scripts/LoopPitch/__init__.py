import os
import sys

# LoopPitch uses LoopPad's shared helpers; LoopPad lives next to it
_remote_scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _remote_scripts not in sys.path:
    sys.path.append(_remote_scripts)

from .LoopPitch import LoopPitch


def create_instance(c_instance):
    return LoopPitch(c_instance)
