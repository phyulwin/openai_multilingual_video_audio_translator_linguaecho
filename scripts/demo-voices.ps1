# demo-voices.ps1 — Render scripted Japanese and English using installed Windows voices.
param([Parameter(Mandatory=$true)][string]$FixtureDirectory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$demoScript = Get-Content -LiteralPath (Join-Path $FixtureDirectory 'script.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$demoVoice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    # Use one common PCM format so all sentence clips can be concatenated safely.
    $demoFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    for ($demoIndex = 0; $demoIndex -lt $demoScript.originals.Count; $demoIndex++) {
        $demoVoice.SelectVoice('Microsoft Haruka Desktop')
        $demoVoice.SetOutputToWaveFile((Join-Path $FixtureDirectory ('ja-' + ($demoIndex + 1) + '.wav')), $demoFormat)
        $demoVoice.Speak($demoScript.originals[$demoIndex])
        $demoVoice.SetOutputToNull()
        $demoVoice.SelectVoice('Microsoft Zira Desktop')
        $demoVoice.SetOutputToWaveFile((Join-Path $FixtureDirectory ('en-' + ($demoIndex + 1) + '.wav')), $demoFormat)
        $demoVoice.Speak($demoScript.translations[$demoIndex])
        $demoVoice.SetOutputToNull()
    }
} finally {
    # Always release voice and file handles, even if a voice is unavailable.
    $demoVoice.Dispose()
}
