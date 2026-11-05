using System.Globalization;
using System.IO.Compression;
using System.Text;
using System.Xml.Linq;
using TccBenchmark.Models;

namespace TccBenchmark.Services;

public sealed class ExcelConsumptionImporter
{
    private static readonly XNamespace MainNamespace =
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
    private static readonly XNamespace RelationshipNamespace =
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    private static readonly XNamespace PackageRelationshipNamespace =
        "http://schemas.openxmlformats.org/package/2006/relationships";

    private static readonly Dictionary<string, int> PortugueseMonths = new(StringComparer.Ordinal)
    {
        ["jan"] = 1, ["janeiro"] = 1,
        ["fev"] = 2, ["fevereiro"] = 2,
        ["mar"] = 3, ["marco"] = 3,
        ["abr"] = 4, ["abril"] = 4,
        ["mai"] = 5, ["maio"] = 5,
        ["jun"] = 6, ["junho"] = 6,
        ["jul"] = 7, ["julho"] = 7,
        ["ago"] = 8, ["agosto"] = 8,
        ["set"] = 9, ["setembro"] = 9,
        ["out"] = 10, ["outubro"] = 10,
        ["nov"] = 11, ["novembro"] = 11,
        ["dez"] = 12, ["dezembro"] = 12
    };

    public sealed record ImportResult(
        List<ConsumoHistorico> Historico,
        string AbaDeOrigem,
        int MovimentacoesLidas,
        int LinhasDeSubtotalIgnoradas,
        int AgrupamentosConferidos,
        int DivergenciasComPlanilha9);

    public ImportResult Import(Stream stream)
    {
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read, leaveOpen: true);
        var workbook = LoadXml(archive, "xl/workbook.xml");
        var relationships = LoadXml(archive, "xl/_rels/workbook.xml.rels")
            .Root!.Elements(PackageRelationshipNamespace + "Relationship")
            .ToDictionary(
                element => (string)element.Attribute("Id")!,
                element => (string)element.Attribute("Target")!,
                StringComparer.Ordinal);
        var sheets = workbook.Root!
            .Element(MainNamespace + "sheets")!
            .Elements(MainNamespace + "sheet")
            .ToDictionary(
                element => NormalizeHeader((string)element.Attribute("name")!),
                element => element,
                StringComparer.Ordinal);
        var sharedStrings = ReadSharedStrings(archive);
        bool hasSummary = sheets.TryGetValue("planilha9", out var summarySheet);
        bool hasTransactions = sheets.TryGetValue("mb51", out var transactionSheet);
        if (!hasTransactions && !hasSummary)
            throw new InvalidDataException("O arquivo não contém a aba MB51 nem Planilha9.");

        var summaryTotals = hasSummary
            ? ReadSummary(LoadSheet(archive, summarySheet!, relationships), sharedStrings, "Planilha9")
            : null;

        Dictionary<(string Material, DateTime Date), double> signedMonthlyTotals;
        int transactionRows = 0;
        int skippedSubtotalRows = 0;
        string sourceSheet;

        if (hasTransactions)
        {
            sourceSheet = "MB51";
            signedMonthlyTotals = ReadTransactions(
                LoadSheet(archive, transactionSheet!, relationships),
                sharedStrings,
                out transactionRows,
                out skippedSubtotalRows);
        }
        else
        {
            sourceSheet = "Planilha9";
            signedMonthlyTotals = summaryTotals!;
        }

        if (signedMonthlyTotals.Count == 0)
            throw new InvalidDataException($"A aba {sourceSheet} não contém registros de consumo válidos.");

        int reconciledRows = 0;
        int summaryDifferences = 0;
        if (hasTransactions && summaryTotals is not null)
        {
            var sharedKeys = signedMonthlyTotals.Keys.Intersect(summaryTotals.Keys).ToList();
            reconciledRows = sharedKeys.Count;
            summaryDifferences = sharedKeys.Count(key =>
                Math.Abs(signedMonthlyTotals[key] - summaryTotals[key]) > 1e-6);
        }

        DateTime lastMonth = signedMonthlyTotals.Keys.Max(key => key.Date);
        var materials = signedMonthlyTotals.Keys
            .Select(key => key.Material)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(material => material, StringComparer.Ordinal)
            .ToList();
        var firstMonthByMaterial = signedMonthlyTotals.Keys
            .GroupBy(key => key.Material, StringComparer.Ordinal)
            .ToDictionary(
                group => group.Key,
                group => group.Min(key => key.Date),
                StringComparer.Ordinal);

