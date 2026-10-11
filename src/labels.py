"""Shared normalization for common benign and attack labels."""
from __future__ import annotations


def canonical_label(value: object) -> str:
    """Map common dataset labels to the dashboard's canonical attack classes."""
    label = str(value).strip().lower()
    compact = label.replace("_", " ").replace("-", " ")
    if compact in {"normal", "normal.", "benign", "benign.", "benign traffic", "legitimate", "0", "false"}:
        return "normal"
    if any(token in compact for token in ("ddos", "dos", "denial of service", "slowloris", "slow http", "hulk", "goldeneye", "syn flood", "udp flood")):
        return "dos"
    if any(token in compact for token in ("probe", "portscan", "port scan", "scan", "reconnaissance")):
        return "probe"
    if any(token in compact for token in ("u2r", "privilege", "escalation", "rootkit", "local exploit")):
        return "u2r"
    if any(token in compact for token in ("r2l", "remote to local", "brute", "patator", "credential", "password", "ftp write", "ssh attack")):
        return "r2l"
    return "other"
