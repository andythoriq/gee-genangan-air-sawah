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
    """Area of interest as a plain rectangle in WGS84."""
    return ee.Geometry.Rectangle(
        config.AOI_BOUNDS, proj="EPSG:4326", geodesic=False
    )


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
    raise ValueError(
        "unknown CLOUD_MASK_MODE %r, expected 'scl', 'qa60' or 'strict'" % mode
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


def composite(start, end, mode=None, geom=None):
    """Median composite over [start, end), cloud-masked and clipped.

    A median over an already-masked stack leaves a pixel masked only if every
    observation in the window is unusable, so gaps are honest rather than
    filled with cloud. Check coverage() before trusting the result.
    """
    geom = geom or aoi()
    masked = collection(start, end, geom).map(lambda img: mask_clouds(img, mode))
    return masked.median().clip(geom)


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
