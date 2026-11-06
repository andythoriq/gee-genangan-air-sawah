"""Project configuration: study area, flood events, Sentinel-2 constants.

Pure data - no Earth Engine import, so this file can be read and diffed
without an authenticated session. Coordinates are (longitude, latitude)
in WGS84, which is the order Earth Engine expects.
"""

GEE_PROJECT = "tubes-pcd-praktik-004-019"

# Desa Citrajaya, Kabupaten Subang, Jawa Barat.
# Single closed ring of [longitude, latitude] vertices, taken from the field
# survey polygon. Measured area 172.7 ha, roughly 1.9 km north-south and
# 1.7 km east-west. This replaced an earlier 550.6 ha rectangle.
AOI_RING = [
    [107.8165453306055, -6.394861081048648],
    [107.8238014273127, -6.396735270021070],
    [107.8290714925230, -6.397987006207768],
    [107.8316331159016, -6.397869307819206],
    [107.8315541615117, -6.396009647159473],
    [107.8316033092338, -6.393750828438737],
    [107.8305985245429, -6.393680375725702],
    [107.8302398065243, -6.392676765843302],
    [107.8294431266262, -6.393319311013563],
    [107.8283203975000, -6.393349450502306],
    [107.8273315868247, -6.392059207697651],
    [107.8280630914185, -6.391713856395225],
    [107.8279930103718, -6.390372204285814],
    [107.8284554469679, -6.388978292125958],
    [107.8284388792987, -6.388125868780078],
    [107.8266151862043, -6.387879546680330],
    [107.8260754771643, -6.386552475718674],
    [107.8269388620901, -6.384604546522718],
    [107.8261966235703, -6.384343066264780],
    [107.8254391878215, -6.383317417661558],
    [107.8248220022360, -6.384590363778806],
    [107.8239231056402, -6.384279375413631],
    [107.8226550575378, -6.384360755566918],
    [107.8220460790959, -6.383429818809991],
    [107.8210100116073, -6.382621354251695],
    [107.8188460534374, -6.385181003255593],
    [107.8172873065823, -6.389933594980659],
    [107.8165453306055, -6.394861081048648],
]

# Sentinel-2 Level-2A surface reflectance (harmonised processing baseline).
S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

# Band aliases. B11 (SWIR1) is natively 20 m; Earth Engine resamples it onto
# the 10 m grid of B3 when the index is computed, so MNDWI inherits the
# 10 m pixel size but not the 10 m information content.
RED = "B4"
GREEN = "B3"
NIR = "B8"
SWIR1 = "B11"

# Scene-level cloud filter. Measured over this AOI: every scene between
# 2025-02 and 2026-02 carries 70-100 % cloud cover, so any threshold below
# 100 returns an empty collection. Real cloud rejection happens per pixel
# (see CLOUD_MASK_MODE); this stays at 100, i.e. no scene is dropped.
MAX_CLOUDY_PIXEL_PERCENTAGE = 100

# Per-pixel mask strategy.
#   "scl"    Scene Classification Layer: shadow, cloud, cirrus, snow.
#   "qa60"   QA60 bits 10 and 11, the method named in AGENTS.md.
#   "strict" both must agree (fewest pixels, highest confidence).
# Measured: QA60 alone masks 100 % of the AOI on scenes where SCL reports a
# fully clear view (e.g. 2025-12-21), so QA60 over-rejects in this humid
# setting. "scl" is the default for that reason, not out of preference.
CLOUD_MASK_MODE = "scl"

# Reference windows used as the "before" state when measuring excess water.
# A baseline must be a period when the plots are not flood-affected, so any
# water in the event composite can be attributed to the reported event.
#
# Measured AOI coverage with CLOUD_MASK_MODE = "scl" (2026-11-05):
#   name                window                     coverage
#   dry_season_2024     2024-06-01..2024-08-31         100%
#   pre_event_2025_02   2024-11-01..2024-12-31          55%
#   pre_event_2026_01   2025-12-15..2026-01-15         100%
# January 2025 itself has 0% coverage, so the nearest usable pre-event window
# for the 2025-02-17 flood is Nov-Dec 2024, not the preceding month.
#
# Baseline choice is not cosmetic. Measured on the 2025-02-17 event, comparing
# against dry_season_2024 (June-August, the dry-season cropping period) reports
# 67 ha "receded" and makes all three inundated plots read drier than the
# baseline - the seasonal cropping cycle dominates the flood signal. Comparing
# against pre_event_2025_02 keeps that confound small enough for the validation
# points to separate correctly. Prefer a pre-event window over a dry-season one.
BASELINES = {
    "dry_season_2024": ("2024-06-01", "2024-08-31"),
    "pre_event_2025_02": ("2024-11-01", "2024-12-31"),
    "pre_event_2026_01": ("2025-12-15", "2026-01-15"),
}

