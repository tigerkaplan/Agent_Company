from dataclasses import FrozenInstanceError
from fractions import Fraction
import unittest

from synthetic_cost_scenario import (
    ScaledInteger,
    SyntheticCostItem,
    SyntheticCostRequest,
    calculate_synthetic_cost_scenario,
)


def fraction_oracle(request):
    """Independent exact oracle built from Fraction, not the pilot helper."""

    total = sum(item.coefficient for item in request.items)
    scaled_per_unit = (
        Fraction(total, 10**request.common_scale)
        / request.quantity
        * (10**request.output_scale)
    )
    magnitude = abs(scaled_per_unit)
    quotient, remainder = divmod(magnitude.numerator, magnitude.denominator)

    if request.rounding_mode == "DOWN":
        increment = False
    elif request.rounding_mode == "HALF_UP":
        increment = 2 * remainder >= magnitude.denominator
    else:
        comparison = (2 * remainder) - magnitude.denominator
        increment = comparison > 0 or (
            comparison == 0 and quotient % 2 == 1
        )

    rounded = quotient + int(increment)
    if scaled_per_unit < 0 and rounded:
        rounded = -rounded
    return total, rounded


def make_request(
    coefficients,
    *,
    common_scale=0,
    quantity=1,
    output_scale=0,
    rounding_mode="HALF_EVEN",
):
    items = tuple(
        SyntheticCostItem(f"synthetic:item-{index}", coefficient)
        for index, coefficient in enumerate(coefficients, start=1)
    )
    return SyntheticCostRequest(
        items=items,
        common_scale=common_scale,
        quantity=quantity,
        output_scale=output_scale,
        rounding_mode=rounding_mode,
    )


