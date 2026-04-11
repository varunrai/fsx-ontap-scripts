#Requires -Modules NetApp.ONTAP
# ─────────────────────────────────────────────────────────────────────────────
# MODULE NOTE: This script requires the NetApp.ONTAP PowerShell Toolkit
# (formerly named "DataONTAP" — renamed as of toolkit version 9.11.1).
#
# To install the latest version from PowerShell Gallery:
#     Install-Module -Name NetApp.ONTAP
#
# If you previously had the old DataONTAP module and need backward compatibility,
# run these two commands once after installing NetApp.ONTAP (as Administrator):
#     New-Item -ItemType SymbolicLink `
#         -Path   "C:\Program Files\WindowsPowerShell\Modules\DataONTAP" `
#         -Target "C:\Program Files\WindowsPowerShell\Modules\NetApp.ONTAP"
#     New-Item -ItemType SymbolicLink `
#         -Path   "C:\Program Files\WindowsPowerShell\Modules\DataONTAP\9.16.1.2501\DataONTAP.psd1" `
#         -Target "C:\Program Files\WindowsPowerShell\Modules\NetApp.ONTAP\9.16.1.2501\NetApp.ONTAP.psd1"
# ─────────────────────────────────────────────────────────────────────────────
<#
.SYNOPSIS
    Provisions a LUN (block storage unit) on Amazon FSx for NetApp ONTAP and maps it
    to a Windows host via iSCSI — the equivalent of presenting a new virtual disk to
    your server.

.DESCRIPTION
    This script automates five steps that are normally run one-by-one in an SSH session:
      1. Connect to your FSx file system
      2. Create a LUN (the block storage container your Windows host will use as a disk)
      3. Verify the LUN was created correctly
      4. Create an igroup (a named list of servers allowed to access the LUN)
      5. Map the LUN to that igroup so the host can mount it

    Think of it like this:
      LUN      = a virtual hard drive living inside your NetApp storage
      igroup   = a VIP guest list — only servers on the list can see the drive
      Mapping  = handing the keys to the servers on the guest list

.PARAMETER ManagementIP
    The IP address of your FSx file system's management endpoint.
    Found in the AWS Console → FSx → your file system → "Management endpoint".

.PARAMETER SVMName
    The Storage Virtual Machine (SVM) name — a logical container inside FSx
    that owns your volumes and LUNs. Think of it as a "tenant" on the storage.

.PARAMETER VolumeName
    The FlexVol volume that will hold the LUN. The volume must already exist.

.PARAMETER LunName
    A short, descriptive name for the LUN itself (e.g. "sqldata", "appvol01").

.PARAMETER LunSizeGB
    How large the LUN should be, in gigabytes (e.g. 100 for a 100 GB disk).

.PARAMETER IgroupName
    A name for the initiator group (igroup). Convention: use the hostname or app name
    (e.g. "win-sql01-ig" or "webfarm-ig").

.PARAMETER HostInitiatorName
    The iSCSI Qualified Name (IQN) of the Windows host's iSCSI initiator.
    On Windows: open iSCSI Initiator → Configuration tab → "Initiator Name".
    Format: iqn.1991-05.com.microsoft:your-hostname

.PARAMETER LunId
    The LUN ID number (0–4095). This is the "slot number" the host uses to
    identify the disk. Use 0 if you only have one LUN per igroup; increment for more.

.EXAMPLE
    .\New-OntapLunProvisioning.ps1 `
        -ManagementIP     "198.51.100.25" `
        -SVMName          "svm_prod" `
        -VolumeName       "vol_sqldata" `
        -LunName          "lun_sqldb01" `
        -LunSizeGB        200 `
        -IgroupName       "ig_sqlserver01" `
        -HostInitiatorName "iqn.1991-05.com.microsoft:sql-server-01" `
        -LunId            0

