@echo off

set curPath=%~dp0
set srcPath=%curPath%\src

python3 %srcPath%\provisioner.py %*
