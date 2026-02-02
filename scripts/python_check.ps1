Write-Host "== Python 环境自检（Windows） =="
Write-Host ""

function Show-Cmd($name) {
  try {
    $cmd = Get-Command $name -ErrorAction Stop
    Write-Host ("{0,-10}: {1}" -f $name, $cmd.Source)
    return $cmd.Source
  } catch {
    Write-Host ("{0,-10}: (not found)" -f $name)
    return $null
  }
}

$pythonPath = Show-Cmd "python"
$pyPath = Show-Cmd "py"

Write-Host ""
if ($pythonPath -and $pythonPath -like "*\\Microsoft\\WindowsApps\\python.exe") {
  Write-Host "检测到：python 指向 WindowsApps 的商店别名（通常不可用，会导致脚本退出码 9009 或无输出）。"
  Write-Host ""
  Write-Host "修复建议："
  Write-Host "1) 关闭 App Execution Alias：设置 → 应用 → 高级应用设置 → 应用执行别名，关闭 python.exe / python3.exe"
  Write-Host "2) 安装 Python（推荐 Python 3.11+ 或 3.12+），并勾选 Add to PATH / 安装 py launcher"
  Write-Host "3) 重新打开终端后验证：py -V 或 python --version"
} elseif (-not $pythonPath -and -not $pyPath) {
  Write-Host "检测到：python / py 都不存在。需要安装 Python（并建议启用 py launcher）。"
} else {
  Write-Host "检测到：至少一个 Python 启动方式可用。"
  Write-Host "建议后续在 Windows 上优先用：py scripts\\rest_smoke.py --env dev --user-info"
}

