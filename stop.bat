@echo off
REM ============================================================
REM  JobFinder - derruba os processos rodando nas portas 8765 e 5173
REM ============================================================

echo.
echo  [JobFinder] Procurando processos nas portas 8765 e 5173...
echo.

powershell -NoProfile -Command ^
  "$ports = 8765, 5173; foreach ($p in $ports) { $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue; if ($conns) { foreach ($c in $conns) { try { $proc = Get-Process -Id $c.OwningProcess -ErrorAction Stop; Write-Host ('  Parando ' + $proc.ProcessName + ' (PID ' + $proc.Id + ') na porta ' + $p) -ForegroundColor Yellow; Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} } } else { Write-Host ('  Nada rodando na porta ' + $p) -ForegroundColor DarkGray } }"

echo.
echo  [JobFinder] Pronto.
echo.
timeout /t 3 /nobreak >nul
