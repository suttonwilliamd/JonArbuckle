# JonArbuckle - Service Monitor

A Tkinter-based service monitoring dashboard that displays endpoint status in both mini-bar and full dashboard views.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python jonarbuckle.py
   ```
   Or double-click `jonarbuckle.pyw` on Windows.

## Configuration

Edit `config.json` to configure endpoints and behavior.

### Garfield Homelab Baseline (current)

`config.json` is now aligned to the active services in `/home/suttonwilliamd/docker-compose.yml` and live checks on host `192.168.7.57`.

Monitored local services now include:
- Garfield SSH (`192.168.7.57:22`)
- Jellyfin local (`:8096`)
- Firecrawl local health (`:3002/health`)
- Garfield OBS Avatar overlay (`:8899`)
- qBittorrent WebUI (`:8081`)

Monitored public services include:
- `william64.com`, `dev.william64.com`, `dash.william64.com`, `cms.william64.com`
- `jellyfin.william64.com`, `mc.william64.com`
- `traefik.william64.com`

Monitored APIs include:
- `/api/server-stats`
- `/api/qbittorrent-stats`
- `/api/mc-status`

Removed stale local checks:
- `http://192.168.7.57` (redirect/TLS mismatch noise)
- `https://192.168.7.57` OMV check (not reliable for this dashboard use-case)

### Global Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `refresh_interval` | int | 1 | Refresh interval in seconds |
| `mini_mode_size` | string | "660x70" | Mini bar window size (WxH) |
| `start_mini` | bool | false | Start in mini mode |
| `debug` | bool | false | Enable debug logging for Minecraft checks |
| `default_retries` | int | 1 | Default HTTP retries for transient failures |
| `default_backoff_ms` | int | 200 | Delay between HTTP retries in milliseconds |

### Endpoint Configuration

Each endpoint supports these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | - | Display name |
| `type` | string | "http" | Endpoint type: "http", "ssh", "tcp", "minecraft" |
| `url` | string | - | HTTP endpoint URL (for http type) |
| `host` | string | - | Hostname/IP (for ssh, tcp, minecraft) |
| `port` | int | - | Port number |
| `verify_tls` | bool | true | Enable TLS verification for HTTP endpoints |
| `timeout` | int | 5 (http), 3 (ssh/tcp), 10 (minecraft) | Request timeout in seconds |
| `retries` | int | inherits `default_retries` | HTTP retry count for transient failures |
| `backoff_ms` | int | inherits `default_backoff_ms` | Delay between HTTP retries in milliseconds |
| `check_jellyfin` | bool | false | Verify Jellyfin server response |

### HTTP retry behavior

For HTTP endpoints, `retries` is the number of additional attempts after the
initial request (zero means one request). Received HTTP 500–599 responses and
existing transient exceptions (connection errors, timeouts, and HTTPError with a
5xx response) share that attempt budget. Other responses, including 4xx, return
immediately. Endpoint retry/backoff settings override the global defaults.

The fixed `backoff_ms` delay occurs only between attempts, never after the last
attempt. Discarded intermediate 5xx responses are closed before the next attempt.
An exhausted 5xx is returned unchanged: the dashboard still reports yellow
`HTTP 5xx`, not green or an exception-based red status. Exhausted transient
exceptions are still raised. Timeout and TLS verification settings are forwarded
unchanged on every request; TLS verification remains enabled by default.

`timeout` applies to each Requests call, not a strict whole-operation deadline.
Requests timeouts do not bound all DNS, redirects, or total response-read time;
multiple attempts and fixed backoff can further increase elapsed time. Keep
retry counts and delays modest; this is not a whole-app networking safety claim.

### Endpoint Categories

Endpoints are organized in three categories:
- `local_endpoints` - Local network services
- `public_endpoints` - Public-facing sites
- `api_endpoints` - API endpoints

### Example Configuration

```json
{
    "refresh_interval": 5,
    "debug": true,
    "default_retries": 1,
    "default_backoff_ms": 200,
    "start_mini": false,
    "local_endpoints": [
        {
            "name": "Home Server",
            "url": "http://192.168.1.100",
            "type": "http",
            "timeout": 5
        },
        {
            "name": "SSH Server",
            "host": "192.168.1.100",
            "port": 22,
            "type": "ssh",
            "timeout": 3
        }
    ],
    "public_endpoints": [
        {
            "name": "My Site",
            "url": "https://example.com",
            "type": "http",
            "verify_tls": true,
            "timeout": 10,
            "retries": 2,
            "backoff_ms": 300
        }
    ],
    "api_endpoints": [
        {
            "name": "API",
            "url": "https://api.example.com/health",
            "type": "http",
            "verify_tls": true
        }
    ]
}
```

## Usage

- **Double-click** mini bar to open full dashboard
- **Right-click** mini bar to exit and save window size
- Drag mini bar to reposition
- Double-click full dashboard to return to mini mode
- Status indicators: green (service fully up), yellow (warning/degraded), red (down)
- Minecraft checks now distinguish:
  - `green`: Minecraft instance responded to status ping
  - `yellow`: spin-up gateway reachable but MC instance appears asleep/booting
  - `red`: Minecraft port not reachable

## Offline HTTP contract tests

Use Python 3.11 or 3.13 with Tkinter available and real dependencies installed in
an isolated environment. Do **not** run the dashboard or the default launchers
for these tests. No display server is needed: the suite imports only the core,
blocks desktop/thread/config side effects, uses reserved `.invalid` URLs, injects
HTTP responses/exceptions and sleeps, and rejects real Requests/socket/DNS
transport. No real `config.json` or endpoint is read or contacted.

Ubuntu (with Python/Tkinter already available):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
timeout 60 .venv/bin/python -B -m unittest discover -s tests -v
```

Windows PowerShell (Python installed with Tcl/Tk support):

```powershell
py -3.13 -m venv .venv # or -3.11
.venv/Scripts/python.exe -m pip install -r requirements.txt
$job = Start-Job -ScriptBlock {
    param($repo)
    Set-Location $repo
    & .venv/Scripts/python.exe -B -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
} -ArgumentList $PWD.Path
try {
    if (-not (Wait-Job $job -Timeout 60)) { throw 'Offline tests timed out' }
    Receive-Job $job -ErrorAction Stop
    if ($job.State -ne 'Completed') { throw 'Offline tests failed' }
} finally {
    Stop-Job $job
    Remove-Job $job
}
```

`.github/workflows/offline-tests.yml` defines the equivalent Ubuntu/Windows ×
Python 3.11/3.13 matrix, with read-only repository permissions, no persisted Git
credentials, isolated dependencies, and a five-minute job timeout. Dependency
installation requires package-registry access; the tests themselves are offline.
The workflow is a proposed verification path, not evidence that those platforms
have run. These tests do not qualify native desktop behavior, live endpoints,
packaging, deployment, or Minecraft/non-waking safety.

## Troubleshooting

- If config.json is missing or malformed, the app will display a clear error message and exit
- Use `debug: true` in config to see Minecraft server check logs in console
- Set `verify_tls: false` on an endpoint to disable TLS verification (not recommended for production)