# Install uv, if we don't already have it
if command -v uv &> /dev/null; then
    :
else
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# Run the python script
uv run main.py
