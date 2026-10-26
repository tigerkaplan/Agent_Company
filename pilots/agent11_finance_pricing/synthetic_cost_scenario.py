"""Offline synthetic cost scenario for the accepted Agent 11 design.

The caller supplies every numeric scale and the rounding mode.  This module
contains no currency, tax, pricing, allocation, or business-policy choice and
has no persistence, network, provider, or production-runtime integration.
"""

from dataclasses import dataclass, field
import re
from typing import Literal

from exact_division import divide_scaled_ints


_MAX_ITEMS = 256
_MAX_SCALE = 18
_MAX_MINOR_UNIT_ABS_VALUE = (2**63) - 1
_MAX_INTERMEDIATE_COEFFICIENT_DIGITS = 128
_MAX_WORK_UNITS = 100_000
_ROUNDING_MODES = frozenset({"DOWN", "HALF_UP", "HALF_EVEN"})
_SYNTHETIC_REF = re.compile(r"synthetic:[a-z0-9][a-z0-9._-]{0,63}\Z")


@dataclass(frozen=True, slots=True)
class SyntheticCostItem:
    """One signed synthetic cost coefficient and its inspectable reference."""

    input_ref: str
    coefficient: int


@dataclass(frozen=True, slots=True)
class SyntheticCostRequest:
    """Complete in-memory request for one non-authoritative scenario."""

    items: tuple[SyntheticCostItem, ...]
    common_scale: int
    quantity: int
    output_scale: int
    rounding_mode: str


@dataclass(frozen=True, slots=True)
class ScaledInteger:
    """An exact signed integer coefficient with an explicit decimal scale."""

    coefficient: int
    scale: int


@dataclass(frozen=True, slots=True)
class SyntheticCostResult:
    """Immutable, inspectable result that can never represent authority."""

    input_refs: tuple[str, ...]
    arithmetic_total: ScaledInteger
    per_unit_result: ScaledInteger
    common_scale: int
    output_scale: int
    quantity: int
    rounding_mode: str
    non_authoritative: Literal[True] = field(default=True, init=False)


def _digit_count(value: int) -> int:
    magnitude = abs(value)
    return 1 if magnitude == 0 else len(str(magnitude))


def _require_plain_int(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"invalid_integer_type:{field_name}")
    return value


def _validate_scale(value: object, field_name: str) -> int:
    scale = _require_plain_int(value, field_name)
    if scale < 0 or scale > _MAX_SCALE:
        raise ValueError(f"invalid_scale:{field_name}")
    return scale


def _validate_request(request: SyntheticCostRequest) -> None:
    if type(request) is not SyntheticCostRequest:
        raise TypeError("invalid_request_type")
    if type(request.items) is not tuple:
        raise TypeError("invalid_items_type")
    if not request.items:
        raise ValueError("empty_cost_items")
    if len(request.items) > _MAX_ITEMS:
        raise ValueError("too_many_cost_items")

    _validate_scale(request.common_scale, "common_scale")
    _validate_scale(request.output_scale, "output_scale")

    quantity = _require_plain_int(request.quantity, "quantity")
    if quantity == 0:
        raise ZeroDivisionError("division_by_zero")
    if quantity < 0:
        raise ValueError("quantity_must_be_positive")
    if quantity > _MAX_MINOR_UNIT_ABS_VALUE:
        raise OverflowError("finance_numeric_overflow:quantity")

    if type(request.rounding_mode) is not str:
        raise TypeError("invalid_rounding_mode_type")
    if request.rounding_mode not in _ROUNDING_MODES:
        raise ValueError("invalid_rounding_mode")

    seen_refs: set[str] = set()
    for item in request.items:
        if type(item) is not SyntheticCostItem:
            raise TypeError("invalid_cost_item_type")
        if type(item.input_ref) is not str:
            raise TypeError("invalid_input_ref_type")
        if _SYNTHETIC_REF.fullmatch(item.input_ref) is None:
            raise ValueError("invalid_synthetic_input_ref")
        if item.input_ref in seen_refs:
            raise ValueError("duplicate_input_ref")
        seen_refs.add(item.input_ref)

        coefficient = _require_plain_int(item.coefficient, "coefficient")
        if abs(coefficient) > _MAX_MINOR_UNIT_ABS_VALUE:
            raise OverflowError("finance_numeric_overflow:cost_item")


def calculate_synthetic_cost_scenario(
    request: SyntheticCostRequest,
) -> SyntheticCostResult:
    """Calculate one isolated request from synthetic inputs to immutable result.

    Items share the caller-declared ``common_scale``.  Their signed integer
    coefficients are summed exactly, then divided by the caller-supplied
    positive integer quantity.  Only the caller's output scale and rounding
    mode are used for quantization.
    """

    _validate_request(request)

    total = 0
    work_units = 0
    for item in request.items:
        item_digits = _digit_count(item.coefficient)
        work_units += 1 + item_digits
        work_units += 1 + max(_digit_count(total), item_digits)
        if work_units > _MAX_WORK_UNITS:
            raise OverflowError("finance_numeric_overflow:work_units")

        total += item.coefficient
        if _digit_count(total) > _MAX_INTERMEDIATE_COEFFICIENT_DIGITS:
            raise OverflowError(
                "finance_numeric_overflow:intermediate_coefficient_digits"
            )

    per_unit_coefficient, returned_scale = divide_scaled_ints(
        total,
        request.common_scale,
        request.quantity,
        0,
        request.output_scale,
        request.rounding_mode,
    )
    if returned_scale != request.output_scale:
        raise RuntimeError("unexpected_division_scale")

    return SyntheticCostResult(
        input_refs=tuple(item.input_ref for item in request.items),
        arithmetic_total=ScaledInteger(total, request.common_scale),
        per_unit_result=ScaledInteger(
            per_unit_coefficient,
            request.output_scale,
        ),
        common_scale=request.common_scale,
        output_scale=request.output_scale,
        quantity=request.quantity,
        rounding_mode=request.rounding_mode,
    )


__all__ = [
    "ScaledInteger",
    "SyntheticCostItem",
    "SyntheticCostRequest",
    "SyntheticCostResult",
    "calculate_synthetic_cost_scenario",
]
