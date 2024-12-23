<#
.SYNOPSIS
This script analyzes the LOC (Lines of Code) in Git repositories listed in a file.

.DESCRIPTION
The script reads a list of Git repositories and their associated settings (e.g., excluded directories)
from a specified `repo_list.txt` file. For each repository, it executes a Python script to analyze the LOC.

.PARAMETER repo_list
Path to the `repo_list.txt` file. Default: ".\repo_list.txt".
The file should contain a list of repositories and their settings in the following format:
repository_path1#branch_name1,/path/to/exclude1,/path/to/exclude2,...
repository_path2#branch_name2,/path/to/exclude3,/path/to/exclude4,...

.PARAMETER out_dir
Output directory where results will be saved. Default: "..\out".

.PARAMETER since
Start date for commit analysis. Default: "" (no filtering).

.PARAMETER until
End date for commit analysis. Default: "" (no filtering).

.PARAMETER interval
Interval for analysis (e.g., daily, weekly, monthly). Default: "daily".

.PARAMETER languages
Comma-separated list of languages to include in the analysis. Default: "C#,Python,Markdown,PowerShell,C++".

.PARAMETER author_name
Filter commits by author name. Default: "" (no filtering).

.PARAMETER clear_cache
Clear the cached results before analysis. Default: `$false`.

.PARAMETER no_plot_show
Disable plotting and display. Default: `$false`.

.EXAMPLE
.\run_analysis.ps1 -repo_list ".\custom_repo_list.txt" -interval "weekly"

This command reads repositories from `custom_repo_list.txt` and performs weekly LOC analysis.

#>

# Parameters setting
[CmdletBinding()]
param(
    [switch]$help,
    [string]$repo_paths = ".\repo_list.txt", 
    [string]$out_dir = "..\out",
    [string]$since = "",
    [string]$until = "",
    [string]$interval = "daily",
    [string]$languages = "C#,Python,Markdown,PowerShell,C++",
    [string]$author_name = "",
    [bool]$clear_cache = $false,
    [bool]$no_plot_show = $false
)

# Show help if requested
if ($help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed 
    exit
}

# venv environment activation
$venv_path = Join-Path -Path (Get-Item -Path "..\").FullName -ChildPath ".venv\Scripts\Activate.ps1"
& $venv_path

# PYTHONPATH setting
$env:PYTHONPATH = "../"

# Parse repo_list.txt and execute for each repository
if (-Not (Test-Path $repo_paths)) {
    Write-Host "Error: The specified repo_list file ($repo_paths) does not exist." -ForegroundColor Red
    exit 1
}

# Build the command
$command = "python -m analyze_git_repo_loc"
$command += if ($out_dir) { " -o `"$out_dir`"" } else { "" }
$command += if ($interval) { " --interval $interval" } else { "" }
$command += if ($languages) { " --lang $languages" } else { "" }
$command += if ($since) { " --since $since" } else { "" }
$command += if ($until) { " --until $until" } else { "" }
$command += if ($author_name) { " --author-name `"$author_name`"" } else { "" }
$command += if ($clear_cache) { " --clear-cache" } else { "" }
$command += if ($no_plot_show) { " --no-plot-show" } else { "" }
$command += if ($exclude_dirs) { " --exclude-dirs `"$exclude_dirs`"" } else { "" }
$command += " `"$repo_paths`""

# Display the command for debugging
Write-Host "Command: $command" 
Write-Host "----------------------------------------" `n

# Execute the command
Invoke-Expression $command

# Deactivate venv environment
deactivate