import ctypes
import struct
import platform
import json
import base64
import time

# Keccak-f[1600] Round Constants
RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008
]

# Keccak-f[1600] Rotation Offsets
ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14]
]


def _build_x86_64_jit_solver():
    """Generates x86_64 machine code for 23-round Keccak-f[1600] solver."""
    code = bytearray()

    # Prologue: save non-volatile registers
    code.extend(b"\x53\x55\x57\x56\x41\x54\x41\x55\x41\x56\x41\x57")
    # sub rsp, 704
    code.extend(b"\x48\x81\xec\xc0\x02\x00\x00")

    # mov r12, rcx (prefix_ptr); mov r13, rdx (prefix_len); mov r14, r8 (target_ptr); mov r15, r9 (difficulty)
    code.extend(b"\x49\x89\xcc\x49\x89\xd5\x4d\x89\xc6\x4d\x89\xcf")

    # xor rbx, rbx (nonce = 0)
    code.extend(b"\x48\x31\xdb")

    # LOOP_START:
    loop_start_offset = len(code)

    # cmp rbx, r15
    code.extend(b"\x4c\x39\xfb")
    jg_not_found_idx = len(code)
    code.extend(b"\x0f\x8f\x00\x00\x00\x00")  # placeholder for jg NOT_FOUND

    # Zero out buffer [rsp + 480] (200 bytes)
    code.extend(b"\x48\x8d\xbc\x24\xe0\x01\x00\x00\x31\xc0\xb9\x19\x00\x00\x00\xf3\x48\xab")

    # Copy prefix to buffer
    code.extend(b"\x48\x8d\xbc\x24\xe0\x01\x00\x00\x4c\x89\xe6\x4c\x89\xe9\xf3\xa4")

    # Append nonce string (itoa)
    code.extend(b"\x48\x85\xdb")  # test rbx, rbx
    jnz_idx = len(code)
    code.extend(b"\x75\x00")

    # Zero case:
    code.extend(b"\xc6\x07\x30\x48\xff\xc7")
    jmp_after_idx = len(code)
    code.extend(b"\xeb\x00")

    # Non-zero case:
    non_zero_offset = len(code)
    code[jnz_idx + 1] = non_zero_offset - (jnz_idx + 2)

    code.extend(b"\x48\x89\xd8\x49\xc7\xc0\x0a\x00\x00\x00\x31\xc9")

    itoa_loop_offset = len(code)
    code.extend(b"\x31\xd2\x49\xf7\xf0\x80\xc2\x30\x52\xff\xc1\x48\x85\xc0")
    loop1_rel = itoa_loop_offset - (len(code) + 2)
    code.extend(b"\x75" + struct.pack('b', loop1_rel))

    pop_loop_offset = len(code)
    code.extend(b"\x58\x88\x07\x48\xff\xc7\xff\xc9")
    loop2_rel = pop_loop_offset - (len(code) + 2)
    code.extend(b"\x75" + struct.pack('b', loop2_rel))

    # After itoa:
    after_itoa_offset = len(code)
    code[jmp_after_idx + 1] = after_itoa_offset - (jmp_after_idx + 2)

    # Padding: 0x06 at rdi, 0x80 at block end (offset 135)
    code.extend(b"\xc6\x07\x06")
    code.extend(b"\xc6\x84\x24\x67\x02\x00\x00\x80")

    # Copy buffer to state [rsp + 0]
    code.extend(b"\x48\x8d\xb4\x24\xe0\x01\x00\x00\x48\x89\xe7\xb9\x19\x00\x00\x00\xf3\x48\xa5")

    # 23 rounds of Keccak-f[1600] (rounds 1 through 23)
    for r in range(1, 24):
        # 1. Theta
        for x in range(5):
            code.extend(b"\x48\x8b\x84\x24" + struct.pack('<I', x * 8))
            for y in range(1, 5):
                code.extend(b"\x48\x33\x84\x24" + struct.pack('<I', (x + 5 * y) * 8))
            code.extend(b"\x48\x89\x84\x24" + struct.pack('<I', 400 + x * 8))

        for x in range(5):
            code.extend(b"\x48\x8b\x84\x24" + struct.pack('<I', 400 + ((x + 1) % 5) * 8))
            code.extend(b"\x48\xd1\xc0")
            code.extend(b"\x48\x33\x84\x24" + struct.pack('<I', 400 + ((x + 4) % 5) * 8))
            code.extend(b"\x48\x89\x84\x24" + struct.pack('<I', 440 + x * 8))

        for x in range(5):
            code.extend(b"\x48\x8b\x94\x24" + struct.pack('<I', 440 + x * 8))
            for y in range(5):
                code.extend(b"\x48\x31\x94\x24" + struct.pack('<I', (x + 5 * y) * 8))

        # 2. Rho & Pi
        for x in range(5):
            for y in range(5):
                rot = ROT[x][y]
                code.extend(b"\x48\x8b\x84\x24" + struct.pack('<I', (x + 5 * y) * 8))
                if rot != 0:
                    code.extend(b"\x48\xc1\xc0" + bytes([rot]))
                dest_idx = y + 5 * ((2 * x + 3 * y) % 5)
                code.extend(b"\x48\x89\x84\x24" + struct.pack('<I', 200 + dest_idx * 8))

        # 3. Chi
        for y in range(5):
            for x in range(5):
                code.extend(b"\x48\x8b\x84\x24" + struct.pack('<I', 200 + (((x + 1) % 5) + 5 * y) * 8))
                code.extend(b"\x48\xf7\xd0")
                code.extend(b"\x48\x23\x84\x24" + struct.pack('<I', 200 + (((x + 2) % 5) + 5 * y) * 8))
                code.extend(b"\x48\x33\x84\x24" + struct.pack('<I', 200 + (x + 5 * y) * 8))
                code.extend(b"\x48\x89\x84\x24" + struct.pack('<I', (x + 5 * y) * 8))

        # 4. Iota
        rc_val = RC[r]
        code.extend(b"\x48\xb8" + struct.pack('<Q', rc_val))
        code.extend(b"\x48\x31\x04\x24")

    # Check 32-byte hash match (4 uint64 words)
    code.extend(b"\x48\x8b\x04\x24\x49\x3b\x06")
    jne1_idx = len(code)
    code.extend(b"\x0f\x85\x00\x00\x00\x00")

    code.extend(b"\x48\x8b\x44\x24\x08\x49\x3b\x46\x08")
    jne2_idx = len(code)
    code.extend(b"\x0f\x85\x00\x00\x00\x00")

    code.extend(b"\x48\x8b\x44\x24\x10\x49\x3b\x46\x10")
    jne3_idx = len(code)
    code.extend(b"\x0f\x85\x00\x00\x00\x00")

    code.extend(b"\x48\x8b\x44\x24\x18\x49\x3b\x46\x18")
    jne4_idx = len(code)
    code.extend(b"\x0f\x85\x00\x00\x00\x00")

    # MATCH FOUND! Return rbx in rax
    code.extend(b"\x48\x89\xd8")
    jmp_epilogue_idx = len(code)
    code.extend(b"\xe9\x00\x00\x00\x00")

    # NEXT_NONCE:
    next_nonce_offset = len(code)
    for jne_idx in [jne1_idx, jne2_idx, jne3_idx, jne4_idx]:
        rel = next_nonce_offset - (jne_idx + 6)
        code[jne_idx + 2: jne_idx + 6] = struct.pack('<i', rel)

    code.extend(b"\x48\xff\xc3")  # inc rbx
    loop_jmp_offset = loop_start_offset - (len(code) + 5)
    code.extend(b"\xe9" + struct.pack('<i', loop_jmp_offset))

    # NOT_FOUND:
    not_found_offset = len(code)
    jg_rel = not_found_offset - (jg_not_found_idx + 6)
    code[jg_not_found_idx + 2: jg_not_found_idx + 6] = struct.pack('<i', jg_rel)
    code.extend(b"\x48\xc7\xc0\xff\xff\xff\xff")  # mov rax, -1

    # EPILOGUE:
    epilogue_offset = len(code)
    jmp_rel = epilogue_offset - (jmp_epilogue_idx + 5)
    code[jmp_epilogue_idx + 1: jmp_epilogue_idx + 5] = struct.pack('<i', jmp_rel)

    code.extend(b"\x48\x81\xc4\xc0\x02\x00\x00")  # add rsp, 704
    code.extend(b"\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x5e\x5f\x5d\x5b")
    code.extend(b"\xc3")

    return bytes(code)


