$env:PYTHONPATH = "$PSScriptRoot\src;$env:PYTHONPATH"
python -m codegraph $args
