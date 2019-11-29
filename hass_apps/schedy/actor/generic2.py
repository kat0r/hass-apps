"""
This module implements the generic actor.
"""

import typing as T

import copy

import voluptuous as vol

from ... import common
from .base import ActorBase


ALLOWED_VALUE_TYPES = (float, int, str, type(None))
ALLOWED_VALUE_TYPES_T = T.Union[float, int, str, None]  # pylint: disable=invalid-name
WILDCARD_VALUE = "*"


class Generic2Actor(ActorBase):
    """A configurable, generic actor for Schedy that can control multiple
    attributes at once."""

    name = "generic2"
    config_schema_dict = {
        **ActorBase.config_schema_dict,
        vol.Optional("slots", default=None): vol.All(
            vol.DefaultTo(list),
            [vol.All(vol.DefaultTo(dict), {vol.Required("attribute"): str})],
        ),
        vol.Optional("values", default=None): vol.All(
            vol.DefaultTo(list),
            [
                vol.All(
                    vol.DefaultTo(dict),
                    {
                        vol.Required("slots"): vol.All(
                            [vol.Any(*ALLOWED_VALUE_TYPES)], vol.Coerce(tuple)
                        ),
                        vol.Optional("calls", default=None): vol.All(
                            vol.DefaultTo(list),
                            [
                                vol.All(
                                    vol.DefaultTo(dict),
                                    {
                                        vol.Required("service"): str,
                                        vol.Optional("data", default=None): vol.All(
                                            vol.DefaultTo(dict), dict
                                        ),
                                        vol.Optional(
                                            "include_entity_id", default=True
                                        ): bool,
                                    },
                                )
                            ],
                        ),
                    },
                )
            ],
            # Sort by number of slots in descending order for longest prefix matching
            lambda v: sorted(v, key=lambda k: -len(k["slots"])),
        ),
    }

    def _find_value_cfg(self, value: T.Tuple) -> T.Any:
        for value_cfg in self.cfg["values"]:
            slots = value_cfg["slots"]
            if len(slots) != len(value):
                continue
            for idx, slot in enumerate(slots):
                if slot not in (WILDCARD_VALUE, value[idx]):
                    break
            else:
                return value_cfg
        raise ValueError("No configuration for value {!r}".format(value))

    @staticmethod
    def _populate_service_data(data: T.Dict, fmt: T.Dict[str, T.Any]) -> None:
        memo = set((data,))  # type: T.Set[T.Union[T.Dict, T.List]]
        while memo:
            obj = memo.pop()
            if isinstance(obj, dict):
                _iter = obj.items()  # type: T.Iterable[T.Tuple[T.Any, T.Any]]
            elif isinstance(obj, list):
                _iter = enumerate(obj)
            else:
                continue
            for key, value in _iter:
                if isinstance(value, str):
                    obj[key] = value.format(fmt)
                elif isinstance(value, (dict, list)):
                    memo.add(value)

    def do_send(self) -> None:
        """Executes the configured services for self._wanted_value."""
        value = self._wanted_value
        fmt = {"entity_id": self.entity_id}
        for idx, slot_cfg in enumerate(self.cfg["slots"]):
            fmt["slot{}".format(idx)] = value[idx] if idx < len(value) else None

        for call_cfg in self._find_value_cfg(value)["calls"]:
            service = call_cfg["service"]
            data = copy.deepcopy(call_cfg["data"])
            self._populate_service_data(data, fmt)
            if call_cfg["include_entity_id"]:
                data.setdefault("entity_id", self.entity_id)
            self.log(
                "Calling service {}, data = {}.".format(repr(service), repr(data)),
                level="DEBUG",
                prefix=common.LOG_PREFIX_OUTGOING,
            )
            self.app.call_service(service, **data)

    def filter_set_value(self, value: T.Tuple) -> T.Any:
        """Checks whether the actor supports this value."""
        try:
            self._find_value_cfg(value)
        except ValueError:
            self.log(
                "Value {!r} is not known by this actor.".format(value), level="ERROR"
            )
            return None
        return value

    def notify_state_changed(self, attrs: dict) -> T.Any:
        """Is called when the entity's state changes."""
        items = []
        for slot_cfg in self.cfg["slots"]:
            attr = slot_cfg["attribute"]
            state = attrs.get(attr)
            self.log(
                "Attribute {!r} is {!r}.".format(attr, state),
                level="DEBUG",
                prefix=common.LOG_PREFIX_INCOMING,
            )
            items.append(state)

        tpl = tuple(items)
        # Goes from len(tpl) down to 0
        for size in range(len(tpl), -1, -1):
            value = tpl[:size]
            try:
                self._find_value_cfg(value)
            except ValueError:
                continue
            return value

        self.log(
            "Received state {!r} which is not configured as a value.".format(items),
            level="WARNING",
        )
        return None

    @staticmethod
    def validate_value(value: T.Any) -> T.Any:
        """Converts lists to tuples."""
        if isinstance(value, list):
            items = tuple(value)
        elif isinstance(value, tuple):
            items = value
        else:
            items = (value,)

        for index, item in enumerate(items):
            if not isinstance(item, ALLOWED_VALUE_TYPES):
                raise ValueError(
                    "Value {!r} for slot {} must be of one of these types: {}".format(
                        item, index, ALLOWED_VALUE_TYPES
                    )
                )
        return items
