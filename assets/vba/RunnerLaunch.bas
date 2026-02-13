Attribute VB_Name = "RunnerLaunch"
Option Explicit

Public Enum RunnerMode
    RunnerModeAllPrograms = 0
    RunnerModeExTrend = 1
    RunnerModeTrend = 2
End Enum

Public Sub RunAll_Click()
    Dim selectedDate As String
    Dim parsedDate As Date
    Dim outputDir As String

    selectedDate = ReadSelectedDate()
    parsedDate = ParseAsOfMonth(selectedDate)
    outputDir = "outputs\" & Format$(parsedDate, "yyyy-mm-dd")

    BuildCommand "All", selectedDate, outputDir
End Sub

Public Sub RunExTrend_Click()
    Dim selectedDate As String
    Dim parsedDate As Date
    Dim outputDir As String

    selectedDate = ReadSelectedDate()
    parsedDate = ParseAsOfMonth(selectedDate)
    outputDir = "outputs\" & Format$(parsedDate, "yyyy-mm-dd")

    BuildCommand "ExTrend", selectedDate, outputDir
End Sub

Public Sub RunTrend_Click()
    Dim selectedDate As String
    Dim parsedDate As Date
    Dim outputDir As String

    selectedDate = ReadSelectedDate()
    parsedDate = ParseAsOfMonth(selectedDate)
    outputDir = "outputs\" & Format$(parsedDate, "yyyy-mm-dd")

    BuildCommand "Trend", selectedDate, outputDir
End Sub

Public Sub OpenOutputFolder_Click()
    Dim selectedDate As String
    selectedDate = ReadSelectedDate()
End Sub

Public Function BuildRunArguments(ByVal asOfMonth As String, ByVal mode As RunnerMode) As String
    Dim parsedDate As Date
    Dim outputDir As String

    parsedDate = ParseAsOfMonth(asOfMonth)
    outputDir = "outputs\" & Format$(parsedDate, "yyyy-mm-dd")

    BuildRunArguments = BuildCommand(ModeToString(mode), asOfMonth, outputDir)
End Function

Public Function BuildCommand( _
    ByVal runMode As String, _
    ByVal selectedDate As String, _
    ByVal outputDir As String _
) As String
    Dim parsedDate As Date
    parsedDate = ParseAsOfMonth(selectedDate)

    BuildCommand = "run --fixture-replay --config " & _
                   QuoteArg(ResolveConfigPath(ResolveRunnerMode(runMode))) & _
                   " --output-dir " & QuoteArg(outputDir)
End Function

Public Function BuildExecutableCommand( _
    ByVal executablePath As String, _
    ByVal asOfMonth As String, _
    ByVal mode As RunnerMode _
) As String
    BuildExecutableCommand = QuoteArg(executablePath) & " " & BuildRunArguments(asOfMonth, mode)
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

Private Function ReadSelectedDate() As String
    ReadSelectedDate = CStr(ThisWorkbook.Worksheets("Runner").Range("B3").Value)
End Function
