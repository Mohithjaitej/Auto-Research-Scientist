.PHONY: install playground run test clean

install:
     uv sync   

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run uvicorn app.fast_api_app:app --host 127.0.0.1 --port 8000 --reload

test:
	uv run pytest

clean:
	Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
	Remove-Item -Force uv.lock -ErrorAction SilentlyContinue
