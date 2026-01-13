# nw-check

## Requirements

### Functional Requirements

- Collect LLDP neighbor information from target devices via SNMP and build an As-Is view of links.
- Compare As-Is links against To-Be wiring definitions and classify mismatches or gaps.
- Output human-reviewable tabular reports for:
  - As-Is observed links
  - To-Be vs As-Is diff results with explicit reasoning
  - Summary of failures, missing data, and mismatches
- Support CSV inputs for device inventory and To-Be wiring.
- Make missing or uncertain data explicit (e.g., unknown device, partial observation).

### Non-Functional Requirements

- Operate on Linux/WSL/Windows with Python runtime.
- Handle multi-vendor devices and LLDP schema differences without failing the entire run.
- Keep output deterministic with stable sorting.
- Avoid double counting of the same physical link.

## Assumptions / Non-goals

- Graphical diagrams are optional; if implemented, Mermaid text output only and treated as auxiliary.
- No continuous discovery; only manual execution for initial build and wiring changes.
- No real-time correlation with interface state (up/down) beyond LLDP availability.
- No vendor-specific proprietary discovery beyond standard LLDP-MIB in initial scope.
- SNMPv1, v2c, and v3 are supported for LLDP collection.

## Data Model

### Normalized Common Schema

- **Device**
  - `name`: canonical device name from inventory
  - `mgmt_ip`: management IP address
- `snmp`: version and credentials (community for v1/v2c, user/auth/priv for v3)
- **Interface**
  - `device`: canonical device name
  - `name_raw`: raw interface name
  - `name_norm`: normalized interface name
- **LinkObservation (As-Is)**
  - `local_device`
  - `local_port_raw`
  - `local_port_norm`
  - `remote_device_id`: raw chassis ID or system name
  - `remote_device_name`: resolved canonical device name if mapped
  - `remote_port_raw`
  - `remote_port_norm`
  - `source`: `lldp`
  - `confidence`: `observed` | `partial` | `unknown`
  - `errors`: list of error codes if partial
- **LinkIntent (To-Be)**
  - `device_a`, `port_a_raw`, `port_a_norm`
  - `device_b`, `port_b_raw`, `port_b_norm`
- **LinkDiff**
  - `tobe_link`: LinkIntent reference
  - `asis_link`: LinkObservation reference or `null`
  - `status`: match category
  - `reason`: textual reasoning

## Collection Design (SNMP LLDP)

### Standard LLDP-MIB

- `lldpRemTable` (LLDP-MIB::lldpRemTable)
  - Remote chassis ID
  - Remote port ID
  - Remote system name (if available)
- `lldpLocPortTable` (LLDP-MIB::lldpLocPortTable)
  - Local port ID and description

### Fields to Collect

- Local port identifier and description
- Remote chassis ID (type + value)
- Remote port ID (type + value)
- Remote system name

### Missing Data Handling

- If remote system name missing: keep `remote_device_id` and mark `remote_device_name` as `unknown`.
- If remote port ID missing: mark `remote_port_*` as `unknown` and set `confidence` to `partial`.
- If LLDP tables fail to return: record device-level collection failure.

### Error Classification

- `SNMP_TARGET_UNREACHABLE`
- `SNMP_AUTH_FAILED`
- `SNMP_MIB_MISSING`
- `SNMP_COMMAND_MISSING`
- `SNMP_COMMAND_FAILED`
- `SNMP_UNKNOWN_ERROR`
- `LLDP_TABLE_EMPTY`
- `LLDP_PARTIAL_ROW`

## Normalization Rules

- Interface name normalization:
  - Case-insensitive.
  - Map vendor-specific abbreviations (e.g., `Eth`, `Ethernet`, `Gi`, `GigabitEthernet`).
  - Remove whitespace and standardize delimiters (`Eth1/1` style).
- Device identity normalization:
  - Prefer inventory device name as canonical.
  - Resolve LLDP `sysName` to inventory using exact match or configured alias map.
    - Device inventory can include an `aliases` column with comma-separated names.
  - If only chassis ID is available, keep as `remote_device_id` and mark uncertainty.

## Link Inference + Deduplication

- Treat each LLDP row as a directional observation.
- Deduplicate by canonicalized key:
  - `(device_a, port_a_norm, device_b, port_b_norm)` with lexicographic ordering of device/port pairs.
- If both directions observed:
  - Merge into one link with `confidence=observed` and store evidence list.
- If only one direction observed:
  - Keep single link with `confidence=partial`.

## To-Be vs As-Is Diff Logic

### Match Categories

- `EXACT_MATCH`: devices and ports match after normalization.
- `PORT_MISMATCH`: devices match, ports differ.
- `DEVICE_MISMATCH`: ports match, devices differ.
- `MISSING_ASIS`: no As-Is observation for To-Be link.
- `PARTIAL_OBSERVED`: As-Is is partial; device or port unknown.
- `UNKNOWN`: ambiguous or conflicting matches.

