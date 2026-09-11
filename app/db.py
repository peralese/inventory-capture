import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "inventory.db"

ALLOWED_STATUSES = ["In Stock", "Reserved", "Listed", "Sold", "Kept"]

# Acquisition/listing/sale fields. Originally out of scope for this app (they
# belong to the other Collectibles Suite tools), added back in at the user's
# request once a single real spreadsheet turned out to combine both.
EXTRA_COLUMNS = [
    ("acquired_date", "TEXT"),
    ("acquired_from", "TEXT"),
    ("acquisition_cost", "REAL"),
    ("listed", "INTEGER NOT NULL DEFAULT 0"),
    ("listing_platform", "TEXT"),
    ("listing_price", "REAL"),
    ("listing_date", "TEXT"),
    ("sold_date", "TEXT"),
    ("sold_price", "REAL"),
    ("fees_shipping_cost", "REAL"),
    ("net_profit", "REAL"),
    ("final_disposition", "TEXT"),
]

TEXT_EXTRA_FIELDS = ["acquired_date", "acquired_from", "listing_platform", "listing_date",
                      "sold_date", "final_disposition"]
NUMERIC_EXTRA_FIELDS = ["acquisition_cost", "listing_price", "sold_price",
                         "fees_shipping_cost", "net_profit"]
BOOL_EXTRA_FIELDS = ["listed"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    storage_location TEXT,
    availability_status TEXT NOT NULL DEFAULT 'In Stock',
    condition TEXT,
    photo_on_file INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    acquired_date TEXT,
    acquired_from TEXT,
    acquisition_cost REAL,
    listed INTEGER NOT NULL DEFAULT 0,
    listing_platform TEXT,
    listing_price REAL,
    listing_date TEXT,
    sold_date TEXT,
    sold_price REAL,
    fees_shipping_cost REAL,
    net_profit REAL,
    final_disposition TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection):
    """Add any EXTRA_COLUMNS missing from an existing items table."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    for col_name, col_type in EXTRA_COLUMNS:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}")
    conn.commit()


def init_db():
    conn = get_connection()
    try:
        conn.execute(SCHEMA)
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()


def next_item_id(conn: sqlite3.Connection) -> str:
    """Compute the next sequential zero-padded 4-digit item_id.

    Only considers existing item_ids that are purely numeric so imported
    rows with unexpected id formats don't break the sequence.
    """
    rows = conn.execute("SELECT item_id FROM items").fetchall()
    max_num = 0
    for row in rows:
        raw = row["item_id"]
        if raw and raw.isdigit():
            max_num = max(max_num, int(raw))
    return f"{max_num + 1:04d}"


def list_items(conn: sqlite3.Connection, availability_status: str = "", storage_location: str = ""):
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    if availability_status:
        query += " AND availability_status = ?"
        params.append(availability_status)
    if storage_location:
        query += " AND storage_location = ?"
        params.append(storage_location)
    query += " ORDER BY item_id"
    return conn.execute(query, params).fetchall()


def get_item(conn: sqlite3.Connection, item_id: str):
    return conn.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()


def distinct_storage_locations(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT DISTINCT storage_location FROM items "
        "WHERE storage_location IS NOT NULL AND storage_location != '' "
        "ORDER BY storage_location"
    ).fetchall()
    return [row["storage_location"] for row in rows]


def _extra_values(data: dict):
    """Pull the 12 acquisition/listing/sale fields out of `data` in column order."""
    values = []
    for col_name, _ in EXTRA_COLUMNS:
        if col_name in BOOL_EXTRA_FIELDS:
            values.append(1 if data.get(col_name) else 0)
        else:
            values.append(data.get(col_name) or None)
    return values


def create_item(conn: sqlite3.Connection, data: dict) -> str:
    item_id = next_item_id(conn)
    extra_cols = [c for c, _ in EXTRA_COLUMNS]
    conn.execute(
        f"""
        INSERT INTO items
            (item_id, name, category, storage_location, availability_status,
             condition, photo_on_file, notes, {', '.join(extra_cols)})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, {', '.join(['?'] * len(extra_cols))})
        """,
        (
            item_id,
            data["name"],
            data.get("category") or None,
            data.get("storage_location") or None,
            data["availability_status"],
            data.get("condition") or None,
            1 if data.get("photo_on_file") else 0,
            data.get("notes") or None,
            *_extra_values(data),
        ),
    )
    conn.commit()
    return item_id


def update_item(conn: sqlite3.Connection, item_id: str, data: dict):
    extra_cols = [c for c, _ in EXTRA_COLUMNS]
    extra_assignments = ", ".join(f"{c} = ?" for c in extra_cols)
    conn.execute(
        f"""
        UPDATE items SET
            name = ?,
            category = ?,
            storage_location = ?,
            availability_status = ?,
            condition = ?,
            photo_on_file = ?,
            notes = ?,
            {extra_assignments},
            updated_at = CURRENT_TIMESTAMP
        WHERE item_id = ?
        """,
        (
            data["name"],
            data.get("category") or None,
            data.get("storage_location") or None,
            data["availability_status"],
            data.get("condition") or None,
            1 if data.get("photo_on_file") else 0,
            data.get("notes") or None,
            *_extra_values(data),
            item_id,
        ),
    )
    conn.commit()


def quick_update_item(conn: sqlite3.Connection, item_id: str, availability_status: str = None, storage_location: str = None):
    fields = []
    params = []
    if availability_status is not None:
        fields.append("availability_status = ?")
        params.append(availability_status)
    if storage_location is not None:
        fields.append("storage_location = ?")
        params.append(storage_location)
    if not fields:
        return
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(item_id)
    conn.execute(f"UPDATE items SET {', '.join(fields)} WHERE item_id = ?", params)
    conn.commit()


def item_id_exists(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return row is not None
