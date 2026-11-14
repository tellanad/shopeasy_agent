"""The orders database (SQLite). Every SQL statement of the project is in this file.

    python database.py        creates the sample data again. Run it on the day of a demo.

Four tables:
    customers   who can log in
    orders      what each customer bought, and when it was delivered
    returns     what the agent booked: a return or an exchange, and its status
    stock       which sizes are available, for size exchanges

No AI in this file: the tools in tools.py call these functions, and the agent calls the tools.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

FILE = Path(__file__).parent / "shopeasy.db"     # the whole database is this one file


# ---------------------------------------------------------------- three small helpers

def connect() -> sqlite3.Connection:
    """Open the database. Rows come back like dictionaries: row["item"]."""
    con = sqlite3.connect(FILE)
    con.row_factory = sqlite3.Row
    return con


def read_all(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT and return every row."""
    with connect() as con:
        return [dict(row) for row in con.execute(sql, params).fetchall()]


def read_one(sql: str, params: tuple = ()) -> dict | None:
    """Run a SELECT and return the first row, or None."""
    with connect() as con:
        row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def write(sql: str, params: tuple = ()) -> None:
    """Run an INSERT or UPDATE. Leaving the 'with' block saves it."""
    with connect() as con:
        con.execute(sql, params)


# ---------------------------------------------------------------- reading (used by the tools)

def orders_of(customer_id: str) -> list[dict]:
    """A customer's orders, each with the return or exchange already booked for it (if any).
    Used by get_orders. LEFT JOIN keeps orders that have no booking (booked is then None)."""
    return read_all("""
        SELECT o.order_id, o.item, o.category, o.size, o.price, o.delivered_on,
               r.kind AS booked, r.status AS booked_status
        FROM orders o LEFT JOIN returns r ON r.order_id = o.order_id
        WHERE o.customer_id = ?""", (customer_id,))


def find_order(order_id: str, customer_id: str) -> dict | None:
    """One order, only if it belongs to this customer. Guardrail: nobody touches another customer's order."""
    return read_one("SELECT * FROM orders WHERE order_id = ? AND customer_id = ?", (order_id, customer_id))


def booking_of(order_id: str) -> dict | None:
    """The return or exchange booked for an order: {"kind": ..., "status": ...}, or None.
    Guardrail: an order is booked only once."""
    return read_one("SELECT kind, status FROM returns WHERE order_id = ?", (order_id,))


def in_stock(item: str, size: str) -> bool:
    """Is at least one piece of this item in this size available? Used by create_exchange."""
    row = read_one("SELECT quantity FROM stock WHERE item = ? AND size = ?", (item, size))
    return row is not None and row["quantity"] > 0


def waiting_for_staff() -> list[dict]:
    """The approval queue: returns that a staff member still has to decide (refunds above Rs 10,000)."""
    return read_all("""
        SELECT r.return_id, r.order_id, o.item, r.note
        FROM returns r JOIN orders o USING (order_id)
        WHERE r.status = 'waiting_for_staff'""")


# ---------------------------------------------------------------- writing (used by the tools and by staff)

def book(order_id: str, kind: str, status: str, note: str) -> None:
    """Record a return or an exchange. status: approved or waiting_for_staff."""
    write("INSERT INTO returns (order_id, kind, status, note) VALUES (?, ?, ?, ?)", (order_id, kind, status, note))


def take_from_stock(item: str, size: str) -> None:
    """One piece of this size leaves the shelf, for an exchange."""
    write("UPDATE stock SET quantity = quantity - 1 WHERE item = ? AND size = ?", (item, size))


def decide(return_id: int, status: str) -> None:
    """A staff member's decision: approved or rejected."""
    write("UPDATE returns SET status = ? WHERE return_id = ?", (status, return_id))


# ---------------------------------------------------------------- sample data

def days_ago(days: int) -> str:
    """Delivery dates are counted back from the day the data is created, so the demo works on any day."""
    return str(date.today() - timedelta(days=days))


