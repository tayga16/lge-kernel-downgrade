#!/usr/bin/env python3
"""
Standalone mkbootimg for Android boot images (v0-v2).
Zero external dependencies, uses standard Python library only.
"""
import argparse
import hashlib
import os
import struct
import sys

BOOT_MAGIC = b'ANDROID!'
BOOT_NAME_SIZE = 16
BOOT_ARGS_SIZE = 512
BOOT_EXTRA_ARGS_SIZE = 1024


def pad_file(f, page_size):
    pad = (page_size - (f.tell() & (page_size - 1))) & (page_size - 1)
    f.write(b'\x00' * pad)


def parse_int(x):
    return int(x, 0)


def main():
    parser = argparse.ArgumentParser(description='Pack Android boot.img')
    parser.add_argument('--kernel', required=True, type=argparse.FileType('rb'))
    parser.add_argument('--ramdisk', required=False, type=argparse.FileType('rb'), default=None)
    parser.add_argument('--second', required=False, type=argparse.FileType('rb'), default=None)
    parser.add_argument('--dtb', required=False, type=argparse.FileType('rb'), default=None)
    parser.add_argument('--cmdline', default='', type=str)
    parser.add_argument('--base', default='0x80000000', type=parse_int)
    parser.add_argument('--kernel_offset', default='0x00008000', type=parse_int)
    parser.add_argument('--ramdisk_offset', default='0x01000000', type=parse_int)
    parser.add_argument('--second_offset', default='0x00f00000', type=parse_int)
    parser.add_argument('--tags_offset', default='0x00000100', type=parse_int)
    parser.add_argument('--pagesize', default='2048', type=parse_int)
    parser.add_argument('--board', default='', type=str)
    parser.add_argument('-o', '--output', required=True, type=str)

    args = parser.parse_args()

    kernel_data = args.kernel.read()
    ramdisk_data = args.ramdisk.read() if args.ramdisk else b''
    second_data = args.second.read() if args.second else b''
    dtb_data = args.dtb.read() if args.dtb else b''

    kernel_size = len(kernel_data)
    ramdisk_size = len(ramdisk_data)
    second_size = len(second_data)
    dtb_size = len(dtb_data)

    kernel_addr = args.base + args.kernel_offset
    ramdisk_addr = args.base + args.ramdisk_offset
    second_addr = args.base + args.second_offset
    tags_addr = args.base + args.tags_offset

    # Compute SHA1
    sha1 = hashlib.sha1()
    sha1.update(kernel_data)
    sha1.update(struct.pack('<I', kernel_size))
    sha1.update(ramdisk_data)
    sha1.update(struct.pack('<I', ramdisk_size))
    sha1.update(second_data)
    sha1.update(struct.pack('<I', second_size))
    if dtb_data:
        sha1.update(dtb_data)
        sha1.update(struct.pack('<I', dtb_size))
    img_id = sha1.digest() + b'\x00' * (32 - len(sha1.digest()))

    cmdline_bytes = args.cmdline.encode('ascii', errors='replace')
    if len(cmdline_bytes) > BOOT_ARGS_SIZE:
        cmdline = cmdline_bytes[:BOOT_ARGS_SIZE]
        extra_cmdline = cmdline_bytes[BOOT_ARGS_SIZE:BOOT_ARGS_SIZE + 1024]
    else:
        cmdline = cmdline_bytes
        extra_cmdline = b''

    cmdline = cmdline.ljust(BOOT_ARGS_SIZE, b'\x00')
    extra_cmdline = extra_cmdline.ljust(BOOT_EXTRA_ARGS_SIZE, b'\x00')
    name = args.board.encode('ascii', errors='replace')[:BOOT_NAME_SIZE].ljust(BOOT_NAME_SIZE, b'\x00')

    # Header layout:
    # 8s  - magic
    # 8I  - kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size
    # 2I  - dtb_size, os_version
    # 16s - name
    # 512s- cmdline
    # 32s - id
    # 1024s - extra_cmdline
    header = struct.pack(
        '<8s8II16s512s32s1024s',
        BOOT_MAGIC,
        kernel_size, kernel_addr,
        ramdisk_size, ramdisk_addr,
        second_size, second_addr,
        tags_addr,
        args.pagesize,
        dtb_size,
        0,
        name,
        cmdline,
        img_id,
        extra_cmdline
    )

    with open(args.output, 'wb') as out:
        out.write(header)
        pad_file(out, args.pagesize)

        out.write(kernel_data)
        pad_file(out, args.pagesize)

        if ramdisk_size > 0:
            out.write(ramdisk_data)
            pad_file(out, args.pagesize)

        if second_size > 0:
            out.write(second_data)
            pad_file(out, args.pagesize)

        if dtb_size > 0:
            out.write(dtb_data)
            pad_file(out, args.pagesize)

    print(f"Successfully wrote {args.output} ({os.path.getsize(args.output)} bytes)")


if __name__ == '__main__':
    main()
