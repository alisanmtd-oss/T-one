param(
  [ValidateSet("home", "inventory", "orders", "ads", "coupons")]
  [string]$Surface = "home",
  [ValidateSet(42, 43)]
  [int]$ProfileSeq
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Import-Module -Force -Name (Join-Path $PSScriptRoot "lib\shein_store_surface.psm1") -ErrorAction Stop

function Connect-Cdp([string]$WebSocketUrl) {
  $ws = [System.Net.WebSockets.ClientWebSocket]::new()
  $ws.ConnectAsync([Uri]$WebSocketUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null
  return $ws
}

function Invoke-Cdp($Ws, [ref]$NextId, [string]$Method, $Params) {
  $id = $NextId.Value
  $NextId.Value += 1
  $payload = @{ id = $id; method = $Method; params = $Params } | ConvertTo-Json -Compress -Depth 30
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
  $Ws.SendAsync(
    [ArraySegment[byte]]::new($bytes),
    [System.Net.WebSockets.WebSocketMessageType]::Text,
    $true,
    [Threading.CancellationToken]::None
  ).GetAwaiter().GetResult() | Out-Null
  while ($true) {
    $buffer = New-Object byte[] 1048576
    $stream = [System.IO.MemoryStream]::new()
    do {
      $received = $Ws.ReceiveAsync(
        [ArraySegment[byte]]::new($buffer),
        [Threading.CancellationToken]::None
      ).GetAwaiter().GetResult()
      if ($received.Count -gt 0) { $stream.Write($buffer, 0, $received.Count) }
    } while (-not $received.EndOfMessage)
    $message = [System.Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
    if ($message.id -eq $id) { return $message }
  }
}

function Get-BitBrowserLocalApiHeaders {
  $configPath = Join-Path $env:APPDATA "BitBrowser\config.json"
  if (-not (Test-Path -LiteralPath $configPath)) { return @{} }
  try {
    $config = Get-Content -Raw -LiteralPath $configPath -Encoding UTF8 | ConvertFrom-Json
    $token = [string]$config.authToken
    if ($config.enableAuth -eq $true -and $token) {
      return @{ "X-Api-Key" = $token }
    }
  } catch {
    return @{}
  }
  return @{}
}

$matchedProcess = $null
$debugPort = 0
$tabs = @()
$reusedExistingSession = $true
$profileIds = @{
  42 = "baa9da493f804f85aa500e49cc27db3a"
  43 = "153c7f1731344b39969c59a5f58dc916"
}
$expectedProfileId = [string]$profileIds[$ProfileSeq]
$activePortFile = Join-Path $env:USERPROFILE "AppData\Roaming\BitBrowser\BrowserCache\$expectedProfileId\DevToolsActivePort"
if (Test-Path -LiteralPath $activePortFile) {
  try {
    $candidatePort = [int]((Get-Content -LiteralPath $activePortFile -TotalCount 1).Trim())
    $candidateTabs = @(Invoke-RestMethod -Uri "http://127.0.0.1:$candidatePort/json/list" -TimeoutSec 5)
    $sellerPages = @($candidateTabs | Where-Object { $_.type -eq "page" -and [string]$_.url -match "^https://sellerhub\.shein\.com" })
    if ($candidatePort -gt 0 -and $sellerPages.Count -gt 0) {
      $debugPort = $candidatePort
      $tabs = $candidateTabs
      $matchedProcess = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "BitBrowser.exe" -and [string]$_.CommandLine -match [regex]::Escape($expectedProfileId)
      } | Sort-Object @{ Expression = { if ([int]$_.ProcessId -gt 0) { 0 } else { 1 } } } | Select-Object -First 1
      if (-not $matchedProcess) { $matchedProcess = [pscustomobject]@{ ProcessId = 0 } }
    }
  } catch {
    $debugPort = 0
    $tabs = @()
    $matchedProcess = $null
  }
}
$sheinProcesses = @(Get-Process -Name "BitBrowser" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
foreach ($process in @($sheinProcesses | Where-Object { $debugPort -le 0 })) {
  $ports = @($listeners | Where-Object { $_.OwningProcess -eq $process.Id } | Select-Object -ExpandProperty LocalPort)
  foreach ($port in $ports) {
    try {
      $rawCandidateTabs = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/list" -TimeoutSec 5
      $candidateTabs = @()
      foreach ($candidateTab in $rawCandidateTabs) { $candidateTabs += $candidateTab }
      $profileMarker = @($candidateTabs | Where-Object { $_.type -eq "page" -and [string]$_.url -match [regex]::Escape($expectedProfileId) })
      $sellerPages = @($candidateTabs | Where-Object { $_.type -eq "page" -and [string]$_.url -match "^https://sellerhub\.shein\.com" })
      if ($profileMarker.Count -gt 0 -and $sellerPages.Count -gt 0) {
        $matchedProcess = $process
        $debugPort = [int]$port
        $tabs = $candidateTabs
        break
      }
    } catch {
      # Ignore non-CDP listeners owned by the already selected SHEIN process.
    }
  }
  if ($debugPort -gt 0) { break }
}

if ($debugPort -le 0 -or -not $matchedProcess) {
  $managerOpenError = ""
  try {
    $openBody = @{ id = $expectedProfileId; queue = $true } | ConvertTo-Json -Compress
    $opened = Invoke-RestMethod `
      -Method Post `
      -Uri "http://127.0.0.1:54345/browser/open" `
      -ContentType "application/json" `
      -Headers (Get-BitBrowserLocalApiHeaders) `
      -Body $openBody `
      -TimeoutSec 20
    if ($opened.success -and $opened.data.http) {
      $debugPort = [int](([string]$opened.data.http -split ':')[-1])
      $reusedExistingSession = $false
      for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
          $tabs = @(Invoke-RestMethod -Uri "http://127.0.0.1:$debugPort/json/list" -TimeoutSec 5)
          if ($tabs.Count -gt 0) { break }
        } catch {
          $tabs = @()
        }
        Start-Sleep -Milliseconds 500
      }
      $openedPid = [int]($opened.data.pid)
      $matchedProcess = if ($openedPid -gt 0) {
        [pscustomobject]@{ ProcessId = $openedPid }
      } else {
        [pscustomobject]@{ ProcessId = 0 }
      }
    }
  } catch {
    $managerOpenError = [string]$_.Exception.Message
    if ($_.ErrorDetails.Message) {
      try {
        $managerFailure = $_.ErrorDetails.Message | ConvertFrom-Json
        if ($managerFailure.msg) { $managerOpenError = [string]$managerFailure.msg }
      } catch {
        # Keep only the exception message; the Local API token is never logged.
      }
    }
    $debugPort = 0
    $tabs = @()
    $matchedProcess = $null
  }
}

if ($debugPort -le 0 -or -not $matchedProcess) {
  $reason = if ($managerOpenError) { " Reason: $managerOpenError" } else { "" }
  throw "BitBrowser profile $ProfileSeq is not active and the exact bound profile could not be opened through the local manager API.$reason"
}

$supportedReadOnlySurface = $Surface -in @("home", "inventory", "orders")
$targetUrls = @{
  home = "https://sellerhub.shein.com/"
  inventory = "https://sellerhub.shein.com/#/spmp/commdities/list"
  orders = "https://sellerhub.shein.com/#/gsp/order-management/list"
}
$targetUrl = if ($supportedReadOnlySurface) { [string]$targetUrls[$Surface] } else { "" }
$pages = @($tabs | Where-Object { $_.type -eq "page" -and [string]$_.url -match "^https://sellerhub\.shein\.com" })
$selectedPages = @(Select-TOneSheinSellerPage -Pages $pages -Surface $Surface)
$page = if ($selectedPages.Count -gt 0) { $selectedPages[0] } else { $null }
$navigationAttempted = $false

if (-not $page -and $supportedReadOnlySurface -and $targetUrl) {
  $navigationAttempted = $true
  try {
    $encodedTarget = [uri]::EscapeDataString($targetUrl)
    Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:$debugPort/json/new?$encodedTarget" -TimeoutSec 10 | Out-Null
    for ($attempt = 0; $attempt -lt 20 -and -not $page; $attempt++) {
      Start-Sleep -Milliseconds 500
      $refreshedTabs = @(Invoke-RestMethod -Uri "http://127.0.0.1:$debugPort/json/list" -TimeoutSec 5)
      $refreshedPages = @($refreshedTabs | Where-Object { $_.type -eq "page" -and [string]$_.url -match "^https://sellerhub\.shein\.com" })
      $selectedPages = @(Select-TOneSheinSellerPage -Pages $refreshedPages -Surface $Surface)
      if ($selectedPages.Count -gt 0) { $page = $selectedPages[0] }
    }
  } catch {
    $page = $null
  }
}

$broughtToFront = $false
if ($page -and $supportedReadOnlySurface) {
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$debugPort/json/activate/$([string]$page.id)" -TimeoutSec 5 | Out-Null
    $broughtToFront = $true
  } catch {
    $broughtToFront = $false
  }
}

