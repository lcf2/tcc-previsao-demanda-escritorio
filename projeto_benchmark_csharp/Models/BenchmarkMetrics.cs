// =====================================================================
// MODELO: BenchmarkMetrics
// Contêiner para as métricas finais usadas no relatório comparativo
// (MAE, tempos em ms, contagem de dados).
// =====================================================================
namespace TccBenchmark.Models;

public class BenchmarkMetrics
{
    public double Mae { get; set; }
    public double MaeSazonalManual { get; set; }
    public double Rmse { get; set; }
    public double RmseSazonalManual { get; set; }
    public long TempoTreinamentoMs { get; set; }
    public long TempoInferenciaMs { get; set; }
    public int LinhasTreino { get; set; }
    public int LinhasTeste { get; set; }
    public int TotalColaboradores { get; set; }
    public int TotalPCDs { get; set; }
    public int TotalPrevisoesFuturas { get; set; }
    public List<float> PrevisoesSazonalManualTeste { get; set; } = new();
    public List<string> DatasTeste { get; set; } = new();
}
