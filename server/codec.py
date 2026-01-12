
import struct

# Mu-law constants
BIAS = 0x84
CLIP = 32635

# Lookup tables for fast conversion
MU_LAW_TO_PCM = []
PCM_TO_MU_LAW = [0] * 65536  # covering -32768 to 32767 mapped to 0-65535 index

def _build_tables():
    # Build MU_LAW_TO_PCM
    global MU_LAW_TO_PCM
    MU_LAW_TO_PCM = [0] * 256
    for i in range(256):
        mu = ~i
        sign = -1 if (mu & 0x80) else 1
        exponent = (mu >> 4) & 0x07
        mantissa = mu & 0x0F
        sample = sign * ((((mantissa << 3) + 0x84) << exponent) - 0x84)
        MU_LAW_TO_PCM[i] = sample

    # Build PCM_TO_MU_LAW (simple approximation logic or full table)
    # Using the standard algorithm for lin2ulaw
    pass # we'll use a function for lin2ulaw or build table on demand/start
    
_build_tables()

def ulaw2lin(data: bytes) -> bytes:
    """Convert G.711 u-law bytes to 16-bit PCM bytes."""
    # data is bytes (uint8)
    # output is bytes (int16 little endian)
    # Using list comprehension for speed, typically fast enough for chunks
    values = [MU_LAW_TO_PCM[b] for b in data]
    return struct.pack(f"<{len(values)}h", *values)

def lin2ulaw(data: bytes) -> bytes:
    """Convert 16-bit PCM bytes to G.711 u-law bytes."""
    # data is bytes (int16 little endian)
    # input must be even length
    count = len(data) // 2
    shorts = struct.unpack(f"<{count}h", data)
    
    encoded = bytearray()
    for sample in shorts:
        sign = 0
        if sample < 0:
            sample = -sample
            sign = 0x80
        if sample > CLIP:
            sample = CLIP
        sample += BIAS
        exponent = 7
        for exp in range(7, -1, -1):
             if sample & (1 << (exp + 7)):
                 exponent = exp
                 break
        mantissa = (sample >> (exponent + 3)) & 0x0F
        byte = ~(sign | (exponent << 4) | mantissa)
        encoded.append(byte & 0xFF)
    return bytes(encoded)

def resample_8k_to_16k(data: bytes) -> bytes:
    """Resample 8kHz PCM 16-bit to 16kHz PCM 16-bit using linear interpolation."""
    count = len(data) // 2
    samples = struct.unpack(f"<{count}h", data)
    output = []
    
    # 8k -> 16k: s[i] -> s[i], (s[i]+s[i+1])/2
    # Simple repeat or linear interp. Linear interp smells better.
    for i in range(count - 1):
        s1 = samples[i]
        s2 = samples[i+1]
        output.append(s1)
        output.append((s1 + s2) // 2)
    
    # Handle last sample
    if count > 0:
        output.append(samples[-1])
        output.append(samples[-1]) # Repeat last
        
    return struct.pack(f"<{len(output)}h", *output)

def resample_16k_to_8k(data: bytes) -> bytes:
    """Resample 16kHz PCM 16-bit to 8kHz PCM 16-bit using simple averaging/decimation."""
    count = len(data) // 2
    samples = struct.unpack(f"<{count}h", data)
    output = []
    
    # 16k -> 8k: Take average of every 2 samples
    for i in range(0, count, 2):
        if i + 1 < count:
            avg = (samples[i] + samples[i+1]) // 2
            output.append(avg)
        else:
            output.append(samples[i])
            
    return struct.pack(f"<{len(output)}h", *output)

# State handling is skipped for simplicity as these are stateless ops (block interactions might have artifacts at edges, but usually negligible for voice)
