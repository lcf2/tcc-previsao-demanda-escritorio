@echo off
title TCC - Random Forest Python + FastTree C#
cd /d "%~dp0"

echo Iniciando dashboard Python (RandomForestRegressor) em http://localhost:8501
start "Python - Random Forest" cmd /k "python -m streamlit run main.py --server.port 8501"

echo Iniciando dashboard C# (ML.NET FastTree) em http://localhost:5202
start "CSharp - FastTree" /D "%~dp0projeto_benchmark_csharp" cmd /k "dotnet run --no-launch-profile --urls http://localhost:5202"

echo.
echo Python: http://localhost:8501
echo C#:     http://localhost:5202
echo Se abrir somente o Python, clique em Executar os dois modelos; o C# sera iniciado automaticamente.
echo Para comparar os algoritmos, envie o Excel uma vez no dashboard Python;
echo o benchmark integrado envia o mesmo historico ao endpoint C#.
echo O upload no dashboard C# e opcional e serve apenas para uso independente.
pause
