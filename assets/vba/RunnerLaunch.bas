Attribute VB_Name = "RunnerLaunch"
Option Explicit

Private Const RUNNER_SHEET_NAME As String = "Runner"
Private Const STATUS_CELL As String = "B7"
Private Const RESULT_CELL As String = "B8"
Private Const SHELL_ERROR_BASE As Long = vbObjectError + 7100

Public Enum RunnerMode
    RunnerModeAllPrograms = 0
    RunnerModeExTrend = 1
    RunnerModeTrend = 2
End Enum

Public Type LaunchStatus
    Success As Boolean
    ErrorCode As Long
    Message As String
    Command As String
    ExitCode As Long
End Type

Public Sub RunAll_Click()
    RunModeClick "All"
End Sub

Public Sub RunExTrend_Click()
    RunModeClick "ExTrend"
End Sub

Public Sub RunTrend_Click()
    RunModeClick "Trend"
End Sub

Public Sub OpenOutputFolder_Click()
    On Error GoTo OpenOutputFolderError

    Dim selectedDate As String
    Dim resolvedPath As String
    Dim missingDirectoryMessage As String
    Dim fileSystem As Object
    Dim status As LaunchStatus

    selectedDate = ReadSelectedDate()
    resolvedPath = ResolveOutputDir(ResolveRepoRoot(), selectedDate)
    missingDirectoryMessage = "Directory not found" & resolvedPath
    If Dir$(resolvedPath, vbDirectory) = "" Then
        Set fileSystem = CreateObject("Scripting.FileSystemObject")
        If Not fileSystem.FolderExists(resolvedPath) Then
            MsgBox missingDirectoryMessage
            WriteResult "Error " & missingDirectoryMessage
            Exit Sub
        End If
    End If

    If Not DirectoryExists(resolvedPath) Then
        MsgBox missingDirectoryMessage
        WriteResult "Error " & missingDirectoryMessage
        Exit Sub
    End If

    status = OpenDirectory(resolvedPath)
    WriteLaunchResult status
    Exit Sub

OpenOutputFolderError:
    WriteResult "Error " & CStr(Err.Number) & ": " & Err.Description
End Sub

Public Function BuildRunArguments(ByVal asOfMonth As String, ByVal mode As RunnerMode) As String
    Dim outputDir As String
    Dim parsedDate As Date

    parsedDate = ParseAsOfMonth(asOfMonth)
    outputDir = ResolveOutputDir(".", asOfMonth)
    BuildRunArguments = BuildCommandArguments(ModeToString(mode), parsedDate, outputDir)
End Function

Public Function BuildCommand( _
    ByVal runMode As String, _
    ByVal selectedDate As String, _
    ByVal outputDir As String _
) As String
    Dim parsedDate As Date
    Dim parsedDateValue As String
    Dim resolvedOutputDir As String
    Dim command As String
    Dim shellObject As Object
    Dim shellCommand As String
    Dim exitCode As Long

    On Error GoTo BuildCommandError
    WriteStatus "Running..."

    parsedDate = ParseAsOfMonth(selectedDate)
    parsedDate = CDate(parsedDate)
    parsedDateValue = Format$(parsedDate, "yyyy-mm-dd")
    resolvedOutputDir = NormalizePathSeparators(ThisWorkbook.Path) & "\runs\" & parsedDateValue
    outputDir = resolvedOutputDir

    command = BuildCommandArguments(runMode, parsedDate, resolvedOutputDir)
    shellCommand = BuildExecutableShellCommand(ResolveExecutablePath(), command)

    Set shellObject = CreateObject("WScript.Shell")
    exitCode = CLng(shellObject.Run(shellCommand, 0, True))
    If exitCode <> 0 Then
        Err.Raise SHELL_ERROR_BASE + exitCode, "RunnerLaunch.BuildCommand", _
                  "Process exited with code " & CStr(exitCode)
    End If

    WriteStatus "Success"
    BuildCommand = command
    Exit Function

BuildCommandError:
    WriteStatus "Error"
    WriteResult "Error " & CStr(Err.Number) & ": " & Err.Description
    BuildCommand = ""
End Function

Private Function BuildCommandArguments( _
    ByVal runMode As String, _
    ByVal parsedDate As Date, _
    ByVal outputDir As String _
) As String
    BuildCommandArguments = "run --fixture-replay --config " & _
                            QuoteArg(ResolveConfigPath(ResolveRunnerMode(runMode))) & _
                            " --as-of-month " & QuoteArg(Format$(parsedDate, "yyyy-mm-dd")) & _
                            " --output-dir " & QuoteArg(outputDir)
