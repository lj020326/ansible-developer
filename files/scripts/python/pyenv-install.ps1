#!/usr/bin/env powershell
##!/usr/bin/env pwsh

$ProgressPreference="SilentlyContinue"

# ref: https://github.com/pyenv-win/pyenv-win
$download_url = "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1"

$install_file_name = "install-pyenv-win.ps1"
$dest_path = "C:\Windows\Temp\$install_file_name"

Invoke-WebRequest -Uri $download_url -OutFile $dest_path
&"$dest_path"

## ref: https://pypi.org/project/pyenv-win/#add-system-settings
[System.Environment]::SetEnvironmentVariable('PYENV',$env:USERPROFILE + "\.pyenv\pyenv-win\","User")
[System.Environment]::SetEnvironmentVariable('PYENV_ROOT',$env:USERPROFILE + "\.pyenv\pyenv-win\","User")
[System.Environment]::SetEnvironmentVariable('PYENV_HOME',$env:USERPROFILE + "\.pyenv\pyenv-win\","User")
[System.Environment]::SetEnvironmentVariable('path', $env:USERPROFILE + "\.pyenv\pyenv-win\bin;" `
    + $env:USERPROFILE + "\.pyenv\pyenv-win\shims;" `
    + [System.Environment]::GetEnvironmentVariable('path', "User"),"User")
