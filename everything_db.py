from __future__ import print_function
import os
from os import path
from array import array
import struct
import sys
import re
from bisect import bisect_right
import fnmatch


class StringBuffer(object):

    def __init__(self):
        self.buf = ""
        self.positions = array("L")
        self.lengths = array("H")

    @classmethod
    def from_items(cls, items):
        self = cls()
        positions = self.positions
        lengths = self.lengths
        pos = 0
        for item in items:
            positions.append(pos)
            length = len(item)
            lengths.append(length)
            pos += length + 1

        positions.append(pos)
        self.buf = b"\n".join(items)
        return self

    @classmethod
    def from_file(cls, f):
        item_count, char_count = struct.unpack("LL", f.read(8))
        self = cls()
        self.positions.fromfile(f, item_count + 1)
        self.lengths.fromfile(f, item_count)
        self.buf = f.read(char_count)
        return self

    def tofile(self, f):
        f.write(struct.pack("LL", len(self.lengths), len(self.buf)))
        self.positions.tofile(f)
        self.lengths.tofile(f)
        f.write(self.buf)

    def __getitem__(self, item):
        start = self.positions[item]
        return self.buf[start:start+self.lengths[item]]

    def __len__(self):
        return len(self.length)

    def iter_locations(self, pattern):
        buf = self.buf
        start = 0
        count = len(pattern)

        while True:
            loc = buf.find(pattern, start)
            if loc < 0:
                break
            yield loc
            start = loc + count

    def find_all(self, pattern, method="find"):
        if method == "find":
            locations = self.iter_locations(pattern)
        else:
            if method == "fnmatch":
                pattern = fnmatch.translate(pattern).replace('\Z(?ms)', '')
            locations = (m.start() for m in re.finditer(b"^" + pattern + b"$", self.buf, re.IGNORECASE|re.MULTILINE))

        start_index = 0
        start_loc = 0
        positions = self.positions

        for loc in locations:
            if loc < start_loc:
                continue
            index = bisect_right(positions, loc, lo=start_index) - 1
            start_index = index + 1
            start_loc = positions[start_index]
            yield index

    def __sizeof__(self):
        return sum(sys.getsizeof(x) for x in (self.positions, self.lengths, self.buf))


class EverythingDB(object):
    FOLDER_COUNT_POS = 0x0c
    CACHE_FN = path.join(path.dirname(__file__), "everything.cache")

    def __init__(self):
        self.items = None
        self.folder_count = None
        self.parents = array("L")

    @classmethod
    def from_cache(cls, fn):
        self = cls()
        with open(fn, "rb") as f:
            self.folder_count, item_count = struct.unpack("LL", f.read(8))
            self.parents.fromfile(f, item_count)
            self.items = StringBuffer.from_file(f)
        return self

    def tofile(self, fn):
        with open(fn, "wb") as f:
            f.write(struct.pack("LL", self.folder_count, len(self.parents)))
            self.parents.tofile(f)
            self.items.tofile(f)

    @classmethod
    def from_db(cls, fn):
        self = cls()
        with open(fn, "rb") as f:
            f.seek(cls.FOLDER_COUNT_POS)
            folder_count, file_count = struct.unpack("LL", f.read(8))
            f.read(3)
            while True:
                c = f.read(1)
                if c == b"\x00":
                    break
            f.read(4)
            f.read(0x14)

            buf1 = f.read(folder_count * 4)
            buf2 = f.read(folder_count * 4)

            f.read(4)

            last_str = b""
            items = []

            for i in range(folder_count):
                length = ord(f.read(1))
                drop_length = 0 if length == 0 else ord(f.read(1))
                s = f.read(length) if length > 0 else b""
                info = f.read(8)
                #the info can be get by fsutil usn readdata  it's call FileRef#
                last_str = last_str[:len(last_str)-drop_length] + s
                items.append(last_str)

            last_str = b""
            parents_buf = bytearray()
            parents_buf.extend(buf1)
            for i in range(file_count):
                info = f.read(4)
                parents_buf.extend(info)
                length = ord(f.read(1))
                drop_length = 0 if length == 0 else ord(f.read(1))
                s = f.read(length) if length > 0 else b""
                last_str = last_str[:len(last_str)-drop_length] + s
                items.append(last_str)

            self.folder_count = folder_count
            self.items = StringBuffer.from_items(items)
            self.parents.fromstring(bytes(parents_buf))
            return self

    def full_path(self, idx):
        names = [self.items[idx]]
        count = self.folder_count
        while True:
            idx = self.parents[idx]
            if idx >= count:
                break
            names.append(self.items[idx])
        return path.sep.encode("utf8").join(names[::-1])

    def find_all(self, pattern, method="find"):
        pattern = pattern.encode("utf8")
        index_generator = self.items.find_all(pattern, method)
        items = self.items
        parents = self.parents
        count = self.folder_count
        names = []
        append = names.append
        sep = path.sep.encode("utf8")
        for index in index_generator:
            del names[:]
            while True:
                append(items[index])
                index = parents[index]
                if index >= count:
                    break
            yield sep.join(reversed(names))

    def __sizeof__(self):
        return sum(sys.getsizeof(x) for x in (self.parents, self.items))


