@echo off
setlocal
rem -- Options (document in manual) --------

set JVM_ARGS=-Xms7G -Xmx7G -XX:+UseG1GC
set PAUSE_AFTER_EXIT=false

rem Adding following to JVM_ARGS *might* disable GPU use in UMP... (echoes) might... might...
rem -Dsun.java2d.d3d=false -Dsun.java2d.opengl=false

rem -- Java Check --------------------------

cd /d "%~dp0"
where java >nul 2>&1 || (
  echo -=[!]=========================================[!]=-
  echo           Could not locate java command.
  echo     This launcher will be very likely to fail!
  echo  Make sure you have java installed and configured.
  echo -=[!]=========================================[!]=-
  echo [C] Continue
  echo [Q] Quit Launcher
  echo [J] Quit Launcher and Open Java Website ^(https://java.com/^)
  choice /n /c:QJC /m "Hit key of your choice>"
  if ERRORLEVEL 3 (
    echo.
    rem continue
  ) else (
    if ERRORLEVEL 2 start "" "https://java.com/"
    exit /b
  )
)

rem -- UMP ---------------------------------

echo Closing this window doesn't stop UMP properly. It should be done only when:
echo - Can't close UMP window
echo - This window stays after closing UMP
echo.
echo -- Begin JVM/UMP Log -----------
if "%~1"=="" (
  java %JVM_ARGS% -jar MIDIPlayer.jar || goto JVM_CRASH
) else (
  java %JVM_ARGS% -jar MIDIPlayer.jar "%~1" || goto JVM_CRASH
)
echo -- End JVM/UMP Log -------------
echo Finished with exitcode %ERRORLEVEL%.
if "%PAUSE_AFTER_EXIT%"=="true" (
  pause
)
exit /b

:JVM_CRASH
echo -- End JVM/UMP Log -------------
echo.
echo Finished with exitcode %ERRORLEVEL% (abnormal termination).
rem Check if PC is definitely 32bit
if "%PROCESSOR_ARCHITECTURE%" == "x86" (
  echo ^(Tip^) 32-Bit computer detected: JVM may fail to start if you change JVM_ARGS to use 4GB or more memory. To allow more memory, you need to get a 64-bit computer.
) else (
  java -version 2>&1 | find /I "32-Bit" && (
    echo ^(Tip^) 32-Bit Java detected: JVM may fail to start if you change JVM_ARGS to use 4GB or more memory. To allow more memory, you need to install 64-bit Java. ^(https://java.com/^)
  )
)
pause
exit /b

rem I suck at writing batch files
