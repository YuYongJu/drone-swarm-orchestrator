"""
Minimal web-based map visualization for drone swarms.

Serves a single-page Leaflet.js map that shows drone positions in real-time
via Server-Sent Events (SSE). No external dependencies beyond the stdlib.

Usage::

    from drone_swarm.viz import start_map_server
    stop = await start_map_server(swarm, port=8080, open_browser=True)
    # ... fly drones ...
    stop()
"""

from __future__ import annotations

import json
import logging
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .swarm import SwarmOrchestrator

logger = logging.getLogger("drone_swarm.viz")

# The map HTML uses only trusted server-generated JSON data via SSE,
# and constructs DOM elements using safe DOM APIs (createElement/textContent).
MAP_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>drone-swarm live map</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9/dist/leaflet.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#1a1a2e; color:#e0e0e0; font-family:monospace; }
  #map { width:100vw; height:80vh; }
  #panel { padding:12px 16px; display:flex; gap:24px; flex-wrap:wrap; }
  .drone-card {
    background:#16213e; border:1px solid #0f3460; border-radius:6px;
    padding:8px 14px; min-width:180px;
  }
  .drone-card-title { color:#e94560; margin-bottom:4px; font-size:14px; font-weight:bold; }
  .drone-card-body { font-size:12px; line-height:1.6; color:#a0a0c0; }
  .status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="panel"></div>
<script>
const map = L.map('map').setView([0, 0], 18);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '\u00a9 OSM \u00a9 CARTO', maxZoom: 20
}).addTo(map);

const markers = {};
const trails = {};
const panel = document.getElementById('panel');
let centered = false;

const STATUS_COLORS = {
  connected: '#4ecca3', armed: '#f5a623', airborne: '#00d2ff',
  returning: '#f5a623', lost: '#e94560', disconnected: '#666'
};

function getColor(status) {
  return STATUS_COLORS[status] || '#fff';
}

function updateDrone(id, data) {
  const lat = data.lat, lon = data.lon;
  if (lat === 0 && lon === 0) return;

  if (!markers[id]) {
    markers[id] = L.circleMarker([lat, lon], {
      radius: 8, fillColor: getColor(data.status),
      fillOpacity: 0.9, color: '#fff', weight: 2
    }).addTo(map).bindTooltip(id, {permanent: true, direction: 'top', offset: [0, -10]});
    trails[id] = L.polyline([], {color: getColor(data.status), weight: 2, opacity: 0.5}).addTo(map);
  }

  markers[id].setLatLng([lat, lon]);
  markers[id].setStyle({fillColor: getColor(data.status)});
  trails[id].addLatLng([lat, lon]);

  if (!centered) {
    map.setView([lat, lon], 18);
    centered = true;
  }
}

function updatePanel(drones) {
  // Clear panel using safe DOM methods
  while (panel.firstChild) { panel.removeChild(panel.firstChild); }

  for (const [id, d] of Object.entries(drones)) {
    const card = document.createElement('div');
    card.className = 'drone-card';

    const title = document.createElement('div');
    title.className = 'drone-card-title';
    const dot = document.createElement('span');
    dot.className = 'status-dot';
    dot.style.backgroundColor = getColor(d.status);
    title.appendChild(dot);
    title.appendChild(document.createTextNode(id));
    card.appendChild(title);

    const body = document.createElement('div');
    body.className = 'drone-card-body';
    const lines = [
      'Status: ' + d.status,
      'Pos: ' + d.lat.toFixed(6) + ', ' + d.lon.toFixed(6),
      'Alt: ' + d.alt.toFixed(1) + 'm | Hdg: ' + d.heading.toFixed(0) + '\u00b0',
      'Batt: ' + d.battery_pct.toFixed(0) + '%'
    ];
    lines.forEach(function(line, i) {
      if (i > 0) body.appendChild(document.createElement('br'));
      body.appendChild(document.createTextNode(line));
    });
    card.appendChild(body);
    panel.appendChild(card);
  }
}

// Server-Sent Events for real-time telemetry (trusted server data)
const evtSource = new EventSource('/telemetry');
evtSource.onmessage = function(event) {
  const drones = JSON.parse(event.data);
  for (const [id, d] of Object.entries(drones)) {
    updateDrone(id, d);
  }
  updatePanel(drones);
};
evtSource.onerror = function() {
  console.log('SSE connection lost, reconnecting...');
};
</script>
</body>
</html>"""


async def start_map_server(
    swarm: SwarmOrchestrator,
    port: int = 8080,
    open_browser: bool = True,
) -> callable:
    """
    Start a lightweight HTTP server that serves a live drone map.

    Returns a callable that stops the server when invoked.

    Args:
        swarm: The SwarmOrchestrator instance to visualize.
        port: HTTP port. Default 8080.
        open_browser: If True, opens the map in the default browser.

    Returns:
        A ``stop()`` function to shut down the server.
    """

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(MAP_HTML.encode())
            elif self.path == "/telemetry":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    while True:
                        import time
                        time.sleep(0.25)  # 4Hz
                        data = _get_telemetry_json(swarm)
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            pass  # suppress default request logging

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Map server running at http://localhost:%d", port)

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    def stop():
        server.shutdown()
        logger.info("Map server stopped")

    return stop


def _get_telemetry_json(swarm: SwarmOrchestrator) -> str:
    """Serialize current drone states as JSON."""
    data = {}
    for drone_id, drone in swarm.drones.items():
        data[drone_id] = {
            "lat": drone.lat,
            "lon": drone.lon,
            "alt": drone.alt,
            "heading": drone.heading,
            "battery_pct": drone.battery_pct,
            "status": drone.status.value,
        }
    return json.dumps(data)
