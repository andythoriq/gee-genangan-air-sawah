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

Per-scene measurement over all 345 acquisitions in 2025 confirms the mechanism: 61 % of scenes cover
less than 1 % of the AOI, 15 % cover 1–90 %, 23 % cover more than 90 %, median 0.00. At scene level the
distribution is bimodal — a single cloud cell closes the whole AOI, a single clear acquisition opens
it — which is why a monthly or windowed average hides how all-or-nothing the data really is.

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
| `pre_event_2025_02` (Nov–Dec 2024) | 5.6 ha | 13.9 ha | 15.5 ha | directionally correct |
| `dry_season_2024` (Jun–Aug 2024) | 19.0 ha | 18.2 ha | 67.0 ha | all inundated plots read *drier* |

The dry-season window is the dry-season cropping period, when the paddies are themselves irrigated.
67 ha of a 172 ha AOI flips to "receded", and every inundated plot is classified as drier than the
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

Additionally, 43 ha is 25 % of the AOI. Since the reference window is the transplanting season, an
unquantified share of that area is cropping stage rather than flood. This is the same confound that
made the dry-season reference fail, just smaller; section 7 puts a number on it.

Recommended framing: present the absolute threshold as the naive baseline that fails, the change
threshold as the working method, and state plainly that the operating point sits on a plateau
supported by a single negative sample.

### 5.4 Otsu as a second opinion

The weakest part of section 5 is that 0.05 is chosen from four plots. Otsu's method removes the
labels from that decision: it takes the same delta histogram and picks the split that maximises
between-class variance. `calibrate_threshold.otsu()` implements it on the 400-bin histogram already
computed for the sweep, and the app reports it under the confusion matrix.

On the flood window it returns **0.045**, which at 46 % of the observed intersection is **43.4 ha** —
the same operating point, reached without looking at a single field observation. That is the
strongest available answer to "why 0.05": two independent routes agree.

It is not, however, a detector. Run on windows with no flood:

| Window | Otsu threshold | Above it |
|---|---|---|
| Flood 2025-02-22 | +0.045 | 46 % |
| Quiet 2025-08-08 | +0.525 | 51 % |
| Quiet 2025-07-07 | +0.265 | 45 % |
| Quiet 2025-09-25 | −0.355 | 65 % |

The threshold moves wildly and the share stays between 45 % and 65 %. That is what maximising
between-class variance does to a unimodal distribution: it always splits the bulk near the middle, so
its output looks equally confident whether or not anything happened. The delta histogram here is
unimodal (mode at −0.015, long positive tail), so Otsu's two-class assumption does not hold.

Use it as corroboration of the operating point, never as a source of extent, and never to pick a
threshold in another window.

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
straight-line openings over 17 orientations at 11° steps. A one-pixel structuring element cannot
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

## 7. Null-model control: the flood estimate is not distinguishable from the season

Everything above compares a flood window to a reference window and reads the difference as
inundation. That inference has an untested premise: that ordinary windows produce *less* of this
difference. `src/null_model.py` tests it. It runs the identical chain - same masker, same
reference (`pre_event_2025_02`, Nov–Dec 2024), same threshold 0.05 - on 17 consecutive 16-day
windows from 2025-03-01 to 2025-11-30, a period with no reported flood, and reports what comes out.

| Window | Coverage | Water (ha) |
|---|---|---|
| 2025-03-01 | 55 % | 16.4 |
| 2025-04-18 | 55 % | 10.5 |
| 2025-05-04 | 55 % | 19.3 |
| 2025-05-20 | 55 % | 10.6 |
| 2025-06-05 | 55 % | 14.5 |
| 2025-06-21 | 55 % | 56.7 |
| 2025-07-07 | 55 % | 64.4 |
| 2025-07-23 | 55 % | 58.2 |
| **2025-08-08** | **55 %** | **88.7** |
| 2025-08-24 | 55 % | 41.3 |
| 2025-09-09 | 55 % | 3.2 |
| 2025-09-25 | 55 % | 1.4 |
| 2025-10-11 | 52 % | 22.9 |
| 2025-10-27 | 55 % | 2.5 |

Median **17.9 ha**, maximum **88.7 ha**. The flood window reports **43.4 ha**, which is above the
median but below the maximum: 10 of 14 quiet windows sit below it, four sit above.

The 88.7 ha is not a bug. August is land preparation for the second planting season: bare and
puddled soil has a higher MNDWI than the vegetated November–December reference, so the delta reads
the tillage cycle as water. Any window that crosses a cropping-stage boundary does the same thing.
With this reference, "43 ha of water" is a plausible ordinary value.

Three consequences:

1. **The 43 ha cannot be presented as flood extent.** It can be presented as a wetness anomaly
   relative to Nov–Dec 2024, which is a weaker and honest claim. Section 5's confusion matrix still
   holds - the four plots do separate at 0.05 - but separation at four points does not make the
   spatial extent specific to flooding.
2. **The comparison must be against the null distribution, not against zero.** Reporting "43 ha"
   next to "0 ha in the reference" is what made the number look strong. Reporting it next to a
   median of 17.9 ha and a maximum of 88.7 ha is what it actually is.
3. **The fix is a same-stage reference, not a better threshold.** No threshold separates flood from
   tillage here, because both raise MNDWI by the same mechanism. What separates them is the
   reference window: compare February against a February, not against November.

Two limits of this control, stated so it is not over-read:

- The quiet windows all sit *after* the event, because January and the months before it are
  unusable. A control drawn from the same season one year earlier would be stronger.
- All windows share the 55 % reference footprint, so the comparison is like-for-like in area, but
  it also means the control inherits whatever bias that footprint has.

