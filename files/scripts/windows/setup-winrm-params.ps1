# Increase the maximum size of a WinRM message (Ansible's headers are larger than 'ipconfig')
winrm set winrm/config @{MaxEnvelopeSizekb="8192"}

# Increase memory limits for the shell (Windows 2012 defaults are very low)
set-item WSMan:\localhost\Shell\MaxMemoryPerShellMB 1024

# Restart service to apply
Restart-Service winrm
