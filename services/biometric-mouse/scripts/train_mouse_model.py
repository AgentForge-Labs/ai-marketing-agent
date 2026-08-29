# train_mouse_model.py — Wassim Sayah
# Reads mouse_data.json and fits a biometric model per distance bucket.
# Output: profile/mouse_profile.json

import json
import math
import sys
import os
from pathlib import Path

try:
    import numpy as np
    from scipy import stats
    from scipy.fft import rfft, rfftfreq
    from scipy.ndimage import uniform_filter1d
except ImportError:
    print("ERROR: pip install numpy scipy")
    sys.exit(1)

ROOT_DIR     = Path(__file__).parent.parent
DATA_FILE    = ROOT_DIR / "data" / "mouse_data.json"
PROFILE_FILE = ROOT_DIR / "profile" / "mouse_profile.json"

BUCKET_DEFS = [
    {"name": "short",  "min": 0,   "max": 100},
    {"name": "medium", "min": 100, "max": 400},
    {"name": "long",   "min": 400, "max": float("inf")},
]


def load_data():
    if not DATA_FILE.exists():
        print(f"[!] Data file not found: {DATA_FILE}")
        print("    Run record_mouse.py first.")
        sys.exit(1)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    segs   = data.get("segments", [])
    clicks = data.get("click_durations", [])
    print(f"[*] Loaded {len(segs)} segments, {len(clicks)} click samples")
    return segs, clicks


def extract_velocity_profile(waypoints):
    if len(waypoints) < 3:
        return None
    t0, t1 = waypoints[0]["t"], waypoints[-1]["t"]
    duration = t1 - t0
    if duration < 0.01:
        return None
    speeds, times = [], []
    for i in range(1, len(waypoints)):
        p0, p1 = waypoints[i - 1], waypoints[i]
        dt = p1["t"] - p0["t"]
        if dt <= 0:
            continue
        speed = math.hypot(p1["x"] - p0["x"], p1["y"] - p0["y"]) / dt
        speeds.append(speed)
        times.append((p1["t"] - t0) / duration)
    return (times, speeds) if speeds else None


def fit_velocity_shape(all_speed_curves):
    peak_positions = []
    for times, speeds in all_speed_curves:
        idx = int(np.argmax(speeds))
        if idx < len(times):
            peak_positions.append(times[idx])
    if not peak_positions:
        return {"peak_mean": 0.3, "peak_std": 0.1}
    arr = np.array(peak_positions)
    return {
        "peak_mean": float(np.mean(arr)),
        "peak_std":  float(np.std(arr)),
        "raw":       arr.tolist()[:50],
    }


def extract_jitter(waypoints, distance):
    if len(waypoints) < 6 or distance < 20:
        return None, None

    xs = np.array([p["x"] for p in waypoints], dtype=float)
    ys = np.array([p["y"] for p in waypoints], dtype=float)
    ts = np.array([p["t"] for p in waypoints], dtype=float)

    dx, dy = xs[-1] - xs[0], ys[-1] - ys[0]
    seg_len = math.hypot(dx, dy)
    if seg_len < 1:
        return None, None

    # unit perpendicular vector
    ux, uy = dx / seg_len, dy / seg_len
    px, py = -uy, ux

    perp = (xs - xs[0]) * px + (ys - ys[0]) * py

    # smooth out the curve to isolate noise
    smooth   = uniform_filter1d(perp, size=5) if len(perp) > 5 else perp
    residual = perp - smooth
    amplitude = float(np.std(residual))

    duration = ts[-1] - ts[0]
    frequency = 0.0
    if duration > 0.05 and len(residual) >= 4:
        freqs   = rfftfreq(len(residual), d=duration / len(residual))
        fft_mag = np.abs(rfft(residual))
        if len(fft_mag) > 1:
            idx = int(np.argmax(fft_mag[1:]) + 1)
            frequency = float(freqs[idx]) if idx < len(freqs) else 0.0

    return amplitude, frequency


def detect_overshoot(waypoints, distance):
    if len(waypoints) < 4 or distance < 10:
        return False, 0.0
    sx, sy = waypoints[0]["x"], waypoints[0]["y"]
    ex, ey = waypoints[-1]["x"], waypoints[-1]["y"]
    dx, dy = ex - sx, ey - sy
    seg_len = math.hypot(dx, dy)
    if seg_len < 1:
        return False, 0.0

    projections = [
        ((p["x"] - sx) * dx + (p["y"] - sy) * dy) / seg_len
        for p in waypoints
    ]
    overshoot_px = max(projections) - seg_len
    if overshoot_px > 2.0:
        return True, float(overshoot_px / seg_len)
    return False, 0.0


def inter_event_delays(waypoints):
    delays = []
    for i in range(1, len(waypoints)):
        dt = (waypoints[i]["t"] - waypoints[i - 1]["t"]) * 1000
        if 1 < dt < 500:
            delays.append(dt)
    return delays


