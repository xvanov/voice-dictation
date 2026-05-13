; voice-toggle.ahk — AutoHotkey v2
;
; Ctrl+Alt+V: first press starts recording, second press stops, transcribes
; via the local transcribe_server, and copies the result to the clipboard.
;
; Requires:
;   - AutoHotkey v2 (https://www.autohotkey.com/)
;   - SoX installed and on PATH (the install.ps1 will put it there)
;   - voice-dictation venv + scripts installed at %LOCALAPPDATA%\voice-dictation
;   - transcribe_server.py running (the installer registers a scheduled task)

#Requires AutoHotkey v2.0

InstallDir := EnvGet("LOCALAPPDATA") "\voice-dictation"
PythonExe  := InstallDir "\venv\Scripts\python.exe"
ClientPy   := InstallDir "\transcribe_client.py"
WavFile    := A_Temp "\voice-recording.wav"
PidFile    := A_Temp "\voice-recording.pid"

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

        ShowToast("Transcribing...")
        cmd := '"' PythonExe '" "' ClientPy '" "' WavFile '"'
        shell := ComObject("WScript.Shell")
        exec := shell.Exec(A_ComSpec ' /c ' cmd)
        text := Trim(exec.StdOut.ReadAll(), " `r`n`t")
        FileDelete(WavFile)

        if (text != "" && !InStr(text, "ERROR:") && !InStr(text, "Server not reachable")) {
            A_Clipboard := text
            preview := SubStr(text, 1, 60)
            ShowToast("Copied: " preview)
        } else {
            ShowToast("No speech (is the server running?)")
        }
    } else {
        ShowToast("Recording...")
        Run('sox -t waveaudio default -c 1 -r 16000 -b 16 "' WavFile '"', , "Hide", &pid)
        FileAppend(pid, PidFile)
    }
}
