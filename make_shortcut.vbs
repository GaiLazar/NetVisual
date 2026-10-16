' Creates "NetVisual A+.lnk" on the Desktop pointing at run.bat, with the
' NetVisual.ico as its icon. Double-click this file to (re)generate it.
Option Explicit
Dim fso, shell, lnkPath, lnkObj, root
Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
lnkPath = shell.SpecialFolders("Desktop") & "\NetVisual A+.lnk"

Set lnkObj = shell.CreateShortcut(lnkPath)
If fso.FileExists(root & "\NetVisual.exe") Then
  lnkObj.TargetPath = fso.GetAbsolutePathName(root & "\NetVisual.exe")
Else
  lnkObj.TargetPath = fso.GetAbsolutePathName(root & "\run.bat")
End If
lnkObj.WorkingDirectory = root
lnkObj.IconLocation     = fso.GetAbsolutePathName(root & "\NetVisual.ico") & ",0"
lnkObj.Description      = "NetVisual A+ v4 - local network visualizer"
lnkObj.Save

WScript.Echo "shortcut created: " & lnkPath
