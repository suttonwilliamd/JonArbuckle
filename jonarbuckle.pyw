import tkinter as tk
import requests
import json
import socket
import struct
import concurrent.futures
import plyer
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple
import threading
import warnings
from mcstatus import JavaServer
warnings.filterwarnings("ignore")

# ── Palette ────────────────────────────────────────────────────────────────────
BG          = "#0a0f1c"
SURFACE     = "#111827"
SURFACE2    = "#1f2937"
BORDER      = "#374151"
TEXT        = "#f9fafb"
TEXT_DIM    = "#9ca3af"
TEXT_MUTED  = "#6b7280"

GREEN       = "#10b981"
YELLOW      = "#f59e0b"
RED         = "#ef4444"

CAT_LOCAL   = "#3b82f6"
CAT_PUBLIC  = "#f97316"
CAT_API     = "#ec4899"

FONT_MONO   = "Consolas"
FONT_ALT    = "Courier New"

STATUS_COLORS  = {"green": GREEN, "yellow": YELLOW, "red": RED}
STATUS_SYMBOLS = {"green": "●", "yellow": "◑", "red": "○"}

# ── Data ───────────────────────────────────────────────────────────────────────
@dataclass
class EndpointStatus:
    name: str
    url: str
    status: str
    response_time: float
    message: str
    last_checked: datetime

# ── Config ─────────────────────────────────────────────────────────────────────
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

# ── Endpoint checking ──────────────────────────────────────────────────────────
def check_endpoint(ep):
    url           = ep.get("url")
    host          = ep.get("host")
    port          = ep.get("port")
    name          = ep.get("name", url or host or "Unknown")
    endpoint_type = ep.get("type", "http")
    start_time    = datetime.now()

    if endpoint_type == "http" and url:
        try:
            resp    = requests.get(url, timeout=5, verify=False)
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            status  = "green" if resp.status_code < 400 else "yellow"
            message = f"HTTP {resp.status_code}"

            # Check if this endpoint should verify Jellyfin
            if ep.get("check_jellyfin"):
                jellyfin_detected = False
                # Check for Jellyfin indicators in headers or content
                server_header = resp.headers.get("Server", "").lower()
                x_application_header = resp.headers.get("X-Application", "").lower()
                content = resp.text.lower()

                if "jellyfin" in server_header or "jellyfin" in x_application_header:
                    jellyfin_detected = True
                elif "jellyfin" in content or "emby" in content:
                    jellyfin_detected = True

                if not jellyfin_detected:
                    status = "yellow"
                    message = "Not Jellyfin"

            return EndpointStatus(
                name=name, url=url,
                status=status,
                response_time=elapsed,
                message=message,
                last_checked=datetime.now()
            )
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return EndpointStatus(name=name, url=url, status="red",
                                  response_time=elapsed, message=str(e)[:30],
                                  last_checked=datetime.now())

    elif endpoint_type == "ssh" and host and port:
        try:
            sock   = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return EndpointStatus(
                name=name, url=f"{host}:{port}",
                status="green" if result == 0 else "red",
                response_time=elapsed,
                message="SSH OK" if result == 0 else f"Port {result}",
                last_checked=datetime.now()
            )
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return EndpointStatus(name=name, url=f"{host}:{port}", status="red",
                                  response_time=elapsed, message=str(e)[:30],
                                  last_checked=datetime.now())

    elif endpoint_type == "tcp" and host and port:
        try:
            sock   = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return EndpointStatus(
                name=name, url=f"{host}:{port}",
                status="green" if result == 0 else "red",
                response_time=elapsed,
                message="TCP OK" if result == 0 else f"Port {result}",
                last_checked=datetime.now()
            )
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return EndpointStatus(name=name, url=f"{host}:{port}", status="red",
                                  response_time=elapsed, message=str(e)[:30],
                                  last_checked=datetime.now())

    elif endpoint_type == "minecraft" and host and port:
        try:
            print(f"[{datetime.now()}] Checking Minecraft {host}:{port}...")
            # Try local IP first (for local network), then fallback to hostname
            hosts_to_try = [host]
            if host == "mc.william64.com":
                hosts_to_try = ["192.168.7.57", "mc.william64.com"]
            
            for try_host in hosts_to_try:
                try:
                    print(f"[{datetime.now()}] Trying {try_host}:{port}...")
                    server = JavaServer(try_host, port, timeout=10)
                    status = server.status()
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    version = status.version.name
                    players_online = status.players.online
                    players_max = status.players.max
                    msg = f"MC {version} | {players_online}/{players_max}"
                    print(f"[{datetime.now()}] SUCCESS: {msg}")
                    return EndpointStatus(name=name, url=f"{try_host}:{port}",
                                          status="green", response_time=elapsed,
                                          message=msg[:30],
                                          last_checked=datetime.now())
                except Exception as e:
                    print(f"[{datetime.now()}] {try_host} failed: {e}")
                    if try_host == hosts_to_try[-1]:
                        raise  # Re-raise if this was the last try
                    continue  # Try next host
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            print(f"[{datetime.now()}] FAILED: {type(e).__name__}: {e}")
            return EndpointStatus(name=name, url=f"{host}:{port}", status="red",
                                  response_time=elapsed, message=str(e)[:30],
                                  last_checked=datetime.now())

    return EndpointStatus(name=name, url=url or host, status="yellow",
                          response_time=0, message="Unknown",
                          last_checked=datetime.now())

