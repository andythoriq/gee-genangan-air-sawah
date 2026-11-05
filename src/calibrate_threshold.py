"""Sweep a water threshold against the field validation points.

Two thresholds are possible and they answer different questions:

  --mode mndwi   "is this plot water now?"      MNDWI above the threshold
  --mode delta   "did this plot get wetter?"    event MNDWI minus baseline

Both are scored the same way, and both report the water extent the threshold
implies. Read the extent alongside the confusion matrix: a threshold can
separate four points perfectly while marking most of the AOI as water, which
means it is fitting noise rather than detecting floods.

Usage:
    python src/calibrate_threshold.py --event 2025-02-17 --mode mndwi
    python src/calibrate_threshold.py --event 2025-02-17 --mode delta
"""

import argparse
import csv
import os

import ee

import config
import indices
import sentinel

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

THRESHOLDS = [round(-0.60 + 0.01 * i, 2) for i in range(121)]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--event", required=True, choices=sorted(config.EVENTS))
    p.add_argument("--window", choices=("t1", "t2"), default="t2")
    p.add_argument("--mode", choices=("mndwi", "delta"), default="mndwi")
    p.add_argument("--baseline", choices=sorted(config.BASELINES),
                   help="reference window for --mode delta; defaults per event")
    p.add_argument("--step", type=float, default=0.05, help="print interval for the sweep")
    return p.parse_args()


def build_layer(args):
    """Return the image to threshold, plus a label describing it."""
    geom = sentinel.aoi()
    event_composite = sentinel.composite(
        *config.EVENTS[args.event][args.window], geom=geom, clip=False)
    if args.mode == "mndwi":
        return indices.mndwi(event_composite), "MNDWI"
    baseline = args.baseline or config.EVENTS[args.event]["baseline"]
    base_composite = sentinel.composite(*config.BASELINES[baseline], geom=geom, clip=False)
    return indices.mndwi(event_composite).subtract(indices.mndwi(base_composite)), "MNDWI delta"


def sample_points(image):
    """Mean value at each validation plot, or None where the plot is clouded."""
    features = [
        ee.Feature(
            ee.Geometry.Point(spec["lonlat"]).buffer(config.VALIDATION_BUFFER_M),
            {"name": name, "expected": spec["expected"]},
        )
        for name, spec in config.VALIDATION_POINTS.items()
    ]
    sampled = image.reduceRegions(
        ee.FeatureCollection(features), ee.Reducer.mean(), 10
    ).getInfo()["features"]
    return [
        {"name": f["properties"]["name"],
         "expected": f["properties"]["expected"],
         "value": f["properties"].get("mean")}
        for f in sampled
    ]


def histogram(image, mode, geom):
    """Counts in fixed-width bins across the AOI, as (bin_centre, count).

    The range must cover the full value domain, otherwise values outside it
    are dropped from both the numerator and the denominator and the resulting
    water fraction is inflated. MNDWI is bounded by [-1, 1]; a difference of
    two MNDWIs is bounded by [-2, 2].
    """
    low, high, steps = (-2.0, 2.0, 400) if mode == "delta" else (-1.0, 1.0, 200)
    width = (high - low) / steps
    band = image.bandNames().getInfo()[0]
    hist = image.reduceRegion(
        ee.Reducer.fixedHistogram(low, high, steps),
        geom, 10, maxPixels=int(1e9), bestEffort=True,
    ).get(band).getInfo()
    if not hist:
        # Fully masked window: reduceRegion returns null rather than an empty
        # histogram. Callers treat an empty list as "no water anywhere".
        return []
    return [(bucket[0] + width / 2, bucket[1]) for bucket in hist]


def water_fraction(hist, threshold):
    total = sum(count for _, count in hist)
    if not total:
        return 0.0
    return sum(count for centre, count in hist if centre > threshold) / total


def otsu(hist):
    """Threshold that maximises between-class variance, from a histogram alone.

    No labels involved, which is the point: it is a second opinion on where the
    distribution separates, independent of the field points.

    Read it as a corroboration, not a detector. Otsu assumes two classes, and
    the delta histogram here is unimodal with a long positive tail, so the
    algorithm will split whatever it is given: on quiet windows it still puts
    45-65 % of the observed area above its threshold. It cannot tell a flood
    from a cropping-stage change, so never report an extent derived from it.
    """
    total = sum(count for _, count in hist)
    if not total:
        return None
    weighted = sum(centre * count for centre, count in hist)
    low_count = 0.0
    low_sum = 0.0
    best = (-1.0, None)
    for index in range(len(hist) - 1):
        centre, count = hist[index]
        low_count += count
        low_sum += centre * count
        high_count = total - low_count
        if low_count <= 0 or high_count <= 0:
            continue
        between = (low_count * high_count
                   * (low_sum / low_count - (weighted - low_sum) / high_count) ** 2)
        if between > best[0]:
            best = (between, hist[index + 1][0])
    return best[1]