def open_everything(fn=None, use_cache=True):
    if fn is None:
        fn = path.join(os.environ['APPDATA'], r"Everything\Everything.db")

    cache_fn = EverythingDB.CACHE_FN
    if not use_cache or not path.exists(cache_fn) or path.getmtime(fn) > path.getmtime(cache_fn):
        db = EverythingDB.from_db(fn)
        db.tofile(cache_fn)
        return db
    else:
        return EverythingDB.from_cache(cache_fn)


def test_string_buffer():
    sb = StringBuffer.from_items([b"bcabcdbcdbcbcbc", b"xyz", b"ahbca", b"1234"])
    assert sb[1] == b"xyz"
    flag = "find"
    assert list(sb.find_all(b"bc", method=flag)) == [0, 2]
    assert list(sb.find_all(b"xyz", method=flag)) == [1]
    assert list(sb.find_all(b"123", method=flag)) == [3]
    assert list(sb.find_all(b"234", method=flag)) == [3]
    assert list(sb.find_all(b"12345", method=flag)) == []
    flag = "re"
    assert list(sb.find_all(b".*bc.*", method=flag)) == [0, 2]
    assert list(sb.find_all(b".*xyz.*", method=flag)) == [1]
    assert list(sb.find_all(b".*123.*", use_re=flag)) == [3]
    assert list(sb.find_all(b".*234.*", method=flag)) == [3]
    assert list(sb.find_all(b".*12345.*", method=flag)) == []


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file_pattern", help="filename")
    parser.add_argument("-f", "--folder", help="folder pattern", type=str, default="")
    parser.add_argument("-c", "--content", help="content pattern", type=str, default="")

    args = parser.parse_args()
    db = open_everything()

    def find_files():
        for p in db.find_all(args.file_pattern, method="fnmatch"):
            yield p

    def filter_folder(items):
        return (p for p in items if args.folder in path.dirname(p))

    def filter_content(items):
        for p in items:
            if not path.exists(p):
                continue

            if path.getsize(p) > 50e6:
                yield  p, "too big"
            else:
                try:
                    with open(p, "rb") as f:
                        text = f.read()
                        if args.content in text:
                            yield p
                except IOError:
                    yield p, "can't read"

    items = find_files()

    if args.folder:
        items = filter_folder(items)
    if args.content:
        items = filter_content(items)

    for item in items:
        fn, info = item if isinstance(item, tuple) else (item, "")
        fn = fn.decode("utf8").encode(sys.stdout.encoding, errors="replace")
        if info:
            print("{} {}".format(fn, info))
        else:
            print(fn)

if __name__ == '__main__':
    main()
