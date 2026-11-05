// =====================================================================
// MODELO: MlFeatureRow
// Representa a linha de features numéricas/categóricas que alimenta
// o trainer do ML.NET. Contém Lag_1, Lag_2, Mês, Ano, e colunas
// categóricas (Setor, Material) para One-Hot Encoding.
// =====================================================================
using Microsoft.ML.Data;

namespace TccBenchmark.Models;

public class MlFeatureRow
{
    [LoadColumn(0)] public float Mes { get; set; }
    [LoadColumn(1)] public float Ano { get; set; }
    [LoadColumn(2)] public float Lag_1 { get; set; }
    [LoadColumn(3)] public float Lag_2 { get; set; }
    [LoadColumn(4)] public string Setor { get; set; } = string.Empty;
    [LoadColumn(5)] public string Material { get; set; } = string.Empty;
    [LoadColumn(6)] public float Label { get; set; } // QuantidadeConsumida (alvo)
}
