@echo off
chcp 65001 >nul
echo [INFO] 사내망 접속용 서버를 시작합니다...
echo.
echo [INFO] 필수 라이브러리 확인 및 설치 중...
pip install -r backend/requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] 라이브러리 설치 실패! Python이 설치되어 있는지 확인하세요.
    pause
    exit /b
)

echo [INFO] Ollama(AI) 실행 상태 확인 중...
tasklist | findstr "ollama.exe" >nul
if %errorlevel% neq 0 (
    echo [WARNING] Ollama가 실행 중이지 않습니다! AI 주소 보정 기능이 작동하지 않을 수 있습니다.
    echo [TIP] 'setup_ollama_v2.bat'를 실행하거나 Ollama를 먼저 켜주세요.
) else (
    echo [OK] Ollama가 실행 중입니다.
)

echo [BACKEND] API 서버 시작 (Port 8000)
start "SpatialAddressPro-Backend" cmd /k "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [FRONTEND] 웹 서버 시작 (Port 5173)...
echo.
echo ========================================================
echo   접속 주소: http://192.168.0.8:5173
echo   (사내 동료들에게 이 주소를 공유하세요)
echo ========================================================
echo.
cd frontend
npm run dev -- --host 0.0.0.0
pause
