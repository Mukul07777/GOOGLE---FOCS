@echo off
rem Pre-make the detailed notes library with the AI, so students get every topic's notes instantly.
rem   build_notes.bat --exam jee                      every JEE topic (a few hours on the free AI tier; safe to stop and resume)
rem   build_notes.bat --exam neet --subject Biology   one subject
rem   build_notes.bat --exam jee --limit 20           just the next 20 topics
rem   build_notes.bat --exam jee --capsules           the chapters' last-day revision capsules
rem   build_notes.bat --exam jee --asked              every chapter's most-asked topics (last-day revision; a few minutes)
setlocal
title Focs - notes library
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first, so Focs is installed.
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Usage: build_notes.bat --exam jee^|neet [--subject Physics] [--chapter "Kinematics"] [--limit 20] [--capsules] [--asked]
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\build_topic_notes.py %*
pause
