# visualize.py — Wassim Sayah
# Sanity check: plots real recorded paths vs AI-generated paths side by side.
# Run after train_mouse_model.py. Output: profile/visualize_report.png

import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
except ImportError:
    print("ERROR: pip install matplotlib numpy")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_mouse.human_mouse import HumanMouse

ROOT_DIR     = Path(__file__).parent.parent
DATA_FILE    = ROOT_DIR / "data"    / "mouse_data.json"
PROFILE_FILE = ROOT_DIR / "profile" / "mouse_profile.json"
OUTPUT_FILE  = ROOT_DIR / "profile" / "visualize_report.png"

N_PATHS = 15

BG    = "#0a0b0f"
BG2   = "#10121a"
GRID  = "#1e2235"
REAL  = "#6b7280"
GEN_S = "#5b6ef5"
GEN_M = "#f59e0b"
GEN_L = "#22d3a0"
ACCENT = "#e8eaf6"

BUCKET_COLORS  = {"short": GEN_S, "medium": GEN_M, "long": GEN_L}
BUCKET_LABELS  = {"short": "Short (0-100px)", "medium": "Medium (100-400px)", "long": "Long (400px+)"}
BUCKET_RANGES  = {"short": (0, 100), "medium": (100, 400), "long": (400, 9999)}


def load_data():
    for f, hint in [(DATA_FILE, "record_mouse.py"), (PROFILE_FILE, "train_mouse_model.py")]:
        if not f.exists():
            print(f"[!] {f.name} not found. Run {hint} first.")
            sys.exit(1)
    with open(DATA_FILE,    encoding="utf-8") as f: data    = json.load(f)
    with open(PROFILE_FILE, encoding="utf-8") as f: profile = json.load(f)
    return data["segments"], profile


def bucket_segments(segments):
    out = {"short": [], "medium": [], "long": []}
    for seg in segments:
        d = seg.get("distance", 0)
        if   d < 100: out["short"].append(seg)
        elif d < 400: out["medium"].append(seg)
        else:         out["long"].append(seg)
    return out


def seg_speed_curve(seg):
    wp = seg["waypoints"]
    if len(wp) < 3:
        return None
    t0, t1 = wp[0]["t"], wp[-1]["t"]
    dur = t1 - t0
    if dur < 0.01:
        return None
    speeds, times = [], []
    for i in range(1, len(wp)):
        dt = wp[i]["t"] - wp[i-1]["t"]
        if dt <= 0:
            continue
        speeds.append(math.hypot(wp[i]["x"] - wp[i-1]["x"], wp[i]["y"] - wp[i-1]["y"]) / dt)
        times.append((wp[i]["t"] - t0) / dur)
    if not speeds:
        return None
    mx = max(speeds)
    return (times, [s / mx for s in speeds]) if mx > 1e-6 else None


def path_from_seg(seg):
    wp = seg["waypoints"]
    if len(wp) < 2:
        return None
    sx, sy = wp[0]["x"], wp[0]["y"]
    ex, ey = wp[-1]["x"], wp[-1]["y"]
    dist = math.hypot(ex - sx, ey - sy)
    if dist < 1:
        return None
    dx, dy = (ex - sx) / dist, (ey - sy) / dist
    px, py = -dy, dx
    xs = [(p["x"] - sx) * dx + (p["y"] - sy) * dy for p in wp]
    ys = [(p["x"] - sx) * px + (p["y"] - sy) * py for p in wp]
    return [v / dist for v in xs], [v / dist for v in ys]


def path_from_waypoints(waypoints):
    if len(waypoints) < 2:
        return None
    sx, sy = waypoints[0][0], waypoints[0][1]
    ex, ey = waypoints[-1][0], waypoints[-1][1]
    dist = math.hypot(ex - sx, ey - sy)
    if dist < 1:
        return None
    dx, dy = (ex - sx) / dist, (ey - sy) / dist
    px, py = -dy, dx
    xs, ys = [], []
    for x, y, _ in waypoints:
        rx, ry = x - sx, y - sy
        xs.append((rx * dx + ry * dy) / dist)
        ys.append((rx * px + ry * py) / dist)
    return xs, ys


def speed_from_waypoints(waypoints):
    if len(waypoints) < 4:
        return None
    total_t = sum(d for _, _, d in waypoints)
    total_d = sum(
        math.hypot(waypoints[i][0] - waypoints[i-1][0], waypoints[i][1] - waypoints[i-1][1])
        for i in range(1, len(waypoints))
    )
    if total_t < 1 or total_d < 1:
        return None
    ct, cd = [0.0], [0.0]
    for i in range(1, len(waypoints)):
        x0, y0, _ = waypoints[i-1]
        x1, y1, d = waypoints[i]
        ct.append(ct[-1] + d)
        cd.append(cd[-1] + math.hypot(x1 - x0, y1 - y0))
    sample_ts = np.linspace(0, total_t, 40)
    speeds    = np.gradient(np.interp(sample_ts, ct, cd), sample_ts)
    mx = speeds.max()
    if mx < 1e-6:
        return None
    return (sample_ts / total_t).tolist(), (speeds / mx).tolist()


