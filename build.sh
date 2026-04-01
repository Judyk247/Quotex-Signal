#!/bin/bash
# Exit on error
set -e

echo "=== Updating system packages ==="
apt-get update -y

echo "=== Installing build tools and dependencies ==="
apt-get install -y build-essential gcc g++ python3-dev wget

# TA-Lib installation from source
echo "=== Downloading TA-Lib source ==="
cd /tmp
wget https://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib-0.4.0/

echo "=== Compiling TA-Lib ==="
./configure --prefix=/usr
make
make install

# Link libraries so Python can find them
ldconfig

echo "=== Installing Python dependencies ==="
cd /opt/render/project/src
pip install -r requirements.txt

echo "=== Build complete ==="
