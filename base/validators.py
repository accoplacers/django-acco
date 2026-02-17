import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

def validate_no_sql_injection(value):
    """
    Validates that the input doesn't contain SQL injection patterns.
    """
    if not value:
        return

    # Common SQL injection patterns
    sql_patterns = [
        r'(SELECT|UNION|DROP|INSERT|UPDATE|DELETE|EXEC|EXECUTE|SCRIPT|JAVASCRIPT)',
        r'(PG_SLEEP|WAITFOR\s+DELAY|BENCHMARK)',
        r'(--|;--|\'\s*OR|\"\s*OR)',
        r'(XOR|0x[0-9A-F]+)',
        r'(<script|javascript:)',
    ]

    for pattern in sql_patterns:
        if re.search(pattern, str(value), re.IGNORECASE):
            raise ValidationError(
                'Invalid input detected. Please enter valid data without special characters or SQL commands.'
            )


def validate_company_name(value):
    """
    Validates company name format.
    """
    if not value or len(value.strip()) < 2:
        raise ValidationError('Company name must be at least 2 characters long.')

    if len(value) > 200:
        raise ValidationError('Company name is too long (max 200 characters).')

    # Check for SQL injection
    validate_no_sql_injection(value)

    # Allow letters, numbers, spaces, and common business characters
    if not re.match(r'^[a-zA-Z0-9\s\.\,\-\&\'\(\)]+$', value):
        raise ValidationError(
            'Company name contains invalid characters. Only letters, numbers, and basic punctuation allowed.'
        )


def validate_phone_number(value):
    """
    Validates phone number format.
    """
    if not value:
        raise ValidationError('Phone number is required.')

    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\+]', '', value)

    # Check if it's numeric and reasonable length
    if not cleaned.isdigit() or len(cleaned) < 7 or len(cleaned) > 15:
        raise ValidationError('Please enter a valid phone number (7-15 digits).')


def validate_safe_email(value):
    """
    Validates email and checks for SQL injection patterns.
    """
    # First use Django's built-in email validator
    validate_email(value)

    # Then check for SQL injection
    validate_no_sql_injection(value)

    # Additional check for @ and reasonable length
    if value.count('@') != 1:
        raise ValidationError('Invalid email format.')

    if len(value) > 254:  # RFC 5321
        raise ValidationError('Email address is too long.')


def validate_text_input(value, min_length=0, max_length=1000):
    """
    Generic text input validator.
    """
    if value and len(value.strip()) < min_length:
        raise ValidationError(f'Input must be at least {min_length} characters.')

    if value and len(value) > max_length:
        raise ValidationError(f'Input is too long (max {max_length} characters).')

    # Check for SQL injection
    validate_no_sql_injection(value)
