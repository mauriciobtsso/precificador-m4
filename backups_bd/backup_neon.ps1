# Caminho do executável do pg_dump
$pgDumpPath = "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"

# Caminho da pasta de backups
$backupDir = "C:\precificador-m4\backups_bd"

# Garante que a pasta existe
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

# Nome do arquivo com data/hora
$timestamp = Get-Date -Format "yyyyMMdd_HHmm"
$backupFile = "$backupDir\neon_backup_$timestamp.dump"

# String de conexão do Neon
$connectionString = "postgresql://neondb_owner:npg_qXEJL5vYs7Zz@ep-young-cake-ad2mlkly-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Executa o backup
Write-Host "Iniciando backup para $backupFile..."
& "$pgDumpPath" $connectionString -F c -b -v -f $backupFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Backup concluído com sucesso: $backupFile"
} else {
    Write-Host "❌ Ocorreu um erro no backup. Código: $LASTEXITCODE"
}
