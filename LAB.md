# ShopEasy Returns Agent: hands-on lab

An AI agent that handles returns and exchanges for an online store.
It reads orders from a database, searches a policy handbook (RAG), decides, and books returns, with guardrails in code and a staff approval step.

**Agent = LLM + Tools + Memory + Loop**

---

## What is in the folder

| File | What it is |
|---|---|
| `database.py` | The facts: customers, orders, returns, stock (SQLite) |
| `retrieval.py` | The knowledge: searches the handbook and the catalog (RAG) |
| `tools.py` | The 4 tools the agent can use, with the guardrails |
| `prompts.py` | The system prompt, versions v1 to v5 |
| `agent.py` | Puts it together: LLM + Tools + Memory + Loop |
| `chat.py` | Chat with the agent in the terminal |
| `app.py` | Chat with the agent in the browser (Streamlit) |
| `evals.py` | Tests the agent on the golden dataset |
| `golden_dataset.csv` | The golden dataset: 8 test questions and what should happen for each (open it in Excel) |
| `knowledge/` | `handbook.txt` (the rules) and `catalog.txt` (the products) |
| `flow.html` | Open in a browser: watch one message move through the agent |
| `architecture.html` | Open in a browser: all the pieces and how they connect |

---

## Setup (once, about 10 minutes)

**1. Get a free Groq key.** Sign up at **console.groq.com** → API Keys → Create. Copy it. Use your own key: the free limit is per account.

**2. Open this folder in VS Code** (File → Open Folder), then open the terminal: **Ctrl + `**

**3. Run the setup:**

Mac / Linux
```bash
sh setup.sh
```

Windows
```bat
setup.bat
```

It gets Python 3.12 just for this project (whatever Python your computer has), installs everything, and creates the file `.env`.

**4. Add your key.** Open `.env` and paste your Groq key after `GROQ_API_KEY=`. Save.

> In every command below, Windows users write `.venv\Scripts\python` instead of `.venv/bin/python`.

---

## The lab: one piece at a time

### Step 1. The data
```bash
.venv/bin/python database.py
```
Prints `Created shopeasy.db: 6 customers, 17 orders`. Run it again any time to start fresh.

Look inside:
```bash
.venv/bin/python -c "import sqlite3; [print(r) for r in sqlite3.connect('shopeasy.db').execute('SELECT * FROM orders')]"
```
Change `orders` to `customers`, `stock` or `returns`. **`returns` is empty:** nothing is booked yet.

### Step 2. The knowledge (RAG, no LLM)
```bash
.venv/bin/python retrieval.py
```
The first run downloads two small models (about 1 minute). You see the 3 best handbook passages for a question about dresses, and the catalog entry for the TV model `ZT-55U5`.

### Step 3. The tools and their guardrails (no LLM)
```bash
.venv/bin/python tools.py
```
Each answer ends with `Checks in code: ... ✓ / ✗`. The TV is refused (electronics), size 9 is out of stock, another customer's order is refused, and the pressure cooker is booked. **The same return a second time** fails `not booked before ✗`.

Then reset: `.venv/bin/python database.py`

### Step 4. The agent, in the terminal
```bash
.venv/bin/python chat.py
```
Log in as `C-101` and type: **I want to return the kurta I got last week**

Watch every step:
- `LLM thinks`: the model's reasoning
- `LLM asks for`: the tool the model wants (the agent runs it, not the LLM)
- `tool returns`: what the tool gave back
- `LLM answers`: the final reply

Count the LLM calls. Type `quit` to stop.

### Step 5. Prove the agent wrote to the database
```bash
.venv/bin/python -c "import sqlite3; [print(r) for r in sqlite3.connect('shopeasy.db').execute('SELECT * FROM returns')]"
```
The return the agent booked is now a row.

### Step 6. Try every customer
Run `chat.py` again for each login. Reset with `database.py` if an order says "already booked".

| Login | Ask this | What should happen |
|---|---|---|
| C-101 | Please return my Sequin Party Dress | Refused: party wear allows 7 days, it is 9 days old |
| C-102 | The running shoes are too small, I need size 9 → then: ok, return them then | Size 9 out of stock, offers a return, remembers which shoes |
| C-102 | Is my TV supposed to be 120 Hz? It looks slow. → then: Then I want to return it | Checks the catalog (60 Hz), refuses the return from the handbook |
| C-103 | I want to return the coffee table | Rs 18,500: waits for staff. Type `staff` to approve |
| C-104 | I want to return the kurta | Asks which one: there are two kurtas |
| C-105 | My sneakers are too small, I need size 7 | Exchange booked |
| C-106 | I want to return my party dress | Asks which: one is too old, one can be returned |

### Step 7. The same agent in the browser
```bash
.venv/bin/streamlit run app.py --server.headless true
```
Open **http://localhost:8501**. Pick a customer in the sidebar. Return C-103's coffee table, then press **Approve** in the sidebar: a person makes the final call. Stop with Ctrl-C.

### Step 8. Break it, and see what changes
Change one thing, run `chat.py`, and compare. Undo it after.

| Change | Where | What you should see |
|---|---|---|
| `STAFF_APPROVAL_ABOVE = 1000` | `tools.py` | Even the kurta waits for staff |
| `CURRENT = "v4"` | `prompts.py` | The TV return is usually refused by the tool, not by the model |
| Delete the line `checkpointer=InMemorySaver(),` | `agent.py` | "ok, return them then" no longer knows which shoes |
| Shorten the docstring of `search_knowledge` to just `"""Search."""` | `tools.py` | The agent no longer knows when to use the handbook or the catalog |
| `run_limit=2` | `agent.py` | After 2 tool calls the agent is blocked, so it cannot book the return |

---

## Optional

**Open the visuals:** double-click `flow.html` and `architecture.html`.

**Run the tests.** Open `golden_dataset.csv` first: each row is a question and what the agent should do. Then run it (uses many tokens, so only 1 run per case):
```bash
.venv/bin/python evals.py v5 1
```
Add your own test: add a row to `golden_dataset.csv`, and run it again.

**See every step in LangSmith:** create a free key at smith.langchain.com, and uncomment the three `LANGSMITH_` lines in `.env`.

---

## If something goes wrong

| Problem | Fix |
|---|---|
| `Rate limit reached ... tokens per day` | The free Groq limit is used up. Wait a few minutes, or use another Groq account |
| `No matching distribution found` or `has no wheels` | The `.venv` was made with the wrong Python. Run `sh setup.sh` (Windows: `setup.bat`) again |
| A popup asks to install developer tools (Mac) | Click Install, wait, then run the command again |
| `GROQ_API_KEY` error | Check that the file is named `.env` (not `.env.txt`) and the key is pasted after `=` |
| "already booked" | Run `.venv/bin/python database.py` to reset the data |
| Streamlit asks for an email | Press Enter, or add `--server.headless true` |
| Streamlit opens on port 8502 | Another one is still running: stop it with Ctrl-C |
| First start is slow | It loads the search models and indexes the handbook. Normal |
