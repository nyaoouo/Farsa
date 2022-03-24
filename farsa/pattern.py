import re


def wild_card(count: int):
    if not count:
        return b''
    ans = b"(?:.|\\n)"
    if count > 1:
        ans += ("{" + str(count) + "}").encode()
    return ans


def sig_to_pattern(sig: str):
    ans = bytearray()
    flag1 = False
    wild_card_counter = 0
    offset = []
    i = 0
    for i, s in enumerate(sig.split(' ')):
        if not s:
            raise Exception(f'Bad at sig[{i}]')
        if s.startswith('*'):
            if not flag1:
                ans += wild_card(wild_card_counter)
                wild_card_counter = 0
                ans += b'('
                flag1 = True
        elif flag1:
            ans += wild_card(wild_card_counter)
            wild_card_counter = 0
            ans += b')'
            flag1 = False
            offset.append(i)
        if flag1 or s.startswith('?'):
            wild_card_counter += 1
        else:
            if wild_card_counter:
                ans += wild_card(wild_card_counter)
                wild_card_counter = 0
            temp = int(s, 16)
            if temp in special_chars_map:
                ans += b'\\'
            ans.append(temp)
    ans += wild_card(wild_card_counter)
    if flag1:
        ans += b')'
        offset.append(i + 1)
    return bytes(ans), offset


special_chars_map = {i for i in b'()[]{}?*+-|^$\\.&~# \t\n\r\v\f'}


class StaticPatternSearcher:
    def __init__(self, pe):
        self.pe = pe
        self.text_sections = [sect for sect in self.pe.sections if sect.Name.rstrip(b'\0') == b'.text']
        self.section_datas = [sect.get_data() for sect in self.pe.sections]
        self.section_virtual_addresses = [sect.VirtualAddress for sect in self.pe.sections]

    def search_raw_pattern(self, pattern: bytes):
        res = []
        for i in range(len(self.text_sections)):
            va = self.section_virtual_addresses[i]
            res.extend(
                (
                    match.span()[0] + va,
                    [int.from_bytes(g, byteorder='little', signed=True) for g in match.groups()]
                ) for match in re.finditer(bytes(pattern), self.section_datas[i])
            )
        return res

    def search_from_text(self, pattern: str):
        _pattern, offsets = sig_to_pattern(pattern)
        return [(
            address, [g + offsets[i] for i, g in enumerate(groups)]
        ) for address, groups in self.search_raw_pattern(_pattern)]

    def find_address(self, pattern: str):
        return [address for address, offsets in self.search_from_text(pattern)]

    def find_point(self, pattern: str):
        return [[address + offset for offset in offsets] for address, offsets in self.search_from_text(pattern)]

class MemoryPatternSearcher:
    pass

