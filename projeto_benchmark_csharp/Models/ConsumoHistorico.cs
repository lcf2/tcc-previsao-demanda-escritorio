// =====================================================================
// MODELO: ConsumoHistorico
// Representa uma linha do histórico de consumo mensal de materiais/EPIs.
// Equivalente ao df_consumo / df_history do projeto Python.
// =====================================================================
namespace TccBenchmark.Models;

public class ConsumoHistorico
{
    public DateTime Data { get; set; }
    public int Ano => Data.Year;
    public int Mes => Data.Month;
    public string Material { get; set; } = string.Empty;
    public string Categoria { get; set; } = string.Empty;
    public string Subcategoria { get; set; } = string.Empty;
    public string Setor { get; set; } = string.Empty;
    public float QuantidadeConsumida { get; set; }
}
