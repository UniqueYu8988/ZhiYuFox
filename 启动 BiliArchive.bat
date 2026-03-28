@echo off
setlocal

cd /d "%~dp0"
if exist local_env.bat call local_env.bat

set "APP_UNPACKED_NEW=desktop\release\win-unpacked\知语狸.exe"
set "APP_UNPACKED_OLD=desktop\release\win-unpacked\BiliArchive.exe"
set "APP_PORTABLE_OLD=desktop\release\BiliArchive Portable.exe"

for %%f in ("desktop\release\知语狸*.exe") do (
    if exist "%%~ff" (
        start "" "%%~ff"
        goto :end
    )
)

if exist "desktop\release\知语狸.exe" (
    start "" "desktop\release\知语狸.exe"
    goto :end
)

if exist "%APP_PORTABLE_OLD%" (
    start "" "%APP_PORTABLE_OLD%"
    goto :end
)

if exist "%APP_UNPACKED_NEW%" (
    start "" "%APP_UNPACKED_NEW%"
    goto :end
)

if exist "%APP_UNPACKED_OLD%" (
    start "" "%APP_UNPACKED_OLD%"
    goto :end
)

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -ieq 'pythonw.exe' -or $_.Name -ieq 'python.exe') -and $_.CommandLine -like '*src\\gui_qt.py*' }; $procs | ForEach-Object { $_.ProcessId }"`) do (
    taskkill /PID %%i /F >nul 2>nul
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw src\gui_qt.py
) else (
    start "" python src\gui_qt.py
)

:end
endlocal
