# Parameters setting
$out_dir = Get-Item -Path "..\out"
$since = ""
$until = ""
$branch_name = "develop"
$interval = "weekly"
$languages = "C#,python,markdown,txt"
$author_name = ""
$clear_cache = $false

# Repository List
$repo_list = @(
    "../../AnalyzeGitRepoLoc/"
)
$repo_paths = $repo_list -join ","

# venv environment activation
$venv_path = Join-Path -Path (Get-Item -Path "..\").FullName -ChildPath ".venv\Scripts\Activate.ps1"
& $venv_path

# Command options setting
$command = "python -m analyze_git_repo_loc"
$command += if ($out_dir) { " -o $out_dir" } else { "" }
$command += if ($interval) { " --interval $interval" } else { "" }
$command += if ($branch_name) { " --branch $branch_name" } else { "" }
$command += if ($languages) { " --lang $languages" } else { "" }
$command += if ($since) { " --since $since" } else { "" }
$command += if ($until) { " --until $until" } else { "" }
$command += if ($author_name) { " --author-name $author_name" } else { "" }
$command += if ($clear_cache) { " --clear_cache" } else { "" }
$command += " $repo_paths"

#comment display and line feed, space
Write-Host "Command: $command" 
Write-Host "----------------------------------------" `n

# Command execution
Invoke-Expression $command

# Deactivate venv environment
deactivate