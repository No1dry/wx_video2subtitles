# 一键打包 Windows 便携版（CPU 版 + GPU 版），产物在 packaging\dist\ 下。
# 用法：在 res-downloader\packaging 目录下执行  powershell -ExecutionPolicy Bypass -File build-windows.ps1
#
# 依赖：
#   - Python(已装 faster-whisper) 与 PyInstaller： pip install faster-whisper pyinstaller
#   - wails CLI： go install github.com/wailsapp/wails/v2/cmd/wails@latest
#   - 如需 GPU 版：本机存在 CUDA 12 的 cublas/cudnn DLL（脚本里 $CudaBin 指定）
$ErrorActionPreference = "Stop"
$Py      = "D:\python3.8\python.exe"                              # 用于打包的 python（须装了 faster-whisper）
$CudaBin = "D:\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"        # GPU 版所需 CUDA 12 库目录
$Root    = Split-Path -Parent $PSScriptRoot                       # res-downloader 目录
$Pkg     = $PSScriptRoot
$Model   = Join-Path $Root "python\models\faster-whisper-small"

Set-Location $Pkg

# 1) PyInstaller 打包转录器（CPU 自包含）
& $Py -m PyInstaller --noconfirm --onedir --name transcribe `
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all av `
  --collect-all onnxruntime --collect-all tokenizers `
  --exclude-module torch --exclude-module matplotlib --exclude-module scipy `
  --distpath dist --workpath build --specpath . `
  (Join-Path $Root "python\transcribe.py")

# 2) GPU 版 = CPU 版 + CUDA 库
Remove-Item -Recurse -Force "dist\transcribe-gpu" -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force "dist\transcribe" "dist\transcribe-gpu"
$ctDir = "dist\transcribe-gpu\_internal\ctranslate2"
foreach ($n in @("cublas64_12.dll","cublasLt64_12.dll","cudnn64_8.dll","cudnn_ops_infer64_8.dll","cudnn_cnn_infer64_8.dll")) {
  Copy-Item -Force (Join-Path $CudaBin $n) (Join-Path $ctDir $n)
}

# 3) 编译主程序
Set-Location $Root
& wails build -platform windows/amd64 -clean
Set-Location $Pkg

# 4) 组装两个便携包
function Assemble($name, $transcriberDir) {
  $out = "dist\$name"
  Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Force $out | Out-Null
  Copy-Item -Force (Join-Path $Root "build\bin\res-downloader.exe") $out
  Copy-Item -Force "使用说明.txt" $out
  Copy-Item -Recurse -Force $transcriberDir (Join-Path $out "transcriber")
  New-Item -ItemType Directory -Force (Join-Path $out "transcriber\models") | Out-Null
  Copy-Item -Recurse -Force $Model (Join-Path $out "transcriber\models\faster-whisper-small")
}
Assemble "res-downloader-portable-cpu" "dist\transcribe"
Assemble "res-downloader-portable-gpu" "dist\transcribe-gpu"

# 5) 打包 zip
Compress-Archive -Force -Path "dist\res-downloader-portable-cpu\*" -DestinationPath "dist\res-downloader-portable-cpu.zip"
Compress-Archive -Force -Path "dist\res-downloader-portable-gpu\*" -DestinationPath "dist\res-downloader-portable-gpu.zip"
Write-Output "完成。产物见 packaging\dist\*.zip"