        var history = new List<ConsumoHistorico>();

        foreach (string material in materials)
        {
            for (DateTime date = firstMonthByMaterial[material]; date <= lastMonth; date = date.AddMonths(1))
            {
                double signedQuantity = signedMonthlyTotals.GetValueOrDefault((material, date));
                history.Add(new ConsumoHistorico
                {
                    Data = date,
                    Material = material,
                    Categoria = "Não informado",
                    Subcategoria = "Não informado",
                    Setor = "Geral",
                    QuantidadeConsumida = (float)Math.Max(0, -signedQuantity)
                });
            }
        }

        return new ImportResult(
            history,
            sourceSheet,
            transactionRows,
            skippedSubtotalRows,
            reconciledRows,
            summaryDifferences);
    }

    private static Dictionary<(string Material, DateTime Date), double> ReadTransactions(
        XDocument worksheet,
        IReadOnlyList<string> sharedStrings,
        out int transactionRows,
        out int skippedSubtotalRows)
    {
        var rows = ReadRows(worksheet);
        var header = FindHeader(
            rows,
            sharedStrings,
            "MB51",
            "tipodemovimento", "material", "quantidade", "mes", "ano");
        var totals = new Dictionary<(string Material, DateTime Date), double>();
        transactionRows = 0;
        skippedSubtotalRows = 0;

        foreach (var row in rows.Where(row => ParseRowNumber(row) > header.RowNumber))
        {
            var cells = ReadRow(row, sharedStrings);
            string movementType = cells.GetValueOrDefault(header.Columns["tipodemovimento"], "").Trim();
            if (movementType.Length == 0)
            {
                skippedSubtotalRows++;
                continue;
            }

            int rowNumber = ParseRowNumber(row);
            string material = cells.GetValueOrDefault(header.Columns["material"], "").Trim();
            if (material.Length == 0)
                throw new InvalidDataException($"Material inválido na linha {rowNumber} da aba MB51.");

            if (!int.TryParse(cells.GetValueOrDefault(header.Columns["ano"]),
                    NumberStyles.Integer, CultureInfo.InvariantCulture, out int year))
                throw new InvalidDataException($"Ano inválido na linha {rowNumber} da aba MB51.");

            int month = ParseMonth(cells.GetValueOrDefault(header.Columns["mes"]), rowNumber);
            if (!double.TryParse(cells.GetValueOrDefault(header.Columns["quantidade"]),
                    NumberStyles.Float, CultureInfo.InvariantCulture, out double quantity))
                throw new InvalidDataException($"Quantidade inválida na linha {rowNumber} da aba MB51.");

            DateTime date = new(year, month, 1);
            var key = (material, date);
            totals[key] = totals.GetValueOrDefault(key) + quantity;
            transactionRows++;
        }

        return totals;
    }

    private static Dictionary<(string Material, DateTime Date), double> ReadSummary(
        XDocument worksheet,
        IReadOnlyList<string> sharedStrings,
        string sheetName)
    {
        var rows = ReadRows(worksheet);
        var header = FindHeader(
            rows,
            sharedStrings,
            sheetName,
            "material", "ano", "mes", "somadequantidade");
        var totals = new Dictionary<(string Material, DateTime Date), double>();

        foreach (var row in rows.Where(row => ParseRowNumber(row) > header.RowNumber))
        {
            var cells = ReadRow(row, sharedStrings);
            string material = cells.GetValueOrDefault(header.Columns["material"], "").Trim();
            if (material.Length == 0)
                continue;

            int rowNumber = ParseRowNumber(row);
            string yearValue = cells.GetValueOrDefault(header.Columns["ano"], "");
            string monthValue = cells.GetValueOrDefault(header.Columns["mes"], "");
            if (yearValue.Length == 0 && monthValue.Length == 0)
                continue;

            if (!int.TryParse(yearValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out int year))
                throw new InvalidDataException($"Ano inválido na linha {rowNumber} da aba {sheetName}.");

            int month = ParseMonth(monthValue, rowNumber);
            if (!double.TryParse(cells.GetValueOrDefault(header.Columns["somadequantidade"]),
                    NumberStyles.Float, CultureInfo.InvariantCulture, out double quantity))
                throw new InvalidDataException($"Quantidade inválida na linha {rowNumber} da aba {sheetName}.");

            var key = (material, new DateTime(year, month, 1));
            totals[key] = totals.GetValueOrDefault(key) + quantity;
        }
        return totals;
    }

    private static List<XElement> ReadRows(XDocument worksheet)
        => worksheet.Root!
            .Element(MainNamespace + "sheetData")?
            .Elements(MainNamespace + "row")
            .ToList() ?? [];

    private static XDocument LoadSheet(
        ZipArchive archive,
        XElement sheet,
        IReadOnlyDictionary<string, string> relationships)
    {
        var relationshipId = (string?)sheet.Attribute(RelationshipNamespace + "id");
        if (relationshipId is null || !relationships.TryGetValue(relationshipId, out var target))
            throw new InvalidDataException("Não foi possível localizar uma aba no arquivo.");

        string sheetPath = target.TrimStart('/');
        if (!sheetPath.StartsWith("xl/", StringComparison.OrdinalIgnoreCase))
            sheetPath = "xl/" + sheetPath;
        return LoadXml(archive, sheetPath);
    }

    private static (int RowNumber, Dictionary<string, int> Columns) FindHeader(
        IReadOnlyList<XElement> rows,
        IReadOnlyList<string> sharedStrings,
        string sheetName,
        params string[] requiredColumns)
    {
        foreach (var row in rows)
        {
            var columns = ReadRow(row, sharedStrings)
                .Select(pair => (Name: NormalizeHeader(pair.Value), pair.Key))
                .Where(pair => pair.Name.Length > 0)
                .ToDictionary(pair => pair.Name, pair => pair.Key, StringComparer.Ordinal);
            if (requiredColumns.All(columns.ContainsKey))
                return (ParseRowNumber(row), columns);
        }

        throw new InvalidDataException($"Não encontrei as colunas necessárias na aba '{sheetName}'.");
    }

    private static Dictionary<int, string> ReadRow(XElement row, IReadOnlyList<string> sharedStrings)
    {
        var values = new Dictionary<int, string>();
        foreach (var cell in row.Elements(MainNamespace + "c"))
        {
            string reference = (string?)cell.Attribute("r") ?? "";
            int column = ColumnIndex(reference);
            string type = (string?)cell.Attribute("t") ?? "";

            string value;
            if (type == "inlineStr")
            {
                value = string.Concat(cell.Descendants(MainNamespace + "t").Select(text => text.Value));
            }
            else
            {
                value = cell.Element(MainNamespace + "v")?.Value ?? "";
                if (type == "s" && int.TryParse(value, out int index) &&
                    index >= 0 && index < sharedStrings.Count)
                    value = sharedStrings[index];
            }

            values[column] = value;
        }
        return values;
    }

    private static List<string> ReadSharedStrings(ZipArchive archive)
    {
        var entry = archive.GetEntry("xl/sharedStrings.xml");
        if (entry is null)
            return [];

        var document = LoadXml(entry);
        return document.Root!
            .Elements(MainNamespace + "si")
            .Select(item => string.Concat(item.Descendants(MainNamespace + "t").Select(text => text.Value)))
            .ToList();
    }

    private static XDocument LoadXml(ZipArchive archive, string path)
    {
        var entry = archive.GetEntry(path)
            ?? throw new InvalidDataException($"O arquivo Excel está incompleto: {path} não existe.");
        return LoadXml(entry);
    }

    private static XDocument LoadXml(ZipArchiveEntry entry)
    {
        using var stream = entry.Open();
        return XDocument.Load(stream);
    }

    private static int ColumnIndex(string cellReference)
    {
        int column = 0;
        foreach (char character in cellReference)
        {
            if (!char.IsLetter(character))
                break;
            column = checked(column * 26 + char.ToUpperInvariant(character) - 'A' + 1);
        }

        return column - 1;
    }

    private static int ParseRowNumber(XElement row)
        => int.TryParse((string?)row.Attribute("r"), out int rowNumber) ? rowNumber : 0;

    private static string NormalizeHeader(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var normalized = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark &&
                char.IsLetterOrDigit(character))
                normalized.Append(char.ToLowerInvariant(character));
        }
        return normalized.ToString();
    }

    private static int ParseMonth(string? value, int rowNumber)
    {
        string normalized = NormalizeHeader(value ?? "");
        if (int.TryParse(normalized, NumberStyles.Integer, CultureInfo.InvariantCulture, out int number) &&
            number is >= 1 and <= 12)
            return number;

        if (PortugueseMonths.TryGetValue(normalized, out number))
            return number;

        throw new InvalidDataException($"Mês inválido na linha {rowNumber} da aba Planilha9.");
    }
}
