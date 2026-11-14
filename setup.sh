#!/bin/sh
# One-time setup for Mac and Linux. Run it from this folder:   sh setup.sh
#
# It works whatever Python your computer has: uv downloads Python 3.12 just for this project.

set -e
cd "$(dirname "$0")"

echo "1/4  Getting uv (a fast Python installer)..."
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"

echo "2/4  Creating .venv with Python 3.12..."
"$UV" venv --clear --python 3.12 .venv

echo "3/4  Installing the packages (a few minutes)..."
"$UV" pip install --python .venv/bin/python -r requirements.txt

echo "4/4  Creating .env..."
if [ ! -f .env ]; then
    cp .env.example .env
fi

echo ""
echo "Setup done. Last step: open .env and paste your Groq key after GROQ_API_KEY="
echo "Then run:   .venv/bin/python database.py   and   .venv/bin/python chat.py"
