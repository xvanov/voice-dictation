; voice-toggle.ahk — AutoHotkey v2
;
; Ctrl+Alt+V: first press starts recording, second press stops, transcribes
; via the local transcribe_server, and copies the result to the clipboard.
;
; Requires:
;   - AutoHotkey v2 (https://www.autohotkey.com/)
;   - SoX copied into the install dir by install.ps1 (sox.exe lives next to this script)
;   - voice-dictation venv + scripts installed at %LOCALAPPDATA%\voice-dictation
;   - transcribe_server.py running (the installer registers a scheduled task)

#Requires AutoHotkey v2.0

InstallDir := EnvGet("LOCALAPPDATA") "\voice-dictation"
PythonExe  := InstallDir "\venv\Scripts\python.exe"
ClientPy   := InstallDir "\transcribe_client.py"
SoxExe     := InstallDir "\sox.exe"
WavFile    := A_Temp "\voice-recording.wav"
PidFile    := A_Temp "\voice-recording.pid"

if (!FileExist(SoxExe)) {
    MsgBox("sox.exe not found at:`n" SoxExe "`nRe-run install.ps1 to fix this.", "Voice Dictation", 0x10)
    ExitApp
}

ShowToast(msg) {
    TrayTip("Voice", msg, 0x10)
    SetTimer(() => TrayTip(), -1500)
}

^!v:: {
    global
    if FileExist(PidFile) {
        pid := FileRead(PidFile)
        RunWait('taskkill /F /PID ' pid, , "Hide")
        FileDelete(PidFile)
        Sleep(150)  ; let sox flush the wav header

        if (!FileExist(WavFile)) {
            ShowToast("Record failed (sox wrote no file)")
            return
        }

        ShowToast("Transcribing...")
        outFile := A_Temp "\vd-transcript.txt"
        RunWait(A_ComSpec ' /c ""' PythonExe '" "' ClientPy '" "' WavFile '" > "' outFile '" 2>&1"',, "Hide")
        text := Trim(FileExist(outFile) ? FileRead(outFile) : "", " `r`n`t")
        try FileDelete(outFile)
        try FileDelete(WavFile)

        if (text != "" && !InStr(text, "ERROR:") && !InStr(text, "Server not reachable")) {
            A_Clipboard := ""
            A_Clipboard := text
            ClipWait(2)
            preview := SubStr(text, 1, 60)
            ShowToast("Copied: " preview)
        } else {
            detail := text != "" ? text : "no output from server"
            ShowToast("Failed: " SubStr(detail, 1, 80))
        }
    } else {
        ShowToast("Recording...")
        Run('"' SoxExe '" -t waveaudio default -c 1 -r 16000 -b 16 "' WavFile '"', , "Hide", &pid)
        FileAppend(pid, PidFile)
    }
}
