import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tomorrowcities.pages import connect_storage  # noqa: E402


def get_storage():
    storage = connect_storage()
    if storage is None:
        raise RuntimeError("S3 storage configuration could not be loaded.")
    return storage


def list_keys(client, bucket_name):
    keys = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def delete_all_objects(client, bucket_name, keys):
    for start in range(0, len(keys), 1000):
        batch = keys[start:start + 1000]
        client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )


def main():
    parser = argparse.ArgumentParser(description="Clear the configured S3 bucket.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only show how many objects are currently in the bucket.",
    )
    args = parser.parse_args()

    storage = get_storage()
    client = storage.get_client()
    keys = list_keys(client, storage.bucket_name)

    if args.check:
        print(f"bucket={storage.bucket_name}")
        print(f"remaining={len(keys)}")
        return

    delete_all_objects(client, storage.bucket_name, keys)
    print(f"bucket={storage.bucket_name}")
    print(f"deleted={len(keys)}")


if __name__ == "__main__":
    main()
