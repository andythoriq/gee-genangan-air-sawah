"""Project configuration: study area, flood events, Sentinel-2 constants.

Pure data - no Earth Engine import, so this file can be read and diffed
without an authenticated session. Coordinates are (longitude, latitude)
in WGS84, which is the order Earth Engine expects.
"""

GEE_PROJECT = "tubes-pcd-praktik-004-019"

# Desa Citrajaya, Kabupaten Subang, Jawa Barat.
# [west, south, east, north] -> roughly 3.3 km x 1.7 km of paddy mosaic.
AOI_BOUNDS = [107.8050, -6.4000, 107.8350, -6.3850]

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
#   pre_event_2025_02   2024-11-01..2024-12-31          68%
#   pre_event_2026_01   2025-12-15..2026-01-15         100%
# January 2025 itself has 0% coverage, so the nearest usable pre-event window
# for the 2025-02-17 flood is Nov-Dec 2024, not the preceding month.
#
# Baseline choice is not cosmetic. Measured on the 2025-02-17 event, comparing
# against dry_season_2024 (June-August, the dry-season cropping period) reports
# 277 ha "receded" and makes all three inundated plots read drier than the
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
# Measured AOI coverage with CLOUD_MASK_MODE = "scl" (2026-11-05):
#   event        t1    t2    nearest usable acquisition
#   2025-02-17   0%   100%   2025-02-27 (10 days after)
#   2026-01-24   0%    35%   2026-02-02 (9 days after, partial)
#   2026-01-29   0%     0%   2026-02-02 (4 days after, partial)
#
# Every t1 window is empty: no clear pixel exists over the AOI on or near any
# reported flood date. Do not treat these windows as validated - widen them
# and re-run `python src/preview_event.py --diagnose` before committing to a
# design.
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

# Field validation points. "Safe" is the negative control: it should stay
# dry in every event, so any water detected there is a false positive.
VALIDATION_POINTS = {
    "Sawah Kontrak 1": {"lonlat": [107.83064, -6.39555], "expected": "inundated"},
    "Sawah Impres": {"lonlat": [107.80748, -6.39770], "expected": "safe"},
    "Sawah PU & Keprak": {"lonlat": [107.81818, -6.38834], "expected": "inundated"},
    "Sawah Kontrak 2": {"lonlat": [107.82643, -6.39678], "expected": "inundated"},
}

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