# ── Notification ───────────────────────────────────────────────────────────────
def send_notification(title, message):
    try:
        plyer.notification.notify(title=f"JonArbuckle: {title}",
                                  message=message, timeout=5)
    except:
        pass

# ── Helpers ────────────────────────────────────────────────────────────────────
def make_frame(parent, bg=SURFACE, bd_color=BORDER, bd_width=1,
               padx=0, pady=0):
    """A frame with a 1-px border drawn via a wrapper Frame."""
    outer = tk.Frame(parent, bg=bd_color, padx=bd_width, pady=bd_width)
    inner = tk.Frame(outer, bg=bg, padx=padx, pady=pady)
    inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


def label(parent, text="", font_size=10, bold=False, color=TEXT,
          bg=SURFACE, anchor="w", **kw):
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text,
                    font=(FONT_MONO, font_size, weight),
                    fg=color, bg=bg, anchor=anchor, **kw)


# ── Main app ───────────────────────────────────────────────────────────────────
class JonArbuckle:
    def __init__(self):
        self.config        = load_config()
        self.endpoints: List[EndpointStatus] = []

        # widget registries
        self.mini_dots:   Dict[str, tk.Label] = {}
        self.mini_names:  Dict[str, tk.Label] = {}
        self.full_dots:   Dict[str, tk.Label] = {}
        self.full_labels: Dict[str, tk.Label] = {}
        self.full_indicators: Dict[str, Tuple[tk.Frame, tk.Label]] = {}

        mini_size      = self.config.get("mini_mode_size", "660x70").split("x")
        self.mini_w    = int(mini_size[0])
        self.mini_h    = int(mini_size[1])

        # ── Root (mini bar) ───────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BORDER)        # thin border via bg

        self.drag_data = {"start_x_root": 0, "start_y_root": 0, "win_x": 0, "win_y": 0}

        self.mini_canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.mini_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.mini_canvas.bind("<Button-3>",      lambda e: self.save_and_exit())
        self.mini_canvas.bind("<Double-Button-1>",lambda e: self.toggle_full())
        self.mini_canvas.bind("<Button-1>",      lambda e: self.drag_start(e))
        self.mini_canvas.bind("<B1-Motion>",      self.drag_window)

        self.aot_var = tk.BooleanVar(value=True)

        # Handle window close button (X) for root
        self.root.protocol("WM_DELETE_WINDOW", self.save_and_exit)

        self.endpoints_list = (self.config.get("local_endpoints", []) +
                               self.config.get("public_endpoints", []) +
                               self.config.get("api_endpoints", []))

        self.last_notifications  = {}
        self.notification_cooldown = 60
        self.mode = "full"
        self.checking = False  # Prevent overlapping checks

        self.build_full_window()
        self.build_mini_window()

        if self.config.get("start_mini", False):
            self.set_mode("mini")
        else:
            self.set_mode("full")

        self.root.after(2000, self.refresh_loop)
        self.root.mainloop()

    # ── Mini bar ───────────────────────────────────────────────────────────────
    def build_mini_window(self):
        local_eps  = self.config.get("local_endpoints", [])
        public_eps = self.config.get("public_endpoints", [])
        api_eps    = self.config.get("api_endpoints", [])

        categories = [
            (local_eps,  CAT_LOCAL),
            (public_eps, CAT_PUBLIC),
            (api_eps,    CAT_API),
        ]

        total_eps = sum(len(e) for e, _ in categories)
        n_cats    = sum(1 for e, _ in categories if e)

        # Grid layout: ~square, 3 columns
        COLS = 3
        ROWS = (total_eps + COLS - 1) // COLS + 1
        CELL_W = 80
        CELL_H = 40
        BAR_W = COLS * CELL_W + 8
        BAR_H = max(120, ROWS * CELL_H + 8)

        # Don't call set_mode here - it's called by the caller (toggle_mini or __init__)
        self.root.geometry(f"{BAR_W}x{BAR_H}+100+100")

        # destroy old widgets
        for d in self.mini_dots.values():   d.destroy()
        for n in self.mini_names.values():  n.destroy()
        self.mini_dots.clear()
        self.mini_names.clear()

        # ── shell — entire surface is draggable ───────────────────────────────
        if hasattr(self, 'shell'):
            self.shell.destroy()
        self.shell = tk.Frame(self.root, bg=BG, cursor="fleur")
        self.shell.place(x=0, y=0, relwidth=1, relheight=1)
        # Only bind drag events to the shell, not to individual widgets
        # This prevents event conflicts that cause sluggishness
        self.shell.bind("<Button-1>",       lambda e: self.drag_start(e))
        self.shell.bind("<B1-Motion>",      self.drag_window)
        self.shell.bind("<Double-Button-1>",lambda e: self.toggle_full())
        self.shell.bind("<Button-3>",       lambda e: self.save_and_exit())

        c = 0
        r = 0

        for ep_list, cat_color in categories:
            if not ep_list:
                continue

            for ep in ep_list:
                x = c * CELL_W + 4
                y = r * CELL_H + 2

                # status dot - no drag bindings, shell handles it
                dot = tk.Label(self.shell, text="●", font=(FONT_MONO, 12), bg=BG, fg=cat_color)
                dot.place(x=x+4, y=y+4)

                # endpoint name - special handling for Garfield SSH
                original_name = ep.get("name", ep.get("url", ep.get("host", "?")))
                display_name = original_name
                if original_name == "Garfield SSH":
                    display_name = "SSH"
                # Truncate display name to fit in the space
                label_text = display_name[:7]
                name_lbl = tk.Label(self.shell, text=label_text, font=(FONT_MONO, 8, "bold"), bg=BG, fg=cat_color, anchor="w")
                name_lbl.place(x=x+14, y=y+3)

                c += 1
                if c >= COLS:
                    c = 0
                    r += 1

                self.mini_dots[display_name]   = dot
                # self.mini_labels[display_name] = rt_lbl  # Response time removed to reduce clutter
                self.mini_names[display_name]  = name_lbl

    # ── Full dashboard ─────────────────────────────────────────────────────────
    def build_full_window(self):
        self.full = tk.Toplevel()
        self.full.title("JonArbuckle")
        self.full.geometry("900x600")
        self.full.configure(bg=BG)
        self.full.overrideredirect(False)
        self.full.attributes("-topmost", True)
        self.full.withdraw()
        # Handle window close button (X) for full window
        self.full.protocol("WM_DELETE_WINDOW", self.save_and_exit)

        # ── Title bar ─────────────────────────────────────────────────────────
        topbar = tk.Frame(self.full, bg=SURFACE, pady=0)
        topbar.pack(fill=tk.X, side=tk.TOP)

        # accent strip
        tk.Frame(topbar, bg=CAT_LOCAL, height=4).pack(fill=tk.X)

        header_row = tk.Frame(topbar, bg=SURFACE, padx=20, pady=12)
        header_row.pack(fill=tk.X)

        tk.Label(header_row, text="JON ARBUCKLE",
                 font=(FONT_MONO, 20, "bold"),
                 bg=SURFACE, fg=TEXT).pack(side=tk.LEFT)

        tk.Label(header_row, text="SERVICE MONITOR",
                 font=(FONT_MONO, 10),
                 bg=SURFACE, fg=TEXT_DIM).pack(side=tk.LEFT, padx=(15, 0), pady=(8, 0))

        # mini-mode button
        mini_btn = tk.Label(header_row, text="  ▼ COMPACT  ",
                            font=(FONT_MONO, 9, "bold"),
                            bg=BORDER, fg=TEXT_MUTED,
                            cursor="hand2", padx=8, pady=6)
        mini_btn.pack(side=tk.RIGHT)
        mini_btn.bind("<Button-1>", lambda e: self.toggle_mini())

        # last-refresh label
        self.refresh_lbl = tk.Label(header_row, text="last check: —",
                                     font=(FONT_MONO, 9),
                                     bg=SURFACE, fg=TEXT_DIM)
        self.refresh_lbl.pack(side=tk.RIGHT, padx=15)

        # ── Content ────────────────────────────────────────────────────────────
        content = tk.Frame(self.full, bg=BG, padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        sections = [
            ("LOCAL SERVICES", self.config.get("local_endpoints", []),  CAT_LOCAL),
            ("PUBLIC SITES",   self.config.get("public_endpoints", []), CAT_PUBLIC),
            ("API ENDPOINTS",  self.config.get("api_endpoints", []),    CAT_API),
        ]

        for col_idx, (sec_name, eps, cat_color) in enumerate(sections):
            # column
            col_frame = tk.Frame(content, bg=BG)
            col_frame.grid(row=0, column=col_idx, sticky="nsew",
                           padx=(0, 15 if col_idx < 2 else 0))
            content.columnconfigure(col_idx, weight=1)
            content.rowconfigure(0, weight=1)

            # section header
            hdr = tk.Frame(col_frame, bg=SURFACE, pady=0)
            hdr.pack(fill=tk.X, side=tk.TOP)
            tk.Frame(hdr, bg=cat_color, height=3).pack(fill=tk.X)

            hdr_inner = tk.Frame(hdr, bg=SURFACE, padx=12, pady=8)
            hdr_inner.pack(fill=tk.X)
            tk.Label(hdr_inner, text=sec_name,
                     font=(FONT_MONO, 10, "bold"),
                     bg=SURFACE, fg=cat_color).pack(side=tk.LEFT)
            count_lbl = tk.Label(hdr_inner,
                                 text=f"{len(eps)} endpoints",
                                 font=(FONT_MONO, 9),
                                 bg=SURFACE, fg=TEXT_DIM)
            count_lbl.pack(side=tk.RIGHT)

            # endpoint rows
            rows_frame = tk.Frame(col_frame, bg=SURFACE2)
            rows_frame.pack(fill=tk.BOTH, expand=True)

            for i, ep in enumerate(eps):
                name   = ep.get("name", ep.get("url", ep.get("host", "Unknown")))
                url    = ep.get("url", ep.get("host", ""))

                row_bg = SURFACE if i % 2 == 0 else SURFACE2
                row    = tk.Frame(rows_frame, bg=row_bg, padx=12, pady=8)
                row.pack(fill=tk.X, pady=2)

                # left accent strip
                tk.Frame(row, bg=cat_color, width=3).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

                # status indicator with colored background for better visibility
                indicator_frame = tk.Frame(row, bg=row_bg, width=28, height=28)
                indicator_frame.pack(side=tk.LEFT, padx=(0, 12))
                indicator_frame.pack_propagate(False)
                
                # Create a colored background that will show the status
                indicator_bg = tk.Frame(indicator_frame, bg=STATUS_COLORS.get("green", GREEN), width=20, height=20)
                indicator_bg.place(relx=0.5, rely=0.5, anchor="center")
                
                # Store references to both the background frame and the inner label for updates
                indicator_inner = tk.Label(indicator_bg, text="●", 
                                          font=(FONT_MONO, 16),
                                          bg=STATUS_COLORS.get("green", GREEN), fg=row_bg)
                indicator_inner.place(relx=0.5, rely=0.5, anchor="center")

                # name + url
                info = tk.Frame(row, bg=row_bg)
                info.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

                tk.Label(info, text=name[:25],
                         font=(FONT_MONO, 11, "bold"),
                         bg=row_bg, fg=TEXT, anchor="w").pack(anchor="w")

                tk.Label(info, text=(url[:40] + "…" if len(url) > 40 else url),
                         font=(FONT_MONO, 8),
                         bg=row_bg, fg=TEXT_DIM, anchor="w").pack(anchor="w", pady=(2, 0))

                # response time
                rt_lbl = tk.Label(row, text="—",
                                   font=(FONT_MONO, 9),
                                   bg=row_bg, fg=TEXT_DIM,
                                   width=8, anchor="e")
                rt_lbl.pack(side=tk.RIGHT, padx=(10, 0))

                # For backward compatibility with check_all, create a label that represents the status
                # We'll use a hidden label or repurpose one of our indicator components
                # For now, let's create a simple label for the registries
                status_label = tk.Label(row, text="●", font=(FONT_MONO, 16), bg=row_bg, fg=TEXT_DIM)
                
                self.full_dots[name]   = status_label
                self.full_labels[name] = rt_lbl

                # also register as mini targets so check_all can update both
                self.mini_dots[name]   = status_label
                # self.mini_labels[name] = rt_lbl  # Response time removed from mini mode
                # Store indicator components for full window updates
                self.full_indicators[name] = (indicator_bg, indicator_inner)

    # ── Mode control ───────────────────────────────────────────────────────────
    def set_mode(self, mode):
        self.mode = mode
        if mode == "mini":
            self.root.deiconify()
            if hasattr(self, "full"):
                self.full.withdraw()
        else:
            self.root.withdraw()
            if hasattr(self, "full"):
                self.full.deiconify()

    def toggle_mini(self):
        self.build_mini_window()
        self.set_mode("mini")

    def toggle_full(self):
        self.set_mode("full")

    # ── Polling & updates ──────────────────────────────────────────────────────
    def check_all(self):
        """Start background check if not already running."""
        if self.checking:
            return
        # Capture old statuses on main thread
        old_statuses = {ep.name: ep.status for ep in self.endpoints}
        self.checking = True

        def run_check():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                    new_endpoints = list(ex.map(check_endpoint, self.endpoints_list))
                # Schedule UI update on main thread
                self.root.after(0, lambda: self.update_ui(old_statuses, new_endpoints))
            finally:
                self.checking = False

        # Run checks in background thread
        threading.Thread(target=run_check, daemon=True).start()

    def update_ui(self, old_statuses, new_endpoints):
        """Update UI with check results (runs on main thread)."""
        self.endpoints = new_endpoints

        for ep in self.endpoints:
            color        = STATUS_COLORS.get(ep.status, TEXT_DIM)
            symbol       = STATUS_SYMBOLS.get(ep.status, "?")
            rt           = min(ep.response_time, 9999)
            rt_mini      = f"{rt:.0f}" if rt < 1000 else "999+"    # no "ms", fits tile
            rt_full      = f"{rt:.0f}ms" if rt < 1000 else "999+ms"

            # Special handling for Garfield SSH in mini mode
            display_name = ep.name
            if ep.name == "Garfield SSH":
                display_name = "SSH"

            if display_name in self.mini_dots:
                try:
                    self.mini_dots[display_name].configure(fg=color, text=symbol)
                except tk.TclError:
                    pass

            # Update full window status indicators
            if ep.name in self.full_indicators:
                try:
                    indicator_bg, indicator_inner = self.full_indicators[ep.name]
                    indicator_bg.configure(bg=color)
                    if color in [GREEN, YELLOW]:
                        indicator_inner.configure(bg=color, fg="#0a0f1c")
                    else:
                        indicator_inner.configure(bg=color, fg="#f9fafb")
                    indicator_inner.configure(text=symbol)
                except tk.TclError:
                    pass
            if ep.name in self.full_labels:
                try:
                    self.full_labels[ep.name].configure(text=rt_full, fg=color)
                except tk.TclError:
                    pass

            # notifications
            old = old_statuses.get(ep.name)
            now = datetime.now().timestamp()
            key = f"{ep.name}_{ep.status}"

            if old and old != ep.status:
                if ep.status == "red":
                    if now - self.last_notifications.get(key, 0) > self.notification_cooldown:
                        send_notification(f"{ep.name} DOWN", ep.message)
                        self.last_notifications[key] = now

        # update timestamp in full window
        if hasattr(self, "refresh_lbl"):
            ts = datetime.now().strftime("%H:%M:%S")
            try:
                self.refresh_lbl.configure(text=f"last check: {ts}")
            except tk.TclError:
                pass

    def refresh_loop(self):
        self.check_all()
        interval = self.config.get("refresh_interval", 1) * 1000
        self._refresh_timer = self.root.after(interval, self.refresh_loop)

    # ── Drag ───────────────────────────────────────────────────────────────────
    def drag_start(self, event):
        self.drag_data["start_x_root"] = event.x_root
        self.drag_data["start_y_root"] = event.y_root
        self.drag_data["win_x"] = self.root.winfo_x()
        self.drag_data["win_y"] = self.root.winfo_y()

    def drag_window(self, event):
        dx = event.x_root - self.drag_data["start_x_root"]
        dy = event.y_root - self.drag_data["start_y_root"]
        new_x = self.drag_data["win_x"] + dx
        new_y = self.drag_data["win_y"] + dy
        self.root.geometry(f"+{new_x}+{new_y}")

    # ── Other ──────────────────────────────────────────────────────────────────
    def toggle_aot(self):
        self.aot_var.set(not self.aot_var.get())
        self.root.attributes("-topmost", self.aot_var.get())

    def save_and_exit(self):
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w > 0 and h > 0:
            self.config["mini_mode_size"] = f"{w}x{h}"
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=4)
        # Cancel any pending after events
        try:
            self.root.after_cancel(self._refresh_timer)
        except:
            pass
        # Destroy full window if it exists
        if hasattr(self, 'full'):
            self.full.destroy()
        self.root.destroy()
        # Force exit to clean up console window
        import sys
        sys.exit(0)


if __name__ == "__main__":
    app = JonArbuckle()
