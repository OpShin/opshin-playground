git pull
source .venv/bin/activate
pip install -Ur requirements.txt
# run the mock server
uvicorn server:app --workers 2 --port 8001

