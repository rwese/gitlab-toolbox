"""Canonical JSON serialization for all toolbox output.

Drop-in replacement for the stdlib :mod:`json` module. Import it as ``json``
so existing call sites keep working::

    from ..formatters import json_output as json

    json.dumps(payload, indent=2)

``dumps``/``dump`` force stable, sorted key order so that output is byte-for-byte
reproducible across runs and API response orderings. Everything else (``load``,
``loads``, ``JSONDecodeError``, ...) is re-exported from the stdlib unchanged.
"""

import json as _json
from typing import IO, Any, Dict

# Re-exported stdlib names so this module can stand in for ``json``.
JSONDecodeError = _json.JSONDecodeError
JSONDecoder = _json.JSONDecoder
JSONEncoder = _json.JSONEncoder
load = _json.load
loads = _json.loads

__all__ = [
    "JSONDecodeError",
    "JSONDecoder",
    "JSONEncoder",
    "dump",
    "dumps",
    "load",
    "loads",
]

# Serialization defaults applied to every dumps()/dump() call.
_DEFAULTS: Dict[str, Any] = {"sort_keys": True, "default": str}


def dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize ``obj`` to a JSON string with stable key ordering.

    Args:
        obj: Object to serialize
        **kwargs: Passed through to :func:`json.dumps`

    Returns:
        JSON string with keys sorted at every level
    """
    return _json.dumps(obj, **{**_DEFAULTS, **kwargs})


def dump(obj: Any, fp: IO[str], **kwargs: Any) -> None:
    """Serialize ``obj`` as JSON to ``fp`` with stable key ordering.

    Args:
        obj: Object to serialize
        fp: Writable file-like object
        **kwargs: Passed through to :func:`json.dump`
    """
    _json.dump(obj, fp, **{**_DEFAULTS, **kwargs})
