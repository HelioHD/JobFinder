@echo off
REM ============================================================
REM  JobFinder - inicia backend e frontend em janelas separadas
REM  Duplo-clique neste arquivo para subir tudo de uma vez.
REM ============================================================

cd /d "%~dp0"

echo.
echo  [JobFinder] Iniciando backend (FastAPI) na porta 8765...
start "JobFinder Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8765"

REM Espera 2s pro backend acordar antes do front
timeout /t 2 /nobreak >nul

echo  [JobFinder] Iniciando frontend (Vite) na porta 5173...
start "JobFinder Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM Espera o Vite subir antes de abrir o navegador
timeout /t 4 /nobreak >nul

echo  [JobFinder] Abrindo no navegador...
start "" "http://localhost:5173"

echo.
echo  ============================================================
echo   Backend  - http://127.0.0.1:8765  (docs em /docs)
echo   Frontend - http://localhost:5173
echo.
echo   Para parar tudo: feche as duas janelas abertas
echo   ou execute o stop.bat.
echo  ============================================================
echo.
timeout /t 5 /nobreak >nul
