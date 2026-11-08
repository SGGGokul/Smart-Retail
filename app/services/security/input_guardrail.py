"""Multi-Layer Input Security Guardrails for RetailIQ AI Assistant.

Provides Unicode NFKC normalization, zero-width/invisible character detection,
homoglyph/mixed-script inspection, prompt injection detection, rate-limiting,
and model-based classification via Llama Prompt Guard 2 86M.
"""

from dataclasses import dataclass, field
import enum
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

logger = logging.getLogger("retailiq.security.input_guardrail")


class Decision(str, enum.Enum):
    ALLOW = "ALLOW"
    FLAG = "FLAG"
    BLOCK = "BLOCK"


@dataclass
class GuardrailResult:
    """Security assessment outcome."""
    decision: Decision
    reasons: List[str] = field(default_factory=list)
    normalized_text: str = ""
    prompt_guard_score: Optional[float] = None
    sanitized_for_inspection: str = ""


# Zero-width, invisible, and format control Unicode codepoints
ZERO_WIDTH_CHARS = {
    "\u200B",  # Zero-width space
    "\u200C",  # Zero-width non-joiner
    "\u200D",  # Zero-width joiner
    "\u2060",  # Word joiner
    "\uFEFF",  # Zero-width no-break space / BOM
    "\u00AD",  # Soft hyphen
    "\u200E",  # Left-to-right mark
    "\u200F",  # Right-to-left mark
    "\u202A",  # Left-to-right embedding
    "\u202B",  # Right-to-left embedding
    "\u202C",  # Pop directional formatting
    "\u202D",  # Left-to-right override
    "\u202E",  # Right-to-left override
}

# High-risk prompt injection and jailbreak regex patterns (matched on NFKC normalized text)
INJECTION_SIGNATURES = [
    re.compile(r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|former)\s+(instructions|prompts?|rules?|directives?)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|rules?|context)", re.I),
    re.compile(r"(reveal|print|show|dump|repeat|leak|display)\s+(the\s+)?(system\s+prompt|system\s+instructions?|developer\s+prompt)", re.I),
    re.compile(r"<\s*\|\s*(im_start|im_end|system|developer|user|assistant)\s*\|\s*>", re.I),
    re.compile(r"(\[|\()system(\]|\))\s*:\s*", re.I),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|unrestricted\s+mode|god\s+mode|dan\s+mode)", re.I),
    re.compile(r"pretend\s+(you\s+have\s+no\s+(rules?|filters?|guidelines?)|there\s+are\s+no\s+safety)", re.I),
    re.compile(r"bypass\s+(all\s+)?(restrictions?|safety|security|rules?)", re.I),
    re.compile(r"new\s+(system\s+prompt|directive)\s*:\s*", re.I),
    re.compile(r"execute\s+(shell|bash|powershell|cmd|system|os\.system|subprocess)", re.I),
    re.compile(r"(sudo\s+rm|format\s+c:|eval\(|exec\()", re.I),
]