def reset() -> None:
    """Delete everything and create the sample data again."""
    FILE.unlink(missing_ok=True)
    con = connect()

    # 1. the four tables
    con.executescript("""
        CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT);

        CREATE TABLE orders (
            order_id     TEXT PRIMARY KEY,
            customer_id  TEXT REFERENCES customers,
            item         TEXT,
            category     TEXT,      -- party_wear, clothing, footwear, home or electronics
            size         TEXT,
            price        INTEGER,   -- rupees
            delivered_on TEXT
        );

        CREATE TABLE returns (
            return_id INTEGER PRIMARY KEY,
            order_id  TEXT REFERENCES orders,
            kind      TEXT,         -- return or exchange
            status    TEXT,         -- approved, waiting_for_staff or rejected
            note      TEXT
        );

        CREATE TABLE stock (item TEXT, size TEXT, quantity INTEGER);
    """)

    # 2. six customers, each set up to show one behaviour of the agent
    con.executemany("INSERT INTO customers VALUES (?, ?)", [
        ("C-101", "Priya Menon"),
        ("C-102", "Rahul Verma"),
        ("C-103", "Anita Desai"),
        ("C-104", "Vikram Shah"),       # two kurtas: "return the kurta" is not clear
        ("C-105", "Neha Kapoor"),       # two pairs of shoes, and two earbuds
        ("C-106", "Arjun Nair"),        # the same dress ordered twice
    ])

    # 3. seventeen orders: order id, customer, item, category, size, price, delivered
    con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", [
        ("ORD-5001", "C-101", "Cotton Kurta",                         "clothing",    "M",  1299, days_ago(6)),
        ("ORD-5002", "C-101", "Sequin Party Dress",                   "party_wear",  "S",  3499, days_ago(9)),   # past its 7 days
        ("ORD-5003", "C-102", "Stride Running Shoes",                 "footwear",    "8",  2799, days_ago(4)),
        ("ORD-5004", "C-102", "Zentro Vision 55 4K LED TV (ZT-55U5)", "electronics", None, 36990, days_ago(3)),
        ("ORD-5005", "C-103", "Sheesham Wood Coffee Table",           "home",        None, 18500, days_ago(5)),

        ("ORD-5006", "C-104", "Cotton Kurta",                         "clothing",    "L",  1299, days_ago(3)),
        ("ORD-5007", "C-104", "Linen Kurta",                          "clothing",    "L",  1899, days_ago(8)),
        ("ORD-5008", "C-104", "Slim Fit Jeans",                       "clothing",    "34", 2199, days_ago(12)),
        ("ORD-5009", "C-104", "Steel Pressure Cooker 5L",             "home",        None, 2450, days_ago(2)),

        ("ORD-5010", "C-105", "Stride Running Shoes",                 "footwear",    "6",  2799, days_ago(5)),
        ("ORD-5011", "C-105", "Urban Walk Sneakers",                  "footwear",    "6",  3299, days_ago(2)),
        ("ORD-5012", "C-105", "Nexa Buds 3 (NX-B3)",                  "electronics", None, 2499, days_ago(6)),
        ("ORD-5013", "C-105", "Nexa Buds 3 Pro (NX-B3P)",             "electronics", None, 4999, days_ago(1)),
        ("ORD-5014", "C-105", "Silk Saree",                           "clothing",    None, 5499, days_ago(10)),

        ("ORD-5015", "C-106", "Sequin Party Dress",                   "party_wear",  "M",  3499, days_ago(10)),  # past its 7 days
        ("ORD-5016", "C-106", "Sequin Party Dress",                   "party_wear",  "L",  3499, days_ago(2)),
        ("ORD-5017", "C-106", "Leather Formal Shoes",                 "footwear",    "9",  4299, days_ago(4)),
    ])

    # 4. stock for size exchanges: item, size, how many
    con.executemany("INSERT INTO stock VALUES (?, ?, ?)", [
        ("Cotton Kurta", "S", 4), ("Cotton Kurta", "L", 2),
        ("Stride Running Shoes", "7", 3), ("Stride Running Shoes", "9", 0),      # size 9 is out of stock
        ("Linen Kurta", "M", 5), ("Linen Kurta", "XL", 1),
        ("Urban Walk Sneakers", "7", 2),
        ("Leather Formal Shoes", "10", 2),
    ])
    con.commit()
    con.close()


if __name__ == "__main__":
    reset()
    print(f"Created {FILE.name}: 6 customers, 17 orders")
