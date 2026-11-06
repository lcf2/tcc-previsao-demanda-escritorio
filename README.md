# Previsão de Demanda de Materiais de Escritório

Projeto acadêmico de previsão mensal de consumo com dois modelos: **Random Forest** em Python e **FastTree** em C#/.NET. Inclui dashboards locais e um benchmark temporal que compara os modelos usando o mesmo histórico.

## Modelos

- **Python:** `RandomForestRegressor`, do scikit-learn.
- **C#:** FastTree Regression, do ML.NET (gradient boosting).
- **Regra manual:** previsão sazonal ingênua, repetindo para cada material/setor o consumo do mesmo mês do ano anterior; sem registro, assume zero.

O benchmark integrado avalia um corte cronológico por execução e prevê os doze meses seguintes. Compara Random Forest, FastTree e a regra sazonal manual pela mesma série de teste, usando MAE, RMSE e WAPE. O método manual repete o valor do mesmo mês do ano anterior; se esse mês não tiver registro no histórico, assume consumo zero. Um resultado melhor em um único corte não comprova que um método seja superior em todos os períodos. Consulte [a metodologia e as limitações](projeto_benchmark_csharp/Benchmark_Comparison.md).

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

Dê duplo clique em `executar_ambos.bat`. Ele abre:

- Python — <http://localhost:8501>
- C# — <http://localhost:5202>

### Abrir somente o Python

Na pasta do projeto, ative o ambiente virtual e execute:

```powershell
python -m streamlit run main.py --server.port 8501
```

Também é possível abrir <http://localhost:8501>. Se o C# não estiver ativo, o dashboard Python tenta iniciá-lo automaticamente quando você executa o benchmark integrado. O endpoint C# usado na comparação é <http://localhost:5202/api/benchmark>.

Para iniciar o C# manualmente:

```powershell
dotnet run --project projeto_benchmark_csharp\TccBenchmark.csproj --no-launch-profile --urls http://localhost:5202
```

## Importar dados reais e comparar

1. Abra o dashboard Python em <http://localhost:8501>.
2. Na barra lateral, selecione a opção para importar a planilha Excel completa.
3. Envie o arquivo `.xlsx` localmente ou coloque-o como `dados_privados/base_real.xlsx` na pasta do projeto. Nessa pasta local, ambos os dashboards carregam a base ao iniciar; no Python, selecione a origem Excel. O upload continua disponível para substituir a base.
4. Abra a aba **Benchmark RF × FastTree × sazonal**.
5. Selecione o mês de corte e clique em **Executar os dois modelos**.

Random Forest, FastTree e a regra manual são comparados no mesmo corte e nos mesmos doze meses. Na nova planilha de movimentações, o histórico termina em setembro de 2026; o corte mais recente é setembro de 2025 e o teste vai de outubro de 2025 a setembro de 2026. O dashboard verifica se os dois modelos usaram os mesmos registros reais; a regra manual é calculada localmente sobre essa série.

O formato de movimentações da nova planilha é lido da aba `Planilha2`, com material, quantidade, tipo de movimento e data de lançamento. A lista da aba `Planilha1` não é aplicada como filtro: seus itens não têm movimentações correspondentes na `Planilha2`. Assim, o benchmark usa somente os materiais que aparecem nas movimentações dessa aba.

O importador também reconhece tabelas já organizadas com material, data e quantidade em qualquer aba. Se a tabela tiver tipo de movimento SAP, aplica a regra de consumo/estorno; sem essa coluna, considera as quantidades como consumo absoluto.

No dashboard Python, a aba **Dashboard Preditivo** mostra, por material, o histórico, a previsão Random Forest de 90 dias e a validação temporal. A aba **Dashboard Sazonal Manual**, ao lado, exibe o histórico e a previsão para os próximos 12 meses, repetindo o consumo do mesmo mês do ano anterior e usando zero quando não há registro. O indicador MAPE não é exibido nos cartões do cabeçalho.

## Dados e privacidade

- Planilhas reais não fazem parte deste repositório. Não versione arquivos de dados confidenciais.
- O diretório local `dados_privados/` é ignorado pelo Git e pode guardar `base_real.xlsx` para carregamento automático nos dashboards.
- O `.gitignore` exclui arquivos Excel e CSV, caches Python, builds .NET e arquivos locais de ambiente.
- A aplicação e o benchmark foram projetados para execução local; o benchmark integrado transmite o histórico do Python para o C# em `localhost`.
- A interface de benchmark apresenta resultados agregados, sem exibir nomes, códigos ou textos dos materiais.

## Limitações importantes

- Quando a coluna de tipo de movimento está presente, o importador trata 201/261 como consumo e 202/262 como estorno; o estorno é subtraído do consumo no agregado mensal. Tipos diferentes desses são rejeitados para evitar classificação silenciosa. Confirme esse mapeamento com a área SAP antes de usar previsões em decisões de compra.
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
