"""Streamlit dashboard for independent exploration of the flood analysis.

Run with:
    /opt/miniconda3/envs/ee/bin/streamlit run src/app.py

The ee environment is declared in environment.yml at the repository root.

Design note: every widget change costs one or more Earth Engine round trips, so
nothing is computed until the "Hitung" button is pressed, and the whole result
is then held in session state. Moving between tabs re-renders without touching
the server.
"""

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import calibrate_threshold as cal
import config
import indices
import morphology
import null_model
import runs
import sentinel

st.set_page_config(page_title="Deteksi Genangan Sawah", layout="wide")

TOOLTIPS = {
    "referensi": (
        "Periode pembanding yang dianggap kondisi normal, sebelum kejadian. Karena tidak "
        "ada citra bebas awan saat puncak banjir, yang dibandingkan bukan 'sebelum vs saat "
        "banjir' melainkan 'kondisi saat kejadian vs kondisi di periode referensi'. Nilai "
        "MNDWI tiap piksel dikurangkan; selisih positif berarti piksel itu lebih basah."
    ),
    "titik": (
        "Nilai indeks di setiap sawah validasi. Kolom Prediksi membandingkan nilai itu "
        "dengan ambang yang sedang dipakai, jadi isinya sama dengan sel-sel confusion "
        "matrix di tab Kalibrasi."
    ),
    "peta": (
        "Ikon di kanan atas peta dipakai untuk berpindah antara basemap jalan dan citra "
        "satelit Esri, serta menyalakan/mematikan layer hasil analisis. Titik kuning "
        "adalah sawah validasi; Sawah Impres berada di luar poligon AOI."
    ),
    "kalibrasi": (
        "Confusion matrix membandingkan prediksi dengan kenyataan lapangan: TP tergenang "
        "dan diprediksi air, FN tergenang tapi diprediksi kering, FP aman tapi diprediksi "
        "air, TN aman dan diprediksi kering. Sapuan ambang mencoba 121 nilai dari -0.60 "
        "sampai 0.60. Plateau adalah rentang ambang yang menghasilkan matrix identik, "
        "sehingga di dalamnya matrix tidak bisa memilih dan luas air dipakai sebagai "
        "penentu."
    ),
    "null": (
        "Kontrol: pipeline yang sama dijalankan pada jendela-jendela yang tidak ada "
        "banjir, dengan referensi dan ambang yang sama. Hasilnya adalah lantai - "
        "berapa hektar 'air' yang tetap muncul saat tidak terjadi apa-apa. Angka "
        "banjir hanya berarti kalau berada di atas sebaran ini."
    ),
    "morfologi": (
        "Uji pada gambar sintetis dengan jawaban yang sudah diketahui: satu kanal panjang, "
        "lima bund pendek, lima blok kecil. Dipakai karena di citra asli tidak ada acuan "
        "bentuk sungai yang bisa dijadikan patokan."
    ),
    "cakupan": (
        "Persentase AOI yang benar-benar punya piksel bebas awan di setiap jendela waktu. "
        "Ini gerbang pertama: kalau 0 persen, jendela itu tidak bisa dianalisis sama sekali."
    ),
    "kalender": (
        "Cakupan per bulan sepanjang arsip, dihitung dalam satu permintaan ke Earth Engine. "
        "Pakai ini untuk memilih jendela referensi berdasarkan bukti, bukan tebakan: cari "
        "bulan dengan batang tinggi yang posisinya dekat dengan kejadian. Perhatikan bahwa "
        "Januari hampir selalu nol di lokasi ini."
    ),
    "simpan": (
        "Menyimpan parameter, nilai titik validasi, sapuan ambang dan ringkasan markdown "
        "ke outputs/runs/. Isi outputs/ sepenuhnya bisa dibuat ulang, kecuali folder runs "
        "yang menyimpan catatan analisis Anda."
    ),
}


@st.cache_resource
def boot():
    sentinel.init()
    return True


def area_ha(mask=None):
    """Area in hectares, optionally restricted to a boolean mask."""
    import ee

    image = ee.Image.pixelArea()
    if mask is not None:
        image = image.updateMask(mask)
    return (image.reduceRegion(
        ee.Reducer.sum(), sentinel.aoi(), 10, maxPixels=int(1e9), bestEffort=True
    ).get("area").getInfo() or 0.0) / 10000.0


