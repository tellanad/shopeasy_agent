"""Test the agent against the golden dataset: play each conversation, and count how often it does the right thing.

    python evals.py             the current version, 3 runs of every case
    python evals.py v4 v5       compare two versions
    python evals.py v4 v5 1     the same, with 1 run of every case (uses fewer tokens)

An agent does not behave the same way every time, so each case is run several times and we report a rate.
Each run uses many tokens: on Groq's free tier, run few cases or 1 run.
"""

import csv
import sys
from pathlib import Path
from uuid import uuid4

import database
from agent import build_agent
from prompts import CURRENT, PROMPTS

# ================================================================ the golden dataset
# golden_dataset.csv: one test per row. Open it in Excel or VS Code to read or add tests.
#   customer_says         what the customer types; two messages are separated by " | "
#   expected_behaviour    what should happen, in plain English (for people; the code does not read it)
#   order + expected_booking   what must be booked for that order at the end ("nothing" = nothing booked)
#   must_use              a tool (or search source) the agent must have used
#   must_not_use          a tool the agent must NOT have used ("create" = any create_ tool)
#   reply_must_not_say    a word the last reply must not contain

GOLDEN = Path(__file__).parent / "golden_dataset.csv"


def load_golden() -> list[dict]:
    """Read the golden dataset: one test case per row."""
    cases = []
    with open(GOLDEN, newline="") as file:
        for row in csv.DictReader(file):
            case = {"name": row["test"], "customer": row["customer"], "say": row["customer_says"].split(" | ")}
            if row["order"]:
                case["order"] = row["order"]
                case["booked"] = None if row["expected_booking"] == "nothing" else tuple(row["expected_booking"].split())
            for check in ("must_use", "must_not_use", "reply_must_not_say"):
                if row[check]:
                    case[check] = row[check]
            cases.append(case)
    return cases


CASES = load_golden()


# ================================================================ playing a case

def play(agent, case: dict) -> tuple[list[str], str]:
    """Play one conversation. Returns the tools the agent used, and its last reply."""
    memory = {"configurable": {"thread_id": uuid4().hex}}          # a fresh conversation
    for text in case["say"]:
        result = agent.invoke({"messages": [("user", text)]}, memory, context={"customer_id": case["customer"]})

    used = []
    for message in result["messages"]:
        for call in getattr(message, "tool_calls", []):
            # a search is recorded by its source ("handbook" or "catalog"), every other tool by its name
            used.append(call["args"].get("source") or call["name"])
    return used, result["messages"][-1].content


def booked(order_id: str):
    """What is booked for an order now: ("return", "approved"), ("exchange", "approved") ... or None."""
    booking = database.booking_of(order_id)
    return (booking["kind"], booking["status"]) if booking else None


def passed(case: dict, used: list[str], reply: str) -> bool:
    """Is everything the case expects true?"""
    if "order" in case and booked(case["order"]) != case["booked"]:
        return False
    if "must_use" in case and not any(tool.startswith(case["must_use"]) for tool in used):
        return False
    if "must_not_use" in case and any(tool.startswith(case["must_not_use"]) for tool in used):
        return False
    if "reply_must_not_say" in case and case["reply_must_not_say"] in reply.lower():
        return False
    return True


# ================================================================ run: python evals.py [versions] [runs]

if __name__ == "__main__":
    args = sys.argv[1:]
    runs = int(args.pop()) if args and args[-1].isdigit() else 3
    versions = args or [CURRENT]

    for version in versions:
        agent = build_agent(version)
        score = {case["name"]: 0 for case in CASES}
        for _ in range(runs):
            database.reset()                                        # fresh data for every run
            for case in CASES:
                used, reply = play(agent, case)
                score[case["name"]] += passed(case, used, reply)

        print(f"\n{version}: {PROMPTS[version]['why']}")
        for name, count in score.items():
            print(f"  {count} / {runs}  {name}")
        print(f"  {version} score: {sum(score.values())} / {runs * len(CASES)}")
