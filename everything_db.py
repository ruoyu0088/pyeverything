from os import path
import cPickle
from array import array
import bz2
import struct

FOLDER_COUNT_POS = 0x0c
ENTRY_POS = 0x4e


class EverythingDB(object):
    CACHE_FN = path.join(path.dirname(__file__), "everything.cache")

    def __init__(self, fn):
        if not path.exists(self.CACHE_FN) or path.getmtime(fn) > path.getmtime(self.CACHE_FN):
            self._load_db(fn)
            with open(self.CACHE_FN, "wb") as f:
                cPickle.dump((self.items, self.parents), f, protocol=cPickle.HIGHEST_PROTOCOL)
        else:
            with open(self.CACHE_FN, "rb") as f:
                self.items, self.parents = cPickle.load(f)

    def _load_db(self, fn):
        with bz2.BZ2File(fn) as f:
            f.seek(FOLDER_COUNT_POS)
            folder_count, file_count = struct.unpack("LL", f.read(8))
            f.seek(ENTRY_POS, 0)

            last_str = ""

            items = []
            locations = []
            parents_buffer = bytearray()

            loc = 0
            for i in xrange(folder_count):
                locations.append(loc)
                info = f.read(0x11)
                parents_buffer.extend(info[-8:-4])
                length = ord(f.read(1))
                if length == 0:
                    drop_length = 0
                else:
                    drop_length = ord(f.read(1))

                if length != 0:
                    s = f.read(length)
                    last_str = last_str[:len(last_str)-drop_length] + s
                items.append(last_str)
                loc += len(last_str) + 14

            last_str = ""

            for i in xrange(file_count):
                info = f.read(4)
                parents_buffer.extend(info)
                length = ord(f.read(1))
                drop_length = 0 if not length else ord(f.read(1))
                if length != 0:
                    s = f.read(length)
                    last_str = last_str[:len(last_str)-drop_length] + s
                items.append(last_str)

            parents = array("L")
            parents.fromstring(str(parents_buffer))

            location_map = {loc:idx for idx, loc in enumerate(locations)}
            location_map[0xffffffff] = -1
            parents = [location_map[loc] for loc in parents]
            self.items = items
            self.parents = parents

    def full_path(self, idx):
        names = [self.items[idx]]
        while True:
            idx = self.parents[idx]
            if idx == -1:
                break
            names.append(self.items[idx])
        return "/".join(names[::-1])

    def find_all(self, pattern, use_re=False):
        if not use_re:
            index_list = (i for i, name in enumerate(self.items) if pattern in name)
        else:
            import re
            pattern = re.compile(pattern, re.IGNORECASE)
            method = pattern.match
            index_list = (i for i, name in enumerate(self.items) if method(name))

        items = self.items
        parents = self.parents

        names = []
        append = names.append
        for index in index_list:
            del names[:]
            while True:
                append(items[index])                
                index = parents[index]
                if index == -1:
                    break
            yield "/".join(reversed(names))

    def __sizeof__(self):
        size1 = sys.getsizeof(self.parents) + sum(sys.getsizeof(x) for x in self.parents)
        size2 = sys.getsizeof(self.items) + sum(sys.getsizeof(x) for x in self.items)
        return sys.getsizeof(self.__dict__) + size1 + size2


if __name__ == '__main__':
    fn = r"C:\Program Files\Everything\Everything.db"
    import sys
    import time
    start = time.clock()
    db = EverythingDB(fn)
    print time.clock() - start
    start = time.clock()
    res = list(db.find_all(sys.argv[1], use_re=True))
    #print time.clock() - start
    print "\n".join(res)
    with open("result.txt", "w") as f:
        f.write("\n".join(res))
