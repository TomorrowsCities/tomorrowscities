"""Versioned, provisional flood harm screening (injury including fatalities).

The hazard/exposure/harm equations follow Defra/EA FD2321/TR1 (2006),
sections 3.5, 5.4 and 6. This application's floor-by-floor population model,
explicit occupancy/evacuation/shelter factors and probability bounds are
adaptations, not a locally calibrated implementation of that methodology.
"""

from dataclasses import asdict, dataclass
import re

import numpy as np
import pandas as pd


FLOOD_CASUALTY_MODEL = 'people-risk-v1'
FLOOD_CASUALTY_SOURCE = (
    'https://assets.publishing.service.gov.uk/media/602bbc768fa8f50383c41f80/'
    'Flood_risks_to_people_-_Phase_2_The_flood_risks_to_people_methodology_technical_report.pdf'
)


@dataclass(frozen=True)
class FloodCasualtySettings:
    """Illustrative scenario defaults; none are measurements for Mumbai.

    Velocity=0 and debris=0 describe a still-water/no-debris scenario, not
    missing-data estimates. AV=6 and PV=0.25 are illustrative sensitivity
    inputs, not inferred from income, seismic code or economic damage.
    Fractions use 0..1; AV is the sum of warning/onset/area scores (3..9).
    """

    velocity_m_s: float = 0.0
    debris_factor: float = 0.0
    area_vulnerability: float = 6.0
    people_vulnerability: float = 0.25
    floor_height_m: float = 3.0
    occupancy_fraction: float = 1.0
    evacuation_fraction: float = 0.0
    shelter_fraction: float = 0.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not np.isfinite(value):
                raise ValueError(f'{key} must be finite')
        if self.velocity_m_s < 0 or self.floor_height_m <= 0:
            raise ValueError('Velocity must be nonnegative and floor height positive')
        if not 0 <= self.debris_factor <= 1:
            raise ValueError('Debris factor must be within [0, 1]')
        if not 3 <= self.area_vulnerability <= 9:
            raise ValueError('Area vulnerability must be within [3, 9]')
        if not 0 <= self.people_vulnerability <= 2:
            raise ValueError('People vulnerability is the sum of two fractions, within [0, 2]')
        for key in ['occupancy_fraction', 'evacuation_fraction', 'shelter_fraction']:
            if not 0 <= getattr(self, key) <= 1:
                raise ValueError(f'{key} must be within [0, 1]')


def flood_casualty_metadata(settings=None):
    settings = settings or FloodCasualtySettings()
    return {
        'model': FLOOD_CASUALTY_MODEL,
        'status': 'Provisional scenario screening; not locally calibrated',
        'definition': 'Unique people injured or killed; fatalities are a subset, not added twice',
        'settings': asdict(settings),
        'source': FLOOD_CASUALTY_SOURCE,
        'adaptations': 'Equal residents per floor; floor-relative depths; explicit occupancy, '
                       'evacuation and additional safe shelter; bounded fractions; '
                       'stock-wide largest-remainder integer allocation',
        'limitations': 'Defaults are illustrative, not observed local conditions. No velocity '
                       'raster, rise-rate, duration, collapse, basement, daytime facility '
                       'occupants, or individual floor/health data are modelled. Upper floors '
                       'are assumed habitable and structurally stable. AV must not double-count '
                       'evacuation/shelter already represented by explicit fractions.',
    }


