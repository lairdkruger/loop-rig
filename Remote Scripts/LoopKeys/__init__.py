import os
import sys

# LoopKeys shares genre definitions with LoopPad, which lives next to it
_remote_scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _remote_scripts not in sys.path:
    sys.path.append(_remote_scripts)

from .LoopKeys import LoopKeys


def create_instance(c_instance):
    return LoopKeys(c_instance)
