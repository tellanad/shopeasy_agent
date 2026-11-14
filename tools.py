"""The four tools of the Returns Agent: what it can do.

    get_orders         reads   the customer's orders        (SQLite, database.py)
    search_knowledge   reads   the handbook or the catalog  (Qdrant, retrieval.py)
    create_return      acts    books a return               - after its guardrails pass
    create_exchange    acts    books a size exchange        - after its guardrails pass

How a tool works:
- @tool turns a normal Python function into a tool the LLM can ask for.
- The docstring is what the LLM reads to decide when to use the tool. Change it and the agent behaves differently.
- `runtime.context` carries who is logged in. chat.py sends it with every message; the LLM cannot see or set it.

The LLM decides from the handbook. The guardrails here, in code, are the safety net it cannot break.
"""

from typing import Literal

from langchain.tools import ToolRuntime, tool

import database
from retrieval import search

STAFF_APPROVAL_ABOVE = 10_000   # a refund above this many rupees waits for a staff member


# ================================================================ the tools that read

@tool
def get_orders(runtime: ToolRuntime) -> list[dict]:
    """The customer's orders: order id, item, category, size, price, delivery date, and any return already booked."""
    return database.orders_of(runtime.context["customer_id"])


@tool
def search_knowledge(query: str, source: Literal["handbook", "catalog"]) -> str:
    """Search ShopEasy's knowledge. Choose the source:
    handbook = the rules for returns, exchanges, refunds, electronics and damaged items.
    catalog  = what an electronics product is listed as: features, specifications, price, warranty."""
    return search(query, source)


# ================================================================ guardrails

def reply(text: str, checks: list[str]) -> str:
    """The tool's answer, plus the guardrails it ran, so we can see them."""
    return f"{text}\nChecks in code: {' · '.join(checks)}"


def guardrails(order_id: str, customer_id: str):
    """The three guardrails every return and exchange must pass. Stops at the first one that fails.
    Returns: the order, a refusal message (None if all passed), and the list of checks with ✓ or ✗."""
    order = database.find_order(order_id, customer_id)

    # 1. Is it this customer's own order?
    if order is None:
        return None, f"Refused: this customer has no order {order_id}.", ["this customer's order ✗"]

    # 2. Is a return or exchange already booked for it?
    if database.booking_of(order_id):
        return None, f"Refused: a return or exchange is already booked for {order_id}.", \
            ["this customer's order ✓", "not booked before ✗"]

    # 3. Is it electronics?
    if order["category"] == "electronics":
        return None, "Refused: electronics cannot be returned for a refund (handbook, section 13).", \
            ["this customer's order ✓", "not booked before ✓", "not electronics ✗"]

    # all three passed
    return order, None, ["this customer's order ✓", "not booked before ✓", "not electronics ✓"]


# ================================================================ the tools that act

@tool
def create_return(order_id: str, runtime: ToolRuntime) -> str:
    """Book a return and refund for one order. Checks its limits itself and says so if the return is not allowed."""
    order, refusal, checks = guardrails(order_id, runtime.context["customer_id"])
    if refusal:
        return reply(refusal, checks)

    price = order["price"]

    # Above Rs 10,000: book it, but a staff member must approve (human in the loop)
    if price > STAFF_APPROVAL_ABOVE:
        database.book(order_id, "return", "waiting_for_staff", f"Refund of Rs {price}")
        return reply(f"Request recorded, not refused. Refunds above Rs {STAFF_APPROVAL_ABOVE} need a staff member's approval, "
                     f"and this one is Rs {price}. Tell the customer a team member will review it.",
                     checks + [f"Rs {price} > Rs {STAFF_APPROVAL_ABOVE} → waiting for staff"])

    # Otherwise: book it, approved
    database.book(order_id, "return", "approved", f"Refund of Rs {price}")
    return reply(f"Return booked for {order['item']}. Pickup within 2 working days. Refund of Rs {price} after the quality check.",
                 checks + [f"Rs {price} ≤ Rs {STAFF_APPROVAL_ABOVE} ✓"])


@tool
def create_exchange(order_id: str, new_size: str, runtime: ToolRuntime) -> str:
    """Exchange one order for another size. Checks its limits and the stock itself."""
    order, refusal, checks = guardrails(order_id, runtime.context["customer_id"])
    if refusal:
        return reply(refusal, checks)

    item, old_size = order["item"], order["size"]

    # Only items with a size (clothing, footwear) can be exchanged
    if old_size is None:
        return reply("Refused: only clothing and footwear can be exchanged for another size.",
                     checks + ["has a size ✗"])

    # The new size must be in stock
    if not database.in_stock(item, new_size):
        return reply(f"Out of stock: {item} is not available in size {new_size}. A return for a refund is possible instead.",
                     checks + ["has a size ✓", f"size {new_size} in stock ✗"])

    # All good: take one from stock and book the exchange
    database.take_from_stock(item, new_size)
    database.book(order_id, "exchange", "approved", f"Size {old_size} to size {new_size}")
    return reply(f"Exchange booked: {item} in size {new_size} will be delivered when size {old_size} is picked up.",
                 checks + ["has a size ✓", f"size {new_size} in stock ✓"])


# ================================================================ try the guardrails without the LLM:  python tools.py
# Run  python database.py  first. The last two lines try the same return twice: the second is refused.

if __name__ == "__main__":
    class Login:                                    # stands in for the login that chat.py sends
        context = {"customer_id": "C-102"}

    print(f"C-102 returns the TV:\n{create_return.func(order_id='ORD-5004', runtime=Login)}\n")
    print(f"C-102 exchanges shoes for size 9:\n{create_exchange.func(order_id='ORD-5003', new_size='9', runtime=Login)}\n")
    print(f"C-102 returns C-101's kurta:\n{create_return.func(order_id='ORD-5001', runtime=Login)}\n")

    Login.context = {"customer_id": "C-104"}
    print(f"C-104 returns the pressure cooker:\n{create_return.func(order_id='ORD-5009', runtime=Login)}\n")
    print(f"C-104 returns it again:\n{create_return.func(order_id='ORD-5009', runtime=Login)}")