.NOTES
    Prerequisites
    -------------
    • NetApp.ONTAP PowerShell Toolkit (v9.11.1 or later) installed:
          Install-Module -Name NetApp.ONTAP
      ⚠ The old module was named "DataONTAP" — it has been renamed to "NetApp.ONTAP".
        If you have the old module, uninstall it first:
          Uninstall-Module -Name DataONTAP
        then install the new one.
    • PowerShell 5.1 or later (PowerShell 7+ recommended for cross-platform use)
    • Network access from this machine to the FSx management endpoint (port 443)
    • fsxadmin credentials (or an account with lun-create / igroup-create privileges)
    • The target volume ($VolumeName) must already exist and have enough free space

    API Mode — REST vs ZAPI (ONTAPI)
    ---------------------------------
    • FSx for NetApp ONTAP runs ONTAP 9.12 or later.
    • From toolkit version 9.11.1 onwards, cmdlets automatically use the REST API
      (not the older ZAPI/ONTAPI protocol) when connecting to ONTAP 9.10.1 or later.
      This script relies on that default — no extra flags needed.
    • ZAPI is being phased out by NetApp. Do NOT use the -ONTAPI switch for new scripts
      targeting FSx. All Nc-prefixed cmdlets in this script are REST-backed on FSx.

    AWS FSx Specifics
    -----------------
    • This script connects over HTTPS (port 443) to the FSx management endpoint.
    • Space allocation (-SpaceAllocationEnabled $true) lets the volume reclaim space
      when the host deletes files inside the LUN — always recommended on FSx.
    • OsType 'windows' tells ONTAP to use the correct disk geometry and alignment
      for Windows hosts. Use 'linux' or 'vmware' for other platforms.
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory, HelpMessage = "FSx management endpoint IP address")]
    [ValidatePattern('^\d{1,3}(\.\d{1,3}){3}$')]
    [string] $ManagementIP,

    [Parameter(Mandatory, HelpMessage = "Storage Virtual Machine (SVM) name")]
    [ValidateNotNullOrEmpty()]
    [string] $SVMName,

    [Parameter(Mandatory, HelpMessage = "Existing FlexVol volume name that will host the LUN")]
    [ValidateNotNullOrEmpty()]
    [string] $VolumeName,

    [Parameter(Mandatory, HelpMessage = "Short name for the new LUN (no spaces, no slashes)")]
    [ValidatePattern('^[A-Za-z0-9_\-]+$')]
    [string] $LunName,

    [Parameter(Mandatory, HelpMessage = "LUN size in gigabytes")]
    [ValidateRange(1, 65536)]
    [int] $LunSizeGB,

    [Parameter(Mandatory, HelpMessage = "igroup name (use host or application name as convention)")]
    [ValidatePattern('^[A-Za-z0-9_\-]+$')]
    [string] $IgroupName,

    [Parameter(Mandatory, HelpMessage = "Windows host iSCSI IQN (from iSCSI Initiator → Configuration)")]
    [ValidatePattern('^iqn\.\d{4}-\d{2}\.[a-z0-9\.\-]+:[a-z0-9\.\-]+$')]
    [string] $HostInitiatorName,

    [Parameter(Mandatory = $false, HelpMessage = "LUN ID (0–4095); use 0 if this is the only LUN in the igroup")]
    [ValidateRange(0, 4095)]
    [int] $LunId = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ──────────────────────────────────────────────────────────────
# MODULE VERSION GUARD
# Ensure the correct module (NetApp.ONTAP, not the legacy DataONTAP) is loaded.
# The minimum version is 9.11.1 — earlier versions do not support REST API mode.
# ──────────────────────────────────────────────────────────────
$requiredModule  = 'NetApp.ONTAP'
$minimumVersion  = [Version]'9.11.1'

$loadedModule = Get-Module -Name $requiredModule -ErrorAction SilentlyContinue
if (-not $loadedModule) {
    # Try to import it (it may be installed but not yet imported in this session)
    try {
        Import-Module -Name $requiredModule -MinimumVersion $minimumVersion -ErrorAction Stop
        $loadedModule = Get-Module -Name $requiredModule
    }
    catch {
        Write-Error @"
The '$requiredModule' module is not installed or is below the minimum version ($minimumVersion).

To install it, run (in an elevated PowerShell window):
    Install-Module -Name NetApp.ONTAP

If you have the old 'DataONTAP' module installed, remove it first:
    Uninstall-Module -Name DataONTAP

Then re-run this script.
"@
        exit 1
    }
}

$moduleVersion = $loadedModule.Version
if ($moduleVersion -lt $minimumVersion) {
    Write-Error "NetApp.ONTAP module version $moduleVersion is below the required minimum ($minimumVersion). Run: Update-Module -Name NetApp.ONTAP"
    exit 1
}

