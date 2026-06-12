"""
Credential Guard — standalone content filter layer.

Sits between speech transcription and action execution.
Pattern-matches credential-like content and blocks/redacts it.

Non-negotiable security boundary:
  - NEVER passes credential content to the executor
  - NEVER logs credential content
  - NEVER stores credential content
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Patterns  — compiled once at import time for performance
# ---------------------------------------------------------------------------

# Contextual phrases that indicate credentials
_CREDENTIAL_TRIGGERS = re.compile(
    r"(?:my\s+)?(?:password|passwd|pwd|pass\s?phrase|secret|pin|otp|2fa|"
    r"two[-\s]?factor|auth(?:entication)?\s?code|code|login|sign[-\s]?in|"
    r"credential|security\s?question|recovery\s?code|backup\s?code)\s*"
    r"(?:is|:|=)",
    re.IGNORECASE,
)

# Common API key / token formats
_API_KEY_PATTERNS = re.compile(
    r"""(?x)
        (?: sk|pk|api ) [-_] [A-Za-z0-9_-]{4,} [-] [A-Za-z0-9]{20,}   # OpenAI / Anthropic / generic (e.g. sk-proj-xxx)
        |  (?: sk|pk|api ) [-_] [A-Za-z0-9]{20,}                      # OpenAI / Anthropic short form (e.g. sk-xxx)
        |  ghp_ [A-Za-z0-9]{36}                                       # GitHub
        |  (?: AKIA | ASIA ) [A-Z0-9]{16}                             # AWS
        |  [A-Za-z0-9+/]{32,} (?: ={1,2} )?                           # generic long token
    """,
)

# Numeric OTP patterns (6-8 digits in credential context)
_OTP_PATTERN = re.compile(r"\b\d{6,8}\b")

# JWT-like patterns (base64url chunks separated by dots)
_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)

# Redacted replacement
_REDACTED = "[CREDENTIAL BLOCKED — enter manually]"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    safe: bool
    blocked_categories: List[str] = field(default_factory=list)
    redacted_text: str = ""
    original_text: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

class CredentialGuard:
    """
    Inspects transcribed text before it reaches the action executor.

    Usage:
        guard = CredentialGuard()
        result = guard.inspect("my password is hunter2")
        result.safe  # False
    """

    def __init__(self, patterns: Optional[dict] = None):
        self._patterns = patterns or {
            "credential_trigger": _CREDENTIAL_TRIGGERS,
            "api_key": _API_KEY_PATTERNS,
            "otp": _OTP_PATTERN,
            "jwt": _JWT_PATTERN,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inspect(self, text: str) -> GuardResult:
        """
        Analyse *text* for credential-like content.

        Returns a GuardResult with:
          - safe         : True if nothing credential-like was found
          - blocked_categories : list of matching pattern names
          - redacted_text: cleaned version with credentials replaced
          - original_text: the input as-is (never passed to executor if blocked!)
          - reason       : human-readable explanation
        """
        if not text or not text.strip():
            return GuardResult(safe=True, redacted_text=text, original_text=text)

        text_stripped = text.strip()
        blocked: List[str] = []
        redacted = text_stripped

        # 1. Check for JWT tokens first (high-confidence)
        if self._patterns["jwt"].search(redacted):
            blocked.append("jwt")
            redacted = self._patterns["jwt"].sub(_REDACTED, redacted)

        # 2. Check for API key patterns
        if self._patterns["api_key"].search(redacted):
            blocked.append("api_key")
            redacted = self._patterns["api_key"].sub(_REDACTED, redacted)

        # 3. Check for credential triggers + nearby OTP
        cred_match = self._patterns["credential_trigger"].search(redacted)
        # Only flag OTP if a credential trigger is also present (reduces false
        # positives on ordinary numbers)
        otp_match = self._patterns["otp"].search(redacted) if cred_match else None

        if cred_match:
            blocked.append("credential_trigger")
            # Redact from the trigger phrase onward in that sentence
            redacted = self._redact_sentence_from_match(redacted, cred_match)

        if otp_match:
            if "otp" not in blocked:
                blocked.append("otp")
            redacted = self._patterns["otp"].sub(_REDACTED, redacted)

        # 4. Final pass: any remaining high-entropy strings in a credential
        #    context — conservative: if we already blocked, redact anything
        #    that looks like a long random string
        if blocked:
            redacted = self._redact_remaining_suspicious(redacted)

        safe = len(blocked) == 0
        reason = self._build_reason(blocked) if blocked else ""

        return GuardResult(
            safe=safe,
            blocked_categories=blocked,
            redacted_text=redacted,
            original_text=text_stripped,
            reason=reason,
        )

    def assert_safe(self, text: str) -> str:
        """
        Convenience: returns *redacted_text* if safe, raises GuardError otherwise.
        """
        result = self.inspect(text)
        if not result.safe:
            raise GuardError(result)
        return result.redacted_text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_sentence_from_match(text: str, match: re.Match) -> str:
        """Redact from the credential trigger to the end of the sentence."""
        start = match.start()
        # Find the end of the sentence (period, exclamation, question mark,
        # newline, or end-of-string)
        remainder = text[start:]
        end_match = re.search(r"[.!?\n]|$", remainder)
        end = start + end_match.end() if end_match else len(text)
        return text[:start] + _REDACTED + text[end:]

    @staticmethod
    def _redact_remaining_suspicious(text: str) -> str:
        """Conservative catch-all: redact remaining long alphanumeric
        sequences that survived earlier passes."""
        suspicious = re.compile(r"\b[A-Za-z0-9!@#$%^&*()_+=\-]{12,}\b")
        return suspicious.sub(_REDACTED, text)

    @staticmethod
    def _build_reason(categories: List[str]) -> str:
        mapping = {
            "credential_trigger": "Text contains a credential-related phrase",
            "api_key": "Text resembles an API key or token",
            "otp": "Text contains a numeric code in a credential context",
            "jwt": "Text contains a JSON Web Token",
        }
        reasons = [mapping.get(c, f"Unknown category: {c}") for c in categories]
        return "; ".join(reasons)


class GuardError(Exception):
    """Raised when credential content is detected and blocked."""

    def __init__(self, result: GuardResult):
        self.result = result
        super().__init__(result.reason)
