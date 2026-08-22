import pytest
from backend.config import settings
from backend.services.adapters.sms_adapter import sms_adapter

def test_verify_sms_configuration_and_dispatch():
    configured = sms_adapter.is_configured()
    missing = []
    
    placeholders = sms_adapter.PLACEHOLDERS
    if not sms_adapter._is_valid(settings.SMS_PROVIDER):
        missing.append("SMS_PROVIDER")
    if not sms_adapter._is_valid(settings.SMS_ACCOUNT_ID):
        missing.append("SMS_ACCOUNT_ID")
    if not sms_adapter._is_valid(settings.SMS_FROM_NUMBER):
        missing.append("SMS_FROM_NUMBER")
    if not sms_adapter._is_valid(settings.TEST_PHONE_NUMBER):
        missing.append("TEST_PHONE_NUMBER")

    has_api_key = sms_adapter._is_valid(settings.SMS_API_KEY_SID) and sms_adapter._is_valid(settings.SMS_API_KEY_SECRET)
    has_auth_token = sms_adapter._is_valid(settings.SMS_AUTH_TOKEN)
    if not (has_api_key or has_auth_token):
        missing.append("SMS_AUTH_TOKEN or (SMS_API_KEY_SID and SMS_API_KEY_SECRET)")

    output_lines = []
    if missing or not configured:
        output_lines.append("SMS CONFIGURATION INCOMPLETE")
        output_lines.append("Missing/placeholder:")
        for item in missing:
            output_lines.append(f"- {item}")
        
        with open(r"c:\Users\rajub\Downloads\genai\genai\sms_out_log.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        
        pytest.fail(f"SMS Configuration Incomplete: {missing}")

    else:
        output_lines.append("EXECUTING REAL SMS TEST")
        res = sms_adapter.send_sms(
            recipients=[settings.TEST_PHONE_NUMBER],
            message="CAMPUSFLOW AI: Controlled Real-Time SMS Emergency Test"
        )
        output_lines.append(f"Success: {res.success}")
        output_lines.append(f"Status: {res.status.value}")
        output_lines.append(f"Provider: {res.provider}")
        output_lines.append(f"Message ID: {res.message_id}")
        if res.error:
            output_lines.append(f"Error: {res.error}")

        if res.success and res.message_id:
            delivery = sms_adapter.get_delivery_status(res.message_id)
            output_lines.append(f"Delivery Status: {delivery.get('status')}")

        with open(r"c:\Users\rajub\Downloads\genai\genai\sms_out_log.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))

        
        assert res.success is True, f"Real SMS Provider failed: {res.error}"
        assert res.message_id is not None

