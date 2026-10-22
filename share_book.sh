#!/bin/bash

set -euo pipefail

# Make sure all 3 arguments were given
if [ $# -lt 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET_NAME EXPIRATION_SECONDS" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"

# Keep the file name from the end of the URL (e.g. pg1234.txt)
FILENAME="$(basename "$URL")"

# Download the book into the books/ folder
mkdir -p books
echo "Downloading $URL ..."
curl -fsSL -o "books/$FILENAME" "$URL"

# Create the bucket only if it doesn't already exist
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    echo "Creating bucket $BUCKET ..."
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book (it stays private) so browsers show it as text
echo "Uploading $FILENAME ..."
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Make a temporary link and print it
echo "Presigned URL (expires in $EXPIRES seconds):"
aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in "$EXPIRES"