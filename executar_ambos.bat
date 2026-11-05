@echo off
setlocal
title TCC - Random Forest Python + FastTree C#
cd /d "%~dp0"

set "DOTNET_AVAILABLE=1"
where dotnet >nul 2>nul
if errorlevel 1 (
    set "DOTNET_AVAILABLE=0"
    echo AVISO: dotnet nao foi encontrado. O Python sera iniciado,
    echo mas o benchmark precisa do .NET 8 SDK. Instale em https://dotnet.microsoft.com/download/dotnet/8.0
    echo.
) else (
    echo Iniciando dashboard C# (ML.NET FastTree) em http://localhost:5202
    start "CSharp - FastTree" /D "%~dp0projeto_benchmark_csharp" cmd /k "dotnet run --no-launch-profile --urls http://localhost:5202"
)

set "PYTHON_LAUNCHER="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_LAUNCHER=py -3"
if not defined PYTHON_LAUNCHER (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_LAUNCHER=python"
)

if not defined PYTHON_LAUNCHER (
    echo ERRO: Python 3 nao foi encontrado.
    echo Instale Python 3.10 ou superior em https://www.python.org/downloads/
    echo Durante a instalacao, marque "Add python.exe to PATH".
    pause
    exit /b 1
)

%PYTHON_LAUNCHER% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo ERRO: e necessario Python 3.10 ou superior.
    echo Instale uma versao compativel e execute este arquivo novamente.
    pause
    exit /b 1
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo Criando ambiente virtual Python do projeto...
    %PYTHON_LAUNCHER% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo ERRO: nao foi possivel criar o ambiente virtual.
        echo Verifique a instalacao do Python e tente executar este arquivo novamente.
        pause
        exit /b 1
    )
)

"%VENV_PYTHON%" -c "import streamlit, pandas, numpy, sklearn, matplotlib, seaborn, openpyxl, plotly" >nul 2>nul
if errorlevel 1 (
    echo Instalando as dependencias Python. A primeira execucao precisa de internet...
    "%VENV_PYTHON%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo ERRO: falha ao instalar as dependencias Python.
        echo Confira sua conexao com a internet e tente novamente.
        pause
        exit /b 1
    )
)

echo Iniciando dashboard Python (RandomForestRegressor) em http://localhost:8501
start "Python - Random Forest" cmd /k ""%VENV_PYTHON%" -m streamlit run "%~dp0main.py" --server.port 8501"

echo.
echo Python: http://localhost:8501
if "%DOTNET_AVAILABLE%"=="1" echo C#:     http://localhost:5202
if "%DOTNET_AVAILABLE%"=="0" echo C#:     instale .NET 8 SDK para usar o FastTree
echo Para comparar, envie o Excel uma vez no dashboard Python e clique em Executar os dois modelos.
echo Se abrir somente o Python, ele tenta iniciar o servico C# ao executar o benchmark.
pause
