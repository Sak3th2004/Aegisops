"""Render a realistic dark-theme Grafana-style snapshot for the vision agent.

This is a REAL image the Diagnosis agent reads with Gemini vision — not a
placeholder. It shows request rate, error-rate %, and latency percentiles with
a clear regression starting ~12 min ago (aligned with the bad deploy), so the
multimodal step has genuine signal to detect and annotate.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless render
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

OUT = Path(__file__).resolve().parent / "grafana_checkout_spike.png"

# Grafana-ish palette
BG = "#0b0e14"
PANEL = "#12161f"
GRID = "#2a3242"
TEXT = "#c7d0e0"
GREEN = "#3fb950"
AMBER = "#d29922"
RED = "#f85149"
BLUE = "#58a6ff"


def _style_ax(ax, title: str) -> None:
    ax.set_facecolor(PANEL)
    ax.set_title(title, color=TEXT, fontsize=11, loc="left", fontweight="bold", pad=8)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)
    ax.tick_params(colors=TEXT, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


def generate() -> Path:
    now = datetime.now()
    # 60 min window, 1-min resolution. Regression begins at t = -12 min.
    times = [now - timedelta(minutes=60 - i) for i in range(61)]
    x = np.array([mdates.date2num(t) for t in times])
    n = len(times)
    spike_start = n - 12  # index where the deploy regression kicks in
    rng = np.random.default_rng(7)

    step = np.zeros(n)
    step[spike_start:] = 1.0
    ramp = np.clip((np.arange(n) - spike_start) / 4.0, 0, 1)

    req = 820 + rng.normal(0, 18, n)  # req/s stays roughly flat
    err = 0.4 + rng.normal(0, 0.15, n) + step * (ramp * 41.5)  # % → spikes to ~42
    err = np.clip(err, 0, 100)
    p50 = 45 + rng.normal(0, 4, n) + step * ramp * 120
    p95 = 130 + rng.normal(0, 10, n) + step * ramp * 520
    p99 = 210 + rng.normal(0, 16, n) + step * ramp * 900

    fig, axes = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)
    fig.patch.set_facecolor(BG)
    fig.suptitle(
        "checkout-svc  ·  Production  ·  us-central1",
        color=TEXT, fontsize=14, fontweight="bold", x=0.09, ha="left", y=0.965,
    )

    _style_ax(axes[0], "Request rate (req/s)")
    axes[0].plot(x, req, color=BLUE, linewidth=1.6)
    axes[0].fill_between(x, req, color=BLUE, alpha=0.10)
    axes[0].set_ylim(0, 1100)

    _style_ax(axes[1], "HTTP 5xx error rate (%)")
    axes[1].plot(x, err, color=RED, linewidth=1.8)
    axes[1].fill_between(x, err, color=RED, alpha=0.15)
    axes[1].axhline(5, color=AMBER, linestyle="--", linewidth=1, alpha=0.8)
    axes[1].annotate(
        "SLO 5%", xy=(x[2], 5), color=AMBER, fontsize=8, va="bottom"
    )
    axes[1].set_ylim(0, 55)

    _style_ax(axes[2], "Request latency (ms)")
    axes[2].plot(x, p50, color=GREEN, linewidth=1.4, label="p50")
    axes[2].plot(x, p95, color=AMBER, linewidth=1.4, label="p95")
    axes[2].plot(x, p99, color=RED, linewidth=1.6, label="p99")
    axes[2].legend(loc="upper left", facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
    axes[2].set_ylim(0, 1250)

    # Mark the deploy time on every panel.
    for ax in axes:
        ax.axvline(x[spike_start], color="#8957e5", linestyle=":", linewidth=1.4, alpha=0.9)
    axes[0].annotate(
        "deploy v2.4.1",
        xy=(x[spike_start], 1000), color="#b392f0", fontsize=8,
        xytext=(x[spike_start] + 0.004, 1010),
    )

    fig.autofmt_xdate()
    fig.subplots_adjust(left=0.09, right=0.97, top=0.92, bottom=0.07, hspace=0.35)
    fig.savefig(OUT, dpi=130, facecolor=BG)
    plt.close(fig)
    return OUT


if __name__ == "__main__":
    print(f"Grafana snapshot written to {generate()}")
