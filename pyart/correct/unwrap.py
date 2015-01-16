"""
pyart.correct.unwrap
====================

Dealias using multidimensional phase unwrapping algorithms.

.. autosummary::
    :toctree: generated/

    dealias_unwrap_phase
    _parse_fields
    _parse_nyquist_vel
    _parse_gatefilter
    _parse_rays_wrap_around
    _dealias_unwrap_3d
    _dealias_unwrap_2d
    _dealias_unwrap_1d
    _verify_unwrap_unit
    _is_radar_cubic
    _is_radar_sweep_aligned
    _is_radar_sequential
    _is_sweep_sequential

"""

from __future__ import print_function

import numpy as np

from ..config import get_field_name, get_metadata
from .filters import moment_based_gate_filter, GateFilter

from ._unwrap_1d import unwrap_1d
from ._unwrap_2d import unwrap_2d
from ._unwrap_3d import unwrap_3d


def dealias_unwrap_phase(
        radar, unwrap_unit='sweep', nyquist_vel=None, gatefilter=None,
        rays_wrap_around=None, keep_original=True, vel_field=None,
        corr_vel_field=None, **kwargs):
    """
    Dealias Doppler velocities using multi-dimensional phase unwrapping.

    Parameters
    ----------
    radar : Radar
        Radar object containing Doppler velocities to dealias.
    unwrap_unit : {'ray', 'sweep', 'volume'}, optional
        Unit to unwrap independently.  'ray' will unwrap each ray
        individually, 'sweep' each sweep, and 'volume' will unwrap the entire
        volume in a single pass.  'sweep', the default, often gives superior
        results when the lower sweeps of the radar volume are contaminated by
        clutter. 'ray' does not use the gatefilter parameter and rays where
        gates ared masked will result in poor dealiasing for that ray.
    nyquist_velocity : float, optional
        Nyquist velocity in unit identical to those stored in the radar's
        velocity field.  None will attempt to determine this value from the
        instrument_parameters attribute.
    gatefilter : GateFilter, None or False, optional.
        A GateFilter instance which specified which gates should be
        ignored when performing de-aliasing.  A value of None, the default,
        created this filter from the radar moments using any additional
        arguments by passing them to :py:func:`moment_based_gate_filter`.
        False disables filtering including all gates in the dealiasing.
    rays_wrap_around : bool or None, optional
        True when the rays at the beginning of the sweep and end of the sweep
        should be interpreted as connected when de-aliasing (PPI scans).
        False if they edges should not be interpreted as connected (other scan
        types).  None will determine the correct value from the radar
        scan type.
    keep_original : bool, optional
        True to retain the original Doppler velocity values at gates
        where the dealiasing procedure fails or was not applied. False
        does not replacement and these gates will be masked in the corrected
        velocity field.
    vel_field : str, optional
        Field in radar to use as the Doppler velocities during dealiasing.
        None will use the default field name from the Py-ART configuration
        file.
    corr_vel_field : str, optional
        Name to use for the dealiased Doppler velocity field metadata.  None
        will use the default field name from the Py-ART configuration file.

    Returns
    -------

    References
    ----------
    .. [1] Miguel Arevallilo Herraez, David R. Burton, Michael J. Lalor,
           and Munther A. Gdeisat, "Fast two-dimensional phase-unwrapping
           algorithm based on sorting by reliability following a noncontinuous
           path", Journal Applied Optics, Vol. 41, No. 35 (2002) 7437,
    .. [2] Abdul-Rahman, H., Gdeisat, M., Burton, D., & Lalor, M., "Fast
           three-dimensional phase-unwrapping algorithm based on sorting by
           reliability following a non-continuous path. In W. Osten,
           C. Gorecki, & E. L. Novak (Eds.), Optical Metrology (2005) 32--40,
           International Society for Optics and Photonics.

    """
    vel_field, corr_vel_field = _parse_fields(vel_field, corr_vel_field)
    gatefilter = _parse_gatefilter(gatefilter, radar, **kwargs)
    rays_wrap_around = _parse_rays_wrap_around(rays_wrap_around, radar)
    nyquist_vel = _parse_nyquist_vel(nyquist_vel, radar)
    _verify_unwrap_unit(radar, unwrap_unit)

    # exclude masked and invalid velocity gates
    gatefilter.exclude_masked(vel_field)
    gatefilter.exclude_invalid(vel_field)
    gfilter = gatefilter.gate_excluded

    # perform dealiasing
    vdata = radar.fields[vel_field]['data']
    if unwrap_unit == 'ray':
        # 1D unwrapping does not use the gate filter nor respect
        # masked gates in the rays.  No information from the radar object is
        # needed for the unfolding
        data = _dealias_unwrap_1d(vdata, nyquist_vel)
    elif unwrap_unit == 'sweep':
        data = _dealias_unwrap_2d(
            radar, vdata, nyquist_vel, gfilter, rays_wrap_around)
    elif unwrap_unit == 'volume':
        data = _dealias_unwrap_3d(
            radar, vdata, nyquist_vel, gfilter, rays_wrap_around)
    else:
        message = ("Unknown `unwrap_unit` parameter, must be one of"
                   "'ray', 'sweep', or 'volume'")
        raise ValueError(message)

    # mask filtered gates and restore original velocities if requested
    if np.any(gfilter):
        data = np.ma.array(data, mask=gfilter)
    if keep_original:
        # restore original values where dealiasing not applied
        data[gfilter] = vdata[gfilter]

    # return field dictionary containing dealiased Doppler velocities
    corr_vel = get_metadata(corr_vel_field)
    corr_vel['data'] = data
    return corr_vel


