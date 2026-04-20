#!/usr/bin/env python3

import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict


# -----------------------------
# Mock interval lookup table
# key: (experiment_id) -> (period (in seconds), number of receivers)
# -----------------------------
CHARTS_DIR = "charts"
CONFIGURATION_TABLE = {}


def parse_md_config(path):
    global CONFIGURATION_TABLE

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            # Skip non-table lines
            if not line.startswith("|"):
                continue
            if "---" in line:
                continue

            # Split columns
            parts = [p.strip() for p in line.strip("|").split("|")]

            # Skip header row
            if parts[0] == "Experiment":
                continue

            # Extract fields
            try:
                exp_id = int(parts[0])
                receivers = int(parts[1])
                period = float(parts[2])
            except (ValueError, IndexError):
                sys.exit(f"Error parsing config line: {line}")

            # Only consider periods of interest
            if period in (1, 2, 5):
                CONFIGURATION_TABLE[exp_id] = (period, receivers)


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


def find_matching_files(matches, root, protocols):
    """
    Recursively find CSV files matching given protocols
    """
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            parsed = parse_filename(f)
            if not parsed:
                continue

            exp_id, protocol = parsed
            if protocol in protocols:
                print(f"Added {f} from {dirpath}")
                matches.append(os.path.join(dirpath, f))

    return matches


def compute_latency(df):
    """
    Compute arrival_time - generation_time
    """
    return df["arrival_time"] - df["generation_time"]


def plot_log(values, labels, period, receivers, dir):
    plt.figure()
    plt.boxplot(values)
    plt.yscale("log")
    #plt.title(f"Latency distribution (period = {period}s, receivers = {receivers})")
    plt.xticks(range(1, len(labels) + 1), labels, rotation=55, fontsize=20)
    plt.yticks(fontsize=20)
    #plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (s)", fontsize=18)
    plt.tight_layout()

    output_file = os.path.join(
        dir, f"boxplot_period_{period}_receivers_{receivers}_log.png"
    )
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()


def plot_ylim(values, labels, period, receivers, dir):
    plt.figure()
    plt.boxplot(values)
    plt.ylim(0, 1)
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)
    plt.title(f"Latency distribution (period = {period}s, receivers = {receivers})")
    plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (s)")
    plt.tight_layout()

    output_file = os.path.join(dir, f"boxplot_period_{period}_receivers_{receivers}_ylim_0-1.png")
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()

    plt.figure()
    plt.boxplot(values)
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)
    plt.title(f"Latency distribution (period = {period}s, receivers = {receivers})")
    plt.xlabel("Protocol:Message Size")
    plt.ylabel("Latency (s)")
    plt.tight_layout()

    output_file = os.path.join(dir, f"boxplot_period_{period}_receivers_{receivers}_ylim_none.png")
    plt.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close()


def plot_broken(values, labels, period, receivers, dir):
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

    output_file = os.path.join(dir, f"boxplot_period_{period}_receivers_{receivers}_broken.png")
    fig.savefig(output_file)
    print(f"Saved {output_file}")

    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate boxplots from CSV datasets")
    parser.add_argument("root", help="Root folder to search")
    parser.add_argument("config", help="Configuration file path (Markdown table)")
    parser.add_argument("protocols", nargs='+', help="Protocols to include")

    args = parser.parse_args()

    root = args.root
    parse_md_config(args.config)
    protocols = set(args.protocols)

    os.makedirs(CHARTS_DIR, exist_ok=True)

    files = []
    find_matching_files(files, root, protocols)

    if not files:
        print("No matching files found.")
        return

    # Structure:
    # data[(period, receivers)][(protocol, size)] = list of latencies
    data = defaultdict(lambda: defaultdict(list))
    # losses[(period, receivers)][(protocol, size)] = count of incomplete msg_ids
    losses = defaultdict(lambda: defaultdict(int))

    for filepath in files:
        parsed = parse_filename(filepath)
        if not parsed:
            continue

        exp_id, protocol = parsed

        if exp_id not in CONFIGURATION_TABLE:
            print(f"Skipping {filepath}: no configuration entry")
            continue

        period, receivers = CONFIGURATION_TABLE[exp_id]

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"Failed to read {filepath}: {e}")
            continue

        if df.empty:
            continue

        print(f"Processing {filepath}")
        # Assume size is constant per file
        message_size = df["size"].iloc[0]
        if message_size == 24:
            message_size = 20
        if message_size == 160:
            message_size = 200
        # Only consider msg_id in [1, 100]
        filtered_df = df[(df["msg_id"] >= 1) & (df["msg_id"] <= 100)]
        if filtered_df.empty:
            continue

        # The number of expected messages is 100 times the number of receivers in the experiment (N)
        expected = 100 * receivers
        actual = len(filtered_df)
        num_losses = max(0, expected - actual)
        latencies = compute_latency(filtered_df)

        scenario_key = (period, receivers)
        group_key = (message_size, protocol)
        losses[scenario_key][group_key] += int(num_losses)
        data[scenario_key][group_key].extend(latencies.tolist())

    # Generate one plot per period
    for (period, receivers), groups in data.items():
        if not groups:
            continue

        labels = []
        values = []
        for (size, protocol), lat_list in sorted(groups.items()):
            size_label = "S" if size <= 50 else "M" if size <= 150 else "L"
            proto_label = "mt" if protocol == "meshtastic" else "mc" if protocol == "meshcore" else protocol
            labels.append(f"{proto_label}:{size_label}")
            values.append(lat_list)

        for mode in ["log", "ylim", "broken"]:
            if mode == "log":
                dir = os.path.join(CHARTS_DIR, "log")
                os.makedirs(dir, exist_ok=True)
                plot_log(values, labels, period, receivers, dir)
            elif mode == "ylim":
                dir = os.path.join(CHARTS_DIR, "ylim")
                os.makedirs(dir, exist_ok=True)
                plot_ylim(values, labels, period, receivers, dir)
            elif mode == "broken":
                dir = os.path.join(CHARTS_DIR, "broken")
                os.makedirs(dir, exist_ok=True)
                plot_broken(values, labels, period, receivers, dir)
            else:
                print("Wrong mode")
                exit(1)

    print("\nLoss summary:")
    for (period, receivers), groups in sorted(losses.items()):
        print(f"Period {period}s, Receivers {receivers}:")
        for (protocol, size), count in sorted(groups.items()):
            print(f"  {protocol}:{size} -> {count} losses")


if __name__ == "__main__":
    main()