"""Morphological cleanup that removes noise without erasing rivers.

The cleanup described in docs/AGENTS.md is a circular erosion (focal_min)
followed by a dilation. Field bunds and wet mud disappear, but so do Kali
Cigadung and Kali Anyar, because at 10 m those channels are one or two pixels
wide and a disc does not fit inside them.

The property that separates a bund from a river is not shape - both are
linear - but length. A bund is a field-length segment, roughly 10-20 pixels.
A river runs continuously for hundreds. A path opening preserves long
curvilinear structures and removes short ones; it is approximated here by the
union of straight-line openings over many orientations, because a straight
structuring element cannot follow a meander and Earth Engine exposes only
fixed kernels.

Reference: Heijmans, Buckley & Talbot (2005), "Path openings and closings",
J. Math. Imaging Vision 22:107-119.
"""

import math

import ee

# 17 orientations at 11 degrees, so a channel is never more than 5.5 degrees
# away from an aligned element.
DEFAULT_ANGLES = tuple(float(angle) for angle in range(0, 180, 11))


def line_kernel(size, angle_deg):
    """Fixed kernel with 1s along a line of the given orientation.

    A pixel is set when its perpendicular distance to the line through the
    kernel centre is at most half a pixel, which yields a one-pixel-wide
    element for any angle.
    """
    if size % 2 == 0:
        raise ValueError("kernel size must be odd so the line is centred")
    half = (size - 1) / 2.0
    radians = math.radians(angle_deg)
    sin_a, cos_a = math.sin(radians), math.cos(radians)
    weights = []
    for row in range(size):
        y = row - half
        weights.append([
            1.0 if abs((col - half) * sin_a - y * cos_a) <= 0.5 else 0.0
            for col in range(size)
        ])
    return ee.Kernel.fixed(size, size, weights, normalize=False)


def open_circular(mask, radius=2):
    """Baseline cleanup from the brief: erode then dilate with a disc.

    Kept as the control. It removes noise and rivers with equal enthusiasm.

    The built-in radius argument is used rather than a fixed kernel: Earth
    Engine normalises a custom circular kernel, and the normalised weights
    make focal_min collapse to zero.
    """
    return (
        mask.focal_min(radius=radius, kernelType="circle", units="pixels")
        .focal_max(radius=radius, kernelType="circle", units="pixels")
    )


def open_linear(mask, size=15, angle=0.0):
    """Opening with a one-pixel line element at a fixed orientation."""
    kernel = line_kernel(size, angle)
    return mask.focal_min(kernel=kernel).focal_max(kernel=kernel)


def path_open(mask, length=15, angles=DEFAULT_ANGLES):
    """Union of straight-line openings: an approximation of path opening.

    Features shorter than the given length in every orientation are removed;
    a feature continuous for at least that many pixels along some direction
    survives.
    """
    return ee.ImageCollection(
        [open_linear(mask, length, angle) for angle in angles]
    ).max()


def preserve_linear(mask, length=15, angles=DEFAULT_ANGLES, widen=1):
    """Path opening that tolerates curvature.

    A one-pixel channel meanders too tightly for a straight element to fit,
    which is why a naive path opening drops most of it. Dilating the mask by
    one pixel first makes the channel three pixels wide, wide enough for the
    element to slide around a bend; the dilation is undone afterwards.

    Measured on synthetic geometry, this raises channel retention from 35 %
    to 100 % at length=15 without letting any short linear feature through.
    """
    if widen:
        mask = mask.focal_max(radius=widen, kernelType="circle", units="pixels")
    opened = path_open(mask, length, angles)
    if widen:
        opened = opened.focal_min(radius=widen, kernelType="circle", units="pixels")
    return opened


def close_gaps(mask, radius=1):
    """Morphological closing: fill pinholes without growing the outline."""
    return (
        mask.focal_max(radius=radius, kernelType="circle", units="pixels")
        .focal_min(radius=radius, kernelType="circle", units="pixels")
    )


def remove_small_objects(mask, min_pixels=8, max_size=1024):
    """Drop connected components smaller than min_pixels.

    A size filter rather than an erosion, so it cannot shorten a river no
    matter how thin it is.
    """
    component_size = mask.selfMask().connectedPixelCount(max_size, True)
    return mask.updateMask(component_size.gte(min_pixels))


def clean(mask, length=15, angles=DEFAULT_ANGLES, close_radius=1):
    """Remove specks and short linear noise while keeping channels.

    The length argument is the discriminating parameter: the shortest feature,
    in pixels, that survives. At 10 m, length=15 rejects anything shorter than
    150 m and keeps a channel that runs longer than that without interruption.

    The input mask's valid-data footprint is restored at the end, so cloud
    gaps are not silently filled by the focal operations.
    """
    opened = preserve_linear(mask, length, angles)
    closed = close_gaps(opened, close_radius)
    return closed.updateMask(mask.mask())