def make_plot(segments, mouse):
    bucketed = bucket_segments(segments)
    session  = mouse.new_session(variance=0.05)

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(18, 14), facecolor=BG)
    fig.suptitle("Mouse Biometric Profile — Real vs Generated",
                 fontsize=16, fontweight="bold", color=ACCENT, y=0.98)
    gs = gridspec.GridSpec(3, 3, figure=fig,
                           hspace=0.42, wspace=0.32,
                           left=0.06, right=0.97, top=0.93, bottom=0.05)

    for row, bucket in enumerate(["short", "medium", "long"]):
        real_segs   = bucketed[bucket]
        color       = BUCKET_COLORS[bucket]
        label       = BUCKET_LABELS[bucket]
        lo, hi      = BUCKET_RANGES[bucket]
        sample_dist = (lo + min(hi, lo + 200)) / 2

        def styled_ax(col, title):
            ax = fig.add_subplot(gs[row, col])
            ax.set_facecolor(BG2)
            ax.tick_params(colors=GRID, labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID)
            ax.set_title(f"{label}\n{title}", color=ACCENT, fontsize=9, pad=6)
            return ax

        # --- col 0: path shapes ---
        ax0 = styled_ax(0, "Path Shapes")
        ax0.set_xlabel("Along movement", color=GRID, fontsize=7)
        ax0.set_ylabel("Perpendicular (px)", color=GRID, fontsize=7)
        n_real = 0
        for seg in np.random.choice(real_segs, min(N_PATHS, len(real_segs)), replace=False):
            r = path_from_seg(seg)
            if r:
                ax0.plot(r[0], r[1], color=REAL, alpha=0.35, linewidth=0.8)
                n_real += 1
        n_gen = 0
        for _ in range(N_PATHS):
            r = path_from_waypoints(session.path_to((100, 500), (int(100 + sample_dist), 500)))
            if r:
                ax0.plot(r[0], r[1], color=color, alpha=0.55, linewidth=0.9)
                n_gen += 1
        ax0.axhline(0, color=GRID, linewidth=0.5, linestyle="--")
        ax0.axvline(1, color=GRID, linewidth=0.5, linestyle="--")
        ax0.legend(handles=[
            Line2D([0], [0], color=REAL,  linewidth=1.5, label=f"Real ({n_real})"),
            Line2D([0], [0], color=color, linewidth=1.5, label=f"Generated ({n_gen})"),
        ], fontsize=7, facecolor=BG, edgecolor=GRID, labelcolor=ACCENT)

        # --- col 1: speed profiles ---
        ax1 = styled_ax(1, "Speed Profiles (normalized)")
        ax1.set_xlabel("Time (0=start, 1=end)", color=GRID, fontsize=7)
        ax1.set_ylabel("Speed (normalized)", color=GRID, fontsize=7)
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1.4)
        real_curves, gen_curves = [], []
        for seg in np.random.choice(real_segs, min(N_PATHS, len(real_segs)), replace=False):
            r = seg_speed_curve(seg)
            if r:
                ax1.plot(r[0], r[1], color=REAL, alpha=0.3, linewidth=0.8)
                real_curves.append(r)
        for _ in range(N_PATHS):
            r = speed_from_waypoints(session.path_to((100, 500), (int(100 + sample_dist), 500)))
            if r:
                ax1.plot(r[0], r[1], color=color, alpha=0.4, linewidth=0.9)
                gen_curves.append(r)
        interp_t = np.linspace(0, 1, 100)
        if real_curves:
            ax1.plot(interp_t, np.mean([np.interp(interp_t, t, s) for t, s in real_curves], axis=0),
                     color=REAL,  linewidth=2.0, label="Real mean",      zorder=5)
        if gen_curves:
            ax1.plot(interp_t, np.mean([np.interp(interp_t, t, s) for t, s in gen_curves], axis=0),
                     color=color, linewidth=2.0, label="Generated mean", zorder=5)
        ax1.legend(fontsize=7, facecolor=BG, edgecolor=GRID, labelcolor=ACCENT)

        # --- col 2: duration distribution ---
        ax2 = styled_ax(2, "Movement Duration (ms)")
        ax2.set_xlabel("Duration (ms)", color=GRID, fontsize=7)
        ax2.set_ylabel("Count", color=GRID, fontsize=7)
        real_durs = [seg["duration"] * 1000 for seg in real_segs if seg.get("duration", 0) > 0]
        gen_durs  = [
            sum(d for _, _, d in session.path_to((100, 500), (int(100 + sample_dist), 500)))
            for _ in range(min(80, len(real_segs) * 2))
        ]
        if real_durs and gen_durs:
            all_v = real_durs + gen_durs
            bins  = np.linspace(min(all_v) * 0.8, max(all_v) * 1.1, 25)
            ax2.hist(real_durs, bins=bins, color=REAL,  alpha=0.55, label="Real",      density=True)
            ax2.hist(gen_durs,  bins=bins, color=color, alpha=0.55, label="Generated", density=True)
            ax2.legend(fontsize=7, facecolor=BG, edgecolor=GRID, labelcolor=ACCENT)

    fig.text(0.5, 0.01,
             f"Profile: {PROFILE_FILE.name}  |  Real segments: {len(segments)}  |  "
             f"short={len(bucketed['short'])}  medium={len(bucketed['medium'])}  long={len(bucketed['long'])}",
             ha="center", fontsize=8, color=GRID)

    plt.savefig(OUTPUT_FILE, dpi=130, bbox_inches="tight", facecolor=BG)
    print(f"[OK] Report saved -> {OUTPUT_FILE}")
    plt.show()


if __name__ == "__main__":
    print("[*] Mouse Profile Visualizer")
    segments, profile = load_data()
    print(f"[*] {len(segments)} real segments loaded")
    make_plot(segments, HumanMouse.load_profile(PROFILE_FILE))
