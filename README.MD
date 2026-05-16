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

## Troubleshooting

- If config.json is missing or malformed, the app will display a clear error message and exit
- Use `debug: true` in config to see Minecraft server check logs in console
- Set `verify_tls: false` on an endpoint to disable TLS verification (not recommended for production)