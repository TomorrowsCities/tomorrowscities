"""Bounded upload staging and single-pass table parsing for interactive imports."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile

import geopandas as gpd
import pandas as pd

from .cloud_files import CLOUD_EXTENSIONS, cloud_key


UPLOAD_CHUNK_BYTES = 1024 * 1024


def _positive_limit(name, default):
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f'{name} must be a positive integer')
    return value


@contextmanager
def staged_upload(fileinfo):
    """Copy one browser upload to a temporary file, requesting at most 1 MiB at once.

    Byte-backed sample/cloud callers remain supported. Browser streams stay
    owned by the upload widget; staging never closes a caller-owned stream.
    """
    name = str(fileinfo['name'])
    suffix = Path(name).suffix.lower()
    if suffix not in {'.json', '.geojson', '.xlsx', '.xml', '.tif', '.tiff'}:
        raise ValueError(f'Unsupported file format: {suffix or name}')
    limit = _positive_limit('TC_MAX_UPLOAD_BYTES', 512 * 1024 * 1024)
    size = fileinfo.get('size', 0)
    if size and size > limit:
        raise ValueError(f'{name} exceeds the {limit // (1024 * 1024)} MiB upload limit. '
                         'Crop global rasters to the study area before uploading.')
    data = fileinfo.get('data')
    stream = fileinfo.get('file_obj')
    if data is None and stream is None:
        raise ValueError(f'{name}: no upload content was provided')
    with tempfile.TemporaryDirectory(prefix='tc-upload-') as folder:
        path = Path(folder) / ('input' + suffix)
        with path.open('wb') as target:
            if data is not None:
                if len(data) > limit:
                    raise ValueError(f'{name} exceeds the upload size limit')
                target.write(data)
            else:
                stream.seek(0)
                written = 0
                while True:
                    chunk = stream.read(UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > limit:
                        raise ValueError(f'{name} exceeds the upload size limit')
                    target.write(chunk)
        yield path


@contextmanager
def staged_cloud_upload(storage, path, cancelled=lambda: False):
    """Download bounded chunks into a private file; never retain a full byte copy."""
    key = cloud_key(path)
    name = key.rsplit('/', 1)[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in CLOUD_EXTENSIONS:
        raise ValueError(f'Unsupported cloud file format: {name}')
    limit = _positive_limit('TC_MAX_UPLOAD_BYTES', 512 * 1024 * 1024)
    if cancelled():
        raise InterruptedError('Cloud import cancelled')
    response = storage.get_client().get_object(Bucket=storage.bucket_name, Key=key)
    body = response['Body']
    try:
        expected = response.get('ContentLength')
        if expected is not None and expected > limit:
            raise ValueError(f'{name} exceeds the {limit // (1024 * 1024)} MiB upload limit')
        with tempfile.TemporaryDirectory(prefix='tc-cloud-') as folder:
            target_path = Path(folder) / ('input' + suffix)
            size = 0
            with target_path.open('wb') as target:
                while True:
                    if cancelled():
                        raise InterruptedError('Cloud import cancelled')
                    chunk = body.read(UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError(f'{name} exceeds the upload size limit')
                    target.write(chunk)
            if expected is not None and size != expected:
                raise ValueError(f'{name}: incomplete cloud download; please retry')
            with target_path.open('rb') as stream:
                yield {'name': name, 'size': size, 'data': None, 'file_obj': stream}
    finally:
        body.close()


def read_upload(path, raster_reader, xml_reader):
    """Preserve pandas JSON inference without parsing full JSON tables twice."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.xlsx':
        return pd.read_excel(path)
    if suffix in {'.tif', '.tiff'}:
        return raster_reader(path)
    if suffix == '.xml':
        return xml_reader(path.read_bytes())

    with path.open('rb') as source:
        prefix = source.read(64 * 1024)
    geojson = suffix == '.geojson' or bool(re.search(rb'"(?:features|FeatureCollection)"', prefix))
    if not geojson:
        try:
            frame = pd.read_json(path)
        except ValueError as table_error:
            # A GeoJSON file may use .json and have unusually long leading metadata.
            with path.open(encoding='utf-8-sig') as source:
                payload = json.load(source)
            if isinstance(payload, dict) and 'features' in payload:
                return gpd.GeoDataFrame.from_features(payload['features'])
            raise table_error
        if 'features' not in frame.columns:
            return frame
    with path.open(encoding='utf-8-sig') as source:
        payload = json.load(source)
    if isinstance(payload, dict) and 'features' in payload:
        return gpd.GeoDataFrame.from_features(payload['features'])
    # False positive in a table value: retain the usual pandas semantics.
    return pd.read_json(path)


def validate_raster_size(width, height, bands):
    limit = _positive_limit('TC_MAX_RASTER_VALUES', 10_000_000)
    if width * height * bands > limit:
        raise ValueError('Raster is too large for interactive import '
                         f'({width} x {height} x {bands}; limit {limit:,} values). '
                         'Crop it to the study area before uploading.')
