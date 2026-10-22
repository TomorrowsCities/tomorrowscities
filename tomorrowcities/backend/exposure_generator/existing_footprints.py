"""Generate linked exposure on existing footprints, without placing new geometry.

The profile supplies regional demographic marginals and explicit scenario
assumptions. Structural classes, income and untagged uses remain synthetic.
Gender codes follow data_processing: 1=female, 2=male. Age is a category;
age_years retains the sampled age so the category definition is auditable.
"""

import re

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .logging_utils import log_info
from .utilities import dist2vector


INCOMES = ["veryLowIncome", "lowIncome", "midIncome", "highIncome"]
EDUCATION = {"school", "college", "university", "kindergarten", "childcare"}
HEALTH = {"hospital", "clinic", "doctors", "dentist", "nursing_home"}
NON_OCCUPIED = {"no", "construction", "roof", "shed", "storage_tank", "wall", "ruins"}
RESIDENTIAL = {"apartments", "residential", "house", "detached", "terrace", "bungalow", "cabin", "dormitory"}
COMMERCIAL = {"commercial", "retail", "office", "hotel", "supermarket", "transportation", "train_station",
              "government", "church", "mosque", "temple", "stadium", "fire_station", "parking", "service"}


def _balanced(values, probabilities, count, rng):
    """Use the exposure core's count allocator with a local random generator."""
    if count == 0:
        return np.asarray([], dtype=np.asarray(values).dtype)
    p = np.asarray(probabilities, dtype=float)
    if len(p) != len(values) or not np.isfinite(p).all() or (p < 0).any() or p.sum() <= 0:
        raise ValueError("Invalid profile probability distribution")
    result = np.asarray(dist2vector(values, p / p.sum() * count, count, "no_shuffle"))
    return rng.permutation(result)


def _tags(row):
    tags = dict(re.findall(r'"([^"\\]+)"=>"((?:\\.|[^"\\])*)"', str(row.get("other_tags", ""))))
    for key in ("amenity", "building", "office", "shop", "craft", "tourism", "landuse",
                "building:levels", "height", "building:use", "building:material", "material"):
        value = row.get(key)
        if pd.notna(value) and str(value).strip():
            tags[key] = str(value).lower().strip()
    return {k: str(v).lower().strip() for k, v in tags.items()}


def _use(tags, landuse):
    amenity, building = tags.get("amenity", ""), tags.get("building", "")
    if building in NON_OCCUPIED:
        return "Com", "osm_non_occupied", False
    if amenity:
        if amenity in EDUCATION:
            return "Edu", "osm_amenity", True
        if amenity in HEALTH:
            return "Hea", "osm_amenity", True
        # The application has six occupancy classes. Civic/religious/transport
        # uses have no separate class and use non-residential Com as a proxy.
        return "Com", "osm_amenity_nonres_proxy", True
    for key in ("building:use", "building"):
        value = tags.get(key, "")
        if value in EDUCATION:
            return "Edu", "osm_" + key, True
        if value in HEALTH:
            return "Hea", "osm_" + key, True
        if value in RESIDENTIAL:
            return "Res", "osm_" + key, True
        if value in {"industrial", "warehouse", "factory", "farm"}:
            return "Ind", "osm_" + key, True
        if value in COMMERCIAL:
            return "Com", "osm_" + key, True
        if value in {"mixed", "mixed_use", "residential;commercial"}:
            return "ResCom", "osm_" + key, True
    if tags.get("craft"):
        return "Ind", "osm_craft", True
    if any(tags.get(key) for key in ("shop", "office", "tourism")):
        return "Com", "osm_activity", True
    if landuse in {"hospital", "healthcare", "health"}:
        return "Hea", "landuse_inferred", True
    if landuse in {"school", "college", "education", "educational"}:
        return "Edu", "landuse_inferred", True
    if landuse in {"industrial", "industrial area"}:
        return "Ind", "landuse_inferred", True
    if landuse in {"retail", "commercial", "commercial area"}:
        return "Com", "landuse_inferred", True
    if landuse in {"mixed use", "mixed_use"}:
        return "ResCom", "landuse_inferred", True
    if landuse in {"water body", "water", "vegetation", "forest", "cropland", "fallow land"}:
        return "Com", "nonurban_landuse_proxy", False
    return "Res", "profile_inferred", True


