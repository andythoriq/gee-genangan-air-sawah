"""Sentinel-2 access, cloud masking and compositing for the project AOI.

Every function returns a server-side Earth Engine object. Nothing is
evaluated until a caller asks for .getInfo(), so these compose cheaply.
"""

import ee

import config

_initialized = False


def init():
    """Initialise Earth Engine once per process."""
    global _initialized
    if not _initialized:
        ee.Initialize(project=config.GEE_PROJECT)
        _initialized = True


def aoi():
    """Area of interest as the survey polygon, in WGS84."""
    return ee.Geometry.Polygon([config.AOI_RING])


def mask_qa60(image):
    """Drop opaque cloud (bit 10) and cirrus (bit 11) flagged by QA60."""
    qa = image.select("QA60")
    clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(clear)


def mask_scl(image):
    """Drop cloud shadow, cloud, thin cirrus and snow using the SCL band.

    SCL classes: 3 = cloud shadow, 8 = medium probability cloud,
    9 = high probability cloud, 10 = thin cirrus, 11 = snow.
    """
    scl = image.select("SCL")
    bad = (
        scl.eq(3)
        .Or(scl.eq(8))
        .Or(scl.eq(9))
        .Or(scl.eq(10))
        .Or(scl.eq(11))
    )
    return image.updateMask(bad.Not())


def mask_clouds(image, mode=None):
    """Apply the configured per-pixel cloud mask."""
    mode = mode or config.CLOUD_MASK_MODE
    if mode == "qa60":
        return mask_qa60(image)
    if mode == "scl":
        return mask_scl(image)
    if mode == "strict":
        return mask_scl(mask_qa60(image))
    if mode == "none":
        # Deliberately unmasked. Used only for the map preview when the masked
        # composite has no usable pixels: the analyst still wants to see what
        # the window actually looks like, clouds included.
        return image
    raise ValueError(
        "unknown CLOUD_MASK_MODE %r, expected 'scl', 'qa60', 'strict' or 'none'" % mode
    )


def collection(start, end, geom=None):
    """Sentinel-2 collection over [start, end) intersecting the AOI."""
    return (
        ee.ImageCollection(config.S2_COLLECTION)
        .filterBounds(geom or aoi())
        .filterDate(start, end)
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE", config.MAX_CLOUDY_PIXEL_PERCENTAGE
            )
        )
    )


def composite(start, end, mode=None, geom=None, clip=True):
    """Median composite over [start, end), cloud-masked and optionally clipped.

    A median over an already-masked stack leaves a pixel masked only if every
    observation in the window is unusable, so gaps are honest rather than
    filled with cloud. Check coverage() before trusting the result.

    Pass clip=False when the composite is only used for sampling validation
    points: some of those points lie outside the AOI, and clipping would turn
    them into missing data. Area statistics are unaffected because they are
    bounded by the geometry passed to reduceRegion.
    """
    geom = geom or aoi()
    scenes = collection(start, end, geom)
    if scenes.size().getInfo() == 0:
        # An empty collection produces an image with no bands, which fails much
        # later with a confusing "No band named B3" message.
        raise ValueError(
            "Tidak ada citra Sentinel-2 pada %s sampai %s. Periksa urutan tanggal "
            "dan pastikan rentangnya berada di dalam arsip (2015 sampai sekarang)."
            % (start, end))
    masked = scenes.map(lambda img: mask_clouds(img, mode))
    median = masked.median()
    return median.clip(geom) if clip else median


def composite_index(start, end, index, mode=None, geom=None, clip=True):
    """Median of a per-scene index, instead of an index of the median scene.

    The two orders are not equivalent. Index-of-median applies the index once
    to a stack of medians, so a pixel where half the scenes are cloudy still
    contributes its median reflectance. Median-of-index scores each scene
    first and then takes the median score, which is more robust where scenes
    disagree but costs one index evaluation per scene.

    'index' is a callable taking an ee.Image and returning a named band image,
    e.g. indices.mndwi.
    """
    geom = geom or aoi()
    scenes = collection(start, end, geom)
    if scenes.size().getInfo() == 0:
        raise ValueError(
            "Tidak ada citra Sentinel-2 pada %s sampai %s. Periksa urutan tanggal "
            "dan pastikan rentangnya berada di dalam arsip (2015 sampai sekarang)."
            % (start, end))
    indexed = scenes.map(lambda img: index(mask_clouds(img, mode)))
    median = indexed.median()
    return median.clip(geom) if clip else median


def monthly_coverage(start, end, geom=None, mode=None):
    """AOI coverage per calendar month, as an ee.FeatureCollection.

    Built server-side in a single request so the caller can scan two years of
    months without paying one round trip each. Use it to choose reference
    windows from evidence instead of guessing.
    """
    geom = geom or aoi()
    start_date = ee.Date(start)
    end_date = ee.Date(end)
    total = end_date.difference(start_date, "month").round()
    months = ee.List.sequence(0, total.subtract(1)).map(
        lambda offset: start_date.advance(offset, "month"))

    def summarise(month):
        month = ee.Date(month)
        scenes = collection(month.format("YYYY-MM-dd"), month.advance(1, "month"), geom)
        masked = scenes.map(lambda img: mask_clouds(img, mode))
        valid = masked.median().select(0).mask()
        share = valid.reduceRegion(
            ee.Reducer.mean(), geom, 10, maxPixels=int(1e9), bestEffort=True
        ).values().get(0)
        return ee.Feature(None, {
            "month": month.format("YYYY-MM"),
            "coverage": share,
            "scenes": scenes.size(),
        })

    return ee.FeatureCollection(months.map(summarise))


def coverage(image, geom=None, band=None):
    """Fraction of AOI pixels carrying a valid observation, as an ee.Number.

    Call .getInfo() to read it. Values near 0 mean the window is unusable,
    which is the normal state here during the wet season. Without a band name
    the first band is used, which lets this work on single-band index images.
    """
    valid = image.select(band if band is not None else 0).mask().rename("valid")
    return valid.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom or aoi(),
        scale=10,
        maxPixels=int(1e9),
        bestEffort=True,
    ).get("valid")


def scene_count(start, end, geom=None):
    """Number of scenes in the window, as an ee.Number."""
    return collection(start, end, geom).size()