End Function

Public Function BuildExecutableCommand( _
    ByVal executablePath As String, _
    ByVal asOfMonth As String, _
    ByVal mode As RunnerMode _
) As String
    BuildExecutableCommand = QuoteArg(executablePath) & " " & BuildRunArguments(asOfMonth, mode)
End Function

Public Function ResolveOutputDir(ByVal repoRoot As String, ByVal selectedDate As String) As String
    Dim parsedDate As Date
    parsedDate = ParseAsOfMonth(selectedDate)

    ResolveOutputDir = NormalizePathSeparators(repoRoot) & "\runs\" & Format$(parsedDate, "yyyy-mm-dd")
End Function

Public Function ExecuteRunnerCommand(ByVal executablePath As String, ByVal command As String) As LaunchStatus
    Dim status As LaunchStatus
    Dim shellCommand As String
    Dim exitCode As Long

    On Error GoTo ExecuteRunnerCommandError
    shellCommand = BuildExecutableShellCommand(executablePath, command)
    exitCode = ExecuteShellCommand(shellCommand)
    status = BuildSuccessStatus(shellCommand, exitCode)
    If exitCode <> 0 Then
        status.Success = False
        status.ErrorCode = SHELL_ERROR_BASE + exitCode
        status.Message = "Process exited with code " & CStr(exitCode)
    End If

    ExecuteRunnerCommand = status
    Exit Function

ExecuteRunnerCommandError:
    ExecuteRunnerCommand = BuildErrorStatus(command, Err.Number, Err.Description)
End Function

Private Function ResolveConfigPath(ByVal mode As RunnerMode) As String
    Select Case mode
        Case RunnerModeAllPrograms
            ResolveConfigPath = "config\all_programs.yml"
        Case RunnerModeExTrend
            ResolveConfigPath = "config\ex_trend.yml"
        Case RunnerModeTrend
            ResolveConfigPath = "config\trend.yml"
        Case Else
            Err.Raise vbObjectError + 7000, "RunnerLaunch.ResolveConfigPath", _
                      "Unsupported run mode value: " & CStr(mode)
    End Select
End Function

Private Function ResolveRunnerMode(ByVal runMode As String) As RunnerMode
    Select Case UCase$(Trim$(runMode))
        Case "ALL"
            ResolveRunnerMode = RunnerModeAllPrograms
        Case "EXTREND", "EX_TREND", "EX TREND"
            ResolveRunnerMode = RunnerModeExTrend
        Case "TREND"
            ResolveRunnerMode = RunnerModeTrend
        Case Else
            Err.Raise vbObjectError + 7002, "RunnerLaunch.ResolveRunnerMode", _
                      "Unsupported run mode value: " & runMode
    End Select
End Function

Private Function ModeToString(ByVal mode As RunnerMode) As String
    Select Case mode
        Case RunnerModeAllPrograms
            ModeToString = "All"
        Case RunnerModeExTrend
            ModeToString = "ExTrend"
        Case RunnerModeTrend
            ModeToString = "Trend"
        Case Else
            Err.Raise vbObjectError + 7003, "RunnerLaunch.ModeToString", _
                      "Unsupported run mode value: " & CStr(mode)
    End Select
End Function

Private Function ParseAsOfMonth(ByVal asOfMonth As String) As Date
    Dim parsedDate As Date
    If Not IsDate(asOfMonth) Then
        Err.Raise vbObjectError + 7001, "RunnerLaunch.ParseAsOfMonth", _
                  "As-of month must be a valid date value."
    End If

    parsedDate = CDate(asOfMonth)
    ParseAsOfMonth = DateSerial(Year(parsedDate), Month(parsedDate) + 1, 0)
End Function

Private Function QuoteArg(ByVal value As String) As String
    QuoteArg = Chr$(34) & value & Chr$(34)
End Function

Private Sub RunModeClick(ByVal runMode As String)
    On Error GoTo RunModeClickError

    Dim selectedDate As String
    Dim outputDir As String
    Dim command As String

    selectedDate = ReadSelectedDate()
    outputDir = ResolveOutputDir(ResolveRepoRoot(), selectedDate)
    command = BuildCommand(runMode, selectedDate, outputDir)
    If LenB(command) = 0 Then
        Exit Sub
    End If
    WriteResult "Success"
    Exit Sub

