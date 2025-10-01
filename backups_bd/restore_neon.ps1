# Caminho do executável pg_restore
$pgRestorePath = "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"

# Caminho da pasta de backups
$backupDir = "C:\precificador-m4\backups_bd"

# String de conexão do Neon
$connectionString = "postgresql://neondb_owner:npg_qXEJL5vYs7Zz@ep-young-cake-ad2mlkly-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Lista os arquivos de backup disponíveis
$backups = Get-ChildItem -Path $backupDir -Filter "*.dump" | Sort-Object LastWriteTime -Descending

if ($backups.Count -eq 0) {
    Write-Host "❌ Nenhum backup encontrado em $backupDir"
    exit 1
}

Write-Host "📂 Backups disponíveis:"
for ($i = 0; $i -lt $backups.Count; $i++) {
    Write-Host "[$i] $($backups[$i].Name)"
}

# Pergunta qual arquivo restaurar
$choice = Read-Host "Digite o número do backup que deseja restaurar"
if ($choice -notmatch '^\d+$' -or [int]$choice -ge $backups.Count) {
    Write-Host "❌ Escolha inválida."
    exit 1
}

$backupFile = $backups[$choice].FullName
Write-Host "🔄 Restaurando backup: $backupFile"

# Executa o pg_restore
& "$pgRestorePath" -d $connectionString -v $backupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Restauração concluída com sucesso!"
} else {
    Write-Host "❌ Ocorreu um erro na restauração. Código: $LASTEXITCODE"
}