def _levels(tags):
    raw = str(tags.get("building:levels", "")).lower().strip()
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        levels = int(np.ceil(float(raw)))
        if 1 <= levels <= 200:
            return levels, "osm_building_levels"
    ground = re.fullmatch(r"g\s*\+\s*(\d+)", raw)
    if ground and 0 <= int(ground[1]) < 200:
        return int(ground[1]) + 1, "osm_ground_plus_levels"
    height = str(tags.get("height", "")).lower().strip()
    if re.fullmatch(r"\d+(\.\d+)?\s*m?", height):
        metres = float(height.rstrip("m").strip())
        if 2.5 <= metres <= 600:
            return max(1, int(round(metres / 3.0))), "osm_height_3m_per_storey"
    return None, "profile_inferred"


def _assign_zones(buildings, landuse, metric_crs):
    points = buildings[["geometry"]].copy()
    points.geometry = points.geometry.representative_point()
    matches = gpd.sjoin(points, landuse[["zoneid", "geometry"]], how="left", predicate="intersects")
    if matches.zoneid.isna().any():
        missing = matches.index[matches.zoneid.isna()].tolist()
        raise ValueError(f"Footprints outside landuse coverage: {missing[:10]}")
    # Resolve overlapping landuse zones by the largest footprint intersection.
    duplicate_indices = matches.index[matches.index.duplicated()].unique()
    if len(duplicate_indices):
        bm, lm = buildings.to_crs(metric_crs), landuse.to_crs(metric_crs)
        selected = []
        for idx in duplicate_indices:
            candidates = matches.loc[[idx]]
            areas = [bm.geometry.loc[idx].intersection(lm.geometry.loc[int(j)]).area for j in candidates.index_right]
            selected.append((idx, int(candidates.iloc[int(np.argmax(areas))].zoneid)))
        matches = matches[~matches.index.isin(duplicate_indices)]
        resolved = pd.Series(dict(selected))
    else:
        resolved = pd.Series(dtype="int64")
    zones = matches.zoneid.reindex(buildings.index)
    zones.loc[resolved.index] = resolved
    return zones.astype("int64"), set(duplicate_indices)


def _nearest_ids(buildings, use):
    facilities = buildings[buildings.occbld.isin(use) & buildings.active]
    if facilities.empty:
        return np.full(len(buildings), -1, dtype="int64")
    xy = np.column_stack((buildings.geometry.centroid.x, buildings.geometry.centroid.y))
    facility_xy = np.column_stack((facilities.geometry.centroid.x, facilities.geometry.centroid.y))
    _, indices = cKDTree(facility_xy).query(xy)
    return facilities.bldid.to_numpy()[indices]


