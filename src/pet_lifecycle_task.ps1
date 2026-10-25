param(
    [ValidateSet('enable','disable')][string]$Mode,
    [string]$TaskName,[string]$Python,[string]$Script,[string]$DataDir,
    [switch]$Standalone
)
$ErrorActionPreference='Stop'
$petService=New-Object -ComObject 'Schedule.Service'
$petService.Connect()
$petFolder=$petService.GetFolder('\')
if ($Mode -eq 'disable') {
    $petExisting=@($petFolder.GetTasks(0)) | Where-Object { $_.Name -eq $TaskName }
    if ($petExisting) { $petFolder.DeleteTask($TaskName,0) }
    exit 0
}
$petSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$petTask=$petService.NewTask(0)
$petTask.RegistrationInfo.Description='Start the quota accessory only while Codex and its pet are open.'
$petTask.Principal.UserId=$petSid
$petTask.Principal.LogonType=3
$petTask.Principal.RunLevel=0
$petTask.Settings.Enabled=$true
$petTask.Settings.StartWhenAvailable=$true
$petTask.Settings.DisallowStartIfOnBatteries=$false
$petTask.Settings.StopIfGoingOnBatteries=$false
$petTask.Settings.ExecutionTimeLimit='PT0S'
$petTask.Settings.MultipleInstances=2
$petTrigger=$petTask.Triggers.Create(1)
$petTrigger.StartBoundary=(Get-Date).AddSeconds(10).ToString('yyyy-MM-ddTHH:mm:ss')
$petTrigger.Repetition.Interval='PT1M'
$petTrigger.Repetition.StopAtDurationEnd=$false
$petLogon=$petTask.Triggers.Create(9)
$petLogon.UserId=$petSid
$petAction=$petTask.Actions.Create(0)
$petAction.Path=$Python
if ($Standalone) {
    $petAction.Arguments='--auto-start --data-dir "'+$DataDir+'"'
    $petAction.WorkingDirectory=Split-Path -LiteralPath $Python
} else {
    $petAction.Arguments='"'+$Script+'" --auto-start --data-dir "'+$DataDir+'"'
    $petAction.WorkingDirectory=Split-Path -LiteralPath $Script
}
$null=$petFolder.RegisterTaskDefinition($TaskName,$petTask,6,$petSid,$null,3)
Write-Output $TaskName

