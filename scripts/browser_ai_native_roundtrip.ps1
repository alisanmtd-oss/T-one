param(
  [Parameter(Mandatory = $true)][ValidateSet('chatgpt','gemini')][string]$Provider,
  [Parameter(Mandatory = $true)][string]$PromptPath,
  [Parameter(Mandatory = $true)][string]$OutputPath,
  [string]$ProfileHint = '(AI)',
  [string]$ConversationKey = '',
  [string]$ConversationUrl = '',
  [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TOneBrowserWindow {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void SwitchToThisWindow(IntPtr h, bool altTab);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
}
'@

function Write-Result([hashtable]$Payload) {
  $target = [System.IO.Path]::GetFullPath($OutputPath)
  [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null
  $Payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $target -Encoding utf8
}

function Find-ByAutomationId($Root, [string]$AutomationId) {
  $condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
    $AutomationId
  )
  return $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
}

function Find-ByName($Root, [string]$Name) {
  $condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty,
    $Name
  )
  return $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
}

function Find-GeminiComposer($Root) {
  $items = $Root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  foreach ($item in $items) {
    if ($item.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and
        $item.Current.ClassName -like '*ql-editor*' -and $item.Current.IsEnabled) {
      return $item
    }
  }
  return $null
}

function Find-ChromeWindow([string]$Hint) {
  $windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
    [System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  foreach ($window in $windows) {
    if ($window.Current.ClassName -ne 'Chrome_WidgetWin_1') { continue }
    $avatar = Find-ByAutomationId $window 'view_1018'
    if ($avatar -and $avatar.Current.Name -like "*$Hint*") { return $window }
  }
  return $null
}

function Select-ExistingAiTab($Window, [string]$Surface) {
  $address = Find-ByAutomationId $Window 'view_1012'
  $currentAddress = if ($address) {
    try { $address.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value } catch { '' }
  } else { '' }
  $items = $Window.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  $preferred = $null
  $fallback = $null
  foreach ($item in $items) {
    if ($item.Current.ControlType -ne [System.Windows.Automation.ControlType]::TabItem) { continue }
    $name = [string]$item.Current.Name
    $isChatGpt = $name -match 'ChatGPT|^Tone\b'
    $isGemini = $name -match 'Gemini|Exact String'
    if (($Surface -eq 'chatgpt' -and $isChatGpt) -or ($Surface -eq 'gemini' -and $isGemini)) {
      $preferred = $item
      break
    }
    $selection = $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    $selectedAiUrl = $selection.Current.IsSelected -and $currentAddress -match 'chatgpt\.com|gemini\.google\.com'
    if (-not $fallback -and ($isChatGpt -or $isGemini -or $selectedAiUrl)) { $fallback = $item }
  }
  $tab = if ($preferred) { $preferred } else { $fallback }
  if (-not $tab) { throw 'No existing ChatGPT or Gemini tab was found in the logged-in AI Chrome profile.' }
  $tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
  Start-Sleep -Milliseconds 500
  return $tab
}

function Ensure-AiTabSelected($Tab) {
  if (-not $Tab) { return }
  $selection = $Tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
  if (-not $selection.Current.IsSelected) {
    $selection.Select()
    Start-Sleep -Milliseconds 350
  }
}

function Activate-ChromeWindow([IntPtr]$Handle) {
  # Keep the AI composer physically inside the display. Chrome can report a
  # control as visible even when the restored window extends below the screen.
  [TOneBrowserWindow]::ShowWindow($Handle, 3) | Out-Null
  [TOneBrowserWindow]::SetWindowPos($Handle, [IntPtr](-1), 0, 0, 0, 0, 0x43) | Out-Null
  [TOneBrowserWindow]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
  [TOneBrowserWindow]::keybd_event(0x12, 0, 0x0002, [UIntPtr]::Zero)
  [TOneBrowserWindow]::BringWindowToTop($Handle) | Out-Null
  [TOneBrowserWindow]::SetForegroundWindow($Handle) | Out-Null
  if ([TOneBrowserWindow]::GetForegroundWindow() -ne $Handle) {
    [TOneBrowserWindow]::SwitchToThisWindow($Handle, $true)
  }
  for ($index = 0; $index -lt 20; $index++) {
    if ([TOneBrowserWindow]::GetForegroundWindow() -eq $Handle) {
      [TOneBrowserWindow]::SetWindowPos($Handle, [IntPtr](-2), 0, 0, 0, 0, 0x03) | Out-Null
      return
    }
    Start-Sleep -Milliseconds 100
  }
  [TOneBrowserWindow]::SetWindowPos($Handle, [IntPtr](-2), 0, 0, 0, 0, 0x03) | Out-Null
  throw 'The existing AI Chrome window could not be brought to the foreground for visible input.'
}

function Click-VisibleElement($Element) {
  if (-not $Element -or $Element.Current.IsOffscreen) { throw 'The required browser AI control is not visible.' }
  $rect = $Element.Current.BoundingRectangle
  if ($rect.Width -lt 2 -or $rect.Height -lt 2) { throw 'The required browser AI control has no clickable area.' }
  $x = [int]($rect.X + ($rect.Width / 2))
  $y = [int]($rect.Y + ($rect.Height / 2))
  [TOneBrowserWindow]::SetCursorPos($x, $y) | Out-Null
  [TOneBrowserWindow]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
  [TOneBrowserWindow]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 250
}

function Navigate-Chrome($Window, [string]$Url) {
  Activate-ChromeWindow ([IntPtr]$Window.Current.NativeWindowHandle)
  $address = Find-ByAutomationId $Window 'view_1012'
  if (-not $address) { throw 'Chrome address bar is unavailable.' }
  $value = $address.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  $value.SetValue($Url)
  $address.SetFocus()
  $shell = New-Object -ComObject WScript.Shell
  $shell.SendKeys('{ENTER}')
}

function Get-ChromeAddress($Window) {
  $address = Find-ByAutomationId $Window 'view_1012'
  if (-not $address) { return '' }
  try {
    return [string]$address.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
  } catch {
    return ''
  }
}

function Test-ProviderThreadUrl([string]$Surface, [string]$Url) {
  if ([string]::IsNullOrWhiteSpace($Url)) { return $false }
  if ($Surface -eq 'chatgpt') {
    return $Url -match '^https://chatgpt\.com/.*/?c/' -or $Url -match '^https://chatgpt\.com/c/'
  }
  return $Url -match '^https://gemini\.google\.com/app/.+'
}

function Text-Values($Root) {
  $items = $Root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  $values = New-Object System.Collections.Generic.List[string]
  foreach ($item in $items) {
    if ($item.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text) { continue }
    $value = [string]$item.Current.Name
    if (-not [string]::IsNullOrWhiteSpace($value)) { $values.Add($value.Trim()) }
  }
  return @($values)
}

function Latest-GeminiResponse($Root) {
  $items = $Root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  $containers = New-Object System.Collections.Generic.List[object]
  foreach ($item in $items) {
    if ($item.Current.AutomationId -like 'model-response-message-content*') {
      $containers.Add($item)
    }
  }
  if ($containers.Count -eq 0) { return '' }
  return ((Text-Values $containers[$containers.Count - 1]) -join "`n").Trim()
}

function Wait-Composer([IntPtr]$Handle, [string]$Surface, [datetime]$Deadline, $AiTab) {
  $readySince = $null
  while ((Get-Date) -lt $Deadline) {
    Activate-ChromeWindow $Handle
    Ensure-AiTabSelected $AiTab
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    if ($Surface -eq 'chatgpt') {
      $overlayClosed = Close-OptionalBlockingOverlay $root
      if ($overlayClosed) { $readySince = $null }
      $root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
    }
    $composer = if ($Surface -eq 'chatgpt') {
      Find-ByAutomationId $root 'prompt-textarea'
    } else {
      Find-GeminiComposer $root
    }
    if ($composer -and $composer.Current.IsEnabled) {
      if ($Surface -ne 'chatgpt') { return @($root, $composer) }
      if (-not $readySince) { $readySince = Get-Date }
      if (((Get-Date) - $readySince).TotalMilliseconds -ge 2000) { return @($root, $composer) }
    } else {
      $readySince = $null
    }
    Start-Sleep -Milliseconds 350
  }
  throw "The $Surface composer was not available in the existing AI Chrome profile."
}

function Send-VisiblePrompt([IntPtr]$Handle, $Root, $Composer, [string]$Surface, [string]$Prompt) {
  Activate-ChromeWindow $Handle
  if ($Surface -eq 'chatgpt') {
    $Composer.SetFocus()
    Set-Clipboard -Value $Prompt
    try {
      $shell = New-Object -ComObject WScript.Shell
      $shell.SendKeys('^v')
      Start-Sleep -Milliseconds 350
      $send = $null
      for ($index = 0; $index -lt 30 -and -not $send; $index++) {
        $send = Find-ByAutomationId $Root 'composer-submit-button'
        if (-not $send) { Start-Sleep -Milliseconds 200 }
      }
      if (-not $send) { throw 'The ChatGPT send button did not appear after visible keyboard input.' }
      $send.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
      return
    } finally {
      Set-Clipboard -Value ' '
    }
  }
  Set-Clipboard -Value $Prompt
  try {
    $Composer = $null
    for ($index = 0; $index -lt 30 -and -not $Composer; $index++) {
      $Root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
      $Composer = Find-GeminiComposer $Root
      if (-not $Composer) { Start-Sleep -Milliseconds 200 }
    }
    if (-not $Composer) { throw 'The Gemini visible composer is unavailable before keyboard input.' }
    Click-VisibleElement $Composer
    for ($index = 0; $index -lt 20 -and -not $Composer.Current.HasKeyboardFocus; $index++) {
      try { $Composer.SetFocus() } catch {}
      Start-Sleep -Milliseconds 100
    }
    Start-Sleep -Milliseconds 300
    [TOneBrowserWindow]::keybd_event(0x11, 0, 0, [UIntPtr]::Zero)
    [TOneBrowserWindow]::keybd_event(0x56, 0, 0, [UIntPtr]::Zero)
    [TOneBrowserWindow]::keybd_event(0x56, 0, 0x0002, [UIntPtr]::Zero)
    [TOneBrowserWindow]::keybd_event(0x11, 0, 0x0002, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 500
    $currentComposer = $null
    for ($index = 0; $index -lt 20 -and -not $currentComposer; $index++) {
      $Root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
      $currentComposer = Find-GeminiComposer $Root
      if (-not $currentComposer) { Start-Sleep -Milliseconds 100 }
    }
    if (-not $currentComposer) { throw 'The Gemini visible composer disappeared after keyboard input.' }
    $value = $currentComposer.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    if ($value.Current.Value -ne $Prompt) {
      Activate-ChromeWindow $Handle
      Click-VisibleElement $currentComposer
      try { $currentComposer.SetFocus() } catch {}
      $shell = New-Object -ComObject WScript.Shell
      $shell.SendKeys('^a')
      $shell.SendKeys('{BACKSPACE}')
      $shell.SendKeys('^v')
      Start-Sleep -Milliseconds 700
      $Root = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
      $currentComposer = Find-GeminiComposer $Root
      if (-not $currentComposer) { throw 'The Gemini visible composer disappeared during the keyboard retry.' }
      $value = $currentComposer.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    }
    if ($value.Current.Value -ne $Prompt) { throw 'The Gemini visible composer did not accept the keyboard prompt.' }
    $sendName = [string][char]21457 + [char]36865
    $send = $null
    for ($index = 0; $index -lt 30 -and -not $send; $index++) {
      $send = Find-ByName $Root $sendName
      if (-not $send) { Start-Sleep -Milliseconds 200 }
    }
    if (-not $send) { throw 'The Gemini send button did not appear after visible input.' }
    $send.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  } finally {
    Set-Clipboard -Value ' '
  }
}

function Close-OptionalBlockingOverlay($Root) {
  $pricingCloseName = [string][char]20851 + [char]38381 + [char]21319 + [char]32423 + [char]22871 + [char]39184 + [char]24377 + [char]31383
  $button = Find-ByName $Root $pricingCloseName
  if ($button) {
    try {
      $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
      Start-Sleep -Milliseconds 500
    } catch {
      throw 'A ChatGPT pricing overlay blocked the existing logged-in chat.'
    }
    return $true
  }
  return $false
}

try {
  $prompt = (Get-Content -LiteralPath $PromptPath -Raw -Encoding utf8).Trim()
  if (-not $prompt) { throw 'Browser AI prompt is empty.' }
  $window = Find-ChromeWindow $ProfileHint
  if (-not $window) { throw "No existing Chrome window matched profile hint $ProfileHint." }
  $handle = [IntPtr]$window.Current.NativeWindowHandle
  $aiTab = Select-ExistingAiTab $window $Provider
  $selectedAiTabName = [string]$aiTab.Current.Name
  $currentUrl = Get-ChromeAddress $window
  $providerHome = if ($Provider -eq 'chatgpt') { 'https://chatgpt.com/' } else { 'https://gemini.google.com/app' }
  $conversationReused = $false
  $targetUrl = $providerHome
  if (Test-ProviderThreadUrl $Provider $ConversationUrl) {
    $targetUrl = $ConversationUrl
    $conversationReused = $true
  } elseif (Test-ProviderThreadUrl $Provider $currentUrl) {
    # The first task turn adopts the already-open real thread. Later turns use
    # the locally persisted project/task/provider URL passed above.
    $targetUrl = $currentUrl
    $conversationReused = $true
  }
  $navigationRequired = $currentUrl.TrimEnd('/') -ne $targetUrl.TrimEnd('/')
  if ($navigationRequired) {
    Navigate-Chrome $window $targetUrl
  } else {
    Activate-ChromeWindow $handle
  }
  $deadline = (Get-Date).AddSeconds([Math]::Max(30, $TimeoutSeconds))
  $ready = Wait-Composer $handle $Provider $deadline $aiTab
  $root = $ready[0]
  $composer = $ready[1]
  $pricingOverlayClosed = Close-OptionalBlockingOverlay $root
  $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
  $ready = Wait-Composer $handle $Provider $deadline $aiTab
  $composer = $ready[1]
  $loginName = [string][char]30331 + [char]24405
  if (Find-ByName $root $loginName) { throw "The selected $Provider page is not logged in." }

  $before = @(Text-Values $root)
  $beforeSet = @{}
  foreach ($value in $before) { $beforeSet[$value] = $true }
  $beforeProviderResponse = if ($Provider -eq 'gemini') { Latest-GeminiResponse $root } else { '' }
  Send-VisiblePrompt $handle $root $composer $Provider $prompt

  $last = ''
  $stable = 0
  $response = ''
  $submissionConfirmed = $false
  while ((Get-Date) -lt $deadline) {
    Activate-ChromeWindow $handle
    Ensure-AiTabSelected $aiTab
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
    if (-not $submissionConfirmed) {
      $visibleText = @(Text-Values $root)
      $addressNow = Find-ByAutomationId $root 'view_1012'
      $urlNow = if ($addressNow) {
        $addressNow.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
      } else { '' }
      $submissionConfirmed = @($visibleText | Where-Object {
        $_ -eq $prompt -or $_.EndsWith($prompt)
      }).Count -gt 0
      if ($Provider -eq 'chatgpt') { $submissionConfirmed = $submissionConfirmed -and $urlNow.Contains('chatgpt.com/c/') }
      if ($Provider -eq 'gemini') { $submissionConfirmed = $submissionConfirmed -and $urlNow.Contains('gemini.google.com/app/') }
      if (-not $submissionConfirmed) { Start-Sleep -Seconds 1; continue }
    }
    if ($Provider -eq 'gemini') {
      $candidate = (Latest-GeminiResponse $root).Trim()
      if ($candidate -eq $beforeProviderResponse) { $candidate = '' }
    } else {
      $after = @(Text-Values $root)
      $mistakeWord = [string][char]29359 + [char]38169
      $delta = @($after | Where-Object {
        $_ -ne $prompt -and
        -not $beforeSet.ContainsKey($_) -and
        $_.Length -gt 1 -and
        -not ($_.StartsWith('ChatGPT ') -and $_.Contains($mistakeWord))
      })
      $candidate = ($delta -join "`n").Trim()
    }
    if ($candidate -and $candidate -eq $last) { $stable++ } else { $stable = 0; $last = $candidate }
    if ($candidate -and $stable -ge 3) { $response = $candidate; break }
    Start-Sleep -Seconds 1
  }
  if (-not $response) { throw "Timed out waiting for the visible $Provider response." }
  $currentRoot = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
  $address = Find-ByAutomationId $currentRoot 'view_1012'
  $addressValue = if ($address) {
    $address.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
  } else { $targetUrl }
  Write-Result @{
    ok = $true
    provider = $Provider
    result_text = $response
    external_thread_url = $addressValue
    window_title = $currentRoot.Current.Name
    browser_session_mode = 'existing_logged_profile'
    delivery_method = 'windows_uia_visible_keyboard'
    cookie_or_password_read = $false
    new_browser_profile_created = $false
    submission_confirmed = $submissionConfirmed
    selected_existing_ai_tab = $selectedAiTabName
    conversation_key = $ConversationKey
    conversation_reused = $conversationReused
    navigation_performed = $navigationRequired
    pricing_overlay_closed = [bool]$pricingOverlayClosed
    completed_at = (Get-Date).ToUniversalTime().ToString('o')
  }
  exit 0
} catch {
  Set-Clipboard -Value ' '
  Write-Result @{
    ok = $false
    provider = $Provider
    error = $_.Exception.Message
    browser_session_mode = 'existing_logged_profile'
    delivery_method = 'windows_uia_visible_keyboard'
    cookie_or_password_read = $false
    new_browser_profile_created = $false
    conversation_key = $ConversationKey
    completed_at = (Get-Date).ToUniversalTime().ToString('o')
  }
  exit 1
}
