"""Minimal ELF byte strings for tests that need a real-looking mission
binary header without a compiled executable."""

EM_X86_64 = 62
EM_AARCH64 = 183


def fake_elf(machine: int, size: int = 64) -> bytes:
    """A little-endian ELF64 header for `machine`, zero-padded to `size`."""
    header = (
        b"\x7fELF"
        + bytes([2, 1, 1])  # ELFCLASS64, ELFDATA2LSB, EV_CURRENT
        + bytes(9)  # EI_OSABI .. EI_PAD
        + (2).to_bytes(2, "little")  # e_type = ET_EXEC
        + machine.to_bytes(2, "little")  # e_machine
    )
    return header + bytes(max(size, 64) - len(header))
