#!/bin/sh
# Copy Bursa's encrypted backups off this server with rclone (https://rclone.org),
# to any storage rclone supports (Google Drive, Backblaze B2, S3, another server...).
#
#   deploy/offsite-backup.sh <rclone-remote:path>      e.g. gdrive:bursa-backups
#
# Only `.age` files are copied (BACKUP_RECIPIENT set): an unencrypted backup holds
# every account and portfolio and never leaves the machine. Uses `rclone copy`,
# so backups pruned here stay there; tidy the remote yourself now and then (or
# set a lifecycle rule on it). Run it from cron after the 02:30 backup, e.g.
#   15 4 * * * /home/bursa/bursa/deploy/offsite-backup.sh gdrive:bursa-backups
set -eu

remote="${1:?usage: $0 <rclone-remote:path>}"
dir="$(cd "$(dirname "$0")/.." && pwd)/backend/data/backups"

if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is not installed: https://rclone.org/install/" >&2
    exit 1
fi
if ! ls "$dir"/*.age >/dev/null 2>&1; then
    echo "No encrypted (.age) backups in $dir: set BACKUP_RECIPIENT first" >&2
    exit 1
fi

rclone copy "$dir" "$remote" --include "*.age" --max-age 8d --log-level NOTICE
echo "Copied encrypted backups to $remote"
