"""
This module implements a binary on/off switch, derived from the generic actor.
"""

from .generic2 import Generic2Actor


class SwitchActor(Generic2Actor):
    """A binary on/off switch actor for Schedy."""

    name = "switch"
    config_defaults = {
        **Generic2Actor.config_defaults,
        "slots": [{"attribute": "state"}],
        "values": [
            {"slots": ["on"], "calls": [{"service": "homeassistant/turn_on"}]},
            {"slots": ["off"], "calls": [{"service": "homeassistant/turn_off"}]},
        ],
    }
