param(
    [string]$OutputRoot = "dist/portable"
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $projectRoot "packaging/portable-manifest.json"
$manifest = Get-Content -Raw -LiteralPath $manifestPath -Encoding UTF8 | ConvertFrom-Json
$version = [string]$manifest.version
$product = [string]$manifest.product
$buildRoot = Join-Path $projectRoot "dist/portable-build"
$staging = Join-Path $buildRoot "$product-v$version"
$pyinstallerDist = Join-Path $buildRoot "pyinstaller-dist"
$pyinstallerWork = Join-Path $buildRoot "pyinstaller-work"
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
$resolvedBuildRoot = [System.IO.Path]::GetFullPath($buildRoot)
$expectedBuildPrefix = [System.IO.Path]::GetFullPath((Join-Path $resolvedProjectRoot "dist")) + [System.IO.Path]::DirectorySeparatorChar
if (-not $resolvedBuildRoot.StartsWith($expectedBuildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Portable build root escaped the project dist directory."
}
$resolvedOutputRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputRoot))
if (-not ($resolvedOutputRoot + [System.IO.Path]::DirectorySeparatorChar).StartsWith($expectedBuildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Portable output root escaped the project dist directory."
}
$outputArchive = Join-Path $resolvedOutputRoot "$product-v$version-portable-x64.zip"
Remove-Item -LiteralPath $outputArchive, ($outputArchive + ".sha256") -Force -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $resolvedBuildRoot) {
    Remove-Item -Recurse -Force -LiteralPath $resolvedBuildRoot
}
New-Item -ItemType Directory -Path $staging | Out-Null

