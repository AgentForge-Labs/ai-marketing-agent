# human_mouse.py — Wassim Sayah
# Biometric path generator. Loads a fitted profile and produces (x, y, delay_ms) waypoints.

import json
import math
import copy
import random
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise ImportError("Run: pip install numpy scipy")

_BUCKET_THRESHOLDS = [
    ("short",  0,   100),
    ("medium", 100, 400),
    ("long",   400, float("inf")),
]


def _select_bucket(distance):
    for name, lo, hi in _BUCKET_THRESHOLDS:
        if lo <= distance < hi:
            return name
    return "long"


def _bezier(P0, P1, P2, P3, t):
    u = 1 - t
    return (
        u**3 * P0[0] + 3*u**2*t * P1[0] + 3*u*t**2 * P2[0] + t**3 * P3[0],
        u**3 * P0[1] + 3*u**2*t * P1[1] + 3*u*t**2 * P2[1] + t**3 * P3[1],
    )


def _perpendicular(dx, dy):
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return 0.0, 1.0
    return -dy / length, dx / length


def _velocity_remap(n_points, peak_pos, peak_std):
    # warp bezier t-params so speed peaks at peak_pos (gaussian profile)
    # bunching points at start/end = natural accel/decel
    grid = np.linspace(0, 1, 500)
    speed = np.exp(-0.5 * ((grid - peak_pos) / max(peak_std, 0.05)) ** 2)
    speed = np.clip(speed, 0.05, None)

    cumulative = np.cumsum(speed)
    cumulative /= cumulative[-1]

    uniform = np.linspace(0, 1, n_points)
    return np.interp(uniform, cumulative, grid)