Write-Host "  ✔  Module: $requiredModule v$moduleVersion loaded (REST API mode active for ONTAP 9.10.1+)" -ForegroundColor DarkGreen

# ──────────────────────────────────────────────────────────────
# HELPER: Write a clearly formatted section header to the console
# ──────────────────────────────────────────────────────────────
function Write-Step {
    param([int]$Step, [string]$Title)
    Write-Host "`n━━━ Step $Step of 5 — $Title ━━━" -ForegroundColor Cyan
}

function Write-OK   { param([string]$Msg) Write-Host "  ✔  $Msg" -ForegroundColor Green  }
function Write-Info { param([string]$Msg) Write-Host "  ℹ  $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "  ✘  $Msg" -ForegroundColor Red    }

# ──────────────────────────────────────────────────────────────
# DERIVED VARIABLES
# ──────────────────────────────────────────────────────────────
# The full path where the LUN lives inside ONTAP.
# ONTAP uses Unix-style paths:  /vol/<volume>/<lun>
$LunPath   = "/vol/$VolumeName/$LunName"

# Convert GB → bytes (ONTAP expects sizes in bytes)
$LunSizeBytes = [int64]$LunSizeGB * 1GB

Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host   "║   NetApp ONTAP LUN Provisioning — FSx for NetApp ONTAP  ║" -ForegroundColor Magenta
Write-Host   "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host "`nConfiguration summary:"
Write-Host "  FSx Management IP  : $ManagementIP"
Write-Host "  SVM                : $SVMName"
Write-Host "  Volume             : $VolumeName"
Write-Host "  LUN path           : $LunPath"
Write-Host "  LUN size           : $LunSizeGB GB  ($LunSizeBytes bytes)"
Write-Host "  igroup name        : $IgroupName"
Write-Host "  Host IQN           : $HostInitiatorName"
Write-Host "  LUN ID             : $LunId"


# ══════════════════════════════════════════════════════════════
# STEP 1 — Connect to the FSx file system
# ══════════════════════════════════════════════════════════════
Write-Step 1 "Connect to FSx for NetApp ONTAP"
Write-Info "Enter your fsxadmin password when prompted."
Write-Info "(This is the management password you set when creating the FSx file system.)"

try {
    # Connect-NcController opens an HTTPS (TLS) management session to ONTAP.
    #
    # KEY BEHAVIOUR in NetApp.ONTAP toolkit (v9.11.1+):
    #   • On ONTAP 9.10.1 and later (which covers all FSx versions), the toolkit
    #     automatically uses the REST API — no extra switch is needed.
    #   • On older ONTAP versions it would fall back to ZAPI (ONTAPI).
    #   • Do NOT add -ONTAPI here — that forces the deprecated protocol and will
    #     stop working in a future ONTAP release.
    #
    # -HTTPS : Encrypts all traffic over port 443. Always use this.
    # -HTTP  : NOT recommended; credentials travel in plain text.
    $controller = Connect-NcController `
        -Name       $ManagementIP `
        -HTTPS `
        -Credential (Get-Credential -UserName "fsxadmin" -Message "Enter FSx admin password for $ManagementIP")

    Write-OK "Connected to: $($controller.Name)  |  ONTAP version: $($controller.OntapVersion)"
}
catch {
    Write-Fail "Could not connect to $ManagementIP. Verify:"
    Write-Fail "  • The management endpoint IP is correct"
    Write-Fail "  • Port 443 is reachable from this machine"
    Write-Fail "  • Credentials are correct"
    throw
}


# ══════════════════════════════════════════════════════════════
# PRE-FLIGHT CHECKS  (run before making any changes)
# ══════════════════════════════════════════════════════════════
Write-Host "`n━━━ Pre-flight checks ━━━" -ForegroundColor Cyan

# 1. SVM exists?
Write-Info "Checking SVM '$SVMName' exists..."
$svm = Get-NcVserver -Name $SVMName -ErrorAction SilentlyContinue
if (-not $svm) {
    Write-Fail "SVM '$SVMName' not found. Run 'Get-NcVserver' to list available SVMs."
    throw "SVM not found: $SVMName"
}
Write-OK "SVM '$SVMName' found (type: $($svm.VserverType))"

