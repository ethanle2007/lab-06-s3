#!/usr/bin/env python3

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

# Set up the logger (this prints status messages)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# One S3 client shared by all functions
s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    #Read the 3 command line arguments.
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py LIST_FILE INDEX_FILE BUCKET_NAME")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    #Download every book in list_file into dest_dir
    os.makedirs(dest_dir, exist_ok=True)
    paths = []

    # Read the URLs, skipping blank lines
    try:
        with open(list_file) as f:
            urls = [line.strip() for line in f if line.strip()]
    except OSError as e:
        log.error(f"Could not read {list_file}: {e}")
        return paths

    for url in urls:
        # Name the file after the last part of the URL
        path = os.path.join(dest_dir, url.split("/")[-1])

        # Skip books we already have
        if os.path.exists(path):
            log.info(f"Already have {path}, skipping")
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # error on 404 etc.
            with open(path, "wb") as f:
                f.write(response.content)
            log.info(f"Downloaded {path}")
            paths.append(path)
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")

        time.sleep(1)  # be nice to Gutenberg's servers

    return paths


def create_bucket(bucket):
    #Create the bucket unless it already exists.
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True
    except ClientError:
        log.info(f"Bucket {bucket} not found, creating it")

    # Create it
    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket {bucket}")
        return True
    except ClientError as e:
        log.error(f"Could not create bucket: {e}")
        return False


def make_public(bucket):
    #Turn off Block Public Access, then allow everyone to read objects.
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Bucket {bucket} is now public")
        return True
    except ClientError as e:
        log.error(f"Could not make bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    count = 0
    for path in file_paths:
        key = os.path.basename(path)  # pg1342.txt, not books/pg1342.txt
        try:
            s3.upload_file(
                path, bucket, key,
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            log.info(f"Uploaded {key}")
            count += 1
        except (ClientError, OSError) as e:
            log.error(f"Could not upload {path}: {e}")
    return count


def upload_index(bucket, index_path):
    try:
        s3.upload_file(
            index_path, bucket, "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )
        log.info("Uploaded index.html")
        return True
    except (ClientError, OSError) as e:
        log.error(f"Could not upload {index_path}: {e}")
        return False


def main():
    list_file, index_path, bucket = parse_args()

    paths = download_books(list_file, "books")
    if not paths:
        log.error("No books downloaded, stopping")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    uploaded = upload_files(bucket, paths)
    index_ok = upload_index(bucket, index_path)

    if index_ok and uploaded == len(paths):
        log.info("Success!")
    else:
        log.warning(f"Finished with problems: {uploaded}/{len(paths)} books uploaded")
    log.info(f"Public URL: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()