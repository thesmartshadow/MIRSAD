.PHONY: install dev test e2e lint format typecheck build doctor evaluate benchmark verify-live reset-db

install:
	npm run install:all

dev:
	npm run dev

test:
	npm test

e2e:
	npm run test:e2e

lint:
	npm run lint

format:
	npm run format

typecheck:
	npm run typecheck

build:
	npm run build

doctor:
	npm run doctor

evaluate:
	npm run evaluate:search

benchmark:
	npm run benchmark

verify-live:
	npm run verify:live

reset-db:
	npm run reset-db