def tile_url(image, vis):
    return image.getMapId(vis)["tile_fetcher"].url_format


@st.cache_data(ttl=3600, show_spinner="Menyiapkan citra mentah...")
def raw_preview(start, end):
    """Unmasked true-colour composite for windows where masking leaves nothing.

    The point is not analysis, it is orientation: when a window is fully
    clouded the analyst still needs to see the AOI, the points and what the
    clouds actually look like, instead of a blank map.
    """
    image = sentinel.composite(start, end, mode="none", clip=True)
    vis = {"bands": [config.RED, config.GREEN, "B2"], "min": 0, "max": 3000}
    return tile_url(image, vis)


def compute(event_start, event_end, base_start, base_end, mode, mask_mode,
            threshold, clean_length, run_label):
    import ee

    geom = sentinel.aoi()

    # Unclipped so validation points outside the AOI are still sampled; map
    # layers are clipped explicitly further down.
    event_composite = sentinel.composite(event_start, event_end, mode=mask_mode,
                                         geom=geom, clip=False)

    if mode == "delta":
        base_composite = sentinel.composite(base_start, base_end, mode=mask_mode,
                                            geom=geom, clip=False)
        layer = indices.mndwi(event_composite).subtract(indices.mndwi(base_composite))
        layer_label = "MNDWI delta"
        base_window = "%s..%s" % (base_start, base_end)
    else:
        base_composite = None
        layer = indices.mndwi(event_composite)
        layer_label = "MNDWI"
        base_window = None

    observed = sentinel.coverage(layer).getInfo() or 0.0
    event_coverage = sentinel.coverage(event_composite).getInfo() or 0.0
    base_coverage = (sentinel.coverage(base_composite).getInfo() or 0.0
                     if base_composite is not None else None)
    points = cal.sample_points(layer)
    hist = cal.histogram(layer, mode, geom)
    total_ha = area_ha()

    # Label-free second opinion on where the distribution splits. Reported for
    # comparison only; the analysis keeps using the calibrated threshold.
    otsu_threshold = cal.otsu(hist)
    otsu_share = (cal.water_fraction(hist, otsu_threshold) * observed
                  if otsu_threshold is not None else None)

    # Recorded per point so the table can show that Sawah Impres sits outside
    # the polygon even though it is still sampled.
    for point in points:
        lonlat = config.VALIDATION_POINTS[point["name"]]["lonlat"]
        point["inside_aoi"] = geom.contains(ee.Geometry.Point(lonlat)).getInfo()

    sweep = []
    for value in cal.THRESHOLDS:
        metrics = cal.score(points, value)
        fraction = cal.water_fraction(hist, value) * observed
        sweep.append({
            "threshold": value,
            "tp": metrics["tp"], "fn": metrics["fn"],
            "fp": metrics["fp"], "tn": metrics["tn"],
            "recall": metrics["recall"], "specificity": metrics["specificity"],
            "balanced": metrics["balanced"],
            "water_pct": 100 * fraction,
            "water_ha": fraction * total_ha,
        })

    water = layer.gt(threshold).selfMask()
    cleaned = (morphology.clean(layer.gt(threshold), clean_length).selfMask()
               if clean_length else None)

    vis_mndwi = {"min": -0.6, "max": 0.6, "palette": ["8c510a", "f5f5f5", "2b83ba"]}
    vis_water = {"palette": ["08306b"]}
    vis_clean = {"palette": ["41b6c4"]}
    vis_tc = {"bands": [config.RED, config.GREEN, "B2"], "min": 0, "max": 3000}

    layers = {"Citra true colour": tile_url(event_composite.clip(geom), vis_tc),
              layer_label: tile_url(layer.clip(geom), vis_mndwi),
              "Air (ambang)": tile_url(water.clip(geom), vis_water)}
    if cleaned is not None:
        layers["Air (setelah morfologi)"] = tile_url(cleaned.clip(geom), vis_clean)

    thumb = water.clip(geom).getThumbURL({
        "palette": ["ffffff", "08306b"], "region": geom,
        "dimensions": 512, "format": "png"})

    return {
        "label": run_label, "layer_label": layer_label,
        "mode": mode, "mask_mode": mask_mode, "threshold": threshold,
        "clean_length": clean_length,
        "observed": observed, "total_ha": total_ha,
        "event_coverage": event_coverage, "base_coverage": base_coverage,
        "points": points, "sweep": sweep,
        "otsu": None if otsu_threshold is None else {
            "threshold": otsu_threshold,
            "water_pct": 100 * otsu_share,
            "water_ha": otsu_share * total_ha,
            # Share of the observed intersection, which is what Otsu actually
            # splits. The AOI figure is smaller because clouds are excluded.
            "observed_pct": 100 * otsu_share / observed if observed else None,
        },
        "raw_ha": area_ha(water),
        "clean_ha": area_ha(cleaned) if cleaned is not None else None,
        "layers": layers, "thumb_url": thumb,
        "event_window": "%s..%s" % (event_start, event_end),
        "event_start": event_start, "event_end": event_end,
        "base_start": base_start, "base_end": base_end,
        "base_window": base_window,
    }


