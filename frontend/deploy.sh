#!/usr/bin/env bash
# Rebuild the frontend and deploy to project root.
# Run from the project root: bash frontend/deploy.sh
set -e
cd "$(dirname "$0")"
npm run build
cd ..
rm -rf assets
cp -r frontend/dist/assets assets
cp frontend/dist/index.html index.html
echo "Deployed. Restart uvicorn to pick up changes."