class DeepSeekPoWSolver:
    """High performance solver for DeepSeekHashV1."""

    def __init__(self):
        self._jit_fn = None
        self._init_jit()

    def _init_jit(self):
        if platform.system() == "Windows" and platform.machine().lower() in ("amd64", "x86_64"):
            try:
                code_bytes = _build_x86_64_jit_solver()
                kernel32 = ctypes.windll.kernel32
                VirtualAlloc = kernel32.VirtualAlloc
                VirtualAlloc.restype = ctypes.c_void_p
                VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]

                MEM_COMMIT = 0x1000
                MEM_RESERVE = 0x2000
                PAGE_EXECUTE_READWRITE = 0x40

                addr = VirtualAlloc(None, len(code_bytes), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
                if addr:
                    ctypes.memmove(addr, code_bytes, len(code_bytes))
                    func_type = ctypes.CFUNCTYPE(
                        ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64
                    )
                    self._jit_fn = func_type(addr)
            except Exception:
                self._jit_fn = None

    def solve(self, challenge_dict: dict) -> dict:
        """
        Solves the PoW challenge and returns the response payload dictionary.
        """
        salt = challenge_dict["salt"]
        expire_at = challenge_dict["expire_at"]
        difficulty = challenge_dict.get("difficulty", 144000)
        target_hex = challenge_dict["challenge"]
        signature = challenge_dict["signature"]
        algorithm = challenge_dict.get("algorithm", "DeepSeekHashV1")
        target_path = challenge_dict.get("target_path", "/api/v0/chat/completion")

        prefix = f"{salt}_{expire_at}_".encode("utf-8")
        target_bytes = bytes.fromhex(target_hex)

        nonce = None
        t0 = time.perf_counter()

        if self._jit_fn:
            target_buf = ctypes.create_string_buffer(target_bytes)
            ans = self._jit_fn(prefix, len(prefix), ctypes.byref(target_buf), difficulty)
            if ans >= 0:
                nonce = int(ans)

        # Fallback if JIT is not available or failed
        if nonce is None:
            nonce = self._solve_python(salt, expire_at, difficulty, target_bytes)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return {
            "algorithm": algorithm,
            "challenge": target_hex,
            "salt": salt,
            "answer": nonce,
            "signature": signature,
            "target_path": target_path,
            "_elapsed_ms": elapsed_ms,
        }

    def solve_to_header(self, challenge_dict: dict) -> str:
        """Solves challenge and returns Base64 string for x-ds-pow-response header."""
        ans = self.solve(challenge_dict)
        cleaned = {k: v for k, v in ans.items() if not k.startswith("_")}
        json_str = json.dumps(cleaned, separators=(",", ":"))
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _solve_python(salt: str, expire_at: int, difficulty: int, target_bytes: bytes) -> int:
        """Pure python fallback solver."""
        def rotl64(x, n):
            return ((x << (n % 64)) & 0xFFFFFFFFFFFFFFFF) | (x >> ((64 - (n % 64)) % 64))

        target_words = struct.unpack("<4Q", target_bytes)

        for nonce in range(difficulty + 1):
            msg = f"{salt}_{expire_at}_{nonce}".encode("utf-8")
            rate = 136
            padded = bytearray(msg)
            padded.append(0x06)
            while len(padded) % rate != rate - 1:
                padded.append(0x00)
            padded.append(0x80)

            state = [[0] * 5 for _ in range(5)]
            for block_start in range(0, len(padded), rate):
                block = padded[block_start: block_start + rate]
                words = struct.unpack("<17Q", block)
                for i, val in enumerate(words):
                    state[i % 5][i // 5] ^= val

                # 23 rounds
                for r in range(1, 24):
                    C = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
                    D = [C[(x - 1) % 5] ^ rotl64(C[(x + 1) % 5], 1) for x in range(5)]
                    for x in range(5):
                        for y in range(5):
                            state[x][y] ^= D[x]

                    B = [[0] * 5 for _ in range(5)]
                    for x in range(5):
                        for y in range(5):
                            B[y][(2 * x + 3 * y) % 5] = rotl64(state[x][y], ROT[x][y])

                    for x in range(5):
                        for y in range(5):
                            state[x][y] = B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) & 0xFFFFFFFFFFFFFFFF

                    state[0][0] ^= RC[r]

            if (
                state[0][0] == target_words[0]
                and state[1][0] == target_words[1]
                and state[2][0] == target_words[2]
                and state[3][0] == target_words[3]
            ):
                return nonce

        return 0


default_solver = DeepSeekPoWSolver()
