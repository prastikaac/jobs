Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper"
WshShell.Run """C:\Users\Ac\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"" ""C:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper\schedule_jobs.py""", 0, False
