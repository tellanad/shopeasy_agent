"""A chat UI for the Returns Agent. Run  python database.py  once first.

    streamlit run app.py

Left: log in as a customer, and act as staff to approve returns.  Right: the chat, with every agent step.
"""

from uuid import uuid4

import streamlit as st

import database
from agent import build_agent

st.set_page_config(page_title="ShopEasy Returns Agent", page_icon="🛍️")


@st.cache_resource
def get_agent():
    """Streamlit reruns this file on every click, so build the agent (and its memory) only once."""
    if not database.FILE.exists():
        database.reset()
    return build_agent()


agent = get_agent()
chats = st.session_state.setdefault("chats", {})     # what we show on screen, one list per customer
session = st.session_state.setdefault("session", uuid4().hex[:8])   # a page reload starts a fresh memory

# ---------------------------------------------------------------- sidebar: customer and staff

with st.sidebar:
    customer_id = st.selectbox("Log in as customer", [f"C-{n}" for n in range(101, 107)])

    st.divider()
    st.subheader("🧑‍💼 Staff approvals")
    waiting = database.waiting_for_staff()
    if not waiting:
        st.caption("Nothing is waiting for approval.")
    for row in waiting:
        st.markdown(f"**{row['order_id']}** · {row['item']}  \n{row['note']}")
        approve, reject = st.columns(2)
        if approve.button("Approve", key=f"a{row['return_id']}", type="primary"):
            database.decide(row["return_id"], "approved")
            st.rerun()
        if reject.button("Reject", key=f"r{row['return_id']}"):
            database.decide(row["return_id"], "rejected")
            st.rerun()

# ---------------------------------------------------------------- the chat

st.title("🛍️ ShopEasy Returns Agent")
history = chats.setdefault(customer_id, [])


def show_step(kind: str, text: str) -> None:
    """One step of the agent: what it thought, a tool it asked for, or what the tool answered."""
    icon = {"thinks": "💭", "tool": "🔧", "result": "📦"}[kind]
    st.markdown(f"{icon} **{kind}**")
    st.code(text, language=None, wrap_lines=True)


for turn in history:
    with st.chat_message(turn["role"]):
        if turn.get("steps"):
            with st.expander(f"Agent steps ({len(turn['steps'])})"):
                for kind, text in turn["steps"]:
                    show_step(kind, text)
        st.markdown(turn["content"])

if text := st.chat_input("Ask about a return or an exchange"):
    history.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)

    with st.chat_message("assistant"):
        steps, reply = [], ""
        with st.status("Agent is working...", expanded=True) as status:
            # stream_mode="updates" hands us each step as it happens, instead of only the final answer
            for step in agent.stream(
                {"messages": [("user", text)]},
                {"configurable": {"thread_id": f"{customer_id}-{session}"}},   # memory per customer, per visit
                context={"customer_id": customer_id},             # the tools read who is logged in
                stream_mode="updates",
            ):
                for update in step.values():
                    for message in (update or {}).get("messages", []):
                        new = []
                        if message.type == "ai":
                            if thinking := message.additional_kwargs.get("reasoning_content"):
                                new.append(("thinks", thinking))
                            new += [("tool", f"{c['name']}({c['args']})") for c in message.tool_calls]
                            reply = message.content or reply
                        elif message.type == "tool":
                            new.append(("result", message.content))
                        for kind, step_text in new:
                            show_step(kind, step_text)
                        steps += new
            status.update(label=f"Agent steps ({len(steps)})", state="complete", expanded=False)
        st.markdown(reply)

    history.append({"role": "assistant", "content": reply, "steps": steps})
    st.rerun()      # refresh the sidebar, in case the agent just sent a return to staff
