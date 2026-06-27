#!/usr/bin/env python3
"""
In-place patch a built APK's binary AndroidManifest.xml to remove attributes
that old Android devices (e.g. NOOK2 Android 2.1) don't understand.

Instead of rebuilding the ZIP, this patches the manifest bytes in-place
and replaces only that entry, preserving all other ZIP entries and alignment.

Removes these attributes by name:
  - compileSdkVersion
  - compileSdkVersionCodename
  - platformBuildVersionCode
  - platformBuildVersionName
"""

import struct
import sys
import zipfile
import io

ATTRS_TO_REMOVE = {
    "compileSdkVersion",
    "compileSdkVersionCodename",
    "platformBuildVersionCode",
    "platformBuildVersionName",
}


def parse_string_pool(data, offset):
    """Parse ResStringPool chunk starting at offset. Returns list of strings."""
    str_count = struct.unpack_from('<I', data, offset + 8)[0]
    flags = struct.unpack_from('<I', data, offset + 16)[0]
    str_start = struct.unpack_from('<I', data, offset + 20)[0]

    is_utf8 = (flags & 0x100) != 0
    strings = []

    for s in range(str_count):
        stroff = struct.unpack_from('<I', data, offset + 28 + s * 4)[0]
        addr = offset + str_start + stroff

        if is_utf8:
            strlen = data[addr + 1]
            sdata = data[addr + 2:addr + 2 + strlen]
            strings.append(sdata.decode('utf-8', errors='replace'))
        else:
            strlen = struct.unpack_from('<H', data, addr)[0] * 2
            sdata = data[addr + 2:addr + 2 + strlen]
            strings.append(sdata.decode('utf-16le', errors='replace').rstrip('\x00'))

    return strings


def remove_attrs_from_chunk(chunk_data, strings):
    """Remove target attributes from a StartElement chunk. Returns modified chunk."""
    data = bytearray(chunk_data)
    attr_start = struct.unpack_from('<H', data, 24)[0]
    attr_size = struct.unpack_from('<H', data, 26)[0]
    attr_count = struct.unpack_from('<H', data, 28)[0]

    if attr_size != 20 or attr_count == 0:
        return bytes(data)

    new_attrs = bytearray()
    removed = 0

    for i in range(attr_count):
        aoff = 16 + attr_start + i * attr_size
        attr_name_idx = struct.unpack_from('<I', data, aoff + 4)[0]

        if attr_name_idx < len(strings) and strings[attr_name_idx] in ATTRS_TO_REMOVE:
            removed += 1
        else:
            new_attrs.extend(data[aoff:aoff + attr_size])

    if removed == 0:
        return bytes(data)

    new_count = attr_count - removed
    struct.pack_into('<H', data, 28, new_count)

    # Rebuild chunk
    header = data[:16 + attr_start]
    footer = data[16 + attr_start + attr_count * attr_size:]
    data = header + new_attrs + footer

    # Update chunk size
    struct.pack_into('<I', data, 4, len(data))

    print(f"  Removed {removed} attribute(s) from element chunk")
    return bytes(data)


def parse_axml(data):
    """Parse binary AXML, remove target attributes, return cleaned data."""
    ftype = struct.unpack_from('<H', data, 0)[0]
    fheader_size = struct.unpack_from('<H', data, 2)[0]

    # First pass: find string pool
    strings = []
    offset = fheader_size
    while offset < len(data):
        if offset + 8 > len(data):
            break
        ctype = struct.unpack_from('<H', data, offset)[0]
        csize = struct.unpack_from('<I', data, offset + 4)[0]
        if csize < 8 or offset + csize > len(data):
            break
        if ctype == 0x0001:
            strings = parse_string_pool(data, offset)
            print(f"  String pool: {len(strings)} strings")
            break
        offset += csize

    # Second pass: process chunks
    result = bytearray(data[:fheader_size])
    offset = fheader_size
    while offset < len(data):
        if offset + 8 > len(data):
            break
        ctype = struct.unpack_from('<H', data, offset)[0]
        csize = struct.unpack_from('<I', data, offset + 4)[0]
        if csize < 8 or offset + csize > len(data):
            break

        chunk_data = data[offset:offset + csize]
        if ctype == 0x0102:
            chunk_data = remove_attrs_from_chunk(chunk_data, strings)

        result.extend(chunk_data)
        offset += csize

    # Update file size
    struct.pack_into('<I', result, 4, len(result))
    return bytes(result)


def patch_apk_manifest(input_path, output_path):
    """Patch the AndroidManifest.xml inside an APK in-place, preserving ZIP structure."""
    print(f"Processing: {input_path}")

    with zipfile.ZipFile(input_path, 'r') as zin:
        manifest_data = zin.read('AndroidManifest.xml')
        manifest_info = zin.getinfo('AndroidManifest.xml')
        # Read all entries as raw bytes with their info
        all_entries = []
        for info in zin.infolist():
            all_entries.append((info, zin.read(info.filename)))

    print(f"  Original manifest size: {len(manifest_data)} bytes")

    cleaned = parse_axml(manifest_data)
    print(f"  Cleaned manifest size: {len(cleaned)} bytes")

    # Build a new ZIP preserving the structure of the original as much as possible
    with open(input_path, 'rb') as f:
        raw = f.read()

    # Use zipfile to rebuild, but preserve compress_type and try to keep alignment
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as zout:
        for info, data in all_entries:
            if info.filename == 'AndroidManifest.xml':
                data = cleaned
                # Ensure manifest is STORED (not compressed)
                new_info = zipfile.ZipInfo(info.filename)
                new_info.compress_type = zipfile.ZIP_STORED
                new_info.external_attr = info.external_attr
                zout.writestr(new_info, data)
            else:
                # Preserve original compression
                zout.writestr(info, data)

    with open(output_path, 'wb') as f:
        f.write(out.getvalue())

    print(f"Written patched APK: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.apk output.apk")
        sys.exit(1)

    patch_apk_manifest(sys.argv[1], sys.argv[2])
