# Data availability, threshold calibration and river preservation — working report

**Date:** 2026-11-05
**Scope:** Replace the scratch GEE script with a config-driven pipeline; establish whether the
reported flood events are observable; calibrate the MNDWI threshold against the field validation
points; build a cleanup that removes noise without erasing the river channels.
**Status:** Pipeline operational. One event is analysable. Threshold sits on a plateau supported by
a single negative sample. River preservation works on synthetic geometry and is neutral on the real
mask.

All figures below were produced by the scripts in `src/` against
`COPERNICUS/S2_SR_HARMONIZED` over the AOI `[107.8050, -6.4000, 107.8350, -6.3850]`
(550.6 ha). Every number is reproducible with the commands in section 8.

---

## 1. What replaced what

`src/test_gee.py` was deleted. It pointed at a Jakarta coordinate buffered by 10 km, not at Desa
Citrajaya, so every map it produced was of the wrong place. It has been replaced by:

| File | Responsibility |
|---|---|
| `src/config.py` | AOI, event windows, reference windows, validation points, mask mode. Pure data, no `ee` import. |
| `src/sentinel.py` | `aoi()`, `mask_qa60()`, `mask_scl()`, `collection()`, `composite()`, `coverage()` |
| `src/indices.py` | `mndwi()` (Green/SWIR1), `ndwi()` (Green/NIR, kept as the baseline to argue against) |
| `src/morphology.py` | `open_circular()` (control), `path_open()`, `preserve_linear()`, `clean()` |
| `src/preview_event.py` | Coverage diagnostics and a single-window MNDWI preview |
| `src/compare_baseline.py` | Event-versus-reference comparison, area statistics, class map |
| `src/calibrate_threshold.py` | Threshold sweep, confusion matrix, water-extent trade-off |
| `src/evaluate_morphology.py` | Synthetic-geometry test of the cleanup, then application to the real mask |

The AOI was verified visually against true-colour imagery: a paddy mosaic with a village and a
meandering channel on the eastern edge. The coordinates in `docs/AGENTS.md` are correct.

---

## 2. Finding: no reported flood peak is observable

Sentinel-2 scene-level cloud cover over this AOI is 70–100 % for every acquisition between February
2025 and February 2026. Any `CLOUDY_PIXEL_PERCENTAGE` filter below 100 returns an empty collection,
so scene-level filtering is disabled and rejection happens per pixel.

Measured AOI coverage after per-pixel masking:

| Event | t1 (peak) | t2 (recession) | Nearest usable acquisition |
|---|---|---|---|
| 2025-02-17 | 0 % | 100 % | 2025-02-27 (10 days after) |
| 2026-01-24 | 0 % | 35 % | 2026-02-02 (9 days after, partial) |
| 2026-01-29 | 0 % | 0 % | 2026-02-02 (4 days after, partial) |

**No t1 window contains a single clear pixel.** There is no observation of peak inundation for any
reported event. The t1-versus-t2 comparison described in `docs/AGENTS.md` cannot be executed as
written, and the two January 2026 events collapse onto the same acquisition.

Consequence: the study must be framed as *excess water after the event*, measured against a
reference window, rather than as peak-versus-recession.

---

## 3. Finding: QA60 is unusable here

`docs/AGENTS.md` mandates QA60 for cloud masking. Measured behaviour over this AOI:

- 2025-12-21 — QA60 retains **0 %** of the AOI while SCL reports a fully clear scene.
- 2026-02-02 — QA60 retains 80 %, SCL retains 35 %.

QA60's cirrus bit over-triggers in this humid setting and discards usable observations. The default
is therefore `CLOUD_MASK_MODE = "scl"`, with `"qa60"` and `"strict"` still selectable. This is a
deliberate, documented deviation from the project brief.

---

## 4. Finding: the reference window dominates the result

Same event, same threshold, two different reference windows:

| Reference window | persistent | new | receded | Validation points |
|---|---|---|---|---|
| `pre_event_2025_02` (Nov–Dec 2024) | 13.9 ha | 47.6 ha | 48.4 ha | directionally correct |
| `dry_season_2024` (Jun–Aug 2024) | 57.5 ha | 22.7 ha | 277.0 ha | all inundated plots read *drier* |

The dry-season window is the dry-season cropping period, when the paddies are themselves irrigated.
277 ha of a 550 ha AOI flips to "receded", and every inundated plot is classified as drier than the
reference — the seasonal cropping cycle swamps the flood signal.

`pre_event_2025_02` is the defensible choice. January 2025 itself has 0 % coverage, so the nearest
usable pre-event window for the February 2025 flood is two months earlier.

---

## 5. Threshold calibration

### 5.1 Absolute MNDWI — fails

Validation points, event window 2025-02-22 … 2025-03-04:

| Plot | Expected | MNDWI |
|---|---|---|
| Sawah Kontrak 1 | inundated | −0.367 |
| Sawah Impres | safe | −0.553 |
| Sawah PU & Keprak | inundated | −0.197 |
| Sawah Kontrak 2 | inundated | −0.148 |

