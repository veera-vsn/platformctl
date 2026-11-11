.PHONY: install test lint db-up db-down api operator kind-up kind-down crd deploy-operator sample

install:
	python -m pip install -e ".[dev,ui]"

test:
	pytest

lint:
	ruff check src tests

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

api:
	uvicorn platformctl.api.main:app --reload --host 127.0.0.1 --port 8000

operator:
	kopf run --all-namespaces src/platformctl/operator/main.py

kind-up:
	kind create cluster --name platformctl --config kind/cluster.yaml

kind-down:
	kind delete cluster --name platformctl

crd:
	kubectl apply -f config/crd/application.yaml
	kubectl apply -f deploy/namespace.yaml

deploy-operator:
	docker build -f Dockerfile.operator -t platformctl-operator:dev .
	kind load docker-image platformctl-operator:dev --name platformctl
	kubectl apply -f config/rbac/operator.yaml
	kubectl apply -f deploy/operator.yaml

sample:
	kubectl apply -f config/samples/application-web.yaml
