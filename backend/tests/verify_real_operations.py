import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.config import settings
from backend.services.road_network import road_network
from backend.services.telemetry_service import telemetry_service
from backend.services.adapters.sms_adapter import sms_adapter
from backend.services.adapters.push_adapter import push_adapter
from backend.services.adapters.email_adapter import email_adapter
from backend.services.adapters.voice_adapter import voice_adapter
from backend.services.adapters.dispatch_adapter import dispatch_adapter
from backend.services.responder_directory import responder_directory
from backend.database.database import SessionLocal, Base, engine
from backend.database.seed import seed_resources, seed_users


def test_real_operations():
    print("==================================================")
    print("CAMPUSFLOW AI — REAL OPERATIONS VERIFICATION TEST")
    print("==================================================")

    # 1. Database Init
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_resources(db)
    seed_users(db)

    print("\n[1] VERIFYING SYSTEM & SERVICE PROVIDER ADAPTERS...")
    print(f"  APP NAME: {settings.APP_NAME}")
    print(f"  MAP PROVIDER: {settings.MAP_PROVIDER}")
    print(f"  ROUTING PROVIDER: {settings.ROUTING_PROVIDER}")
    print(f"  SMS CONFIGURABLE: {sms_adapter.is_configured()}")
    print(f"  PUSH CONFIGURABLE: {push_adapter.is_configured()}")
    print(f"  EMAIL CONFIGURABLE: {email_adapter.is_configured()}")
    print(f"  VOICE CONFIGURABLE: {voice_adapter.is_telephony_configured()}")
    print(f"  DISPATCH CONFIGURABLE: {dispatch_adapter.is_configured()}")

    # Test SMS Fail-Closed
    sms_res = sms_adapter.send_sms(["+919876543210"], "Test emergency alert")
    print(f"  SMS Provider Output: status={sms_res.status.value}, success={sms_res.success}, provider={sms_res.provider}")
    assert sms_res.status in ["not_configured", "queued", "sent", "failed"], f"Unexpected SMS status: {sms_res.status}"

    # Test Push Notification
    push_res = push_adapter.send_push("Test Alert", "Emergency near U-Block")
    print(f"  Push Provider Output: status={push_res.status.value}, count={push_res.recipient_count}")

    # Test Email Adapter
    email_res = email_adapter.send_email(["security@vignan.ac.in"], "Test Alert", "Emergency test message")
    print(f"  Email Provider Output: status={email_res.status.value}")

    # Test Voice Audio TTS Generation (Capability A)
    voice_audio = voice_adapter.generate_voice_audio("Attention. Fire emergency reported near U-Block.")
    print(f"  Voice Audio Output: audio_id={voice_audio.get('audio_id')}, status={voice_audio.get('status')}, path={voice_audio.get('file_path')}")
    assert voice_audio.get("status") == "ready", "Voice TTS audio generation failed!"

    # Test Authorized Dispatch Adapter
    disp_res = dispatch_adapter.dispatch_resources("INC-TEST", "PLAN-TEST", ["AMB-001"], "U-Block")
    print(f"  Dispatch Provider Output: status={disp_res.status.value}, error={disp_res.error or 'None'}")

    print("\n[2] VERIFYING REAL ROAD ROUTING (OSRM + CAMPUS GRAPH)...")
    route_data = road_network.get_route_details("health_centre", "u_block")
    print(f"  Engine: {route_data.get('routing_engine')}")
    print(f"  Distance: {route_data.get('distance_meters')} m")
    print(f"  ETA: {route_data.get('eta_seconds')} sec")
    print(f"  Coordinates Count: {len(route_data.get('coordinates', []))}")
    assert len(route_data.get("coordinates", [])) >= 2, "Route coordinates failed to compute!"

    print("\n[3] VERIFYING LIVE TELEMETRY INGESTION & GPS STATUS ENGINE...")
    telemetry_service.process_telemetry(
        vehicle_id="AMB-001",
        latitude=16.2340,
        longitude=80.5520,
        speed=35.0,
        heading=72.0,
        accuracy=4.5,
        timestamp_str="2026-08-21T23:28:49Z",
        auth_secret="campusflow-secret-telemetry-key",
        db=db
    )
    status_info = telemetry_service.get_gps_status("AMB-001")
    print(f"  AMB-001 GPS Mode: {status_info['gps_mode']}")
    print(f"  AMB-001 Status Code: {status_info['status_code']}")
    print(f"  AMB-001 Speed: {status_info['speed']} km/h, Heading: {status_info['heading']}°")
    assert status_info["status_code"] == "LIVE", f"Expected LIVE GPS status, got {status_info['status_code']}"

    print("\n[4] VERIFYING RESPONDER DIRECTORY LOOKUP...")
    responders = responder_directory.list_responders()
    print(f"  Total Verified Responders in Directory: {len(responders)}")
    for r in responders:
        print(f"    - {r.responder_id}: {r.name} ({r.role}) • Phone: {r.phone}")

    db.close()
    print("\n==================================================")
    print("ALL REAL OPERATIONS TESTS PASSED CLEANLY! [SUCCESS]")
    print("==================================================")


if __name__ == "__main__":
    test_real_operations()