def _parse_fields(vel_field, corr_vel_field):
    """ Parse and return the radar fields for dealiasing. """
    if vel_field is None:
        vel_field = get_field_name('velocity')
    if corr_vel_field is None:
        corr_vel_field = get_field_name('corrected_velocity')
    return vel_field, corr_vel_field


def _parse_nyquist_vel(nyquist_vel, radar):
    """ Parse the nyquist_vel parameter, extract from the radar if needed. """
    if nyquist_vel is None:
        if (radar.instrument_parameters is None) or (
                'nyquist_velocity' not in radar.instrument_parameters):
            message = ('Nyquist velocity not specified in radar object, '
                       'provide this value explicitly in the function call.')
            raise ValueError(message)
        nyquist_vel = radar.instrument_parameters[
            'nyquist_velocity']['data'][0]
    return nyquist_vel


def _parse_gatefilter(gatefilter, radar, **kwargs):
    """ Parse the gatefilter, return a valid GateFilter object. """
    # parse the gatefilter parameter
    if gatefilter is None:  # create a moment based filter
        gatefilter = moment_based_gate_filter(radar, **kwargs)
    elif gatefilter is False:
        gatefilter = GateFilter(radar)
    else:
        gatefilter = gatefilter.copy()
    return gatefilter


def _parse_rays_wrap_around(rays_wrap_around, radar):
    """ Parse the rays_wrap_around parameter. """
    if rays_wrap_around is None:
        if radar.scan_type == 'ppi':
            rays_wrap_around = True
        else:
            rays_wrap_around = False
    return rays_wrap_around


def _dealias_unwrap_3d(radar, vdata, nyquist_vel, gfilter, rays_wrap_around):
    """ Dealias using 3D phase unwrapping (full volume at once). """

    # form cube and scale to phase units
    shape = (radar.nsweeps, -1, radar.ngates)
    scaled_cube = (np.pi * vdata / nyquist_vel).reshape(shape)
    filter_cube = gfilter.reshape(shape)

    # perform unwrapping
    wrapped = np.require(np.ma.getdata(scaled_cube), np.float64, ['C'])
    mask = np.require(filter_cube, np.uint8, ['C'])
    unwrapped = np.empty_like(wrapped, dtype=np.float64, order='C')
    unwrap_3d(wrapped, mask, unwrapped, [False, rays_wrap_around, False])

    # scale back to velocity units
    unwrapped_cube = unwrapped * nyquist_vel / np.pi
    unwrapped_volume = unwrapped_cube.reshape(-1, radar.ngates)
    unwrapped_volume = unwrapped_volume.astype(vdata.dtype)
    return unwrapped_volume


