# Parameters setting
$out_dir = Get-Item -Path "..\out"
$since = ""
$until = ""
$interval = "daily"
$languages = "C#,Python,Markdown,PowerShell,C++"
$author_name = ""
$clear_cache = $false
$no_plot_show = $true
$repo_paths = ".\repo_list.txt"

# venv environment activation
$venv_path = Join-Path -Path (Get-Item -Path "..\").FullName -ChildPath ".venv\Scripts\Activate.ps1"
& $venv_path

# PYTHONPATH setting
$env:PYTHONPATH = "../"

# Command options setting
$command = "python -m analyze_git_repo_loc"
$command += if ($out_dir) { " -o $out_dir" } else { "" }
$command += if ($interval) { " --interval $interval" } else { "" }
$command += if ($languages) { " --lang $languages" } else { "" }
$command += if ($since) { " --since $since" } else { "" }
$command += if ($until) { " --until $until" } else { "" }
$command += if ($author_name) { " --author-name $author_name" } else { "" }
$command += if ($clear_cache) { " --clear-cache" } else { "" }
$command += if ($no_plot_show) { " --no-plot-show" } else { "" }
$command += " $repo_paths"

#comment display and line feed, space
Write-Host "Command: $command" 
Write-Host "----------------------------------------" `n

# Command execution
Invoke-Expression $command

# Deactivate venv environment
deactivate