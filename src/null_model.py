"""Null model: how much "water" this pipeline reports when nothing happened.

The flood estimate only means something if it stands above what the same
pipeline produces on quiet windows. Run the identical chain - same masker,
same reference window, same threshold - on a series of ordinary 16-day windows
and see what comes out. Whatever that distribution is, it is the floor. A flood
window at 43 ha is evidence only if the quiet windows sit well below it.

This is deliberately not a second flood detection method: it never looks at
the event, it only measures the noise.

Usage:
    python src/null_model.py
    python src/null_model.py --start 2025-03-01 --end 2025-11-30 --threshold 0.05
    python src/null_model.py --csv
"""

import argparse
import datetime as dt
import os
import statistics

import ee

import config
import indices
import sentinel

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")


def windows(start, end, days=16, step=16):
    """Consecutive [start, start+days) windows, stepping by 'step' days."""
    first = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    out = []
    cursor = first
    while cursor + dt.timedelta(days=days) <= last:
        out.append((cursor.isoformat(),
                    (cursor + dt.timedelta(days=days)).isoformat()))
        cursor += dt.timedelta(days=step)
    return out


def measure(layer, threshold, geom):
    """Observed coverage and water area for one thresholded image.

    One round trip for both numbers: coverage says whether the window can be
    trusted at all, area says what it reported. Reading them separately would
    double the cost of a scan that runs this for every window.
    """
    water = layer.gt(threshold).selfMask()
    # mask() keeps the source band name, so rename before reading the reducer
    # output or the lookup fails with "Dictionary does not contain key".
    valid = layer.mask().rename("valid")
    stats = ee.Dictionary({
        "coverage": valid.reduceRegion(
            ee.Reducer.mean(), geom, 10, maxPixels=int(1e9),
            bestEffort=True).get("valid"),
        "area": ee.Image.pixelArea().updateMask(water).reduceRegion(
            ee.Reducer.sum(), geom, 10, maxPixels=int(1e9),
            bestEffort=True).get("area"),
    }).getInfo()
    coverage = stats.get("coverage") or 0.0
    hectares = (stats.get("area") or 0.0) / 10000.0
    return coverage, hectares


def run(start, end, base_start, base_end, threshold=0.05, mask_mode=None,
        days=16, step=16, min_coverage=0.9):
    """Measure every window in [start, end) against the same reference.

    Returns one row per window. Windows below 'min_coverage' keep their
    coverage but get water_ha = None: a half-observed window can report a
    higher number than a fully observed one, so it cannot enter the floor.
    """
    geom = sentinel.aoi()
    base = sentinel.composite(base_start, base_end, mode=mask_mode, geom=geom, clip=False)
    base_mndwi = indices.mndwi(base)
    # The delta mask is the intersection of both windows, so its coverage can
    # never exceed the reference footprint. Gating on an absolute 90% would
    # reject every window whenever the reference itself covers only half the
    # AOI, which is the normal case here.
    base_coverage = sentinel.coverage(base, geom).getInfo() or 0.0
    cutoff = min_coverage * base_coverage

    rows = []
    for window_start, window_end in windows(start, end, days, step):
        composite = sentinel.composite(window_start, window_end, mode=mask_mode,
                                       geom=geom, clip=False)
        layer = indices.mndwi(composite).subtract(base_mndwi)
        coverage, hectares = measure(layer, threshold, geom)
        rows.append({
            "start": window_start,
            "end": window_end,
            "coverage": coverage,
            "water_ha": hectares if coverage >= cutoff else None,
        })
    return rows, base_coverage


def usable(rows):
    return [row["water_ha"] for row in rows if row["water_ha"] is not None]


def summary(rows, flood_ha=None):
    values = usable(rows)
    if not values:
        return {"count": 0, "median": None, "max": None, "exceeded": None}
    below = sum(1 for value in values if value < flood_ha) if flood_ha is not None else None
    return {
        "count": len(values),
        "median": statistics.median(values),
        "max": max(values),
        "exceeded": below,
    }


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", default="2025-03-01", help="first quiet window start")
    p.add_argument("--end", default="2025-11-30", help="last quiet window end")
    p.add_argument("--days", type=int, default=16, help="window length in days")
    p.add_argument("--step", type=int, default=16, help="days between window starts")
    p.add_argument("--threshold", type=float, default=config.CALIBRATED_DELTA_THRESHOLD)
    p.add_argument("--baseline", choices=sorted(config.BASELINES),
                   default="pre_event_2025_02",
                   help="reference window; keep it identical to the flood analysis")
    p.add_argument("--mask", choices=("scl", "qa60", "strict"),
                   default=config.CLOUD_MASK_MODE)
    p.add_argument("--min-coverage", type=float, default=0.9,
                   help="windows below this are excluded from the floor")
    p.add_argument("--flood-ha", type=float,
                   help="flood estimate to compare against, e.g. 43.4")
    p.add_argument("--csv", action="store_true", help="also write outputs/null_model.csv")
    return p.parse_args()


def main():
    args = parse_args()
    sentinel.init()

    base_start, base_end = config.BASELINES[args.baseline]
    rows, base_coverage = run(args.start, args.end, base_start, base_end,
                              args.threshold, args.mask, args.days, args.step,
                              args.min_coverage)
    stats = summary(rows, args.flood_ha)

    print("Kontrol null-model: delta MNDWI vs %s, ambang %.2f, masker %s"
          % (args.baseline, args.threshold, args.mask))
    print("%s..%s, jendela %d hari, langkah %d hari" 
          % (args.start, args.end, args.days, args.step))
    print("Referensi menutup %.0f%% AOI, jadi ambang kelayakan %.0f%% irisan\n"
          % (100 * base_coverage, 100 * args.min_coverage * base_coverage))
    print("%-12s %-12s %8s %10s" % ("Mulai", "Selesai", "Cakupan", "Air (ha)"))
    for row in rows:
        water = "-" if row["water_ha"] is None else "%.1f" % row["water_ha"]
        print("%-12s %-12s %7.0f%% %10s"
              % (row["start"], row["end"], 100 * row["coverage"], water))

    print("\nJendela terpakai: %d dari %d (irisan >= %.0f%% AOI)"
          % (stats["count"], len(rows), 100 * args.min_coverage * base_coverage))
    if stats["count"]:
        print("Lantai: median %.1f ha, maksimum %.1f ha"
              % (stats["median"], stats["max"]))
    if args.flood_ha is not None and stats["count"]:
        print("\nJendela banjir: %.1f ha - lebih tinggi dari %d/%d jendela tenang."
              % (args.flood_ha, stats["exceeded"], stats["count"]))

    if args.csv:
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "null_model.csv")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("start,end,coverage,water_ha\n")
            for row in rows:
                handle.write("%s,%s,%.4f,%s\n" % (
                    row["start"], row["end"], row["coverage"],
                    "" if row["water_ha"] is None else "%.2f" % row["water_ha"]))
        print("\nCSV: %s" % path)


if __name__ == "__main__":
    main()
