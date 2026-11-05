"""Spectral water indices.

Sentinel-2 surface reflectance is stored as integers scaled by 10000, but a
normalised difference cancels that scale, so no rescaling is needed here.
"""

import config


def mndwi(image):
    """Modified NDWI (Xu 2006): (Green - SWIR1) / (Green + SWIR1).

    Preferred over NDWI for this study because the floodwater and the Kali
    Cigadung / Kali Anyar channels carry heavy sediment, and SWIR separates
    turbid water from wet soil far better than NIR does.
    """
    return image.normalizedDifference([config.GREEN, config.SWIR1]).rename("MNDWI")


def ndwi(image):
    """McFeeters NDWI: (Green - NIR) / (Green + NIR).

    Kept as the conventional baseline to show, in the results, why MNDWI is
    the right choice for sediment-laden water.
    """
    return image.normalizedDifference([config.GREEN, config.NIR]).rename("NDWI")
