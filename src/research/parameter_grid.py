"""Enumerate frozen parameter domains without reading performance results."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from itertools import product
from math import prod


def _value(value):
    if isinstance(value, bool):
        raise ValueError("boolean parameter values are not supported")
    try:
        return Decimal(str(value)).normalize()
    except InvalidOperation:
        return str(value)


def variants_from_grid(spec: dict) -> list[str]:
    if "groups" in spec:
        groups = spec["groups"]
        if not groups:
            raise ValueError("parameter grid groups must not be empty")
        variants = ["baseline"] if spec.get("include_baseline", True) else []
        maximum = int(spec.get("max_combinations", 1_000_000))
        for group in groups:
            if "groups" in group:
                raise ValueError("nested parameter grid groups are not supported")
            variants.extend(variants_from_grid({**group, "include_baseline": False,
                                                "max_combinations": maximum}))
            if len(variants) > maximum + int(spec.get("include_baseline", True)):
                raise ValueError("parameter domain exceeds max_combinations; narrow it before running")
        if len(variants) != len(set(variants)):
            raise ValueError("duplicate variant ids")
        return variants
    axes = spec["axes"]
    if not axes or len(axes) > 4:
        raise ValueError("parameter grid needs 1-4 axes")
    names = list(axes)
    values = []
    maximum = int(spec.get("max_combinations", 1_000_000))
    if maximum < 1:
        raise ValueError("max_combinations must be positive")
    for name in names:
        axis = axes[name]
        if "values" in axis:
            selected = [_value(item) for item in axis["values"]]
            if not selected or len(selected) != len(set(selected)):
                raise ValueError(f"empty or duplicate values: {name}")
            values.append(selected)
            continue
        start, stop, step = (Decimal(str(axis["start"])), Decimal(str(axis["stop"])),
                             Decimal(str(axis.get("step", 1))))
        if stop < start or step <= 0:
            raise ValueError(f"invalid numeric domain: {name}")
        count = int((stop - start) // step) + 1
        if count > maximum:
            raise ValueError("parameter domain exceeds max_combinations; narrow it before running")
        values.append([(start + index * step).normalize() for index in range(count)])
    constraints = spec.get("less_than", [])
    if prod(len(axis) for axis in values) > maximum:
        raise ValueError("parameter domain exceeds max_combinations; narrow it before running")
    if any(len(pair) != 2 or pair[0] not in axes or pair[1] not in axes
           for pair in constraints):
        raise ValueError("less_than references unknown axes")
    variants = []
    if spec.get("include_baseline", True):
        variants.append("baseline")
    for combo in product(*values):
        params = dict(zip(names, combo))
        if all(isinstance(params[left], Decimal) and isinstance(params[right], Decimal)
               and params[left] < params[right] for left, right in constraints):
            variants.append(spec["variant_template"].format(
                **{key: format(value, "f") if isinstance(value, Decimal) else value
                   for key, value in params.items()}))
    if len(variants) != len(set(variants)):
        raise ValueError("duplicate variant ids")
    if not variants:
        raise ValueError("empty parameter grid")
    return variants
