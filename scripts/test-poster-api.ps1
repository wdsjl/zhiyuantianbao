param(
  [int]$UserId = 89,
  [string]$BaseUrl = 'https://api.zntb.lhyun.net'
)

$uri = "$BaseUrl/api/referral/poster?user_id=$UserId&template_key=gold"
Write-Host "请求: $uri"
try {
  $resp = Invoke-RestMethod -Uri $uri -Method Get
  Write-Host "invite_code:" $resp.invite_code
  Write-Host "qr_error:" $resp.qr_error
  Write-Host "image_base64 length:" ($(if ($resp.image_base64) { $resp.image_base64.Length } else { 0 }))
  Write-Host "poster_base64 length:" ($(if ($resp.poster_base64) { $resp.poster_base64.Length } else { 0 }))
  Write-Host "scan_reward:" ($resp.scan_reward | ConvertTo-Json -Compress)
} catch {
  Write-Host "HTTP 错误:" $_.Exception.Message -ForegroundColor Red
  if ($_.ErrorDetails.Message) {
    Write-Host $_.ErrorDetails.Message
  }
}
