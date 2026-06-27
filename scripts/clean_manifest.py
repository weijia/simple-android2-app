#!/usr/bin/env python3
"""
Post-process a built APK's binary AndroidManifest.xml to remove attributes
that old Android devices (e.g. NOOK2 Android 2.1) don't understand.

Removes these attributes by their resource ID:
  - compileSdkVersion (0x01010572)
  - compileSdkVersionCodename (0x01010573)
  - platformBuildVersionCode (0x01010481)
  - platformBuildVersionName (0x01010480)

Usage: python3 clean_manifest.py input.apk output.apk
"""

import struct
import sys
import zipfile
import io
import os

# Android resource IDs to remove
ATTRS_TO_REMOVE = {
    0x01010572,  # compileSdkVersion
    0x01010573,  # compileSdkVersionCodename
    0x01010481,  # platformBuildVersionCode
    0x01010480,  # platformBuildVersionName
}

def read_int(data, offset):
    return struct.unpack_from('<I', data, offset)[0]

def write_int(val):
    return struct.pack('<I', val)

def parse_axml(data):
    """Parse binary AXML and return cleaned data."""
    # Validate header
    magic = read_int(data, 0)
    if magic not in (0x00080003, 0x00080001):
        print(f"Warning: unexpected AXML magic: 0x{magic:08x}")
    file_size = read_int(data, 4)

    chunks = []
    offset = 0
    while offset < len(data):
        if offset + 8 > len(data):
            break
        chunk_type = read_int(data, offset)
        chunk_size = read_int(data, offset + 4)

        if chunk_size < 8 or offset + chunk_size > len(data):
            break

        chunk_data = bytearray(data[offset:offset + chunk_size])

        # RES_XML_START_ELEMENT_CHUNK = 0x00010202
        # RES_XML_END_ELEMENT_CHUNK = 0x00010203
        if chunk_type == 0x00010202:
            # Start Element chunk - process attributes
            if len(chunk_data) >= 28:
                attr_start = read_int(chunk_data, 20)  # attributeStart
                attr_size = read_int(chunk_data, 24)  # attributeSize
                attr_count = read_int(chunk_data, 16)  # attributeCount

                if attr_size == 20 and attr_count > 0:  # 5 ints per attribute
                    new_attrs = bytearray()
                    removed = 0
                    for i in range(attr_count):
                        attr_offset = attr_start + i * attr_size
                        if attr_offset + attr_size > len(chunk_data):
                            break
                        ns = read_int(chunk_data, attr_offset)
                        name = read_int(chunk_data, attr_offset + 4)
                        if name in ATTRS_TO_REMOVE and ns == 0:
                            removed += 1
                        else:
                            new_attrs.extend(chunk_data[attr_offset:attr_offset + attr_size])

                    if removed > 0:
                        new_count = attr_count - removed
                        struct.pack_into('<I', chunk_data, 16, new_count)
                        # Rebuild chunk
                        chunk_data = chunk_data[:attr_start] + new_attrs + chunk_data[attr_start + attr_count * attr_size:]
                        struct.pack_into('<I', chunk_data, 4, len(chunk_data))
                        print(f"  Removed {removed} attribute(s) from element chunk")

        chunks.append(bytes(chunk_data))
        offset += chunk_size

    return b''.join(chunks)

def process_apk(input_path, output_path):
    """Read APK, clean manifest, write new APK."""
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
            # Keep META-INF entries (signatures will be replaced later)
            # Keep everything else as-is
            zout.writestr(name, data)

    print(f"Written cleaned APK: {output_path}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.apk output.apk")
        sys.exit(1)

    process_apk(sys.argv[1], sys.argv[2])