def sidebar():
    with st.sidebar:
        st.header("Konfigurasi")
        source = st.radio("Sumber tanggal", ["Preset", "Manual"], horizontal=True,
                          help="Preset memakai tanggal dari src/config.py. Manual "
                               "membebaskan rentang, tapi tidak ada penanda event.")

        valid = True
        if source == "Preset":
            event = st.selectbox("Event banjir", sorted(config.EVENTS), index=0)
            window = st.radio("Jendela", ["t2", "t1"], horizontal=True,
                              help="t1 = puncak banjir, t2 = resesi. t1 selalu 0 persen cakupan.")
            baseline = st.selectbox("Jendela referensi", sorted(config.BASELINES),
                                    index=sorted(config.BASELINES).index(
                                        config.EVENTS[event]["baseline"]),
                                    help="Periode pembanding normal.")
            event_start, event_end = config.EVENTS[event][window]
            base_start, base_end = config.BASELINES[baseline]
            run_label = "%s-%s" % (event, window)
        else:
            st.caption("Rentang bebas. Cakupan tetap dihitung dan bisa nol.")
            for key, fallback in (("ev_start", dt.date(2025, 2, 22)),
                                  ("ev_end", dt.date(2025, 3, 4)),
                                  ("ref_start", dt.date(2024, 11, 1)),
                                  ("ref_end", dt.date(2024, 12, 31))):
                if key not in st.session_state:
                    st.session_state[key] = fallback
            event_start = st.date_input("Awal jendela kejadian", key="ev_start")
            event_end = st.date_input("Akhir jendela kejadian", key="ev_end")
            base_start = st.date_input("Awal jendela referensi", key="ref_start")
            base_end = st.date_input("Akhir jendela referensi", key="ref_end")
            baseline = None
            run_label = "manual"

        mode = st.radio("Besaran", ["delta", "mndwi"], horizontal=True,
                        help="delta = selisih terhadap jendela referensi; mndwi = nilai absolut.")
        mask_mode = st.radio("Masker awan", ["scl", "qa60", "strict"], horizontal=True,
                             help="qa60 membuang hampir semua piksel di AOI ini.")
        threshold = st.slider("Ambang", -0.60, 0.60,
                              config.CALIBRATED_DELTA_THRESHOLD, 0.01)

        with st.expander("Morfologi", expanded=False):
            use_morph = st.checkbox("Terapkan pembersihan", value=True)
            clean_length = st.slider("Panjang minimum (piksel)", 5, 31, 15, 2,
                                     help="Harus ganjil: structuring element berupa garis "
                                          "butuh satu piksel pusat, jadi kernel genap tidak "
                                          "bisa dipusatkan. Pada 10 m, 15 piksel = 150 m.")

        event_start = event_start.isoformat() if hasattr(event_start, "isoformat") else event_start
        event_end = event_end.isoformat() if hasattr(event_end, "isoformat") else event_end
        base_start = base_start.isoformat() if hasattr(base_start, "isoformat") else base_start
        base_end = base_end.isoformat() if hasattr(base_end, "isoformat") else base_end

        if event_start >= event_end:
            st.error("Awal jendela kejadian harus sebelum akhirnya.")
            valid = False
        if mode == "delta" and base_start >= base_end:
            st.error("Awal jendela referensi harus sebelum akhirnya.")
            valid = False

        if mode == "delta" and base_end <= event_start:
            gap = (dt.date.fromisoformat(event_start)
                   - dt.date.fromisoformat(base_end)).days
            st.caption("Jarak referensi ke jendela kejadian: %d hari" % gap)
            if gap < 14:
                st.warning("Jarak di bawah 14 hari. Selisihnya bisa didominasi noise, "
                           "bukan genangan.")
        elif mode == "delta" and base_start >= event_end:
            gap = (dt.date.fromisoformat(base_start)
                   - dt.date.fromisoformat(event_end)).days
            st.caption("Referensi berada %d hari setelah jendela kejadian." % gap)
        elif mode == "delta":
            st.error("Jendela referensi beririsan dengan jendela kejadian. "
                     "Selisihnya tidak akan mengukur apa pun.")
            valid = False

        st.divider()
        run = st.button("Hitung", type="primary", width="stretch", disabled=not valid)
        if st.button("Hapus hasil", width="stretch"):
            st.session_state.pop("result", None)

    return dict(event_start=event_start, event_end=event_end,
                base_start=base_start, base_end=base_end, mode=mode,
                mask_mode=mask_mode, threshold=threshold,
                clean_length=clean_length if use_morph else 0,
                run_label=run_label), run


