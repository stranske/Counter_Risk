# Remote Trigger Testing

This document describes how to test the Counter Risk pipeline using the
shared-folder remote request flow — for cases where the requesting machine
cannot run the pipeline directly.

## Overview

```
[Work PC / Requester]                   [Worker Machine]
        |                                       |
  request_counter_risk_remote.cmd        process_counter_risk_remote.cmd
        |                                       |
        +---- writes .request file ---->  shared folder
                                                |
                                         reads .request file
                                                |
                                         runs counter-risk CLI
                                                |
                                         writes output to output_dir
                                                |
                                         renames .request -> .done / .failed
```

Both scripts are included in the release bundle. Both machines must have the
bundle extracted to a local folder. Only the worker machine needs to be able to
reach the pipeline's input data.

---

## Prerequisites

| Requirement | Requester | Worker |
|---|---|---|
| Bundle extracted locally | yes | yes |
| Macros allowed (counter_risk_runner.xlsm) | yes (optional) | no |
| Read/write access to shared folder | yes | yes |
| Access to source data (N:\\ or equivalent) | no | yes |
| Access to output directory | read (to view results) | write |

---

## Step-by-Step

### 1. Set up the shared folder

Create a folder that both machines can read and write. For example:

```
\\server\shared\counter_risk_requests\
```

This is a request drop box — not the output location.

### 2. Start the worker

On the worker machine, open a Command Prompt, navigate to the bundle folder,
and run:

```
process_counter_risk_remote.cmd
```

When prompted, enter the shared request folder path. Leave the window open;
it polls every 30 seconds.

### 3. Submit a request

On the requesting machine, run:

```
request_counter_risk_remote.cmd
```

Enter:
- **As-of date**: e.g. `2025-12-31`
- **Mode**: `all`, `ex_trend`, or `trend`
- **Output directory**: where the worker should write results
  (must be writable by the worker; can be a UNC path or mapped drive)
- **Input root** *(optional)*: override for the worker's input data root
- **Shared request folder**: same path configured on the worker

The script writes a `.request` file to the shared folder and exits.

### 4. Monitor progress

The worker console shows one line per request as it processes:

```
[14:03:22] Found: counter_risk_2025-12-31_all_20260101_140300.request
[14:03:22] Running: all / 2025-12-31
[14:03:22] Output:  \\server\shared\outputs\2025-12
[14:08:45] DONE:   counter_risk_2025-12-31_all_20260101_140300
```

The `.request` file is renamed to `.done` on success or `.failed` on error.

### 5. Retrieve results

Check the output directory you specified in step 3. A successful run produces:

```
<output_dir>/
  manifest.json
  DATA_QUALITY_SUMMARY.txt
  distribution_static/      <- updated PPT outputs
  *.xlsx                    <- updated historical workbooks
```

---

## Request File Format

Request files are plain text (`key=value`, one per line):

```
as_of_date=2025-12-31
mode=all
output_dir=\\server\shared\outputs\2025-12
input_root=N:\Data\CounterRisk
requested_by=jsmith
requested_at=Sat 01/03/2026 14:03:00.12
```

`input_root` is optional. If omitted, the worker uses the bundle folder as
the input root (appropriate when data is co-located with the bundle).

---

## Request File Lifecycle

| Extension | Meaning |
|---|---|
| `.request` | Pending — waiting to be picked up |
| `.processing` | Claimed by a worker — run in progress |
| `.done` | Completed successfully |
| `.failed` | Run failed — check worker console output |

If a worker crashes mid-run, the file stays as `.processing`. Rename it back
to `.request` manually to resubmit.

---

## Troubleshooting

**"Could not write request file"**
The requester does not have write access to the shared folder. Check folder
permissions.

**Request stays as `.request` indefinitely**
The worker is not running, or it is watching a different folder path. Verify
the worker console shows the correct path and is still running.

**Request is renamed to `.failed`**
The worker encountered an error running the pipeline. Check the worker console
for the error message. Common causes:
- `as_of_date` format is wrong (must be `YYYY-MM-DD`)
- `output_dir` path is not writable by the worker machine
- Source data files are missing or path is incorrect
- License or configuration issue on the worker machine

**Two workers processing the same request**
The `.processing` rename is atomic on Windows NTFS shares. If two workers race,
one rename will fail and that worker will skip the file. Running multiple
workers against the same folder is safe for testing but not recommended for
production without additional coordination.
