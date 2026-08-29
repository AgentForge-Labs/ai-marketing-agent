# record_mouse.py — Wassim Sayah
# Captures raw OS-level mouse events alongside the Mouse Dojo game.
# Outputs: data/mouse_data.json

import sys
import io

if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

import json
import time
import os
import threading
from pathlib import Path

ROOT_DIR       = Path(__file__).parent.parent
OUTPUT_FILE    = ROOT_DIR / "data" / "mouse_data.json"
MIN_MOVE_PX    = 3      # drop sub-pixel jitter
REST_TIMEOUT   = 0.15   # seconds of stillness = segment end
AUTOSAVE_EVERY = 60

BUCKETS = [
    {"label": "0-100px",   "min": 0,   "max": 100,          "count": 0, "target": 80},
    {"label": "100-300px", "min": 100, "max": 300,          "count": 0, "target": 80},
    {"label": "300-600px", "min": 300, "max": 600,          "count": 0, "target": 60},
    {"label": "600px+",    "min": 600, "max": float('inf'), "count": 0, "target": 40},
]

events          = []
segments        = []
current_seg     = []
last_event_t    = None
last_x          = None
last_y          = None
last_save_t     = None
click_durations = []
_click_down_t   = None
lock            = threading.Lock()
stop_event      = threading.Event()


def flush_segment():
    global current_seg
    if len(current_seg) < 3:
        current_seg = []
        return
    pts = current_seg
    sx, sy = pts[0]["x"], pts[0]["y"]
    ex, ey = pts[-1]["x"], pts[-1]["y"]
    dist = ((ex - sx)**2 + (ey - sy)**2) ** 0.5
    dur  = pts[-1]["t"] - pts[0]["t"]
    if dist < MIN_MOVE_PX or dur < 0.01:
        current_seg = []
        return
    segments.append({
        "start":     {"x": sx, "y": sy},
        "end":       {"x": ex, "y": ey},
        "distance":  round(dist, 2),
        "duration":  round(dur, 4),
        "waypoints": pts,
    })
    for b in BUCKETS:
        if b["min"] <= dist < b["max"]:
            b["count"] += 1
            break
    current_seg = []


def coverage_score():
    filled = sum(min(b["count"] / b["target"], 1.0) for b in BUCKETS)
    return round((filled / len(BUCKETS)) * 100)


def segment_watcher():
    global last_event_t
    while not stop_event.is_set():
        time.sleep(0.05)
        with lock:
            if last_event_t and (time.time() - last_event_t) > REST_TIMEOUT:
                if current_seg:
                    flush_segment()
                    last_event_t = None


def on_move(x, y):
    global last_x, last_y, last_event_t
    now = time.time()
    with lock:
        if last_x is not None:
            if ((x - last_x)**2 + (y - last_y)**2) ** 0.5 < MIN_MOVE_PX:
                return
        ev = {"x": x, "y": y, "t": now}
        events.append(ev)
        current_seg.append(ev)
        last_x, last_y = x, y
        last_event_t = now


def on_click(x, y, button, pressed):
    global _click_down_t
    now = time.time()
    with lock:
        if pressed:
            _click_down_t = now
        else:
            if _click_down_t is not None:
                ms = (now - _click_down_t) * 1000
                if 10 < ms < 800:
                    click_durations.append(round(ms, 2))
                _click_down_t = None


def save_data(silent=False):
    global last_save_t
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        if current_seg:
            flush_segment()
    data = {
        "recorded_at":     time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_events":    len(events),
        "total_segments":  len(segments),
        "coverage_score":  coverage_score(),
        "buckets":         BUCKETS,
        "segments":        segments,
        "click_durations": click_durations,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    last_save_t = time.time()
    if not silent:
        print(f"\n[*] Saved {len(segments)} segments, {len(click_durations)} clicks ({len(events):,} events)")
        print(f"     -> {OUTPUT_FILE}")
        print(f"     Coverage: {coverage_score()}%")


def print_stats():
    os.system('cls' if os.name == 'nt' else 'clear')
    pct  = coverage_score()
    bar  = "#" * int(30 * pct / 100) + "-" * (30 - int(30 * pct / 100))

    print("+----------------------------------------------+")
    print("|           Mouse Dojo  -  W. Sayah            |")
    print("+----------------------------------------------+")
    print(f"|  Raw events : {len(events):>10,}                    |")
    print(f"|  Segments   : {len(segments):>10,}                    |")
    print(f"|  Coverage   : [{bar}] {pct:>3}%  |")
    print("+----------------------------------------------+")
    for b in BUCKETS:
        n, t  = b["count"], b["target"]
        bfill = "#" * min(20, int(20 * n / t)) + "-" * max(0, 20 - int(20 * n / t))
        ok    = "OK" if n >= t else "  "
        print(f"|  {b['label']:<12} [{bfill}] {n:>4}/{t} {ok}  |")
    print("+----------------------------------------------+")
    if pct >= 100:
        print("|  [DONE] All buckets full  -  safe to stop  |")
    else:
        remaining = sum(max(0, b["target"] - b["count"]) for b in BUCKETS)
        print(f"|  [....] Need ~{remaining:<4} more segments             |")
    print("+----------------------------------------------+")
    avg_click = f"{sum(click_durations)/len(click_durations):.1f}ms" if click_durations else "---"
    print(f"|  Clicks recorded : {len(click_durations):>4}  avg={avg_click:<10}       |")
    print("+----------------------------------------------+")
    if last_save_t:
        print(f"|  [AUTO] Last save: {int(time.time()-last_save_t):>3}s ago                   |")
    else:
        print("|  [AUTO] First auto-save in 60s               |")
    print("|  Press ESC to stop and save                  |")
    print("+----------------------------------------------+")


def display_loop():
    last_autosave = time.time()
    while not stop_event.is_set():
        print_stats()
        if time.time() - last_autosave >= AUTOSAVE_EVERY:
            save_data(silent=True)
            last_autosave = time.time()
        time.sleep(2)


if __name__ == "__main__":
    try:
        from pynput import mouse, keyboard
    except ImportError:
        print("ERROR: pip install pynput")
        sys.exit(1)

    print("[*] Recorder started. Open http://localhost:8765 and play.")
    print("    Press ESC to stop.\n")

    def on_key_press(key):
        if key == keyboard.Key.esc:
            stop_event.set()
            return False

    threading.Thread(target=segment_watcher, daemon=True).start()
    threading.Thread(target=display_loop,    daemon=True).start()

    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
    mouse_listener.start()

    kb_listener = keyboard.Listener(on_press=on_key_press)
    kb_listener.start()

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        pass

    mouse_listener.stop()
    kb_listener.stop()

    print("\n[*] Stopping...")
    save_data(silent=False)
    sys.exit(0)
