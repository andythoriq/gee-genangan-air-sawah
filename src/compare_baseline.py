"""Compare a flood event against a dry reference window.

This answers the question the t1/t2 design cannot: since no clear Sentinel-2
observation exists at any reported flood peak over this AOI, measure excess
water as "water present in the event window but absent in a reference window"
instead of "water at t1 versus t2".

Usage:
    python src/compare_baseline.py --event 2025-02-17
    python src/compare_baseline.py --all
    python src/compare_baseline.py --event 2026-01-24 --baseline dry_season_2024

Classes reported per event, in hectares:
    persistent  water in both windows - candidate hazard, needs inspection
    new         water only in the event window - the actual flood signal
    receded     water only in the reference window - drainage or misalignment
"""

import argparse
import os

import ee
import geemap

import config
import indices
import sentinel

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

MNDWI_VIS = {"min": -0.6, "max": 0.6, "palette": ["8c510a", "f5f5f5", "2b83ba"]}
DELTA_VIS = {"min": -0.5, "max": 0.5, "palette": ["2166ac", "f7f7f7", "b2182b"]}
TRUE_COLOR_VIS = {"bands": [config.RED, config.GREEN, "B2"], "min": 0, "max": 3000}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--event", choices=sorted(config.EVENTS))
    p.add_argument("--all", action="store_true", help="run every event")
    p.add_argument("--window", choices=("t1", "t2"), default="t2")
    p.add_argument("--baseline", choices=sorted(config.BASELINES),
                   help="reference window; defaults to the one set per event")
    p.add_argument("--threshold", type=float, default=config.PREVIEW_THRESHOLD,
                   help="MNDWI water threshold (preview value, not calibrated)")
    return p.parse_args()


def area_ha(mask, geom):
    """Area of a boolean mask in hectares, or None where nothing matches."""
    square_metres = (
        ee.Image.pixelArea()
        .updateMask(mask)
        .reduceRegion(ee.Reducer.sum(), geom, 10, maxPixels=int(1e9), bestEffort=True)
        .get("area")
        .getInfo()
    )
    return None if square_metres is None else square_metres / 10000.0


def sample_points(layers, geom):
    """Sample every layer at the validation points and print a comparison."""
    features = [
        ee.Feature(
            ee.Geometry.Point(spec["lonlat"]).buffer(config.VALIDATION_BUFFER_M),
            {"name": name, "expected": spec["expected"]},
        )
        for name, spec in config.VALIDATION_POINTS.items()
    ]
    fc = ee.FeatureCollection(features)
    values = {
        label: image.reduceRegions(fc, ee.Reducer.mean(), 10).getInfo()["features"]
        for label, image in layers.items()
    }
    print("  %-20s %-10s %9s %9s %8s  %s"
          % ("point", "expected", "baseline", "event", "delta", "reading"))
    for i, feature in enumerate(features):
        name = feature.get("name").getInfo()
        expected = feature.get("expected").getInfo()
        row = {label: values[label][i]["properties"].get("mean") for label in layers}
        base, event = row["baseline"], row["event"]
        if base is None or event is None:
            print("  %-20s %-10s %9s %9s %8s  no data" % (name, expected, "-", "-", "-"))
            continue
        delta = event - base
        reading = "wet increase" if delta > 0.05 else "no change" if abs(delta) <= 0.05 else "drier"
        print("  %-20s %-10s %9.3f %9.3f %8.3f  %s"
              % (name, expected, base, event, delta, reading))


def run(event, window, baseline_name, threshold):
    event_start, event_end = config.EVENTS[event][window]
    base_start, base_end = config.BASELINES[baseline_name]
    geom = sentinel.aoi()

    event_composite = sentinel.composite(event_start, event_end, geom=geom, clip=False)
    base_composite = sentinel.composite(base_start, base_end, geom=geom, clip=False)
    event_mndwi = indices.mndwi(event_composite)
    base_mndwi = indices.mndwi(base_composite)

    event_water = event_mndwi.gt(threshold)
    base_water = base_mndwi.gt(threshold)
    persistent = event_water.And(base_water)
    new_water = event_water.And(base_water.Not())
    receded = event_water.Not().And(base_water)

    event_cov = sentinel.coverage(event_composite).getInfo() or 0
    base_cov = sentinel.coverage(base_composite).getInfo() or 0

    print("=" * 78)
    print("%s  window %s  %s..%s" % (event, window, event_start, event_end))
    print("baseline %s  %s..%s" % (baseline_name, base_start, base_end))
    print("threshold MNDWI > %.2f   mask mode %s" % (threshold, config.CLOUD_MASK_MODE))
    print("  coverage   event %.0f%%   baseline %.0f%%" % (100 * event_cov, 100 * base_cov))
    print("  area (ha)  persistent %.2f   new %.2f   receded %.2f   AOI %.2f"
          % (area_ha(persistent, geom) or 0.0,
             area_ha(new_water, geom) or 0.0,
             area_ha(receded, geom) or 0.0,
             area_ha(ee.Image.constant(1), geom) or 0.0))
    sample_points({"baseline": base_mndwi, "event": event_mndwi}, geom)

    m = geemap.Map()
    m.centerObject(geom, 15)
    m.add_basemap("SATELLITE")
    m.addLayer(base_composite, TRUE_COLOR_VIS, "baseline true colour")
    m.addLayer(event_composite, TRUE_COLOR_VIS, "event true colour")
    m.addLayer(base_mndwi, MNDWI_VIS, "baseline MNDWI")
    m.addLayer(event_mndwi, MNDWI_VIS, "event MNDWI")
    m.addLayer(event_mndwi.subtract(base_mndwi), DELTA_VIS, "MNDWI delta")
    m.addLayer(persistent.selfMask(), {"palette": ["08306b"]}, "persistent")
    m.addLayer(new_water.selfMask(), {"palette": ["41b6c4"]}, "new water")
    m.addLayer(receded.selfMask(), {"palette": ["fd8d3c"]}, "receded")
    m.addLayer(geom, {"color": "red"}, "AOI")
    for name, spec in config.VALIDATION_POINTS.items():
        m.addLayer(ee.Geometry.Point(spec["lonlat"]), {"color": "yellow"}, name)

    out = os.path.join(OUT_DIR, "compare_%s_%s.html" % (event, baseline_name))
    m.to_html(out)
    print("  map written to %s" % out)
    return out


def main():
    args = parse_args()
    sentinel.init()
    if not args.all and not args.event:
        raise SystemExit("pass --event <date> or --all")
    events = sorted(config.EVENTS) if args.all else [args.event]
    for event in events:
        baseline_name = args.baseline or config.EVENTS[event]["baseline"]
        run(event, args.window, baseline_name, args.threshold)


if __name__ == "__main__":
    main()
