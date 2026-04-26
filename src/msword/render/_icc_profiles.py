"""ICC profile helpers for PDF/X export.

Provides sRGB and CMYK (FOGRA39) ICC profile bytes used as PDF/X output intents.

For sRGB we use Pillow's built-in ``ImageCms.createProfile("sRGB")``.

For CMYK we *prefer* a real Coated FOGRA39 (ISO 12647-2:2004) ICC profile —
loadable via the ``MSWORD_CMYK_ICC_PATH`` environment variable or by passing
``output_intent_icc`` directly to :func:`msword.render.pdf_x.export_pdf_x`.
When no real profile is available we synthesize a *minimal-but-syntactically-
valid* CMYK ICC v2.1 profile so PDF/X export still produces a reasonable
``/OutputIntents`` entry. The synthesized fallback is **not** print-accurate
and should be replaced with a real FOGRA39 profile in production. See spec
§7 — "CMYK fallback acceptable".
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

from PIL import ImageCms

_ENV_CMYK_PATH = "MSWORD_CMYK_ICC_PATH"


def srgb_profile() -> bytes:
    """Return sRGB ICC profile bytes.

    Uses Pillow's :func:`PIL.ImageCms.createProfile` to synthesize a standard
    sRGB IEC61966-2.1 profile.
    """
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return bytes(profile.tobytes())


def cmyk_fogra39_profile() -> bytes:
    """Return CMYK FOGRA39 ICC profile bytes.

    Resolution order:

    1. ``MSWORD_CMYK_ICC_PATH`` environment variable (path to .icc/.icm file).
    2. Synthesized minimal CMYK profile (fallback — not print-accurate).
    """
    env_path = os.environ.get(_ENV_CMYK_PATH)
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return candidate.read_bytes()
    return _synthesize_minimal_cmyk_icc()


def _synthesize_minimal_cmyk_icc() -> bytes:
    """Build a minimal, syntactically-valid CMYK ICC v2.1 output profile.

    The profile carries only the four tags required by the ICC specification
    for any v2.x profile — ``desc``, ``cprt``, ``wtpt``, ``A2B0`` — with the
    A2B0 transform set to a 1-D identity LUT. It is sufficient to be embedded
    as a PDF/X ``/OutputIntents`` ICC stream; it is **not** colorimetrically
    meaningful and must not be used to *render* color.
    """
    # ---- tag data blocks -------------------------------------------------
    desc_text = b"msword synthetic CMYK fallback (not for production)\x00"
    desc_data = (
        b"desc"
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(desc_text))
        + desc_text
        + b"\x00" * (67 - 1)  # 67 bytes of unicode + scriptcode reserved
        + b"\x00\x00\x00"  # macScriptCode (2) + macDescriptionLength (1)
    )
    # Pad desc_data to 4-byte boundary
    while len(desc_data) % 4:
        desc_data += b"\x00"

    cprt_text = b"No copyright, msword synthetic profile.\x00"
    cprt_data = b"text" + b"\x00\x00\x00\x00" + cprt_text
    while len(cprt_data) % 4:
        cprt_data += b"\x00"

    # XYZType for white point — D50: X=0.9642, Y=1.0, Z=0.8249
    # encoded as s15Fixed16Number (signed 16.16 fixed point)
    def s15f16(value: float) -> int:
        return round(value * 65536.0)

    wtpt_data = (
        b"XYZ "
        + b"\x00\x00\x00\x00"
        + struct.pack(">iii", s15f16(0.9642), s15f16(1.0000), s15f16(0.8249))
    )

    # A2B0: minimal mft1 (1-byte LUT) — 4 input channels (CMYK) -> 3 output (XYZ)
    # mft1 layout: sig 'mft1' + 4 reserved + iCh + oCh + clut + reserved + e[9]
    # + input table (256 * iCh bytes) + clut (clut^iCh * oCh bytes) + output (256 * oCh)
    # Use clut=2 (smallest), 9 entries of 1.0 for matrix
    in_ch = 4
    out_ch = 3
    clut_pts = 2
    e_matrix = b""
    for v in (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0):
        e_matrix += struct.pack(">i", s15f16(v))
    input_table = b"\x00" * (256 * in_ch)
    clut = b"\x00" * ((clut_pts**in_ch) * out_ch)
    output_table = b"\x00" * (256 * out_ch)
    a2b0_data = (
        b"mft1"
        + b"\x00\x00\x00\x00"
        + bytes([in_ch, out_ch, clut_pts, 0])
        + e_matrix
        + input_table
        + clut
        + output_table
    )
    while len(a2b0_data) % 4:
        a2b0_data += b"\x00"

    # ---- tag table ------------------------------------------------------
    # 4-byte tag count + N * (4-byte sig + 4-byte offset + 4-byte size)
    tags = [
        (b"desc", desc_data),
        (b"cprt", cprt_data),
        (b"wtpt", wtpt_data),
        (b"A2B0", a2b0_data),
    ]
    header_size = 128
    tag_table_size = 4 + 12 * len(tags)
    data_offset = header_size + tag_table_size
    # Align data_offset to 4-byte boundary
    while data_offset % 4:
        data_offset += 1

    tag_table = struct.pack(">I", len(tags))
    cursor = data_offset
    payload = b""
    for sig, data in tags:
        tag_table += sig + struct.pack(">II", cursor, len(data))
        payload += data
        cursor += len(data)

    # ---- header ---------------------------------------------------------
    header = bytearray(128)
    struct.pack_into(">I", header, 8, 0x02100000)  # version 2.1
    header[12:16] = b"prtr"  # device class: output
    header[16:20] = b"CMYK"
    header[20:24] = b"XYZ "
    # date/time at 24..36 — 12 bytes of zeros is acceptable
    header[36:40] = b"acsp"
    # rendering intent at 64: 0 (perceptual) — already zero-filled
    # PCS illuminant — D50 — at 68..80
    struct.pack_into(
        ">iii", header, 68, s15f16(0.9642), s15f16(1.0000), s15f16(0.8249)
    )
    header[80:84] = b"msw "  # profile creator

    gap = b"\x00" * (data_offset - header_size - len(tag_table))
    profile = bytes(header) + tag_table + gap + payload
    # Patch the final profile size into bytes 0..4 of the header.
    return struct.pack(">I", len(profile)) + profile[4:]
