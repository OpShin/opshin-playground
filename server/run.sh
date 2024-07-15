git pull
source .venv/bin/activate
pip install -U requirements.txt
# run the mock server
uvicorn server:app --workers 2 --port 8001

