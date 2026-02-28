# Chat Logging

Counter_Risk persists each chat interaction to the active run folder for auditability.

## Log Location

- Directory: `runs/<as_of_timestamp>/chat_logs/`
- File pattern: `chat_log_<YYYYMMDD>.jsonl`
- Format: one JSON object per line (one line per chat submission)

## Logged Fields

Each JSONL row contains:

- `interaction`: incrementing interaction number in the current session
- `timestamp`: UTC timestamp (`Z` suffix)
- `selected_provider` / `selected_model`: provider/model chosen by the operator
- `provider` / `model`: resolved provider/model used for the actual invocation
- `question`: validated user question text
- `prompt`: guarded prompt payload sent to provider
- `response`: assistant text returned by provider
- `trace_id`: LangSmith trace ID when available
- `trace_url`: full LangSmith trace URL when available

## LangSmith Correlation

When LangSmith tracing is enabled and the provider returns a trace/run ID, the
`trace_id` and `trace_url` fields are populated so operators can correlate a chat
turn in the run folder with the LangSmith trace view.

## Failure Behavior

If the chat log directory/file cannot be written, the chat submission fails with a
clear error so operators know transcript persistence did not succeed.
