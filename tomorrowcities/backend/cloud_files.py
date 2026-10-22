"""S3 sample-file paths and directory listing, independent of the host OS."""

from pathlib import PurePosixPath
import posixpath
from uuid import uuid4


CLOUD_EXTENSIONS = {'.xlsx', '.geojson', '.json', '.xml', '.tif', '.tiff'}


def cloud_path(path='/'):
    # S3 keys use forward slashes even when the app runs on Windows.
    text = str(path or '/').replace('\\', '/')
    return PurePosixPath(posixpath.normpath('/' + text.lstrip('/')))


def cloud_key(path):
    return str(cloud_path(path)).lstrip('/')


def cloud_import_sources(storage, paths, folder_batch=False):
    """Queue file references only; each request can be retried without reusing bytes."""
    request_id = uuid4().hex
    return [{'name': cloud_path(path).name, 'cloud_path': str(cloud_path(path)),
             'cloud_storage': storage, 'request_id': request_id,
             'cloud_folder_batch': folder_batch} for path in paths]


def validate_cloud_drop_paths(paths):
    """Accept only supported sample-input paths from a browser drag payload."""
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        raise ValueError('Choose one or more cloud input files')
    root = PurePosixPath('/datastore')
    result = []
    for text in paths:
        path = cloud_path(text)
        if root not in path.parents or path.suffix.lower() not in CLOUD_EXTENSIONS:
            raise ValueError('Only files from the cloud sample folders can be dropped here')
        if path not in result:
            result.append(path)
    if len({path.parent for path in result}) != 1:
        raise ValueError('Choose files from a single cloud folder')
    return result


def list_cloud_directory(storage, path, filter=lambda path: True, directory_first=False):
    """List immediate children, including empty folders and all S3 result pages."""
    if storage is None:
        raise ValueError('Cloud storage is not connected')
    directory = cloud_path(path)
    prefix = cloud_key(directory)
    if prefix:
        prefix += '/'
    entries = {}
    paginator = storage.get_client().get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=storage.bucket_name, Prefix=prefix, Delimiter='/'):
        for folder in page.get('CommonPrefixes', []):
            name = folder['Prefix'][len(prefix):].rstrip('/')
            if name and '/' not in name:
                entries[(name, False)] = {'name': name, 'is_file': False}
        for item in page.get('Contents', []):
            name = item['Key'][len(prefix):]
            if not name or '/' in name:
                continue
            candidate = directory / name
            if candidate.suffix.lower() in CLOUD_EXTENSIONS and filter(candidate):
                entries[(name, True)] = {'name': name, 'is_file': True}
    return sorted(entries.values(), key=lambda item: (item['is_file'] == directory_first, item['name'].lower()))
