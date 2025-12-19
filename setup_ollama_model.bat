@echo off
echo [INFO] Ollama 설치 확인 중...

:CHECK_OLLAMA
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [WAIT] Ollama가 아직 설치되지 않았거나 PATH에 등록되지 않았습니다. 설치 완료를 기다리는 중...
    timeout /t 5 >nul
    goto CHECK_OLLAMA
)

echo [INFO] Ollama가 감지되었습니다. 모델(llama3) 다운로드를 시작합니다...
echo [INFO] 이 작업은 몇 분 정도 걸릴 수 있습니다 (약 4~5GB).

ollama pull llama3

if %errorlevel% neq 0 (
    echo [ERROR] 모델 다운로드 실패. Ollama 서비스가 실행 중인지 확인하세요.
    echo 트레이 아이콘에서 Ollama를 실행하거나 'ollama serve'를 실행하세요.
    pause
    exit /b 1
)

echo [INFO] 모델 다운로드 완료! 테스트를 진행합니다.
ollama run llama3 "Hello! Are you ready for address correction?"

echo.
echo [SUCCESS] 모든 LLM 설정이 완료되었습니다! 백엔드와 연동 가능합니다.
pause
