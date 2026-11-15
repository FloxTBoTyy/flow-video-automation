@echo off
REM launch_browser.bat - Inicia Brave, Chrome o Edge con Remote Debugging Port (CDP 9222) en Windows

set PORT=9222
echo [1/3] Verificando si el puerto %PORT% ya esta activo...
curl -s http://127.0.0.1:%PORT%/json/version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] El puerto de depuracion remota ya esta activo en http://127.0.0.1:%PORT%
    exit /b 0
)

REM Detectar rutas habituales de navegadores Chromium en Windows
set "BRAVE_LOCAL=%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
set "BRAVE_PROG=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
set "CHROME_PROG=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME_X86=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set "EDGE_PROG=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

set "TARGET_BIN="

if exist "%BRAVE_LOCAL%" (
    set "TARGET_BIN=%BRAVE_LOCAL%"
) else if exist "%BRAVE_PROG%" (
    set "TARGET_BIN=%BRAVE_PROG%"
) else if exist "%CHROME_PROG%" (
    set "TARGET_BIN=%CHROME_PROG%"
) else if exist "%CHROME_X86%" (
    set "TARGET_BIN=%CHROME_X86%"
) else if exist "%EDGE_PROG%" (
    set "TARGET_BIN=%EDGE_PROG%"
)

if "%TARGET_BIN%"=="" (
    echo [ERROR] No se encontro Brave, Chrome ni Edge en las rutas estandar.
    echo Puedes iniciar tu navegador manualmente con:
    echo   "ruta\a\tu\navegador.exe" --remote-debugging-port=%PORT%
    pause
    exit /b 1
)

echo [2/3] Navegador detectado: %TARGET_BIN%
echo [3/3] Iniciando navegador con --remote-debugging-port=%PORT%...
start "" "%TARGET_BIN%" --remote-debugging-port=%PORT% --restore-last-session

timeout /t 2 >nul
echo [OK] Navegador listo para la automatizacion en http://127.0.0.1:%PORT%
