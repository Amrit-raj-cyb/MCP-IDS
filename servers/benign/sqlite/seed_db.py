"""Build the dummy SQLite database (synthetic data, deterministic).

The database is *generated*, not committed: ``build_database(path, seed)``
always produces the same rows for the same seed, so the dataset stays
reproducible and the repo holds no binary blobs. Each session gets a fresh
copy (see :mod:`common.lab_env`), so inserts in one session never leak into
the next.

All people, emails and products are invented. Emails use the reserved
``example.test`` domain, which can never belong to a real organisation.

Run:  python -m servers.benign.sqlite.seed_db database/dummy.db
"""

from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE users (
    id         INTEGER PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    email      TEXT NOT NULL,
    country    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    category TEXT NOT NULL,
    price    REAL NOT NULL CHECK (price > 0),
    stock    INTEGER NOT NULL CHECK (stock >= 0)
);
CREATE TABLE orders (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    order_date TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled'))
);
CREATE TABLE logs (
    id      INTEGER PRIMARY KEY,
    ts      TEXT NOT NULL,
    level   TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    message TEXT NOT NULL
);
"""

_FIRST = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi", "ivan", "judy",
          "mallory", "niaj", "olivia", "peggy", "rupert", "sybil", "trent", "victor", "walter", "zoe"]
_COUNTRIES = ["IN", "US", "DE", "BR", "JP", "KE", "FR", "AU"]
_PRODUCTS = [("Widget", "tools"), ("Gadget", "electronics"), ("Doohickey", "misc"),
             ("Gizmo", "electronics"), ("Sprocket", "tools"), ("Thingamajig", "misc"),
             ("Notebook", "stationery"), ("Pen Set", "stationery"), ("Cable", "electronics"),
             ("Lamp", "home")]
_LOG_MESSAGES = [("INFO", "user login"), ("INFO", "order created"), ("INFO", "report generated"),
                 ("WARNING", "slow query detected"), ("WARNING", "low stock"),
                 ("ERROR", "payment gateway timeout (simulated)"), ("DEBUG", "cache refreshed")]
_EPOCH = date(2026, 1, 1)


def build_database(path: Path, seed: int = 1234, n_users: int = 30,
                   n_products: int = 20, n_orders: int = 80, n_logs: int = 50) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO users VALUES (?,?,?,?,?)", [
            (i, f"{_FIRST[(i - 1) % len(_FIRST)]}_{i:02d}", f"user{i:02d}@example.test",
             rng.choice(_COUNTRIES), (_EPOCH + timedelta(days=rng.randint(0, 200))).isoformat())
            for i in range(1, n_users + 1)
        ])
        con.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
            (i, f"{_PRODUCTS[(i - 1) % len(_PRODUCTS)][0]} {chr(64 + (i - 1) // len(_PRODUCTS) + 1)}",
             _PRODUCTS[(i - 1) % len(_PRODUCTS)][1], round(rng.uniform(2, 120), 2), rng.randint(0, 300))
            for i in range(1, n_products + 1)
        ])
        con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", [
            (i, rng.randint(1, n_users), rng.randint(1, n_products), rng.randint(1, 5),
             (_EPOCH + timedelta(days=rng.randint(0, 270))).isoformat(),
             rng.choice(["pending", "shipped", "delivered", "delivered", "cancelled"]))
            for i in range(1, n_orders + 1)
        ])
        con.executemany("INSERT INTO logs VALUES (?,?,?,?)", [
            (i, f"2026-09-{rng.randint(1, 30):02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00Z",
             *rng.choice(_LOG_MESSAGES))
            for i in range(1, n_logs + 1)
        ])
        con.commit()
    finally:
        con.close()
    return path


if __name__ == "__main__":
    out = build_database(Path(sys.argv[1] if len(sys.argv) > 1 else "database/dummy.db"))
    print(f"wrote {out}")
