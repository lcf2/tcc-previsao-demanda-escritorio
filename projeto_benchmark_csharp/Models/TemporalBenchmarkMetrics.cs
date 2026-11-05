namespace TccBenchmark.Models;

public sealed record TemporalBenchmarkMetrics(
    double Mae,
    double Rmse,
    double? Wape,
    double BaselineMae,
    double BaselineRmse,
    double? BaselineWape,
    double BaselineTotalPrevisto,
    double Vies,
    double TotalReal,
    double TotalPrevisto,
    int Sobreprevisoes,
    int Subprevisoes,
    int PontosTeste,
    int LinhasTreino,
    double TempoTreinamentoMs,
    double TempoPrevisaoMs,
    double TempoCpuMs,
    double MemoriaBaseMb,
    double PicoMemoriaMb,
    double AumentoPicoMemoriaMb,
    IReadOnlyList<TemporalBenchmarkPrediction> Previsoes);

public sealed record TemporalBenchmarkPrediction(
    DateTime Data,
    string Setor,
    string Material,
    double Real,
    double Previsto);
