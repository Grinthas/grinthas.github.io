#Requires -RunAsAdministrator
<#
    Ускоряет уже установленную Windows 10/11 на слабом ПК.
    Подходит и для облегчённого ISO, и для обычной Windows.

    Перед изменениями создаётся точка восстановления.
    Защитник, Центр обновления и Microsoft Store не отключаются.

    Ключи:
      -NoIndexing   отключить индексирование поиска (меньше нагрузка на диск,
                    но поиск по файлам станет медленнее)
#>
param([switch]$NoIndexing)

$ErrorActionPreference = 'Continue'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

function Set-Reg($path, $name, $value, $type = 'DWord') {
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name $name -Value $value -Type $type -Force
}

Step 'Точка восстановления'
try {
    Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction Stop
    Checkpoint-Computer -Description 'До optimize.ps1' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
    Write-Host '  создана'
} catch {
    Write-Warning "Не удалось создать точку восстановления: $($_.Exception.Message)"
    if ((Read-Host 'Продолжить без неё? (y/n)') -ne 'y') { exit 1 }
}

Step 'Удаление лишних приложений'
$apps = @(
    'Clipchamp.Clipchamp', 'Microsoft.549981C3F5F10', 'Microsoft.BingNews', 'Microsoft.BingSearch',
    'Microsoft.BingWeather', 'Microsoft.Copilot', 'Microsoft.GetHelp', 'Microsoft.Getstarted',
    'Microsoft.Microsoft3DViewer', 'Microsoft.MicrosoftOfficeHub', 'Microsoft.MicrosoftSolitaireCollection',
    'Microsoft.MixedReality.Portal', 'Microsoft.Office.OneNote', 'Microsoft.OutlookForWindows',
    'Microsoft.People', 'Microsoft.PowerAutomateDesktop', 'Microsoft.SkypeApp', 'Microsoft.Todos',
    'Microsoft.Wallet', 'Microsoft.Windows.DevHome', 'Microsoft.WindowsAlarms',
    'microsoft.windowscommunicationsapps', 'Microsoft.WindowsFeedbackHub', 'Microsoft.WindowsMaps',
    'Microsoft.WindowsSoundRecorder', 'Microsoft.XboxGameOverlay', 'Microsoft.XboxGamingOverlay',
    'Microsoft.XboxSpeechToTextOverlay', 'Microsoft.YourPhone', 'Microsoft.ZuneMusic', 'Microsoft.ZuneVideo',
    'MicrosoftCorporationII.MicrosoftFamily', 'MicrosoftCorporationII.QuickAssist', 'MicrosoftTeams', 'MSTeams',
    'king.com.*', 'Microsoft.BingFinance', 'Microsoft.BingSports', 'Microsoft.Messaging', 'Microsoft.MSPaint',
    'Microsoft.OneConnect', 'Microsoft.Print3D'
)
foreach ($a in $apps) {
    Get-AppxPackage -AllUsers -Name $a -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  - $($_.Name)"
        Remove-AppxPackage -Package $_.PackageFullName -AllUsers -ErrorAction SilentlyContinue
    }
    Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like $a |
        Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue | Out-Null
}

Step 'OneDrive'
Get-Process OneDrive -ErrorAction SilentlyContinue | Stop-Process -Force
foreach ($setup in "$env:SystemRoot\System32\OneDriveSetup.exe", "$env:SystemRoot\SysWOW64\OneDriveSetup.exe") {
    if (Test-Path $setup) { Start-Process $setup '/uninstall' -Wait; break }
}
Remove-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name OneDrive -ErrorAction SilentlyContinue

Step 'Телеметрия, реклама, подсказки'
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' 'AllowTelemetry' 0
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 1
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo' 'DisabledByGroupPolicy' 1
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
Set-Reg 'HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Dsh' 'AllowNewsAndInterests' 0
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Feeds' 'EnableFeeds' 0
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization' 'DODownloadMode' 0
Set-Reg 'HKCU:\Software\Policies\Microsoft\Windows\Explorer' 'DisableSearchBoxSuggestions' 1
$cdm = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
foreach ($n in 'ContentDeliveryAllowed', 'OemPreInstalledAppsEnabled', 'PreInstalledAppsEnabled',
               'SilentInstalledAppsEnabled', 'SoftLandingEnabled', 'SystemPaneSuggestionsEnabled',
               'SubscribedContent-310093Enabled', 'SubscribedContent-338388Enabled',
               'SubscribedContent-338389Enabled', 'SubscribedContent-338393Enabled',
               'SubscribedContent-353694Enabled', 'SubscribedContent-353696Enabled') {
    Set-Reg $cdm $n 0
}

