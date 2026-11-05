# start_server.ps1 - Sobe o servidor web publicado e valida endpoints
$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
$project = Join-Path $projectDir "TccBenchmark.csproj"
$publishDir = Join-Path $projectDir "bin\Release\net8.0\publish"
$exe = Join-Path $publishDir "TccBenchmark.exe"

dotnet publish $project --configuration Release --output $publishDir
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao publicar o dashboard C#."
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.WorkingDirectory = $publishDir
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true

Write-Host "[BOOT] Iniciando $exe..."
$proc = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Seconds 16

if ($proc.HasExited) {
  Write-Host "== PROCESS CRASHED Exit=$($proc.ExitCode) =="
  Write-Host "=== STDOUT ==="
  Write-Host $proc.StandardOutput.ReadToEnd()
  Write-Host "=== STDERR ==="
  Write-Host $proc.StandardError.ReadToEnd()
  exit 1
}

Write-Host "== PROCESS RUNNING PID=$($proc.Id) =="

try {
  $meta = Invoke-RestMethod -Uri "http://127.0.0.1:5202/api/meta" -TimeoutSec 10
  Write-Host "OK /api/meta -> EPIs: $($meta.Epis.Count), Colabs: $($meta.Colaboradores), PCDs: $($meta.TotalPcds)"
} catch {
  Write-Host "FAIL /api/meta: $($_.Exception.Message)"
}

Start-Sleep -Seconds 2

try {
  $dash = Invoke-RestMethod -Uri "http://127.0.0.1:5202/api/dashboard?epi=Bota%20de%20Seguranca&arvores=150&folhas=25&minLeaf=5&lr=0.15" -TimeoutSec 45
  Write-Host "OK /api/dashboard -> EPI selecionado: $($dash.EpiSelecionado)"
  Write-Host "   CARDS:"
  Write-Host "      - MAE:         $($dash.Cards.Mae)"
  Write-Host "      - MAE Base:    $($dash.Cards.MaeBaseline)"
  Write-Host "      - Ganho:       $($dash.Cards.GanhoPrecisao) %"
  Write-Host "      - Treino ms:   $($dash.Cards.TempoTreinoMs)"
  Write-Host "      - Infer. ms:   $($dash.Cards.TempoInferenciaMs)"
  Write-Host "      - Adaptados:   $($dash.Cards.TotalItensAdaptados) un."
  Write-Host "      - Volume 90d:  $($dash.Cards.Volume90dBruto) un."
  Write-Host "   GRAFICO: hist=$($dash.Grafico.Historico.Count) meses | prev=$($dash.Grafico.Previsao.Count) meses"
  Write-Host "   PAINEL INCLUSIVO: $($dash.PainelInclusivo.Count) linhas"
  Write-Host "   SUMARIO MENSAL: $($dash.SumarioMensal.Count) meses"
} catch {
  Write-Host "FAIL /api/dashboard: $($_.Exception.Message)"
}

try {
  $root = Invoke-WebRequest -Uri "http://127.0.0.1:5202/" -UseBasicParsing -TimeoutSec 10
  $temBody = $root.Content -match '<body'
  Write-Host "OK ROOT /  -> ContentLength=$($root.Content.Length) bytes, Contem <body>: $temBody"
} catch {
  Write-Host "FAIL ROOT/: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "[DONE] PID continua rodando: $(-not $proc.HasExited)"