Push-Location $projectRoot
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
    python -m PyInstaller --noconfirm --distpath $pyinstallerDist --workpath $pyinstallerWork packaging/backend.spec
    if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed with exit code $LASTEXITCODE." }

    New-Item -ItemType Directory -Path (Join-Path $staging "runtime") | Out-Null
    Copy-Item -Recurse -LiteralPath (Join-Path $pyinstallerDist "backend") -Destination (Join-Path $staging "runtime/backend")
    Copy-Item -Recurse -LiteralPath "packages/frontend/dist" -Destination (Join-Path $staging "web")
    New-Item -ItemType Directory -Path (Join-Path $staging "resources") | Out-Null
    Copy-Item -Recurse -LiteralPath "word_templates" -Destination (Join-Path $staging "resources/word_templates")

    $nodeDistributionRoot = if ($env:BIJI_NODE_DIST_DIR) {
        $env:BIJI_NODE_DIST_DIR
    } else {
        $localNodeDistributionRoot = Join-Path (
            Join-Path $projectRoot "dist/toolchain"
        ) "node-v$($manifest.node_version)-win-x64"
        if (Test-Path -LiteralPath $localNodeDistributionRoot -PathType Container) {
            $localNodeDistributionRoot
        } else {
            Split-Path -Parent (Get-Command node.exe -ErrorAction Stop).Source
        }
    }
    $nodeExecutable = Join-Path $nodeDistributionRoot "node.exe"
    $nodeLicense = Join-Path $nodeDistributionRoot "LICENSE"
    if (-not (Test-Path -LiteralPath $nodeLicense -PathType Leaf)) {
        throw "Node distribution LICENSE is missing; set BIJI_NODE_DIST_DIR to an official Windows x64 distribution."
    }
    $actualNodeVersion = (& $nodeExecutable --version).TrimStart('v')
    if ($actualNodeVersion -ne [string]$manifest.node_version) {
        throw "Node version mismatch: expected $($manifest.node_version), got $actualNodeVersion"
    }
    New-Item -ItemType Directory -Path (Join-Path $staging "runtime/node") | Out-Null
    Copy-Item -LiteralPath $nodeExecutable -Destination (Join-Path $staging "runtime/node/node.exe")
    Copy-Item -LiteralPath $nodeLicense -Destination (Join-Path $staging "runtime/node/LICENSE")

    $officecliRoot = if ($env:BIJI_OFFICECLI_PACKAGE_DIR) {
        $env:BIJI_OFFICECLI_PACKAGE_DIR
    } else {
        $localOfficecliRoot = Join-Path (
            Join-Path (
                Join-Path $projectRoot "dist/toolchain"
            ) "officecli-$($manifest.officecli_version)"
        ) "node_modules/@officecli/officecli"
        if (Test-Path -LiteralPath $localOfficecliRoot -PathType Container) {
            $localOfficecliRoot
        } else {
            Join-Path $env:APPDATA "npm/node_modules/@officecli/officecli"
        }
    }
    $officePackage = Get-Content -Raw -LiteralPath (Join-Path $officecliRoot "package.json") -Encoding UTF8 | ConvertFrom-Json
    if ([string]$officePackage.version -ne [string]$manifest.officecli_version) {
        throw "OfficeCLI version mismatch: expected $($manifest.officecli_version), got $($officePackage.version)"
    }
    $officeTarget = Join-Path $staging "tools/officecli"
    New-Item -ItemType Directory -Path (Join-Path $officeTarget "lib") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $officeTarget "vendor") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $officecliRoot "officecli.js") -Destination (Join-Path $officeTarget "officecli.js")
    Copy-Item -LiteralPath (Join-Path $officecliRoot "package.json") -Destination (Join-Path $officeTarget "package.json")
    Copy-Item -LiteralPath (Join-Path $officecliRoot "README.md") -Destination (Join-Path $officeTarget "README.md")
    Copy-Item -LiteralPath (Join-Path $officecliRoot "lib/install-binary.js") -Destination (Join-Path $officeTarget "lib/install-binary.js")
    Copy-Item -LiteralPath (Join-Path $officecliRoot "vendor/officecli.exe") -Destination (Join-Path $officeTarget "vendor/officecli.exe")
    Copy-Item -Recurse -LiteralPath "hashmyfiles" -Destination (Join-Path $staging "tools/hashmyfiles")

    Copy-Item -LiteralPath "packaging/THIRD-PARTY-NOTICES.txt" -Destination (Join-Path $staging "THIRD-PARTY-NOTICES.txt")
    Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $staging "portable-manifest.json")
    New-Item -ItemType Directory -Path (Join-Path $staging "licenses") | Out-Null
    Copy-Item -LiteralPath "packaging/licenses/Apache-2.0.txt" -Destination (Join-Path $staging "licenses/officecli-Apache-2.0.txt")
    Set-Content -LiteralPath (Join-Path $staging "VERSION") -Value $version -Encoding UTF8
    $usageFileName = -join ([char]0x4f7f, [char]0x7528, [char]0x8bf4, [char]0x660e) + ".txt"
    $usageText = Get-Content -Raw -LiteralPath "packaging/PORTABLE-README.txt" -Encoding UTF8
    $usageText = $usageText.Replace("{{PRODUCT}}", $product).Replace("{{VERSION}}", $version)
    Set-Content -LiteralPath (Join-Path $staging $usageFileName) -Encoding UTF8 -Value $usageText

    $generatedLauncher = Join-Path $buildRoot "generated-launcher"
    python scripts/generate-launcher-integrity.py --staging $staging --output (Join-Path $generatedLauncher "generated_integrity.py")
    if ($LASTEXITCODE -ne 0) { throw "Launcher integrity generation failed with exit code $LASTEXITCODE." }
    $env:BIJI_LAUNCHER_GENERATED_DIR = $generatedLauncher
    python -m PyInstaller --noconfirm --distpath $pyinstallerDist --workpath $pyinstallerWork packaging/launcher.spec
    if ($LASTEXITCODE -ne 0) { throw "Launcher packaging failed with exit code $LASTEXITCODE." }
    Copy-Item -LiteralPath (Join-Path $pyinstallerDist "$product.exe") -Destination (Join-Path $staging "$product.exe")

    $privateNode = Join-Path $staging "runtime/node/node.exe"
    $privateOfficecli = Join-Path $staging "tools/officecli/officecli.js"
    $actualOfficecliVersion = (& $privateNode $privateOfficecli --version).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Bundled officecli smoke test failed with exit code $LASTEXITCODE." }
    if ($actualOfficecliVersion -ne [string]$manifest.officecli_version) {
        throw "Bundled OfficeCLI binary mismatch: expected $($manifest.officecli_version), got $actualOfficecliVersion"
    }
    $officeSmokeRoot = Join-Path $buildRoot "officecli-smoke"
    New-Item -ItemType Directory -Path $officeSmokeRoot | Out-Null
    $officeSmokeDocx = Join-Path $officeSmokeRoot "SYNTHETIC-officecli-smoke.docx"
    $officeSmokeBatch = Join-Path $officeSmokeRoot "SYNTHETIC-officecli-batch.json"
    Set-Content -LiteralPath $officeSmokeBatch -Encoding ASCII -Value '[{"command":"add","parent":"/body","type":"paragraph","props":{"text":"SYNTHETIC portable smoke"}}]'
    $savedPath = $env:Path
    $hadOfficecliNoAutoResident = Test-Path Env:OFFICECLI_NO_AUTO_RESIDENT
    $savedOfficecliNoAutoResident = $env:OFFICECLI_NO_AUTO_RESIDENT
    try {
        $env:Path = Join-Path $env:SystemRoot "System32"
        $env:OFFICECLI_NO_AUTO_RESIDENT = "1"
        & $privateNode $privateOfficecli create $officeSmokeDocx
        if ($LASTEXITCODE -ne 0) { throw "Bundled officecli create smoke failed with exit code $LASTEXITCODE." }
        & $privateNode $privateOfficecli batch $officeSmokeDocx --input $officeSmokeBatch
        if ($LASTEXITCODE -ne 0) { throw "Bundled officecli batch smoke failed with exit code $LASTEXITCODE." }
        & $privateNode $privateOfficecli save $officeSmokeDocx
        if ($LASTEXITCODE -ne 0) { throw "Bundled officecli save smoke failed with exit code $LASTEXITCODE." }
    } finally {
        $env:Path = $savedPath
        if ($hadOfficecliNoAutoResident) {
            $env:OFFICECLI_NO_AUTO_RESIDENT = $savedOfficecliNoAutoResident
        } else {
            Remove-Item Env:OFFICECLI_NO_AUTO_RESIDENT -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path -LiteralPath $officeSmokeDocx -PathType Leaf) -or (Get-Item -LiteralPath $officeSmokeDocx).Length -eq 0) {
        throw "Bundled officecli smoke output is missing or empty."
    }
    python scripts/verify-portable-package.py --staging $staging --manifest $manifestPath --output (Join-Path $projectRoot $OutputRoot)
    if ($LASTEXITCODE -ne 0) { throw "Portable package verification failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}