foreach ($svc in 'DiagTrack', 'dmwappushservice', 'MapsBroker', 'RetailDemo', 'WerSvc') {
    if (Get-Service $svc -ErrorAction SilentlyContinue) {
        Stop-Service $svc -Force -ErrorAction SilentlyContinue
        Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Host "  служба $svc отключена"
    }
}
foreach ($t in '\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser',
               '\Microsoft\Windows\Application Experience\ProgramDataUpdater',
               '\Microsoft\Windows\Customer Experience Improvement Program\Consolidator',
               '\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip',
               '\Microsoft\Windows\Feedback\Siuf\DmClient',
               '\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload') {
    $path = $t.Substring(0, $t.LastIndexOf('\') + 1)
    $name = $t.Substring($t.LastIndexOf('\') + 1)
    Disable-ScheduledTask -TaskPath $path -TaskName $name -ErrorAction SilentlyContinue | Out-Null
}

Step 'Фоновые приложения и Game Bar'
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy' 'LetAppsRunInBackground' 2
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled' 1
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\GameDVR' 'AllowGameDVR' 0
Set-Reg 'HKCU:\System\GameConfigStore' 'GameDVR_Enabled' 0
Set-Reg 'HKCU:\Software\Microsoft\GameBar' 'UseNexusForGameBarEnabled' 0

Step 'Визуальные эффекты: максимальное быстродействие, сглаживание шрифтов оставлено'
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting' 3
Set-Reg 'HKCU:\Control Panel\Desktop' 'UserPreferencesMask' ([byte[]](0x90, 0x12, 0x03, 0x80, 0x10, 0x00, 0x00, 0x00)) 'Binary'
Set-Reg 'HKCU:\Control Panel\Desktop' 'FontSmoothing' '2' 'String'
Set-Reg 'HKCU:\Control Panel\Desktop' 'MenuShowDelay' '50' 'String'
Set-Reg 'HKCU:\Control Panel\Desktop\WindowMetrics' 'MinAnimate' '0' 'String'
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarAnimations' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ListviewAlphaSelect' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ListviewShadow' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarDa' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowCopilotButton' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' 'EnableTransparency' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\DWM' 'EnableAeroPeek' 0

Step 'Панель задач Windows 10'
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Search' 'SearchboxTaskbarMode' 1
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowCortanaButton' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowTaskViewButton' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\People' 'PeopleBand' 0
Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Feeds' 'ShellFeedsTaskbarViewMode' 2
Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search' 'AllowCortana' 0
Set-Reg 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer' 'HideSCAMeetNow' 1

Step 'Электропитание'
$isLaptop = [bool](Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
if ($isLaptop) {
    Write-Host '  ноутбук: схема питания не меняется, чтобы не сажать батарею'
} else {
    & powercfg.exe /setactive SCHEME_MIN
    Write-Host '  включена схема «Высокая производительность»'
}
& powercfg.exe /hibernate off
Write-Host '  гибернация отключена (освобождает место на диске, равное объёму ОЗУ)'

Step 'Диск'
$sysDisk = Get-Partition -DriveLetter $env:SystemDrive[0] | Get-Disk | Get-PhysicalDisk -ErrorAction SilentlyContinue
if ($sysDisk.MediaType -eq 'SSD') {
    Write-Host '  SSD: SysMain (SuperFetch) не нужен, отключаю'
    Stop-Service SysMain -Force -ErrorAction SilentlyContinue
    Set-Service SysMain -StartupType Disabled -ErrorAction SilentlyContinue
} else {
    Write-Host '  жёсткий диск (HDD): SysMain оставлен, он ускоряет запуск программ с HDD'
}
if ($NoIndexing) {
    Stop-Service WSearch -Force -ErrorAction SilentlyContinue
    Set-Service WSearch -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host '  индексирование поиска отключено'
}

Step 'Очистка временных файлов'
foreach ($dir in $env:TEMP, "$env:SystemRoot\Temp") {
    Get-ChildItem $dir -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
& dism.exe /Online /Cleanup-Image /StartComponentCleanup | Out-Null

Write-Host "`nГотово. Перезагрузите компьютер." -ForegroundColor Green
Write-Host 'Откатить всё: Панель управления -> Восстановление -> Запуск восстановления системы.'
