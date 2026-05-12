$myshell = New-Object -com "Wscript.Shell"
while ($true) {
    $myshell.sendkeys("{SCROLLLOCK}")
    Start-Sleep -Seconds 60
    $myshell.sendkeys("{SCROLLLOCK}")
    Start-Sleep -Seconds 60
}
