import sys
import os
import traceback

log_file = r"c:\Users\rajub\Downloads\genai\genai\sms_check_output.txt"
with open(log_file, "w", encoding="utf-8") as f:
    f.write("--- STARTING CHECK_ENV ---\n")
    f.flush()
    try:
        f.write(f"Python executable: {sys.executable}\n")
        f.flush()

        from backend.config import settings
        from backend.services.adapters.sms_adapter import sms_adapter

        f.write(f"SMS_PROVIDER: {repr(settings.SMS_PROVIDER)}\n")
        f.write(f"SMS_ACCOUNT_ID set: {bool(settings.SMS_ACCOUNT_ID)}\n")
        f.write(f"SMS_AUTH_TOKEN set: {bool(settings.SMS_AUTH_TOKEN)}\n")
        f.write(f"SMS_API_KEY_SID set: {bool(settings.SMS_API_KEY_SID)}\n")
        f.write(f"SMS_API_KEY_SECRET set: {bool(settings.SMS_API_KEY_SECRET)}\n")
        f.write(f"SMS_FROM_NUMBER set: {bool(settings.SMS_FROM_NUMBER)}\n")
        f.write(f"TEST_PHONE_NUMBER set: {bool(settings.TEST_PHONE_NUMBER)}\n")
        f.write(f"is_configured: {sms_adapter.is_configured()}\n")
        f.flush()

        missing = []
        if not sms_adapter._is_valid(settings.SMS_PROVIDER): missing.append("SMS_PROVIDER")
        if not sms_adapter._is_valid(settings.SMS_ACCOUNT_ID): missing.append("SMS_ACCOUNT_ID")
        if not sms_adapter._is_valid(settings.SMS_FROM_NUMBER): missing.append("SMS_FROM_NUMBER")
        if not sms_adapter._is_valid(settings.TEST_PHONE_NUMBER): missing.append("TEST_PHONE_NUMBER")
        has_api_key = sms_adapter._is_valid(settings.SMS_API_KEY_SID) and sms_adapter._is_valid(settings.SMS_API_KEY_SECRET)
        has_auth_token = sms_adapter._is_valid(settings.SMS_AUTH_TOKEN)
        if not (has_api_key or has_auth_token):
            missing.append("SMS_AUTH_TOKEN or (SMS_API_KEY_SID and SMS_API_KEY_SECRET)")

        f.write(f"missing_list: {missing}\n")
        f.flush()

        if not missing and sms_adapter.is_configured():
            f.write("SENDING_REAL_TEST_SMS...\n")
            f.flush()
            res = sms_adapter.send_sms([settings.TEST_PHONE_NUMBER], "CAMPUSFLOW AI: Controlled Real-Time SMS Emergency Test")
            f.write(f"success: {res.success}\n")
            f.write(f"status: {res.status.value}\n")
            f.write(f"provider: {res.provider}\n")
            f.write(f"message_id: {res.message_id}\n")
            if res.details:
                f.write(f"auth_mode: {res.details.get('auth_mode')}\n")
                f.write(f"twilio_status: {res.details.get('twilio_status')}\n")
            if res.error:
                f.write(f"error: {res.error}\n")

            if res.success and res.message_id:
                delivery = sms_adapter.get_delivery_status(res.message_id)
                f.write(f"delivery_status: {delivery.get('status')}\n")
        else:
            f.write("SMS CONFIGURATION INCOMPLETE\n")
        f.flush()

    except Exception as e:
        f.write(f"EXCEPTION: {e}\n")
        f.write(traceback.format_exc())
        f.flush()
