#!/usr/bin/env bash
# List motion resources installed on an A3 Ultra (read-only).
# Usage: ./list_motion_resources.sh [MDU-IP]

set -euo pipefail

MDU_IP="${1:-10.42.10.10}"
URL="http://${MDU_IP}:51049/rpc/aimdk.protocol.ResourceService/GetResourceList"

response="$(curl --fail-with-body --silent --show-error \
  -H 'content-type: application/json' \
  -X POST "$URL" \
  -d '{"resource_type":"RESOURCE_TYPE_MOTION"}')"

python3 -c '
import json, sys
data = json.load(sys.stdin)
resources = data.get("resources", [])
if not resources:
    print("No motion resources reported.")
for resource in resources:
    print(resource.get("resource_path", ""))
' <<< "$response"
