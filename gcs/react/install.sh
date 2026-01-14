#!/bin/bash
# FRONTEND
# install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
# install npm
nvm install 22
source ~/.bashrc
cd prime
npm install
cd ..
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
