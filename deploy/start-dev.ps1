# Windows 11 开发环境一键启动（后端 8000 + 前端 5173）
# 用法：在项目根目录执行  powershell -ExecutionPolicy Bypass -File deploy\start-dev.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Write-Host '[1/3] 启动后端 http://127.0.0.1:8000 ...'
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    '-NoExit',
    '-Command',
    "Set-Location '$root\backend'; .\.venv\Scripts\Activate.ps1; python manage.py runserver 0.0.0.0:8000"
)

Write-Host '[2/3] 启动前端 http://127.0.0.1:5173 ...'
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    '-NoExit',
    '-Command',
    "Set-Location '$root\frontend'; npm run dev"
)

Write-Host '[3/3] 启动订单超时与事件扫描 ...'
$workerPython = Join-Path $root 'backend\.venv\Scripts\python.exe'
Start-Process -FilePath $workerPython -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -ArgumentList @('manage.py','process_order_events','--watch')

Write-Host '启动完成。若首次运行，请先按 README 完成依赖安装与 migrate。'