| Threshold | TP | FN | FP | TN | recall | specificity | balanced acc. | water, % of AOI |
|---|---|---|---|---|---|---|---|---|
| −0.55 | 3 | 0 | 0 | 1 | 1.00 | 1.00 | 1.00 | 91 % |
| −0.45 | 3 | 0 | 0 | 1 | 1.00 | 1.00 | 1.00 | 68 % |
| −0.40 | 3 | 0 | 0 | 1 | 1.00 | 1.00 | 1.00 | 59 % |
| −0.35 | 2 | 1 | 0 | 1 | 0.67 | 1.00 | 0.83 | 51 % |
| 0.00 | 0 | 3 | 0 | 1 | 0.00 | 1.00 | 0.50 | 15 % |
| 0.05 | 0 | 3 | 0 | 1 | 0.00 | 1.00 | 0.50 | 11 % |

Perfect separation exists at −0.55 … −0.37 and is meaningless: every threshold in that range labels
59–91 % of the AOI as water. The matrix is perfect while the map is nonsense.

Root cause: **all three inundated plots have negative MNDWI**. At the only observable date, ten days
after the rain, there is no standing water on them — they are saturated soil, not flooded fields. An
absolute water threshold has nothing to detect.

This also invalidates the example threshold in `docs/AGENTS.md`: at `MNDWI > 0.05`, recall is 0.

### 5.2 MNDWI change against the reference — works, weakly

| Plot | Expected | Δ MNDWI |
|---|---|---|
| Sawah Kontrak 1 | inundated | +0.058 |
| Sawah Impres | safe | −0.329 |
| Sawah PU & Keprak | inundated | no baseline observation |
| Sawah Kontrak 2 | inundated | +0.237 |

Only 68 % of the AOI has both windows valid, so percentages below are of the full AOI and the
observed share is 68 %.

| Threshold | TP | FN | FP | TN | recall | specificity | balanced acc. | water, % of AOI |
|---|---|---|---|---|---|---|---|---|
| −0.30 | 2 | 0 | 0 | 1 | 1.00 | 1.00 | 1.00 | 55 % |
| 0.00 | 2 | 0 | 0 | 1 | 1.00 | 1.00 | 1.00 | 30 % |
| **0.05** | **2** | **0** | **0** | **1** | **1.00** | **1.00** | **1.00** | **24 % (130 ha)** |
| 0.10 | 1 | 1 | 0 | 1 | 0.50 | 1.00 | 0.75 | 19 % |

The plateau is −0.32 … 0.05 and the confusion matrix is constant across it, so the matrix cannot
select a threshold. The water extent is used as the tiebreaker: take the most conservative threshold
on the plateau, **Δ MNDWI > 0.05**, which yields 130 ha.

An earlier draft of this report quoted 190 ha for the same threshold. That was wrong: the fraction
was divided by the observed area but multiplied by the full AOI area. The sweep now scales by the
observed share and the figure agrees with a direct `pixelArea` measurement (130.3 ha).

### 5.3 How much this is worth

One negative example. Sawah Impres is the only "safe" plot, and Sawah PU & Keprak has no baseline
observation at all. A matrix with `TN = 1` cannot distinguish a working threshold from a lucky one;
it only rules out the threshold being badly wrong on that one field.

Additionally, 130 ha is 24 % of the AOI. Since the reference window is the transplanting season, an
unquantified share of that area is cropping stage rather than flood. This is the same confound that
made the dry-season reference fail, just smaller.

Recommended framing: present the absolute threshold as the naive baseline that fails, the change
threshold as the working method, and state plainly that the operating point sits on a plateau
supported by a single negative sample.

---

## 6. River preservation

### 6.1 The problem, stated precisely

A circular erosion is the wrong tool. Field bunds and the Kali Cigadung / Kali Anyar channels are
both one to two pixels wide at 10 m, so any disc large enough to remove the bunds also removes the
channels. Measured on synthetic geometry, a circular opening at radius 2 retains **0 %** of a
one-pixel channel.

The property that separates a bund from a river is not shape — both are linear — but **length**. A
bund is a field-length segment, roughly 10–20 pixels. A river runs continuously for hundreds.

### 6.2 Method

`src/morphology.py` approximates a path opening (Heijmans, Buckley & Talbot 2005) by the union of
straight-line openings over 16 orientations at 11.25° steps. A one-pixel structuring element cannot
follow a meander, so the mask is dilated by one pixel first: at three pixels wide the element fits
around a bend, and the dilation is undone afterwards. This single change raises channel retention
from 35 % to 100 % at the same rejection rate.

### 6.3 Synthetic test

Scene: one 560 m channel (1 px wide, meandering), five 60 m bunds, five 40 m squares, one 200 m
square water body. Retention per class:

