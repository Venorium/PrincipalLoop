# From the project root: powershell -File scripts/bootstrap.ps1
# Changes neither PATH, the registry, a global Python installation nor Git remotes.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.tools/bootstrap/Scripts/python.exe')) {
        & python -m venv .tools/bootstrap
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the bootstrap environment.' }
    }
    & .tools/bootstrap/Scripts/python -m pip install --disable-pip-version-check 'uv==0.12.23'
    if ($LASTEXITCODE -ne 0) { throw 'Could not install uv.' }
    & .tools/bootstrap/Scripts/uv --cache-dir .tools/cache python install 3.13.16 --install-dir .tools/python --no-bin --no-registry
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the Python runtime.' }
    $runtime = Join-Path $projectRoot '.tools/python/cpython-3.13.16-windows-x86_64-none/python.exe'
    if (-not (Test-Path -LiteralPath $runtime)) { throw 'This bootstrap is qualified for Windows x64 only.' }
    & .tools/bootstrap/Scripts/uv --cache-dir .tools/cache sync --locked --no-python-downloads --python $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Could not rebuild the environment.' }
    & .venv/Scripts/python -m principalloop doctor
    if ($LASTEXITCODE -ne 0) { throw 'The runtime is not admitted.' }
} finally {
    Pop-Location
}
