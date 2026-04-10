#!/usr/bin/env python3

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict


# -----------------------------
# Mock interval lookup table
# key: (experiment_id, protocol) -> period (seconds)
# -----------------------------
INTERVAL_TABLE = {
    (1, "meshtastic"): 1,
    (1, "meshcore"): 2,
    (1, "lrf"): 5,
    (2, "meshtastic"): 2,
    (2, "meshcore"): 5,
    (2, "lrf"): 1,
    (5, "meshtastic"): 5,
    (5, "meshcore"): 1,
    (5, "lrf"): 2,
    (27, "meshtastic"): 1,
}

CHARTS_DIR = "charts"


def parse_filename(filename):
    """
    Expected format: <experiment_id>_<protocol>.csv
    """
    base = os.path.basename(filename)
    if not base.endswith(".csv"):
        return None

    try:
        name = base[:-4]
        exp_id_str, protocol = name.split("_")
        exp_id = int(exp_id_str)
        return exp_id, protocol
    except Exception:
        return None


def find_matching_files(root, protocols):
    """
    Recursively find CSV files matching given protocols
    """
    matches = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            parsed = parse_filename(f)
            if not parsed:
                continue

            exp_id, protocol = parsed
            if protocol in protocols:
                matches.append(os.path.join(dirpath, f))

    return matches


def compute_latency(df):
    """
    Compute arrival_time - generation_time
    """
    return df["arrival_time"] - df["generation_time"]


def plot_log(values, labels, period):
    plt.figure()
    plt.boxplot(values)
    plt.yscale("log")
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)
    plt.title(f"Latency distribution (period = {period}s)")
    plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (arrival - generation)")
    plt.tight_layout()

    output_file = os.path.join(CHARTS_DIR, f"boxplot_period_{period}_log.png")
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()


def plot_ylim(values, labels, period):
    plt.figure()
    plt.boxplot(values)
    plt.ylim(0, 1)
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)
    plt.title(f"Latency distribution (period = {period}s)")
    plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (arrival - generation)")
    plt.tight_layout()

    output_file = os.path.join(CHARTS_DIR, f"boxplot_period_{period}_ylim_0-1.png")
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()

    plt.figure()
    plt.boxplot(values)
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)
    plt.title(f"Latency distribution (period = {period}s)")
    plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (arrival - generation)")
    plt.tight_layout()

    output_file = os.path.join(CHARTS_DIR, f"boxplot_period_{period}_ylim_none.png")
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()


def plot_broken(values, labels, period):
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)

    # Top plot (outliers)
    ax1.boxplot(values)
    ax1.set_ylim(13, 20)

    # Bottom plot (main cluster)
    ax2.boxplot(values)
    ax2.set_ylim(0, 1)

    # Hide spines between plots
    ax1.spines['bottom'].set_visible(False)
    ax2.spines['top'].set_visible(False)

    ax1.tick_params(labeltop=False)
    ax2.xaxis.tick_bottom()

    # X labels
    ax2.set_xticks(range(1, len(labels) + 1))
    ax2.set_xticklabels(labels, rotation=45)

    # ---- Add diagonal break marks ----
    d = 0.01  # size of diagonal lines in axes coords

    kwargs = dict(transform=ax1.transAxes, color='k', clip_on=False)
    ax1.plot((-d, +d), (-d, +d), **kwargs)        # left diagonal
    ax1.plot((1 - d, 1 + d), (-d, +d), **kwargs)  # right diagonal

    kwargs.update(transform=ax2.transAxes)
    ax2.plot((-d, +d), (1 - d, 1 + d), **kwargs)        # left diagonal
    ax2.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)  # right diagonal
    # ---------------------------------

    plt.tight_layout()

    output_file = os.path.join(CHARTS_DIR, f"boxplot_period_{period}_broken.png")
    fig.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate boxplots from CSV datasets")
    parser.add_argument("root", help="Root folder to search")
    parser.add_argument("protocols", nargs='+', help="Protocols to include")

    args = parser.parse_args()

    root = args.root
    protocols = set(args.protocols)

    os.makedirs(CHARTS_DIR, exist_ok=True)

    files = find_matching_files(root, protocols)

    if not files:
        print("No matching files found.")
        return

    # Structure:
    # data[period][(protocol, size)] = list of latencies
    data = defaultdict(lambda: defaultdict(list))

    for filepath in files:
        parsed = parse_filename(filepath)
        if not parsed:
            continue

        exp_id, protocol = parsed

        key = (exp_id, protocol)
        if key not in INTERVAL_TABLE:
            print(f"Skipping {filepath}: no interval entry")
            continue

        period = INTERVAL_TABLE[key]

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"Failed to read {filepath}: {e}")
            continue

        if df.empty:
            continue

        # Assume size is constant per file
        message_size = df["size"].iloc[0]

        latencies = compute_latency(df)

        group_key = (protocol, message_size)
        data[period][group_key].extend(latencies.tolist())

    # Generate one plot per period
    for period, groups in data.items():
        if not groups:
            continue

        labels = []
        values = []

        for (protocol, size), lat_list in sorted(groups.items()):
            labels.append(f"{protocol}:{size}")
            values.append(lat_list)

        for mode in ["log", "ylim", "broken"]:
            if mode == "log":
                plot_log(values, labels, period)
            elif mode == "ylim":
                plot_ylim(values, labels, period)
            elif mode == "broken":
                plot_broken(values, labels, period)
            else:
                print("Wrong mode")
                exit(1)


if __name__ == "__main__":
    main()