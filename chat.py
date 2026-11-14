"""Chat with the Returns Agent in the terminal. Run  python database.py  once first.

    python chat.py

Type a message as the customer. Every step the agent takes is printed, so you can watch it work.
Type  staff  to act as a staff member and clear the approval queue.  Type  quit  to stop.
"""

import textwrap

import database
from agent import agent

GREY, BLUE, YELLOW, BOLD, END = "\033[90m", "\033[36m", "\033[33m", "\033[1m", "\033[0m"   # terminal colours


def staff_queue() -> None:
    """A staff member approves or rejects the returns that are waiting."""
    waiting = database.waiting_for_staff()
    if not waiting:
        print("  Nothing is waiting for approval.")
    for row in waiting:
        answer = input(f"  {row['order_id']}  {row['item']}  {row['note']}.  Approve? (y/n) ")
        status = "approved" if answer.lower().startswith("y") else "rejected"
        database.decide(row["return_id"], status)
        print(f"  -> {status}")


def line(label: str, text: str, colour: str) -> None:
    """Print one step as a tidy paragraph: a coloured label, then the text wrapped under it."""
    text = " ".join(str(text).split())                     # join the lines the model or the tool broke
    print(textwrap.fill(text, width=110, initial_indent=f"   {colour}{label:<13}{END}", subsequent_indent=" " * 16))


def show(message) -> None:
    """Print one step of the agent: what it thought, a tool it asked for, what the tool answered, or its reply."""
    if message.type == "ai":
        thinking = message.additional_kwargs.get("reasoning_content")      # the model's own note on its thinking
        if thinking:
            line("LLM thinks", thinking, GREY)
        for call in message.tool_calls:
            line("LLM asks for", f"{call['name']}({call['args']})", BLUE)     # the agent runs it, not the LLM
        if message.content:
            print(f"\n{BOLD}LLM answers:{END} {message.content}")
    elif message.type == "tool":
        line("tool returns", message.content, YELLOW)
        print()


customer_id = input("Log in as customer (C-101 to C-106): ").strip() or "C-101"
login = {"customer_id": customer_id}                        # sent with every message; the tools read it
conversation = {"configurable": {"thread_id": customer_id}}  # the memory is kept per conversation

while True:
    text = input("\nYou: ").strip()
    if text == "quit":
        break
    if text == "staff":
        staff_queue()
        continue
    # stream_mode="updates" hands us each step as it happens, instead of only the final answer
    for step in agent.stream({"messages": [("user", text)]}, conversation, context=login, stream_mode="updates"):
        for update in step.values():
            for message in (update or {}).get("messages", []):
                show(message)
