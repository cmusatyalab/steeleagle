#!/bin/bash
# FRONTEND
# install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
# install npm
nvm use 22
# copy config template
cp ./prime/src/config.js.template ./prime/src/config.js
# BACKEND
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# copy config template
cp ./backend/config.toml.template ./backend/config.toml
# install dependencies
cd backend
uv sync
