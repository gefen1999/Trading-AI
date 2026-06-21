# coursor_1

Minimal Python data validation infrastructure.

## Setup (local)

```bash
git clone https://github.com/gefen1999/coursor_1.git
cd coursor_1
```

Requires **Python 3.10+**.

## Run tests

```bash
python3 -m unittest test_validation.py -v
```

## Usage

```python
from validation import BaseValidator, validation, ValidationResult

class UserValidator(BaseValidator):
    @validation
    def check_email(self, data: dict) -> ValidationResult:
        email = data.get("email")
        if not email or "@" not in email:
            return ValidationResult(
                name="check_email", passed=False, message="Invalid email"
            )
        return ValidationResult(name="check_email", passed=True)

validator = UserValidator()
results = validator.run({"email": "bad"})
```

## Open in Cursor

1. **File → Open Folder**
2. Select the `coursor_1` folder you cloned
3. Open Terminal (`` Ctrl+` ``) and run the test command above