# 2. Volume exists inside the SVM?
Write-Info "Checking volume '$VolumeName' exists in SVM '$SVMName'..."
$volume = Get-NcVol -VserverContext $SVMName -Name $VolumeName -ErrorAction SilentlyContinue
if (-not $volume) {
    Write-Fail "Volume '$VolumeName' not found under SVM '$SVMName'."
    Write-Fail "Run 'Get-NcVol -VserverContext $SVMName' to list volumes."
    throw "Volume not found: $VolumeName"
}

# 3. Does the volume have enough free space?
#    Under the NetApp.ONTAP REST-backed toolkit the volume size data lives in
#    VolumeSpaceAttributes. We read it safely with a null-guard; if the property
#    is absent (can happen on some REST responses) we fall back to a direct
#    Get-NcVol with explicit -Attributes to request the space fields.
$volSpaceAttrs = $volume.VolumeSpaceAttributes
$volFreeBytes  = $null

if ($volSpaceAttrs -and $volSpaceAttrs.SizeAvailable) {
    $volFreeBytes = $volSpaceAttrs.SizeAvailable
} else {
    # Explicit attribute request — ensures the REST response includes space data
    $volumeWithSpace = Get-NcVol -VserverContext $SVMName -Name $VolumeName `
        -Attributes (Get-NcVol -Template | ForEach-Object {
            $_.VolumeSpaceAttributes = New-Object DataONTAP.C.Types.Volume.VolumeSpaceAttributes
            $_
        }) -ErrorAction SilentlyContinue
    $volFreeBytes = $volumeWithSpace.VolumeSpaceAttributes.SizeAvailable
}

if (-not $volFreeBytes) {
    # Last resort: compare TotalSize - SizeUsed
    $volFreeBytes = $volume.VolumeSpaceAttributes.Size - $volume.VolumeSpaceAttributes.SizeUsed
}

$volFreeGB = [math]::Round($volFreeBytes / 1GB, 2)
Write-Info "Volume free space: $volFreeGB GB available"
if ($volFreeBytes -lt $LunSizeBytes) {
    Write-Fail "Not enough free space. You need $LunSizeGB GB but only $volFreeGB GB is available."
    throw "Insufficient volume space"
}
Write-OK "Volume has sufficient free space ($volFreeGB GB available)"

# 4. LUN path already exists?
Write-Info "Checking LUN path '$LunPath' is not already in use..."
$existingLun = Get-NcLun -VserverContext $SVMName -Path $LunPath -ErrorAction SilentlyContinue
if ($existingLun) {
    Write-Fail "A LUN already exists at '$LunPath'. Choose a different LUN name."
    throw "LUN path already exists: $LunPath"
}
Write-OK "LUN path '$LunPath' is available"

# 5. igroup name already exists?
Write-Info "Checking igroup name '$IgroupName'..."
$existingIgroup = Get-NcIgroup -VserverContext $SVMName -Name $IgroupName -ErrorAction SilentlyContinue
if ($existingIgroup) {
    Write-Info "igroup '$IgroupName' already exists — will map to it (not re-created)."
    $igroupExists = $true
} else {
    Write-OK "igroup name '$IgroupName' is available"
    $igroupExists = $false
}


# ══════════════════════════════════════════════════════════════
# STEP 2 — Create the LUN
# ══════════════════════════════════════════════════════════════
Write-Step 2 "Create LUN"
Write-Info "Creating a $LunSizeGB GB Windows LUN at '$LunPath'..."
<#
  What each parameter means:
    -Path             : Full ONTAP path /vol/<volume>/<lun>
    -Size             : Size in bytes (the toolkit converts this correctly over REST)
    -OsType windows   : Configures correct block geometry/alignment for Windows hosts.
                        'windows' covers Windows Server 2008 R2 and later (all modern
                        Windows versions). Use 'linux', 'vmware', or 'hyper_v' for others.
                        NOTE: 'windows_2008' is a legacy alias — 'windows' is preferred
                        in the NetApp.ONTAP module targeting ONTAP 9.x.
    -SpaceAllocationEnabled $true
                      : When the Windows host deletes data, ONTAP reclaims that
                        space in the volume (thin provisioning / SCSI UNMAP).
                        Strongly recommended on FSx to prevent wasted capacity.

  REST API note: In NetApp.ONTAP v9.11.1+, New-NcLun calls POST /api/storage/luns
  on ONTAP 9.10.1+ instead of the deprecated ZAPI lun-create. The parameter names
  in PowerShell remain identical — only the underlying wire protocol changed.
#>
if ($PSCmdlet.ShouldProcess($LunPath, "Create LUN ($LunSizeGB GB, Windows)")) {
    try {
        New-NcLun `
            -VserverContext         $SVMName `
            -Path                   $LunPath `
            -Size                   $LunSizeBytes `
            -OsType                 windows `
            -SpaceAllocationEnabled $true | Out-Null

        Write-OK "LUN created successfully at '$LunPath'"
    }
    catch {
        Write-Fail "Failed to create LUN: $_"
        throw
    }
}


