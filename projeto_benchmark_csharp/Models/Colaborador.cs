// =====================================================================
// MODELO: Colaborador
// Representa o cadastro de RH com dados ergonômicos/inclusivos.
// Combina os dois padrões existentes no Python (app.py e data_loader.py).
// =====================================================================
namespace TccBenchmark.Models;

public class Colaborador
{
    public string ColaboradorId { get; set; } = string.Empty;
    public string Nome { get; set; } = string.Empty;
    public string Setor { get; set; } = string.Empty;

    // ===== Dados de EPIs (app.py: 150 colaboradores, 8% PCD) =====
    public string TamanhoLuva { get; set; } = "M";
    public int TamanhoBota { get; set; } = 40;
    public bool PCD { get; set; }
    public string RestricaoErgonomica { get; set; } = "Nenhuma";
    public string LadoAfetado { get; set; } = "N/A";

    // ===== Dados de Materiais de Escritório (data_loader.py: 200 colabs, 15% restrições) =====
    public bool TemRestricaoEscritorio => RestricaoErgonomica != "Nenhuma";
}
