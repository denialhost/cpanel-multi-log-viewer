Multi Log Viewer (MLV) v1.1.5 for cPanel/WHM
===========================================

This project provides a WHM plugin that centralizes access to the most relevant
server logs (cPanel, Apache, Nginx, firewall, and more). From the browser you can
list available files, view the latest lines, perform filtered searches, detect
compressed logs (.gz/.bz2/.xz) and download them safely for offline review.

**Version:** 1.1.5  
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

## Installation

1. **Download the plugin package:**

   ```bash
   wget https://github.com/denialhost/cpanel-multi-log-viewer/releases/latest/download/cpanel-multi-log-viewer.tar.gz
   ```

2. **Extract the archive:**

   ```bash
   tar -xzf cpanel-multi-log-viewer.tar.gz
   ```

3. **Run the installer:**

   ```bash
   cd cpanel-multi-log-viewer
   chmod +x install.sh
   ./install.sh
   ```

4. **Access the plugin:**
   - Log in to WHM as `root`
   - Navigate to **Plugins → Multi Log Viewer** in the left sidebar

## Upgrade

If you already have the plugin installed, you can upgrade it using the built-in updater or manually:

**Method 1: Using the web updater (recommended)**
- Open the plugin in WHM
- Click the "Update Plugin" button if a new version is available

**Method 2: Manual upgrade via SSH**

```bash
wget https://github.com/denialhost/cpanel-multi-log-viewer/releases/latest/download/cpanel-multi-log-viewer.tar.gz
tar -xzf cpanel-multi-log-viewer.tar.gz
cd cpanel-multi-log-viewer
chmod +x install.sh
./install.sh --upgrade
```

The installer automatically:

- creates a backup of the current installation
- removes the previous version
- installs the new version
- restores configuration files

**Note:** If you run `./install.sh` without options and the plugin is already installed, it will automatically detect and perform an upgrade.

## Uninstallation

```bash
cd /root/cpanel-multi-log-viewer
chmod +x install.sh
./install.sh --uninstall
```

## Reinstallation

To completely remove and reinstall the plugin:

```bash
cd /root/cpanel-multi-log-viewer
chmod +x install.sh
./install.sh --reinstall
```

**Note:** `upgrade.sh` and `uninstall.sh` are wrapper scripts that call `install.sh` with the appropriate options. You can use either method.

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

