@echo off
chcp 65001 >nul
echo [INFO] Ollama 설치 및 실행 대기 중...

:CHECK_OLLAMA_CMD
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [WAIT] Ollama 명령어를 찾을 수 없습니다. 설치가 완료될 때까지 기다립니다...
    timeout /t 5 >nul
    goto CHECK_OLLAMA_CMD
)

echo [INFO] Ollama 명령어가 감지되었습니다.

:TRY_PULL
echo [INFO] 모델(llama3) 다운로드를 시도합니다...
ollama pull llama3
if %errorlevel% neq 0 (
    echo [WAIT] Ollama 서버가 응답하지 않습니다. 백그라운드 실행을 기다리는 중입니다...
    echo (트레이 아이콘에 Ollama가 떴는지 확인해주세요)
    timeout /t 5 >nul
    goto TRY_PULL
)

echo.
echo [INFO] 모델 다운로드 완료! 간단한 테스트를 수행합니다.
ollama run llama3 "Hello! Address correction ready?"

echo.
echo [SUCCESS] 설정 완료! 이제 웹사이트에서 AI 보정 기능을 사용할 수 있습니다.
pause
