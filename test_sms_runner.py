import sys
from backend.config import settings
from backend.services.adapters.sms_adapter import sms_adapter

def run():
    lines = []
    lines.append("--- SMS INTEGRATION TEST ---")
    configured = sms_adapter.is_configured()
    lines.append(f"SMS Configured: {configured}")

    missing = []
    if not settings.SMS_PROVIDER or str(settings.SMS_PROVIDER).lower() in sms_adapter.PLACEHOLDERS:
        missing.append("SMS_PROVIDER")
    if not settings.SMS_ACCOUNT_ID or str(settings.SMS_ACCOUNT_ID).lower() in sms_adapter.PLACEHOLDERS:
        missing.append("SMS_ACCOUNT_ID")
    if not settings.SMS_AUTH_TOKEN or str(settings.SMS_AUTH_TOKEN).lower() in sms_adapter.PLACEHOLDERS:
        missing.append("SMS_AUTH_TOKEN")
    if not settings.SMS_FROM_NUMBER or str(settings.SMS_FROM_NUMBER).lower() in sms_adapter.PLACEHOLDERS:
        missing.append("SMS_FROM_NUMBER")
    if not settings.TEST_PHONE_NUMBER or str(settings.TEST_PHONE_NUMBER).lower() in sms_adapter.PLACEHOLDERS:
        missing.append("TEST_PHONE_NUMBER")

    if missing or not configured:
        lines.append("SMS CONFIGURATION INCOMPLETE")
        lines.append("Missing/placeholder:")
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("All SMS credentials present. Sending ONE controlled test SMS...")
        res = sms_adapter.send_sms(
            recipients=[settings.TEST_PHONE_NUMBER],
            message="CAMPUSFLOW AI: Controlled Real-Time SMS Emergency Test"
        )
        lines.append(f"Result Success: {res.success}")
        lines.append(f"Result Status: {res.status.value}")
        lines.append(f"Result Provider: {res.provider}")
        lines.append(f"Message ID: {res.message_id}")
        if res.error:
            lines.append(f"Error: {res.error}")

        if res.success and res.message_id:
            lines.append("Querying delivery status...")
            delivery = sms_adapter.get_delivery_status(res.message_id)
            lines.append(f"Delivery Status: {delivery.get('status')}")

    out_str = "\n".join(lines)
    print(out_str)
    with open("sms_result.txt", "w", encoding="utf-8") as f:
        f.write(out_str)


if __name__ == "__main__":
    run()
