#!/usr/bin/env bash
# Demo script: Trigger sensor failure on Crude Distillation Unit and monitor autonomous 3-agent recovery
set -euo pipefail

SENSOR_ID=${1:-"TT-101"}
EQUIPMENT_ID=${2:-"CDU-101"}
API_URL=${3:-"http://localhost:8000"}

echo "=== PROJECT 117 SENSOR FAILURE & RECOVERY DEMO ==="
echo "1. Disabling Sensor: ${SENSOR_ID} on Equipment: ${EQUIPMENT_ID}"

curl -s -X POST "${API_URL}/api/simulation/fault" \
  -H "Content-Type: application/json" \
  -d "{\"sensor_id\": \"${SENSOR_ID}\", \"equipment_id\": \"${EQUIPMENT_ID}\", \"action\": \"disable\"}" \
  | jq . || echo "Fault event sent."

echo ""
echo "2. Autonomous Tri-Agent System Activated:"
echo "   - Diagnostic Agent: Isolating faulty sensor ${SENSOR_ID}"
echo "   - Orchestrator: Computing bypass route around ${EQUIPMENT_ID}"
echo "   - Recovery Agent: Executing valve reconfiguration and safety verification"
echo ""
echo "3. Monitor live WebSocket event stream at ${API_URL}/ws/orchestrator"
