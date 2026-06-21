import unittest

from validation import BaseValidator, ValidationResult, validation


class SampleValidator(BaseValidator):
    @validation
    def check_email(self, data: dict) -> ValidationResult:
        email = data.get("email")
        if not email or "@" not in email:
            return ValidationResult(
                name="check_email", passed=False, message="Invalid email"
            )
        return ValidationResult(name="check_email", passed=True)

    @validation
    def check_age(self, data: dict) -> ValidationResult:
        age = data.get("age")
        if age is None or age < 0:
            return ValidationResult(
                name="check_age", passed=False, message="Invalid age"
            )
        return ValidationResult(name="check_age", passed=True)

    def not_a_validation(self, data: dict) -> bool:
        return True


class TestValidationDecorator(unittest.TestCase):
    def test_marks_function(self):
        @validation
        def sample():
            pass

        self.assertTrue(getattr(sample, "_validation", False))


class TestBaseValidator(unittest.TestCase):
    def test_registers_only_decorated_methods(self):
        self.assertEqual(
            SampleValidator._validations,
            ["check_email", "check_age"],
        )

    def test_run_returns_validation_results(self):
        results = SampleValidator().run({"email": "bad", "age": -1})

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ValidationResult)
        self.assertIsInstance(results[1], ValidationResult)

    def test_run_reports_failures(self):
        results = SampleValidator().run({"email": "bad", "age": -1})

        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].name, "check_email")
        self.assertEqual(results[0].message, "Invalid email")

        self.assertFalse(results[1].passed)
        self.assertEqual(results[1].name, "check_age")
        self.assertEqual(results[1].message, "Invalid age")

    def test_run_reports_success(self):
        results = SampleValidator().run({"email": "a@b.com", "age": 25})

        self.assertTrue(all(result.passed for result in results))
        self.assertIsNone(results[0].message)
        self.assertIsNone(results[1].message)


if __name__ == "__main__":
    unittest.main()
