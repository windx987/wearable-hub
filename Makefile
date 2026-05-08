DOCKER_COMMAND = docker compose -f docker-compose.yml
DOCKER_EXEC = $(DOCKER_COMMAND) exec app
ALEMBIC_CMD = uv run alembic

help:	## Show this help.
	@echo "============================================================"
	@echo "This is a list of available commands for this project."
	@echo "============================================================"
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

build:	## Builds docker image
	$(DOCKER_COMMAND) build --no-cache

run:	## Runs the environment in detached mode
	$(DOCKER_COMMAND) up -d --force-recreate
	$(DOCKER_COMMAND) rm -f db-svix-init

up:	## Runs the non-detached environment
	$(DOCKER_COMMAND) up --force-recreate

watch:	## Runs the environment with hot-reload
	$(DOCKER_COMMAND) watch

stop:	## Stops running instance
	$(DOCKER_COMMAND) stop

down:	## Kills running instance
	$(DOCKER_COMMAND) down

test:	## Run the tests.
	cd backend && uv run pytest -v --cov=app

migrate:  ## Apply all migrations
	$(DOCKER_EXEC) $(ALEMBIC_CMD) upgrade head

seed:  ## Seed sample data (test users and activity data)
	$(DOCKER_EXEC) uv sync --group dev
	$(DOCKER_EXEC) uv run python scripts/init/seed_activity_data.py

stream:  ## Stream live wearable data for a specific user (runs until Ctrl+C). Requires USER=email. Optional: SPEED=N (default 60), START=YYYY-MM-DD (default Jan 1 this year).
	@if [ -z "$(USER)" ]; then \
		echo "Error: You must provide a target user using 'USER=email'"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) uv run python scripts/stream_data.py --user $(USER) --speed $(or $(SPEED),60) $(if $(START),--start $(START),)

create_migration:  ## Create a new migration. Use 'make create_migration m="Description of the change"'
	@if [ -z "$(m)" ]; then \
		echo "Error: You must provide a migration description using 'm=\"Description\"'"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) $(ALEMBIC_CMD) revision --autogenerate -m "$(m)"

downgrade:  ## Revert the last migration
	$(DOCKER_EXEC) $(ALEMBIC_CMD) downgrade -1

reset_db:  ## Truncate all tables in the database (WARNING: deletes all data)
	$(DOCKER_EXEC) uv run python scripts/reset_database.py

seed_questionnaire:  ## Seed 90 days of questionnaire history for all scenarios. Requires USER=email. Optional: DAYS=N.
	@if [ -z "$(USER)" ]; then \
		echo "Usage: make seed_questionnaire USER=email [DAYS=90]"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) uv run python scripts/seed_questionnaire.py --user $(USER) --days $(or $(DAYS),90)

scenario:  ## Seed signals to trigger a specific questionnaire scenario. Requires USER=email SCENARIO=name.
	@if [ -z "$(USER)" ] || [ -z "$(SCENARIO)" ]; then \
		echo "Usage: make scenario USER=email SCENARIO=hrv_drop|elevated_arousal|poor_sleep|post_workout|streak_risk|rops|baseline"; \
		exit 1; \
	fi
	$(DOCKER_EXEC) uv run python scripts/seed_scenario.py --user $(USER) --scenario $(SCENARIO)