def _dealias_unwrap_1d(vdata, nyquist_vel):
    """ Dealias using 1D phase unwrapping (ray-by-ray) """
    data = np.empty_like(vdata)
    for i, ray in enumerate(vdata):
        # extract ray and scale to phase units
        scaled_ray = ray * np.pi / nyquist_vel

        # perform unwrapping
        wrapped = np.require(np.ma.getdata(scaled_ray), np.float64, ['C'])
        unwrapped = np.empty_like(wrapped, dtype=np.float64, order='C')
        unwrap_1d(wrapped, unwrapped)

        # scale back into velocity units and store
        data[i] = unwrapped * nyquist_vel / np.pi
    return data


def _dealias_unwrap_2d(radar, vdata, nyquist_vel, gfilter, rays_wrap_around):
    """ Dealias using 2D phase unwrapping (sweep-by-sweep). """
    data = np.zeros_like(vdata)
    for sweep_slice in radar.iter_slice():
        # extract sweep and scale to phase units
        scaled_sweep = vdata[sweep_slice] * np.pi / nyquist_vel
        sweep_mask = gfilter[sweep_slice]

        # perform unwrapping
        wrapped = np.require(scaled_sweep, np.float64, ['C'])
        mask = np.require(sweep_mask, np.uint8, ['C'])
        unwrapped = np.empty_like(wrapped, dtype=np.float64, order='C')
        unwrap_2d(np.ma.getdata(wrapped), np.ma.getdata(mask),
                  np.ma.getdata(unwrapped), [rays_wrap_around, False])

        # scale back into velocity units and store
        data[sweep_slice, :] = unwrapped * nyquist_vel / np.pi
    return data


def _verify_unwrap_unit(radar, unwrap_unit):
    """
    Verify that the radar supports the requested unwrap unit

    raises a ValueError if the unwrap_unit is not supported.
    """
    if unwrap_unit == 'sweep' or unwrap_unit == 'volume':
        if _is_radar_sequential(radar) is False:
            mess = ("rays are not sequentially ordered, must use 'ray' "
                    "unwrap_unit.")
            raise ValueError(mess)
    if unwrap_unit == 'volume':
        if _is_radar_cubic(radar) is False:
            mess = "Non-cubic radar volume, 'volume' unwrap_unit invalid. "
            raise ValueError(mess)
        if _is_radar_sweep_aligned(radar) is False:
            mess = ("Angle in sequential sweeps in radar volumes are not "
                    "aligned, 'volume unwrap_unit invalid")
            raise ValueError(mess)


def _is_radar_cubic(radar):
    """ Test if a radar is cubic (sweeps have the same number of rays). """
    rays_per_sweep = radar.rays_per_sweep['data']
    return bool(np.all(rays_per_sweep == rays_per_sweep[0]))


def _is_radar_sweep_aligned(radar, diff=0.1):
    """
    Test that all sweeps in the radar sample nearly the same angles.

    Test that the maximum difference in sweep sampled angles is below
    `diff` degrees. The radar should first be tested to verify that is cubic
    before calling this function using the _is_radar_cubic function.

    """
    if radar.scan_type == 'ppi':
        angles = radar.azimuth['data']
    elif radar.scan_type == 'rhi':
        angles = radar.elevation['data']
    starts = radar.sweep_start_ray_index['data']
    ends = radar.sweep_end_ray_index['data']
    ref_angles = angles[starts[0]:ends[0] + 1]
    for start, end in zip(starts, ends):
        test_angles = angles[start:end+1]
        if np.any(np.abs(test_angles - ref_angles) > diff):
            return False
    return True


def _is_radar_sequential(radar):
    """ Test if all sweeps in radar are sequentially ordered. """
    for i in xrange(radar.nsweeps):
        if not _is_sweep_sequential(radar, i):
            return False
    return True


def _is_sweep_sequential(radar, sweep_number):
    """ Test if a specific sweep is sequentially ordered. """
    start = radar.sweep_start_ray_index['data'][sweep_number]
    end = radar.sweep_end_ray_index['data'][sweep_number]
    if radar.scan_type == 'ppi':
        angles = radar.azimuth['data'][start:end+1]
    elif radar.scan_type == 'rhi':
        angles = radar.elevation['data'][start:end+1]
    else:
        raise ValueError('invalid scan_type: %s' % (radar.scan_type))
    rolled_angles = np.roll(angles, -np.argmin(angles))
    return np.all(np.diff(rolled_angles) >= 0)
