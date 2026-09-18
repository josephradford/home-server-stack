# iCloud Photos Backup

One `icloudpd` container backs up two iCloud photo libraries to an external
drive, processing both accounts sequentially each cycle (icloudpd's own
native multi-account support). Defined in `docker-compose.photos.yml`.

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

The container refuses to run unless a sentinel file on the drive matches
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
`ICLOUD_A_SUBDIR` / `ICLOUD_B_SUBDIR`, `ICLOUD_LABEL`, and the `ICLOUD_SMTP_*`
+ `ICLOUD_NOTIFICATION_EMAIL` values. See `.env.example`.

The Apple ID **passwords are not set in `.env`** — each is entered in the web
UI, one account at a time (see Step 4).

Any `$` characters in `.env` values (for example an SMTP password) must be
escaped as `$$` for Docker Compose — a stack-wide rule, see `.env.example`.

### 4. Start and authenticate

```bash
make start
```

Then open `https://icloud.${DOMAIN}` — access is restricted to the home
network / VPN by the `admin-secure` middleware. Because icloudpd processes
accounts sequentially, the web UI prompts for **account A first**; once that
password + 2FA code is entered, it moves on to **account B**. There is no
way to authenticate both at once — expect two separate password/2FA prompts,
one after the other, not simultaneously.

The container begins downloading once both are authenticated. First run can
take hours to days depending on library size.

## Re-authentication (about every 2 months)

Apple expires each account's session independently, roughly every two
months. When either needs it:

- `icloudpd` sends an email to `ICLOUD_NOTIFICATION_EMAIL`.
- The Homepage **Backups** tile shows **Re-auth needed** — this reflects the
  *worse* of the two accounts' states, so it doesn't say which account. If
  it's not obvious from context (e.g. you know account B just had its 2FA
  window expire), check `make logs-icloudpd` for the specific
  `Processing user: <email>` line the error appears under.

To fix: open `https://icloud.${DOMAIN}` and enter a fresh 2FA code for
whichever account needs it. No restart required.

## Dashboard status meaning

The tile shows one status covering both accounts — whichever is worse, by
this order (worst first): **Re-auth needed** > **Syncing** > **Unknown** >
**OK**. A drive problem or the container being stopped overrides both
accounts' states entirely.

| Tile status | Meaning |
|-------------|---------|
| OK | Both accounts' last sync cycle completed; `Last sync` shows the more recent of the two |
| Syncing | At least one account has a download pass in progress |
| Re-auth needed | At least one account's Apple sign-in expired — open the web UI |
| Drive not mounted | Sentinel check failed — drive missing or wrong drive |
| Stopped | Container not running |
| Unknown | No recent log activity for at least one account / cannot read state |

## Replacing the drive

1. Copy existing data to the new drive (`rsync -a /mnt/photos-backup/ /mnt/new/`).
2. Write the sentinel: `echo "<new-id>" > /mnt/new/.backup-drive`.
3. Update `/etc/fstab` with the new UUID and `ICLOUD_BACKUP_DRIVE_ID` in `.env`.
4. `sudo mount -a && make restart`.

## Logs

```bash
make logs-icloudpd
```

Each account's activity is marked by its own `Processing user: <email>` line
— search for the relevant address to see just that account's recent history.
