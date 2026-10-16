@echo off
echo Starting QPI Backend, Frontend, and Admin Portal...
start "QPI Backend (Port 8001)" cmd /k "start_backend.bat"
start "QPI Admin Portal (Port 3001)" cmd /k "start_admin.bat"
start "QPI Frontend (Port 3002)" cmd /k "start_frontend.bat"
echo All services launched!
