<#
    Push the app to a Hugging Face Space.

    The Space needs its own README.md carrying YAML frontmatter that Hugging
    Face reads as configuration. Putting that frontmatter in the project README
    would clutter the GitHub landing page, so deployment happens from a staging
    copy: the repo is exported, the Space README swapped in, and that pushed.

    Usage:
        .\deploy\huggingface\deploy.ps1 -Space "ashwinsureshh/industrial-product-intelligence"

    Prerequisites:
        huggingface-cli login      (or set $env:HF_TOKEN)
        git lfs install
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Space,

    [string]$Message = "Deploy product intelligence engine"
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$staging = Join-Path ([System.IO.Path]::GetTempPath()) "pi-space-$(Get-Random)"

Write-Host "Staging from $root" -ForegroundColor Cyan

# Export the tracked tree only — never the working directory, so an untracked
# .env or local cache cannot reach a public Space.
git -C $root archive --format=tar HEAD | tar -x -C (New-Item -ItemType Directory -Path $staging).FullName

# The Space's own README replaces the project one.
Copy-Item (Join-Path $PSScriptRoot 'README.md') (Join-Path $staging 'README.md') -Force

# Belt and braces: these should never be tracked, but a public Space is not the
# place to discover otherwise.
foreach ($unsafe in @('backend\.env', 'backend\.env.local')) {
    $path = Join-Path $staging $unsafe
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Warning "Removed $unsafe from the staged copy."
    }
}

Push-Location $staging
try {
    git init -q
    git checkout -q -b main
    git add -A

    $leak = git grep -I -l -E 'sk-ant-[A-Za-z0-9_-]{20,}' -- . 2>$null
    if ($leak) {
        throw "Refusing to deploy: possible API key found in $leak"
    }

    git -c user.email="deploy@local" -c user.name="deploy" commit -q -m $Message
    git remote add space "https://huggingface.co/spaces/$Space"

    Write-Host "Pushing to https://huggingface.co/spaces/$Space" -ForegroundColor Yellow
    git push -f space main

    Write-Host "`nDeployed. The Space will build for a few minutes, then be live at:" -ForegroundColor Green
    Write-Host "  https://huggingface.co/spaces/$Space"
}
finally {
    Pop-Location
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
}
