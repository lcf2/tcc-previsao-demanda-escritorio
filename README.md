# Previsão de Demanda de Materiais de Escritório

Projeto acadêmico de previsão mensal de consumo com dois modelos: **Random Forest** em Python e **FastTree** em C#/.NET. Inclui dashboards locais e um benchmark temporal que compara os modelos usando o mesmo histórico.

## Modelos

- **Python:** `RandomForestRegressor`, do scikit-learn.
- **C#:** FastTree Regression, do ML.NET (gradient boosting).
- **Referência:** baseline de último consumo observado.

O benchmark integrado avalia um corte cronológico por execução e prevê os três meses seguintes. Compara MAE, RMSE, WAPE, viés, totais e tempos medidos. Um resultado melhor em um único corte não comprova que o modelo seja superior em todos os períodos. Consulte [a metodologia e as limitações](projeto_benchmark_csharp/Benchmark_Comparison.md).

## Requisitos

- Windows 10/11
- Python 3.10 ou superior
- .NET 8 SDK
- Git (opcional, para clonar o repositório)

## Instalação

Abra o PowerShell na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente, use o caminho direto do Python virtual:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O primeiro início do serviço C# pode restaurar os pacotes NuGet definidos em `projeto_benchmark_csharp/TccBenchmark.csproj`.

## Executar os dashboards

### Opção recomendada: iniciar os dois

Dê duplo clique em `executar_ambos.bat`. Na primeira execução, o arquivo cria o ambiente `.venv` e instala automaticamente as dependências Python de `requirements.txt` (é necessária conexão com a internet). Depois, abre:

- Python — <http://localhost:8501>
- C# — <http://localhost:5202>

Se o Python ou o .NET não estiverem instalados, o inicializador informa o que está faltando. Para o benchmark integrado, instale os dois requisitos; o dashboard Python sozinho não executa o FastTree.

### Abrir somente o Python

Depois de executar `executar_ambos.bat` ao menos uma vez, ou de instalar as dependências manualmente, use:

```powershell
.\.venv\Scripts\python.exe -m streamlit run main.py --server.port 8501
```

Também é possível abrir <http://localhost:8501>. Se o C# não estiver ativo, o dashboard Python tenta iniciá-lo automaticamente quando você executa o benchmark integrado. O endpoint C# usado na comparação é <http://localhost:5202/api/benchmark>.

Para iniciar o C# manualmente:

```powershell
dotnet run --project projeto_benchmark_csharp\TccBenchmark.csproj --no-launch-profile --urls http://localhost:5202
```

## Importar dados reais e comparar

1. Abra o dashboard Python em <http://localhost:8501>.
2. Na barra lateral, selecione a opção para importar a planilha Excel completa.
3. Envie o arquivo `.xlsx` localmente. Para a comparação integrada, o upload no dashboard C# é opcional: o Python envia o histórico ao serviço C# local.
4. Abra a aba **Benchmark RF × FastTree**.
5. Selecione o mês de corte e clique em **Executar os dois modelos**.

Os modelos treinam até o mesmo corte temporal e preveem os mesmos três meses. Antes de exibir a comparação, o dashboard verifica se os dados reais e o baseline coincidem entre Python e C#.

## Dados e privacidade

- Planilhas reais não fazem parte deste repositório. Não versione arquivos de dados confidenciais.
- O `.gitignore` exclui arquivos Excel e CSV, caches Python, builds .NET e arquivos locais de ambiente.
- A aplicação e o benchmark foram projetados para execução local; o benchmark integrado transmite o histórico do Python para o C# em `localhost`.
- A interface de benchmark apresenta resultados agregados, sem exibir nomes, códigos ou textos dos materiais.

## Limitações importantes

- O importador ainda **não classifica os tipos de movimento SAP**. Soma as quantidades assinadas por material/mês e converte o saldo negativo em consumo positivo. Valide com a área responsável quais movimentos representam consumo, estorno e entrada antes de usar a previsão em decisões de compra.
- Meses sem movimentação são tratados como consumo zero a partir do primeiro mês registrado para cada material. Essa interpretação depende de o extrato estar completo.
- A planilha importada não fornece setor ou cadastro de RH; as séries utilizam um setor genérico.
- O sistema prevê consumo mensal. Não calcula estoque de segurança, ponto de reposição, lead time ou lote econômico.
- Tempo e memória são medições de uma execução e do processo local; não representam custo de nuvem ou API.

## Estrutura principal

```text
main.py                              Dashboard Python e benchmark integrado
forecaster.py                        Random Forest e previsão
benchmark.py                         Avaliação temporal do Random Forest
data_loader.py                       Geração de dados sintéticos e importação Excel
projeto_benchmark_csharp/
  Program.cs                         API e dashboard C#
  Services/MlPipelineService.cs       FastTree e benchmark temporal
  Services/ExcelConsumptionImporter.cs Importação Excel no C#
  wwwroot/                            Interface web e logo local
executar_ambos.bat                    Inicialização dos dois dashboards
```

## Compilar o serviço C#

```powershell
dotnet build projeto_benchmark_csharp\TccBenchmark.csproj
```

## Licença e uso acadêmico

Consulte a licença do repositório, se definida. Confirme a qualidade e a semântica dos dados com a área responsável antes de usar os resultados operacionalmente.
