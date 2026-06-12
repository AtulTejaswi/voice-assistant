"""
Tests for the CredentialGuard module.

Run:  python -m pytest tests/test_credential_guard.py -v
"""

import pytest
from src.credential_guard import CredentialGuard, GuardError


@pytest.fixture
def guard():
    return CredentialGuard()


# ---------------------------------------------------------------------------
# Safe inputs — should pass through unmodified
# ---------------------------------------------------------------------------

def test_safe_plain_text(guard: CredentialGuard):
    result = guard.inspect("open Chrome and search for cat videos")
    assert result.safe is True
    assert result.redacted_text == "open Chrome and search for cat videos"


def test_safe_numbers(guard: CredentialGuard):
    result = guard.inspect("set volume to 42")
    assert result.safe is True


def test_safe_date(guard: CredentialGuard):
    result = guard.inspect("what time is it")
    assert result.safe is True
    assert result.redacted_text == "what time is it"


def test_safe_with_special_chars(guard: CredentialGuard):
    result = guard.inspect("type my email is user@example.com")
    assert result.safe is True


def test_safe_empty_string(guard: CredentialGuard):
    result = guard.inspect("")
    assert result.safe is True


def test_safe_whitespace(guard: CredentialGuard):
    result = guard.inspect("   ")
    assert result.safe is True


# ---------------------------------------------------------------------------
# Credential triggers — must be blocked
# ---------------------------------------------------------------------------

def test_block_password_is(guard: CredentialGuard):
    result = guard.inspect("my password is hunter2")
    assert result.safe is False
    assert "credential_trigger" in result.blocked_categories
    assert result.redacted_text != result.original_text


def test_block_password_colon(guard: CredentialGuard):
    result = guard.inspect("password: mysecret123")
    assert result.safe is False
    assert "credential_trigger" in result.blocked_categories


def test_block_pin(guard: CredentialGuard):
    result = guard.inspect("my pin is 1234")
    assert result.safe is False
    assert "credential_trigger" in result.blocked_categories


def test_block_two_factor_code(guard: CredentialGuard):
    result = guard.inspect("the two-factor code is 847291")
    assert result.safe is False
    assert "otp" in result.blocked_categories or "credential_trigger" in result.blocked_categories


def test_block_login_credentials(guard: CredentialGuard):
    result = guard.inspect("my login is admin and password is pass123")
    assert result.safe is False


# ---------------------------------------------------------------------------
# API key patterns — must be blocked
# ---------------------------------------------------------------------------

def test_block_openai_api_key(guard: CredentialGuard):
    result = guard.inspect("use sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456 for the API")
    assert result.safe is False
    assert "api_key" in result.blocked_categories


def test_block_github_token(guard: CredentialGuard):
    result = guard.inspect("the token is ghp_abcdefghijklmnopqrstuvwxyz1234567890")
    assert result.safe is False
    assert "api_key" in result.blocked_categories


def test_block_aws_key(guard: CredentialGuard):
    result = guard.inspect("AKIAIOSFODNN7EXAMPLE is the access key")
    assert result.safe is False
    assert "api_key" in result.blocked_categories


def test_block_jwt(guard: CredentialGuard):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    result = guard.inspect(f"use token {jwt} for auth")
    assert result.safe is False
    assert "jwt" in result.blocked_categories


# ---------------------------------------------------------------------------
# assert_safe convenience
# ---------------------------------------------------------------------------

def test_assert_safe_raises_on_credential(guard: CredentialGuard):
    with pytest.raises(GuardError) as exc_info:
        guard.assert_safe("my password is secret")
    assert "credential_trigger" in exc_info.value.result.blocked_categories


def test_assert_safe_returns_text(guard: CredentialGuard):
    result = guard.assert_safe("open Firefox")
    assert result == "open Firefox"


# ---------------------------------------------------------------------------
# Redaction quality — no credential content leaks in redacted output
# ---------------------------------------------------------------------------

def test_redacted_does_not_contain_password(guard: CredentialGuard):
    result = guard.inspect("my password is supersecret123")
    assert result.safe is False
    assert "supersecret123" not in result.redacted_text


def test_redacted_blocks_api_key_content(guard: CredentialGuard):
    result = guard.inspect("api key sk-proj-abcdefghijklmnopqrstuvwxyz123456")
    assert result.safe is False
    assert "sk-proj" not in result.redacted_text


# ---------------------------------------------------------------------------
# Edge cases — mixed safe + unsafe
# ---------------------------------------------------------------------------

def test_mixed_safe_and_password(guard: CredentialGuard):
    result = guard.inspect("open Chrome and my password is secret quit Chrome")
    assert result.safe is False


def test_case_insensitivity(guard: CredentialGuard):
    result = guard.inspect("My PASSWORD is secret")
    assert result.safe is False


def test_multiple_credential_types(guard: CredentialGuard):
    result = guard.inspect("password is pass123 and token is sk-abc123def456ghi789jkl012mno345")
    assert result.safe is False
    # Should catch both credential_trigger and api_key
    assert len(result.blocked_categories) >= 1
