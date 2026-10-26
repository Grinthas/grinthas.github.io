#Requires -RunAsAdministrator
<#
    Собирает облегчённый ISO Windows 10/11 для слабых ПК из ОФИЦИАЛЬНОГО образа Microsoft.

    Что делает:
      - оставляет в образе одну выбранную редакцию (Home, Pro и т. д.);
      - удаляет предустановленный мусор (новости, погода, Xbox Game Bar, Teams, Clipchamp, Copilot...);
      - отключает рекламу, «рекомендуемые» приложения, телеметрию (насколько позволяет редакция);
      - не даёт установиться OneDrive;
      - снимает требования Windows 11 к TPM, Secure Boot, процессору и ОЗУ;
      - позволяет создать локальную учётную запись без интернета и аккаунта Microsoft;
      - чистит хранилище компонентов и сжимает образ.

    Защитник Windows, Центр обновления, Microsoft Store, калькулятор, блокнот,
    фотографии и драйверы НЕ трогаются: система остаётся безопасной и обновляемой.

    Запуск (PowerShell от имени администратора):
      powershell -ExecutionPolicy Bypass -File .\build-lite-iso.ps1 -IsoPath D:\Win11_Russian_x64.iso
#>
param(
    [string]$IsoPath,
    [string]$OutIso = (Join-Path $PSScriptRoot 'Windows-Lite.iso'),
    [int]$Index = 0,
    [string]$WorkDir = 'C:\winlite'
)

$ErrorActionPreference = 'Stop'

# Приложения, которые удаляются из образа (по началу имени пакета).
$RemoveApps = @(
    'Clipchamp.Clipchamp'
    'Microsoft.549981C3F5F10'            # Cortana
    'Microsoft.BingNews'
    'Microsoft.BingSearch'
    'Microsoft.BingWeather'
    'Microsoft.Copilot'
    'Microsoft.GetHelp'
    'Microsoft.Getstarted'
    'Microsoft.Microsoft3DViewer'
    'Microsoft.MicrosoftOfficeHub'
    'Microsoft.MicrosoftSolitaireCollection'
    'Microsoft.MixedReality.Portal'
    'Microsoft.Office.OneNote'
    'Microsoft.OutlookForWindows'
    'Microsoft.People'
    'Microsoft.PowerAutomateDesktop'
    'Microsoft.SkypeApp'
    'Microsoft.Todos'
    'Microsoft.Wallet'
    'Microsoft.Windows.DevHome'
    'Microsoft.WindowsAlarms'
    'microsoft.windowscommunicationsapps' # Почта и календарь
    'Microsoft.WindowsFeedbackHub'
    'Microsoft.WindowsMaps'
    'Microsoft.WindowsSoundRecorder'
    'Microsoft.XboxGameOverlay'
    'Microsoft.XboxGamingOverlay'          # Game Bar
    'Microsoft.XboxSpeechToTextOverlay'
    'Microsoft.YourPhone'
    'Microsoft.ZuneMusic'
    'Microsoft.ZuneVideo'
    'MicrosoftCorporationII.MicrosoftFamily'
    'MicrosoftCorporationII.QuickAssist'
    'MicrosoftTeams'
    'MSTeams'
    # Windows 10
    'king.com.'                            # Candy Crush и прочие игры King
    'Microsoft.BingFinance'
    'Microsoft.BingSports'
    'Microsoft.Messaging'
    'Microsoft.MSPaint'                    # Paint 3D (обычный Paint остаётся)
    'Microsoft.OneConnect'
    'Microsoft.Print3D'
)

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

function Set-Reg($key, $name, $value, $type = 'REG_DWORD') {
    & reg.exe add $key /v $name /t $type /d $value /f | Out-Null
}

function Unload-Hives {
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    foreach ($h in 'zSOFTWARE', 'zSYSTEM', 'zDEFAULT', 'zNTUSER') {
        & cmd.exe /c "reg unload HKLM\$h >nul 2>&1"
    }
}

# --- Исходный образ ---------------------------------------------------------
if (-not $IsoPath) {
    Write-Host 'Скачайте официальный ISO: https://www.microsoft.com/ru-ru/software-download/windows11'
    Write-Host '(или windows10 вместо windows11 в адресе)'
    $IsoPath = (Read-Host 'Путь к ISO-файлу').Trim('"')
}
if (-not (Test-Path $IsoPath)) { throw "Файл не найден: $IsoPath" }
$IsoPath = (Resolve-Path $IsoPath).Path

$isoDir   = Join-Path $WorkDir 'iso'
$mountDir = Join-Path $WorkDir 'mount'