$observedUrl = if ($page) { [string]$page.url } else { "" }
$surfaceVerified = [bool]($page -and (Test-TOneSheinSurface -Page $page -Surface $Surface))
$authRequired = [bool]($observedUrl -match "(?i)(login|signin|sso|identity|verification)")
$pageState = if ($authRequired) {
  "needs_login"
} elseif (-not $supportedReadOnlySurface) {
  "unsupported_read_only_surface"
} elseif ($broughtToFront -and $surfaceVerified) {
  "opened"
} else {
  "unverified"
}

$orderSummary = $null
if ($Surface -eq "orders" -and $pageState -eq "opened" -and $page.webSocketDebuggerUrl) {
  try {
    $ws = Connect-Cdp ([string]$page.webSocketDebuggerUrl)
    $nextId = 1
    Invoke-Cdp $ws ([ref]$nextId) "Runtime.enable" @{} | Out-Null
    $expression = @'
(() => {
  const text = String(document.body ? document.body.innerText : '');
  const lines = text.split('\n').map(value => value.trim()).filter(Boolean);
  const summaryLine = lines.find(value => value.includes('\u5f53\u524d\u7b5b\u9009\u6761\u4ef6\u4e0b\u6570\u636e')) || '';
  const between = (value, start, end) => {
    const left = value.indexOf(start);
    if (left < 0) return '';
    const from = left + start.length;
    const right = end ? value.indexOf(end, from) : value.length;
    return value.slice(from, right < 0 ? value.length : right).trim();
  };
  const numberText = value => [...String(value || '')].filter(char => '0123456789.-'.includes(char)).join('');
  const normalizeCount = value => value && value !== '-' ? Number(numberText(value).replaceAll(',', '')) || 0 : 0;
  const normalizeAmount = value => value && value !== '-' ? numberText(value).replaceAll(',', '') || '0' : '0';
  const rawOrders = between(summaryLine, '\u8ba2\u5355\u6570', '\u5546\u54c1\u4ef6\u6570');
  const rawUnits = between(summaryLine, '\u5546\u54c1\u4ef6\u6570', '\u5546\u54c1\u603b\u4ef7');
  const rawGross = between(summaryLine, '\u5546\u54c1\u603b\u4ef7', '\u9884\u8ba1\u6536\u5165\u6c47\u603b\u91d1\u989d');
  const rawIncome = between(summaryLine, '\u9884\u8ba1\u6536\u5165\u6c47\u603b\u91d1\u989d', '');
  const totalLine = lines.find(value => value.startsWith('\u5171') && value.includes('\u6761')) || '';
  const totalCount = normalizeCount(totalLine);
  const inputs = [...document.querySelectorAll('input')];
  const dateValue = placeholder => {
    const input = inputs.find(node => node.getAttribute('placeholder') === placeholder);
    return String(input ? input.value : '');
  };
  const visible = lines.some(value => value === '\u6211\u7684\u8ba2\u5355' || value.includes('\u8ba2\u5355\u7ba1\u7406') || value === '\u5168\u90e8\u8ba2\u5355');
  const dataReturned = visible && Boolean(summaryLine || totalLine || lines.some(value => value.includes('\u6682\u65e0\u7b26\u5408\u7b5b\u9009\u6761\u4ef6\u7684\u8ba2\u5355')));
  return {
    data_returned: dataReturned,
    order_count: summaryLine ? normalizeCount(rawOrders) : totalCount,
    unit_count: summaryLine ? normalizeCount(rawUnits) : 0,
    gross_sales: summaryLine ? normalizeAmount(rawGross) : '0',
    expected_income: summaryLine ? normalizeAmount(rawIncome) : '0',
    window_start: dateValue('\u5f00\u59cb\u65f6\u95f4').slice(0, 24),
    window_end: dateValue('\u7ed3\u675f\u65f6\u95f4').slice(0, 24),
    source: 'seller_hub_visible_aggregate',
    contains_order_ids_or_customer_pii: false
  };
})()
'@
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
      Start-Sleep -Milliseconds 750
      $evaluated = Invoke-Cdp $ws ([ref]$nextId) "Runtime.evaluate" @{
        expression = $expression
        returnByValue = $true
        awaitPromise = $true
      }
      $orderSummary = $evaluated.result.result.value
      if ($orderSummary -and $orderSummary.data_returned -eq $true) { break }
    }
    $ws.Dispose()
    if (-not $orderSummary -or $orderSummary.data_returned -ne $true) {
      $surfaceVerified = $false
      $pageState = "unverified_order_data"
    }
  } catch {
    $orderSummary = $null
    $surfaceVerified = $false
    $pageState = "unverified_order_data"
  }
}
$matchedProcessId = 0
if ($matchedProcess) {
  if ($matchedProcess.PSObject.Properties.Name -contains "Id") {
    $matchedProcessId = [int]$matchedProcess.Id
  } elseif ($matchedProcess.PSObject.Properties.Name -contains "ProcessId") {
    $matchedProcessId = [int]$matchedProcess.ProcessId
  }
}

[ordered]@{
  ok = $pageState -eq "opened"
  code = if ($authRequired) { "needs_store_login" } elseif ($pageState -eq "opened") { "opened" } else { "unverified_store_surface" }
  platform = "shein"
  country_site = "US"
  surface = $Surface
  profile_seq = $ProfileSeq
  process_id = $matchedProcessId
  debug_port = $debugPort
  reused_existing_session = $reusedExistingSession
  navigation_attempted = $navigationAttempted
  target_url = $targetUrl
  observed_url = $observedUrl
  page_title = if ($page) { [string]$page.title } else { "" }
  auth_required = $authRequired
  page_state = $pageState
  surface_verified = $surfaceVerified
  order_summary = $orderSummary
  external_store_write_actions = 0
} | ConvertTo-Json -Compress
