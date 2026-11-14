"""The Returns Agent: a model, a system prompt, four tools, a memory and a limit."""

import warnings
from datetime import date

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver

from prompts import CURRENT, PROMPTS
from tools import create_exchange, create_return, get_orders, search_knowledge

# The library warns when a tool receives the login (context). The warning is harmless, so we hide just that one.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

load_dotenv()       # reads GROQ_API_KEY from the .env file

llm = ChatGroq(model="openai/gpt-oss-120b", max_retries=8)     # retries when Groq's per-minute limit is hit


def build_agent(version: str = CURRENT):
    """Build the agent with one version of the prompt. chat.py uses the current one; evals.py tries them all."""
    return create_agent(
        llm,
        tools=[get_orders, search_knowledge, create_return, create_exchange],
        system_prompt=PROMPTS[version]["text"].format(today=f"{date.today():%d %B %Y}"),
        checkpointer=InMemorySaver(),                           # remembers the conversation
        middleware=[ToolCallLimitMiddleware(run_limit=10)],     # the loop cannot run away
    )


agent = build_agent()
