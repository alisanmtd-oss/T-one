function Test-TOneSheinSurface {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [object]$Page,
    [Parameter(Mandatory = $true)]
    [ValidateSet("home", "inventory", "orders", "ads", "coupons")]
    [string]$Surface
  )

  $url = [string]$Page.url
  if ([string]$Page.type -ne "page" -or
      $url -notmatch "^https://sellerhub\.shein\.com" -or
      $url -match "(?i)(login|signin|sso|identity|verification)") {
    return $false
  }
  if ($Surface -eq "inventory") {
    return [bool]($url -match "(?i)#/(?:spmp/commdities|spmp/commodities|spmc/commodities)/list(?:[/?]|$)")
  }
  if ($Surface -eq "orders") {
    return [bool]($url -match "(?i)#/gsp/order-management/list(?:[/?]|$)")
  }
  if ($Surface -eq "home") {
    return [bool]($url -match "^https://sellerhub\.shein\.com/?(?:#/?(?:home)?)?$")
  }
  return $false
}

function Select-TOneSheinSellerPage {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyCollection()]
    [object[]]$Pages,
    [Parameter(Mandatory = $true)]
    [ValidateSet("home", "inventory", "orders", "ads", "coupons")]
    [string]$Surface
  )

  $flatPages = @()
  foreach ($candidate in $Pages) {
    if ($candidate -is [System.Array]) {
      foreach ($nestedCandidate in $candidate) { $flatPages += $nestedCandidate }
    } else {
      $flatPages += $candidate
    }
  }

  $sellerPages = @(
    $flatPages | Where-Object {
      $url = [string]$_.url
      [string]$_.type -eq "page" -and
        $url -match "^https://sellerhub\.shein\.com" -and
        $url -notmatch "(?i)(login|signin|sso|identity|verification)"
    }
  )
  if ($sellerPages.Count -eq 0) { return $null }

  if ($Surface -eq "inventory") {
    $inventoryPages = @(
      $sellerPages | Where-Object {
        Test-TOneSheinSurface -Page $_ -Surface "inventory"
      }
    )
    if ($inventoryPages.Count -gt 0) { return $inventoryPages[0] }
    return $null
  }

  if ($Surface -eq "orders") {
    $orderPages = @(
      $sellerPages | Where-Object {
        Test-TOneSheinSurface -Page $_ -Surface "orders"
      }
    )
    if ($orderPages.Count -gt 0) { return $orderPages[0] }
    return $null
  }

  $homePages = @(
    $sellerPages | Where-Object {
      Test-TOneSheinSurface -Page $_ -Surface "home"
    }
  )
  if ($homePages.Count -gt 0) { return $homePages[0] }
  return $null
}

Export-ModuleMember -Function Select-TOneSheinSellerPage, Test-TOneSheinSurface
