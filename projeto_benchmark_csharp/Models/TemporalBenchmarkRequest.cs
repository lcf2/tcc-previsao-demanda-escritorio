namespace TccBenchmark.Models;

public sealed class TemporalBenchmarkRequest
{
    public List<TemporalBenchmarkObservation> Historico { get; set; } = [];
    public DateTime Corte { get; set; }
    public int Horizonte { get; set; } = 12;
    public int Arvores { get; set; } = 100;
    public int Folhas { get; set; } = 20;
    public int MinLeaf { get; set; } = 5;
    public double Lr { get; set; } = 0.2;
}

public sealed class TemporalBenchmarkObservation
{
    public DateTime Data { get; set; }
    public string Material { get; set; } = string.Empty;
    public string Setor { get; set; } = string.Empty;
    public float QuantidadeConsumida { get; set; }
}