def fit_bucket(segments):
    if len(segments) < 5:
        return None

    overshoot_flags, overshoot_ratios = [], []
    jitter_amps, jitter_freqs         = [], []
    speed_curves, all_delays          = [], []
    durations, distances              = [], []

    for seg in segments:
        wp, dist, dur = seg["waypoints"], seg["distance"], seg["duration"]
        if len(wp) < 3 or dur < 0.01:
            continue

        distances.append(dist)
        durations.append(dur)

        did_os, os_ratio = detect_overshoot(wp, dist)
        overshoot_flags.append(did_os)
        if did_os:
            overshoot_ratios.append(os_ratio)

        amp, freq = extract_jitter(wp, dist)
        if amp is not None:
            jitter_amps.append(amp)
        if freq is not None and freq > 0:
            jitter_freqs.append(freq)

        result = extract_velocity_profile(wp)
        if result:
            speed_curves.append(result)

        all_delays.extend(inter_event_delays(wp))

    def safe_stats(arr):
        arr = [x for x in arr if not math.isnan(x) and not math.isinf(x)]
        if not arr:
            return {"mean": 0.0, "std": 0.01, "p25": 0.0, "p75": 0.0}
        a = np.array(arr)
        return {
            "mean": float(np.mean(a)),
            "std":  float(np.std(a)),
            "p25":  float(np.percentile(a, 25)),
            "p75":  float(np.percentile(a, 75)),
        }

    return {
        "sample_count":        len(segments),
        "overshoot_rate":      round(float(np.mean(overshoot_flags)) if overshoot_flags else 0.0, 4),
        "overshoot_ratio":     safe_stats(overshoot_ratios) if overshoot_ratios else
                               {"mean": 0.05, "std": 0.02, "p25": 0.03, "p75": 0.07},
        "velocity_shape":      fit_velocity_shape(speed_curves),
        "jitter_amplitude_px": safe_stats(jitter_amps),
        "jitter_frequency_hz": safe_stats(jitter_freqs),
        "event_delay_ms":      safe_stats(all_delays),
        "duration_s":          safe_stats(durations),
        "distance_px":         safe_stats(distances),
    }


def main():
    print("[*] Mouse Biometric Model Fitter")
    segments, click_durations = load_data()

    bucketed = {b["name"]: [] for b in BUCKET_DEFS}
    for seg in segments:
        for b in BUCKET_DEFS:
            if b["min"] <= seg.get("distance", 0) < b["max"]:
                bucketed[b["name"]].append(seg)
                break

    for name, segs in bucketed.items():
        print(f"  [{name}] {len(segs)} segments")

    fitted_buckets = {}
    for name, segs in bucketed.items():
        result = fit_bucket(segs)
        if result:
            fitted_buckets[name] = result
            print(f"  [{name}] overshoot={result['overshoot_rate']:.1%} "
                  f"jitter={result['jitter_amplitude_px']['mean']:.2f}px "
                  f"vel_peak={result['velocity_shape']['peak_mean']:.2f}")
        else:
            print(f"  [{name}] not enough data — skipped")

    # global inter-event delay
    all_delays = [
        d for seg in segments
        for d in inter_event_delays(seg["waypoints"])
        if not math.isnan(d)
    ]
    if all_delays:
        arr = np.array(all_delays)
        global_delay = {
            "mean_ms": float(np.mean(arr)),
            "std_ms":  float(np.std(arr)),
            "p10_ms":  float(np.percentile(arr, 10)),
            "p90_ms":  float(np.percentile(arr, 90)),
        }
    else:
        global_delay = {"mean_ms": 16.0, "std_ms": 4.0, "p10_ms": 8.0, "p90_ms": 32.0}

    # hardware click hold timing
    valid_clicks = [d for d in click_durations if not math.isnan(d) and 10 < d < 800]
    if valid_clicks:
        c = np.array(valid_clicks)
        hardware_click = {
            "mean_ms": float(np.mean(c)),
            "std_ms":  float(np.std(c)),
            "p25_ms":  float(np.percentile(c, 25)),
            "p75_ms":  float(np.percentile(c, 75)),
            "count":   len(valid_clicks),
        }
        print(f"[*] Click hold: {hardware_click['mean_ms']:.1f}ms avg "
              f"(std={hardware_click['std_ms']:.1f}ms, n={hardware_click['count']})")
    else:
        hardware_click = {"mean_ms": 85.0, "std_ms": 20.0, "p25_ms": 65.0, "p75_ms": 105.0, "count": 0}
        print("[!] No click data — using fallback defaults")

    profile = {
        "version":         "1.0",
        "recorded_at":     __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "source_segments": len(segments),
        "global":          {"inter_event_delay_ms": global_delay},
        "hardware_click":  hardware_click,
        "buckets":         fitted_buckets,
    }

    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    print(f"[OK] Profile saved -> {PROFILE_FILE}")
    print(f"     Buckets: {list(fitted_buckets.keys())}")
    print(f"     Event delay: {global_delay['mean_ms']:.1f}ms avg")


if __name__ == "__main__":
    main()