def process_existing_footprints(buildings, landuse, profile, seed=42):
    """Return buildings, households, individuals, landuse on unchanged geometry.

    Profile fields describe probability distributions, occupancy assumptions,
    dwelling sizes and replacement costs. No municipality-wide population is
    assigned to a smaller study area: households follow estimated floor space.
    The optional target_households rescales residential capacity by building.
    """
    if buildings.empty or landuse.empty or buildings.crs is None or landuse.crs is None:
        raise ValueError("Non-empty georeferenced building and landuse layers are required")
    if not buildings.geometry.is_valid.all() or not landuse.geometry.is_valid.all():
        raise ValueError("Repair invalid input geometry explicitly before generation")
    if not buildings.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Existing footprints must be polygons")
    rng = np.random.default_rng(seed)
    b = buildings.copy().reset_index(drop=True)
    l = landuse.to_crs(b.crs).copy().reset_index(drop=True)
    l["source_luf"] = l.luf.astype(str)
    l["zoneid"] = np.arange(1, len(l) + 1, dtype="int64")
    b["bldid"] = np.arange(1, len(b) + 1, dtype="int64")
    b["zoneid"], overlapping = _assign_zones(b, l, profile["metric_crs"])
    b["zone_source"] = ["largest_overlap" if i in overlapping else "representative_point" for i in b.index]
    source_luf = b.zoneid.map(l.set_index("zoneid").source_luf).str.lower()
    all_tags = [_tags(row) for _, row in b.iterrows()]
    uses = [_use(tags, lu) for tags, lu in zip(all_tags, source_luf)]
    b[["occbld", "use_source", "active"]] = pd.DataFrame(uses, index=b.index)
    inferred = b.use_source.eq("profile_inferred")
    b.loc[inferred, "occbld"] = _balanced(["Res", "ResCom", "Com", "Ind"], profile["unknown_urban_occupancy"], int(inferred.sum()), rng)
    b["specialfac"] = b.occbld.map({"Edu": 1, "Hea": 2}).fillna(0).astype("int64")
    bm = b.to_crs(profile["metric_crs"])
    b["fptarea"] = bm.geometry.area.to_numpy()
    levels = [_levels(tags) for tags in all_tags]
    b["nstoreys"] = [item[0] or 0 for item in levels]
    b["storeys_source"] = [item[1] for item in levels]
    for key, selector in [("small", b.fptarea < 150), ("medium", b.fptarea.between(150, 600, inclusive="left")), ("large", b.fptarea >= 600)]:
        mask = selector & b.nstoreys.eq(0)
        model = profile["storeys"][key]
        b.loc[mask, "nstoreys"] = _balanced(model["values"], model["probabilities"], int(mask.sum()), rng)
    b["nstoreys"] = b.nstoreys.astype("int64")
    b["income_assumption"] = _balanced(INCOMES, profile["income_probabilities"], len(b), rng)
    b["lrstype"] = _balanced(profile["structure"]["values"], profile["structure"]["probabilities"], len(b), rng)
    b["structure_source"] = "profile_inferred"
    for i, tags in enumerate(all_tags):
        material = tags.get("building:material", tags.get("material", ""))
        value = {"concrete": "RConcrete", "reinforced_concrete": "RConcrete", "brick": "Masonry", "bricks": "Masonry", "stone": "Masonry", "steel": "Steel"}.get(material)
        if value:
            b.loc[i, ["lrstype", "structure_source"]] = [value, "osm_material_proxy"]
    b["codelevel"] = _balanced(["LC", "MC", "HC"], profile["code_level_probabilities"], len(b), rng)
    b["code_source"] = "profile_inferred"
    b["expstr"] = b.lrstype + "+" + b.codelevel + "+" + b.nstoreys.astype(str) + "s+" + b.occbld
    b["unit_price"] = b.occbld.map(profile["replacement_cost_per_m2"])
    b["repvalue"] = b.fptarea * b.nstoreys * b.unit_price
    b["repvalue_currency"] = profile["currency"]
    fraction = b.occbld.map({"Res": 1.0, "ResCom": profile["mixed_residential_fraction"]}).fillna(0)
    floor_area = b.fptarea * b.nstoreys * fraction * profile["net_floor_area_ratio"]
    capacity = np.floor(floor_area / b.income_assumption.map(profile["dwelling_area_m2"])).astype("int64")
    capacity.loc[~b.active | (b.fptarea < profile["minimum_occupied_footprint_m2"])] = 0
    if profile.get("target_households") is not None:
        target = int(profile["target_households"])
        if target <= 0 or capacity.sum() == 0:
            raise ValueError("target_households requires positive residential capacity")
        # A target must not exceed estimated physical capacity.
        if target > capacity.sum():
            raise ValueError("target_households exceeds estimated dwelling capacity")
        scaled = capacity / capacity.sum() * target
        rounded = np.floor(scaled).astype("int64")
        order = (scaled - rounded).sort_values(ascending=False, kind="stable").index
        rounded.loc[order[:target - int(rounded.sum())]] += 1
        capacity = rounded
    b["nhouse"] = capacity
    b["population_source"] = "synthetic_floor_space_capacity"
    household_building_indices = np.repeat(b.index.to_numpy(), capacity.to_numpy())
    h = pd.DataFrame({"bldid": b.bldid.to_numpy()[household_building_indices]})
    if h.empty:
        raise ValueError("No residential households can be generated")
    h["hhid"] = np.arange(1, len(h) + 1, dtype="int64")
    h["income"] = b.income_assumption.to_numpy()[household_building_indices]
    h["nind"] = _balanced(profile["household_sizes"], profile["household_size_probabilities"], len(h), rng).astype("int64")
    log_info(f"Existing footprints: {len(b)} buildings, {len(h)} households, {int(h.nind.sum())} individuals")
    bm = b.to_crs(profile["metric_crs"])
    h["commfacid"] = _nearest_ids(bm, ["Hea"])[household_building_indices]
    person_hh_indices = np.repeat(h.index.to_numpy(), h.nind.to_numpy())
    n = len(person_hh_indices)
    i = pd.DataFrame({"individ": np.arange(1, n + 1, dtype="int64"), "hhid": h.hhid.to_numpy()[person_hh_indices]})
    i["gender"] = _balanced([1, 2], [profile["female_fraction"], 1 - profile["female_fraction"]], n, rng).astype("int64")
    age_group = _balanced(np.arange(len(profile["age_year_ranges"])), profile["age_probabilities"], n, rng)
    ages = np.empty(n, dtype="int64")
    for code, (lower, upper) in enumerate(profile["age_year_ranges"]):
        mask = age_group == code
        ages[mask] = rng.integers(lower, upper + 1, size=int(mask.sum()))
    head_positions = np.r_[0, h.nind.cumsum().to_numpy()[:-1]]
    is_head = np.zeros(n, dtype=bool)
    is_head[head_positions] = True
    child_heads = head_positions[ages[head_positions] < 18]
    adult_others = np.flatnonzero((ages >= 18) & ~is_head)
    if len(child_heads) > len(adult_others):
        raise ValueError("Age profile cannot supply one adult per household")
    replacements = rng.choice(adult_others, len(child_heads), replace=False)
    ages[child_heads], ages[replacements] = ages[replacements].copy(), ages[child_heads].copy()
    # Swap genders to reach the assumed female-headed-household share while
    # preserving the official regional sex marginal exactly.
    target_female_heads = round(len(h) * profile["female_head_fraction"])
    gender = i.gender.to_numpy(copy=True)
    difference = target_female_heads - int((gender[head_positions] == 1).sum())
    from_gender, to_gender = (2, 1) if difference > 0 else (1, 2)
    source = head_positions[gender[head_positions] == from_gender]
    donors = np.flatnonzero(~is_head & (gender == to_gender))
    count = min(abs(difference), len(source), len(donors))
    selected_heads = rng.choice(source, count, replace=False)
    selected_donors = rng.choice(donors, count, replace=False)
    gender[selected_heads], gender[selected_donors] = to_gender, from_gender
    i["gender"], i["age_years"], i["head"] = gender, ages, is_head.astype("int64")
    i["age"] = np.searchsorted(profile["age_category_upper_bounds"], ages, side="left") + 1
    education = np.ones(n, dtype="int64")
    for gender_code, literacy in [(1, profile["female_literacy_7plus"]), (2, profile["male_literacy_7plus"])]:
        eligible = np.flatnonzero((gender == gender_code) & (ages >= 7))
        literate = _balanced([0, 1], [1 - literacy, literacy], len(eligible), rng).astype(bool)
        recipients = eligible[literate]
        education[recipients] = _balanced([2, 3, 4, 5], profile["literate_education_probabilities"], len(recipients), rng)
    education[(ages < 11) & (education > 2)] = 2
    education[(ages < 15) & (education > 3)] = 3
    education[(ages < 21) & (education > 4)] = 4
    i["eduattstat"] = education
    person_building_indices = household_building_indices[person_hh_indices]
    schools = _nearest_ids(bm, ["Edu"])[person_building_indices]
    workplaces = _nearest_ids(bm, ["Com", "Ind", "ResCom"])[person_building_indices]
    enrolled = ((ages >= 6) & (ages <= 17) & (rng.random(n) < profile["school_enrollment_6_17"])) | ((ages >= 18) & (ages <= 21) & (rng.random(n) < profile["tertiary_enrollment_18_21"]))
    employment_probability = np.where(gender == 1, profile["female_employment_18_64"], profile["male_employment_18_64"])
    employed = (ages >= 18) & (ages <= 64) & ~enrolled & (rng.random(n) < employment_probability)
    i["indivfacid_1"] = np.where(enrolled, schools, -1)
    i["indivfacid_2"] = np.where(employed, workplaces, -1)
    i["indivfacid"] = np.where(employed, i.indivfacid_2, i.indivfacid_1)
    residents = h.groupby("bldid").nind.sum()
    b["residents"] = b.bldid.map(residents).fillna(0).astype("int64")
    l["luf"] = l.source_luf.str.lower().map(profile["landuse_mapping"]).fillna(l.source_luf)
    lm = l.to_crs(profile["metric_crs"])
    l["area"] = lm.geometry.area / 10000.0
    l["population"] = l.zoneid.map(b.groupby("zoneid").residents.sum()).fillna(0).astype("int64")
    l["population_source"] = "sum_synthetic_building_residents"
    l["densitycap"] = l.population / l["area"]
    l["floorarear"] = l.zoneid.map((b.fptarea * b.nstoreys).groupby(b.zoneid).sum()).fillna(0) / (l["area"] * 10000)
    l["floorarat"] = l.floorarear  # Existing engine UI spelling.
    l["setback"] = 0.0  # No placement or displacement of the existing stock.
    hh_zones = h.bldid.map(b.set_index("bldid").zoneid)
    modes = h.assign(zoneid=hh_zones).groupby("zoneid").income.agg(lambda values: values.mode().iloc[0])
    l["avgincome"] = l.zoneid.map(modes).fillna("midIncome")
    l["income_source"] = "mode_synthetic_household_income"
    return b, h, i, l
