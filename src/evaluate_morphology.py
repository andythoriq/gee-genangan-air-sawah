"""Test the river-preservation filter and apply it to the real water mask.

Part 1 builds a synthetic scene with known geometry: one long channel, five
field-length bunds, five small blobs and one large water body. Retention is
measured per class, so the trade-off between removing noise and erasing rivers
is visible as numbers rather than as an impression.

Part 2 applies the same operators to the 2025-02-17 water mask.

No external river vector exists for this AOI to test against: JRC Global
Surface Water reports 0 % occurrence inside the AOI and MERIT Hydro puts the
entire area within 5.4 m of the nearest drainage, because it is a flat paddy
plain. Synthetic geometry with a known answer is therefore the only honest
reference available here.

Usage:
    python src/evaluate_morphology.py
"""

import os

import ee
import requests

import config
import indices
import morphology
import sentinel

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

CRS = "EPSG:32748"          # UTM zone 48S, covers West Java
ORIGIN = (700000.0, 9293000.0)
EXTENT = 640.0              # metres, i.e. 64 pixels at 10 m

RIVER = [(40, 560), (180, 552), (300, 566), (420, 540), (600, 556)]
BUNDS = [
    ((60, 430), (120, 430)),
    ((160, 440), (200, 470)),
    ((260, 430), (260, 490)),
    ((320, 440), (380, 440)),
    ((430, 430), (470, 470)),
]
BLOBS = [(80, 340), (180, 340), (280, 340), (380, 340), (480, 340)]
BLOB_SIZE = 40.0
BODY = (400.0, 80.0, 200.0)


def _xy(dx, dy):
    return [ORIGIN[0] + dx, ORIGIN[1] + dy]


def _line(coords):
    return ee.Geometry.LineString([_xy(*c) for c in coords], proj=CRS)


def _square(x, y, side):
    corners = [
        _xy(x, y), _xy(x + side, y), _xy(x + side, y + side),
        _xy(x, y + side), _xy(x, y),
    ]
    return ee.Geometry.Polygon([corners], proj=CRS, evenOdd=False)


def _paint(geometries, width=None):
    """Paint geometries at 10 m. A width turns a polygon into an outline."""
    collection = ee.FeatureCollection([ee.Feature(g) for g in geometries])
    image = ee.Image.constant(0)
    image = image.paint(collection, 1) if width is None else image.paint(collection, 1, width)
    return image.reproject(crs=CRS, scale=10)


def synthetic_layers():
    return {
        "river": _paint([_line(RIVER)]),
        "bunds": _paint([_line(b) for b in BUNDS]),
        "blobs": _paint([_square(x, y, BLOB_SIZE) for x, y in BLOBS]),
        "body": _paint([_square(*BODY)]),
    }


def region():
    corners = [
        _xy(0, 0), _xy(EXTENT, 0), _xy(EXTENT, EXTENT),
        _xy(0, EXTENT), _xy(0, 0),
    ]
    return ee.Geometry.Polygon([corners], proj=CRS, evenOdd=False)


def count(image):
    result = image.selfMask().reduceRegion(
        ee.Reducer.count(), region(), 10, crs=CRS, maxPixels=int(1e9)
    ).getInfo()
    return list(result.values())[0] or 0


def retention(layer, filtered):
    total = count(layer)
    return (count(layer.And(filtered)) / total) if total else 0.0


def run_synthetic():
    layers = synthetic_layers()
    combined = ee.ImageCollection(list(layers.values())).max()

    variants = [
        ("circular r=1", lambda m: morphology.open_circular(m, 1)),
        ("circular r=2", lambda m: morphology.open_circular(m, 2)),
        ("path len=9", lambda m: morphology.path_open(m, 9)),
        ("path len=15", lambda m: morphology.path_open(m, 15)),
        ("path len=21", lambda m: morphology.path_open(m, 21)),
        ("path len=25", lambda m: morphology.path_open(m, 25)),
        ("preserve len=15", lambda m: morphology.preserve_linear(m, 15)),
        ("preserve len=21", lambda m: morphology.preserve_linear(m, 21)),
        ("small objects", lambda m: morphology.remove_small_objects(m, 12)),
        ("clean len=15", lambda m: morphology.clean(m, 15)),
    ]

    print("Synthetic scene: 1 channel (560 m, 1 px wide), 5 bunds (60 m),")
    print("5 blobs (40 m squares), 1 water body (200 m square).")
    print()
    print("  %-16s %8s %8s %8s %8s %8s" %
          ("operator", "river", "bunds", "blobs", "body", "all px"))
    baseline = count(combined)
    for label, operator in variants:
        filtered = operator(combined)
        print("  %-16s %7.0f%% %7.0f%% %7.0f%% %7.0f%% %7.0f%%"
              % (label,
                 100 * retention(layers["river"], filtered),
                 100 * retention(layers["bunds"], filtered),
                 100 * retention(layers["blobs"], filtered),
                 100 * retention(layers["body"], filtered),
                 100 * count(filtered) / baseline))
    return combined


def run_real():
    event = sentinel.composite(*config.EVENTS["2025-02-17"]["t2"])
    base = sentinel.composite(*config.BASELINES["pre_event_2025_02"])
    delta = indices.mndwi(event).subtract(indices.mndwi(base))
    water = delta.gt(config.CALIBRATED_DELTA_THRESHOLD).rename("water")

    area = lambda image: (
        ee.Image.pixelArea().updateMask(image).reduceRegion(
            ee.Reducer.sum(), sentinel.aoi(), 10, maxPixels=int(1e9), bestEffort=True
        ).get("area").getInfo() or 0
    ) / 10000.0

    raw = area(water.selfMask())
    circular = area(morphology.open_circular(water, 2).selfMask())
    cleaned = area(morphology.clean(water, 15).selfMask())

    print()
    print("Real scene: 2025-02-17, delta MNDWI > %.2f" % config.CALIBRATED_DELTA_THRESHOLD)
    print("  %-16s %8s %8s" % ("operator", "water ha", "kept"))
    for label, value in (("none", raw),
                         ("circular r=2", circular),
                         ("clean len=15", cleaned)):
        print("  %-16s %8.1f %7.0f%%" % (label, value, 100 * value / raw if raw else 0))
    return water


def save_thumb(image, name, vis, geom=None, width=64, scale=10):
    """Render at the analysis scale.

    A thumbnail computed at a finer scale re-evaluates the focal operations on
    that finer grid, which silently turns a 1-pixel channel into a 7-pixel one
    and makes the filter look far gentler than it is. Pinning the reprojection
    and the output width to 10 m keeps the picture consistent with the counts.
    """
    url = image.reproject(crs=CRS, scale=scale).getThumbURL({
        **vis, "region": geom or region(), "dimensions": width,
        "crs": CRS, "format": "png",
    })
    path = os.path.join(OUT_DIR, name)
    with open(path, "wb") as handle:
        handle.write(requests.get(url).content)
    return path


def main():
    sentinel.init()
    combined = run_synthetic()
    water = run_real()

    vis = {"min": 0, "max": 1, "palette": ["ffffff", "08306b"]}
    print()
    for label, image in (("synthetic_raw", combined),
                         ("synthetic_circular", morphology.open_circular(combined, 2)),
                         ("synthetic_clean", morphology.clean(combined, 15))):
        print("  wrote %s" % save_thumb(image, label + ".png", vis))
    for label, image in (("real_raw", water),
                         ("real_clean", morphology.clean(water, 15))):
        print("  wrote %s" % save_thumb(
            image, label + ".png", vis, geom=sentinel.aoi(), width=330))


if __name__ == "__main__":
    main()
