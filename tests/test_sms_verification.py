import pytest
from backend.config import settings
from backend.services.adapters.sms_adapter import sms_adapter

# Where the human-readable diagnostic/result log is written (existing behavior).
LOG_PATH = r"c:\Users\rajub\Downloads\genai\genai\sms_out_log.txt"


def _write_log(lines):
    """Best-effort diagnostic log; must never break the test if the path is
    unavailable on a given machine."""
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass


def test_verify_sms_configuration_and_dispatch():
    """Verify the SMS provider configuration and, only when real credentials are
    present and valid, exercise a controlled real dispatch.

    External SMS credentials are OPTIONAL for the core application, so this test
    SKIPS (it does not fail) when the provider is not configured.

    The single source of truth for "is it configured / what is wrong" is the
    adapter's own diagnostics: `sms_adapter.configuration_issues()` (and its
    derived `is_configured()`). The previous version of this test re-derived a
    weaker validity check locally, which drifted from the adapter's strict Twilio
    format validation. That drift produced the reported inconsistency where the
    locally-computed `missing` list was empty even though `is_configured()`
    returned False. Delegating to the adapter keeps the two perfectly consistent
    and avoids fabricating any credentials.
    """
    issues = sms_adapter.configuration_issues()

    if issues or not sms_adapter.is_configured():
        lines = ["SMS CONFIGURATION INCOMPLETE", "Issues (non-secret diagnostics):"]
        lines += [f"- {item}" for item in issues]
        _write_log(lines)
        # Optional integration: skip rather than fail so the core suite stays green
        # without SMS credentials. No fake credentials are ever injected.
        pytest.skip(
            "SMS provider not configured/valid; skipping real dispatch. "
            f"Issues: {issues}"
        )

    # Credentials are present AND valid -> perform a single controlled real send.
    lines = ["EXECUTING REAL SMS TEST"]
    res = sms_adapter.send_sms(
        recipients=[settings.TEST_PHONE_NUMBER],
        message="CAMPUSFLOW AI: Controlled Real-Time SMS Emergency Test",
    )
    lines.append(f"Success: {res.success}")
    lines.append(f"Status: {res.status.value}")
    lines.append(f"Provider: {res.provider}")
    lines.append(f"Message ID: {res.message_id}")
    if res.error:
        lines.append(f"Error: {res.error}")

    if res.success and res.message_id:
        delivery = sms_adapter.get_delivery_status(res.message_id)
        lines.append(f"Delivery Status: {delivery.get('status')}")

    _write_log(lines)

    assert res.success is True, f"Real SMS Provider failed: {res.error}"
    assert res.message_id is not None