# ══════════════════════════════════════════════════════════════
# STEP 3 — Verify the LUN
# ══════════════════════════════════════════════════════════════
Write-Step 3 "Verify LUN"
Write-Info "Retrieving LUN details to confirm creation..."

$lun = Get-NcLun -VserverContext $SVMName -Path $LunPath -ErrorAction SilentlyContinue
if (-not $lun) {
    Write-Fail "LUN not found after creation — something went wrong. Check ONTAP logs."
    throw "LUN verification failed"
}

# Display a friendly summary table
Write-OK "LUN verified. Details:"
Write-Host ""
Write-Host "  Property            Value" -ForegroundColor White
Write-Host "  ──────────────────  ────────────────────────────────────"
Write-Host "  Path                $($lun.Path)"
Write-Host "  SVM                 $($lun.Vserver)"
Write-Host "  Size                $([math]::Round($lun.Size / 1GB, 2)) GB"
Write-Host "  OS Type             $($lun.OsType)"
Write-Host "  State               $($lun.State)"
Write-Host "  Space Allocation    $($lun.SpaceAllocationEnabled)"
Write-Host "  Mapped              $($lun.Mapped)"     # Should be 'false' until Step 5
Write-Host ""

# Warn if the LUN is offline (unlikely but possible)
if ($lun.State -ne 'online') {
    Write-Fail "LUN state is '$($lun.State)' — expected 'online'. Check space or snapshot reserve."
    throw "LUN is not online"
}


# ══════════════════════════════════════════════════════════════
# STEP 4 — Create the igroup (initiator group)
# ══════════════════════════════════════════════════════════════
Write-Step 4 "Create igroup (host access list)"
<#
  An igroup is a named security group that controls WHICH servers (initiators)
  can see and mount a LUN. You can add multiple servers to one igroup.

  -Protocol iscsi   : We're using iSCSI (IP-based storage). Alternative: FCP (Fibre Channel).
  -OsType windows   : Tells ONTAP the servers in this igroup run Windows.
                      This affects SCSI reservations and other protocol details.
#>

if (-not $igroupExists) {
    Write-Info "Creating igroup '$IgroupName' for Windows iSCSI host '$HostInitiatorName'..."

    if ($PSCmdlet.ShouldProcess($IgroupName, "Create igroup")) {
        try {
            New-NcIgroup `
                -VserverContext $SVMName `
                -Name           $IgroupName `
                -Protocol       iscsi `
                -OsType         windows `
                -InitiatorName  $HostInitiatorName | Out-Null
                # NOTE: In NetApp.ONTAP v9.11.1+, -InitiatorName is the REST-aligned
                # parameter name. The legacy -Initiator alias may still work but
                # -InitiatorName is preferred for forward compatibility.

            Write-OK "igroup '$IgroupName' created with initiator '$HostInitiatorName'"
        }
        catch {
            Write-Fail "Failed to create igroup: $_"
            throw
        }
    }
}
else {
    # igroup already existed; make sure our initiator is a member
    $existingInitiators = $existingIgroup.Initiators.InitiatorName
    if ($existingInitiators -notcontains $HostInitiatorName) {
        Write-Info "Adding initiator '$HostInitiatorName' to existing igroup '$IgroupName'..."
        if ($PSCmdlet.ShouldProcess($IgroupName, "Add initiator")) {
            # NetApp.ONTAP v9.11.1+: the parameter is -InitiatorName (REST-aligned).
            # Older DataONTAP used -Initiator. Both may work via alias, but
            # -InitiatorName is the canonical parameter name in the new module.
            Add-NcIgroupInitiator `
                -VserverContext $SVMName `
                -Name           $IgroupName `
                -InitiatorName  $HostInitiatorName | Out-Null
            Write-OK "Initiator added to existing igroup"
        }
    }
    else {
        Write-OK "Initiator '$HostInitiatorName' is already a member of '$IgroupName'"
    }
}

