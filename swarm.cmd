@echo off
rem Windows launcher for the Swarm Hub. Usage:  swarm setup  |  swarm  |  swarm adduser <name>
rem Bypass only applies to this one script, so it runs even where PowerShell scripts are blocked.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\swarm.ps1" %*
