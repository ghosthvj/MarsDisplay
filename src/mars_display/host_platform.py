"""Passive host admission policy; no runtime construction or host probing."""


def is_supported_host(system: str, machine: str, pointer_size: int) -> bool:
    """Admit Windows/Linux x64 with a 64-bit process (pointer size in bytes)."""
    return (system in {"win32", "linux"} and machine.lower() in {"amd64", "x86_64"}
            and pointer_size == 8)


def is_non_root_user(real_uid: int, effective_uid: int) -> bool:
    """Fail closed unless both Linux credentials are known non-root UIDs."""
    return (type(real_uid) is int and type(effective_uid) is int
            and real_uid > 0 and effective_uid > 0)
