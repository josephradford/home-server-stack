# iCloud Photos Backup

Two `icloudpd` containers (`icloudpd-a`, `icloudpd-b`) continuously download two
iCloud photo libraries to an external drive. Defined in `docker-compose.photos.yml`.

## What this protects against

`icloudpd` runs **download-only**. It never modifies or deletes local files, and
the `--auto-delete` / `--delete-after-download` flags are deliberately not used.

- **Protects against:** accidental deletion of photos in iCloud, Apple account
  lockout or loss, cloud-side library corruption. The local copy always remains.
- **Does NOT protect against:** loss of the backup drive itself (single copy —
  drive failure, theft, corruption, ransomware, or an accidental delete on the
  drive loses the backup), and point-in-time gaps (a photo deleted in iCloud
  before it was ever downloaded is never captured). This is not a 3-2-1 backup.
  A second rotated drive is the practical way to add durability later.
- **Partial mid-run protection:** a start-up guard plus a 5-minute re-check stop
  new writes if the backup drive drops out, but a write in the few-minute gap
  before detection could land on the server's system disk. Keep an eye on the
  dashboard tile.

## One-time setup

### 1. Mount the external drive

Find the drive UUID:

```bash
lsblk -f
```

Add to `/etc/fstab` (mount by UUID, `nofail` so a missing drive doesn't block
boot):

```
UUID=<drive-uuid>  /mnt/photos-backup  ext4  defaults,nofail  0  2
```

```bash
sudo mkdir -p /mnt/photos-backup
sudo mount -a
```

### 2. Create the drive sentinel

The containers refuse to run unless a sentinel file on the drive matches
`ICLOUD_BACKUP_DRIVE_ID`. Pick any unique string:

```bash
echo "photos-backup-drive-01" | sudo tee /mnt/photos-backup/.backup-drive
sudo mkdir -p /mnt/photos-backup/account-a /mnt/photos-backup/account-b
```

(the `account-a` / `account-b` directory names must match `ICLOUD_A_SUBDIR` /
`ICLOUD_B_SUBDIR` in `.env`.)

### 3. Configure `.env`

Set at least: `ICLOUD_BACKUP_ROOT`, `ICLOUD_BACKUP_DRIVE_ID` (must equal the
sentinel contents), `ICLOUD_A_USERNAME` / `ICLOUD_B_USERNAME`,
`ICLOUD_A_SUBDIR` / `ICLOUD_B_SUBDIR`, `ICLOUD_A_LABEL` / `ICLOUD_B_LABEL`, and
the `ICLOUD_SMTP_*` + `ICLOUD_NOTIFICATION_EMAIL` values. See `.env.example`.

The Apple ID **password is not set in `.env`** — it is entered in the web UI.

Any `$` characters in `.env` values (for example an SMTP password) must be
escaped as `$$` for Docker Compose — a stack-wide rule, see `.env.example`.

### 4. Start and authenticate

```bash
make start
```

Then, for each account:

1. Open `https://icloud-a.${DOMAIN}` (and `https://icloud-b.${DOMAIN}`).
   Access is restricted to the home network / VPN by the `admin-secure`
   middleware.
2. Enter the Apple ID password, then the 2FA code sent to a trusted device.
3. The container begins downloading. First run can take hours to days depending
   on library size.

## Re-authentication (about every 2 months)

Apple expires the session roughly every two months. When that happens:

- `icloudpd` sends an email to `ICLOUD_NOTIFICATION_EMAIL`.
- The Homepage **Backups** tile shows **Re-auth needed**.

To fix: open the relevant `https://icloud-a.${DOMAIN}` / `icloud-b` URL and
enter a fresh 2FA code. No restart needed.

## Dashboard status meaning

| Tile status | Meaning |
|-------------|---------|
| OK | Last sync cycle completed; `Last sync` shows when |
| Syncing | A download pass is in progress |
| Re-auth needed | Apple sign-in expired — open the web UI |
| Drive not mounted | Sentinel check failed — drive missing or wrong drive |
| Stopped | Container not running |
| Unknown | No recent log activity / cannot read state |

## Replacing the drive

1. Copy existing data to the new drive (`rsync -a /mnt/photos-backup/ /mnt/new/`).
2. Write the sentinel: `echo "<new-id>" > /mnt/new/.backup-drive`.
3. Update `/etc/fstab` with the new UUID and `ICLOUD_BACKUP_DRIVE_ID` in `.env`.
4. `sudo mount -a && make restart`.

## Logs

```bash
make logs-icloudpd
```
