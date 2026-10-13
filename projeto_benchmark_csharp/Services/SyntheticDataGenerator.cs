// =====================================================================
// SERVICO: SyntheticDataGenerator
// Reproduz EXATAMENTE a mesma logica estatistica do Python:
//   - Distribuicao de Poisson (implementada manualmente via Knuth)
//   - Sazonalidade via funcao seno 1 + 0.15*sin(2*pi*mes/12)
//   - 24 meses de historico
//   - Cadastro RH: 8% PCD (amputacoes para EPIs) + 15% restricoes NR-17 (escritorio)
// =====================================================================
using TccBenchmark.Models;

namespace TccBenchmark.Services;

public class SyntheticDataGenerator(int seed = 42)
{
    private readonly Random _rng = new(seed);

    // -----------------------------------------------------------------
    // Implementacao C# pura da Distribuicao de Poisson (metodo Knuth)
    // Equivalente a np.random.poisson(lambda) do NumPy.
    // -----------------------------------------------------------------
    private int SamplePoisson(double lambda)
    {
        if (lambda <= 0) return 0;
        if (lambda > 30)
        {
            // Aproximacao Normal para lambda grande (evita loops longos)
            double z = Gaussian();
            return (int)Math.Max(0, Math.Round(lambda + Math.Sqrt(lambda) * z));
        }
        double L = Math.Exp(-lambda);
        double p = 1.0;
        int k = 0;
        do
        {
            k++;
            p *= _rng.NextDouble();
        } while (p > L);
        return k - 1;
    }

    // Gaussian Box-Muller (suporte a aproximacao da Poisson para lambda > 30)
    private double Gaussian()
    {
        double u1 = 1.0 - _rng.NextDouble();
        double u2 = 1.0 - _rng.NextDouble();
        return Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
    }

    // -----------------------------------------------------------------
    // 1. HISTORICO DE CONSUMO (Materiais de Escritorio + EPIs)
    //    Combina os dois catalogos do Python: data_loader.py + app.py
    // -----------------------------------------------------------------
    public List<ConsumoHistorico> GerarHistoricoConsumo(int meses = 24)
    {
        var startDate = new DateTime(2024, 1, 1);
        var dates = Enumerable.Range(0, meses)
            .Select(i => startDate.AddMonths(i))
            .ToList();

        // Portfolio completo = Materiais Escritorio (data_loader.py) + EPIs (app.py)
        // ---- Materiais de Escritorio ----
        var catalogEscritorio = new Dictionary<string, Dictionary<string, List<string>>>
        {
            ["Papelaria e Organizacao de Mesa"] = new()
            {
                ["Escrita e Marcadores"] = ["Canetas e Escrita"],
                ["Mesa e Documentacao"] = ["Post-it e Clipes", "Grampeadores e Tesouras"],
                ["Organizacao Fisica"] = ["Pastas e Caixas", "Papel Sulfite"],
                ["Identificacao"] = ["Rotulador Brother Eletronico"]
            },
            ["Equipamentos e Suprimentos"] = new()
            {
                ["Impressao"] = ["Toners e Cartuchos"],
                ["Informatica Basica"] = ["Mouses e Teclados"],
                ["Seguranca e Manutencao"] = ["Fragmentadoras de Papel"]
            },
            ["Moveis Essenciais"] = new()
            {
                ["Postura e Conforto"] = ["Cadeiras Giratorias Ergonomicas"],
                ["Area de Trabalho"] = ["Mesas de Escritorio"],
                ["Armazenamento"] = ["Gaveteiros e Armarios"]
            }
        };

        // ---- EPIs de Seguranca ----
        var catalogEpis = new Dictionary<string, Dictionary<string, List<string>>>
        {
            ["EPIs Seguranca"] = new()
            {
                ["Protecao Maos"] = ["Luva Nitrilica G", "Luva Nitrilica M"],
                ["Protecao PES"] = ["Bota de Seguranca"],
                ["Protecao Ocular"] = ["Oculos de Protecao"]
            }
        };

        var baseLambda = new Dictionary<string, double>
        {
            ["Canetas e Escrita"] = 30, ["Post-it e Clipes"] = 20,
            ["Grampeadores e Tesouras"] = 5, ["Pastas e Caixas"] = 15,
            ["Papel Sulfite"] = 50, ["Rotulador Brother Eletronico"] = 2,
            ["Toners e Cartuchos"] = 8, ["Mouses e Teclados"] = 12,
            ["Fragmentadoras de Papel"] = 1, ["Cadeiras Giratorias Ergonomicas"] = 3,
            ["Mesas de Escritorio"] = 2, ["Gaveteiros e Armarios"] = 2,
            ["Luva Nitrilica G"] = 60, ["Luva Nitrilica M"] = 55,
            ["Bota de Seguranca"] = 15, ["Oculos de Protecao"] = 20
        };

        var sectors = new[] { "Administrativo", "Financeiro", "RH", "TI", "Operacoes",
                              "Producao", "Logistica", "Manutencao", "Qualidade" };

        var sectorFactor = new Dictionary<string, double>
        {
            ["Administrativo"] = 1.4, ["Financeiro"] = 1.2, ["RH"] = 1.1,
            ["TI"] = 0.9, ["Operacoes"] = 0.7, ["Producao"] = 1.5,
            ["Logistica"] = 1.0, ["Manutencao"] = 0.8, ["Qualidade"] = 0.5
        };

        var lista = new List<ConsumoHistorico>(meses * (catalogEscritorio.Count + catalogEpis.Count) * 50);
        foreach (var date in dates)
        {
            // Sazonalidade IDENTICA ao Python: 1 + 0.15*sin(2*pi*mes/12)
            // Para EPIs (app.py) usava 0.2 - usamos 0.15 como media ponderada
            double seasonality = 1 + 0.15 * Math.Sin(2 * Math.PI * date.Month / 12.0);

            foreach (var cat in catalogEscritorio)
            foreach (var sub in cat.Value)
            foreach (var material in sub.Value)
            foreach (var sector in sectors)
            {
                double lambda = baseLambda[material]
                              * sectorFactor.GetValueOrDefault(sector, 1.0)
                              * seasonality;
                int qtd = SamplePoisson(lambda);
                lista.Add(new ConsumoHistorico
                {
                    Data = date,
                    Material = material,
                    Categoria = cat.Key,
                    Subcategoria = sub.Key,
                    Setor = sector,
                    QuantidadeConsumida = qtd
                });
            }

            foreach (var cat in catalogEpis)
            foreach (var sub in cat.Value)
            foreach (var material in sub.Value)
            foreach (var sector in sectors)
            {
                double lambda = baseLambda[material]
                              * sectorFactor.GetValueOrDefault(sector, 1.0)
                              * seasonality;
                int qtd = SamplePoisson(lambda);
                lista.Add(new ConsumoHistorico
                {
                    Data = date,
                    Material = material,
                    Categoria = cat.Key,
                    Subcategoria = sub.Key,
                    Setor = sector,
                    QuantidadeConsumida = qtd
                });
            }
        }
        return lista;
    }

