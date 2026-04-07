# Run FastAPI

```sh
uv run uvicorn src.main:app --reload --port 8080
```

# Setting up DB

## Locally

```sh
docker run --name azens-db \
    -e POSTGRES_USER=azens \
    -e POSTGRES_PASSWORD=azens \
    -e POSTGRES_DB=azens \
    -p 5432:5432 \
    -d postgres:16
```

## Check users in DB

```sh
docker exec azens-db psql -U azens -d azens -c "SELECT id, email, full_name, is_admin FROM users;"
```

# Database Migrations (Alembic)

## Generate a new migration after changing models

```sh
alembic revision --autogenerate -m "describe what changed"
```

## Apply all pending migrations to the database

```sh
alembic upgrade head
```

## Rollback the last migration

```sh
alembic downgrade -1
```

## See current migration status

```sh
alembic current
```

## See migration history

```sh
alembic history
```

# Upload Data to S3

## With curl

```sh
# 1. Paste the URL into a file (no escaping needed in a text editor) - Get url from /cv/uploal-url endpoint
pbpaste > /tmp/upload_url.txt

# 2. Use it
curl -X PUT "$(cat /tmp/upload_url.txt)" \
-H "Content-Type: application/pdf" \
--data-binary @/path/to/file
```
