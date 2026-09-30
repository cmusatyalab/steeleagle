import pytest

from app.mission_binary import elf_arch
from tests.elf_fixtures import EM_AARCH64, EM_X86_64, fake_elf


def test_elf_arch_amd64():
    assert elf_arch(fake_elf(EM_X86_64)) == "amd64"


def test_elf_arch_arm64():
    assert elf_arch(fake_elf(EM_AARCH64)) == "arm64"


def test_elf_arch_big_endian_header():
    data = bytearray(fake_elf(0))
    data[5] = 2  # ELFDATA2MSB
    data[18:20] = EM_AARCH64.to_bytes(2, "big")
    assert elf_arch(bytes(data)) == "arm64"


@pytest.mark.parametrize(
    "data",
    [b"", b"\x7fELF", b"#!/bin/sh\necho not a mission binary at all\n", bytes(64)],
)
def test_elf_arch_rejects_non_elf(data):
    with pytest.raises(ValueError, match="not an ELF"):
        elf_arch(data)


def test_elf_arch_rejects_unsupported_machine():
    with pytest.raises(ValueError, match="unsupported"):
        elf_arch(fake_elf(3))  # EM_386
