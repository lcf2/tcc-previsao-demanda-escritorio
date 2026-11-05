// =====================================================================
// SERVICO: InclusiveRulesEngine
// Motor de regras que cruza as previsoes brutas do ML.NET com o cadastro
// de RH para gerar o plano de compras ADAPTADO (conformidade NR-17/ESG).
//
// Dois blocos de regras replicando o Python:
//   BLOCO A) EPIs/Luvas: mix pares completos vs avulsas (Esquerda/Direita)
//   BLOCO B) Materiais Escritorio: LER/DORT, Baixa Visao, Canhoto, Postura
// =====================================================================
using TccBenchmark.Models;

namespace TccBenchmark.Services;

public class InclusiveRulesEngine
{
    public List<PrevisaoFutura> AplicarRegras(
        List<PrevisaoFutura> previsoesBrutas,
        List<Colaborador> colaboradores)
    {
        var resultado = new List<PrevisaoFutura>(previsoesBrutas.Count);

        foreach (var p in previsoesBrutas)
        {
            var clone = new PrevisaoFutura
            {
                Data = p.Data,
                Setor = p.Setor,
                Material = p.Material,
                PrevisaoBruta = p.PrevisaoBruta,
                PrevisaoAdaptada = p.PrevisaoBruta,
                QuantidadeEspecial = 0,
                ItemEspecial = "Nenhum",
                Observacao = "Nenhuma adequacao ergonomica pendente para este material no setor."
            };

            // Colaboradores do setor da linha atual
            var colabsSetor = colaboradores.Where(c => c.Setor == p.Setor).ToList();

            // ==============================================================
            // BLOCO A - EPIs: Luvas (avulsas E/D) + Bota Ortopedica
            // ==============================================================
            if (p.Material.Contains("Luva", StringComparison.OrdinalIgnoreCase))
            {
                AplicarRegraLuvas(clone, colabsSetor);
            }
            else if (p.Material.Contains("Bota", StringComparison.OrdinalIgnoreCase))
            {
                AplicarRegraBotaOrtopedica(clone, colabsSetor);
            }
            // ==============================================================
            // BLOCO B - Materiais de Escritorio (NR-17)
            // ==============================================================
            else if (ContemQualquer(p.Material, "mouse", "teclado"))
            {
                AplicarRegraGenerica(clone, colabsSetor,
                    "Combo Mouse Vertical + Teclado Split Ergonomico",
                    "LER/DORT");
            }
            else if (ContemQualquer(p.Material, "rotulador"))
            {
                AplicarRegraGenerica(clone, colabsSetor,
                    "Rotulador com Teclas de Auto-Relevo/Braille",
                    "Visual", "Visao");
            }
            else if (ContemQualquer(p.Material, "cadeira"))
            {
                AplicarRegraGenerica(clone, colabsSetor,
                    "Cadeiras Ergonomicas Ajustaveis Premium (NR-17)",
                    "Postura", "NR-17");
            }
            else if (ContemQualquer(p.Material, "caneta", "escrita"))
            {
                AplicarRegraGenerica(clone, colabsSetor,
                    "Canetas Ergonomicas Canhotas",
                    "Canhoto");
            }

            resultado.Add(clone);
        }
        return resultado;
    }

    // -----------------------------------------------------------------
    // REGRA ESPECIAL: Luvas avulsas (amputacao unilateral)
    // - "Direito" afetado -> precisa apenas de luva ESQUERDA avulsa
    // - "Esquerdo" afetado -> precisa apenas de luva DIREITA avulsa
    // - "Ambos"        -> bota ortopedica / tratado separado
    // -----------------------------------------------------------------
    private static void AplicarRegraLuvas(PrevisaoFutura p, List<Colaborador> colabsSetor)
    {
        var pcdsAmputacao = colabsSetor
            .Where(c => c.PCD && c.RestricaoErgonomica.Contains("Amputacao")
                     && c.RestricaoErgonomica.Contains("Mao"))
            .ToList();

        int esqAvulsa = pcdsAmputacao.Count(c => c.LadoAfetado == "Direito");  // falta mao direita -> usa esq
        int dirAvulsa = pcdsAmputacao.Count(c => c.LadoAfetado == "Esquerdo"); // falta mao esquerda -> usa dir
        int totalAvulsas = esqAvulsa + dirAvulsa;

        p.LuvasAvulsasEsquerda = esqAvulsa;
        p.LuvasAvulsasDireita  = dirAvulsa;
        p.ParesCompletos       = Math.Max(0, p.PrevisaoBruta - totalAvulsas);
        p.PrevisaoAdaptada     = p.ParesCompletos;
        p.QuantidadeEspecial   = totalAvulsas;

        if (totalAvulsas > 0)
        {
            p.ItemEspecial = $"{esqAvulsa}x Luva Avulsa (ESQ) + {dirAvulsa}x Luva Avulsa (DIR)";
            p.Observacao = $"Ajuste Inclusivo: Comprar {p.ParesCompletos} pares completos + "
                         + $"{esqAvulsa} luvas ESQUERDA avulsas + {dirAvulsa} luvas DIREITA avulsas. "
                         + "Reduzir lote comum para evitar desperdicio de par incompleto.";
        }
    }

    private static void AplicarRegraBotaOrtopedica(PrevisaoFutura p, List<Colaborador> colabsSetor)
    {
        int orto = colabsSetor.Count(c =>
            c.PCD && c.RestricaoErgonomica.Contains("Calcado Ortopedico"));

        if (orto > 0)
        {
            p.PrevisaoAdaptada   = Math.Max(0, p.PrevisaoBruta - orto);
            p.QuantidadeEspecial = orto;
            p.ItemEspecial       = "Bota de Seguranca com Palmilha Ortopedica (Sob Medida)";
            p.Observacao = $"Ajuste PCD: {orto}x bota ortopedica medido junto ao RH. "
                         + $"Reduzir lote comum em {orto} pares.";
        }
    }

    private static void AplicarRegraGenerica(
        PrevisaoFutura p,
        List<Colaborador> colabsSetor,
        string itemAdaptado,
        params string[] restricaoContem)
    {
        int contagem = colabsSetor.Count(c =>
            c.RestricaoErgonomica != "Nenhuma" &&
            restricaoContem.Any(r => c.RestricaoErgonomica.Contains(r, StringComparison.OrdinalIgnoreCase)));

        if (contagem <= 0) return;

        p.PrevisaoAdaptada   = Math.Max(0, p.PrevisaoBruta - contagem);
        p.QuantidadeEspecial = contagem;
        p.ItemEspecial       = itemAdaptado;
        p.Observacao = $"Ajuste NR-17/Inclusao: Encomendar {contagem}x {itemAdaptado} sob medida e reduzir lote comum.";
    }

    private static bool ContemQualquer(string texto, params string[] palavras)
        => palavras.Any(p => texto.Contains(p, StringComparison.OrdinalIgnoreCase));
}
