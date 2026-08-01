' Wrapper script - запускает бота без окна консоли
Dim WShell
Set WShell = CreateObject("WScript.Shell")
WShell.CurrentDirectory = "E:\AE_projects\ai_photo_bot"
WShell.Run """E:\AE_projects\ai_photo_bot\venv\Scripts\pythonw.exe"" ""E:\AE_projects\ai_photo_bot\bot.py""" , 0, False
Set WShell = Nothing
