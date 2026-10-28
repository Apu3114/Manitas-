@echo off
rem Lanza Manitas en segundo plano: sin ventana de deteccion y sin consola.
cd /d "%~dp0"
for /f "usebackq delims=" %%P in (`python -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))"`) do set PW=%%P
start "" "%PW%" main.py
exit
