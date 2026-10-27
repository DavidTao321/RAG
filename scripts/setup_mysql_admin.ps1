# MySQL 8.4 一次性初始化脚本（需管理员权限）
# 作用：初始化数据目录 → 注册 Windows 服务 MySQL84 → 启动服务
$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot 'mysql_setup.log'
"===== setup start: $(Get-Date) =====" | Out-File $log

try {
    $base = 'C:\Program Files\MySQL\MySQL Server 8.4'
    if (-not (Test-Path "$base\bin\mysqld.exe")) {
        throw "找不到 mysqld.exe: $base"
    }
    $datadir = 'C:\ProgramData\MySQL\MySQL Server 8.4\Data'

    # 1. 初始化数据目录（root@localhost 初始无密码，随后由应用侧脚本设置）
    "step1: initialize datadir" | Out-File $log -Append
    & "$base\bin\mysqld.exe" --initialize-insecure --basedir="$base" --datadir="$datadir" 2>&1 | Out-File $log -Append
    if ($LASTEXITCODE -ne 0) { throw "mysqld --initialize 失败" }

    # 2. 注册服务
    "step2: install service" | Out-File $log -Append
    & "$base\bin\mysqld.exe" --install MySQL84 2>&1 | Out-File $log -Append
    if ($LASTEXITCODE -ne 0) { throw "mysqld --install 失败" }

    # 3. 启动服务
    "step3: start service" | Out-File $log -Append
    Start-Service MySQL84
    "step4: service started OK" | Out-File $log -Append
} catch {
    "ERROR: $_" | Out-File $log -Append
    throw
}
"===== setup end: $(Get-Date) =====" | Out-File $log -Append
