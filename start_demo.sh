!/bin/bash
# start_demo.sh — run this ONCE, a few minutes before your demo.
# It starts Postgres, starts the API (which also serves all 4 frontends),
# and opens your browser tabs automatically. After this finishes, you
# should never need to touch the terminal again during the actual demo.
#
# Usage:
#   chmod +x start_demo.sh   (only needed once, ever)
#   ./start_demo.sh
#
# To stop everything after your demo: press Ctrl+C in this terminal window.
 
set -e
 
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$REPO_ROOT/venv/bin/python"
VENV_UVICORN="$REPO_ROOT/venv/bin/uvicorn"
PORT=8000
 
echo "=== 1/4: Starting Postgres ==="
sudo service postgresql start
sleep 1
 
echo "=== 2/4: Confirming database is reachable ==="
if ! PGPASSWORD=gi_pass psql -U gi_user -d gi_ledger -h localhost -c "SELECT 1;" > /dev/null 2>&1; then
    echo "!! Could not reach Postgres. Check that the gi_ledger database exists and Postgres is running."
    exit 1
fi
echo "Database OK."
 
echo "=== 3/4: Starting the API server (serves API + all 4 dashboards) ==="
cd "$REPO_ROOT/api"
export DATABASE_URL="postgresql://gi_user:gi_pass@localhost:5432/gi_ledger"
"$VENV_UVICORN" main:app --host 0.0.0.0 --port $PORT &
UVICORN_PID=$!
sleep 3
 
if ! curl -s "http://127.0.0.1:$PORT/health" > /dev/null; then
    echo "!! API did not start correctly. Check the output above for errors."
    exit 1
fi
echo "API is live."
 
echo "=== 4/4: Opening browser tabs ==="
BASE="http://localhost:$PORT"
for path in "/regulator/" "/consumer/" "/farmer-app/" "/nfc-capture/"; do
    explorer.exe "$BASE$path" 2>/dev/null || true
    sleep 0.5
done
 
echo
echo "======================================================"
echo " Everything is running. Browser tabs should be open."
echo " Regulator dashboard : $BASE/regulator/"
echo " Consumer verify     : $BASE/consumer/"
echo " Farmer batch capture: $BASE/farmer-app/"
echo " NFC capture tool    : $BASE/nfc-capture/"
echo
echo " Leave THIS terminal window open in the background —"
echo " closing it stops the server. You don't need to type"
echo " anything else into it during your demo."
echo " Press Ctrl+C here when your demo is completely done."
echo "======================================================"
 
wait $UVICORN_PID
 