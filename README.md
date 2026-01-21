# PingInfo

PingInfo is a lightweight, cross-platform CLI alternative to NirSoft's PingInfoView.
It pings multiple hosts concurrently and prints latency and status in a compact table.

## Features

- Concurrent pings with per-host status and reverse DNS lookup
- Cross-platform (Windows, macOS, Linux)
- Configurable interval, timeout, and count

## Quick start

```bash
python -m pinginfo --hosts example.com 1.1.1.1
```

## GUI

```bash
python -m pinginfo.gui
```

## Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
pinginfo --hosts example.com 1.1.1.1 --interval 1.0 --timeout 1.5 --count 5
```

## Notes

- ICMP permissions vary by OS. On some systems, ping requires elevated privileges.
- This tool uses the system `ping` command for compatibility.