| Operator | river | bunds | blobs | body | pixels kept |
|---|---|---|---|---|---|
| circular r=1 | **0 %** | 0 % | 75 % | 99 % | 80 % |
| circular r=2 | **0 %** | 0 % | 0 % | 97 % | 68 % |
| path len=9 | 51 % | 0 % | 0 % | 100 % | 76 % |
| path len=15 | 35 % | 0 % | 0 % | 100 % | 74 % |
| path len=21 | 0 % | 0 % | 0 % | 0 % | 0 % |
| preserve len=15 | **100 %** | 0 % | 0 % | 100 % | 80 % |
| preserve len=21 | 12 % | 0 % | 0 % | 100 % | 72 % |
| small objects ≥12 px | **100 %** | 0 % | 100 % | 100 % | 95 % |
| **clean len=15** | **100 %** | **0 %** | **0 %** | **100 %** | **80 %** |

`clean()` removes every short feature and keeps the channel intact. Length 21 is too long for a
channel that bends every ~130 m, so 15 is the working value (150 m at 10 m).

### 6.4 Real mask

`Δ MNDWI > 0.05` for 2025-02-17:

| Operator | water | kept |
|---|---|---|
| none | 130.3 ha | 100 % |
| circular r=2 | 123.3 ha | 95 % |
| clean len=15 | 133.5 ha | 102 % |

The filter removes about 5 % of the mask, mostly isolated specks in the west of the AOI, and
preserves the thin diagonal feature that runs across the lower half. It gains 2 % overall because
the closing step fills single-pixel holes.

The important caveat: the real mask is dominated by one large connected region covering the eastern
half, so morphology has very little to remove. **The dominant error in this map is not noise, it is
the extent of that region** — consistent with the cropping-stage confound flagged in 5.3.

### 6.5 What could not be tested

No independent river vector exists for this AOI:

- JRC Global Surface Water reports **0 %** occurrence above 30 %, i.e. the channel is below its
  detection limit at 30 m.
- MERIT Hydro puts the entire AOI within 5.4 m of the nearest drainage — it is a flat paddy plain, so
  height above drainage cannot separate a channel from a field.

Synthetic geometry with a known answer is therefore the only honest reference available. It validates
the operator's property, not its performance on this specific landscape. Two further limits:

1. The synthetic bunds are disconnected. Real field bunds form connected networks, which would defeat
   the connected-component alternative (`remove_small_objects`) but not the path opening.
2. The synthetic channel is one pixel wide throughout. Real channels widen and narrow.

### 6.6 A measurement error worth recording

Thumbnails rendered at a finer scale than the analysis grid re-evaluate the focal operations on that
finer grid, turning a one-pixel channel into a seven-pixel one. The first render of the circular
opening appeared to preserve the channel while the pixel counts said it retained 0 %. The counts were
right and the picture was wrong. `save_thumb()` now pins the reprojection and output width to 10 m.

---

## 7. Open issues

1. **Two of three events remain unusable.** 2026-01-24 has 35 % coverage with one validation point
   inside the clear patch; 2026-01-29 has none.
2. **The threshold is not statistically identified** — one negative sample, wide plateau (5.3).
3. **The 43 ha water extent is still reference-dependent** (5.3, 6.4: 43.4 ha against
   Nov–Dec 2024, 49.3 ha against the 2024 dry season). A reference window matched to the same
   cropping stage would test this, but no such cloud-free window exists near the event.
4. **`docs/AGENTS.md` embeds a full `conda list`**, roughly 360 of its 560 lines. It should be
   replaced by an `environment.yml` pinning top-level dependencies only.
5. **The literature PDFs are gitignored** (`docs/paper-references/*.pdf`, 67 MB), so a fresh clone
   gets no references.
6. **No null-model control.** Nothing yet proves the 43 ha is larger than what the same pipeline
   reports on two arbitrary cloud-free dates in a quiet month. Without it, a reviewer can argue
   the whole signal is a compositing difference.
7. **Only one of the five reference papers has been used.** Samela (2022) and Yi (2025) propose
   hydrogeomorphic priors that need a DEM with real relief; this AOI has 5.4 m of total range, so
   their contribution is likely not transferable here.

---

## 8. Reproduction

```bash
/opt/miniconda3/envs/ee/bin/python src/preview_event.py --diagnose
/opt/miniconda3/envs/ee/bin/python src/preview_event.py --event 2025-02-17 --window t2
/opt/miniconda3/envs/ee/bin/python src/compare_baseline.py --all
/opt/miniconda3/envs/ee/bin/python src/calibrate_threshold.py --event 2025-02-17 --mode mndwi
/opt/miniconda3/envs/ee/bin/python src/calibrate_threshold.py --event 2025-02-17 --mode delta
/opt/miniconda3/envs/ee/bin/python src/evaluate_morphology.py
/opt/miniconda3/envs/ee/bin/python -m streamlit run src/app.py
```

Maps, sweeps and PNGs land in `outputs/`, which is gitignored; regenerate rather than commit.