class InputGuardrail:
    """Multi-layer input inspection defending against adversarial manipulation."""

    def __init__(
        self,
        max_length: int = 2000,
        rate_limit_requests: int = 30,
        rate_limit_window_seconds: float = 60.0,
        prompt_guard_block_threshold: float = 0.85,
        prompt_guard_flag_threshold: float = 0.50,
    ) -> None:
        self.max_length = max_length
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.prompt_guard_block_threshold = prompt_guard_block_threshold
        self.prompt_guard_flag_threshold = prompt_guard_flag_threshold

        # Sliding window for rate limiting: client_ip/session_id -> List[timestamp]
        self._request_history: Dict[str, List[float]] = {}

    def check_rate_limit(self, client_id: str = "default") -> bool:
        """Check sliding window rate limiting. Returns True if allowed, False if exceeded."""
        now = time.time()
        timestamps = self._request_history.get(client_id, [])
        # Purge timestamps outside the window
        timestamps = [t for t in timestamps if now - t <= self.rate_limit_window_seconds]
        if len(timestamps) >= self.rate_limit_requests:
            self._request_history[client_id] = timestamps
            return False
        timestamps.append(now)
        self._request_history[client_id] = timestamps
        return True

    @staticmethod
    def detect_invisible_and_zero_width(text: str) -> List[str]:
        """Detect zero-width characters and invisible directional overrides."""
        found: List[str] = []
        for ch in text:
            if ch in ZERO_WIDTH_CHARS:
                found.append(f"U+{ord(ch):04X}")
        return found

    @staticmethod
    def detect_mixed_script_and_homoglyphs(text: str) -> Tuple[bool, List[str]]:
        """Detect suspicious mixed-script tokens (e.g. Cyrillic letters embedded in Latin words)."""
        reasons: List[str] = []
        has_suspicious_mix = False

        words = re.findall(r"\w+", text)
        for w in words:
            scripts: Set[str] = set()
            for ch in w:
                try:
                    name = unicodedata.name(ch)
                    if "LATIN" in name:
                        scripts.add("LATIN")
                    elif "CYRILLIC" in name:
                        scripts.add("CYRILLIC")
                    elif "GREEK" in name:
                        scripts.add("GREEK")
                except ValueError:
                    continue

            # Flag if an individual token mixes Latin with Cyrillic or Greek (classic homoglyph spoofing)
            if "LATIN" in scripts and ("CYRILLIC" in scripts or "GREEK" in scripts):
                has_suspicious_mix = True
                reasons.append(f"Mixed-script homoglyph word detected: '{w}'")

        return has_suspicious_mix, reasons

    @staticmethod
    def normalize_for_inspection(text: str) -> str:
        """Normalize Unicode to NFKC form.

        Converts mathematical alphanumeric symbols (e.g. 𝑖𝑔𝑛𝑜𝑟𝑒 -> ignore)
        and fullwidth characters (ｉｇｎｏｒｅ -> ignore) while preserving normal text.
        """
        # 1. Strip zero-width chars from inspection copy
        stripped = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
        # 2. Apply Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", stripped)
        return normalized

    def validate_input(
        self,
        raw_text: str,
        client_id: str = "default",
        prompt_guard_score: Optional[float] = None,
    ) -> GuardrailResult:
        """Perform comprehensive multi-layer input security assessment.

        Returns GuardrailResult with decision: ALLOW, FLAG, or BLOCK.
        """
        reasons: List[str] = []

        # 1. Empty / Whitespace check
        if not raw_text or not raw_text.strip():
            return GuardrailResult(
                decision=Decision.BLOCK,
                reasons=["Input is empty or whitespace only."],
                normalized_text="",
            )

        # 2. Maximum length constraint
        if len(raw_text) > self.max_length:
            return GuardrailResult(
                decision=Decision.BLOCK,
                reasons=[f"Input exceeds maximum allowed length ({len(raw_text)} > {self.max_length} chars)."],
                normalized_text=raw_text[:self.max_length],
            )

        # 3. Rate limiting check
        if not self.check_rate_limit(client_id):
            return GuardrailResult(
                decision=Decision.BLOCK,
                reasons=["Rate limit exceeded. Too many requests in short window."],
                normalized_text=raw_text,
            )

        # 4. Invisible and Zero-width character inspection
        hidden_chars = self.detect_invisible_and_zero_width(raw_text)
        if hidden_chars:
            reasons.append(f"Detected {len(hidden_chars)} invisible or zero-width character(s): {', '.join(hidden_chars[:5])}")

        # 5. Unicode NFKC normalization (translates mathematical letters & fullwidth forms)
        normalized = self.normalize_for_inspection(raw_text)

        # 6. Mixed-script homoglyph inspection
        is_mixed, mixed_reasons = self.detect_mixed_script_and_homoglyphs(raw_text)
        if is_mixed:
            reasons.extend(mixed_reasons)

        # 7. Prompt Injection and Jailbreak Signatures
        for sig in INJECTION_SIGNATURES:
            if sig.search(normalized):
                reasons.append(f"Prompt injection signature detected: {sig.pattern}")
                # High-confidence injection pattern -> Immediate BLOCK
                return GuardrailResult(
                    decision=Decision.BLOCK,
                    reasons=reasons,
                    normalized_text=normalized,
                    prompt_guard_score=prompt_guard_score,
                )

        # 8. Model-Based Classifier (Llama Prompt Guard 2 86M) Assessment
        if prompt_guard_score is not None:
            if prompt_guard_score >= self.prompt_guard_block_threshold:
                reasons.append(
                    f"Prompt Guard 2 classifier score ({prompt_guard_score:.3f}) exceeded block threshold ({self.prompt_guard_block_threshold})."
                )
                return GuardrailResult(
                    decision=Decision.BLOCK,
                    reasons=reasons,
                    normalized_text=normalized,
                    prompt_guard_score=prompt_guard_score,
                )
            elif prompt_guard_score >= self.prompt_guard_flag_threshold:
                reasons.append(
                    f"Prompt Guard 2 classifier score ({prompt_guard_score:.3f}) flagged for review."
                )

        # 9. Evaluate Flag vs Block vs Allow
        if is_mixed:
            # Homoglyph attacks to evade filters are blocked
            return GuardrailResult(
                decision=Decision.BLOCK,
                reasons=reasons,
                normalized_text=normalized,
                prompt_guard_score=prompt_guard_score,
            )

        if reasons:
            # Invisible characters without injection signatures are flagged but permitted
            return GuardrailResult(
                decision=Decision.FLAG,
                reasons=reasons,
                normalized_text=normalized,
                prompt_guard_score=prompt_guard_score,
            )

        return GuardrailResult(
            decision=Decision.ALLOW,
            reasons=[],
            normalized_text=normalized,
            prompt_guard_score=prompt_guard_score,
        )


_input_guardrail: Optional[InputGuardrail] = None


def get_input_guardrail() -> InputGuardrail:
    global _input_guardrail
    if _input_guardrail is None:
        _input_guardrail = InputGuardrail()
    return _input_guardrail
