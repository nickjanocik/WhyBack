"""Small immutable container helpers for authoritative nested model state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Never, TypeVar, cast

K = TypeVar("K")
V = TypeVar("V")


class FrozenDict(dict[K, V]):
    """A JSON-serializable dictionary that rejects every mutation operation."""

    @staticmethod
    def _immutable(*_args: object, **_kwargs: object) -> Never:
        """Reject any dictionary mutation routed through an aliased method."""

        raise TypeError("FrozenDict is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __copy__(self) -> FrozenDict[K, V]:
        """Return this immutable dictionary because a shallow copy is unnecessary."""

        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> FrozenDict[K, V]:
        """Return this recursively frozen dictionary for deep-copy operations."""

        return self


class FrozenList(list[V]):
    """A JSON-compatible list that rejects every mutation operation."""

    @staticmethod
    def _immutable(*_args: object, **_kwargs: object) -> Never:
        """Reject any list mutation routed through an aliased method."""

        raise TypeError("FrozenList is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable

    def __copy__(self) -> FrozenList[V]:
        """Return this immutable list because a shallow copy is unnecessary."""

        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> FrozenList[V]:
        """Return this recursively frozen list for deep-copy operations."""

        return self


def freeze_json(value: Any) -> Any:
    """Recursively freeze JSON-shaped mappings and sequences."""

    if isinstance(value, Mapping):
        return FrozenDict({str(key): freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return FrozenList(freeze_json(item) for item in value)
    return value


def frozen_mapping[V](value: Mapping[str, V]) -> dict[str, V]:
    """Return a deeply frozen mapping while preserving dict-compatible typing."""

    return cast(dict[str, V], freeze_json(value))
