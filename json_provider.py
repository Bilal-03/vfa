"""Emit standard JSON even when external providers return missing numbers."""
import math
from numbers import Integral, Real

from flask.json.provider import DefaultJSONProvider


def finite_values(value):
    if isinstance(value, dict):
        return {key: finite_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_values(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value) if math.isfinite(value) else None
    return value


class FiniteJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs['allow_nan'] = False
        return super().dumps(finite_values(obj), **kwargs)
