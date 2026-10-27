# 以管理员权限执行 setup_mysql_admin.ps1（触发 UAC 弹窗，需用户点「是」）
try {
    $target = Join-Path $PSScriptRoot 'setup_mysql_admin.ps1'
    $p = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $target
    Write-Output ("ELEVATED_EXIT_CODE=" + $p.ExitCode)
} catch {
    Write-Output ("UAC_FAILED: " + $_.Exception.Message)
}