def render_points(result):
    st.subheader("Titik validasi", help=TOOLTIPS["titik"])
    rows = []
    for point in result["points"]:
        value = point["value"]
        if value is None:
            predicted = "tidak ada data"
        elif value > result["threshold"]:
            predicted = "air"
        else:
            predicted = "kering"
        rows.append({
            "Titik": point["name"],
            "Harapan": point["expected"],
            result["layer_label"]: None if value is None else round(value, 3),
            "Prediksi": predicted,
            "Di AOI": "ya" if point.get("inside_aoi") else "tidak",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

def render_status(result):
    columns = st.columns(4)
    columns[0].metric("Cakupan AOI", "%.0f%%" % (100 * result["observed"]))
    columns[1].metric("Luas AOI", "%.1f ha" % result["total_ha"])
    columns[2].metric("Air mentah", "%.1f ha" % result["raw_ha"])
    if result["clean_ha"] is not None:
        columns[3].metric("Setelah morfologi", "%.1f ha" % result["clean_ha"],
                          delta="%+.1f ha" % (result["clean_ha"] - result["raw_ha"]))

    st.caption("%s · jendela %s · %s · masker %s · ambang %.2f"
               % (result["label"], result["event_window"], result["layer_label"],
                  result["mask_mode"], result["threshold"]))
    if result["base_window"]:
        st.caption("Referensi: %s" % result["base_window"])

    event_cov = result["event_coverage"]
    base_cov = result["base_coverage"]
    breakdown = "Cakupan jendela kejadian %.0f%%" % (100 * event_cov)
    if base_cov is not None:
        breakdown += " · referensi %.0f%% · irisan %.0f%%" % (
            100 * base_cov, 100 * result["observed"])
    st.caption(breakdown)

    if result["observed"] >= 0.5:
        return True

    # Say which window is actually empty. The three causes need different fixes.
    if event_cov < 0.05:
        st.error(
            "Jendela kejadian sendiri tidak punya piksel bebas awan (%.0f%%). "
            "Ini yang harus diganti dulu: pakai t2, atau pilih tanggal lain di tab "
            "Cakupan. Jendela referensi bukan penyebabnya." % (100 * event_cov))
    elif base_cov is not None and base_cov < 0.05:
        st.error(
            "Jendela referensi tidak punya piksel bebas awan (%.0f%%). Jendela "
            "kejadian sendiri baik (%.0f%%). Pilih bulan lain dari Kalender cakupan "
            "bulanan - hindari Januari." % (100 * base_cov, 100 * event_cov))
    elif result["observed"] < 0.05:
        st.error(
            "Kedua jendela punya data (kejadian %.0f%%, referensi %.0f%%) tapi hampir "
            "tidak ada piksel yang cerah di keduanya sekaligus. Area yang terlihat "
            "pada citra kejadian tertutup awan pada citra referensi, atau sebaliknya. "
            "Coba geser salah satu jendela." % (100 * event_cov, 100 * base_cov))
    else:
        st.warning(
            "Cakupan irisan hanya %.0f%% (kejadian %.0f%%, referensi %.0f%%). "
            "Angka luas mewakili sebagian AOI saja."
            % (100 * result["observed"], 100 * event_cov,
               100 * (base_cov if base_cov is not None else event_cov)))
    return result["observed"] >= 0.05


def render_map(result, ok):
    st.subheader("Peta", help=TOOLTIPS["peta"])
    lats = [p[1] for p in config.AOI_RING]
    lons = [p[0] for p in config.AOI_RING]
    fmap = folium.Map(location=[(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2],
                      zoom_start=15, tiles=None, control_scale=True)
    def osm():
        return folium.TileLayer("OpenStreetMap", name="Jalan (OSM)")

    def esri():
        return folium.TileLayer(
            tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
                   "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
            attr="Esri, Maxar, Earthstar Geographics",
            name="Satelit (Esri)", overlay=False, control=True)

    # Folium shows the first base layer added. When the window has no usable
    # pixels the satellite basemap is the only thing that can orient the
    # reader, so it goes first.
    for make in ([esri, osm] if not ok else [osm, esri]):
        make().add_to(fmap)
    if ok:
        for name, url in result["layers"].items():
            folium.raster_layers.TileLayer(tiles=url, attr="Google Earth Engine",
                                           name=name, overlay=True,
                                           control=True).add_to(fmap)
    else:
        # Nothing survived the mask, so the analysed layers would be blank.
        # Offer the window as it is, but off by default: at 0% coverage it is
        # a wall of cloud that would hide the basemap underneath.
        try:
            preview = raw_preview(result["event_start"], result["event_end"])
        except Exception:
            # The basemap, AOI and points are the point of this branch; a
            # failed preview must not take them down with it.
            preview = None
        if preview:
            folium.raster_layers.TileLayer(
                tiles=preview, attr="Google Earth Engine",
                name="Citra mentah (tanpa masker)",
                overlay=True, control=True, show=False).add_to(fmap)
    folium.Polygon([(p[1], p[0]) for p in config.AOI_RING],
                   color="red", weight=2, fill=False, name="AOI").add_to(fmap)
    for name, spec in config.VALIDATION_POINTS.items():
        folium.CircleMarker([spec["lonlat"][1], spec["lonlat"][0]], radius=5,
                            color="yellow", fill=True, tooltip=name).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    st_folium(fmap, height=560, use_container_width=True)
    st.caption("Titik kuning = validasi lapangan. Sawah Impres berada di luar poligon AOI.")
    if not ok:
        st.warning(
            "Layer MNDWI tidak digambar karena jendela ini hampir tidak punya piksel "
            "bebas awan. Peta tetap menampilkan basemap satelit, batas AOI dan titik "
            "validasi. Layer **Citra mentah (tanpa masker)** bisa dinyalakan dari "
            "kontrol layer di kanan atas: isinya hampir seluruhnya awan, dan itulah "
            "sebabnya cakupan 0%. Luas air tidak bisa diukur dari peta ini.")


def render_calibration(result):
    df = pd.DataFrame(result["sweep"])
    scored = df[df["balanced"].notna()]
    if scored.empty:
        st.info("Tidak ada titik validasi dengan data di jendela ini.")
        return

    best = scored["balanced"].max()
    plateau = scored[scored["balanced"] == best]
    low, high = plateau["threshold"].min(), plateau["threshold"].max()

    st.subheader("Confusion matrix pada ambang %.2f" % result["threshold"],
                 help=TOOLTIPS["kalibrasi"])
    row = scored.iloc[(scored["threshold"] - result["threshold"]).abs().idxmin()]
    left, right = st.columns([1, 2])
    with left:
        st.dataframe(pd.DataFrame(
            [[int(row.tp), int(row.fn)], [int(row.fp), int(row.tn)]],
            columns=["prediksi air", "prediksi kering"],
            index=["tergenang", "aman"]), width="stretch")
        st.caption("balanced accuracy %.2f · air %.0f ha (%.0f%% AOI)"
                   % (row.balanced, row.water_ha, row.water_pct))
    with right:
        st.markdown(
            "**Plateau: %.2f s/d %.2f** (balanced accuracy %.2f). "
            "Di dalam rentang ini confusion matrix identik, jadi matrix tidak bisa "
            "memilih ambang - luas air dipakai sebagai penentu." % (low, high, best))
        st.warning(
            "Ambang di dalam plateau bersifat sembarang. Dengan satu titik kontrol, "
            "matrix ini tidak membuktikan ambangnya benar, hanya membuktikan ambangnya "
            "tidak salah pada satu sawah. Jangan memilih ambang dari tabel ini saja.")

    otsu = result.get("otsu")
    if otsu:
        gap = abs(otsu["threshold"] - result["threshold"])
        if gap <= 0.02:
            verdict = ("Otsu tidak memakai titik lapangan sama sekali, dan hasilnya "
                       "berdekatan dengan %.2f - jadi pilihan ambang tidak "
                       "bergantung pada satu metode." % result["threshold"])
        else:
            verdict = ("Selisihnya %.2f dari ambang yang dipakai, jadi keduanya "
                       "tidak saling mendukung dan selisih itu perlu dijelaskan, "
                       "bukan diabaikan." % gap)
        st.caption(
            "Pembanding Otsu pada histogram yang sama: ambang **%.3f**, air %.1f ha "
            "(%.0f%% AOI, %.0f%% dari irisan teramati). %s Angka ini tidak dipakai "
            "untuk analisis: pada jendela tanpa banjir Otsu tetap membagi 45-65%% "
            "area teramati sebagai air."
            % (otsu["threshold"], otsu["water_ha"], otsu["water_pct"],
               otsu["observed_pct"], verdict))

    st.subheader("Sapuan ambang", help=TOOLTIPS["kalibrasi"])
    show = scored.copy()
    show["threshold"] = show["threshold"].round(2)
    st.dataframe(
        show[["threshold", "tp", "fn", "fp", "tn", "recall", "specificity",
              "balanced", "water_ha", "water_pct"]].round(3),
        hide_index=True, width="stretch", height=320)

    chart = scored.set_index("threshold")[["balanced"]].copy()
    chart["air (ternormalisasi)"] = (scored.set_index("threshold")["water_ha"]
                                     / scored["water_ha"].max())
    st.line_chart(chart, height=220)

    st.divider()
    render_null_model(result)


@st.cache_data(ttl=3600, show_spinner="Menghitung kontrol null-model...")
def null_frame(base_start, base_end, threshold, mask_mode):
    """Same pipeline on windows with no reported flood, using the same reference."""
    rows, base_coverage = null_model.run("2025-03-01", "2025-11-30",
                                         base_start, base_end, threshold,
                                         mask_mode, min_coverage=0.9)
    return pd.DataFrame(rows), base_coverage


def render_null_model(result):
    st.subheader("Kontrol null-model", help=TOOLTIPS["null"])
    st.caption("Jendela 16 hari sepanjang Mar-Nov 2025 dijalankan dengan referensi "
               "dan ambang yang sama. Tidak ada banjir yang dilaporkan pada rentang "
               "itu, jadi apa pun yang muncul di sini adalah lantai metode, bukan "
               "genangan.")

    if st.button("Hitung lantai", key="null_run"):
        st.session_state["null_result"] = null_frame(
            result["base_start"], result["base_end"], result["threshold"],
            result["mask_mode"])

    stored = st.session_state.get("null_result")
    if stored is None:
        return

    frame, base_coverage = stored
    usable = frame[frame["water_ha"].notna()]
    if usable.empty:
        st.warning("Tidak ada jendela tenang yang cukup teramati. Cakupan referensi "
                   "hanya %.0f%% AOI, jadi jendela yang lolos sangat sedikit."
                   % (100 * base_coverage))
        return

    flood = result["raw_ha"]
    median = usable["water_ha"].median()
    worst = usable["water_ha"].max()
    below = int((usable["water_ha"] < flood).sum())

    columns = st.columns(3)
    columns[0].metric("Median jendela tenang", "%.1f ha" % median)
    columns[1].metric("Maksimum jendela tenang", "%.1f ha" % worst)
    columns[2].metric("Jendela banjir", "%.1f ha" % flood,
                      delta="%+.1f ha dari median" % (flood - median))
    st.caption("%d dari %d jendela tenang berada di bawah angka banjir. Referensi "
               "menutup %.0f%% AOI, jadi semua angka dihitung pada irisan yang sama."
               % (below, len(usable), 100 * base_coverage))

    if flood > worst:
        st.success("Angka banjir berada di atas semua jendela tenang. Inilah bukti "
                   "yang sebelumnya tidak ada: sinyalnya tidak bisa dijelaskan oleh "
                   "variasi musiman saja.")
    elif flood > median:
        st.warning("Angka banjir di atas median jendela tenang tapi masih di dalam "
                   "rentangnya. Sebagian dari angka itu bisa berasal dari perubahan "
                   "fase tanam, bukan genangan. Bandingkan dengan maksimum, bukan "
                   "dengan nol.")
    else:
        st.error("Angka banjir tidak lebih tinggi dari jendela tanpa banjir. Dengan "
                 "referensi ini, metode belum bisa membedakan genangan dari perubahan "
                 "fase tanam. Ganti referensi ke fase tanam yang sama sebelum angka "
                 "ini dipakai.")

    show = frame.rename(columns={"start": "Mulai", "end": "Selesai"})
    show["Cakupan"] = 100 * show["coverage"]
    show["Air (ha)"] = show["water_ha"]
    st.dataframe(show[["Mulai", "Selesai", "Cakupan", "Air (ha)"]].round(1),
                 hide_index=True, width="stretch", height=300)


def render_morphology(result):
    st.subheader("Uji geometri sintetis", help=TOOLTIPS["morfologi"])
    st.caption("Kanal 560 m selebar 1 piksel, lima bund 60 m, lima blok 40 m, "
               "satu badan air 200 m.")
    if st.button("Jalankan uji morfologi", key="morph_run"):
        import ee
        import evaluate_morphology as em

        layers = em.synthetic_layers()
        combined = ee.ImageCollection(list(layers.values())).max()
        variants = [
            ("circular r=2", lambda m: morphology.open_circular(m, 2)),
            ("path len=15", lambda m: morphology.path_open(m, 15)),
            ("clean len=%d" % (result["clean_length"] or 15),
             lambda m: morphology.clean(m, result["clean_length"] or 15)),
        ]
        rows = []
        for label, operator in variants:
            filtered = operator(combined)
            rows.append({
                "Operator": label,
                "Kanal": "%.0f%%" % (100 * em.retention(layers["river"], filtered)),
                "Bund": "%.0f%%" % (100 * em.retention(layers["bunds"], filtered)),
                "Blok": "%.0f%%" % (100 * em.retention(layers["blobs"], filtered)),
                "Badan air": "%.0f%%" % (100 * em.retention(layers["body"], filtered)),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.divider()
    st.subheader("Efek pada citra nyata")
    st.metric("Air mentah", "%.1f ha" % result["raw_ha"])
    if result["clean_ha"] is not None:
        st.metric("Setelah morfologi", "%.1f ha" % result["clean_ha"],
                  delta="%+.1f ha" % (result["clean_ha"] - result["raw_ha"]))


@st.cache_data(ttl=3600, show_spinner="Menghitung cakupan...")
def coverage_frame():
    """Cached because Streamlit executes every tab body on each rerun."""
    rows = []
    for event, windows in config.EVENTS.items():
        for name in ("t1", "t2"):
            start, end = windows[name]
            composite = sentinel.composite(start, end)
            rows.append({
                "Event": event, "Jendela": name, "Rentang": "%s..%s" % (start, end),
                "Scene": sentinel.scene_count(start, end).getInfo(),
                "Cakupan": "%.0f%%" % (100 * (sentinel.coverage(composite).getInfo() or 0)),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner="Memindai cakupan bulanan...")
def monthly_frame():
    rows = sentinel.monthly_coverage("2024-01-01", "2026-11-01").getInfo()["features"]
    return pd.DataFrame([
        {"Bulan": f["properties"]["month"],
         "Scene": f["properties"]["scenes"],
         "Cakupan": 100 * (f["properties"].get("coverage") or 0)}
        for f in rows
    ])


def apply_month(month):
    """Callback: copy a chosen month into the manual reference inputs."""
    start = dt.date.fromisoformat(month + "-01")
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    st.session_state["ref_start"] = start
    st.session_state["ref_end"] = end - dt.timedelta(days=1)


def render_coverage():
    st.subheader("Cakupan per event", help=TOOLTIPS["cakupan"])
    st.dataframe(coverage_frame(), hide_index=True, width="stretch")
    st.caption("t1 selalu 0 persen: tidak ada piksel bebas awan pada atau dekat "
               "tanggal banjir.")

    st.divider()
    st.subheader("Kalender cakupan bulanan", help=TOOLTIPS["kalender"])
    months = monthly_frame()
    st.bar_chart(months.set_index("Bulan")["Cakupan"], height=240, color="#2b83ba")
    st.dataframe(months.round(0), hide_index=True, width="stretch", height=200)

    pick = st.selectbox("Ambil satu bulan sebagai jendela referensi",
                        months["Bulan"], key="month_pick")
    st.button("Pakai sebagai referensi", on_click=apply_month, args=(pick,))
    st.caption("Hanya berpengaruh pada mode Manual. Bulan Januari hampir selalu nol "
               "di lokasi ini, jadi hindari Januari untuk referensi.")


def render_save(result):
    st.subheader("Simpan hasil", help=TOOLTIPS["simpan"])
    st.caption("Tersimpan ke outputs/runs/<waktu>_<label>/ berisi run.json, points.csv, "
               "sweep.csv, summary.md dan water_mask.png.")
    note = st.text_input("Catatan", placeholder="mis. percobaan ambang 0.10")
    if st.button("Simpan sekarang", type="primary"):
        path = runs.save(result, note=note)
        st.success("Tersimpan di %s" % path)

    st.divider()
    st.caption("Hasil tersimpan terakhir")
    saved = runs.recent(8)
    if not saved:
        st.text("Belum ada.")
    for folder in saved:
        st.text(os.path.basename(folder))


def main():
    boot()
    params, run = sidebar()

    if run:
        with st.spinner("Menghitung di Earth Engine..."):
            try:
                st.session_state["result"] = compute(**params)
            except Exception as error:
                st.error("Perhitungan gagal: %s" % error)
                return

    st.title("Deteksi Genangan Sawah - Desa Citrajaya")

    result = st.session_state.get("result")
    if result is None:
        st.info("Atur konfigurasi di panel kiri, lalu tekan **Hitung**.")
        st.markdown(
            "Parameter yang sengaja **tidak** bisa diubah dari sini: AOI, koleksi "
            "citra, dan pemetaan band. Mengubahnya akan membatalkan validasi lapangan "
            "yang sudah dikumpulkan, jadi perubahan itu harus lewat src/config.py dan "
            "ditinjau ulang.")
        return

    ok = render_status(result)
    tabs = st.tabs(["Titik validasi", "Peta", "Kalibrasi ambang",
                    "Morfologi", "Cakupan", "Simpan"])
    with tabs[0]:
        render_points(result)
    with tabs[1]:
        # The map stays available even at 0% coverage: it falls back to the
        # unmasked window, which is enough to locate the AOI and the points.
        render_map(result, ok)
    with tabs[2]:
        if ok:
            render_calibration(result)
        else:
            st.info("Kalibrasi butuh piksel yang benar-benar teramati. Lihat tab "
                    "Peta untuk citra mentah jendela ini, dan tab Cakupan untuk "
                    "mencari jendela lain.")
    with tabs[3]:
        render_morphology(result)
    with tabs[4]:
        render_coverage()
    with tabs[5]:
        render_save(result)


main()