def score(points, threshold):
    """Confusion counts and derived rates for one threshold."""
    tp = fn = fp = tn = 0
    for point in points:
        if point["value"] is None:
            continue
        wet = point["value"] > threshold
        if point["expected"] == "inundated":
            tp += wet
            fn += not wet
        else:
            fp += wet
            tn += not wet
    recall = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    balanced = None
    if recall is not None and specificity is not None:
        balanced = (recall + specificity) / 2
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "recall": recall, "specificity": specificity, "balanced": balanced}


def fmt(value):
    return "   -  " if value is None else "%6.2f" % value


def main():
    args = parse_args()
    sentinel.init()

    image, label = build_layer(args)
    geom = sentinel.aoi()
    points = sample_points(image)
    hist = histogram(image, args.mode, geom)
    usable = [p for p in points if p["value"] is not None]

    start, end = config.EVENTS[args.event][args.window]
    print("%s %s  %s..%s   %s" % (args.event, args.window, start, end, label))
    print()
    print("Validation points")
    print("  %-20s %-10s %9s" % ("point", "expected", label))
    for point in points:
        shown = "      n/a" if point["value"] is None else "%9.3f" % point["value"]
        print("  %-20s %-10s %s" % (point["name"], point["expected"], shown))
    print()
    print("  %d of %d points have data." % (len(usable), len(points)))
    if len(usable) < len(points):
        print("  no observation: %s"
              % ", ".join(p["name"] for p in points if p["value"] is None))

    # water_fraction() is relative to observed pixels, which is not the AOI when
    # the layer is partly cloud-masked. Scale it so the printed extent is honest.
    observed = (sentinel.coverage(image).getInfo() or 0)
    aoi_ha = ee.Image.pixelArea().reduceRegion(
        ee.Reducer.sum(), geom, 10, maxPixels=int(1e9), bestEffort=True
    ).get("area").getInfo() / 10000.0
    scored = [(t, score(usable, t), water_fraction(hist, t) * observed)
              for t in THRESHOLDS]

    print()
    print("Sweep")
    print("  observed %.0f%% of AOI" % (100 * observed))
    print("  %6s %3s %3s %3s %3s %7s %7s %8s %8s"
          % ("thr", "TP", "FN", "FP", "TN", "recall", "spec", "bal_acc", "water%AOI"))
    for threshold, metrics, fraction in scored:
        if abs(round(threshold / args.step) * args.step - threshold) > 1e-9:
            continue
        print("  %6.2f %3d %3d %3d %3d %s %s %s %7.0f%%"
              % (threshold, metrics["tp"], metrics["fn"], metrics["fp"], metrics["tn"],
                 fmt(metrics["recall"]), fmt(metrics["specificity"]),
                 fmt(metrics["balanced"]), 100 * fraction))

    best = max(m["balanced"] for _, m, _ in scored if m["balanced"] is not None)
    winners = [t for t, m, _ in scored if m["balanced"] == best]
    print()
    print("Best balanced accuracy %.2f over thresholds %.2f..%.2f"
          % (best, min(winners), max(winners)))
    for threshold in (min(winners), max(winners), 0.0):
        metrics = score(usable, threshold)
        fraction = water_fraction(hist, threshold) * observed
        print("  thr %6.2f  water %5.1f%% (%.0f ha)  TP%d FN%d FP%d TN%d"
              % (threshold, 100 * fraction, fraction * aoi_ha,
                 metrics["tp"], metrics["fn"], metrics["fp"], metrics["tn"]))

    reference = otsu(hist)
    if reference is not None:
        fraction = water_fraction(hist, reference) * observed
        print()
        print("  Otsu (pembanding, tanpa label): thr %6.3f  water %5.1f%% (%.0f ha)"
              % (reference, 100 * fraction, fraction * aoi_ha))
        print("  Otsu tidak dipakai untuk analisis - lihat docstring otsu().")

    out = os.path.join(OUT_DIR, "threshold_%s_%s_%s.csv"
                       % (args.mode, args.event, args.window))
    with open(out, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["threshold", "tp", "fn", "fp", "tn", "recall",
                         "specificity", "balanced_accuracy", "water_fraction"])
        for threshold, metrics, fraction in scored:
            writer.writerow([threshold, metrics["tp"], metrics["fn"], metrics["fp"],
                             metrics["tn"], metrics["recall"], metrics["specificity"],
                             metrics["balanced"], round(fraction, 4)])
    print()
    print("sweep written to %s" % out)


if __name__ == "__main__":
    main()