Step 'Подготовка рабочей папки'
if (Test-Path $mountDir) {
    Unload-Hives
    & cmd.exe /c "dism /Unmount-Image /MountDir:`"$mountDir`" /Discard >nul 2>&1"
}
if (Test-Path $WorkDir) { Remove-Item $WorkDir -Recurse -Force }
New-Item -ItemType Directory -Path $isoDir, $mountDir | Out-Null

Step 'Копирование файлов из ISO'
$disk = Mount-DiskImage -ImagePath $IsoPath -PassThru
try {
    $letter = ($disk | Get-Volume).DriveLetter
    Copy-Item "${letter}:\*" $isoDir -Recurse -Force
} finally {
    Dismount-DiskImage -ImagePath $IsoPath | Out-Null
}
Get-ChildItem $isoDir -Recurse -File | ForEach-Object { $_.Attributes = 'Normal' }

$wim = Join-Path $isoDir 'sources\install.wim'
$esd = Join-Path $isoDir 'sources\install.esd'
$src = if (Test-Path $wim) { $wim } elseif (Test-Path $esd) { $esd } else { throw 'В ISO нет sources\install.wim или install.esd' }

# --- Выбор редакции ---------------------------------------------------------
$images = Get-WindowsImage -ImagePath $src
if ($Index -eq 0) {
    $images | ForEach-Object { Write-Host ('  {0,2}. {1}' -f $_.ImageIndex, $_.ImageName) }
    $Index = [int](Read-Host 'Номер редакции (обычно Pro или Home)')
}
$edition = ($images | Where-Object ImageIndex -eq $Index).ImageName
if (-not $edition) { throw "Нет редакции с номером $Index" }
Write-Host "Выбрана: $edition"

# Оставляем только одну редакцию: образ меньше, установка без лишних вопросов.
Step 'Извлечение выбранной редакции'
$single = Join-Path $WorkDir 'single.wim'
& dism.exe /Export-Image /SourceImageFile:$src /SourceIndex:$Index /DestinationImageFile:$single /Compress:max /CheckIntegrity
if ($LASTEXITCODE) { throw 'Не удалось извлечь редакцию' }
Remove-Item $src -Force
$Index = 1

# --- Правка install.wim -----------------------------------------------------
Step 'Подключение образа (несколько минут)'
Mount-WindowsImage -ImagePath $single -Index 1 -Path $mountDir | Out-Null

try {
    Step 'Удаление предустановленных приложений'
    $pattern = '^(' + (($RemoveApps | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')'
    Get-AppxProvisionedPackage -Path $mountDir |
        Where-Object DisplayName -match $pattern |
        ForEach-Object {
            Write-Host "  - $($_.DisplayName)"
            Remove-AppxProvisionedPackage -Path $mountDir -PackageName $_.PackageName | Out-Null
        }

    Step 'Настройка реестра образа'
    & reg.exe load HKLM\zSOFTWARE "$mountDir\Windows\System32\config\SOFTWARE" | Out-Null
    & reg.exe load HKLM\zSYSTEM   "$mountDir\Windows\System32\config\SYSTEM"   | Out-Null
    & reg.exe load HKLM\zDEFAULT  "$mountDir\Windows\System32\config\default"  | Out-Null
    & reg.exe load HKLM\zNTUSER   "$mountDir\Users\Default\ntuser.dat"         | Out-Null

    # Обход требований Windows 11 (TPM, Secure Boot, CPU, RAM, диск)
    foreach ($n in 'BypassTPMCheck', 'BypassSecureBootCheck', 'BypassCPUCheck', 'BypassRAMCheck', 'BypassStorageCheck') {
        Set-Reg 'HKLM\zSYSTEM\Setup\LabConfig' $n 1
    }
    Set-Reg 'HKLM\zSYSTEM\Setup\MoSetup' 'AllowUpgradesWithUnsupportedTPMOrCPU' 1
    foreach ($h in 'zDEFAULT', 'zNTUSER') {
        Set-Reg "HKLM\$h\Control Panel\UnsupportedHardwareNotificationCache" 'SV1' 0
        Set-Reg "HKLM\$h\Control Panel\UnsupportedHardwareNotificationCache" 'SV2' 0
    }

    # Локальная учётная запись без интернета
    Set-Reg 'HKLM\zSOFTWARE\Microsoft\Windows\CurrentVersion\OOBE' 'BypassNRO' 1

    # Телеметрия, реклама, «рекомендации»
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\DataCollection' 'AllowTelemetry' 0
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 1
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableConsumerAccountStateContent' 1
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableCloudOptimizedContent' 1
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo' 'DisabledByGroupPolicy' 1
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\Windows Chat' 'ChatIcon' 3
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Dsh' 'AllowNewsAndInterests' 0
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\Windows Feeds' 'EnableFeeds' 0
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\GameDVR' 'AllowGameDVR' 0
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization' 'DODownloadMode' 0
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\AppPrivacy' 'LetAppsRunInBackground' 2

    # Резерв ~7 ГБ под обновления не нужен на маленьком диске
    Set-Reg 'HKLM\zSOFTWARE\Microsoft\Windows\CurrentVersion\ReserveManager' 'ShippedWithReserves' 0

    # Настройки нового пользователя
    $cdm = 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
    foreach ($n in 'ContentDeliveryAllowed', 'FeatureManagementEnabled', 'OemPreInstalledAppsEnabled',
                   'PreInstalledAppsEnabled', 'PreInstalledAppsEverEnabled', 'SilentInstalledAppsEnabled',
                   'SoftLandingEnabled', 'SystemPaneSuggestionsEnabled', 'SubscribedContentEnabled',
                   'SubscribedContent-310093Enabled', 'SubscribedContent-338388Enabled',
                   'SubscribedContent-338389Enabled', 'SubscribedContent-338393Enabled',
                   'SubscribedContent-353694Enabled', 'SubscribedContent-353696Enabled') {
        Set-Reg $cdm $n 0
    }
    Set-Reg 'HKLM\zNTUSER\Software\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
    Set-Reg 'HKLM\zNTUSER\Software\Policies\Microsoft\Windows\Explorer' 'DisableSearchBoxSuggestions' 1
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarDa' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarMn' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowCopilotButton' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'HideFileExt' 0
    # Панель задач Windows 10: значок поиска вместо поля, без Кортаны, «Людей», Meet Now и представления задач
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Search' 'SearchboxTaskbarMode' 1
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowCortanaButton' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowTaskViewButton' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\People' 'PeopleBand' 0
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\Feeds' 'ShellFeedsTaskbarViewMode' 2
    Set-Reg 'HKLM\zSOFTWARE\Policies\Microsoft\Windows\Windows Search' 'AllowCortana' 0
    Set-Reg 'HKLM\zSOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer' 'HideSCAMeetNow' 1
    Set-Reg 'HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications' 'GlobalUserDisabled' 1
    Set-Reg 'HKLM\zNTUSER\System\GameConfigStore' 'GameDVR_Enabled' 0

    # OneDrive не ставится при первом входе
    foreach ($k in 'Run', 'RunOnce') {
        & cmd.exe /c "reg delete HKLM\zNTUSER\Software\Microsoft\Windows\CurrentVersion\$k /v OneDriveSetup /f >nul 2>&1"
    }
}
finally {
    Unload-Hives
}

Step 'Файл ответов: локальная учётка, без лишних экранов'
$unattend = Join-Path $PSScriptRoot 'autounattend.xml'
Copy-Item $unattend (Join-Path $isoDir 'autounattend.xml') -Force
New-Item -ItemType Directory -Path "$mountDir\Windows\System32\Sysprep" -Force | Out-Null
Copy-Item $unattend "$mountDir\Windows\System32\Sysprep\unattend.xml" -Force

Step 'Очистка хранилища компонентов (долго, 10–30 минут)'
& dism.exe /Image:$mountDir /Cleanup-Image /StartComponentCleanup /ResetBase
if ($LASTEXITCODE) { Write-Warning 'Очистка завершилась с ошибкой, продолжаем без неё' }

Step 'Сохранение образа'
Dismount-WindowsImage -Path $mountDir -Save | Out-Null

Step 'Сжатие образа'
& dism.exe /Export-Image /SourceImageFile:$single /SourceIndex:1 /DestinationImageFile:$wim /Compress:max /CheckIntegrity
if ($LASTEXITCODE) { throw 'Не удалось сжать образ' }
Remove-Item $single -Force

# --- boot.wim: обход проверок в самом установщике ---------------------------
Step 'Правка установщика (boot.wim)'
$boot = Join-Path $isoDir 'sources\boot.wim'
Mount-WindowsImage -ImagePath $boot -Index 2 -Path $mountDir | Out-Null
try {
    & reg.exe load HKLM\zSYSTEM "$mountDir\Windows\System32\config\SYSTEM" | Out-Null
    foreach ($n in 'BypassTPMCheck', 'BypassSecureBootCheck', 'BypassCPUCheck', 'BypassRAMCheck', 'BypassStorageCheck') {
        Set-Reg 'HKLM\zSYSTEM\Setup\LabConfig' $n 1
    }
} finally {
    Unload-Hives
}
Dismount-WindowsImage -Path $mountDir -Save | Out-Null

# --- Сборка ISO -------------------------------------------------------------
Step 'Сборка ISO'
$oscdimg = 'C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe'
if (-not (Test-Path $oscdimg)) {
    $oscdimg = Join-Path $WorkDir 'oscdimg.exe'
    Write-Host 'Скачиваю oscdimg.exe с сервера Microsoft...'
    Invoke-WebRequest 'https://msdl.microsoft.com/download/symbols/oscdimg.exe/3D44737265000/oscdimg.exe' -OutFile $oscdimg -UseBasicParsing
}
$bios = Join-Path $isoDir 'boot\etfsboot.com'
$uefi = Join-Path $isoDir 'efi\microsoft\boot\efisys.bin'
& $oscdimg -m -o -u2 -udfver102 "-bootdata:2#p0,e,b$bios#pEF,e,b$uefi" $isoDir $OutIso
if ($LASTEXITCODE) { throw 'oscdimg не смог собрать ISO' }

Remove-Item $WorkDir -Recurse -Force
Write-Host "`nГотово: $OutIso" -ForegroundColor Green
Write-Host 'Запишите его на флешку через Rufus (https://rufus.ie) и установите как обычную Windows.'
Write-Host 'После установки запустите optimize.cmd из этой же папки.'
