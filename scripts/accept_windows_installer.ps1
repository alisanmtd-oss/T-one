param(
  [string]$InstallerPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $InstallerPath) {
  $InstallerPath = Join-Path $root "desktop_public\dist\T-One-Community-Setup-0.4.3.exe"
}
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$acceptanceRoot = Join-Path ([IO.Path]::GetTempPath()) ("t-one-community-installer-" + [guid]::NewGuid().ToString("N"))
$installDir = Join-Path $acceptanceRoot "app"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "T One Community.lnk"
$startShortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "T One Community.lnk"

if ((Test-Path -LiteralPath $desktopShortcut) -or (Test-Path -LiteralPath $startShortcut)) {
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
  $appPath = Join-Path $installDir "T One Community.exe"
  $uninstaller = Join-Path $installDir "Uninstall T One Community.exe"
  if (-not (Test-Path -LiteralPath $appPath)) { throw "Installed application is missing." }
  if (-not (Test-Path -LiteralPath (Join-Path $installDir "resources\public-demo\chat-first-workspace.html"))) {
    throw "Installed offline demo resource is missing."
  }
  $result.desktop_shortcut_created = Test-Path -LiteralPath $desktopShortcut
  $result.start_menu_shortcut_created = Test-Path -LiteralPath $startShortcut
  $result.uninstaller_present = Test-Path -LiteralPath $uninstaller
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
  if ((Test-Path -LiteralPath $desktopShortcut) -or (Test-Path -LiteralPath $startShortcut)) {
    throw "Uninstaller left a shortcut behind."
  }
  $result.status = "PASS"
} finally {
  $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  $resolvedAcceptanceRoot = [IO.Path]::GetFullPath($acceptanceRoot)
  if ($resolvedAcceptanceRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $acceptanceRoot)) {
    Remove-Item -LiteralPath $acceptanceRoot -Recurse -Force
  }
}

$result | ConvertTo-Json -Depth 4
if ($result.status -ne "PASS") { exit 1 }