### Matching Priority

1. Exact match on normalized device + port pairs.
2. Device match with any port mismatch evidence.
3. Port match with device mismatch evidence.
4. Partial matches using chassis ID or remote system name if ambiguous.

### Uncertainty 표현

- If remote device name is unresolved, report `PARTIAL_OBSERVED` with `reason` including the raw chassis ID.
- If multiple As-Is candidates match a To-Be link, report `UNKNOWN` with candidates listed.

## CLI / Config Spec

### Command Examples

- `nw-check --devices devices.csv --tobe tobe.csv --out-dir out/`

### Getting Started

1. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `python -m pip install -e .[dev]`
2. Ensure the `snmpwalk` CLI is available on your PATH for LLDP collection.
3. Run the CLI with your inventory and intent CSVs:
   - `nw-check --devices devices.csv --tobe tobe.csv --out-dir out/`

### Device Inventory CSV

Columns:
- `name` (required)
- `mgmt_ip` (required)
- `snmp_version` (required; `1`, `2c`, or `3`)
- `snmp_community` (required for SNMPv1/v2c)
- `snmp_user` (required for SNMPv3)
- `snmp_auth` (optional for SNMPv3, format `protocol:secret`, e.g. `sha:authpass`)
- `snmp_priv` (optional for SNMPv3, format `protocol:secret`, e.g. `aes:privpass`)
- `aliases` (optional, comma-separated)

### Development Commands

- Tests: `python -m pytest`
- Lint: `python -m pylint nw_check`
- Format: `python -m ruff format`
- Static analysis: `python -m mypy nw_check`

### Continuous Integration

- GitHub Actions runs formatting checks, linting, type checks, tests, and pre-commit hooks on
  pushes and pull requests.

### Arguments

- `--devices`: path to device inventory CSV
- `--tobe`: path to To-Be wiring CSV
- `--out-dir`: output directory
- `--snmp-timeout`: SNMP timeout seconds
- `--snmp-retries`: SNMP retries
- `--snmp-verbose`: enable verbose SNMP command logging (secrets redacted)
- `--log-level`: `INFO` | `DEBUG` | `WARN`

### Exit Codes

- `0`: success, no critical errors
- `2`: partial success with collection failures
- `3`: invalid input or unrecoverable error

## Output Formats + Examples

### As-Is Links (CSV)

Columns:
- `local_device`, `local_port`, `remote_device`, `remote_port`, `confidence`, `evidence`

Example:
```
leaf01,Eth1/1,spine01,Eth1/1,observed,lldp
leaf02,Eth1/1,unknown,unknown,partial,lldp:missing_remote
```

### To-Be vs As-Is Diff (CSV)

Columns:
- `device_a`, `port_a`, `device_b`, `port_b`, `status`, `reason`

Example:
```
leaf01,Eth1/1,spine01,Eth1/1,EXACT_MATCH,normalized ports matched
leaf02,Eth1/1,spine01,Eth1/2,PORT_MISMATCH,remote port differs: Eth1/3
leaf01,Eth1/2,leaf02,Eth1/2,MISSING_ASIS,no lldp observation
```

### Summary (Text)

- `lldp_failed_devices`: list of device names
- `missing_ports`: count of unknown remote ports
- `mismatch_links`: count of non-EXACT_MATCH

Sorting:
- Sort by `local_device`, `local_port`, then `remote_device` for As-Is.
- Sort by `device_a`, `port_a`, `device_b`, `port_b` for To-Be diff.

## Test Plan

### Unit Tests

- Normalize interface names (abbreviation mapping and case handling).
- Deduplication logic for bidirectional observations.
- Diff classification for each category.

### Sample Input Expectations

- Use provided sample CSVs in `samples/` to validate:
  - Exact match detection
  - Port mismatch detection
  - Missing As-Is link detection
  - Partial observation handling when sysName is absent

## Implementation Plan

### Modules

- `nw_check.cli`: CLI parsing and entrypoint
- `nw_check.inventory`: device CSV parsing
- `nw_check.lldp_snmp`: SNMP collection and LLDP parsing
- `nw_check.normalize`: normalization utilities
- `nw_check.link_infer`: inference and deduplication
- `nw_check.diff`: To-Be vs As-Is comparison
- `nw_check.output`: CSV/text report rendering

### Dependencies

- `pysnmp` for SNMP collection
- `pydantic` (optional) for schema validation
- `rich` (optional) for table output in terminal

### Logging

- Structured logs with device context and error codes.
- Debug logs for raw LLDP rows.

## Optional: Graph Output

- Mermaid `graph LR` output only.
- Limit to a configurable maximum number of nodes (default 50).
- Explicitly labeled as auxiliary and not authoritative.
