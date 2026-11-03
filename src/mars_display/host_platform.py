"""Passive host admission policy; no runtime construction or host probing."""


def is_supported_host(system: str, machine: str, pointer_size: int) -> bool:
    """Admit only Windows x64 with a 64-bit process (pointer size in bytes)."""
    return (system == "win32" and machine.lower() in {"amd64", "x86_64"}
            and pointer_size == 8)
