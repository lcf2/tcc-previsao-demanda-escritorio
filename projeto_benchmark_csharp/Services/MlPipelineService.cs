// =====================================================================
// SERVICO: MlPipelineService
// Pipeline preditivo completo em ML.NET:
//   a) Feature Engineering: Mes, Ano, Lag_1, Lag_2 (por grupo Setor+Material)
//   b) One-Hot Encoding das colunas categoricas (Setor, Material)
//   c) Treinamento FastTreeRegression (Gradient Boosted Trees)
//      -> CONTRASTE intencional com Random Forest (Bagging) do Scikit-Learn
//   d) Avaliacao MAE + medicao exata via Stopwatch
//   e) Previsao recursiva para os proximos 3 meses
// =====================================================================
using System.Diagnostics;
using Microsoft.ML;
using Microsoft.ML.Data;
using TccBenchmark.Models;

namespace TccBenchmark.Services;

public class MlPipelineService
{
    private readonly MLContext _ml = new(seed: 42);
    private ITransformer? _modeloTreinado;
    private string[]? _colunasTreino;

    // -----------------------------------------------------------------
    // Feature Engineering: cria linhas MlFeatureRow com Lag_1 e Lag_2
    // Ordena por Setor->Material->Data para replicar a semantica do
    // groupby(['Setor','Material']).shift() do Pandas.
    // -----------------------------------------------------------------
    public List<MlFeatureRow> ConstruirFeatures(List<ConsumoHistorico> historico)
    {
        var ordenado = historico
            .OrderBy(h => h.Setor)
            .ThenBy(h => h.Material)
            .ThenBy(h => h.Data)
            .ToList();

        // Chave = (Setor, Material) -> guarda os ultimos 2 valores para Lag
        var ultimosPorGrupo = new Dictionary<(string, string), (float Lag1, float Lag2)>();
        var mediaPorGrupo = new Dictionary<(string, string), float>();

        // 1a passagem: calcula media por grupo para preencher NaNs iniciais
        foreach (var g in ordenado.GroupBy(x => (x.Setor, x.Material)))
            mediaPorGrupo[g.Key] = (float)g.Average(x => x.QuantidadeConsumida);

        var features = new List<MlFeatureRow>(ordenado.Count);
        foreach (var h in ordenado)
        {
            var chave = (h.Setor, h.Material);
            float media = mediaPorGrupo[chave];

            if (!ultimosPorGrupo.TryGetValue(chave, out var ult))
                ult = (media, media); // primeira ocorrencia: usa media do grupo

            features.Add(new MlFeatureRow
            {
                Mes = h.Mes,
                Ano = h.Ano,
                Lag_1 = ult.Lag1,
                Lag_2 = ult.Lag2,
                Setor = h.Setor,
                Material = h.Material,
                Label = h.QuantidadeConsumida
            });

            // Atualiza janela deslizante para a proxima linha do grupo
            ultimosPorGrupo[chave] = (h.QuantidadeConsumida, ult.Lag1);
        }
        return features;
    }

    // -----------------------------------------------------------------
    // Hiperparametros do FastTree (ajustaveis pelo Dashboard Web)
    // -----------------------------------------------------------------
    public record FastTreeOptions(
        int NumberOfTrees = 100,
        int NumberOfLeaves = 20,
        int MinimumExampleCountPerLeaf = 5,
        double LearningRate = 0.2);

