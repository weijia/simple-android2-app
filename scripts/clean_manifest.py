#!/usr/bin/env python3
"""
Post-process a built APK's binary AndroidManifest.xml to remove attributes
that old Android devices (e.g. NOOK2 Android 2.1) don't understand.

Removes these attributes by name:
  - compileSdkVersion
  - compileSdkVersionCodename
  - platformBuildVersionCode
  - platformBuildVersionName
"""

import struct
import sys
import zipfile

ATTRS_TO_REMOVE = {
    "compileSdkVersion",
    "compileSdkVersionCodename",
    "platformBuildVersionCode",
    "platformBuildVersionName",
}


def parse_string_pool(data, offset):
    """Parse ResStringPool chunk starting at offset. Returns list of strings."""
    str_count = struct.unpack_from('<I', data, offset + 8)[0]
    style_count = struct.unpack_from('<I', data, offset + 12)[0]
    flags = struct.unpack_from('<I', data, offset + 16)[0]
    str_start = struct.unpack_from('<I', data, offset + 20)[0]
    style_start = struct.unpack_from('<I', data, offset + 24)[0]

    is_utf8 = (flags & 0x100) != 0
    strings = []

    for s in range(str_count):
        stroff = struct.unpack_from('<I', data, offset + 28 + s * 4)[0]
        addr = offset + str_start + stroff

        if is_utf8:
            u8len = data[addr]
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
    # Validate file header
    ftype = struct.unpack_from('<H', data, 0)[0]
    fheader_size = struct.unpack_from('<H', data, 2)[0]
    fsize = struct.unpack_from('<I', data, 4)[0]

    if ftype not in (0x0003, 0x0001):
        print(f"Warning: unexpected AXML type: 0x{ftype:04x}")

    # First pass: find string pool and build string list
    strings = []
    offset = fheader_size
    while offset < len(data):
        if offset + 8 > len(data):
            break
        ctype = struct.unpack_from('<H', data, offset)[0]
        hsize = struct.unpack_from('<H', data, offset + 2)[0]
        csize = struct.unpack_from('<I', data, offset + 4)[0]

        if csize < 8 or offset + csize > len(data):
            break

        if ctype == 0x0001:  # RES_STRING_POOL_TYPE
            strings = parse_string_pool(data, offset)
            print(f"  String pool: {len(strings)} strings")
            break

        offset += csize

    # Second pass: process chunks and rebuild
    result = bytearray(data[:fheader_size])
    offset = fheader_size

    while offset < len(data):
        if offset + 8 > len(data):
            break
        ctype = struct.unpack_from('<H', data, offset)[0]
        hsize = struct.unpack_from('<H', data, offset + 2)[0]
        csize = struct.unpack_from('<I', data, offset + 4)[0]

        if csize < 8 or offset + csize > len(data):
            break

        chunk_data = data[offset:offset + csize]

        if ctype == 0x0102:  # RES_XML_START_ELEMENT_TYPE
            chunk_data = remove_attrs_from_chunk(chunk_data, strings)

        result.extend(chunk_data)
        offset += csize

    # Update file size
    struct.pack_into('<I', result, 4, len(result))
    return bytes(result)


def process_apk(input_path, output_path):
    print(f"Processing: {input_path}")

    with zipfile.ZipFile(input_path, 'r') as zin:
        entries = {}
        for name in zin.namelist():
            entries[name] = zin.read(name)

    if 'AndroidManifest.xml' not in entries:
        print("ERROR: AndroidManifest.xml not found in APK!")
        sys.exit(1)

    manifest = entries['AndroidManifest.xml']
    print(f"  Original manifest size: {len(manifest)} bytes")

    cleaned = parse_axml(manifest)
    print(f"  Cleaned manifest size: {len(cleaned)} bytes")

    entries['AndroidManifest.xml'] = cleaned

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    print(f"Written cleaned APK: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.apk output.apk")
        sys.exit(1)

    process_apk(sys.argv[1], sys.argv[2])
