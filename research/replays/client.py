"""Decryption of replay packet fields with the client's own code, without running it.

    pip install pefile capstone unicorn
    python research/replays/client.py "C:/Riot Games/League of Legends/Game/League of Legends.exe"

It is all analysis of the executable on disk: the code in the .text section is in the clear
(normal entropy and 25,000 function prologues), so there is no need to open the game
or touch Vanguard. Patch 16.18:

- Packet registry: a function (REGISTER) receives (registry, context, packet id
  in r8d, handler in r9). Each call is preceded by `mov r8d, id` and by an
  `lea rax, [rip + handler]` that is stored as a function pointer. 284 ids; those for
  position and movement (0x0181, 0x007d, 0x004c, 0x00ab, 0x043e) do not go through here.
- The handlers copy the raw field to the stack and decrypt it byte by byte, with an
  auxiliary function (e.g. 0x14024ec10) or inline (additions, NOT, bit swapping with
  masks 0xd5/0x55, rotations, XOR and 256-byte tables in .rdata). Each field has
  its own chain. Emulating the chain with the 256 values gives its table.
- Integers go as varint (LEB128) after decryption: the purchase's item id
  (0x033a) comes out right in 535 of 538 purchases from two matches with the table of
  0x14024ec10.

Addresses change with every patch: REGISTER and the auxiliaries are searched for again.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_MODE_64, Uc
from unicorn.x86_const import UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RSP

REGISTER = 0x140709470  # patch 16.18
ITEM_BYTE_DECODER = 0x14024ec10  # field +0x70 of the purchase packet (item id)
_STACK, _RETURN = 0x7000_0000, 0x6000_0000


class Client:
    def __init__(self, exe: Path) -> None:
        self.pe = pefile.PE(str(exe), fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.image = self.pe.get_memory_mapped_image()
        text = next(s for s in self.pe.sections if s.Name.startswith(b".text"))
        self.text = (text.VirtualAddress, text.Misc_VirtualSize)
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self._uc: Uc | None = None

    def registrations(self) -> dict[int, int | None]:
        """packet id → address of its handler (None if it doesn't resolve)."""
        start, size = self.text
        code = self.image[start : start + size]
        sites = [start + m.start() for m in re.finditer(b"\xe8", code)
                 if start + m.start() + 5 + struct.unpack_from("<i", code, m.start() + 1)[0] == REGISTER - self.base]
        out: dict[int, int | None] = {}
        for site in sites:
            ins = [x for x in self.md.disasm(self.image[site - 400 : site + 5], self.base + site - 400) if x.address <= self.base + site]
            cut = max((i for i, x in enumerate(ins[:-1]) if x.mnemonic == "call" and x.op_str == hex(REGISTER)), default=-1)
            ins = ins[cut + 1 :]
            ids = [x for x in ins if x.mnemonic == "mov" and x.op_str.startswith("r8d, ")]
            try:
                packet = int(ids[-1].op_str.split(", ")[1], 0)
            except (IndexError, ValueError):
                continue
            handlers = [x.address + x.size + int(x.op_str.split("+ ")[1].rstrip("]"), 16) for x in ins
                        if x.mnemonic == "lea" and x.op_str.startswith("rax, [rip + ")]
            handlers = [h for h in handlers if start <= h - self.base < start + size]
            out[packet] = handlers[0] if handlers else None
        return out

    def byte_table(self, decoder: int) -> list[int]:
        """256-entry table of an auxiliary function that decrypts one byte (enters in cl, leaves in al)."""
        if self._uc is None:
            self._uc = Uc(UC_ARCH_X86, UC_MODE_64)
            self._uc.mem_map(self.base, (len(self.image) + 0xFFF) & ~0xFFF)
            self._uc.mem_write(self.base, self.image)
            self._uc.mem_map(_STACK - 0x10000, 0x20000)
            self._uc.mem_map(_RETURN, 0x1000)
        table = []
        for value in range(256):
            rsp = _STACK - 0x100
            self._uc.mem_write(rsp, _RETURN.to_bytes(8, "little"))
            self._uc.reg_write(UC_X86_REG_RSP, rsp)
            self._uc.reg_write(UC_X86_REG_RCX, value)
            self._uc.emu_start(decoder, _RETURN, count=10_000)
            table.append(self._uc.reg_read(UC_X86_REG_RAX) & 0xFF)
        return table


def varint(payload: bytes, pos: int, table: list[int]) -> tuple[int, int]:
    """LEB128 integer decrypting each byte with `table`. Returns (value, next position)."""
    value = shift = 0
    while True:
        byte = table[payload[pos]]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def main() -> None:
    client = Client(Path(sys.argv[1]))
    handlers = client.registrations()
    print(f"{len(handlers)} packets registered, {sum(h is not None for h in handlers.values())} with a handler")
    table = client.byte_table(ITEM_BYTE_DECODER)
    assert sorted(table) == list(range(256)), "decrypting a byte should be a bijection"
    # Control Ward (2055) in a real purchase of 16.18: bytes 12-13 of the packet = 71 3f
    assert varint(bytes.fromhex("713f"), 0, table)[0] == 2055
    print("item id: table at 0x14024ec10 is right (Control Ward = 2055)")


if __name__ == "__main__":
    main()
