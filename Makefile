.PHONY: help setup dev-backend dev-frontend test evaluate docker-up docker-down mcp mcp-sse

help:
	@echo "RepoSage - Development & Deployment Commands"
	@echo "---------------------------------------------"
	@echo "setup         : Set up Python virtual environment and install dependencies"
	@echo "dev-backend   : Run backend API with auto-reload"
	@echo "dev-frontend  : Run frontend Vite dev server"
	@echo "test          : Execute backend pytest test suite"
	@echo "evaluate      : Run RAG benchmark and MRR evaluation"
	@echo "mcp           : Start Model Context Protocol server (stdio mode for IDEs)"
	@echo "mcp-sse       : Start MCP server in SSE mode on port 8001"
	@echo "docker-up     : Build and start full stack in Docker Compose"
	@echo "docker-down   : Stop Docker Compose services"

setup:
	python -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

dev-backend:
	PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	PYTHONPATH=backend pytest backend/tests -v

evaluate:
	PYTHONPATH=backend python backend/scripts/evaluate_rag.py

mcp:
	PYTHONPATH=backend python backend/mcp_server.py

mcp-sse:
	PYTHONPATH=backend python backend/mcp_server.py --transport sse --port 8001

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