RunModeClickError:
    WriteResult "Error " & CStr(Err.Number) & ": " & Err.Description
End Sub

Private Function ResolveExecutablePath() As String
    ResolveExecutablePath = NormalizePathSeparators(ResolveRepoRoot()) & "\dist\counter-risk.exe"
End Function

Private Function ResolveRepoRoot() As String
    ResolveRepoRoot = NormalizePathSeparators(ThisWorkbook.Path)
End Function

Private Function BuildExecutableShellCommand(ByVal executablePath As String, ByVal command As String) As String
    BuildExecutableShellCommand = QuoteArg(executablePath) & " " & command
End Function

Private Function ExecuteShellCommand(ByVal shellCommand As String) As Long
    Dim shellObject As Object

    Set shellObject = CreateObject("WScript.Shell")
    ExecuteShellCommand = CLng(shellObject.Run(shellCommand, 0, True))
End Function

Private Function OpenDirectory(ByVal directoryPath As String) As LaunchStatus
    Dim status As LaunchStatus
    Dim shellObject As Object
    Dim openCommand As String

    On Error GoTo OpenDirectoryError
    Set shellObject = CreateObject("WScript.Shell")
    openCommand = BuildOpenFolderCommand(directoryPath)
    shellObject.Run openCommand, 1, False
    status = BuildSuccessStatus(openCommand, 0)
    OpenDirectory = status
    Exit Function

OpenDirectoryError:
    OpenDirectory = BuildErrorStatus(directoryPath, Err.Number, Err.Description)
End Function

Private Function BuildOpenFolderCommand(ByVal directoryPath As String) As String
    Dim platformName As String
    platformName = Application.OperatingSystem

    If InStr(1, platformName, "Windows", vbTextCompare) > 0 Then
        BuildOpenFolderCommand = "cmd /c start " & Chr$(34) & Chr$(34) & " " & QuoteArg(directoryPath)
        Exit Function
    End If
    If InStr(1, platformName, "Mac", vbTextCompare) > 0 Then
        BuildOpenFolderCommand = "open " & QuoteArg(directoryPath)
        Exit Function
    End If

    BuildOpenFolderCommand = "xdg-open " & QuoteArg(directoryPath)
End Function

Private Function DirectoryExists(ByVal directoryPath As String) As Boolean
    DirectoryExists = LenB(Dir$(directoryPath, vbDirectory)) <> 0
End Function

Private Function BuildSuccessStatus(ByVal command As String, ByVal exitCode As Long) As LaunchStatus
    Dim status As LaunchStatus

    status.Success = True
    status.ErrorCode = 0
    status.Message = "Success"
    status.Command = command
    status.ExitCode = exitCode
    BuildSuccessStatus = status
End Function

Private Function BuildErrorStatus( _
    ByVal command As String, _
    ByVal errorCode As Long, _
    ByVal errorMessage As String _
) As LaunchStatus
    Dim status As LaunchStatus

    status.Success = False
    status.ErrorCode = errorCode
    status.Message = errorMessage
    status.Command = command
    status.ExitCode = -1
    BuildErrorStatus = status
End Function

Private Function NormalizePathSeparators(ByVal rawPath As String) As String
    Dim normalizedPath As String

    normalizedPath = Trim$(rawPath)
    normalizedPath = Replace(normalizedPath, "/", "\")
    Do While Len(normalizedPath) > 3 And Right$(normalizedPath, 1) = "\"
        normalizedPath = Left$(normalizedPath, Len(normalizedPath) - 1)
    Loop
    NormalizePathSeparators = normalizedPath
End Function

Private Sub WriteStatus(ByVal statusText As String)
    ThisWorkbook.Worksheets(RUNNER_SHEET_NAME).Range(STATUS_CELL).Value = statusText
End Sub

Private Sub WriteResult(ByVal resultText As String)
    ThisWorkbook.Worksheets(RUNNER_SHEET_NAME).Range(RESULT_CELL).Value = resultText
End Sub

Private Sub WriteLaunchResult(ByRef status As LaunchStatus)
    If status.Success Then
        WriteResult "Success"
        Exit Sub
    End If

    WriteResult "Error " & CStr(status.ErrorCode) & ": " & status.Message
End Sub

Private Function ReadSelectedDate() As String
    ReadSelectedDate = CStr(ThisWorkbook.Worksheets(RUNNER_SHEET_NAME).Range("B3").Value)
End Function
