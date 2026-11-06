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
    private readonly object _modelLock = new();
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

        var features = new List<MlFeatureRow>(ordenado.Count);
        foreach (var grupo in ordenado.GroupBy(x => (x.Setor, x.Material)))
        {
            var serie = grupo.OrderBy(h => h.Data).ToList();
            float mediaLag1 = serie.Count > 1
                ? serie.Take(serie.Count - 1).Average(h => h.QuantidadeConsumida)
                : 0;
            float mediaLag2 = serie.Count > 2
                ? serie.Take(serie.Count - 2).Average(h => h.QuantidadeConsumida)
                : 0;

            for (int i = 0; i < serie.Count; i++)
            {
                var h = serie[i];
                features.Add(new MlFeatureRow
                {
                    Mes = h.Mes,
                    Ano = h.Ano,
                    Lag_1 = i > 0 ? serie[i - 1].QuantidadeConsumida : mediaLag1,
                    Lag_2 = i > 1 ? serie[i - 2].QuantidadeConsumida : mediaLag2,
                    Setor = h.Setor,
                    Material = h.Material,
                    Label = h.QuantidadeConsumida
                });
            }
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
    // Usa corte cronologico 80/20 por mes para nao separar materiais do mesmo periodo.
    // Recebe hiperparametros para o usuario ajustar via sidebar.
    // -----------------------------------------------------------------
    public (BenchmarkMetrics Metricas, List<float> ReaisTeste, List<float> PrevistosTeste)
        TreinarEAvaliar(List<MlFeatureRow> todasFeatures, FastTreeOptions? options = null)
    {
        lock (_modelLock)
            return TreinarEAvaliarCore(todasFeatures, options);
    }

    private (BenchmarkMetrics Metricas, List<float> ReaisTeste, List<float> PrevistosTeste)
        TreinarEAvaliarCore(List<MlFeatureRow> todasFeatures, FastTreeOptions? options)
    {
        options ??= new FastTreeOptions();
        var swTotal = Stopwatch.StartNew();

        // ========== Divisao Cronologica 80/20 por mes ==========
        var dates = todasFeatures
            .Select(feature => feature.Ano * 100 + feature.Mes)
            .Distinct()
            .OrderBy(date => date)
            .ToList();
        int splitDateIndex = (int)(dates.Count * 0.8);
        if (splitDateIndex < 1 || splitDateIndex >= dates.Count)
            throw new InvalidDataException(
                "São necessários pelo menos dois meses para avaliação temporal.");

        float cutoff = dates[splitDateIndex - 1];
        var treino = todasFeatures
            .Where(feature => feature.Ano * 100 + feature.Mes <= cutoff)
            .ToList();
        var teste = todasFeatures
            .Where(feature => feature.Ano * 100 + feature.Mes > cutoff)
            .ToList();
        if (treino.Count == 0 || teste.Count == 0)
            throw new InvalidDataException("A divisão temporal gerou treino ou teste vazio.");

        IDataView dvTreino = _ml.Data.LoadFromEnumerable(treino);
        IDataView dvTeste  = _ml.Data.LoadFromEnumerable(teste);

        // ========== Pipeline de Transformacoes ML.NET ==========
        // 1) One-Hot Encoding para Setor e Material
        // 2) Concatenacao de todas as features numericas+encoded em "Features"
        var pipeline = CriarPipeline(options);

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

        var reais = teste.Select(t => t.Label).ToList();

        // ========== Calculo MAE (Mean Absolute Error) ==========
        double mae = reais.Zip(previstos, (r, p) => Math.Abs(r - p)).Average();

        var observacoesPorAnoMes = treino.ToDictionary(
            row => ((int)row.Ano, (int)row.Mes, row.Setor, row.Material),
            row => row.Label);
        var previsoesSazonaisManuais = teste.Select(row =>
        {
            int anoAnterior = (int)row.Ano - 1;
            var chave = (anoAnterior, (int)row.Mes, row.Setor, row.Material);
            return observacoesPorAnoMes.TryGetValue(chave, out float quantidade)
                ? quantidade
                : 0f;
        }).ToList();
        double maeSazonalManual = reais.Zip(
            previsoesSazonaisManuais,
            (real, previsto) => Math.Abs(real - previsto)).Average();

        // ========== Calculo RMSE (Root Mean Squared Error) ==========
        double rmse = Math.Sqrt(reais.Zip(previstos, (r, p) => Math.Pow(r - p, 2)).Average());
        double rmseSazonalManual = Math.Sqrt(reais.Zip(
            previsoesSazonaisManuais,
            (real, previsto) => Math.Pow(real - previsto, 2)).Average());

        // Datas do periodo de teste (MM/yyyy) para eixo X do grafico comparativo
        var datasTeste = teste.Select(t => $"{t.Mes:00}/{t.Ano}").ToList();

        // Keep holdout metrics from the temporal split, but use all available
        // history for the operational forecast produced after this evaluation.
        var swTreinoCompleto = Stopwatch.StartNew();
        _modeloTreinado = pipeline.Fit(_ml.Data.LoadFromEnumerable(todasFeatures));
        swTreinoCompleto.Stop();
        swTotal.Stop();

        _colunasTreino = new[]
        {
            nameof(MlFeatureRow.Mes), nameof(MlFeatureRow.Ano),
            nameof(MlFeatureRow.Lag_1), nameof(MlFeatureRow.Lag_2),
            nameof(MlFeatureRow.Setor), nameof(MlFeatureRow.Material)
        };

        return (new BenchmarkMetrics
        {
            Mae = mae,
            MaeSazonalManual = maeSazonalManual,
            Rmse = rmse,
            RmseSazonalManual = rmseSazonalManual,
            TempoTreinamentoMs = swTreino.ElapsedMilliseconds + swTreinoCompleto.ElapsedMilliseconds,
            TempoInferenciaMs = swInf.ElapsedMilliseconds,
            LinhasTreino = treino.Count,
            LinhasTeste = teste.Count,
            PrevisoesSazonalManualTeste = previsoesSazonaisManuais,
            DatasTeste = datasTeste
        }, reais, previstos);
    }

    private IEstimator<ITransformer> CriarPipeline(FastTreeOptions options)
        => _ml.Transforms.Categorical.OneHotEncoding("SetorEncoded", nameof(MlFeatureRow.Setor))
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

    public TemporalBenchmarkMetrics ExecutarBenchmarkTemporal(
        List<ConsumoHistorico> historicoCompleto,
        DateTime corte,
        int horizonte,
        FastTreeOptions options)
    {
        lock (_modelLock)
        {
            if (horizonte < 1 || horizonte > 12)
                throw new ArgumentOutOfRangeException(nameof(horizonte), "O horizonte deve ser de 1 a 12 meses.");

            corte = new DateTime(corte.Year, corte.Month, 1);
            var treino = historicoCompleto
                .Where(h => h.Data < corte.AddMonths(1))
                .OrderBy(h => h.Setor)
                .ThenBy(h => h.Material)
                .ThenBy(h => h.Data)
                .ToList();
            var teste = historicoCompleto
                .Where(h => h.Data > corte && h.Data <= corte.AddMonths(horizonte))
                .ToList();

            if (treino.Count == 0)
                throw new InvalidDataException("Não há dados de treinamento até o mês de corte.");

            var grupos = treino.Select(h => (h.Setor, h.Material)).Distinct().ToHashSet();
            int pontosEsperados = grupos.Count * horizonte;
            var datasPrevistas = Enumerable.Range(1, horizonte)
                .Select(m => corte.AddMonths(m))
                .ToHashSet();
            var testeChaves = teste
                .Select(h => (h.Setor, h.Material, Data: new DateTime(h.Data.Year, h.Data.Month, 1)))
                .ToList();
            if (testeChaves.Count != pontosEsperados ||
                testeChaves.Distinct().Count() != pontosEsperados ||
                testeChaves.Any(k => !grupos.Contains((k.Setor, k.Material)) || !datasPrevistas.Contains(k.Data)))
                throw new InvalidDataException(
                    "O período de teste não tem exatamente um valor para cada material/setor em todos os meses.");

            var features = ConstruirFeatures(treino);
            IDataView trainingView = _ml.Data.LoadFromEnumerable(features);
            using var process = Process.GetCurrentProcess();
            long memoryBefore = process.WorkingSet64;
            long peakMemory = memoryBefore;
            object memoryLock = new();
            using var monitor = new Timer(_ =>
            {
                using var sampledProcess = Process.GetCurrentProcess();
                long workingSet = sampledProcess.WorkingSet64;
                lock (memoryLock)
                    peakMemory = Math.Max(peakMemory, workingSet);
            }, null, TimeSpan.Zero, TimeSpan.FromMilliseconds(20));

            TimeSpan cpuBefore = process.TotalProcessorTime;
            var trainingTimer = Stopwatch.StartNew();
            _modeloTreinado = CriarPipeline(options).Fit(trainingView);
            trainingTimer.Stop();

            var forecastTimer = Stopwatch.StartNew();
            var forecasts = PreverMesesCore(treino, horizonte);
            forecastTimer.Stop();
            TimeSpan cpuElapsed = process.TotalProcessorTime - cpuBefore;
            monitor.Change(Timeout.Infinite, Timeout.Infinite);
            lock (memoryLock)
                peakMemory = Math.Max(peakMemory, process.WorkingSet64);

            var actuals = teste.ToDictionary(
                h => (h.Setor, h.Material, Data: new DateTime(h.Data.Year, h.Data.Month, 1)),
                h => (double)h.QuantidadeConsumida);
            var comparisons = forecasts.Select(f =>
            {
                var key = (f.Setor, f.Material, Data: f.Data);
                return new TemporalBenchmarkPrediction(
                    f.Data,
                    f.Setor,
                    f.Material,
                    actuals[key],
                    f.PrevisaoBruta);
            }).ToList();

            var errors = comparisons.Select(p => p.Previsto - p.Real).ToList();
            double mae = errors.Average(error => Math.Abs(error));
            double rmse = Math.Sqrt(errors.Average(error => error * error));
            double realVolume = comparisons.Sum(p => Math.Abs(p.Real));
            double? wape = realVolume > 0
                ? errors.Sum(error => Math.Abs(error)) / realVolume
                : null;
            var observedValues = treino.ToDictionary(
                row => (new DateTime(row.Data.Year, row.Data.Month, 1), row.Setor, row.Material),
                row => (double)row.QuantidadeConsumida);
            var seasonalErrors = comparisons.Select(prediction =>
            {
                var previousYearKey = (
                    prediction.Data.AddYears(-1),
                    prediction.Setor,
                    prediction.Material);
                double previousYearValue = observedValues.GetValueOrDefault(previousYearKey);
                return (Error: previousYearValue - prediction.Real, Forecast: previousYearValue);
            }).ToList();
            double maeSazonalManual = seasonalErrors.Average(item => Math.Abs(item.Error));
            double rmseSazonalManual = Math.Sqrt(
                seasonalErrors.Average(item => item.Error * item.Error));
            double? wapeSazonalManual = realVolume > 0
                ? seasonalErrors.Sum(item => Math.Abs(item.Error)) / realVolume
                : null;
            double totalSazonalManual = seasonalErrors.Sum(item => item.Forecast);
            double memoryBeforeMb = memoryBefore / (1024d * 1024d);
            double peakMb = peakMemory / (1024d * 1024d);

            _colunasTreino = new[]
            {
                nameof(MlFeatureRow.Mes), nameof(MlFeatureRow.Ano),
                nameof(MlFeatureRow.Lag_1), nameof(MlFeatureRow.Lag_2),
                nameof(MlFeatureRow.Setor), nameof(MlFeatureRow.Material)
            };

            return new TemporalBenchmarkMetrics(
                mae,
                rmse,
                wape,
                maeSazonalManual,
                rmseSazonalManual,
                wapeSazonalManual,
                totalSazonalManual,
                errors.Average(),
                comparisons.Sum(p => p.Real),
                comparisons.Sum(p => p.Previsto),
                errors.Count(error => error > 0),
                errors.Count(error => error < 0),
                comparisons.Count,
                features.Count,
                trainingTimer.Elapsed.TotalMilliseconds,
                forecastTimer.Elapsed.TotalMilliseconds,
                cpuElapsed.TotalMilliseconds,
                memoryBeforeMb,
                peakMb,
                Math.Max(0, peakMb - memoryBeforeMb),
                comparisons);
        }
    }

    public List<PrevisaoFutura> PreverProximos3Meses(List<ConsumoHistorico> historico)
        => PreverProximosMeses(historico, 3);

    public List<PrevisaoFutura> PreverProximosMeses(List<ConsumoHistorico> historico, int horizonte)
    {
        lock (_modelLock)
            return PreverMesesCore(historico, horizonte);
    }

    private List<PrevisaoFutura> PreverMesesCore(List<ConsumoHistorico> historico, int horizonte)
    {
        if (_modeloTreinado == null)
            throw new InvalidOperationException("Treine o modelo antes de prever.");
        if (horizonte < 1)
            throw new ArgumentOutOfRangeException(nameof(horizonte));

        var combinacoes = historico.Select(h => (h.Setor, h.Material)).Distinct().ToList();
        var historicoPorGrupo = historico
            .GroupBy(h => (h.Setor, h.Material))
            .ToDictionary(
                group => group.Key,
                group => group.OrderBy(h => h.Data).Select(h => h.QuantidadeConsumida).ToList());
        var datasFuturas = Enumerable.Range(1, horizonte)
            .Select(m =>
            {
                DateTime date = historico.Max(h => h.Data).AddMonths(m);
                return new DateTime(date.Year, date.Month, 1);
            })
            .ToList();
        var engine = _ml.Model.CreatePredictionEngine<MlFeatureRow, MlPrediction>(_modeloTreinado);
        var resultados = new List<PrevisaoFutura>(datasFuturas.Count * combinacoes.Count);

        foreach (var data in datasFuturas)
        foreach (var (setor, material) in combinacoes)
        {
            var serie = historicoPorGrupo[(setor, material)];
            float lag1 = serie[^1];
            float lag2 = serie.Count > 1 ? serie[^2] : lag1;
            var input = new MlFeatureRow
            {
                Mes = data.Month,
                Ano = data.Year,
                Lag_1 = lag1,
                Lag_2 = lag2,
                Setor = setor,
                Material = material
            };
            int previsaoInt = Math.Max(0, (int)Math.Round(engine.Predict(input).Previsao));
            serie.Add(previsaoInt);
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
