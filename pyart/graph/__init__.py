"""
=============================
Graphing (:mod:`pyart.graph`)
=============================

.. currentmodule:: pyart.graph

.. autosummary::
    :toctree: generated/

    RadarDisplay
    RadarMapDisplay
    GridMapDisplay
    MdvDisplay
    RslDisplay
    CFRadialDisplay


"""

from .radardisplay import RadarDisplay
from .plot_mdv import MdvDisplay
from .plot_cfradial import CFRadialDisplay
from . import cm

try:
    from .gridmapdisplay import GridMapDisplay
except ImportError:
    import warnings
    warnings.warn('No grid plotting support, requires basemap.')

try:
    from .radarmapdisplay import RadarMapDisplay
except ImportError:
    import warnings
    warnings.warn('No grid plotting support, requires basemap.')

try:
    from .plot_rsl import RslDisplay
except ImportError:
    pass

__all__ = [s for s in dir() if not s.startswith('_')]
