; voice-toggle.ahk — AutoHotkey v2
;
; Ctrl+Alt+V: start recording. Sox auto-stops after 2s silence.
; Ctrl+Alt+V again: manual stop before silence detected.
; On stop: transcribes via local server, pastes at cursor, copies to clipboard.

#Requires AutoHotkey v2.0
#SingleInstance Force

InstallDir := EnvGet("LOCALAPPDATA") "\voice-dictation"
PythonExe  := InstallDir "\venv\Scripts\python.exe"
ClientPy   := InstallDir "\transcribe_client.py"
SoxExe     := InstallDir "\sox.exe"
WavFile    := A_Temp "\voice-recording.wav"
OutFile    := A_Temp "\vd-transcript.txt"

if (!FileExist(SoxExe)) {
    MsgBox("sox.exe not found at:`n" SoxExe "`nRe-run install.ps1.", "Voice Dictation", 0x10)
    ExitApp
}

global _soxPid      := 0
global _transcribing := false
global _logFile     := EnvGet("LOCALAPPDATA") "\voice-dictation\voice-toggle.log"

_Log(msg) {
    global _logFile
    ts := FormatTime(, "yyyy-MM-dd HH:mm:ss")
    FileAppend(ts " " msg "`n", _logFile)
}

ShowToast(msg) {
    TrayTip("Voice", msg, 0x10)
    SetTimer(() => TrayTip(), -3000)
}

^!v:: {
    global _soxPid, _transcribing

    if _transcribing {
        ShowToast("Busy — still transcribing")
        return
    }

    if (_soxPid > 0 && ProcessExist(_soxPid)) {
        ; Manual stop
        Run('taskkill /F /PID ' _soxPid,, "Hide")
        _soxPid := 0
        SoundBeep(600, 120)
        ; WaitForSox timer will detect sox is gone and kick off transcription
    } else {
        ; Start recording
        try FileDelete(WavFile)
        try FileDelete(OutFile)

        ; silence 1 0.1 3%  = begin recording once audio exceeds 3% for 0.1s
        ; 1 2.0 3%           = stop recording after 2s of audio below 3%
        Run('"' SoxExe '" -t waveaudio default -c 1 -r 16000 -b 16 "' WavFile
            '" silence 1 0.1 3% 1 2.0 3%',, "Hide", &_soxPid)

        SoundBeep(880, 80)
        ShowToast("Recording  (auto-stops on silence, or press Ctrl+Alt+V)")
        SetTimer(WaitForSox, 200)
    }
}

WaitForSox() {
    global _soxPid, _transcribing

    ; Still recording — keep polling
    if (_soxPid > 0 && ProcessExist(_soxPid))
        return

    SetTimer(WaitForSox, 0)   ; Cancel this timer
    _soxPid := 0

    if (!FileExist(WavFile) || FileGetSize(WavFile) < 4096) {
        ShowToast("Nothing recorded")
        return
    }

    _transcribing := true
    SoundBeep(660, 80)
    ShowToast("Transcribing...")
    _Log("transcribing wav=" WavFile)

    ; RunWait blocks this timer thread but NOT the hotkey thread —
    ; the user can keep working while transcription runs.
    RunWait(A_ComSpec ' /c ""' PythonExe '" "' ClientPy '" "' WavFile
        '" > "' OutFile '" 2>&1"',, "Hide")

    text := Trim(FileExist(OutFile) ? FileRead(OutFile) : "", " `r`n`t")
    _Log("server returned: [" text "]")
    try FileDelete(OutFile)
    try FileDelete(WavFile)
    _transcribing := false

    if (text = "" || InStr(text, "ERROR:") || InStr(text, "Server not reachable")) {
        detail := text != "" ? text : "no response from server"
        SoundBeep(300, 300)
        _Log("FAILED: " detail)
        ShowToast("Failed: " SubStr(detail, 1, 80))
        return
    }

    A_Clipboard := ""
    A_Clipboard := text
    ClipWait(2)
    Send("^v")
    SoundBeep(1100, 80)
    _Log("pasted: " text)
    ShowToast("Pasted: " SubStr(text, 1, 60))
}
