"""Reader for Borland Paradox table files (.DB) used by BDE-based applications.

The format was reverse-engineered empirically against real-world databases;
key facts implemented here:

* Header (little-endian): record size @0x00, header size @0x02, block size
  factor @0x05 (block = value * 1024), declared record count @0x06 (NOT
  reliable — some files declare less than actually stored), first data block
  @0x0E, field count @0x21, DOS code page @0x6A.
* Field descriptors: (type, size) pairs at 0x78; field names are NUL-separated
  strings starting at 0x78 + 83 + 6 * field_count.
* Data blocks are linked via the first two bytes of every block (next/prev);
  records are stored back-to-back after a 6-byte block header.
* Numeric values are big-endian with the high bit used as the sign flag.

Because the declared record count can be wrong, the reader walks the whole
block chain and skips empty slots instead of trusting it.
"""

import datetime
import struct

TYPEMAP = {
    1: 'A', 2: 'D', 3: 'S', 4: 'I', 5: '$', 6: 'N', 9: 'L',
    0x0C: 'M', 0x0D: 'B', 0x0E: 'F', 0x0F: 'O', 0x10: 'G',
    0x14: 'T', 0x15: '@', 0x16: '+', 0x17: '#', 0x18: 'Y',
}


def read_be_signed(buf):
    """Read a big-endian integer where the high bit marks a negative value."""
    if all(b == 0 for b in buf):
        return None
    if buf[0] & 0x80:
        return int.from_bytes(bytes([buf[0] & 0x7F] + list(buf[1:])), 'big')
    b = bytearray(x ^ 0xFF for x in buf)
    v = int.from_bytes(b, 'big')
    return -v if v else None


def read_be_double(buf):
    """Read an IEEE-754 double stored big-endian with a separate sign bit."""
    if all(b == 0 for b in buf):
        return None
    b = bytearray(buf)
    if b[0] & 0x80:
        b[0] &= 0x7F
        return struct.unpack('>d', bytes(b))[0]
    b = bytearray(x ^ 0xFF for x in buf)
    return -struct.unpack('>d', bytes(b))[0]


def decode_field(ftype, fsize, raw, cp):
    """Decode a single raw field value to a string (or '' for empty)."""
    if ftype == 1:  # Alpha
        return raw.split(b'\x00')[0].decode(cp, errors='replace')
    if ftype == 2:  # Date: days since 0001-01-01
        v = read_be_signed(raw)
        if v is None or v <= 0:
            return ''
        try:
            return (datetime.date(1, 1, 1) + datetime.timedelta(days=v)).strftime('%d.%m.%Y')
        except Exception:
            return str(v)
    if ftype == 3:  # short
        v = read_be_signed(raw)
        return '' if v is None else str(v)
    if ftype in (4, 0x16):  # long / autoincrement
        v = read_be_signed(raw)
        return '' if v is None else str(v)
    if ftype in (5, 6):  # currency / number
        v = read_be_double(raw)
        return '' if v is None else repr(v)
    if ftype == 9:  # logical: 0xFF = null, 0x80|0 = N, 0x80|1 = Y
        b = raw[0]
        if b == 0xFF:
            return ''
        return 'Y' if (b & 0x7F) == 1 else ('N' if (b & 0x7F) == 0 else hex(b))
    if ftype == 0x14:  # time in ms
        v = read_be_signed(raw)
        if v is None:
            return ''
        s = v // 1000
        return '%02d:%02d:%02d' % (s // 3600, s % 3600 // 60, s % 60)
    if ftype == 0x15:  # timestamp
        v = read_be_double(raw)
        if v is None:
            return ''
        try:
            dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=v)
            return dt.strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            return repr(v)
    if ftype == 0x17:  # BCD
        return raw.hex()
    if ftype in (0x0C, 0x0E, 0x18):  # memo/blob stored inline as text
        s = raw.split(b'\x00')[0]
        try:
            txt = s.decode(cp)
        except Exception:
            return '<' + raw.hex() + '>'
        if all(c.isprintable() or c in '\r\n\t' for c in txt):
            return txt
        return '<' + raw.hex() + '>'
    return '<%s:%s%s>' % (TYPEMAP.get(ftype, hex(ftype)), raw[:16].hex(),
                           '...' if fsize > 16 else '')


class PdxTable(object):
    """A single Paradox .DB table opened for reading."""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.data = f.read()
        d = self.data
        if len(d) < 0x78:
            raise ValueError('file too small to be a Paradox table')
        self.record_size = struct.unpack_from('<H', d, 0)[0]
        self.header_size = struct.unpack_from('<H', d, 2)[0]
        self.block_size = d[5] * 1024
        self.num_records = struct.unpack_from('<I', d, 6)[0]
        self.first_block = struct.unpack_from('<H', d, 0x0E)[0]
        self.num_fields = struct.unpack_from('<H', d, 0x21)[0]
        self.code_page = struct.unpack_from('<H', d, 0x6A)[0]
        self.cp = 'cp%d' % self.code_page if self.code_page in (866, 1251, 1252) else 'cp1251'
        if not (0 < self.num_fields < 1024 and 0 < self.record_size < 8192):
            raise ValueError('does not look like a Paradox table')
        fi = d[0x78:0x78 + self.num_fields * 2]
        self.field_types = [fi[i] for i in range(0, len(fi), 2)]
        self.field_sizes = [fi[i] for i in range(1, len(fi), 2)]
        names_blob = d[0x78 + 83 + 6 * self.num_fields:][:2048]
        names = names_blob.split(b'\x00')[:self.num_fields]
        names += [b''] * (self.num_fields - len(names))
        self.field_names = [n.decode(self.cp, errors='replace') or 'field%d' % (i + 1)
                            for i, n in enumerate(names)]
        if sum(self.field_sizes) != self.record_size:
            raise ValueError('field sizes do not add up to the record size')

    def blocks(self):
        """Yield data blocks by following the block chain from the header."""
        blk = self.first_block
        seen = set()
        while blk and blk not in seen:
            seen.add(blk)
            base = self.header_size + (blk - 1) * self.block_size
            b = self.data[base:base + self.block_size]
            if len(b) < self.block_size:
                break
            yield b
            blk = struct.unpack_from('<H', b, 0)[0]

    def rows(self):
        """Yield decoded rows; skips empty slots (first 4 bytes are zero)."""
        per_block = (self.block_size - 6) // self.record_size
        for b in self.blocks():
            for i in range(per_block):
                off = 6 + i * self.record_size
                rec = b[off:off + self.record_size]
                if len(rec) < self.record_size:
                    continue
                if all(x == 0 for x in rec[:4]):
                    continue
                row, pos = [], 0
                for t, s in zip(self.field_types, self.field_sizes):
                    row.append(decode_field(t, s, rec[pos:pos + s], self.cp))
                    pos += s
                yield row
