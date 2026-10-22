"""Reset derived results before a new independent calculation/trial."""

import pandas as pd


RESULT_DEFAULTS = {
    'building': {'ds': 0, 'casualty': 0, 'node_id': None, 'hospital_access': True, 'has_power': True},
    'household': {'node_id': None, 'hospital_access': True, 'has_power': True, 'hospital_has_power': True},
    'individual': {'facility_access': True},
    'road edges': {'ds': 0, 'is_damaged': False},
    'road nodes': {'ds': 0, 'is_damaged': False},
    'power nodes': {'ds': 0, 'is_damaged': False, 'is_operational': True},
    'power edges': {'ds': 0, 'is_damaged': False, 'is_operational': True},
}
BUILDING_HARM_DETAILS = ['casualty_expected', 'casualty_probability', 'fatalities_expected',
                         'injuries_nonfatal_expected', 'people_at_risk_expected', 'casualty_model']


def reset_analysis_outputs(state):
    """Restore fresh-import defaults in data and table views, keeping all inputs.

    Excluded infrastructure means no modelled disruption, as on a fresh import.
    Each selected calculator then replaces its own defaults with new results.
    Only output fields are changed; geometry, exposure, network topology and
    parameter values remain available for subsequent runs.
    """
    visited = set()
    for name, defaults in RESULT_DEFAULTS.items():
        layer = state['layers'].get(name)
        if layer is None:
            continue
        for key in ['data', 'df']:
            reference = layer.get(key)
            frame = reference.value if reference is not None else None
            if not isinstance(frame, pd.DataFrame) or id(frame) in visited:
                continue
            visited.add(id(frame))
            for column, value in defaults.items():
                if column in frame or column in layer.get('extra_cols', {}):
                    frame[column] = value
            if name == 'building':
                frame.drop(columns=BUILDING_HARM_DETAILS, errors='ignore', inplace=True)
    metadata = state.get('flood_casualty_result_metadata')
    if metadata is not None:
        metadata.set(None)
