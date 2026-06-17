# Clear S3 Bucket Helper

This folder includes a small helper script for clearing the S3 bucket configured by the app environment.

## Purpose

Use this script when you want to remove all objects from the configured bucket without opening the app UI.

## Commands

Clear the bucket:

```powershell
python scripts/clear_s3_bucket.py
```

Check how many objects are currently in the bucket:

```powershell
python scripts/clear_s3_bucket.py --check
```

## What Each Command Does

- `python scripts/clear_s3_bucket.py`
  Deletes every object currently stored in the configured S3 bucket and prints how many objects were removed.

- `python scripts/clear_s3_bucket.py --check`
  Does not delete anything. It only prints the bucket name and the current number of remaining objects.

## Notes

- The script reads the same AWS and bucket configuration used by the application.
- Deletion is permanent for the current bucket objects unless versioning or recovery policies are configured separately in AWS.
- If the bucket is already empty, the delete command will simply report `deleted=0`.
