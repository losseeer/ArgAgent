# 上手只需这六条命令，一条不多（加目标即扩范围）。

.PHONY: up down dev logs eval reset-db

up: ## docker compose up -d
	docker compose up -d --build
	@echo "backend   http://localhost:$${BACKEND_PORT:-8010}"
	@echo "frontend  http://localhost:$${FRONTEND_PORT:-3005}"
	@echo "chroma    http://localhost:$${CHROMA_PORT:-8011}"

down: ## docker compose down
	docker compose down

dev: ## 本地模式（无 docker，依赖 host python/node）
	cd backend && uv sync
	cd backend && uvicorn app.main:app --reload --port $${BACKEND_PORT:-8010} & \
	  cd frontend && npm install && npm run dev

logs: ## 跟踪日志
	docker compose logs -f

eval: ## 跑结构、一致性、gold 集质量、鲁棒、时延五族指标，输出 docs/eval-report.md
	cd backend && python -m app.eval.runner

reset-db: ## 清空 SQLite + Chroma（保留 data/seed）
	rm -rf data/chroma/* data/*.db data/*.sqlite data/*.sqlite3
	@echo "runtime data cleared; data/seed untouched"
