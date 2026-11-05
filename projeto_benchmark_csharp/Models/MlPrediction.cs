// =====================================================================
// MODELO: MlPrediction
// Saída do modelo treinado. Contém o Score (= previsão) calculado
// pelo FastTreeRegressor do ML.NET.
// =====================================================================
using Microsoft.ML.Data;

namespace TccBenchmark.Models;

public class MlPrediction
{
    [ColumnName("Score")]
    public float Previsao { get; set; }
}
