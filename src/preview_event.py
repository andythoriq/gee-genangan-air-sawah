"""Inspect data availability and render an MNDWI preview for one flood event.

Usage:
    python src/preview_event.py --diagnose
    python src/preview_event.py --event 2025-02-17 --window t2

--diagnose reports, for every event and window, how many scenes exist and
what fraction of the AOI survives cloud masking. Run it before choosing
windows: at this AOI most wet-season windows are fully cloud-covered, and a
window with coverage near zero cannot support any conclusion.
"""

import argparse
import datetime as dt
import os

import ee
import geemap

import config
import indices
import sentinel

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

MNDWI_VIS = {"min": -0.6, "max": 0.6, "palette": ["8c510a", "f5f5f5", "2b83ba"]}
TRUE_COLOR_VIS = {"bands": [config.RED, config.GREEN, "B2"], "min": 0, "max": 3000}
WATER_VIS = {"palette": ["0000ff"]}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--event", choices=sorted(config.EVENTS), help="flood event date")
    p.add_argument("--window", choices=("t1", "t2"), default="t2",
                   help="t1 = peak inundation, t2 = recession")
    p.add_argument("--diagnose", action="store_true",
                   help="report scene counts and coverage for all events")
    p.add_argument("--out", default=None, help="output HTML path")
    return p.parse_args()


def report_coverage():
    print("mask mode: %s" % config.CLOUD_MASK_MODE)
    print("%-12s %-3s %-24s %7s %9s" % ("event", "win", "window", "scenes", "coverage"))
    for event, windows in config.EVENTS.items():
        for name in ("t1", "t2"):
            start, end = windows[name]
            cov = sentinel.coverage(sentinel.composite(start, end)).getInfo()
            n = sentinel.scene_count(start, end).getInfo()
            flag = "" if (cov or 0) >= 0.5 else "  <- unusable"
            print("%-12s %-3s %-24s %7d %8.0f%%%s"
                  % (event, name, "%s..%s" % (start, end), n, 100 * (cov or 0), flag))
    print()
    print("Per-scene coverage, clearest 12 scenes around each event:")
    for event in config.EVENTS:
        centre = dt.date.fromisoformat(event)
        start = (centre - dt.timedelta(days=30)).isoformat()
        end = (centre + dt.timedelta(days=30)).isoformat()
        scenes = sentinel.collection(start, end).toList(12).getInfo()
        print("  %s (%s..%s, %d scenes)" % (event, start, end, len(scenes)))
        for meta in scenes:
            img = ee.Image(meta["id"]).clip(sentinel.aoi())
            cov = sentinel.coverage(sentinel.mask_clouds(img)).getInfo() or 0
            stamp = dt.datetime.fromtimestamp(
                meta["properties"]["system:time_start"] / 1000, dt.timezone.utc
            ).strftime("%Y-%m-%d")
            cloud = meta["properties"].get("CLOUDY_PIXEL_PERCENTAGE", -1)
            print("     %s  scene cloud %3.0f%%  aoi coverage %3.0f%%" % (stamp, cloud, 100 * cov))


def sample_points(mndwi_image, event=None):
    features = [
        ee.Feature(
            ee.Geometry.Point(spec["lonlat"]).buffer(config.VALIDATION_BUFFER_M),
            {"name": name},
        )
        for name, spec in config.VALIDATION_POINTS.items()
    ]
    sampled = mndwi_image.reduceRegions(
        ee.FeatureCollection(features), ee.Reducer.mean(), 10
    ).getInfo()["features"]
    print("  %-20s %-10s %8s %10s" % ("point", "ground truth", "MNDWI", "verdict"))
    for feature in sampled:
        props = feature["properties"]
        value = props.get("mean")
        if value is None:
            verdict = "no data"
            shown = "   n/a"
        else:
            verdict = "water" if value > config.PREVIEW_THRESHOLD else "dry"
            shown = "%8.3f" % value
        expected = config.label_for(props["name"], event) or "-"
        print("  %-20s %-10s %s %10s" % (props["name"], expected, shown, verdict))


def build_map(event, window):
    start, end = config.EVENTS[event][window]
    geom = sentinel.aoi()
    composite = sentinel.composite(start, end, geom=geom)
    mndwi_image = indices.mndwi(composite)
    water = mndwi_image.gt(config.PREVIEW_THRESHOLD).selfMask()

    cov = sentinel.coverage(composite).getInfo() or 0
    stats = mndwi_image.reduceRegion(
        ee.Reducer.mean().combine(ee.Reducer.stdDev(), None, True),
        geom, 10, maxPixels=int(1e9), bestEffort=True,
    ).getInfo()

    print("%s %s  %s..%s" % (event, window, start, end))
    print("  scenes: %d   AOI coverage: %.0f%%" % (sentinel.scene_count(start, end).getInfo(), 100 * cov))
    print("  MNDWI mean %.3f  sd %.3f" % (stats["MNDWI_mean"] or 0, stats["MNDWI_stdDev"] or 0))
    sample_points(mndwi_image, event)

    m = geemap.Map()
    m.centerObject(geom, 15)
    m.add_basemap("SATELLITE")
    m.addLayer(composite, TRUE_COLOR_VIS, "Sentinel-2 %s" % window)
    m.addLayer(mndwi_image, MNDWI_VIS, "MNDWI")
    m.addLayer(water, WATER_VIS, "Water > %.2f (preview only)" % config.PREVIEW_THRESHOLD)
    m.addLayer(geom, {"color": "red"}, "AOI")
    for name, spec in config.VALIDATION_POINTS.items():
        m.addLayer(ee.Geometry.Point(spec["lonlat"]), {"color": "yellow"}, name)

    out = os.path.join(OUT_DIR, "mndwi_%s_%s.html" % (event, window))
    m.to_html(out)
    print("  map written to %s" % out)
    return out


def main():
    args = parse_args()
    sentinel.init()
    if args.diagnose:
        report_coverage()
    if args.event:
        build_map(args.event, args.window)
    if not args.diagnose and not args.event:
        print("nothing to do; pass --diagnose and/or --event")


if __name__ == "__main__":
    main()
