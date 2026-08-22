import urllib.request
import json
import os

url = "http://127.0.0.1:8000/api/v1/system/status"
dest = os.path.join(os.path.dirname(__file__), "system_status_result.json")

try:
    req = urllib.request.urlopen(url, timeout=5)
    data = json.loads(req.read().decode("utf-8"))
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"SAVED TO {dest}")
except Exception as e:
    with open(dest, "w", encoding="utf-8") as f:
        json.dump({"error": str(e)}, f, indent=2)
    print(f"ERROR: {e}")
