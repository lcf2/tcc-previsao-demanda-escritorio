// =====================================================================
// MODELO: PrevisaoFutura
// Resultado da projeção para os próximos 3 meses + regras inclusivas.
// Equivalente ao df_future + df_inclusive do Python.
// =====================================================================
namespace TccBenchmark.Models;

public class PrevisaoFutura
{
    public DateTime Data { get; set; }
    public string Setor { get; set; } = string.Empty;
    public string Material { get; set; } = string.Empty;
    public int PrevisaoBruta { get; set; }

    // ===== Colunas calculadas pelo Motor de Regras Inclusivas =====
    public int PrevisaoAdaptada { get; set; }
    public int QuantidadeEspecial { get; set; }
    public string ItemEspecial { get; set; } = "Nenhum";
    public string Observacao { get; set; } = "Nenhuma adequacao ergonomica pendente.";

    // ===== Regras específicas de Luvas / EPIs =====
    public int ParesCompletos { get; set; }
    public int LuvasAvulsasEsquerda { get; set; }
    public int LuvasAvulsasDireita { get; set; }
}
