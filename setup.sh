#!/bin/bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Virtual env set up. Run 'source venv/bin/activate' to use it."