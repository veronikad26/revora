.PHONY: install api dashboard evaluate test docker-up docker-evaluate

install:
	python3 -m pip install -r requirements.txt

api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	streamlit run dashboard/streamlit_app.py

evaluate:
	python3 -m evaluation.run_batch --count $${EVAL_COUNT:-100} --seed $${EVAL_SEED:-42} --output evaluation/results.json

test:
	APP_ENV=development python3 -m pytest -q

docker-up:
	docker compose up --build api dashboard

docker-evaluate:
	docker compose --profile evaluation run --rm evaluator