# Verify igroup
$igroup = Get-NcIgroup -VserverContext $SVMName -Name $IgroupName
Write-Host ""
Write-Host "  igroup Summary" -ForegroundColor White
Write-Host "  ──────────────────  ────────────────────────────────────"
Write-Host "  Name                $($igroup.Name)"
Write-Host "  Protocol            $($igroup.Protocol)"
Write-Host "  OS Type             $($igroup.Type)"
Write-Host "  Initiators          $($igroup.Initiators.InitiatorName -join ', ')"
Write-Host ""


# ══════════════════════════════════════════════════════════════
# STEP 5 — Map the LUN to the igroup
# ══════════════════════════════════════════════════════════════
Write-Step 5 "Map LUN to igroup"
<#
  Mapping is the final handshake:  LUN <──► igroup
  After this step, the Windows servers in the igroup can discover and mount
  the LUN as a disk drive (after running iSCSI discovery on the Windows side).

  -LunId $LunId : The logical unit number the host will see (like a disk slot number).
                  Hosts can have multiple LUNs; each must have a unique ID within
                  its igroup. Start at 0 and increment: 0, 1, 2, ...
#>
Write-Info "Mapping LUN '$LunPath' to igroup '$IgroupName' with LUN ID $LunId..."

# Check if this mapping already exists
$existingMap = Get-NcLunMap `
    -VserverContext $SVMName `
    -Path           $LunPath `
    -ErrorAction    SilentlyContinue `
    | Where-Object { $_.InitiatorGroup -eq $IgroupName }

if ($existingMap) {
    Write-Info "This LUN is already mapped to igroup '$IgroupName' with LUN ID $($existingMap.LunId). Skipping."
}
else {
    if ($PSCmdlet.ShouldProcess("$LunPath → $IgroupName", "Create LUN mapping")) {
        try {
            Add-NcLunMap `
                -VserverContext $SVMName `
                -Path           $LunPath `
                -InitiatorGroup $IgroupName `
                -LunId          $LunId | Out-Null

            Write-OK "LUN mapped successfully"
        }
        catch {
            Write-Fail "Failed to map LUN: $_"
            Write-Fail "Common causes:"
            Write-Fail "  • LUN ID $LunId is already used by another LUN in igroup '$IgroupName'"
            Write-Fail "    → Increment -LunId by 1 and retry"
            throw
        }
    }
}

# Final verification of the mapping
$map = Get-NcLunMap -VserverContext $SVMName -Path $LunPath `
       | Where-Object { $_.InitiatorGroup -eq $IgroupName }

Write-Host ""
Write-Host "  Mapping Summary" -ForegroundColor White
Write-Host "  ──────────────────  ────────────────────────────────────"
Write-Host "  LUN Path            $($map.Path)"
Write-Host "  igroup              $($map.InitiatorGroup)"
Write-Host "  LUN ID              $($map.LunId)"
Write-Host ""


# ══════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              ✔  Provisioning Complete!                   ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host @"

Module used : NetApp.ONTAP v$moduleVersion  (REST API mode)

What was just created:
  LUN path  : $LunPath ($LunSizeGB GB, Windows, space-allocation on)
  igroup    : $IgroupName (iSCSI, Windows OS type)
  Initiator : $HostInitiatorName
  LUN ID    : $LunId

Next steps on your Windows host:
  1. Open 'iSCSI Initiator' (search in Start menu)
  2. Go to the 'Discovery' tab → 'Discover Portal'
  3. Enter the SVM iSCSI data LIF IP address
  4. Go to 'Targets' tab → connect to the discovered target
  5. Open 'Disk Management' → initialize and format the new disk

"@ -ForegroundColor White
