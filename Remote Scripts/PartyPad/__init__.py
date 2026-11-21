import os
import sys

# PartyPad shares genre kits, mix helpers and the phrase finder with LoopPad,
# which lives next to it
_remote_scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _remote_scripts not in sys.path:
    sys.path.append(_remote_scripts)

from .PartyPad import PartyPad


def create_instance(c_instance):
    return PartyPad(c_instance)
