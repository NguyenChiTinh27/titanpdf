Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\ntc27\OneDrive\文件\TitanPDF"
WshShell.Run "python server.py", 0, False
WScript.Sleep 2000
WshShell.Run "python start_tunnel.py", 0, False
