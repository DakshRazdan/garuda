// app.js — the farmer-side capture + offline sync logic.
//
// IMPORTANT: this file talks ONLY to the API (farmer_api.py), never to
// Postgres directly. No database credentials exist anywhere in this
// codebase — that's the whole point of having the API in between.

const API_BASE = window.location.origin;
const QUEUE_KEY = "gi_batch_queue";
const FARMS_CACHE_KEY = "gi_farms_cache";

// ---------- capture_hash: MUST exactly match hash_chain.compute_capture_hash ----------
// Python:  f"{farm_id}|{weight:.3f}|{crop_type}|{timestamp_iso}|{geotag}"
async function computeCaptureHash(farmId, weightKg, cropType, timestampIso, geotag) {
  const normalizedWeight = Number(weightKg).toFixed(3);
  const payload = `${farmId}|${normalizedWeight}|${cropType}|${timestampIso}|${geotag}`;
  const encoded = new TextEncoder().encode(payload);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

// ---------- geolocation, with a safe offline-friendly fallback ----------
function getGeotag() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve("unavailable");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(`${pos.coords.latitude.toFixed(5)},${pos.coords.longitude.toFixed(5)}`),
      () => resolve("unavailable"),       // permission denied, or no GPS fix yet — don't block capture
      { timeout: 5000 },
    );
  });
}

// ---------- local offline queue (works with zero connectivity) ----------
function getQueue() {
  return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
}
function saveQueue(queue) {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}
function enqueue(record) {
  const queue = getQueue();
  queue.push(record);
  saveQueue(queue);
  updateQueueCount();
}

function updateQueueCount() {
  const n = getQueue().length;
  const el = document.getElementById("queueCount");
  el.textContent = n === 0
    ? "All batches synced."
    : `${n} batch${n > 1 ? "es" : ""} waiting to sync (offline or not yet sent).`;
  el.className = n === 0 ? "ok" : "pending";
}

// ---------- syncing the queue to the server whenever we can ----------
async function trySync() {
  const queue = getQueue();
  if (queue.length === 0) return;

  const remaining = [];
  for (const record of queue) {
    try {
      const res = await fetch(`${API_BASE}/farmer/batches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(record),
      });
      if (!res.ok) {
        // Server rejected it (e.g. integrity check failed, unknown farm) —
        // don't keep retrying something that will never succeed.
        const err = await res.json().catch(() => ({}));
        console.error("Batch rejected, dropping from queue:", err);
        continue;
      }
      const data = await res.json();
      console.log("Synced batch:", data.batch_id, data.row_hash);
    } catch (e) {
      // Network error — still offline, keep it queued for next attempt.
      remaining.push(record);
    }
  }
  saveQueue(remaining);
  updateQueueCount();
}

// ---------- farm dropdown, with offline caching ----------
async function loadFarms() {
  const select = document.getElementById("farmId");
  try {
    const res = await fetch(`${API_BASE}/farmer/farms`);
    const farms = await res.json();
    localStorage.setItem(FARMS_CACHE_KEY, JSON.stringify(farms));
    populateFarms(farms);
  } catch (e) {
    const cached = JSON.parse(localStorage.getItem(FARMS_CACHE_KEY) || "[]");
    populateFarms(cached);
  }
}
function populateFarms(farms) {
  const select = document.getElementById("farmId");
  select.innerHTML = "";
  if (farms.length === 0) {
    select.innerHTML = `<option value="">No farms cached — connect once to load</option>`;
    return;
  }
  for (const f of farms) {
    const opt = document.createElement("option");
    opt.value = f.farm_id;
    opt.textContent = f.name;
    select.appendChild(opt);
  }
}

// ---------- form submission ----------
document.getElementById("batchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById("status");

  const farmId = document.getElementById("farmId").value;
  const cropType = document.getElementById("cropType").value.trim();
  const weightKg = parseFloat(document.getElementById("weightKg").value);

  if (!farmId) {
    statusEl.textContent = "No farm selected — cannot log a batch.";
    statusEl.className = "err";
    return;
  }

  const timestampIso = new Date().toISOString();
  const geotag = await getGeotag();
  const captureHash = await computeCaptureHash(farmId, weightKg, cropType, timestampIso, geotag);

  const record = {
    farm_id: farmId,
    weight_kg: weightKg,
    crop_type: cropType,
    timestamp_iso: timestampIso,
    geotag: geotag,
    capture_hash: captureHash,
  };

  // Always queue first — this is what makes it offline-first. Even if
  // we're online, we queue-then-sync rather than assuming the network
  // call will succeed; if it fails partway, the record isn't lost.
  enqueue(record);
  statusEl.textContent = "Batch captured. Syncing...";
  statusEl.className = "pending";

  await trySync();

  statusEl.textContent = getQueue().length === 0
    ? "Batch captured and synced successfully."
    : "Batch captured — will sync automatically once online.";
  statusEl.className = getQueue().length === 0 ? "ok" : "pending";

  document.getElementById("batchForm").reset();
});

// ---------- auto-sync triggers ----------
window.addEventListener("online", trySync);
setInterval(trySync, 15000);   // retry every 15s in case 'online' event is missed

// ---------- initial load ----------
loadFarms();
updateQueueCount();
trySync();

// ---------- register service worker for offline app-shell caching ----------
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(console.error);
}