    // -----------------------------------------------------------------
    // Pipeline completo: Transformacoes + Trainer FastTree + metricas
    // Usa divisao TEMPORAL 80/20 (sem shuffle) = mesmo protocolo Python.
    // Recebe hiperparametros para o usuario ajustar via sidebar.
    // -----------------------------------------------------------------
    public (BenchmarkMetrics Metricas, List<float> ReaisTeste, List<float> PrevistosTeste)
        TreinarEAvaliar(List<MlFeatureRow> todasFeatures, FastTreeOptions? options = null)
    {
        options ??= new FastTreeOptions();
        var swTotal = Stopwatch.StartNew();

        // ========== Divisao Temporal 80/20 (idêntica ao Python) ==========
        int split = (int)(todasFeatures.Count * 0.8);
        var treino = todasFeatures.Take(split).ToList();
        var teste  = todasFeatures.Skip(split).ToList();

        IDataView dvTreino = _ml.Data.LoadFromEnumerable(treino);
        IDataView dvTeste  = _ml.Data.LoadFromEnumerable(teste);

        // ========== Pipeline de Transformacoes ML.NET ==========
        // 1) One-Hot Encoding para Setor e Material
        // 2) Concatenacao de todas as features numericas+encoded em "Features"
        var pipeline = _ml.Transforms.Categorical.OneHotEncoding("SetorEncoded", nameof(MlFeatureRow.Setor))
            .Append(_ml.Transforms.Categorical.OneHotEncoding("MaterialEncoded", nameof(MlFeatureRow.Material)))
            .Append(_ml.Transforms.Concatenate("Features",
                nameof(MlFeatureRow.Mes),
                nameof(MlFeatureRow.Ano),
                nameof(MlFeatureRow.Lag_1),
                nameof(MlFeatureRow.Lag_2),
                "SetorEncoded",
                "MaterialEncoded"))
            .Append(_ml.Regression.Trainers.FastTree(
                labelColumnName: nameof(MlFeatureRow.Label),
                featureColumnName: "Features",
                numberOfLeaves: options.NumberOfLeaves,
                numberOfTrees: options.NumberOfTrees,
                minimumExampleCountPerLeaf: options.MinimumExampleCountPerLeaf,
                learningRate: (float)options.LearningRate));

        // ========== Treinamento c/ medicao de tempo ==========
        var swTreino = Stopwatch.StartNew();
        _modeloTreinado = pipeline.Fit(dvTreino);
        swTreino.Stop();

        // ========== Inferencia no conjunto de TESTE ==========
        var swInf = Stopwatch.StartNew();
        IDataView predicoesTeste = _modeloTreinado.Transform(dvTeste);
        var previstos = _ml.Data.CreateEnumerable<MlPrediction>(predicoesTeste, reuseRowObject: false)
            .Select(p => p.Previsao)
            .ToList();
        swInf.Stop();
        swTotal.Stop();

        var reais = teste.Select(t => t.Label).ToList();

        // ========== Calculo MAE (Mean Absolute Error) ==========
        double mae = reais.Zip(previstos, (r, p) => Math.Abs(r - p)).Average();

        // Baseline: Media Movel Simples 3 periodos (NAO usa IA -> referencia)
        var linhaBase = new List<float>();
        for (int i = 0; i < teste.Count; i++)
        {
            int globalIdx = split + i;
            int inicioJanela = Math.Max(0, globalIdx - 3);
            float media = todasFeatures.Skip(inicioJanela).Take(globalIdx - inicioJanela)
                                                       .Select(f => f.Label)
                                                       .DefaultIfEmpty(0)
                                                       .Average();
            linhaBase.Add(media);
        }
        double maeBase = reais.Zip(linhaBase, (r, p) => Math.Abs(r - p)).Average();

        // ========== Calculo RMSE (Root Mean Squared Error) ==========
        double rmse = Math.Sqrt(reais.Zip(previstos, (r, p) => Math.Pow(r - p, 2)).Average());
        double rmseBase = Math.Sqrt(reais.Zip(linhaBase, (r, p) => Math.Pow(r - p, 2)).Average());

        // Datas do periodo de teste (MM/yyyy) para eixo X do grafico comparativo
        var datasTeste = teste.Select(t => $"{t.Mes:00}/{t.Ano}").ToList();

        _colunasTreino = new[]
        {
            nameof(MlFeatureRow.Mes), nameof(MlFeatureRow.Ano),
            nameof(MlFeatureRow.Lag_1), nameof(MlFeatureRow.Lag_2),
            nameof(MlFeatureRow.Setor), nameof(MlFeatureRow.Material)
        };

        return (new BenchmarkMetrics
        {
            Mae = mae,
            MaeBaseline = maeBase,
            Rmse = rmse,
            RmseBaseline = rmseBase,
            TempoTreinamentoMs = swTreino.ElapsedMilliseconds,
            TempoInferenciaMs = swInf.ElapsedMilliseconds,
            LinhasTreino = treino.Count,
            LinhasTeste = teste.Count,
            PrevisoesBaselineTeste = linhaBase,
            DatasTeste = datasTeste
        }, reais, previstos);
    }

    // -----------------------------------------------------------------
    // Previsao RECURSIVA para os proximos 3 meses (igual ao forecaster.py)
    // Para cada mes futuro -> Setor x Material -> calcula Lags -> prediz
    // -----------------------------------------------------------------
    public List<PrevisaoFutura> PreverProximos3Meses(List<ConsumoHistorico> historico)
    {
        if (_modeloTreinado == null)
            throw new InvalidOperationException("Treine o modelo antes de prever.");

        DateTime ultimaData = historico.Max(h => h.Data);
        var datasFuturas = Enumerable.Range(1, 3)
            .Select(m => new DateTime(ultimaData.AddMonths(m).Year, ultimaData.AddMonths(m).Month, 1))
            .ToList();

        var combinacoes = historico.Select(h => (h.Setor, h.Material)).Distinct().ToList();
        var engine = _ml.Model.CreatePredictionEngine<MlFeatureRow, MlPrediction>(_modeloTreinado);

        var resultados = new List<PrevisaoFutura>(datasFuturas.Count * combinacoes.Count);

        foreach (var data in datasFuturas)
        foreach (var (setor, material) in combinacoes)
        {
            // Ultimos 2 valores conhecidos do grupo para Lag_1 e Lag_2
            var serie = historico
                .Where(h => h.Setor == setor && h.Material == material)
                .OrderBy(h => h.Data)
                .ToList();

            float lag1 = serie.Count >= 1 ? serie[^1].QuantidadeConsumida : 0;
            float lag2 = serie.Count >= 2 ? serie[^2].QuantidadeConsumida : lag1;

            var input = new MlFeatureRow
            {
                Mes = data.Month,
                Ano = data.Year,
                Lag_1 = lag1,
                Lag_2 = lag2,
                Setor = setor,
                Material = material
            };
            float pred = engine.Predict(input).Previsao;
            int previsaoInt = Math.Max(0, (int)Math.Round(pred));

            resultados.Add(new PrevisaoFutura
            {
                Data = data,
                Setor = setor,
                Material = material,
                PrevisaoBruta = previsaoInt,
                PrevisaoAdaptada = previsaoInt
            });
        }
        return resultados;
    }
}
