// =====================================================================
// PROGRAM.CS - ASP.NET CORE WEB (MINIMAL API) - TCC UNIP
// =====================================================================
// Sobe servidor web em localhost:5000 com Dashboard Interativo
// (Bootstrap 5 + Chart.js). Reuso os 3 servicos do Console original:
//   SyntheticDataGenerator  -> Poisson + Sazonalidade + RH (8% PCD)
//   MlPipelineService       -> FastTreeRegression (ML.NET)
//   InclusiveRulesEngine    -> Mix Luvas E/D + Regras NR-17
// =====================================================================
using System.Text.Json;
using System.Xml;
using TccBenchmark.Models;
using TccBenchmark.Services;

// ============================================================
// 1) BUILDER + INJECAO DE DEPENDENCIA DOS SERVICOS
// ============================================================
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Singletons: gerador de dados (seed fixo) e ML treinado
builder.Services.AddSingleton<SyntheticDataGenerator>();
builder.Services.AddSingleton<MlPipelineService>();
builder.Services.AddSingleton<ExcelConsumptionImporter>();
builder.Services.AddScoped<InclusiveRulesEngine>();

// Cache em memoria do ultimo pipeline executado (evita re-treino em todo F5)
builder.Services.AddMemoryCache();

// URLs de lancamento - porta 5202 por padrao.
// Pode ser sobrescrita em tempo de execucao via:
//   dotnet run --urls "http://localhost:5300"
//   $env:ASPNETCORE_URLS = "http://localhost:5300" ; dotnet run
// Nota: UseUrls() tem precedencia maxima e anula --urls, por isso usamos
// ConfigureKestrel apenas como fallback quando nenhuma URL foi configurada.
if (string.IsNullOrEmpty(builder.Configuration["urls"]) &&
    string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ASPNETCORE_URLS")))
{
    builder.WebHost.UseUrls("http://localhost:5202", "https://localhost:5203");
}

// Garante que UseStaticFiles encontre wwwroot mesmo ao rodar via dotnet run de outras pastas
builder.Environment.WebRootPath = Path.Combine(AppContext.BaseDirectory, "wwwroot");
if (!Directory.Exists(builder.Environment.WebRootPath))
{
    // Fallback: pasta do projeto (durante dotnet run sem publish)
    string candidate = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot");
    if (Directory.Exists(candidate)) builder.Environment.WebRootPath = candidate;
}

var app = builder.Build();

// ============================================================
// 2) DADOS GLOBAIS (gerados 1x no startup, seed 42)
// ============================================================
var geradorGlobal = app.Services.GetRequiredService<SyntheticDataGenerator>();
var historicoGlobal = geradorGlobal.GerarHistoricoConsumo(meses: 24);
var rhGlobal        = geradorGlobal.GerarCadastroRH(totalColabs: 200, taxaPcdEpi: 0.08);
var dadosSync = new object();
var origemDadosReal = false;

// ============================================================
// 3) PIPELINE DE MIDDLEWARE
// ============================================================
app.UseDefaultFiles();   // wwwroot/index.html por padrao
app.UseStaticFiles();    // serve CSS/JS/Bootstrap/Chart (CDN fallback no index)
app.UseSwagger();
app.UseSwaggerUI();
app.UseCors(p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());

// ============================================================
// 4) ENDPOINT: GET /api/meta -> listas de EPI/Setor + totais RH
//    (usado para popular os <select> e <sidebar>)
// ============================================================
app.MapGet("/api/meta", () =>
{
    List<ConsumoHistorico> historicoAtual;
    bool dadosReais;
    lock (dadosSync)
    {
        historicoAtual = historicoGlobal;
        dadosReais = origemDadosReal;
    }

    List<Colaborador> colaboradores = dadosReais ? [] : rhGlobal;
    return new
    {
        Epis = historicoAtual.Select(h => h.Material).Distinct().OrderBy(m => m).ToList(),
        Setores = historicoAtual.Select(h => h.Setor).Distinct().OrderBy(s => s).ToList(),
        Colaboradores = colaboradores.Count,
        TotalPcds = colaboradores.Count(c => c.PCD),
        TotalRestricoes = colaboradores.Count(c => c.RestricaoErgonomica != "Nenhuma"),
        DadosReais = dadosReais,
        Origem = dadosReais ? "Real - MB51 detalhada" : "Sintéticos (seed 42)"
    };
});

app.MapPost("/api/upload", async (HttpRequest request, ExcelConsumptionImporter importer) =>
{
    if (!request.HasFormContentType)
        return Results.BadRequest(new { erro = "Envie um arquivo .xlsx como formulário multipart." });

    var form = await request.ReadFormAsync();
    var file = form.Files.GetFile("arquivo");
    if (file is null || file.Length == 0)
        return Results.BadRequest(new { erro = "Selecione um arquivo .xlsx para importar." });

    if (!string.Equals(Path.GetExtension(file.FileName), ".xlsx", StringComparison.OrdinalIgnoreCase))
        return Results.BadRequest(new { erro = "O formato aceito é .xlsx." });

    try
    {
        await using var stream = file.OpenReadStream();
        var resultadoImportacao = importer.Import(stream);
        lock (dadosSync)
        {
            historicoGlobal = resultadoImportacao.Historico;
            origemDadosReal = true;
        }

        return Results.Ok(new
        {
            mensagem = $"Dados importados da aba {resultadoImportacao.AbaDeOrigem}.",
            abaDeOrigem = resultadoImportacao.AbaDeOrigem,
            movimentacoes = resultadoImportacao.MovimentacoesLidas,
            subtotaisIgnorados = resultadoImportacao.LinhasDeSubtotalIgnoradas,
            agrupamentosConferidos = resultadoImportacao.AgrupamentosConferidos,
            divergenciasComPlanilha9 = resultadoImportacao.DivergenciasComPlanilha9,
            registros = resultadoImportacao.Historico.Count,
            materiais = resultadoImportacao.Historico.Select(h => h.Material).Distinct().Count(),
            inicio = resultadoImportacao.Historico.Min(h => h.Data).ToString("MM/yyyy"),
            fim = resultadoImportacao.Historico.Max(h => h.Data).ToString("MM/yyyy")
        });
    }
    catch (Exception exception) when (exception is InvalidDataException or FormatException or
                                      ArgumentException or IOException or InvalidOperationException or XmlException)
    {
        return Results.BadRequest(new { erro = exception.Message });
    }
});

app.MapPost("/api/benchmark", (
    TemporalBenchmarkRequest request,
    MlPipelineService ml) =>
{
    if (request.Historico.Count == 0)
        return Results.BadRequest(new { erro = "O benchmark recebeu um histórico vazio." });
    if (request.Horizonte is < 1 or > 12)
        return Results.BadRequest(new { erro = "O horizonte deve estar entre 1 e 12 meses." });
    if (request.Historico.Any(row => string.IsNullOrWhiteSpace(row.Material) ||
                                     string.IsNullOrWhiteSpace(row.Setor) ||
                                     !float.IsFinite(row.QuantidadeConsumida) ||
                                     row.QuantidadeConsumida < 0))
        return Results.BadRequest(new { erro = "O histórico contém material, setor ou quantidade inválida." });

    var history = request.Historico.Select(row => new ConsumoHistorico
    {
        Data = new DateTime(row.Data.Year, row.Data.Month, 1),
        Material = row.Material,
        Setor = row.Setor,
        Categoria = "Benchmark",
        Subcategoria = "Benchmark",
        QuantidadeConsumida = row.QuantidadeConsumida
    }).ToList();

    try
    {
        var options = new MlPipelineService.FastTreeOptions(
            Math.Clamp(request.Arvores, 10, 500),
            Math.Clamp(request.Folhas, 2, 50),
            Math.Clamp(request.MinLeaf, 1, 50),
            Math.Clamp(request.Lr, 0.001, 1.0));
        var result = ml.ExecutarBenchmarkTemporal(
            history,
            request.Corte,
            request.Horizonte,
            options);

        return Results.Ok(new
        {
            modelo = "FastTree (ML.NET)",
            corte = new DateTime(request.Corte.Year, request.Corte.Month, 1).ToString("yyyy-MM-dd"),
            horizonte = request.Horizonte,
            mesesTeste = Enumerable.Range(1, request.Horizonte)
                .Select(month => request.Corte.AddMonths(month).ToString("MM/yyyy"))
                .ToList(),
            result.Mae,
            result.Rmse,
            result.Wape,
            result.BaselineMae,
            result.BaselineRmse,
            result.BaselineWape,
            result.BaselineTotalPrevisto,
            result.Vies,
            result.TotalReal,
            result.TotalPrevisto,
            diferencaTotal = result.TotalPrevisto - result.TotalReal,
            result.Sobreprevisoes,
            result.Subprevisoes,
            result.PontosTeste,
            result.LinhasTreino,
            result.TempoTreinamentoMs,
            result.TempoPrevisaoMs,
            result.TempoCpuMs,
            result.MemoriaBaseMb,
            result.PicoMemoriaMb,
            result.AumentoPicoMemoriaMb,
            result.Previsoes
        });
    }
    catch (Exception exception) when (exception is InvalidDataException or ArgumentException or
                                      InvalidOperationException or KeyNotFoundException)
    {
        return Results.BadRequest(new { erro = exception.Message });
    }
});

// ============================================================
// 5) ENDPOINT: GET /api/dashboard
//    Parametros query:
//      ?epi=Luva Nitrilica G
//      &arvores=100  (slider)
//      &folhas=20    (slider)
//      &minLeaf=5
//      &lr=0.2
//    Retorna JSON completo p/ renderizar cards, grafico e tabela.
// ============================================================
app.MapGet("/api/dashboard", (
    HttpContext ctx,
    MlPipelineService ml,
    InclusiveRulesEngine regras,
    string? epi,
    int arvores = 100,
    int folhas = 20,
    int minLeaf = 5,
    double lr = 0.2) =>
{
    List<ConsumoHistorico> historicoAtual;
    bool dadosReais;
    lock (dadosSync)
    {
        historicoAtual = historicoGlobal;
        dadosReais = origemDadosReal;
    }

    List<Colaborador> colaboradoresAtuais = dadosReais ? [] : rhGlobal;
    var listaEpis = historicoAtual.Select(h => h.Material).Distinct().OrderBy(m => m).ToList();

    // --- Validar / aplicar defaults dos parametros ---
    string epiAtual = string.IsNullOrWhiteSpace(epi) ? listaEpis[0] : epi;
    if (!listaEpis.Contains(epiAtual)) epiAtual = listaEpis[0];
    arvores = Math.Clamp(arvores, 10, 500);
    folhas  = Math.Clamp(folhas, 2, 50);
    minLeaf = Math.Clamp(minLeaf, 1, 50);
    lr      = Math.Clamp(lr, 0.001, 1.0);

    // --- Feature Engineering (dataset completo) ---
    List<MlFeatureRow> features = ml.ConstruirFeatures(historicoAtual);

    // --- Treino + Avaliacao ---
    var opts = new MlPipelineService.FastTreeOptions(arvores, folhas, minLeaf, lr);
    var (metricas, reaisTeste, previstosTeste) = ml.TreinarEAvaliar(features, opts);
    metricas.TotalColaboradores = colaboradoresAtuais.Count;
    metricas.TotalPCDs = colaboradoresAtuais.Count(c => c.PCD);

    // --- Previsao 3 meses (todos) + filtrar por EPI selecionado ---
    List<PrevisaoFutura> futurosBrutos = ml.PreverProximos3Meses(historicoAtual);
    List<PrevisaoFutura> planoCompras   = regras.AplicarRegras(futurosBrutos, colaboradoresAtuais);

    metricas.TotalPrevisoesFuturas = planoCompras.Count;
    int totalAdaptados = planoCompras.Sum(p => p.QuantidadeEspecial);
    double ganho = metricas.MaeBaseline > 0
        ? (metricas.MaeBaseline - metricas.Mae) / metricas.MaeBaseline * 100.0
        : 0;

    // --- Historico AGREGADO por mes do EPI selecionado ---
    var serieHistorica = historicoAtual
        .Where(h => h.Material == epiAtual)
        .GroupBy(h => new { h.Data.Year, h.Data.Month })
        .OrderBy(g => g.Key.Year).ThenBy(g => g.Key.Month)
        .Select(g => new
        {
            Data = $"{g.Key.Month:00}/{g.Key.Year}",
            Quantidade = (int)Math.Round(g.Sum(x => x.QuantidadeConsumida))
        })
        .ToList();

    // --- Previsao AGREGADA por mes do EPI selecionado ---
    var seriePrevista = planoCompras
        .Where(p => p.Material == epiAtual)
        .GroupBy(p => new { p.Data.Year, p.Data.Month })
        .OrderBy(g => g.Key.Year).ThenBy(g => g.Key.Month)
        .Select(g => new
        {
            Data = $"{g.Key.Month:00}/{g.Key.Year}",
            Quantidade = g.Sum(x => x.PrevisaoBruta),
            Adaptada = g.Sum(x => x.PrevisaoAdaptada),
            Especial = g.Sum(x => x.QuantidadeEspecial)
        })
        .ToList();

    // --- Ultimo ponto real (para conectar linha historico -> previsao) ---
    var ultimoReal = serieHistorica.LastOrDefault();
    if (ultimoReal != null && seriePrevista.Count > 0)
    {
        var primeiroPrev = seriePrevista[0];
        seriePrevista.Insert(0, new {
            Data = ultimoReal.Data,
            Quantidade = ultimoReal.Quantidade,
            Adaptada = ultimoReal.Quantidade,
            Especial = 0
        });
    }

    // --- Painel Inclusivo: linhas com adaptacoes (Top 20 + todas do EPI atual) ---
    var painelInclusivo = planoCompras
        .Where(p => p.QuantidadeEspecial > 0 || p.Material == epiAtual)
        .OrderByDescending(p => p.QuantidadeEspecial)
        .ThenBy(p => p.Data)
        .Take(50)
        .Select(p => new
        {
            p.Data,
            Mes = $"{p.Data:MM/yyyy}",
            p.Setor,
            p.Material,
            p.PrevisaoBruta,
            p.PrevisaoAdaptada,
            p.QuantidadeEspecial,
            p.ItemEspecial,
            p.ParesCompletos,
            p.LuvasAvulsasEsquerda,
            p.LuvasAvulsasDireita,
            p.Observacao
        })
        .ToList();

    // --- Perfil RH (pizza): contagem por restricao ---
    var perfilRh = colaboradoresAtuais
        .Where(c => c.RestricaoErgonomica != "Nenhuma")
        .GroupBy(c => c.RestricaoErgonomica)
        .OrderByDescending(g => g.Count())
        .Select(g => new { Restricao = g.Key, Quantidade = g.Count() })
        .ToList();

    // --- Dados para o grafico ---
    // Serie do baseline de ultimo consumo observado no periodo de teste.
    var serieBaseline = metricas.DatasTeste
        .Zip(metricas.PrevisoesBaselineTeste, (d, v) => new { Data = d, Quantidade = (int)Math.Round(v) })
        .ToList();

    return new
    {
        EpiSelecionado = epiAtual,
        OrigemDados = dadosReais ? "Real - MB51 detalhada" : "Sintéticos (seed 42)",
        DadosReais = dadosReais,
        Opcoes = new { arvores, folhas, minLeaf, lr },

        // Cards do topo
        Cards = new
        {
            Mae = Math.Round(metricas.Mae, 3),
            MaeBaseline = Math.Round(metricas.MaeBaseline, 3),
            Rmse = Math.Round(metricas.Rmse, 3),
            RmseBaseline = Math.Round(metricas.RmseBaseline, 3),
            GanhoPrecisao = Math.Round(ganho, 1),
            TempoTreinoMs = metricas.TempoTreinamentoMs,
            TempoInferenciaMs = metricas.TempoInferenciaMs,
            LinhasTreino = metricas.LinhasTreino,
            LinhasTeste = metricas.LinhasTeste,
            TotalItensAdaptados = totalAdaptados,
            Volume90dBruto = planoCompras.Sum(p => p.PrevisaoBruta),
            TotalColabs = metricas.TotalColaboradores,
            TotalPcds = metricas.TotalPCDs,
            TotalPrevisoes = metricas.TotalPrevisoesFuturas
        },

        // Dados para o grafico
        Grafico = new
        {
            Historico = serieHistorica,
            Previsao  = seriePrevista,
            Baseline  = serieBaseline
        },

        // Painel Inclusivo tabela
        PainelInclusivo = painelInclusivo,

        // Perfil RH
        PerfilRh = perfilRh,

        // Sumario mensal
        SumarioMensal = planoCompras
            .GroupBy(p => new { p.Data.Year, p.Data.Month })
            .OrderBy(g => g.Key.Year).ThenBy(g => g.Key.Month)
            .Select(g => new
            {
                Mes = $"{g.Key.Month:00}/{g.Key.Year}",
                Bruto = g.Sum(x => x.PrevisaoBruta),
                Adaptado = g.Sum(x => x.PrevisaoAdaptada),
                Especial = g.Sum(x => x.QuantidadeEspecial)
            })
            .ToList()
    };
})
.WithName("Dashboard");

// ============================================================
// 6) REDIRECT: caso usuario acesse /swagger ou /api
// ============================================================
app.MapGet("/", () => Results.Redirect("/index.html"));

// ============================================================
// 7) PRINT console startup (igual ao Streamlit)
// ============================================================
Console.WriteLine();
Console.WriteLine("╔══════════════════════════════════════════════════════════════════════════╗");
Console.WriteLine("║   TCC UNIP - Dashboard Web (C# .NET 8 + ML.NET FastTree)                ║");
Console.WriteLine("║   Supply Chain Inclusivo / NR-17 / Ergonomia PCD                       ║");
Console.WriteLine("╚══════════════════════════════════════════════════════════════════════════╝");
Console.WriteLine();
// Determina a URL real que sera usada (args > env > padrao)
string urlAtiva = builder.Configuration["urls"]
    ?? Environment.GetEnvironmentVariable("ASPNETCORE_URLS")
    ?? "http://localhost:5202";
string urlBase = urlAtiva.Split(';')[0].TrimEnd('/');
Console.WriteLine($"👉 Abra no navegador:  {urlBase}");
Console.WriteLine($"👉 API JSON:           {urlBase}/api/dashboard?epi=Luva%20Nitrilica%20G");
Console.WriteLine($"👉 Swagger:            {urlBase}/swagger");
Console.WriteLine();

app.Run();
