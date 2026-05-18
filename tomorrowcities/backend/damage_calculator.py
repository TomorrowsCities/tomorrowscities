import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.stats import norm
from scipy.interpolate import interp1d

class DamageCalculator:
    """
    Standalone Damage Calculator for Tomorrow's Cities WebApp.
    Computes building damage states given hazard, fragility/vulnerability, and building datasets.
    It skips metric calculations such as landuse, household, and individual impacts.
    """

    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIVE = 3
    DS_COMPLETE = 4
    
    HAZARD_EARTHQUAKE = "earthquake"
    HAZARD_FLOOD = "flood"

    def __init__(self, hazard_type="earthquake", **kwargs):
        self.hazard_type = hazard_type.lower()
        
        # Earthquake Defaults
        self.earthquake_intensity_unit = kwargs.get('earthquake_intensity_unit', 'g')
        self.earthquake_simulation_method = kwargs.get('earthquake_simulation_method', 'monte carlo')
        self.number_of_trials = kwargs.get('number_of_trials', 25)
        
        # Flood Defaults (from legacy engine.py)
        self.threshold_flood = kwargs.get('threshold_flood', [0.05, 0.2, 0.5])
        self.threshold_flood_distance = kwargs.get('threshold_flood_distance', 10)
        self.flood_depth_reduction = kwargs.get('flood_depth_reduction', 0.20)
        self.damage_curve_suppress_factor = kwargs.get('damage_curve_suppress_factor', 0.9)

    def calculate(self, buildings: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame, fragility) -> pd.DataFrame:
        """
        Main calculation core.
        
        Args:
            buildings (gpd.GeoDataFrame): Must contain 'bldid', and 'expstr'.
            hazard (gpd.GeoDataFrame): Standard hazard intensity grid.
            fragility (pd.DataFrame or dict): Fragility or vulnerability functions.
            
        Returns:
            pd.DataFrame: A DataFrame with 'bldid' and 'ds' (damage state).
        """
        gem_fragility = isinstance(fragility, dict)
        
        # Ensure correct CRS for joining (using EPSG:3857 for metric distances)
        epsg = 3857
        
        gdf_bld = buildings.copy()
        gdf_haz = hazard.copy()
        
        # Allow missing bldid if index is used, but ideally 'bldid' is present
        if 'bldid' not in gdf_bld.columns:
            gdf_bld['bldid'] = gdf_bld.index

        if 'expstr' not in gdf_bld.columns:
            raise ValueError("Building data must contain 'expstr' column.")

        gdf_bld = gdf_bld.set_crs("EPSG:4326", allow_override=True).to_crs(f"EPSG:{epsg}")
        gdf_haz = gdf_haz.set_crs("EPSG:4326", allow_override=True).to_crs(f"EPSG:{epsg}")
        
        # Spatial join to find nearest hazard intensity
        gdf_building_intensity = gpd.sjoin_nearest(
            gdf_bld, gdf_haz, how='left', rsuffix='intensity', distance_col='distance'
        )
        gdf_building_intensity = gdf_building_intensity.drop_duplicates(subset=['bldid'], keep='first')
        
        if self.hazard_type == self.HAZARD_EARTHQUAKE:
            return self._calculate_earthquake(gdf_building_intensity, fragility, gem_fragility)
        elif self.hazard_type == self.HAZARD_FLOOD:
            return self._calculate_flood(gdf_building_intensity, fragility)
        else:
            raise ValueError(f"Hazard type {self.hazard_type} is not supported by DamageCalculator.")

    def _calculate_earthquake(self, bld_eq: gpd.GeoDataFrame, fragility, gem_fragility: bool) -> pd.DataFrame:
        normalization_factor = 9.81 if self.earthquake_intensity_unit == 'm/s2' else 1.0

        if not gem_fragility:
            fragility = fragility.copy()
            # Handle legacy taxonomy where TypeX might be RCi etc. 
            if 'expstr' in fragility.columns:
                fragility['expstr'] = fragility['expstr'].str.replace('Type[0-9]+','RCi',regex=True)
                fragility = fragility.drop_duplicates(subset=['expstr'])

            bld_eq = bld_eq.merge(fragility, on='expstr', how='left')
            
            med_cols = ['muds1_g','muds2_g','muds3_g','muds4_g']
            # Fallbacks for missing exposures
            nulls = bld_eq['muds1_g'].isna()
            bld_eq.loc[nulls, med_cols] = [0.048, 0.203, 0.313, 0.314]
            bld_eq.loc[nulls, ['sigmads1','sigmads2','sigmads3','sigmads4']] = [0.301, 0.276, 0.252, 0.253]
            
            for col in med_cols:
                bld_eq[col] = bld_eq[col].astype(float)
                
            # IM calculation
            sa_list = np.array([float(x.split()[-1]) for x in bld_eq.columns if x.startswith('sa ')])
            sa_cols = [x for x in bld_eq.columns if x.startswith('sa ') or x == 'pga']
            
            if len(sa_list) == 0:
                if 'im' in bld_eq.columns:
                    bld_eq['logim'] = np.log(bld_eq['im'] / normalization_factor)
                elif 'pga' in bld_eq.columns:
                    bld_eq['logim'] = np.log(bld_eq['pga'] / normalization_factor)
                else:
                    raise ValueError('No intensity measure found')
            else:
                for i, row in bld_eq.iterrows():
                    minp, maxp = row.get('minperiod', 0), row.get('maxperiod', 0)
                    if minp > 0 and maxp > 0 and maxp > minp:
                        x_interp = np.log(np.concatenate(([0.001], sa_list)))
                        y_interp = np.log(row[sa_cols].to_numpy(dtype=np.float32))
                        step = 0.01
                        x_required = np.log(np.linspace(minp, maxp, int((maxp - minp) / step + 1)))
                        sa_interp = np.exp(np.interp(x_required, x_interp, y_interp))
                        sa_gmean = np.prod(sa_interp)**(1/len(sa_interp))
                        bld_eq.at[i, 'logim'] = np.log(sa_gmean / normalization_factor)
                    else:
                        _pga = row.get('pga', row.get('im', 1))
                        bld_eq.at[i, 'logim'] = np.log(_pga / normalization_factor)

            for m in med_cols:
                bld_eq[m] = np.log(bld_eq[m])

            for i in [1, 2, 3, 4]:
                bld_eq[f'prob_ds{i}'] = norm.cdf(bld_eq['logim'], bld_eq[f'muds{i}_g'], bld_eq[f'sigmads{i}'])
        else:
            gem_df = pd.DataFrame(fragility['fragilityFunctions'])
            gem_df['imt_2'] = gem_df['imt'].str.replace('(', ' ', regex=False).str.replace(')', '', regex=False).str.lower()
            gem_df['imt_2'] = gem_df['imt_2'].apply(lambda x: f'sa {float(x.split()[-1]):.2f}' if x.startswith('sa ') else x)    
            bld_eq = bld_eq.merge(gem_df, how='left', left_on='expstr', right_on='id', validate="many_to_one")
            
            def compute_damage_state(row):
                intensity_in_g = row.get(row['imt_2'], 0) / normalization_factor
                prob_ds1 = np.interp(intensity_in_g, row['imls'], row['slight'])
                prob_ds2 = np.interp(intensity_in_g, row['imls'], row['moderate'])
                prob_ds3 = np.interp(intensity_in_g, row['imls'], row['extensive'])
                prob_ds4 = np.interp(intensity_in_g, row['imls'], row['complete'])
                return prob_ds1, prob_ds2, prob_ds3, prob_ds4
                
            bld_eq[['prob_ds1','prob_ds2','prob_ds3','prob_ds4']] = bld_eq.apply(compute_damage_state, axis=1, result_type='expand')

        # Simulation
        if self.earthquake_simulation_method.lower() == 'monte carlo':
            trials_ds = []
            for _ in range(self.number_of_trials):
                rnd = np.random.random(len(bld_eq))
                eq_ds = pd.concat(
                    [(rnd < bld_eq[f'prob_ds{i}']).astype(int) for i in [1, 2, 3, 4]], axis=1
                ).sum(axis=1)
                trials_ds.append(eq_ds)
            
            # Compute mode across trials
            df_modes = pd.DataFrame(trials_ds).mode(axis=0)
            bld_eq['ds'] = df_modes.iloc[0].astype(int)
        else:
            # Legacy expected damage state
            bld_eq[['prob_ds0','prob_ds5']] = [1,0]
            for i in [1, 2, 3, 4, 5]:
                bld_eq[f'ds_{i}'] = np.abs(bld_eq[f'prob_ds{i-1}'] - bld_eq[f'prob_ds{i}'])
            df_ds = bld_eq[['ds_1','ds_2','ds_3','ds_4','ds_5']]
            bld_eq['ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1

        return bld_eq[['bldid', 'ds']].reset_index(drop=True)

    def _calculate_flood(self, bld_flood: gpd.GeoDataFrame, vulnerability) -> pd.DataFrame:
        bld_flood = bld_flood.merge(vulnerability, on='expstr', how='left')
        
        away_from_flood = bld_flood['distance'] > self.threshold_flood_distance
        bld_flood.loc[away_from_flood, 'im'] = 0
        
        bld_flood.loc[bld_flood['im'] < 0, 'im'] = 0

        damage_curve_cols = ['hw0','hw0_5','hw1','hw1_5','hw2','hw3','hw4','hw5','hw6']
        missing_cols = [c for c in damage_curve_cols if c not in bld_flood.columns]
        if missing_cols:
            raise ValueError(f"Vulnerability data must contain columns: {damage_curve_cols}")
            
        x = np.array([0, 0.5, 1, 1.5, 2, 3, 4, 5, 6])
        y = bld_flood[damage_curve_cols].to_numpy()
        xnew = bld_flood['im'].to_numpy(dtype=np.float64)
        
        flood_mapping = interp1d(x, y, axis=1, kind='linear', bounds_error=False, fill_value=(0, 1))
        bld_flood['fl_prob'] = np.diag(flood_mapping(xnew))
        
        ds2_threshold, ds3_threshold, ds4_threshold = self.threshold_flood
        bld_flood['ds'] = bld_flood['fl_prob'].map(
            lambda val: self.DS_COMPLETE if val > ds4_threshold 
            else self.DS_EXTENSIVE if val > ds3_threshold 
            else self.DS_MODERATE if val > ds2_threshold 
            else self.DS_SLIGHT if val > 0 
            else self.DS_NO
        )
        
        return bld_flood[['bldid', 'ds']].reset_index(drop=True)
