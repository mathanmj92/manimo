<#
.SYNOPSIS
  Downloads the offline narration voice model Manimo uses (Kokoro int8) into app\models.
.DESCRIPTION
  The two files are about 115 MB together, so they are not stored in the repository.
  Source: https://github.com/thewh1teagle/kokoro-onnx (release "model-files-v1.0"). Files that are already
  present with the expected size are kept. Run from anywhere:  powershell -ExecutionPolicy Bypass -File tools\Get-Models.ps1
#>
$ErrorActionPreference = 'Stop'
$dest = Join-Path (Split-Path $PSScriptRoot -Parent) 'app\models'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$base = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0'
$files = @(
  @{ Name = 'kokoro-v1.0.int8.onnx'; Size = 92361271; Sha256 = '6E742170D309016E5891A994E1CE1559C702A2CCD0075E67EF7157974F6406CB' },
  @{ Name = 'voices-v1.0.bin';       Size = 28214398; Sha256 = 'BCA610B8308E8D99F32E6FE4197E7EC01679264EFED0CAC9140FE9C29F1FBF7D' }
)
foreach ($f in $files) {
  $path = Join-Path $dest $f.Name
  if ((Test-Path $path) -and (Get-Item $path).Length -eq $f.Size) { Write-Host "$($f.Name): already here"; continue }
  Write-Host "$($f.Name): downloading..."
  Invoke-WebRequest "$base/$($f.Name)" -OutFile $path -UseBasicParsing
  $hash = (Get-FileHash $path -Algorithm SHA256).Hash
  if ($hash -ne $f.Sha256) { Remove-Item $path -Force; throw "$($f.Name): the checksum does not match, so the file was removed. Try again." }
  Write-Host "$($f.Name): ok"
}
Write-Host "Voice model ready in $dest"
