# Inventory Capture

A local web app for tracking collectible inventory, storage locations, and availability. Built with FastAPI, Jinja2 templates, and SQLite; no frontend build step is required.

## Start or restart the app

On the remote machine, open Terminal (or connect over SSH) and run:

```sh
cd /Users/erickperales/Projects/inventory-capture
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On your other computer, open **http://REMOTE_MACHINE_IP:8000**, replacing `REMOTE_MACHINE_IP` with the remote machine's LAN or VPN IP address. For example, if its IP is `192.168.1.50`, open **http://192.168.1.50:8000**.

`0.0.0.0` makes the server listen on all network interfaces; use the machine's actual IP address in your browser. To find it, check the remote machine's network settings. On macOS, run `ipconfig getifaddr en0` for the common primary interface (if blank, check the active interface in System Settings → Network). On Linux, run `hostname -I` and choose the address reachable from your computer.

Keep the Terminal or SSH session running while using the app. For an SSH session that needs to survive disconnecting, run the startup command inside `tmux`, if installed.

To stop the app, press **Control+C** in the Terminal running it. To restart, run the same command again. The `--reload` option automatically restarts the server when Python source files change. Restarting does not erase saved inventory.

The command uses the project's existing virtual environment directly, so activation is unnecessary.

### If startup fails

- **Missing `.venv/bin/python` or missing packages:** follow the setup instructions below.
- **Address already in use:** check whether `http://REMOTE_MACHINE_IP:8000` already opens the app. Use `lsof -nP -iTCP:8000 -sTCP:LISTEN` to identify the process using that port. Stop it from its original Terminal if appropriate, or run this app with `--port 8001` and open `http://REMOTE_MACHINE_IP:8001` instead.
- **Cannot connect from another computer:** confirm both machines can reach each other over the LAN or VPN, the server was started with `--host 0.0.0.0`, and the remote machine's firewall allows inbound TCP port 8000 from your network.
- **Could not import module `app.main`:** make sure Terminal is in the project directory using the `cd` command above.

## Setup on a new machine or rebuild the environment

Install Python 3 (the existing environment uses Python 3.9.6), then run from the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then run the startup command above. Dependency versions are currently unpinned in `requirements.txt`.

## Using the app

- Add and edit inventory items. New items receive sequential IDs such as `0001`.
- Filter inventory by availability status and storage location.
- Update status and location directly from the inventory list.
- Record category, condition, notes, and whether a photo is on file.
- Record acquisition, listing, and sale details, including costs, prices, fees, and net profit.

Availability statuses are **In Stock**, **Reserved**, **Listed**, **Sold**, and **Kept**. The photo field is a checkbox; the app does not upload or store photos. There is no login; anyone who can reach the app can view and edit inventory. Use it on a trusted LAN or private VPN, and keep port 8000 off the public internet.

## Data and backups

Saved inventory lives in **`inventory.db`** in the project root. The app creates the database if it is missing and adds any missing supported columns at startup. The spreadsheet is an import source, not the live database.

To back up your inventory, stop the app and run from the project directory:

```sh
cp inventory.db "inventory-backup-$(date +%Y%m%d-%H%M%S).db"
```

Keep a copy somewhere safe. To restore a backup, stop the app, preserve the current database if needed, and copy the backup to `inventory.db` before restarting.

## Import a spreadsheet

The import script supports CSV and Excel (`.xlsx` / `.xlsm`) files. Back up the database before importing.

Preview an import:

```sh
.venv/bin/python import_data.py antiques_inventory.xlsx --dry-run
```

Import the rows:

```sh
.venv/bin/python import_data.py antiques_inventory.xlsx
```

Replace the filename with your own export as needed. Sample files are in `sample_data/`.

Existing item IDs are preserved, with numeric IDs padded to at least four digits. IDs already present in the database are skipped, and rows without IDs receive new IDs. Reimporting rows without IDs can create duplicates. Rows without a name are skipped; invalid statuses default to `In Stock`, and invalid numeric values are left blank with warnings. See `FIELD_ALIASES` in `import_data.py` for supported column names.

`--dry-run` previews rows without inserting them, but still initializes the database and applies any missing schema columns.

## Project files

| Path | Purpose |
| --- | --- |
| `app/main.py` | Web routes and form handling |
| `app/db.py` | SQLite schema and inventory queries |
| `app/templates/` | HTML pages |
| `import_data.py` | Spreadsheet import command |
| `requirements.txt` | Python dependencies |
| `inventory.db` | Live inventory data |
| `antiques_inventory.xlsx` | Existing spreadsheet import source |
| `sample_data/` | Example import files |
| `inventory-capture-app-prompt.md` | Original build brief; some features have since expanded |
