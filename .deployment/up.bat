@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "COMPOSE_FILE=%SCRIPT_DIR%docker-compose.yml"
set "ENV_FILE=%SCRIPT_DIR%resources\.env"

if not exist "%ENV_FILE%" (
  echo Missing env file: "%ENV_FILE%"
  echo Create deployment\resources\.env and run this script again.
  exit /b 1
)

docker compose -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d