def _add_jitter(xs, ys, amplitude, frequency, duration):
    n = len(xs)
    if n < 2 or amplitude < 0.01:
        return xs, ys

    dx = xs[-1] - xs[0]
    dy = ys[-1] - ys[0]
    px, py = _perpendicular(dx, dy)

    noise = np.random.normal(0, amplitude, n)

    # low-pass filter to target frequency
    if frequency > 0 and duration > 0:
        samples_per_osc = max(2, int(n / (frequency * duration + 0.01)))
        kernel_size = max(1, min(samples_per_osc, n // 2))
        noise = np.convolve(noise, np.ones(kernel_size) / kernel_size, mode='same')

    # taper to zero at endpoints — no jitter on the actual click pixel
    t = np.linspace(0, duration, n)
    taper = np.minimum(t / max(0.05, duration * 0.15),
                       (duration - t) / max(0.05, duration * 0.15))
    taper = np.clip(taper, 0, 1)
    noise *= taper

    return xs + noise * px, ys + noise * py


class HumanMouse:

    def __init__(self, profile: dict, session_variance: float = 0.0):
        self._profile = profile
        self._variance = session_variance
        self._rng = np.random.default_rng()

    @classmethod
    def load_profile(cls, path: str | Path) -> "HumanMouse":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Profile not found: {path}\n"
                "Run train_mouse_model.py first."
            )
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        return cls(profile)

    def new_session(self, variance: float = 0.05) -> "HumanMouse":
        """Returns a clone with slightly varied parameters to avoid profiling."""
        profile = copy.deepcopy(self._profile)
        for bucket in profile.get("buckets", {}).values():
            rate = bucket.get("overshoot_rate", 0.2)
            bucket["overshoot_rate"] = float(np.clip(
                rate + np.random.normal(0, rate * variance), 0.0, 0.8
            ))
            vs = bucket.get("velocity_shape", {})
            if vs:
                vs["peak_mean"] = float(np.clip(
                    vs.get("peak_mean", 0.35) + np.random.normal(0, 0.05 * variance * 10),
                    0.1, 0.7
                ))
        return HumanMouse(profile, session_variance=variance)

    def path_to(
        self,
        start: tuple[int, int],
        end:   tuple[int, int],
    ) -> list[tuple[int, int, float]]:
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]),   float(end[1])
        distance = math.hypot(ex - sx, ey - sy)

        if distance < 2:
            return [(int(ex), int(ey), 0.0)]

        bucket     = self._profile.get("buckets", {}).get(_select_bucket(distance), {})
        global_p   = self._profile.get("global", {})
        params     = self._sample_params(bucket, global_p, distance)

        if random.random() < params["overshoot_rate"]:
            return self._generate_with_overshoot(sx, sy, ex, ey, distance, params)
        return self._generate_smooth(sx, sy, ex, ey, distance, params)

    def _sample_params(self, bucket, global_params, distance):
        rng = self._rng

        def sample(stats, default_mean, default_std, lo=0.0, hi=float("inf")):
            mean = stats.get("mean", default_mean) if stats else default_mean
            std  = stats.get("std",  default_std)  if stats else default_std
            return float(np.clip(rng.normal(mean, std * 0.5), lo, hi))

        vs        = bucket.get("velocity_shape", {})
        peak_mean = float(np.clip(vs.get("peak_mean", 0.35), 0.1, 0.7))
        peak_std  = float(np.clip(vs.get("peak_std",  0.10), 0.02, 0.3))

        jitter_amp  = sample(bucket.get("jitter_amplitude_px"), 0.8, 0.3, 0.0, 5.0)
        jitter_freq = sample(bucket.get("jitter_frequency_hz"), 8.0, 3.0, 1.0, 30.0)

        overshoot_rate  = bucket.get("overshoot_rate", 0.15)
        overshoot_ratio = sample(bucket.get("overshoot_ratio", {}), 0.06, 0.03, 0.01, 0.3)

        delay_stats = bucket.get("event_delay_ms", {})
        delay_mean  = delay_stats.get("mean", 13.5)
        delay_std   = delay_stats.get("std",  4.0)

        dur_stats  = bucket.get("duration_s", {})
        dist_stats = bucket.get("distance_px", {})

        fitted_dist  = dist_stats.get("mean", distance)
        fitted_dur   = dur_stats.get("mean", 0.4)
        fitted_speed = float(np.clip(
            fitted_dist / fitted_dur if fitted_dist > 1 and fitted_dur > 0 else 500.0,
            150.0, 1200.0
        ))

        dur_cv   = dur_stats.get("std", fitted_dur * 0.3) / max(fitted_dur, 0.01)
        base_dur = distance / fitted_speed
        duration = float(np.clip(
            rng.normal(base_dur, base_dur * float(np.clip(dur_cv, 0.1, 0.5)) * 0.5),
            0.08, 6.0
        ))

        return {
            "overshoot_rate":  overshoot_rate,
            "overshoot_ratio": overshoot_ratio,
            "peak_mean":       peak_mean,
            "peak_std":        peak_std,
            "jitter_amp":      jitter_amp,
            "jitter_freq":     jitter_freq,
            "delay_mean":      delay_mean,
            "delay_std":       delay_std,
            "duration":        duration,
            "curve_bias":      float(np.clip(rng.normal(0.15, 0.06), 0.0, 0.4)),
        }

    def _generate_smooth(self, sx, sy, ex, ey, distance, params):
        n_pts = min(max(8, int(params["duration"] / (params["delay_mean"] / 1000))), 400)
        xs, ys, delays = self._bezier_arc(sx, sy, ex, ey, distance, params, n_pts, ex, ey)
        return self._to_output(xs, ys, delays)

    def _generate_with_overshoot(self, sx, sy, ex, ey, distance, params):
        dx, dy = ex - sx, ey - sy
        overshoot_dist = distance * params["overshoot_ratio"]
        ox = ex + (dx / distance) * overshoot_dist
        oy = ey + (dy / distance) * overshoot_dist

        # phase 1: main arc → overshoot point
        dur1  = params["duration"] * 0.80
        n_pt1 = min(max(6, int(dur1 / (params["delay_mean"] / 1000))), 300)
        p1 = dict(params)
        p1["duration"]   = dur1
        p1["jitter_amp"] = params["jitter_amp"] * 0.8
        xs1, ys1, d1 = self._bezier_arc(sx, sy, ox, oy, distance, p1, n_pt1, ox, oy)

        # phase 2: short correction → real target
        dur2  = params["duration"] * 0.22
        n_pt2 = min(max(4, int(dur2 / (params["delay_mean"] / 1000))), 60)
        p2 = dict(params)
        p2["duration"]       = dur2
        p2["curve_bias"]     = params["curve_bias"] * 0.3
        p2["jitter_amp"]     = params["jitter_amp"] * 0.4
        p2["peak_mean"]      = 0.4
        p2["overshoot_rate"] = 0.0
        xs2, ys2, d2 = self._bezier_arc(ox, oy, ex, ey, overshoot_dist, p2, n_pt2, ex, ey)

        xs     = np.concatenate([xs1, xs2[1:]])
        ys     = np.concatenate([ys1, ys2[1:]])
        delays = np.concatenate([d1,  d2[1:]])
        return self._to_output(xs, ys, delays)

    def _bezier_arc(self, sx, sy, ex, ey, distance, params, n_pts, target_x, target_y):
        dx, dy   = ex - sx, ey - sy
        px, py   = _perpendicular(dx, dy)
        bias     = distance * params["curve_bias"]
        side     = random.choice([-1, 1])
        offset1  = side * bias * random.uniform(0.5, 1.0)
        offset2  = side * bias * random.uniform(0.4, 0.9)

        P0 = (sx, sy)
        P1 = (sx + dx * 0.30 + px * offset1, sy + dy * 0.30 + py * offset1)
        P2 = (ex - dx * 0.20 + px * offset2, ey - dy * 0.20 + py * offset2)
        P3 = (ex, ey)

        t_params = _velocity_remap(n_pts, params["peak_mean"], params["peak_std"])
        points   = [_bezier(P0, P1, P2, P3, t) for t in t_params]
        xs = np.array([p[0] for p in points])
        ys = np.array([p[1] for p in points])

        xs, ys = _add_jitter(xs, ys, params["jitter_amp"], params["jitter_freq"], params["duration"])

        # force exact landing on target pixel
        xs[-1] = float(target_x)
        ys[-1] = float(target_y)

        return xs, ys, self._sample_delays(n_pts, params)

    def _sample_delays(self, n_pts, params):
        mean   = params["delay_mean"]
        delays = self._rng.normal(mean, max(1.0, params["delay_std"]) * 0.6, n_pts)
        delays = np.clip(delays, 1.0, mean * 4)

        # rescale so total duration matches exactly — random drift corrected
        total = delays.sum()
        if total > 0:
            delays = delays * (params["duration"] * 1000.0 / total)
        return delays

    @staticmethod
    def _to_output(xs, ys, delays):
        return [
            (int(round(float(x))), int(round(float(y))), float(round(d, 2)))
            for x, y, d in zip(xs, ys, delays)
        ]
