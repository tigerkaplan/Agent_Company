"""Isolated exact-division pilot for the accepted Agent 11 design.

This module has no runtime integration and selects no business rounding policy.
The caller must provide one of the three rounding modes supported by the pilot.
"""

_ROUNDING_MODES = frozenset({"DOWN", "HALF_UP", "HALF_EVEN"})

_MAX_SCALE = 18
_MAX_INPUT_DIGITS = 38
_MAX_ABS_INPUT_ADJUSTED_EXPONENT = 24
_MAX_INTERMEDIATE_COEFFICIENT_DIGITS = 128
_MAX_NUMERATOR_DIGITS = 128
_MAX_DENOMINATOR_DIGITS = 128
_MAX_RESULT_DIGITS = 76
_MAX_ABS_RESULT_ADJUSTED_EXPONENT = 24
_MAX_POWER_OF_TEN_SHIFT = 72
_MAX_WORK_UNITS = 100_000


def _digit_count(magnitude: int) -> int:
    return 1 if magnitude == 0 else len(str(magnitude))


def _adjusted_exponent(magnitude: int, scale: int) -> int:
    if magnitude == 0:
        return 0
    return _digit_count(magnitude) - scale - 1


def _overflow(bound_name: str) -> None:
    raise OverflowError(f"finance_numeric_overflow:{bound_name}")


def _validate_input_coefficient(
    coefficient: int,
    scale: int,
    operand_name: str,
) -> None:
    magnitude = abs(coefficient)
    if _digit_count(magnitude) > _MAX_INPUT_DIGITS:
        _overflow(f"{operand_name}_digits")
    if abs(_adjusted_exponent(magnitude, scale)) > (
        _MAX_ABS_INPUT_ADJUSTED_EXPONENT
    ):
        _overflow(f"{operand_name}_adjusted_exponent")


def divide_scaled_ints(
    dividend_coefficient: int,
    dividend_scale: int,
    divisor_coefficient: int,
    divisor_scale: int,
    output_scale: int,
    rounding_mode: str,
) -> tuple[int, int]:
    """Divide two signed scaled integers using exact integer arithmetic.

    The represented inputs are ``coefficient * 10**(-scale)``. The returned
    tuple is ``(signed_coefficient, output_scale)``; retaining the declared
    scale preserves trailing-zero semantics without converting to a decimal
    string or an approximate numeric type.
    """

    integer_inputs = (
        dividend_coefficient,
        dividend_scale,
        divisor_coefficient,
        divisor_scale,
        output_scale,
    )
    if any(type(value) is not int for value in integer_inputs):
        raise TypeError("invalid_input_type")
    if type(rounding_mode) is not str:
        raise TypeError("invalid_input_type")

    scales = (dividend_scale, divisor_scale, output_scale)
    if any(scale < 0 or scale > _MAX_SCALE for scale in scales):
        raise ValueError("invalid_scale")
    if rounding_mode not in _ROUNDING_MODES:
        raise ValueError("invalid_rounding_mode")
    if divisor_coefficient == 0:
        raise ZeroDivisionError("division_by_zero")

    _validate_input_coefficient(
        dividend_coefficient,
        dividend_scale,
        "dividend",
    )
    _validate_input_coefficient(
        divisor_coefficient,
        divisor_scale,
        "divisor",
    )

    shift = output_scale + divisor_scale - dividend_scale
    if abs(shift) > _MAX_POWER_OF_TEN_SHIFT:
        _overflow("power_of_ten_shift")

    dividend_magnitude = abs(dividend_coefficient)
    divisor_magnitude = abs(divisor_coefficient)
    dividend_digits = _digit_count(dividend_magnitude)
    divisor_digits = _digit_count(divisor_magnitude)

    if shift >= 0:
        numerator_digits = (
            1 if dividend_magnitude == 0 else dividend_digits + shift
        )
        denominator_digits = divisor_digits
    else:
        numerator_digits = dividend_digits
        denominator_digits = divisor_digits - shift

    if numerator_digits > _MAX_NUMERATOR_DIGITS:
        _overflow("intermediate_numerator_digits")
    if denominator_digits > _MAX_DENOMINATOR_DIGITS:
        _overflow("intermediate_denominator_digits")

    work_units = 1 + abs(shift)
    work_units += 1 + (numerator_digits * denominator_digits)
    if work_units > _MAX_WORK_UNITS:
        _overflow("work_units")

    if shift >= 0:
        numerator = dividend_magnitude * (10**shift)
        denominator = divisor_magnitude
    else:
        numerator = dividend_magnitude
        denominator = divisor_magnitude * (10 ** (-shift))

    quotient, remainder = divmod(numerator, denominator)

    if rounding_mode == "DOWN":
        increment = False
    elif rounding_mode == "HALF_UP":
        increment = 2 * remainder >= denominator
    else:
        doubled_remainder = 2 * remainder
        increment = doubled_remainder > denominator or (
            doubled_remainder == denominator and quotient % 2 == 1
        )

    rounded_magnitude = quotient + int(increment)
    intermediate_digits = _digit_count(rounded_magnitude)
    if intermediate_digits > _MAX_INTERMEDIATE_COEFFICIENT_DIGITS:
        _overflow("intermediate_coefficient_digits")
    if intermediate_digits > _MAX_RESULT_DIGITS:
        _overflow("result_coefficient_digits")
    if abs(_adjusted_exponent(rounded_magnitude, output_scale)) > (
        _MAX_ABS_RESULT_ADJUSTED_EXPONENT
    ):
        _overflow("result_adjusted_exponent")

    work_units += 2 + intermediate_digits
    if work_units > _MAX_WORK_UNITS:
        _overflow("work_units")

    if rounded_magnitude == 0:
        signed_coefficient = 0
    elif (dividend_coefficient < 0) != (divisor_coefficient < 0):
        signed_coefficient = -rounded_magnitude
    else:
        signed_coefficient = rounded_magnitude

    return signed_coefficient, output_scale


__all__ = ["divide_scaled_ints"]
