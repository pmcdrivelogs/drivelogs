# Run this script AFTER you install Git and configure credentials.
# Save and run in PowerShell from the project root (where this file lives).

# 1) Configure identity (only needed once)
# git config --global user.name "Your Name"
# git config --global user.email "your.email@example.com"

# 2) Initialize repository if not already a git repo
if (-not (Test-Path .git)) {
  git init
  Write-Output "Initialized empty git repository."
} else {
  Write-Output ".git already exists - skipping git init."
}

# 3) Add all files and commit
git add .
try {
  git commit -m "Updated payment voucher system with header images and form fixes"
} catch {
  Write-Output "No changes to commit or commit failed: $_"
}

# 4) Add remote (if not already present)
$existing = git remote
if (-not $existing) {
  git remote add origin https://github.com/pmcdrivelogs/drivelogs.git
  Write-Output "Added remote origin."
} else {
  Write-Output "Remote(s) present: $existing"
}

# 5) Ensure branch name and push
# Determine local branch (create main if none)
$branch = git rev-parse --abbrev-ref HEAD 2>$null
if ($LASTEXITCODE -ne 0 -or $branch -eq "HEAD") {
  git branch -M main
  $branch = 'main'
  Write-Output "Created/renamed branch to main."
}

# Attempt to push. If remote has history, you may need to pull first or use --allow-unrelated-histories.
Write-Output "Pushing to origin/$branch..."
git push -u origin $branch

Write-Output "If push fails due to authentication, create a Personal Access Token (PAT) on GitHub and use it as your password when prompted, or configure SSH keys."