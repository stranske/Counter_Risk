Attribute VB_Name = "RunnerLaunch"
Option Explicit

Public Enum RunnerMode
    RunnerModeAllPrograms = 0
    RunnerModeExTrend = 1
    RunnerModeTrend = 2
End Enum

Public Sub RunAll_Click()
    BuildRunArguments ReadSelectedDate(), RunnerModeAllPrograms
End Sub

Public Sub RunExTrend_Click()
    BuildRunArguments ReadSelectedDate(), RunnerModeExTrend
End Sub

Public Sub RunTrend_Click()
    BuildRunArguments ReadSelectedDate(), RunnerModeTrend
End Sub

Public Sub OpenOutputFolder_Click()
    Dim selectedDate As String
    selectedDate = ReadSelectedDate()
End Sub

Public Function BuildRunArguments(ByVal asOfMonth As String, ByVal mode As RunnerMode) As String
    Dim parsedDate As Date
    parsedDate = ParseAsOfMonth(asOfMonth)

    BuildRunArguments = "run --fixture-replay --config " & _
                        QuoteArg(ResolveConfigPath(mode)) & _
                        " --output-dir " & QuoteArg("outputs\" & Format$(parsedDate, "yyyy-mm-dd"))
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
