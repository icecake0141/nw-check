<!--
Copyright 2025 nw-check contributors
SPDX-License-Identifier: Apache-2.0

This file was created or modified with the assistance of an AI (Large Language Model).
Review required for correctness, security, and licensing.
-->

# nw-check

English | [日本語](README.ja.md)

**nw-check** is a network wiring validation tool that uses LLDP (Link Layer Discovery Protocol) to verify that your network cabling matches your intended design. It compares the actual physical connections (discovered via SNMP) against your expected wiring plan (defined in CSV files) and highlights any discrepancies.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation & Prerequisites](#installation--prerequisites)
  - [System Requirements](#system-requirements)
  - [Installing Python Dependencies](#installing-python-dependencies)
  - [Installing SNMP Tools](#installing-snmp-tools)
- [Basic Usage](#basic-usage)
  - [Preparing Input Files](#preparing-input-files)
  - [Running Your First Check](#running-your-first-check)
  - [Understanding the Output](#understanding-the-output)
- [Advanced Features](#advanced-features)
  - [Dry-Run Mode](#dry-run-mode)
  - [Filtering Output](#filtering-output)
  - [Output Formats](#output-formats)
  - [Generating Network Diagrams](#generating-network-diagrams)
  - [Supervisor Mode with Web Control](#supervisor-mode-with-web-control)
- [Common Issues & Troubleshooting](#common-issues--troubleshooting)
- [Complete Reference](#complete-reference)
  - [Device Inventory CSV Format](#device-inventory-csv-format)
  - [To-Be Wiring CSV Format](#to-be-wiring-csv-format)
  - [All CLI Arguments](#all-cli-arguments)
  - [Exit Codes](#exit-codes)
  - [Output File Formats](#output-file-formats)
- [Technical Details](#technical-details)
  - [Requirements](#requirements)
  - [Data Model](#data-model)
  - [Collection Design (SNMP LLDP)](#collection-design-snmp-lldp)
  - [Normalization Rules](#normalization-rules)
  - [Link Inference + Deduplication](#link-inference--deduplication)
  - [To-Be vs As-Is Diff Logic](#to-be-vs-as-is-diff-logic)
- [Development](#development)
  - [Development Commands](#development-commands)
  - [Test Plan](#test-plan)
  - [Implementation Plan](#implementation-plan)

## Quick Start

**For impatient users** — here's how to get started in 3 steps:

1. **Install prerequisites**:
   ```bash
   # On Ubuntu/Debian
   sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv snmp
   
   # On macOS with Homebrew
   brew install python3 net-snmp
   
   # On Windows (WSL recommended)
   # Use WSL and follow Ubuntu instructions
   ```

2. **Install nw-check**:
   ```bash
   git clone https://github.com/icecake0141/nw-check.git
   cd nw-check
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Run a check**:
   ```bash
   nw-check --devices samples/devices.csv --tobe samples/tobe.csv --out-dir output/
   ```

Check the `output/` directory for results!

## Installation & Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows with WSL (Windows Subsystem for Linux)
- **Python**: Version 3.10 or later
- **SNMP Tools**: The `snmpwalk` command-line tool (from net-snmp package)
- **Network Access**: Ability to reach network devices via SNMP

### Installing Python Dependencies

**Using a Virtual Environment (Recommended)**:

A virtual environment keeps your Python packages isolated and prevents conflicts with system packages.

```bash
# Clone the repository
git clone https://github.com/icecake0141/nw-check.git
cd nw-check

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install nw-check and its dependencies
pip install -e .

# For development (includes testing and linting tools):
pip install -e .[dev]
```

**Verifying the Installation**:

```bash
# Check that nw-check is installed
nw-check --help

# You should see the help message with available options
```

### Installing SNMP Tools

The tool requires the `snmpwalk` command to query network devices.

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install -y snmp
```

**CentOS/RHEL/Fedora**:
```bash
sudo yum install -y net-snmp-utils
# or on newer systems:
sudo dnf install -y net-snmp-utils
```

**macOS (with Homebrew)**:
```bash
brew install net-snmp
```

**Windows**:
- **Recommended**: Use WSL (Windows Subsystem for Linux) and follow the Ubuntu instructions above
- **Alternative**: Install net-snmp for Windows from unofficial sources (not recommended for production use)

**Verifying SNMP Tools**:
```bash
# Check that snmpwalk is available
snmpwalk -V

# You should see version information like:
# NET-SNMP version: 5.9.1
```

## Basic Usage

### Preparing Input Files

You need two CSV files to run nw-check:

1. **Device Inventory** (`devices.csv`): Lists your network devices and their SNMP credentials
2. **To-Be Wiring** (`tobe.csv`): Defines your intended network connections

**Example Device Inventory** (`devices.csv`):
```csv
name,mgmt_ip,snmp_version,snmp_community,snmp_user,snmp_auth,snmp_priv
leaf01,10.0.0.1,2c,public,,,
spine01,10.0.0.2,3,,snmpuser,sha:authpass,aes:privpass
spine02,10.0.0.3,3,,snmpuser,SHA-256:authpass,AES-256:privpass
```

- For SNMPv1/v2c devices: provide `snmp_community`
- For SNMPv3 devices: provide `snmp_user`, `snmp_auth` (optional), and `snmp_priv` (optional)

**Example To-Be Wiring** (`tobe.csv`):
```csv
device_a,port_a,device_b,port_b
leaf01,Eth1/1,spine01,Eth1/1
leaf01,Eth1/2,spine02,Eth1/1
```

Each row represents one physical link between two devices.

**Sample files** are available in the `samples/` directory for reference.

### Running Your First Check

```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/
```

**What happens**:
1. The tool reads your device inventory and To-Be wiring files
2. It connects to each device via SNMP and collects LLDP neighbor information
3. It compares the actual connections (As-Is) with your intended design (To-Be)
4. It generates reports in the `output/` directory

**Tip**: Add `--show-progress` to see what the tool is doing:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --show-progress
```

### Understanding the Output

After running nw-check, you'll find these files in your output directory:

1. **`asis_links.csv`**: All physical connections discovered via LLDP
   - Shows what's actually connected in your network
   - Includes confidence level (`observed`, `partial`, `unknown`)

2. **`diff_links.csv`**: Comparison between To-Be and As-Is
   - Shows whether each intended link matches reality
   - Status values:
     - `EXACT_MATCH`: Perfect match ✓
     - `PORT_MISMATCH`: Devices match, but ports are different
     - `DEVICE_MISMATCH`: Ports match, but devices are different
     - `MISSING_ASIS`: No actual connection found for this intended link
     - `PARTIAL_OBSERVED`: Connection found but incomplete information
     - `UNKNOWN`: Ambiguous or conflicting information

3. **`summary.txt`**: High-level overview
   - Lists devices where LLDP collection failed
   - Counts of mismatches and missing connections

**Interpreting Results**:

- Look for `status` values other than `EXACT_MATCH` in `diff_links.csv`
- Check the `reason` column for explanation of each mismatch
- Review `summary.txt` for devices with collection failures

## Advanced Features

### Dry-Run Mode

Dry-run mode lets you test changes to your To-Be wiring without re-querying network devices. This is useful for:
- Testing wiring definition changes
- Running in CI/CD pipelines
- Working offline

**Workflow**:

1. First, collect and save observations:
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --save-observations obs.json
   ```

2. Later, test with saved data:
   ```bash
   nw-check --devices devices.csv --tobe tobe-updated.csv --out-dir output/ --dry-run --load-observations obs.json
   ```

### Filtering Output

For large networks, filter the output to focus on specific devices or issues:

**Filter by device name**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-devices leaf01,leaf02
```

**Filter by device pattern**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-devices-regex "^leaf"
```

**Filter by status** (show only mismatches):
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --filter-status PORT_MISMATCH,MISSING_ASIS
```

**Combine filters**:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ \
  --filter-devices-regex "^spine" \
  --filter-status PORT_MISMATCH
```

### Output Formats

By default, nw-check generates CSV reports. You can also output JSON or both:

```bash
# JSON only
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --output-format json

# Both CSV and JSON
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --output-format both
```

JSON output is useful for:
- Integration with other tools and APIs
- Custom reporting scripts
- Programmatic processing

### Generating Network Diagrams

Generate a visual diagram of your network topology in Mermaid format:

```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --generate-mermaid
```

This creates `topology.mmd` which can be:
- Rendered in GitHub markdown
- Viewed with Mermaid-compatible tools
- Embedded in documentation

**Note**: The diagram is limited to 50 devices by default. Adjust with `--mermaid-max-nodes`:
```bash
nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --generate-mermaid --mermaid-max-nodes 100
```

### Supervisor Mode with Web Control

Run nw-check with a web-based control interface for pause/resume/terminate:

```bash
nw-check-supervisor --devices devices.csv --tobe tobe.csv --out-dir output/ --control-port 8080
```

Then open http://127.0.0.1:8080 in your browser to control the process.

**Security Note**: When binding to `0.0.0.0` (e.g., in Docker), use `--control-token` to require authentication:
```bash
nw-check-supervisor --devices devices.csv --tobe tobe.csv --out-dir output/ \
  --control-host 0.0.0.0 --control-port 8080 --control-token mysecrettoken
```

## Common Issues & Troubleshooting

### Problem: `snmpwalk: command not found`

**Solution**: Install SNMP tools as described in [Installing SNMP Tools](#installing-snmp-tools)

### Problem: `SNMP_TARGET_UNREACHABLE` errors

**Possible causes**:
- Network device IP is incorrect or unreachable
- Firewall blocking SNMP traffic (UDP port 161)
- Device is offline or not responding

**Solutions**:
1. Verify IP address is correct: `ping <device_ip>`
2. Check SNMP is enabled on the device
3. Test SNMP manually:
   ```bash
   # For SNMPv2c:
   snmpwalk -v2c -c public <device_ip> system
   
   # For SNMPv3:
   snmpwalk -v3 -u snmpuser -l authPriv -a SHA -A authpass -x AES -X privpass <device_ip> system
   ```

### Problem: `SNMP_AUTH_FAILED` errors

**Possible causes**:
- Wrong SNMP community string (v1/v2c)
- Wrong SNMPv3 credentials
- SNMPv3 protocol mismatch

**Solutions**:
1. Verify SNMP credentials in `devices.csv`
2. Check device SNMP configuration matches your credentials
3. For SNMPv3, ensure authentication and privacy protocols match device settings

### Problem: All links show `MISSING_ASIS`

**Possible causes**:
- LLDP not enabled on devices
- Device names in `tobe.csv` don't match names in `devices.csv`
- LLDP not running on the interfaces

**Solutions**:
1. Enable LLDP on network devices (check your device documentation)
2. Verify device names match exactly (case-sensitive)
3. Check interfaces are up and LLDP is transmitting: review `asis_links.csv`

### Problem: Port names don't match even though they look the same

**Cause**: Port normalization handles most variations, but some formats may not be recognized

**Solution**: 
- Check the `reason` field in `diff_links.csv` for details
- Port names are normalized (e.g., `Eth1/1`, `Ethernet1/1`, `eth1/1` are all treated as equivalent)
- If normalization isn't working, file an issue with your port name format

### Problem: Python `ModuleNotFoundError`

**Cause**: Virtual environment not activated or package not installed

**Solution**:
```bash
# Activate your virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Reinstall if needed
pip install -e .
```

### Problem: Partial observations or unknown devices

**Cause**: LLDP information incomplete (missing system name or chassis ID)

**Solution**:
- Check LLDP configuration on devices
- Some devices may not transmit all LLDP fields
- Add device `aliases` in `devices.csv` to help match chassis IDs

### Getting More Help

1. **Enable verbose logging**:
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --log-level DEBUG
   ```

2. **Enable SNMP command logging** (secrets are redacted):
   ```bash
   nw-check --devices devices.csv --tobe tobe.csv --out-dir output/ --snmp-verbose
   ```

3. **Check the Issues on GitHub**: [icecake0141/nw-check/issues](https://github.com/icecake0141/nw-check/issues)

## Complete Reference

### Device Inventory CSV Format

The device inventory CSV defines all network devices to be checked and their SNMP credentials.

**Required Columns**:
- `name`: Unique device name (used as identifier)
- `mgmt_ip`: Management IP address
- `snmp_version`: SNMP version (`1`, `2c`, or `3`)

**SNMPv1/v2c Columns**:
- `snmp_community`: Community string (required for v1/v2c)

**SNMPv3 Columns**:
- `snmp_user`: Username (required for v3)
- `snmp_auth`: Authentication protocol and passphrase (optional, format: `protocol:secret`)
- `snmp_priv`: Privacy protocol and passphrase (optional, format: `protocol:secret`)

**Optional Columns**:
- `aliases`: Comma-separated alternative names for the device (helps match LLDP system names)

#### SNMPv3 Authentication and Privacy Protocols

For SNMPv3, the `snmp_auth` and `snmp_priv` fields use the format `protocol:secret`.

**Supported Authentication Protocols** (case-insensitive):
- `MD5` - Message Digest 5
- `SHA` or `SHA1` - SHA-1
- `SHA-224` or `SHA224` - SHA-224 (with or without hyphen)
- `SHA-256` or `SHA256` - SHA-256 (with or without hyphen)
- `SHA-384` or `SHA384` - SHA-384 (with or without hyphen)
- `SHA-512` or `SHA512` - SHA-512 (with or without hyphen)

**Supported Privacy Protocols** (case-insensitive):
- `DES` - Data Encryption Standard
- `AES`, `AES128`, or `AES-128` - AES 128-bit (multiple variants accepted)
- `AES-192` or `AES192` - AES 192-bit (with or without hyphen)
- `AES-256` or `AES256` - AES 256-bit (with or without hyphen)

**Example CSV**:
```csv
name,mgmt_ip,snmp_version,snmp_community,snmp_user,snmp_auth,snmp_priv,aliases
leaf01,10.0.0.1,2c,public,,,,"leaf-1,leaf-one"
spine01,10.0.0.2,3,,snmpuser,sha:authpass,aes:privpass,spine-1
spine02,10.0.0.3,3,,snmpuser,SHA-256:authpass,AES-256:privpass,spine-2
leaf02,10.0.0.4,3,,snmpuser,md5:authpass,des:privpass,"leaf-2,leaf-two"
```

**Error Handling**:
If an unsupported protocol is specified, nw-check will log a clear error message indicating which device has the invalid configuration and list the supported protocols. The device will be skipped during LLDP collection.

### To-Be Wiring CSV Format

The To-Be wiring CSV defines the intended network link topology for validation.

**Required Columns**:
- `device_a`: Name of the first device (must match a device in the inventory)
- `port_a`: Port identifier on device_a (e.g., `Eth1/1`, `GigabitEthernet0/1`)
- `device_b`: Name of the second device (must match a device in the inventory)
- `port_b`: Port identifier on device_b (e.g., `Eth1/1`, `GigabitEthernet0/1`)

**Example CSV** (`tobe.csv`):
```csv
device_a,port_a,device_b,port_b
leaf01,Eth1/1,spine01,Eth1/1
leaf01,Eth1/2,spine02,Eth1/1
leaf02,Eth1/1,spine01,Eth1/2
leaf02,Eth1/2,spine02,Eth1/2
```

**Important Notes**:
- Port names will be normalized during comparison (handles vendor-specific abbreviations)
- The order of device_a/device_b doesn't matter; links are bidirectional
- Each row represents one physical link between two devices

### All CLI Arguments

**Required Arguments**:
- `--devices PATH`: Path to device inventory CSV file
- `--tobe PATH`: Path to To-Be wiring CSV file
- `--out-dir PATH`: Output directory for reports

**SNMP Options**:
- `--snmp-timeout SECONDS`: SNMP timeout in seconds (default varies)
- `--snmp-retries N`: Number of SNMP retries (default varies)
- `--snmp-verbose`: Enable verbose SNMP command logging (secrets are redacted)

**Output Options**:
- `--output-format FORMAT`: Output format: `csv`, `json`, or `both` (default: `csv`)
- `--show-progress`: Display progress during LLDP collection
- `--log-level LEVEL`: Logging level: `INFO`, `DEBUG`, or `WARN` (default: `INFO`)

**Dry-Run and Observation Management**:
- `--dry-run`: Skip SNMP collection and use saved observations (requires `--load-observations`)
- `--load-observations PATH`: Load observations from JSON file instead of collecting via SNMP
- `--save-observations PATH`: Save collected observations to JSON file for later dry-run use

**Filtering Options**:
- `--filter-devices NAMES`: Comma-separated list of device names to include in output
- `--filter-devices-regex PATTERN`: Regular expression pattern to filter devices (e.g., `"^leaf"`)
- `--filter-status STATUSES`: Comma-separated list of diff statuses to include (e.g., `PORT_MISMATCH,MISSING_ASIS`)
  - Available statuses: `EXACT_MATCH`, `PORT_MISMATCH`, `DEVICE_MISMATCH`, `MISSING_ASIS`, `PARTIAL_OBSERVED`, `UNKNOWN`

**Diagram Options**:
- `--generate-mermaid`: Generate Mermaid diagram of network topology
- `--mermaid-max-nodes N`: Maximum number of nodes in Mermaid diagram (default: 50)

**Supervisor-Specific Arguments** (for `nw-check-supervisor` command):
- `--control-host HOST`: Bind address for control server (default: `127.0.0.1`)
- `--control-port PORT`: Port for control server (default: `8080`)
- `--control-token TOKEN`: Optional shared secret for UI/API requests (recommended for `0.0.0.0` binding)
- `--shutdown-on-exit` / `--no-shutdown-on-exit`: Whether control server stops when nw-check exits
- `--terminate-timeout SECONDS`: Seconds to wait before force killing process group

### Exit Codes

- `0`: Success, no critical errors
- `2`: Partial success with collection failures (some devices failed LLDP collection)
- `3`: Invalid input or unrecoverable error (e.g., malformed CSV, missing required files)

### Output File Formats

#### As-Is Links (CSV)

**Filename**: `asis_links.csv`

**Columns**:
- `local_device`: Name of the local device
- `local_port`: Port on the local device
- `remote_device`: Name of the remote device (or "unknown")
- `remote_port`: Port on the remote device (or "unknown")
- `confidence`: Confidence level (`observed`, `partial`, `unknown`)
- `evidence`: Source of information (e.g., `lldp`, `lldp:missing_remote`)

**Example**:
```csv
local_device,local_port,remote_device,remote_port,confidence,evidence
leaf01,Eth1/1,spine01,Eth1/1,observed,lldp
leaf02,Eth1/1,unknown,unknown,partial,lldp:missing_remote
```

#### To-Be vs As-Is Diff (CSV)

**Filename**: `diff_links.csv`

**Columns**:
- `device_a`: First device in the intended link
- `port_a`: Port on device_a
- `device_b`: Second device in the intended link
- `port_b`: Port on device_b
- `status`: Match status (see below)
- `reason`: Explanation of the status

**Status Values**:
- `EXACT_MATCH`: Devices and ports match after normalization ✓
- `PORT_MISMATCH`: Devices match, but ports differ
- `DEVICE_MISMATCH`: Ports match, but devices differ
- `MISSING_ASIS`: No As-Is observation found for this To-Be link
- `PARTIAL_OBSERVED`: As-Is observation exists but is incomplete (unknown device or port)
- `UNKNOWN`: Ambiguous or conflicting matches

**Example**:
```csv
device_a,port_a,device_b,port_b,status,reason
leaf01,Eth1/1,spine01,Eth1/1,EXACT_MATCH,normalized ports matched
leaf02,Eth1/1,spine01,Eth1/2,PORT_MISMATCH,remote port differs: Eth1/3
leaf01,Eth1/2,leaf02,Eth1/2,MISSING_ASIS,no lldp observation
```

#### Summary (Text)

**Filename**: `summary.txt`

Contains:
- `lldp_failed_devices`: List of device names where LLDP collection failed
- `missing_ports`: Count of connections with unknown remote ports
- `mismatch_links`: Count of links with status other than `EXACT_MATCH`

#### JSON Output Format

When using `--output-format json` or `--output-format both`, the tool generates JSON files with the same structure as CSV files but in JSON format. This is useful for API integration and programmatic processing.

**Example As-Is Links JSON** (`asis_links.json`):
```json
[
  {
    "local_device": "leaf01",
    "local_port": "Eth1/1",
    "remote_device": "spine01",
    "remote_port": "Eth1/1",
    "confidence": "observed",
    "evidence": ["lldp"]
  }
]
```

#### Mermaid Diagram Output

**Filename**: `topology.mmd`

When using `--generate-mermaid`, generates a Mermaid diagram visualizing the network topology.

**Features**:
- Displays devices as nodes and links as edges
- Shows port labels on connections
- Color-codes devices based on diff status:
  - Green (`#ccffcc`): All links match To-Be
  - Red (`#ffcccc`): One or more mismatches
- Filters out "unknown" devices
- Limited to `--mermaid-max-nodes` devices

**Note**: The diagram is auxiliary and should not be considered authoritative.

## Technical Details

This section contains detailed technical information for developers and advanced users.

### Requirements

#### Functional Requirements

- Collect LLDP neighbor information from target devices via SNMP and build an As-Is view of links.
- Compare As-Is links against To-Be wiring definitions and classify mismatches or gaps.
- Output human-reviewable tabular reports for:
  - As-Is observed links
  - To-Be vs As-Is diff results with explicit reasoning
  - Summary of failures, missing data, and mismatches
- Support CSV inputs for device inventory and To-Be wiring.
- Make missing or uncertain data explicit (e.g., unknown device, partial observation).

#### Non-Functional Requirements

- Operate on Linux/WSL/Windows with Python runtime.
- Handle multi-vendor devices and LLDP schema differences without failing the entire run.
- Keep output deterministic with stable sorting.
- Avoid double counting of the same physical link.

#### Assumptions / Non-goals

- Graphical diagrams are optional; if implemented, Mermaid text output only and treated as auxiliary.
- No continuous discovery; only manual execution for initial build and wiring changes.
- No real-time correlation with interface state (up/down) beyond LLDP availability.
- No vendor-specific proprietary discovery beyond standard LLDP-MIB in initial scope.
- SNMPv1, v2c, and v3 are supported for LLDP collection.

### Data Model

#### Normalized Common Schema

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

### Collection Design (SNMP LLDP)

#### Standard LLDP-MIB

- `lldpRemTable` (LLDP-MIB::lldpRemTable)
  - Remote chassis ID
  - Remote port ID
  - Remote system name (if available)
- `lldpLocPortTable` (LLDP-MIB::lldpLocPortTable)
  - Local port ID and description

#### Fields to Collect

- Local port identifier and description
- Remote chassis ID (type + value)
- Remote port ID (type + value)
- Remote system name

#### Missing Data Handling

- If remote system name missing: keep `remote_device_id` and mark `remote_device_name` as `unknown`.
- If remote port ID missing: mark `remote_port_*` as `unknown` and set `confidence` to `partial`.
- If LLDP tables fail to return: record device-level collection failure.

#### Error Classification

- `SNMP_TARGET_UNREACHABLE`
- `SNMP_AUTH_FAILED`
- `SNMP_MIB_MISSING`
- `SNMP_COMMAND_MISSING`
- `SNMP_COMMAND_FAILED`
- `SNMP_UNKNOWN_ERROR`
- `LLDP_TABLE_EMPTY`
- `LLDP_PARTIAL_ROW`

### Normalization Rules

- Interface name normalization:
  - Case-insensitive.
  - Map vendor-specific abbreviations (e.g., `Eth`, `Ethernet`, `Gi`, `GigabitEthernet`).
  - Remove whitespace and standardize delimiters (`Eth1/1` style).
- Device identity normalization:
  - Prefer inventory device name as canonical.
  - Resolve LLDP `sysName` to inventory using exact match or configured alias map.
    - Device inventory can include an `aliases` column with comma-separated names.
  - If only chassis ID is available, keep as `remote_device_id` and mark uncertainty.

### Link Inference + Deduplication

- Treat each LLDP row as a directional observation.
- Deduplicate by canonicalized key:
  - `(device_a, port_a_norm, device_b, port_b_norm)` with lexicographic ordering of device/port pairs.
- If both directions observed:
  - Merge into one link with `confidence=observed` and store evidence list.
- If only one direction observed:
  - Keep single link with `confidence=partial`.

### To-Be vs As-Is Diff Logic

#### Match Categories

- `EXACT_MATCH`: devices and ports match after normalization.
- `PORT_MISMATCH`: devices match, ports differ.
- `DEVICE_MISMATCH`: ports match, devices differ.
- `MISSING_ASIS`: no As-Is observation for To-Be link.
- `PARTIAL_OBSERVED`: As-Is is partial; device or port unknown.
- `UNKNOWN`: ambiguous or conflicting matches.

#### Matching Priority

1. Exact match on normalized device + port pairs.
2. Device match with any port mismatch evidence.
3. Port match with device mismatch evidence.
4. Partial matches using chassis ID or remote system name if ambiguous.

#### Uncertainty Representation

- If remote device name is unresolved, report `PARTIAL_OBSERVED` with `reason` including the raw chassis ID.
- If multiple As-Is candidates match a To-Be link, report `UNKNOWN` with candidates listed.

## Development

This section is for developers contributing to nw-check.

### Development Commands

**Run Tests**:
```bash
python -m pytest
```

**Lint Code**:
```bash
python -m pylint nw_check
```

**Format Code**:
```bash
python -m ruff format
```

**Type Checking**:
```bash
python -m mypy nw_check
```

### Continuous Integration

GitHub Actions runs formatting checks, linting, type checks, tests, and pre-commit hooks on pushes and pull requests.

### Test Plan

#### Unit Tests

- Normalize interface names (abbreviation mapping and case handling).
- Deduplication logic for bidirectional observations.
- Diff classification for each category.

#### Sample Input Expectations

- Use provided sample CSVs in `samples/` to validate:
  - Exact match detection
  - Port mismatch detection
  - Missing As-Is link detection
  - Partial observation handling when sysName is absent

### Implementation Plan

#### Modules

- `nw_check.cli`: CLI parsing and entrypoint
- `nw_check.inventory`: device CSV parsing
- `nw_check.lldp_snmp`: SNMP collection and LLDP parsing
- `nw_check.normalize`: normalization utilities
- `nw_check.link_infer`: inference and deduplication
- `nw_check.diff`: To-Be vs As-Is comparison
- `nw_check.output`: CSV/text report rendering
- `nw_check.mermaid`: Mermaid diagram generation
- `nw_check.filters`: output filtering utilities
- `nw_check.supervisor`: web control interface

#### Dependencies

- Python 3.10 or later
- `snmpwalk` CLI command (from net-snmp package) for SNMP/LLDP collection
  - Must be available on your system PATH
  - Used to query LLDP-MIB tables from network devices

#### Logging

- Structured logs with device context and error codes.
- Debug logs for raw LLDP rows.

---

**Questions or Issues?** Please visit the [GitHub Issues page](https://github.com/icecake0141/nw-check/issues).
