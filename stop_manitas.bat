@echo off
rem Detiene la instancia de Manitas que corre en segundo plano.
cd /d "%~dp0"
if exist manitas.pid (
    for /f "delims=" %%P in (manitas.pid) do (
        taskkill /F /PID %%P >nul 2>nul && echo Manitas detenido ^(PID %%P^) || echo No se encontro el proceso ^(PID %%P^).
    )
    del manitas.pid 2>nul
) else (
    echo Manitas no esta corriendo ^(no existe manitas.pid^).
)
pause
