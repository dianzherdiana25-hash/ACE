"""Latihan gelombang kedua dipisah agar modul mandiri mudah ditelaah dan diuji."""

from textwrap import dedent
from typing import Any


LANGUAGE_WAVE2: list[dict[str, Any]] = [
    {
        "skill_name": "analisis_konfiks_pe_an_ke_an",
        "domain": "linguistics_confix",
        "title": "Konfiks pe-an dan ke-an",
        "goal": "Mengenali kata dasar dan kategori konfiks pada bentuk berimbuhan yang dikenal",
        "target_file": "projects/learning_lab/bahasa/konfiks_pe_ke.py",
        "verification_str": "KONFIKS_PE_KE_VERIFIED_OK",
        "preconditions": ["Satu kata bahasa Indonesia"],
        "procedure_steps": [
            "Normalisasi spasi dan kapitalisasi",
            "Cocokkan bentuk yang dikenal dengan leksikon beranotasi",
            "Kembalikan kata dasar dan kelompok konfiks",
        ],
        "boundary_limitations": [
            "Leksikon kecil termasuk bentuk peN-an dengan perubahan bunyi",
            "Bentuk di luar leksikon tidak ditebak",
        ],
        "capability_id": "cap_analisis_konfiks_pe_an_ke_an",
        "capability_name": "Analisis Konfiks pe-an dan ke-an",
        "code": dedent("""
            KONFIKS = {
                'pekerjaan': ('kerja', 'pe-an'),
                'perawatan': ('rawat', 'peN-an'),
                'pembacaan': ('baca', 'peN-an'),
                'penulisan': ('tulis', 'peN-an'),
                'penggunaan': ('guna', 'peN-an'),
                'kebaikan': ('baik', 'ke-an'),
                'kebersihan': ('bersih', 'ke-an'),
                'kesulitan': ('sulit', 'ke-an'),
            }

            def analisis_konfiks(kata: str) -> dict[str, str] | None:
                pasangan = KONFIKS.get(kata.strip().casefold())
                if pasangan is None:
                    return None
                dasar, kelompok = pasangan
                return {'kata_dasar': dasar, 'konfiks': kelompok}

            if __name__ == '__main__':
                assert analisis_konfiks(' Pekerjaan ') == {'kata_dasar': 'kerja', 'konfiks': 'pe-an'}
                assert analisis_konfiks('penulisan') == {'kata_dasar': 'tulis', 'konfiks': 'peN-an'}
                assert analisis_konfiks('kebersihan') == {'kata_dasar': 'bersih', 'konfiks': 'ke-an'}
                assert analisis_konfiks('ketan') is None
                assert analisis_konfiks('') is None
                print('KONFIKS_PE_KE_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "makna_kata_ulang_id",
        "domain": "linguistics_reduplication",
        "title": "Kata Ulang dan Ragam Maknanya",
        "goal": "Mengenali reduplikasi penuh serta membedakan makna jamak, intensitas, dan bentuk leksikal",
        "target_file": "projects/learning_lab/bahasa/kata_ulang.py",
        "verification_str": "KATA_ULANG_MAKNA_VERIFIED_OK",
        "preconditions": ["Teks bahasa Indonesia dengan ejaan kata ulang bertanda hubung"],
        "procedure_steps": [
            "Temukan pasangan kata bertanda hubung",
            "Periksa bentuk leksikal khusus sebelum pola reduplikasi penuh",
            "Laporkan makna leksikon atau tandai makna yang bergantung konteks",
        ],
        "boundary_limitations": [
            "Makna di luar leksikon dan pengulangan sebagian tidak diputuskan",
        ],
        "capability_id": "cap_makna_kata_ulang_id",
        "capability_name": "Pengenalan Kata Ulang dan Maknanya",
        "code": dedent(r"""
            import re

            MAKNA = {
                'buku-buku': 'jamak',
                'anak-anak': 'jamak',
                'keras-keras': 'intensitas',
                'pelan-pelan': 'cara',
                'berulang-ulang': 'frekuensi',
                'lauk-pauk': 'keanekaragaman',
                'kupu-kupu': 'leksikal',
            }

            def kata_ulang(teks: str) -> list[tuple[str, str]]:
                hasil = []
                for token in re.findall(r'\b[^\W\d_]+(?:-[^\W\d_]+)+\b', teks.casefold()):
                    if token in MAKNA:
                        hasil.append((token, MAKNA[token]))
                    else:
                        bagian = token.split('-')
                        if len(bagian) == 2 and bagian[0] == bagian[1]:
                            hasil.append((token, 'perlu_konteks'))
                return hasil

            if __name__ == '__main__':
                assert kata_ulang('Buku-buku dibaca pelan-pelan.') == [
                    ('buku-buku', 'jamak'), ('pelan-pelan', 'cara'),
                ]
                assert kata_ulang('Kupu-kupu dan lauk-pauk') == [
                    ('kupu-kupu', 'leksikal'), ('lauk-pauk', 'keanekaragaman'),
                ]
                assert kata_ulang('pagi-pagi, non-aktif, pagi-pagi-pagi') == [
                    ('pagi-pagi', 'perlu_konteks'),
                ]
                print('KATA_ULANG_MAKNA_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "susun_kalimat_pasif_persona",
        "domain": "linguistics_personal_passive",
        "title": "Kalimat Pasif Persona",
        "goal": "Menyusun pola objek, aspek, pelaku pronominal dan verba dasar",
        "target_file": "projects/learning_lab/bahasa/pasif_persona.py",
        "verification_str": "PASIF_PERSONA_VERIFIED_OK",
        "preconditions": ["Objek, pronomina pelaku, aspek opsional, dan verba dasar diberikan terpisah"],
        "procedure_steps": [
            "Periksa pronomina, penanda aspek, dan verba terhadap himpunan yang didukung",
            "Tempatkan objek di awal dan rapatkan pelaku dengan verba",
            "Susun kalimat lengkap",
        ],
        "boundary_limitations": ["Pola deklaratif sederhana dengan verba transitif yang terdaftar"],
        "capability_id": "cap_susun_kalimat_pasif_persona",
        "capability_name": "Penyusunan Kalimat Pasif Persona",
        "code": dedent("""
            PELAKU = {'saya', 'aku', 'kami', 'kita', 'kamu', 'anda', 'dia', 'mereka'}
            ASPEK = {'', 'sudah', 'sedang', 'akan', 'belum'}
            VERBA_DASAR = {'baca', 'beli', 'gambar', 'kirim', 'tulis'}

            def pasif_persona(objek: str, pelaku: str, verba: str, aspek: str = '') -> str:
                objek, pelaku, verba, aspek = (bagian.strip() for bagian in (objek, pelaku, verba, aspek))
                pronomina = pelaku.casefold()
                if not objek or pronomina not in PELAKU or verba not in VERBA_DASAR or aspek not in ASPEK:
                    raise ValueError('Komponen berada di luar pola pasif persona.')
                kata = [objek[0].upper() + objek[1:]]
                if aspek:
                    kata.append(aspek)
                kata.extend(['Anda' if pronomina == 'anda' else pronomina, verba])
                return ' '.join(kata) + '.'

            if __name__ == '__main__':
                assert pasif_persona('surat itu', 'saya', 'kirim', 'sudah') == 'Surat itu sudah saya kirim.'
                assert pasif_persona('buku itu', 'Anda', 'baca') == 'Buku itu Anda baca.'
                try:
                    pasif_persona('buku itu', 'saya', 'membaca')
                except ValueError:
                    pass
                else:
                    raise AssertionError('Verba berprefiks aktif harus ditolak.')
                print('PASIF_PERSONA_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "urai_konjungsi_sebab_akibat",
        "domain": "linguistics_causal_conjunction",
        "title": "Konjungsi Sebab dan Akibat",
        "goal": "Memisahkan klausa sebab dan akibat menurut arah hubungan konjungsi",
        "target_file": "projects/learning_lab/bahasa/konjungsi_kausal.py",
        "verification_str": "KONJUNGSI_KAUSAL_VERIFIED_OK",
        "preconditions": ["Satu kalimat dengan dua klausa dan satu konjungsi kausal eksplisit"],
        "procedure_steps": [
            "Temukan konjungsi pada batas kata",
            "Pisahkan klausa sesuai posisi konjungsi",
            "Kembalikan sebab dan akibat hanya untuk pola yang tidak ambigu",
        ],
        "boundary_limitations": ["Pola sederhana karena, sebab, sehingga, dan maka tanpa kutipan atau kausalitas bertingkat"],
        "capability_id": "cap_urai_konjungsi_sebab_akibat",
        "capability_name": "Penguraian Konjungsi Sebab–Akibat",
        "code": dedent(r"""
            import re

            PENGHUBUNG = re.compile(r'\b(karena|sebab|sehingga|maka)\b', re.IGNORECASE)

            def uraikan_kausal(teks: str) -> dict[str, str] | None:
                kalimat = teks.strip().rstrip('.!?')
                cocok = list(PENGHUBUNG.finditer(kalimat))
                if len(cocok) != 1:
                    return None
                penanda = cocok[0]
                sebelum = kalimat[:penanda.start()].strip(' ,')
                sesudah = kalimat[penanda.end():].strip()
                konjungsi = penanda.group().casefold()
                if konjungsi in {'karena', 'sebab'} and not sebelum:
                    sebab, pemisah, akibat = sesudah.partition(',')
                    if not pemisah:
                        return None
                elif konjungsi in {'karena', 'sebab'}:
                    sebab, akibat = sesudah, sebelum
                else:
                    sebab, akibat = sebelum, sesudah
                if not sebab.strip() or not akibat.strip():
                    return None
                return {'sebab': sebab.strip(), 'akibat': akibat.strip()}

            if __name__ == '__main__':
                target = {'sebab': 'hujan deras', 'akibat': 'jalan licin'}
                assert uraikan_kausal('Karena hujan deras, jalan licin.') == target
                assert uraikan_kausal('jalan licin sebab hujan deras') == target
                assert uraikan_kausal('hujan deras sehingga jalan licin') == target
                assert uraikan_kausal('jalan licin karena hujan deras sehingga siswa pulang') is None
                assert uraikan_kausal('kebersebabannya belum jelas') is None
                print('KONJUNGSI_KAUSAL_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "parafrasa_kalimat_panjang_id",
        "domain": "linguistics_paraphrase",
        "title": "Parafrasa Kalimat Panjang",
        "goal": "Memindahkan klausa sebab ke awal sambil menjaga fakta dan relasi kalimat",
        "target_file": "projects/learning_lab/bahasa/parafrasa_kalimat.py",
        "verification_str": "PARAFRASA_PANJANG_VERIFIED_OK",
        "preconditions": ["Kalimat deklaratif berbentuk akibat karena sebab"],
        "procedure_steps": [
            "Pisahkan dua klausa pada konjungsi karena",
            "Pastikan masing-masing klausa utuh dan pola tunggal",
            "Susun Karena [sebab], [akibat] tanpa mengganti kata bermakna",
        ],
        "boundary_limitations": [
            "Pola satu sebab, dengan daftar nama diri untuk mempertahankan kapitalisasi awal klausa",
        ],
        "capability_id": "cap_parafrasa_kalimat_panjang_id",
        "capability_name": "Parafrasa Kalimat Panjang dengan Relasi Kausal",
        "code": dedent(r"""
            import re

            def parafrasa(teks: str, proper_nouns: set[str] | None = None) -> str | None:
                kalimat = teks.strip()
                klausa = re.split(r'\s+karena\s+', kalimat.removesuffix('.'), flags=re.IGNORECASE)
                if len(klausa) != 2:
                    return None
                akibat, sebab = (bagian.strip() for bagian in klausa)
                if not akibat or not sebab or re.search(r'[.!?,:;]', akibat + sebab):
                    return None
                kata_awal = akibat.split()[0]
                if kata_awal.istitle() and kata_awal not in (proper_nouns or set()):
                    akibat = akibat[0].lower() + akibat[1:]
                return f'Karena {sebab}, {akibat}.'

            if __name__ == '__main__':
                sumber = ('Panitia memindahkan tiga sesi diskusi ke ruang kecil pada sore hari '
                          'karena sistem suara di aula utama perlu diperiksa sampai tengah hari.')
                assert parafrasa(sumber) == (
                    'Karena sistem suara di aula utama perlu diperiksa sampai tengah hari, '
                    'panitia memindahkan tiga sesi diskusi ke ruang kecil pada sore hari.'
                )
                assert parafrasa('Rani pulang karena hujan.', {'Rani'}) == 'Karena hujan, Rani pulang.'
                assert parafrasa('ACE berhenti karena ruang habis.') == 'Karena ruang habis, ACE berhenti.'
                assert parafrasa('Kalimat ini tidak mempunyai klausa sebab.') is None
                print('PARAFRASA_PANJANG_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "deteksi_kalimat_efektif_id",
        "domain": "linguistics_effective_sentence",
        "title": "Deteksi Kalimat Efektif",
        "goal": "Menandai pemborosan kata yang umum sebagai bahan telaah kalimat",
        "target_file": "projects/learning_lab/bahasa/kalimat_efektif.py",
        "verification_str": "KALIMAT_EFEKTIF_VERIFIED_OK",
        "preconditions": ["Satu kalimat dalam ragam formal"],
        "procedure_steps": [
            "Tokenisasi kata dan pertahankan bentuk ulang",
            "Temukan pasangan mubazir dalam segmen yang sama",
            "Laporkan pola dan bagian kalimat yang terindikasi",
        ],
        "boundary_limitations": ["Pemeriksaan indikasi berbasis pola terbatas, tanpa penilaian struktur kalimat umum"],
        "capability_id": "cap_deteksi_kalimat_efektif_id",
        "capability_name": "Deteksi Indikasi Pemborosan Kalimat",
        "code": dedent(r"""
            import re

            REDUNDANSI = (
                ('tujuan_ganda', r'\b(?:agar supaya|demi untuk)\b'),
                ('waktu_ganda', r'\bsejak dari\b'),
                ('jamak_ganda', r'\bpara ([^\W\d_]+)-\1\b'),
            )

            def indikasi_kalimat(teks: str) -> list[tuple[str, str]]:
                hasil = []
                for tipe, pola in REDUNDANSI:
                    hasil.extend((cocok.start(), tipe, cocok.group())
                                 for cocok in re.finditer(pola, teks, flags=re.IGNORECASE))
                return [(tipe, kutipan) for _, tipe, kutipan in sorted(hasil)]

            if __name__ == '__main__':
                assert indikasi_kalimat('Para siswa-siswa belajar agar supaya lulus.') == [
                    ('jamak_ganda', 'Para siswa-siswa'), ('tujuan_ganda', 'agar supaya'),
                ]
                assert indikasi_kalimat('Kami menunggu sejak dari subuh.') == [('waktu_ganda', 'sejak dari')]
                assert indikasi_kalimat('Para siswa belajar agar lulus.') == []
                assert indikasi_kalimat('Ia ingin agar, supaya lebih jelas, bagian itu diulang.') == []
                print('KALIMAT_EFEKTIF_VERIFIED_OK')
        """),
    },
]


TECHNICAL_WAVE2: list[dict[str, Any]] = [
    {
        "skill_name": "struktur_binary_search_tree_dasar",
        "domain": "engineering_binary_search_tree",
        "title": "Binary Search Tree Dasar",
        "goal": "Menyisipkan dan mencari bilangan bulat serta mengunjungi kunci secara terurut",
        "target_file": "projects/learning_lab/teknis/binary_search_tree.py",
        "verification_str": "BINARY_SEARCH_TREE_VERIFIED_OK",
        "preconditions": ["Masukan berupa bilangan bulat yang dapat dibandingkan"],
        "procedure_steps": [
            "Telusuri cabang kiri atau kanan berdasarkan perbandingan kunci",
            "Simpan kunci baru dan abaikan duplikat",
            "Telusuri simpul secara in-order dengan stack eksplisit",
        ],
        "boundary_limitations": ["Pohon tidak menyeimbangkan dirinya dan tidak menyediakan penghapusan"],
        "capability_id": "cap_struktur_binary_search_tree",
        "capability_name": "Penyisipan dan Pencarian Binary Search Tree",
        "code": dedent("""
            from dataclasses import dataclass

            @dataclass
            class Node:
                key: int
                left: 'Node | None' = None
                right: 'Node | None' = None

            class BinarySearchTree:
                def __init__(self) -> None:
                    self.root: Node | None = None

                def insert(self, key: int) -> bool:
                    if self.root is None:
                        self.root = Node(key)
                        return True
                    node = self.root
                    while key != node.key:
                        side = 'left' if key < node.key else 'right'
                        child = getattr(node, side)
                        if child is None:
                            setattr(node, side, Node(key))
                            return True
                        node = child
                    return False

                def contains(self, key: int) -> bool:
                    node = self.root
                    while node is not None:
                        if key == node.key:
                            return True
                        node = node.left if key < node.key else node.right
                    return False

                def keys(self) -> list[int]:
                    order, stack = [], []
                    node = self.root
                    while stack or node is not None:
                        while node is not None:
                            stack.append(node)
                            node = node.left
                        node = stack.pop()
                        order.append(node.key)
                        node = node.right
                    return order

            if __name__ == '__main__':
                tree = BinarySearchTree()
                assert tree.keys() == [] and not tree.contains(5)
                for key in (5, 3, 7, 6, -1):
                    assert tree.insert(key)
                assert not tree.insert(3)
                assert tree.root.left.key == 3 and tree.root.right.key == 7
                assert tree.keys() == [-1, 3, 5, 6, 7]
                assert tree.contains(6) and not tree.contains(4)
                print('BINARY_SEARCH_TREE_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "urut_topologis_graf_dependensi",
        "domain": "engineering_topological_sort",
        "title": "Topological Sort",
        "goal": "Mengurutkan aktivitas agar setiap dependensi diselesaikan sebelum aktivitas pemakainya",
        "target_file": "projects/learning_lab/teknis/topological_sort.py",
        "verification_str": "TOPOLOGICAL_SORT_VERIFIED_OK",
        "preconditions": ["Pemetaan nama aktivitas ke daftar dependensi pada aktivitas yang terdaftar"],
        "procedure_steps": [
            "Hitung indegree tiap aktivitas dan bangun indeks aktivitas pemakai",
            "Ambil aktivitas tanpa dependensi tersisa menurut urutan nama",
            "Tolak graf bila aktivitas tersisa setelah antrian kosong",
        ],
        "boundary_limitations": ["Operasi lokal pada graf berarah dengan nama simpul string"],
        "capability_id": "cap_urut_topologis_graf_dependensi",
        "capability_name": "Pengurutan Topologis dan Deteksi Siklus",
        "code": dedent("""
            import heapq

            def topological_sort(dependencies: dict[str, list[str]]) -> list[str]:
                indegree = {}
                consumers = {task: [] for task in dependencies}
                for task, prerequisites in dependencies.items():
                    unique = set(prerequisites)
                    indegree[task] = len(unique)
                    for prerequisite in unique:
                        if prerequisite not in consumers:
                            raise ValueError('Dependensi tidak terdaftar.')
                        consumers[prerequisite].append(task)
                ready = [task for task, count in indegree.items() if count == 0]
                heapq.heapify(ready)
                order = []
                while ready:
                    task = heapq.heappop(ready)
                    order.append(task)
                    for consumer in consumers[task]:
                        indegree[consumer] -= 1
                        if indegree[consumer] == 0:
                            heapq.heappush(ready, consumer)
                if len(order) != len(dependencies):
                    raise ValueError('Siklus dependensi terdeteksi.')
                return order

            if __name__ == '__main__':
                graph = {'publish': ['review', 'review'], 'review': ['build'], 'build': [], 'backup': []}
                expected = ['backup', 'build', 'review', 'publish']
                assert topological_sort(graph) == expected
                assert topological_sort(dict(reversed(tuple(graph.items())))) == expected
                assert topological_sort({}) == []
                for invalid in ({'a': ['b'], 'b': ['a']}, {'a': ['hilang']}):
                    try:
                        topological_sort(invalid)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Graf tidak sah harus ditolak.')
                print('TOPOLOGICAL_SORT_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "maksimum_sliding_window_linear",
        "domain": "engineering_sliding_window",
        "title": "Sliding-Window Maksimum",
        "goal": "Menghitung maksimum seluruh jendela berukuran tetap dalam waktu linear",
        "target_file": "projects/learning_lab/teknis/sliding_window_max.py",
        "verification_str": "SLIDING_WINDOW_MAX_VERIFIED_OK",
        "preconditions": ["Daftar bilangan bulat dan ukuran jendela antara satu dan panjang daftar"],
        "procedure_steps": [
            "Buang indeks dari depan deque saat keluar jendela",
            "Buang kandidat yang didominasi nilai baru dari belakang",
            "Ambil maksimum dari indeks terdepan",
        ],
        "boundary_limitations": ["Ukuran jendela tetap untuk satu pemanggilan"],
        "capability_id": "cap_maksimum_sliding_window_linear",
        "capability_name": "Sliding-Window Maksimum dengan Deque Monoton",
        "code": dedent("""
            from collections import deque

            def window_max(values: list[int], width: int) -> list[int]:
                if type(width) is not int or not 1 <= width <= len(values):
                    raise ValueError('Ukuran jendela tidak sah.')
                candidates = deque()
                maxima = []
                for index, value in enumerate(values):
                    while candidates and candidates[0] <= index - width:
                        candidates.popleft()
                    while candidates and values[candidates[-1]] <= value:
                        candidates.pop()
                    candidates.append(index)
                    if index + 1 >= width:
                        maxima.append(values[candidates[0]])
                return maxima

            if __name__ == '__main__':
                values = [1, 3, -1, -3, 5, 3, 6, 7]
                assert window_max(values, 3) == [3, 3, 5, 5, 6, 7]
                assert window_max([-3, -3, -5], 2) == [-3, -3]
                assert window_max(values, 1) == values
                assert window_max(values, len(values)) == [7]
                try:
                    window_max([], 1)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Jendela melebihi masukan harus ditolak.')
                print('SLIDING_WINDOW_MAX_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "parser_ekspresi_aritmetika_tanpa_eval",
        "domain": "engineering_expression_parser",
        "title": "Parser Ekspresi Aritmetika Tanpa Eval",
        "goal": "Menghitung ekspresi aritmetika berpresedensi dengan parser rekursif dan pecahan eksak",
        "target_file": "projects/learning_lab/teknis/parser_aritmetika.py",
        "verification_str": "PARSER_ARITMETIKA_VERIFIED_OK",
        "preconditions": ["Ekspresi dengan bilangan bulat, +, -, *, /, dan tanda kurung"],
        "procedure_steps": [
            "Tokenisasi dan tolak karakter di luar grammar",
            "Parse penjumlahan, perkalian dan atom menurut presedensi",
            "Hitung dengan Fraction dan tolak token sisa",
        ],
        "boundary_limitations": [
            "Tidak mencakup variabel, eksponen atau literal desimal",
            "Masukan dibatasi 128 token dan 256 karakter",
        ],
        "capability_id": "cap_parser_ekspresi_aritmetika",
        "capability_name": "Parsing Aritmetika dengan Presedensi dan Fraction",
        "code": dedent(r"""
            from fractions import Fraction
            import re

            def calculate(expression: str) -> Fraction:
                if len(expression) > 256:
                    raise ValueError('Ekspresi terlalu panjang.')
                tokens = re.findall(r'[0-9]+|\S', expression)
                if not tokens or len(tokens) > 128:
                    raise ValueError('Jumlah token tidak sah.')
                position = 0

                def peek() -> str:
                    return tokens[position] if position < len(tokens) else ''

                def take() -> str:
                    nonlocal position
                    token = peek()
                    if not token:
                        raise ValueError('Akhir ekspresi tak terduga.')
                    position += 1
                    return token

                def atom() -> Fraction:
                    token = take()
                    if token == '+':
                        return atom()
                    if token == '-':
                        return -atom()
                    if token == '(':
                        value = addition()
                        if take() != ')':
                            raise ValueError('Tanda kurung tutup diperlukan.')
                        return value
                    if not re.fullmatch('[0-9]+', token):
                        raise ValueError('Bilangan bulat diperlukan.')
                    return Fraction(int(token))

                def multiplication() -> Fraction:
                    value = atom()
                    while peek() in ('*', '/'):
                        operator = take()
                        right = atom()
                        value = value * right if operator == '*' else value / right
                    return value

                def addition() -> Fraction:
                    value = multiplication()
                    while peek() in ('+', '-'):
                        operator = take()
                        right = multiplication()
                        value = value + right if operator == '+' else value - right
                    return value

                result = addition()
                if peek():
                    raise ValueError('Token sisa setelah ekspresi.')
                return result

            if __name__ == '__main__':
                assert calculate('2 + 3 * 4') == 14
                assert calculate('(2 + 3) * -4') == -20
                assert calculate('1 / 3 + 1 / 6') == Fraction(1, 2)
                assert calculate('8 / 4 / 2') == 1
                for invalid in ('', '(2 + 3', '2 ** 3', '1 2', 'x + 1'):
                    try:
                        calculate(invalid)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Ekspresi tidak sah harus ditolak.')
                try:
                    calculate('1 / (2 - 2)')
                except ZeroDivisionError:
                    pass
                else:
                    raise AssertionError('Pembagian nol harus ditolak.')
                print('PARSER_ARITMETIKA_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "simulasi_antrean_prioritas_stabil",
        "domain": "engineering_priority_queue",
        "title": "Simulasi Antrean Prioritas dengan heapq",
        "goal": "Menjadwalkan pekerjaan menurut prioritas dan urutan kedatangan saat seri",
        "target_file": "projects/learning_lab/teknis/priority_queue_sim.py",
        "verification_str": "PRIORITY_QUEUE_SIM_VERIFIED_OK",
        "preconditions": ["Daftar operasi masuk dengan prioritas bilangan bulat atau layanan antrean"],
        "procedure_steps": [
            "Simpan prioritas dan nomor urut kedatangan sebagai kunci heap",
            "Layani pekerjaan teratas dan catat layanan kosong",
            "Kembalikan catatan layanan sesuai urutan operasi",
        ],
        "boundary_limitations": ["Simulasi satu pelayan lokal tanpa waktu nyata atau pembatalan"],
        "capability_id": "cap_simulasi_antrean_prioritas_stabil",
        "capability_name": "Simulasi Antrean Prioritas Stabil",
        "code": dedent("""
            import heapq
            from itertools import count

            def simulate(operations: list[tuple[int, str] | None]) -> list[str | None]:
                sequence = count()
                queue = []
                served = []
                for operation in operations:
                    if operation is None:
                        served.append(heapq.heappop(queue)[2] if queue else None)
                    else:
                        priority, job = operation
                        heapq.heappush(queue, (priority, next(sequence), job))
                return served

            if __name__ == '__main__':
                jobs = [(2, 'laporan'), (1, 'darurat'), (1, 'peringatan'), None,
                        (0, 'pemulihan'), None, None, None, None]
                assert simulate(jobs) == ['darurat', 'pemulihan', 'peringatan', 'laporan', None]
                assert simulate([(1, 'z'), (1, 'a'), None, None]) == ['z', 'a']
                assert simulate([]) == []
                print('PRIORITY_QUEUE_SIM_VERIFIED_OK')
        """),
    },
    {
        "skill_name": "validasi_skema_nested_dict",
        "domain": "engineering_nested_schema",
        "title": "Validasi Skema Data Bertingkat",
        "goal": "Memverifikasi field wajib dan tipe nilai nested dict serta menunjukkan lokasi galat",
        "target_file": "projects/learning_lab/teknis/nested_data_schema.py",
        "verification_str": "NESTED_SCHEMA_VERIFIED_OK",
        "preconditions": ["Skema berupa dict nama field ke tipe Python atau subskema dict"],
        "procedure_steps": [
            "Cocokkan field wajib dan laporkan field tambahan",
            "Turun ke subskema hanya saat nilainya dict",
            "Cocokkan tipe secara persis dan simpan path tiap galat",
        ],
        "boundary_limitations": ["Skema sederhana tak bersiklus dengan nama field string dan tanpa field opsional"],
        "capability_id": "cap_validasi_skema_nested_dict",
        "capability_name": "Validasi Nested Dict dengan Path Galat",
        "code": dedent("""
            def validate(value: object, schema: dict) -> list[tuple[tuple[str, ...], str]]:
                errors = []

                def check(node: object, rule: dict | type, path: tuple[str, ...]) -> None:
                    if not isinstance(rule, dict):
                        if type(node) is not rule:
                            errors.append((path, 'tipe'))
                        return
                    if not isinstance(node, dict):
                        errors.append((path, 'tipe'))
                        return
                    if any(not isinstance(key, str) for key in node):
                        errors.append((path, 'nama_field'))
                        return
                    for key in sorted(rule):
                        next_path = path + (key,)
                        if key not in node:
                            errors.append((next_path, 'wajib'))
                        else:
                            check(node[key], rule[key], next_path)
                    for key in sorted(node.keys() - rule.keys()):
                        errors.append((path + (key,), 'tambahan'))

                check(value, schema, ())
                return errors

            if __name__ == '__main__':
                schema = {'nama': str, 'pengaturan': {'retry': int, 'aktif': bool}}
                assert validate({'nama': 'uji', 'pengaturan': {'retry': 3, 'aktif': False}}, schema) == []
                assert validate({'pengaturan': {'retry': True, 'cache': 1}}, schema) == [
                    (('nama',), 'wajib'), (('pengaturan', 'aktif'), 'wajib'),
                    (('pengaturan', 'retry'), 'tipe'), (('pengaturan', 'cache'), 'tambahan'),
                ]
                assert validate({'nama': 'uji', 'pengaturan': None}, schema) == [
                    (('pengaturan',), 'tipe'),
                ]
                assert validate([], schema) == [((), 'tipe')]
                assert validate({1: '', 'nama': 'uji'}, schema) == [((), 'nama_field')]
                print('NESTED_SCHEMA_VERIFIED_OK')
        """),
    },
]
