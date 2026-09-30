"""Identifies which architecture a compiled mission binary targets, from its
ELF header, so uploads never depend on filenames or operator labels."""

MAX_MISSION_SIZE = 128 * 1024 * 1024

# ELF e_machine -> GOARCH
_ELF_MACHINES = {62: "amd64", 183: "arm64"}


def elf_arch(data: bytes) -> str:
    """Returns the GOARCH `data` was built for. Raises ValueError if it isn't
    an ELF file or targets an unsupported machine."""
    if len(data) < 20 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF executable")
    byteorder = {1: "little", 2: "big"}.get(data[5])
    if byteorder is None:
        raise ValueError("not an ELF executable (unknown byte order)")
    machine = int.from_bytes(data[18:20], byteorder)
    arch = _ELF_MACHINES.get(machine)
    if arch is None:
        raise ValueError(f"unsupported ELF machine type {machine}")
    return arch
