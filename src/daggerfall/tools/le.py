# LE（DOS/4GW）実行ファイルを読み、各オブジェクトを既定の番地に置いて再配置を当てた像を作る
import struct, sys

class LE:
    def __init__(self, path, le_off=None):
        d = open(path, 'rb').read()
        if le_off is None:
            le_off = d.find(b'LE\x00\x00')
        self.d = d
        self.h = h = le_off
        u = lambda o: struct.unpack_from('<I', d, h + o)[0]
        self.page_size = u(0x28)
        self.last_page = u(0x2c)
        self.obj_tab = u(0x40)
        self.nobj = u(0x44)
        self.page_tab = u(0x48)
        self.fixpage_tab = u(0x68)
        self.fixrec_tab = u(0x6c)
        # データページの位置は、LE を指す MZ（DOS/4GW を結合したものは途中にある）からの相対
        mz = 0
        for x in range(0, le_off, 2):
            if d[x:x + 2] == b'MZ' and struct.unpack_from('<I', d, x + 0x3c)[0] + x == le_off:
                mz = x
        self.mz = mz
        self.data_pages = u(0x80) + mz
        self.npages = u(0x14)
        self.eip_obj = u(0x18)
        self.eip = u(0x1c)
        self.esp_obj = u(0x20)
        self.esp = u(0x24)
        self.objs = []
        for i in range(self.nobj):
            o = h + self.obj_tab + i * 24
            vsize, base, flags, pidx, pcnt, _ = struct.unpack_from('<6I', d, o)
            self.objs.append(dict(vsize=vsize, base=base, flags=flags, pidx=pidx, pcnt=pcnt))
        self.build()

    def page_file_off(self, p):  # p: 1-based
        return self.data_pages + (p - 1) * self.page_size

    def build(self):
        d = self.d
        self.img = {}
        for i, ob in enumerate(self.objs):
            buf = bytearray(ob['vsize'] + 0x1000)
            for k in range(ob['pcnt']):
                p = ob['pidx'] + k
                sz = self.page_size if p != self.npages else self.last_page
                fo = self.page_file_off(p)
                buf[k * self.page_size:k * self.page_size + sz] = d[fo:fo + sz]
            self.img[i + 1] = buf
        # 再配置
        h = self.h
        self.fixups = []
        for i, ob in enumerate(self.objs):
            for k in range(ob['pcnt']):
                p = ob['pidx'] + k
                a = struct.unpack_from('<I', d, h + self.fixpage_tab + (p - 1) * 4)[0]
                b = struct.unpack_from('<I', d, h + self.fixpage_tab + p * 4)[0]
                pos = h + self.fixrec_tab + a
                end = h + self.fixrec_tab + b
                while pos < end:
                    src = d[pos]; flg = d[pos + 1]; pos += 2
                    if src & 0x20:
                        cnt = d[pos]; pos += 1
                    else:
                        cnt = None
                        so = struct.unpack_from('<h', d, pos)[0]; pos += 2
                    if (flg & 3) != 0:
                        raise Exception('未対応の再配置 %x' % flg)
                    if flg & 0x40:
                        tobj = struct.unpack_from('<H', d, pos)[0]; pos += 2
                    else:
                        tobj = d[pos]; pos += 1
                    stype = src & 0xf
                    if stype == 2:  # 16bit selector
                        toff = 0
                    elif flg & 0x10:
                        toff = struct.unpack_from('<I', d, pos)[0]; pos += 4
                    else:
                        toff = struct.unpack_from('<H', d, pos)[0]; pos += 2
                    srcs = []
                    if cnt is None:
                        srcs = [so]
                    else:
                        for _ in range(cnt):
                            srcs.append(struct.unpack_from('<h', d, pos)[0]); pos += 2
                    tgt = (self.objs[tobj - 1]['base'] + toff) & 0xffffffff
                    for so in srcs:
                        at = k * self.page_size + so
                        self.fixups.append((i + 1, at, stype, tobj, toff))
                        if at < 0:
                            continue
                        buf = self.img[i + 1]
                        if stype == 7:
                            struct.pack_into('<I', buf, at, tgt)
                        elif stype == 8:  # 32bit self-relative
                            struct.pack_into('<I', buf, at, (tgt - (ob['base'] + at + 4)) & 0xffffffff)
                        elif stype == 2:
                            pass
                        elif stype == 5:
                            struct.pack_into('<H', buf, at, tgt & 0xffff)
                        else:
                            pass

    def read(self, addr, n):
        for i, ob in enumerate(self.objs):
            if ob['base'] <= addr < ob['base'] + ob['vsize']:
                o = addr - ob['base']
                return bytes(self.img[i + 1][o:o + n])
        return None

    def obj_of(self, addr):
        for i, ob in enumerate(self.objs):
            if ob['base'] <= addr < ob['base'] + ob['vsize']:
                return i + 1
        return None

if __name__ == '__main__':
    le = LE(sys.argv[1])
    for i, o in enumerate(le.objs):
        print(i + 1, hex(o['base']), hex(o['vsize']), hex(o['flags']), o['pidx'], o['pcnt'])
    print('eip', le.eip_obj, hex(le.eip), 'fixups', len(le.fixups))
