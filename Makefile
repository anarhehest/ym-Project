ENV_FILE := .env

all: env run

env:
	@if [ -f $(ENV_FILE) ]; then \
  		echo "$(ENV_FILE) file exists; skipping..."; \
  	else \
		printf 'YM_TOKEN=\"\"\n' >> $(ENV_FILE); \
	fi

run:
	@if [ -f $(ENV_FILE) ] && grep -Eq '^YM_TOKEN="[^"]+"' $(ENV_FILE); then \
		echo "YM_TOKEN found — starting docker-compose"; \
		docker-compose up --build -d; \
	else \
		echo "ERROR: YM_TOKEN missing or empty in $(ENV_FILE). Please set YM_TOKEN=\"your_token\""; \
		exit 1; \
	fi


clear: clear-safe

clear-safe:
	docker-compose down

clear-full:
	docker-compose down --rmi all -v --remove-orphans
	@if [ -f $(ENV_FILE) ]; then \
		rm -f $(ENV_FILE); \
		echo "$(ENV_FILE) removed"; \
	else \
		echo "$(ENV_FILE) not present"; \
	fi