class SyntheticCostScenarioTests(unittest.TestCase):
    def assert_error(self, exception_class, message, request):
        with self.assertRaisesRegex(exception_class, f"^{message}$"):
            calculate_synthetic_cost_scenario(request)

    def test_complete_request_to_result_scenario(self):
        request = SyntheticCostRequest(
            items=(
                SyntheticCostItem("synthetic:labour", 12_345),
                SyntheticCostItem("synthetic:supplies", 2_500),
                SyntheticCostItem("synthetic:credit", -345),
            ),
            common_scale=2,
            quantity=4,
            output_scale=2,
            rounding_mode="HALF_EVEN",
        )

        result = calculate_synthetic_cost_scenario(request)

        self.assertEqual(
            result.input_refs,
            (
                "synthetic:labour",
                "synthetic:supplies",
                "synthetic:credit",
            ),
        )
        self.assertEqual(result.arithmetic_total, ScaledInteger(14_500, 2))
        self.assertEqual(result.per_unit_result, ScaledInteger(3_625, 2))
        self.assertEqual(result.common_scale, 2)
        self.assertEqual(result.output_scale, 2)
        self.assertEqual(result.quantity, 4)
        self.assertEqual(result.rounding_mode, "HALF_EVEN")
        self.assertIs(result.non_authoritative, True)

    def test_signed_totals_match_independent_fraction_oracle(self):
        cases = (
            make_request((700, -125, 25), common_scale=2, quantity=4,
                         output_scale=3, rounding_mode="HALF_UP"),
            make_request((-700, 125, -25), common_scale=2, quantity=4,
                         output_scale=3, rounding_mode="HALF_UP"),
            make_request((-5, 5), common_scale=18, quantity=7,
                         output_scale=18, rounding_mode="DOWN"),
        )
        for request in cases:
            with self.subTest(request=request):
                total, per_unit = fraction_oracle(request)
                result = calculate_synthetic_cost_scenario(request)
                self.assertEqual(result.arithmetic_total.coefficient, total)
                self.assertEqual(result.per_unit_result.coefficient, per_unit)

    def test_rounding_ties_for_both_signs_and_all_modes(self):
        cases = (
            (5, 2, "DOWN", 2),
            (-5, 2, "DOWN", -2),
            (5, 2, "HALF_UP", 3),
            (-5, 2, "HALF_UP", -3),
            (5, 2, "HALF_EVEN", 2),
            (-5, 2, "HALF_EVEN", -2),
            (3, 2, "HALF_EVEN", 2),
            (-3, 2, "HALF_EVEN", -2),
        )
        for total, quantity, mode, expected in cases:
            request = make_request(
                (total,), quantity=quantity, rounding_mode=mode
            )
            with self.subTest(total=total, mode=mode):
                result = calculate_synthetic_cost_scenario(request)
                self.assertEqual(result.per_unit_result, ScaledInteger(expected, 0))
                self.assertEqual(
                    result.per_unit_result.coefficient,
                    fraction_oracle(request)[1],
                )

    def test_scale_boundaries_preserve_declared_scales(self):
        zero = calculate_synthetic_cost_scenario(
            make_request((1,), common_scale=0, output_scale=0)
        )
        eighteen = calculate_synthetic_cost_scenario(
            make_request((1,), common_scale=18, output_scale=18)
        )
        self.assertEqual(zero.arithmetic_total, ScaledInteger(1, 0))
        self.assertEqual(zero.per_unit_result, ScaledInteger(1, 0))
        self.assertEqual(eighteen.arithmetic_total, ScaledInteger(1, 18))
        self.assertEqual(eighteen.per_unit_result, ScaledInteger(1, 18))

    def test_item_count_and_integer_limits(self):
        maximum_items = make_request((1,) * 256, quantity=256)
        self.assertEqual(
            calculate_synthetic_cost_scenario(maximum_items).per_unit_result,
            ScaledInteger(1, 0),
        )
        self.assert_error(
            ValueError,
            "too_many_cost_items",
            make_request((1,) * 257),
        )

        maximum_integer = (2**63) - 1
        result = calculate_synthetic_cost_scenario(
            make_request((maximum_integer,), quantity=maximum_integer)
        )
        self.assertEqual(result.per_unit_result, ScaledInteger(1, 0))
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:cost_item",
            make_request((2**63,)),
        )
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:quantity",
            make_request((1,), quantity=2**63),
        )

    def test_zero_division_and_negative_quantity_fail_closed(self):
        self.assert_error(
            ZeroDivisionError,
            "division_by_zero",
            make_request((1,), quantity=0),
        )
        self.assert_error(
            ValueError,
            "quantity_must_be_positive",
            make_request((1,), quantity=-1),
        )

    def test_malformed_collections_items_and_references_fail_closed(self):
        self.assert_error(
            TypeError,
            "invalid_items_type",
            SyntheticCostRequest([], 0, 1, 0, "DOWN"),
        )
        self.assert_error(
            ValueError,
            "empty_cost_items",
            SyntheticCostRequest((), 0, 1, 0, "DOWN"),
        )
        self.assert_error(
            TypeError,
            "invalid_cost_item_type",
            SyntheticCostRequest(("not-an-item",), 0, 1, 0, "DOWN"),
        )
        self.assert_error(
            ValueError,
            "invalid_synthetic_input_ref",
            SyntheticCostRequest(
                (SyntheticCostItem("production:invoice-1", 1),),
                0,
                1,
                0,
                "DOWN",
            ),
        )
        duplicate = SyntheticCostRequest(
            (
                SyntheticCostItem("synthetic:one", 1),
                SyntheticCostItem("synthetic:one", 2),
            ),
            0,
            1,
            0,
            "DOWN",
        )
        self.assert_error(ValueError, "duplicate_input_ref", duplicate)

    def test_bool_and_other_non_integer_values_are_rejected(self):
        malformed = (
            SyntheticCostRequest(
                (SyntheticCostItem("synthetic:item", True),),
                0,
                1,
                0,
                "DOWN",
            ),
            make_request((1,), common_scale=True),
            make_request((1,), quantity=True),
            make_request((1,), output_scale=1.0),
        )
        expected_messages = (
            "invalid_integer_type:coefficient",
            "invalid_integer_type:common_scale",
            "invalid_integer_type:quantity",
            "invalid_integer_type:output_scale",
        )
        for request, message in zip(malformed, expected_messages):
            with self.subTest(message=message):
                self.assert_error(TypeError, message, request)

    def test_invalid_scales_and_rounding_modes_are_rejected(self):
        for field_name, request in (
            ("common_scale", make_request((1,), common_scale=-1)),
            ("common_scale", make_request((1,), common_scale=19)),
            ("output_scale", make_request((1,), output_scale=-1)),
            ("output_scale", make_request((1,), output_scale=19)),
        ):
            with self.subTest(field_name=field_name, request=request):
                self.assert_error(
                    ValueError,
                    f"invalid_scale:{field_name}",
                    request,
                )
        self.assert_error(
            ValueError,
            "invalid_rounding_mode",
            make_request((1,), rounding_mode="half_even"),
        )
        self.assert_error(
            TypeError,
            "invalid_rounding_mode_type",
            make_request((1,), rounding_mode=False),
        )

    def test_result_and_nested_values_are_immutable(self):
        result = calculate_synthetic_cost_scenario(make_request((1, 2)))
        with self.assertRaises(FrozenInstanceError):
            result.quantity = 9
        with self.assertRaises(FrozenInstanceError):
            result.arithmetic_total.coefficient = 0
        with self.assertRaises(TypeError):
            result.input_refs[0] = "synthetic:changed"

    def test_repeated_identical_requests_produce_identical_results(self):
        request = make_request(
            (987_654_321, -123_456_789, 25),
            common_scale=7,
            quantity=13,
            output_scale=11,
            rounding_mode="HALF_EVEN",
        )
        expected_total, expected_per_unit = fraction_oracle(request)
        results = tuple(
            calculate_synthetic_cost_scenario(request) for _ in range(100)
        )
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(
            results[0].arithmetic_total.coefficient,
            expected_total,
        )
        self.assertEqual(
            results[0].per_unit_result.coefficient,
            expected_per_unit,
        )


if __name__ == "__main__":
    unittest.main()
