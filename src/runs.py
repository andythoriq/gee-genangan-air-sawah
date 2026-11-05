"""Persist an analysis run to outputs/runs/ so results survive a refresh.

Each run gets its own folder holding the parameters, the validation samples,
the full threshold sweep and a short markdown summary that can be pasted into
a report. The map is not saved as HTML because Earth Engine tile URLs expire
within hours; a PNG of the water mask is downloaded instead, which is durable.
"""

import csv
import datetime as dt
import json
import os
import urllib.request

RUNS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "runs"
)


def _slug(value):
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(value))
    return cleaned.strip("-")[:40] or "run"


def _confusion(sweep, threshold):
    row = min(sweep, key=lambda entry: abs(entry["threshold"] - threshold))
    return row


def _summary(result, note, saved_at):
    row = _confusion(result["sweep"], result["threshold"])
    lines = [
        "# Analisis genangan — %s" % result["label"],
        "",
        "Disimpan: %s  " % saved_at,
        "Catatan: %s" % (note or "-"),
        "",
        "## Konfigurasi",
        "",
        "| Parameter | Nilai |",
        "|---|---|",
        "| Jendela kejadian | %s |" % result["event_window"],
        "| Jendela referensi | %s |" % (result["base_window"] or "tidak dipakai"),
        "| Besaran | %s |" % result["layer_label"],
        "| Masker awan | %s |" % result["mask_mode"],
        "| Ambang | %.2f |" % result["threshold"],
        "| Panjang morfologi | %s piksel |" % (result["clean_length"] or "tidak aktif"),
        "",
        "## Hasil",
        "",
        "| Ukuran | Nilai |",
        "|---|---|",
        "| Cakupan AOI | %.0f%% |" % (100 * result["observed"]),
        "| Cakupan jendela kejadian | %.0f%% |" % (100 * result["event_coverage"]),
        "| Cakupan jendela referensi | %s |" % (
            "-" if result["base_coverage"] is None
            else "%.0f%%" % (100 * result["base_coverage"])),
        "| Luas AOI | %.1f ha |" % result["total_ha"],
        "| Air mentah | %.1f ha |" % result["raw_ha"],
    ]
    if result["clean_ha"] is not None:
        lines.append("| Air setelah morfologi | %.1f ha |" % result["clean_ha"])
    lines += [
        "",
        "## Titik validasi",
        "",
        "| Titik | Harapan | Nilai |",
        "|---|---|---|",
    ]
    for point in result["points"]:
        shown = "-" if point["value"] is None else "%.3f" % point["value"]
        lines.append("| %s | %s | %s |" % (point["name"], point["expected"], shown))

    lines += [
        "",
        "## Confusion matrix pada ambang %.2f" % result["threshold"],
        "",
        "| | prediksi air | prediksi kering |",
        "|---|---|---|",
        "| tergenang | %d | %d |" % (row["tp"], row["fn"]),
        "| aman | %d | %d |" % (row["fp"], row["tn"]),
        "",
        "Balanced accuracy: %s  " % (
            "-" if row["balanced"] is None else "%.2f" % row["balanced"]),
        "Luas air pada ambang ini: %.1f ha (%.0f%% AOI)" % (
            row["water_ha"], row["water_pct"]),
        "",
        "> Ambang di dalam plateau bersifat sembarang. Dengan satu titik kontrol, "
        "matrix ini tidak membuktikan ambangnya benar.",
        "",
    ]
    return "\n".join(lines)


def save(result, note=""):
    """Write the run to a new folder and return its path."""
    saved_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    folder = os.path.join(
        RUNS_DIR, "%s_%s" % (dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
                             _slug(result["label"])))
    os.makedirs(folder, exist_ok=True)

    payload = {key: value for key, value in result.items() if key != "sweep"}
    payload["note"] = note
    payload["saved_at"] = saved_at
    with open(os.path.join(folder, "run.json"), "w") as handle:
        json.dump(payload, handle, indent=2, default=str)

    with open(os.path.join(folder, "points.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["point", "expected", "value"])
        for point in result["points"]:
            writer.writerow([point["name"], point["expected"], point["value"]])

    with open(os.path.join(folder, "sweep.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["sweep"][0].keys()))
        writer.writeheader()
        writer.writerows(result["sweep"])

    with open(os.path.join(folder, "summary.md"), "w") as handle:
        handle.write(_summary(result, note, saved_at))

    thumb = result.get("thumb_url")
    if thumb:
        try:
            with urllib.request.urlopen(thumb, timeout=30) as response:
                with open(os.path.join(folder, "water_mask.png"), "wb") as handle:
                    handle.write(response.read())
        except Exception:
            pass  # the numbers are saved regardless

    return folder


def recent(limit=5):
    """Most recent run folders, newest first."""
    if not os.path.isdir(RUNS_DIR):
        return []
    folders = [os.path.join(RUNS_DIR, name) for name in os.listdir(RUNS_DIR)
               if os.path.isdir(os.path.join(RUNS_DIR, name))]
    return sorted(folders, reverse=True)[:limit]
