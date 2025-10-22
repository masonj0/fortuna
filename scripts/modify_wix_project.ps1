# scripts/modify_wix_project.ps1
# This script is called by the `msiProjectCreated` hook in electron-builder.
# It receives the path to the auto-generated project.wxs file and modifies it in place
# to add our custom post-install validation logic.

param (
    [string]$WxsPath
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $LogMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Add-Content -Path (Join-Path $env:TEMP "fortuna-wix-hook.log") -Value $LogMessage
}

Write-Log "--- Starting WiX Project Modification ---"
Write-Log "Received WXS Path: $WxsPath"

if (-not (Test-Path $WxsPath)) {
    Write-Log "[FATAL] WXS file not found at path: $WxsPath"
    exit 1
}

# Read the XML content of the .wxs file
[xml]$WxsContent = Get-Content -Path $WxsPath

# Define the XML nodes for our custom action
$CustomActionXml = @'
    <!-- 1. Find PowerShell.exe -->
    <Property Id="POWERSHELL">
      <RegistrySearch Id="PowerShellPath" Root="HKLM" Key="SOFTWARE\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell" Name="Path" Type="raw" />
    </Property>
    <Condition Message="PowerShell is required to complete this installation."><![CDATA[Installed OR POWERSHELL]]></Condition>

    <!-- 2. Add the validation script to the installer's binary table -->
    <Binary Id="ValidateInstallScript" SourceFile="resources\app\scripts\validate_installation.ps1" />

    <!-- 3. Define the Custom Action to run the script -->
    <CustomAction Id="ValidateInstallation"
                  Directory="INSTALLDIR"
                  ExeCommand="[POWERSHELL] -NoProfile -ExecutionPolicy Bypass -File &quot;[#ValidateInstallScript]&quot; -InstallPath &quot;[INSTALLDIR]&quot;"
                  Execute="deferred"
                  Return="check"
                  Impersonate="no" />

    <!-- 4. Schedule the Custom Action -->
    <InstallExecuteSequence>
        <Custom Action="ValidateInstallation" After="InstallFinalize">NOT Installed</Custom>
    </InstallExecuteSequence>
'@

# Create an XML fragment from our string
$Fragment = [xml]("<Fragment>$CustomActionXml</Fragment>")

# Find the <Product> node in the main WXS file
$ProductNode = $WxsContent.Wix.Product

if (-not $ProductNode) {
    Write-Log "[FATAL] Could not find <Product> node in the WXS file."
    exit 1
}

# Import and append each child node from our fragment into the <Product> node
$Fragment.Fragment.ChildNodes | ForEach-Object {
    $ImportedNode = $WxsContent.ImportNode($_, $true)
    $ProductNode.AppendChild($ImportedNode)
    Write-Log "Appended node: $($ImportedNode.LocalName)"
}

# Save the modified XML back to the file
$WxsContent.Save($WxsPath)

Write-Log "--- WiX Project Modification Successful ---"
exit 0
