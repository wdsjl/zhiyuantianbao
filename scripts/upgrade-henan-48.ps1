# Fix stale Henan province_rules row (45 -> 48) in SQLite DB.
# Usage: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\upgrade-henan-48.ps1

$ErrorActionPreference = 'Stop'
Set-Location 'C:\zhiyuantianbao\server'

python -c @"
from province_rules_service import ensure_province_rules_seeded, resolve_volunteer_slots
ensure_province_rules_seeded()
result = resolve_volunteer_slots('河南', '本科批')
print(result)
assert int(result['total_slots']) == 48, result
print('OK: Henan benke = 48')
"@

Write-Host 'Done. Restart pm2 if on server:'
Write-Host '  pm2 restart zhiyuan-backend --update-env'
