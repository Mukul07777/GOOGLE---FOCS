@echo off
rem Starts Focs so a phone on the same Wi-Fi can reach it (the usual run.bat only answers this computer).
rem The window prints the address to type into the Focs app. Windows may ask once to allow Python on private networks.
rem Anyone on the same network can open Focs while this runs: use it at home, not on a public Wi-Fi.
set "HOST=0.0.0.0"
call "%~dp0..\run.bat" %*
