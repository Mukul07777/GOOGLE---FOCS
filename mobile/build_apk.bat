@echo off
setlocal EnableExtensions
title Focs - build the Android app
cd /d "%~dp0"

set "MOBILE=%~dp0"
set "FRONTEND=%MOBILE%..\frontend"

echo.
echo   Focs for Android - build_apk.bat [release]
echo.

rem ------------------------------------------------------------------ 1. Tools: a JDK 21 and the Android SDK
if not defined JAVA_HOME (
  for /d %%D in ("%USERPROFILE%\.jdks\jdk-21*") do set "JAVA_HOME=%%D"
)
if not defined JAVA_HOME goto :no_java
if not exist "%JAVA_HOME%\bin\java.exe" goto :no_java
if not defined ANDROID_HOME set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
if not exist "%ANDROID_HOME%\platforms" goto :no_sdk
where npm >nul 2>nul
if errorlevel 1 (
  echo [x] Node.js 20+ is needed: https://nodejs.org
  goto :fail
)
echo [1/5] Tools found
echo       Java    : %JAVA_HOME%
echo       Android : %ANDROID_HOME%

rem ------------------------------------------------------------------ 2. Which server the app opens on first launch
set "VITE_FOCS_APP=1"
set "VITE_FOCS_SERVER="
if exist "%MOBILE%server.txt" (
  for /f "usebackq eol=# tokens=* delims=" %%L in ("%MOBILE%server.txt") do if not defined VITE_FOCS_SERVER set "VITE_FOCS_SERVER=%%L"
)
if defined VITE_FOCS_SERVER (
  echo [2/5] The app will open %VITE_FOCS_SERVER%
) else (
  echo [2/5] No address in server.txt: the app will ask for the server when it first opens
)

rem ------------------------------------------------------------------ 3. The web app, built for the phone
echo [3/5] Building the web app ...
pushd "%FRONTEND%"
if not exist node_modules (
  call npm install --no-audit --no-fund --loglevel=error
  if errorlevel 1 ( popd & goto :fail )
)
call npx tsc --noEmit
if errorlevel 1 ( popd & goto :fail )
call npx vite build --outDir "%MOBILE%www" --emptyOutDir --logLevel warn
if errorlevel 1 ( popd & goto :fail )
popd
rem the same screen under the name the app opens when a server does not answer
copy /y "%MOBILE%www\index.html" "%MOBILE%www\unreachable.html" >nul

rem ------------------------------------------------------------------ 4. Into the Android project
echo [4/5] Copying it into the Android project ...
if not exist "%MOBILE%node_modules" (
  call npm install --no-audit --no-fund --loglevel=error
  if errorlevel 1 goto :fail
)
call npx cap sync android
if errorlevel 1 goto :fail

rem ------------------------------------------------------------------ 5. The APK
rem Build files go outside this folder: it is inside OneDrive, which locks files a build changes quickly.
set "FOCS_ANDROID_BUILD=%LOCALAPPDATA%\FocsAndroidBuild"
set "TASK=assembleDebug"
set "KIND=debug"
set "APK=app-debug.apk"
if /i "%~1"=="release" (
  if not exist "%MOBILE%keystore.properties" (
    echo [x] A release needs your signing key: copy keystore.properties.example to keystore.properties and fill it in.
    goto :fail
  )
  set "TASK=assembleRelease"
  set "KIND=release"
  set "APK=app-release.apk"
)
echo [5/5] Building the %KIND% APK - the first build downloads Gradle and takes several minutes ...
pushd "%MOBILE%android"
call "%MOBILE%android\gradlew.bat" %TASK% --project-cache-dir "%FOCS_ANDROID_BUILD%\.gradle" --console=plain -q
if errorlevel 1 ( popd & goto :fail )
popd
set "BUILT=%FOCS_ANDROID_BUILD%\app\outputs\apk\%KIND%\%APK%"
if not exist "%BUILT%" (
  echo [x] The build finished but %BUILT% is missing.
  goto :fail
)
set "OUT=%MOBILE%Focs.apk"
if /i "%KIND%"=="debug" set "OUT=%MOBILE%Focs-debug.apk"
copy /y "%BUILT%" "%OUT%" >nul
echo.
echo   Done: %OUT%
echo   Copy it to a phone and open it there (allow "install unknown apps" when Android asks),
echo   or with the phone on USB debugging:  "%ANDROID_HOME%\platform-tools\adb" install -r "%OUT%"
echo.
exit /b 0

:no_java
echo [x] A Java 21 JDK was not found. Put one in %USERPROFILE%\.jdks (see README.md here) or set JAVA_HOME.
goto :fail
:no_sdk
echo [x] The Android SDK was not found at %ANDROID_HOME%. See README.md here for the three commands that install it.
goto :fail
:fail
echo.
echo [x] The app was not built. Scroll up for the first error message.
exit /b 1