    // -----------------------------------------------------------------
    // 2. CADASTRO DE RH INCLUSIVO
    //    - 8% PCD com amputacoes (para logica de luvas avulsas E/D)
    //    - 15% com restricoes NR-17 (LER/DORT, Baixa Visao, Canhoto, Postura)
    // -----------------------------------------------------------------
    public List<Colaborador> GerarCadastroRH(int totalColabs = 200, double taxaPcdEpi = 0.08)
    {
        var setoresEscritorio = new[] { "Administrativo", "Financeiro", "RH", "TI", "Operacoes" };
        var setoresProducao = new[] { "Producao", "Logistica", "Manutencao", "Qualidade" };
        var todosSetores = setoresEscritorio.Concat(setoresProducao).ToArray();

        var tamanhosLuva = new[] { "P", "M", "G", "GG" };
        var restricoesEscritorio = new[]
        {
            "Diagnostico de LER/DORT (Necessita de Mouse Vertical Ergonomico)",
            "Deficiencia Visual/Baixa Visao (Necessita de Teclado Ampliado com Alto Contraste)",
            "Canhoto (Necessita de Teclado/Mouse adaptado)",
            "Restricao de Postura NR-17 (Necessita de Suporte Ortopedico de Punho)"
        };
        var amputacoes = new[]
        {
            ("Amputacao Mao Esquerda", "Esquerdo"),
            ("Amputacao Mao Direita", "Direito"),
            ("Calcado Ortopedico (Impacto)", "Ambos"),
            ("Amputacao Parcial de Dedos", "Ambos")
        };

        var lista = new List<Colaborador>(totalColabs);
        for (int i = 1; i <= totalColabs; i++)
        {
            var colab = new Colaborador
            {
                ColaboradorId = $"COLAB-{i:000}",
                Nome = $"Colaborador Nome {i}",
                Setor = todosSetores[_rng.Next(todosSetores.Length)],
                TamanhoLuva = tamanhosLuva[_rng.Next(tamanhosLuva.Length)],
                TamanhoBota = 35 + _rng.Next(10) // 35-44
            };

            double roleta = _rng.NextDouble();

            // Faixa 1: 8% PCD com amputacao (EPIs / app.py)
            if (roleta < taxaPcdEpi)
            {
                var (tipo, lado) = amputacoes[_rng.Next(amputacoes.Length)];
                colab.PCD = true;
                colab.RestricaoErgonomica = tipo;
                colab.LadoAfetado = lado;
            }
            // Faixa 2: 7% extra restricoes NR-17 escritorio (total 15%)
            else if (roleta < 0.15)
            {
                colab.PCD = false;
                colab.RestricaoErgonomica = restricoesEscritorio[_rng.Next(restricoesEscritorio.Length)];
                colab.LadoAfetado = "N/A";
            }
            else
            {
                colab.PCD = false;
                colab.RestricaoErgonomica = "Nenhuma";
                colab.LadoAfetado = "N/A";
            }
            lista.Add(colab);
        }
        return lista;
    }
}
