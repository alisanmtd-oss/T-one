param(
  [string]$InstallerPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $InstallerPath) {
  $InstallerPath = Join-Path $root "desktop_public\dist\T-One-Community-Setup-0.5.0.exe"
}
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$acceptanceRoot = Join-Path ([IO.Path]::GetTempPath()) ("t-one-community-installer-" + [guid]::NewGuid().ToString("N"))
$installDir = Join-Path $acceptanceRoot "app"
$desktopDirectory = [Environment]::GetFolderPath("Desktop")
$startDirectory = [Environment]::GetFolderPath("Programs")
$desktopShortcut = $null
$startShortcut = $null

if ((Get-ChildItem -LiteralPath $desktopDirectory -Filter "T One*.lnk" -ErrorAction SilentlyContinue) -or
    (Get-ChildItem -LiteralPath $startDirectory -Filter "T One*.lnk" -ErrorAction SilentlyContinue)) {
  throw "Refusing to overwrite an existing T One Community shortcut during acceptance."
}
New-Item -ItemType Directory -Path $acceptanceRoot | Out-Null

$result = [ordered]@{
  status = "FAIL"
  installer = $installer
  selectable_install_directory = $installDir
  installed_app_ready = $false
  desktop_shortcut_created = $false
  start_menu_shortcut_created = $false
  uninstaller_present = $false
  uninstall_removed_install_directory = $false
  external_actions = 0
}

try {
  $install = Start-Process -FilePath $installer -ArgumentList @("/S", "/currentuser", "/D=$installDir") -Wait -PassThru
  if ($install.ExitCode -ne 0) { throw "Installer exited with $($install.ExitCode)." }
  $appPath = Get-ChildItem -LiteralPath $installDir -Filter "*.exe" | Where-Object { $_.Name -notlike "Uninstall*" } | Select-Object -First 1 -ExpandProperty FullName
  $uninstaller = Get-ChildItem -LiteralPath $installDir -Filter "Uninstall*.exe" | Select-Object -First 1 -ExpandProperty FullName
  if (-not $appPath -or -not (Test-Path -LiteralPath $appPath)) {
    $installedNames = @(Get-ChildItem -LiteralPath $installDir -Force -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
    throw "Installed application is missing. Found: $($installedNames -join ', ')"
  }
  if (-not (Test-Path -LiteralPath (Join-Path $installDir "resources\app.asar"))) {
    throw "Installed local workspace runtime is missing."
  }
  $desktopShortcut = Get-ChildItem -LiteralPath $desktopDirectory -Filter "T One*.lnk" | Select-Object -First 1 -ExpandProperty FullName
  $startShortcut = Get-ChildItem -LiteralPath $startDirectory -Filter "T One*.lnk" | Select-Object -First 1 -ExpandProperty FullName
  $result.desktop_shortcut_created = [bool]$desktopShortcut
  $result.start_menu_shortcut_created = [bool]$startShortcut
  $result.uninstaller_present = [bool]$uninstaller -and (Test-Path -LiteralPath $uninstaller)
  if (-not $result.desktop_shortcut_created -or -not $result.start_menu_shortcut_created -or -not $result.uninstaller_present) {
    throw "Installer did not create the expected shortcuts and uninstaller."
  }

  $app = Start-Process -FilePath $appPath -PassThru
  $deadline = [DateTime]::UtcNow.AddSeconds(30)
  while ([DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 250
    $app.Refresh()
    if (-not $app.HasExited -and $app.MainWindowHandle -ne 0) {
      $result.installed_app_ready = $true
      break
    }
  }
  if (-not $result.installed_app_ready) { throw "Installed application did not open a real window." }
  [void]$app.CloseMainWindow()
  if (-not $app.WaitForExit(5000)) { Stop-Process -Id $app.Id -Force }

  $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @("/S", "/currentuser") -Wait -PassThru
  if ($uninstall.ExitCode -ne 0) { throw "Uninstaller exited with $($uninstall.ExitCode)." }
  $deadline = [DateTime]::UtcNow.AddSeconds(15)
  while ([DateTime]::UtcNow -lt $deadline -and (Test-Path -LiteralPath $installDir)) {
    Start-Sleep -Milliseconds 250
  }
  $result.uninstall_removed_install_directory = -not (Test-Path -LiteralPath $installDir)
  if (-not $result.uninstall_removed_install_directory) { throw "Uninstaller left the application directory behind." }
  if (($desktopShortcut -and (Test-Path -LiteralPath $desktopShortcut)) -or
      ($startShortcut -and (Test-Path -LiteralPath $startShortcut))) {
    throw "Uninstaller left a shortcut behind."
  }
  $result.status = "PASS"
} finally {
  $shortcutShell = New-Object -ComObject WScript.Shell
  foreach ($shortcutPath in @($desktopShortcut, $startShortcut)) {
    if ($shortcutPath -and (Test-Path -LiteralPath $shortcutPath)) {
      $shortcutTarget = $shortcutShell.CreateShortcut($shortcutPath).TargetPath
      if ($shortcutTarget -and ([IO.Path]::GetFullPath($shortcutTarget)).StartsWith([IO.Path]::GetFullPath($acceptanceRoot), [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $shortcutPath -Force
      }
    }
  }
  $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  $resolvedAcceptanceRoot = [IO.Path]::GetFullPath($acceptanceRoot)
  if ($resolvedAcceptanceRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $acceptanceRoot)) {
    Remove-Item -LiteralPath $acceptanceRoot -Recurse -Force
  }
}

$result | ConvertTo-Json -Depth 4
if ($result.status -ne "PASS") { exit 1 }
