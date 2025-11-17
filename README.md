Multi Log Viewer (MLV) v1.1.3 for cPanel/WHM
===========================================

This project provides a WHM plugin that centralizes access to the most relevant
server logs (cPanel, Apache, Nginx, firewall, and more). From the browser you can
list available files, view the latest lines, perform filtered searches, detect
compressed logs (.gz/.bz2/.xz) and download them safely for offline review.

**Version:** 1.1.3  
**Internal name:** mlv  

## Requirements

- cPanel & WHM server (118 or newer recommended)
- SSH access as `root`
- Perl 5 (bundled with cPanel) and standard utilities (`stat`, `tar`, etc.)

## Directory layout

```
appconfig/
  mlv.conf                        # WHM AppConfig registration
whostmgr/docroot/cgi/mlv/
  mlv.cgi                         # HTML frontend + API endpoints
  assets/
    app.js                       # Client-side logic
    style.css                    # Stylesheet
  config/
    log_sources.json             # Log catalog
  lib/
    LogReader.pm                 # Helpers to read/search logs
install.sh                       # Installer
uninstall.sh                     # Uninstaller
```

## Packaging the tar.gz

**Important:** ensure the tarball contains the root directory
`cpanel-multi-log-viewer/`. Dropping files at the archive root will break the
installer.

### Method 1: script (recommended)

```bash
# From inside the project directory
cd cpanel-multi-log-viewer
chmod +x MAKE_TAR.sh
./MAKE_TAR.sh
```

The script validates the structure and prints diagnostics for each step.

### Method 2: manual command

Run from the parent directory:

```bash
# Expected tree
# /path/
#   cpanel-multi-log-viewer/
#     install.sh
#     whostmgr/
#     appconfig/

cd /path
tar -czf cpanel-multi-log-viewer.tar.gz cpanel-multi-log-viewer/
```

**Check the contents:**

```bash
tar -tzf cpanel-multi-log-viewer.tar.gz | head -5
# cpanel-multi-log-viewer/
# cpanel-multi-log-viewer/install.sh
# cpanel-multi-log-viewer/whostmgr/
# cpanel-multi-log-viewer/appconfig/
```

If you see `install.sh` at the root level the archive is malformed.

## Quick upgrade

```bash
wget https://github.com/denialhost/cpanel-multi-log-viewer/releases/latest/download/cpanel-multi-log-viewer.tar.gz
tar -xzf cpanel-multi-log-viewer.tar.gz
cd cpanel-multi-log-viewer
chmod +x upgrade.sh
./upgrade.sh
```

`upgrade.sh` automatically

- creates a backup of the current installation
- downloads the latest package
- removes the previous version
- installs the new version
- restores configuration files

To use a custom package URL:

```bash
./upgrade.sh https://your-server.com/plugin.tar.gz
```

To restore from a backup:

```bash
./upgrade.sh --restore /root/.mlv_backup_YYYYMMDD_HHMMSS
```

## Installation

1. Upload the folder `cpanel-multi-log-viewer` to the server (e.g. `/root`).
2. Run the installer:

   ```bash
   cd /root/cpanel-multi-log-viewer
   chmod +x install.sh
   ./install.sh
   ```

3. Log in to WHM as `root` and open **Plugins → Multi Log Viewer**.

## Uninstallation

```bash
cd /root/cpanel-multi-log-viewer
chmod +x uninstall.sh
./uninstall.sh
```

## Log configuration

`config/log_sources.json` controls which log files appear in the UI. Each entry
includes an `id`, a descriptive `name`, and the filesystem `path`. Edit the list
to match your environment; changes take effect immediately.

Example:

```json
{
  "logs": [
    { "id": "cpanel-access", "name": "cPanel Access Log", "path": "/usr/local/cpanel/logs/access_log" },
    { "id": "apache-error", "name": "Apache Error Log", "path": "/etc/apache2/logs/error_log" }
  ]
}
```

## Security notes

- Designed to run inside WHM, so `root` privileges are required.
- Only paths listed in `log_sources.json` are accessible—no arbitrary file reads.
- Keep the deployment directory owned by `root` and restrict write access.
- The "Search All" button tail-searches each configured log (limited lines) and
  groups matches per file.

## Roadmap ideas

- Pagination and search history
- Full-file download from the UI
- Quick metrics (match counts, log sizes, etc.)

## License and contributions

Multi Log Viewer is released as open-source software under the MIT License (see
the `LICENSE` file). Free use, modification, and redistribution are encouraged—
the goal of the project is to simplify server administration, not to generate
profit. Contributions, bug reports, or enhancements are welcome; feel free to
share updates through pull requests or forks.