# Flood events reported by residents. t1 = peak inundation, t2 = recession.
#
# Measured AOI coverage with CLOUD_MASK_MODE = "scl" (re-measured 2026-11-06):
#   event        t1    t2    acquisitions that survive the mask
#   2025-02-17   0%    99%   2025-02-27 (both overpasses) and 2025-03-01
#   2026-01-24   0%    54%   2026-02-02 only, and only 54% of the AOI
#   2026-01-29   0%     0%   nothing - 2026-02-02 falls outside both windows
#
# Every t1 window is empty: no clear pixel exists over the AOI on or near any
# reported flood date. Do not treat these windows as validated - widen them
# and re-run `python src/preview_event.py --diagnose` before committing to a
# design.
#
# The t2 composite is a median, not a date. For 2025-02-17 it mixes 27 Feb and
# 1 Mar, so a ground-truth label for it must describe that two-day window, not
# 27 Feb alone. For 2026-01-24 it is effectively 2 Feb, and the other 46% of
# the AOI has no observation at all - a point there cannot be scored.
EVENTS = {
    "2025-02-17": {
        "t1": ("2025-02-15", "2025-02-19"),
        "t2": ("2025-02-22", "2025-03-04"),
        "baseline": "pre_event_2025_02",
    },
    "2026-01-24": {
        "t1": ("2026-01-22", "2026-01-26"),
        "t2": ("2026-01-29", "2026-02-08"),
        "baseline": "pre_event_2026_01",
    },
    "2026-01-29": {
        "t1": ("2026-01-27", "2026-01-31"),
        "t2": ("2026-02-03", "2026-02-13"),
        "baseline": "pre_event_2026_01",
    },
}

# Ground-truth labels for the confusion matrix. Only these two strings are
# accepted. Anything else ("Inundated", "tergenang", "flooded") would be
# counted as a negative control without warning, because score() only tests
# for equality with "inundated"; label_for() raises instead.
GROUND_TRUTH_LABELS = ("inundated", "safe")

# Field validation points, one entry per plot.
#
#   lonlat       [longitude, latitude] WGS84; sampled as a disc of
#                VALIDATION_BUFFER_M, not a single pixel
#   expected     condition at the surveyed event: "inundated" or "safe".
#                "safe" is the negative control - any water detected there is
#                a false positive.
#   observed_on  optional "YYYY-MM-DD" the condition was read: the field visit,
#                or the acquisition date of the high-resolution image used for
#                visual interpretation. Label the imagery date, not the visit
#                date, if the two differ.
#   source       optional short string: "wawancara petani", "citra Planet
#                2025-02-18", ... The report has to say which of the two it is,
#                so record it here rather than in your notes.
#   events       optional {event date: label} override. A value of None means
#                "not observed in this event": the plot is still sampled and
#                shown, but it is left out of that event's confusion matrix.
#                Without this a plot carries the same label into all three
#                events, which cannot be true for three separate floods.
#
# Add a point before you look at the index value at that point. Choosing the
# location after seeing that the index is high there is label leakage, and it
# inflates every accuracy figure computed from the matrix.
VALIDATION_POINTS = {
    "Sawah Kontrak 1": {"lonlat": [107.83064, -6.39555], "expected": "inundated"},
    "Sawah Impres": {"lonlat": [107.80748, -6.39770], "expected": "safe"},
    "Sawah PU & Keprak": {"lonlat": [107.81818, -6.38834], "expected": "inundated"},
    "Sawah Kontrak 2": {"lonlat": [107.82643, -6.39678], "expected": "inundated"},
}


def label_for(name, event=None):
    """Ground truth for one plot in one event, or None if it was not observed.

    Returns None when the point carries an explicit None override for that
    event. Callers keep such a point in their tables but must drop it from the
    confusion matrix - there is no label to score against.
    """
    spec = VALIDATION_POINTS[name]
    overrides = spec.get("events") or {}
    if event is not None and event in overrides:
        label = overrides[event]
    else:
        label = spec["expected"]
    if label is not None and label not in GROUND_TRUTH_LABELS:
        raise ValueError(
            "titik %r, event %r: label %r tidak dikenal; pakai %s atau None"
            % (name, event, label, " / ".join(repr(l) for l in GROUND_TRUTH_LABELS)))
    return label

# Radius around each validation point used when sampling MNDWI, in metres.
# 30 m spans ~9 pixels of 10 m, which averages out single-pixel noise.
VALIDATION_BUFFER_M = 30

# Threshold used only to draw a rough water layer in the preview map.
# It is NOT the calibrated threshold - that comes from the thresholding step
# and must be justified against the validation points.
PREVIEW_THRESHOLD = 0.0

# Operating point from src/calibrate_threshold.py --mode delta on 2025-02-17.
# Balanced accuracy 1.00 holds across a plateau of -0.32 .. 0.05; 0.05 is the
# most conservative value on it, i.e. the smallest water extent that still
# separates all validation points. Supported by one negative sample only.
CALIBRATED_DELTA_THRESHOLD = 0.05
