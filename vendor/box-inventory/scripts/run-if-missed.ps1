# 计划任务 Kimi-AIHOT-Daily 的入口包装脚本。
# 任务有两个触发器：每天 12:00、登录后延迟 5 分钟。
# 本脚本保证同一天只真正执行一次，且 12:00 之前的登录触发直接跳过（等中午正式运行）。
$now = Get-Date
if ($now.TimeOfDay -lt [TimeSpan]::FromHours(12)) { exit 0 }

$stamp = "E:\workspace\aihot\logs\.last-run-date"
$today = $now.ToString("yyyy-MM-dd")
if ((Test-Path $stamp) -and ((Get-Content $stamp -Raw).Trim() -eq $today)) { exit 0 }

$cmd = '"C:\Users\92926\.kimi-work\run-hidden.vbs" cmd.exe /c cd /d E:\workspace\aihot && "C:\Users\92926\AppData\Local\Programs\Python\Python313\Scripts\uv.exe" run E:\workspace\aihot\aihot-daily-generator-win.py >> E:\workspace\aihot\logs\scheduled-run.log 2>&1'
$p = Start-Process wscript.exe -ArgumentList $cmd -Wait -PassThru
if ($p.ExitCode -eq 0) { Set-Content -Path $stamp -Value $today }
exit $p.ExitCode