def allocate_casualty_counts(expected, capacity, building_ids):
    """Round the stock total once; allocate remainders by ID to avoid small-bin bias."""
    expected = np.asarray(expected, dtype=float)
    capacity = np.asarray(capacity, dtype=float)
    ids = pd.Index(building_ids)
    if (expected.ndim != 1 or expected.shape != capacity.shape or len(ids) != len(expected)
            or ids.has_duplicates or ids.isna().any()):
        raise ValueError('Casualty allocation requires aligned arrays and unique building IDs')
    if (not np.isfinite(expected).all() or not np.isfinite(capacity).all()
            or (expected < 0).any() or (capacity < expected).any()
            or (capacity != np.floor(capacity)).any()):
        raise ValueError('Expected casualties must be finite, nonnegative and within integer population')
    counts = np.floor(expected).astype(np.int64)
    remaining = int(np.floor(expected.sum() + 0.5)) - int(counts.sum())
    if remaining:
        candidates = np.flatnonzero((expected > counts) & (counts < capacity))
        # IDs have no numerical meaning; their string order provides stable ties.
        order = sorted(candidates, key=lambda j: (-(expected[j] - counts[j]), str(ids[j])))
        counts[np.asarray(order[:remaining], dtype=int)] += 1
    return counts


def calculate_flood_casualties(buildings, depths, settings=None):
    """Return combined harm counts and expected severity diagnostics by building.

    For floor k: d=max(h-k*H,0); HR=d*(v+0.5)+DF (zero on dry floors);
    X=clip(HR*AV/100,0,1); Y=clip(2*PV,0,1).
    Combined harm = sum_k N_present/F * X * Y.
    Fatalities are a subset: harm_k * clip(2*HR/100,0,1).
    """
    settings = settings or FloodCasualtySettings()
    if not isinstance(settings, FloodCasualtySettings):
        raise TypeError('Use FloodCasualtySettings for flood casualty parameters')
    depth = np.asarray(depths, dtype=float)
    residents = buildings.residents.to_numpy(dtype=float)
    if (depth.shape != residents.shape or not np.isfinite(depth).all()
            or not np.isfinite(residents).all() or (depth < 0).any()
            or (residents < 0).any() or (residents != np.floor(residents)).any()):
        raise ValueError('Flood casualties require finite nonnegative depths and integer residents')
    floors = []
    for taxonomy in buildings.expstr:
        parts = str(taxonomy).rsplit('+', 3)
        match = re.fullmatch(r'([1-9]\d*)s', parts[-2]) if len(parts) == 4 else None
        if match is None:
            raise ValueError(f'Flood casualties require a valid storey count in expstr: {taxonomy}')
        floors.append(int(match[1]))
    floors = np.asarray(floors, dtype=int)
    x_sum = np.zeros(len(depth))
    harm_sum = np.zeros(len(depth))
    fatal_sum = np.zeros(len(depth))
    y = min(1.0, 2 * settings.people_vulnerability)
    # Only occupied, potentially wet floors need evaluation. Memory stays O(buildings).
    wet_levels = min(int(floors.max(initial=0)), int(np.ceil(depth.max(initial=0) / settings.floor_height_m)))
    for level in range(wet_levels):
        local_depth = np.maximum(depth - level * settings.floor_height_m, 0)
        wet = (local_depth > 0) & (floors > level)
        hr = np.where(wet, local_depth * (settings.velocity_m_s + 0.5) + settings.debris_factor, 0)
        x = np.clip(hr * settings.area_vulnerability / 100, 0, 1)
        harm = x * y
        x_sum += x
        harm_sum += harm
        fatal_sum += harm * np.clip(2 * hr / 100, 0, 1)
    present = residents * settings.occupancy_fraction * (1 - settings.evacuation_fraction) * (1 - settings.shelter_fraction)
    expected = np.clip(present * harm_sum / floors, 0, residents)
    fatal_expected = np.minimum(expected, present * fatal_sum / floors)
    return pd.DataFrame({
        'casualty': allocate_casualty_counts(expected, residents, buildings.bldid),
        'casualty_expected': expected,
        'casualty_probability': np.divide(expected, residents, out=np.zeros(len(depth)), where=residents > 0),
        'fatalities_expected': fatal_expected,
        'injuries_nonfatal_expected': expected - fatal_expected,
        'people_at_risk_expected': present * x_sum / floors,
        'casualty_model': FLOOD_CASUALTY_MODEL,
    }, index=buildings.index)