### 7.1 Compositing order does not explain it

Section 7 leaves three possible causes for the 88 ha: the reference window, the threshold, or the way
the composite is built. The threshold is already ruled out (section 7, consequence 3: flood and
tillage raise MNDWI by the same mechanism, so no threshold separates them). This section rules out the
third.

The question is *when* the index is computed. The default pipeline medians the reflectance and then
indexes the median (index-of-median). The alternative indexes each scene first and then medians the
scores (median-of-index), which is more robust where scenes disagree — the order used by script 1 of
the original GEE notebook, and the one a reviewer is most likely to ask about.
`sentinel.composite_index()` implements it and `null_model.py --order` runs the whole scan either way,
measuring the flood window in the same order rather than comparing against a number produced by the
other one.

Both runs use the same 17 windows, the same reference (`pre_event_2025_02`), the same masker, the
same threshold, and the same 55 % reference footprint, so the rows are paired:

| Window | index-of-median | median-of-index | Δ |
|---|---|---|---|
| 2025-03-01 | 16.4 | 13.4 | −3.0 |
| 2025-04-18 | 10.5 | 6.9 | −3.6 |
| 2025-05-04 | 19.3 | 17.5 | −1.8 |
| 2025-05-20 | 10.6 | 13.2 | +2.6 |
| 2025-06-05 | 14.5 | 13.9 | −0.6 |
| 2025-06-21 | 56.7 | 56.6 | −0.1 |
| 2025-07-07 | 64.4 | 63.7 | −0.7 |
| 2025-07-23 | 58.2 | 59.4 | +1.2 |
| 2025-08-08 | 88.7 | 87.9 | −0.8 |
| 2025-08-24 | 41.3 | 41.2 | −0.1 |
| 2025-09-09 | 3.2 | 3.5 | +0.3 |
| 2025-09-25 | 1.4 | 2.0 | +0.6 |
| 2025-10-11 | 22.9 | 19.9 | −3.0 |
| 2025-10-27 | 2.5 | 2.5 | 0.0 |
| **Median** | **17.9** | **15.7** | **−2.2** |
| **Maximum** | **88.7** | **87.9** | **−0.8** |
| **Flood window 2025-02-22..03-04** | **43.4** | **43.7** | **+0.3** |
| **Quiet windows below the flood** | **10 / 14** | **10 / 14** | **—** |

Mean absolute change per window: **1.3 ha**. The largest is 3.6 ha, on a window that reports about
10 ha.
Every window above 50 ha — the ones that make the null distribution look alarming — moves by at most
1.2 ha. The order lowers the floor by 2.2 ha (12 %) and leaves the conclusion exactly where it was:
the flood value sits inside the quiet distribution either way, at the same rank.

That is the useful part of the result. It removes a methodological objection without changing the
finding. The seasonal signal is in the data, not in the order of operations, which leaves the
reference window as the only remaining cause.

What this does **not** show: that index-of-median is wrong. Median-of-index is still the more robust
choice at cloud edges, and nothing here measures that. The two orders agree so closely here because
the observed footprint is clear in nearly every scene of these windows; where scenes disagree, the
orders would diverge more. The test rules
the order out as the cause of the null-model result; it does not rank the two implementations.

Reproduce:

```bash
/opt/miniconda3/envs/ee/bin/python src/null_model.py --order index-of-median \
    --flood-start 2025-02-22 --flood-end 2025-03-04
/opt/miniconda3/envs/ee/bin/python src/null_model.py --order median-of-index \
    --flood-start 2025-02-22 --flood-end 2025-03-04
```

---

## 8. Open issues

1. **Two of three events remain unusable.** 2026-01-24 has 35 % coverage with one validation point
   inside the clear patch; 2026-01-29 has none.
2. **The threshold is not statistically identified** — one negative sample, wide plateau (5.3).
3. **The 43 ha water extent is still reference-dependent** (5.3, 6.4: 43.4 ha against
   Nov–Dec 2024, 49.3 ha against the 2024 dry season). A reference window matched to the same
   cropping stage would test this, but no such cloud-free window exists near the event.
4. **The literature PDFs are gitignored** (`docs/paper-references/*.pdf`, 67 MB), so a fresh clone
   gets no references.
5. **The null model says the flood estimate is ordinary** (section 7). This is the largest open
   problem in the project: the spatial extent cannot be defended until a same-stage reference
   window exists. Options are a February reference from an earlier year, or a different data
   source entirely.
6. **Only one of the five reference papers has been used.** Samela (2022) and Yi (2025) propose
   hydrogeomorphic priors that need a DEM with real relief; this AOI has 5.4 m of total range, so
   their contribution is likely not transferable here.

---

## 9. Reproduction

```bash
/opt/miniconda3/envs/ee/bin/python src/preview_event.py --diagnose
/opt/miniconda3/envs/ee/bin/python src/preview_event.py --event 2025-02-17 --window t2
/opt/miniconda3/envs/ee/bin/python src/compare_baseline.py --all
/opt/miniconda3/envs/ee/bin/python src/calibrate_threshold.py --event 2025-02-17 --mode mndwi
/opt/miniconda3/envs/ee/bin/python src/calibrate_threshold.py --event 2025-02-17 --mode delta
/opt/miniconda3/envs/ee/bin/python src/evaluate_morphology.py
/opt/miniconda3/envs/ee/bin/python src/null_model.py --flood-ha 43.4 --csv
/opt/miniconda3/envs/ee/bin/python -m streamlit run src/app.py
```

Maps, sweeps and PNGs land in `outputs/`, which is gitignored; regenerate rather than commit.
