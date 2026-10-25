import unittest

from exact_division import divide_scaled_ints


def integer_oracle(
    dividend_coefficient,
    dividend_scale,
    divisor_coefficient,
    divisor_scale,
    output_scale,
    rounding_mode,
):
    """Independent test-local oracle using separately scaled integers."""

    numerator = abs(dividend_coefficient) * (
        10 ** (output_scale + divisor_scale)
    )
    denominator = abs(divisor_coefficient) * (10**dividend_scale)
    quotient, remainder = divmod(numerator, denominator)

    if rounding_mode == "DOWN":
        rounded = quotient
    elif rounding_mode == "HALF_UP":
        rounded = quotient + (2 * remainder >= denominator)
    else:
        comparison = 2 * remainder - denominator
        rounded = quotient + (
            comparison > 0 or (comparison == 0 and quotient % 2 == 1)
        )

    if rounded and (dividend_coefficient < 0) != (divisor_coefficient < 0):
        rounded = -rounded
    return rounded, output_scale


class ExactDivisionTests(unittest.TestCase):
    def assert_error(self, exception_class, message, *arguments):
        with self.assertRaisesRegex(exception_class, f"^{message}$"):
            divide_scaled_ints(*arguments)

    def test_exact_quotient_with_zero_remainder(self):
        self.assertEqual(
            divide_scaled_ints(123, 2, 3, 0, 2, "HALF_EVEN"),
            (41, 2),
        )

    def test_declared_scale_preserves_trailing_zero_semantics(self):
        self.assertEqual(
            divide_scaled_ints(1, 0, 2, 0, 2, "HALF_EVEN"),
            (50, 2),
        )

    def test_half_up_less_tie_greater_for_both_signs(self):
        cases = (
            (1, 4, 0),
            (1, 2, 1),
            (3, 4, 1),
            (-1, 4, 0),
            (-1, 2, -1),
            (-3, 4, -1),
        )
        for dividend, divisor, expected in cases:
            with self.subTest(dividend=dividend, divisor=divisor):
                self.assertEqual(
                    divide_scaled_ints(
                        dividend,
                        0,
                        divisor,
                        0,
                        0,
                        "HALF_UP",
                    ),
                    (expected, 0),
                )

    def test_half_even_ties_retain_even_magnitude_for_both_signs(self):
        cases = ((5, 2), (3, 2), (-5, -2), (-3, -2))
        for dividend, expected in cases:
            with self.subTest(dividend=dividend):
                self.assertEqual(
                    divide_scaled_ints(
                        dividend,
                        0,
                        2,
                        0,
                        0,
                        "HALF_EVEN",
                    ),
                    (expected, 0),
                )

    def test_down_truncates_toward_zero_for_both_signs(self):
        self.assertEqual(
            divide_scaled_ints(7, 0, 2, 0, 0, "DOWN"),
            (3, 0),
        )
        self.assertEqual(
            divide_scaled_ints(-7, 0, 2, 0, 0, "DOWN"),
            (-3, 0),
        )

    def test_rounding_carries_across_integer_boundary(self):
        self.assertEqual(
            divide_scaled_ints(999, 0, 1000, 0, 2, "HALF_UP"),
            (100, 2),
        )
        self.assertEqual(
            divide_scaled_ints(-999, 0, 1000, 0, 2, "HALF_UP"),
            (-100, 2),
        )

    def test_zero_is_canonical_for_every_mode_and_sign_combination(self):
        for divisor in (3, -3):
            for mode in ("DOWN", "HALF_UP", "HALF_EVEN"):
                with self.subTest(divisor=divisor, mode=mode):
                    coefficient, scale = divide_scaled_ints(
                        0,
                        18,
                        divisor,
                        0,
                        18,
                        mode,
                    )
                    self.assertEqual((coefficient, scale), (0, 18))
                    self.assertEqual(str(coefficient), "0")

    def test_scale_boundaries_zero_and_eighteen_succeed(self):
        self.assertEqual(
            divide_scaled_ints(1, 0, 1, 0, 0, "DOWN"),
            (1, 0),
        )
        self.assertEqual(
            divide_scaled_ints(1, 18, 1, 18, 18, "DOWN"),
            (10**18, 18),
        )

    def test_invalid_scales_have_stable_error(self):
        invalid_calls = (
            (1, -1, 1, 0, 0, "DOWN"),
            (1, 19, 1, 0, 0, "DOWN"),
            (1, 0, 1, -1, 0, "DOWN"),
            (1, 0, 1, 19, 0, "DOWN"),
            (1, 0, 1, 0, -1, "DOWN"),
            (1, 0, 1, 0, 19, "DOWN"),
        )
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                self.assert_error(ValueError, "invalid_scale", *arguments)

    def test_bool_and_other_wrong_types_have_stable_error(self):
        invalid_calls = (
            (True, 0, 1, 0, 0, "DOWN"),
            (1, False, 1, 0, 0, "DOWN"),
            (1, 0, True, 0, 0, "DOWN"),
            (1, 0, 1, False, 0, "DOWN"),
            (1, 0, 1, 0, True, "DOWN"),
            (1, 0, 1, 0, 0, False),
            (1.0, 0, 1, 0, 0, "DOWN"),
        )
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                self.assert_error(TypeError, "invalid_input_type", *arguments)

    def test_invalid_rounding_mode_has_stable_error(self):
        self.assert_error(
            ValueError,
            "invalid_rounding_mode",
            1,
            0,
            2,
            0,
            0,
            "half_up",
        )

    def test_division_by_zero_has_stable_error(self):
        self.assert_error(
            ZeroDivisionError,
            "division_by_zero",
            1,
            0,
            0,
            0,
            0,
            "DOWN",
        )

    def test_input_digit_boundary(self):
        largest_accepted = 10**37
        self.assertEqual(
            divide_scaled_ints(
                largest_accepted,
                18,
                largest_accepted,
                18,
                18,
                "HALF_EVEN",
            ),
            (10**18, 18),
        )
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:dividend_digits",
            10**38,
            18,
            1,
            0,
            0,
            "DOWN",
        )

    def test_input_adjusted_exponent_boundary(self):
        self.assertEqual(
            divide_scaled_ints(10**24, 0, 1, 0, 0, "DOWN"),
            (10**24, 0),
        )
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:dividend_adjusted_exponent",
            10**25,
            0,
            1,
            0,
            0,
            "DOWN",
        )

    def test_result_adjusted_exponent_overflow(self):
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:result_adjusted_exponent",
            10**24,
            0,
            1,
            18,
            0,
            "DOWN",
        )

    def test_rounding_carry_is_revalidated_against_result_bounds(self):
        dividend = (2 * (10**25)) - 1
        self.assertEqual(
            divide_scaled_ints(dividend, 1, 2, 1, 0, "DOWN"),
            ((10**25) - 1, 0),
        )
        self.assert_error(
            OverflowError,
            "finance_numeric_overflow:result_adjusted_exponent",
            dividend,
            1,
            2,
            1,
            0,
            "HALF_UP",
        )

    def test_reachable_shift_extremes_match_integer_oracle(self):
        cases = (
            (123456789, 18, 7, 0, 0, "HALF_EVEN"),
            (123456789, 0, 10**18, 18, 18, "HALF_UP"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(
                    divide_scaled_ints(*arguments),
                    integer_oracle(*arguments),
                )

    def test_largest_reachable_valid_operands_match_integer_oracle(self):
        arguments = (
            10**37,
            18,
            (10**37) - 1,
            18,
            18,
            "HALF_EVEN",
        )
        self.assertEqual(
            divide_scaled_ints(*arguments),
            integer_oracle(*arguments),
        )

    def test_repeated_results_are_exactly_deterministic(self):
        arguments = (-987654321, 7, 1234567, 5, 11, "HALF_EVEN")
        expected = integer_oracle(*arguments)
        results = [divide_scaled_ints(*arguments) for _ in range(100)]
        self.assertTrue(all(result == expected for result in results))
        self.assertTrue(all(type(result) is tuple for result in results))


if __name__ == "__main__":
    unittest.main()
