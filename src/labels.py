"""Shared normalization for common benign and attack labels."""
from __future__ import annotations

import re


def canonical_label(value: object) -> str:
    """Map known labels to classes without substring false positives."""
    compact = re.sub(r"[^a-z0-9]+", " ", str(value).strip().casefold()).strip()
    tokens = set(compact.split())

    if compact in {"normal", "normal traffic", "benign", "benign traffic", "legitimate", "0", "false"}:
        return "normal"

    dos_tokens = {"ddos", "dos", "slowloris", "hulk", "goldeneye", "synflood", "udpflood"}
    dos_phrases = ("denial of service", "slow http", "syn flood", "udp flood")
    if tokens & dos_tokens or any(phrase in compact for phrase in dos_phrases):
        return "dos"

    probe_tokens = {"probe", "portscan", "scan", "reconnaissance", "ipsweep", "nmap", "portsweep", "mscan", "saint", "satan"}
    if tokens & probe_tokens or "port scan" in compact:
        return "probe"

    u2r_tokens = {"u2r", "rootkit", "loadmodule", "perl"}
    if tokens & u2r_tokens or "privilege escalation" in compact or "local exploit" in compact or "buffer overflow" in compact:
        return "u2r"

    r2l_tokens = {"r2l", "brute", "bruteforce", "patator", "credential", "password", "phf", "imap", "multihop", "warezclient", "warezmaster", "spy"}
    if tokens & r2l_tokens or "remote to local" in compact or "ftp write" in compact or "ssh attack" in compact:
        return "r2l"

    other_tokens = {
        "other", "attack", "attacks", "malicious", "threat", "intrusion",
        "infiltration", "bot", "botnet", "heartbleed", "exploit", "exploitkit",
        "sql", "xss", "custom",
    }
    if tokens & other_tokens or "custom threat" in compact or "unknown attack" in compact:
        return "other"

    # Keep ambiguous labels separate from attacks. Callers that forecast must
    # explicitly reject this value rather than counting it as an attack.
    return "unclassified"
