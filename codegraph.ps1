$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$env:PYTHONPATH = "$PSScriptRoot\src;$env:PYTHONPATH"
python -m codegraph $args
