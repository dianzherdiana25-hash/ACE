# Garis A Tranche 2 (A5) — Laporan Pra-Review Branch Terpin Operator

Menindaklanjuti usulan tranche 2 butir 5 pada [ACE_GARIS_A_AKUNTANSI.md](ACE_GARIS_A_AKUNTANSI.md), `tools/self_dev_git_audit.py` kini menyediakan `pre_review_report(...)` (`ace.self-dev-branch-prereview.v1`) serta subperintah `prereview`:

```sh
python3 tools/self_dev_git_audit.py --repo . prereview \
  --base origin/main --tip HEAD --pin-file pins.json \
  --checkpoint checkpoints/self_dev/v03_researcher_state.json
```

## Kemampuan audit pra-review

1. **Verifikasi commit terpin operator (`strict_oid_clean`)**: memeriksa bahwa `base` merupakan leluhur `tip`, menelusuri seluruh induk commit (termasuk jalur merge), lalu mengklasifikasikan `matched_pinned`, `unexpected_commits`, dan `missing_pinned_commits`.
2. **Deteksi cherry-pick lintas rebase (`cherry_picked_equivalents`)**: mencocokkan `git patch-id --stable` commit non-merge di branch terhadap commit terpin yang ID-nya berubah setelah cherry-pick (`patch_equivalent_clean`), sehingga perbedaan OID karena cherry-pick dibedakan secara eksplisit dari commit asing nyata.
3. **Pelacakan merge commit (`merge_commits`)**: mencatat commit dengan >1 induk beserta daftar induk dan status apakah merge commit itu ikut dipin operator.
4. **Ringkasan perubahan berkas & checkpoint**: melampirkan daftar `changed_files` (`--name-status`) dan `diff_checkpoints` untuk `--checkpoint` yang diminta.

## Cara menjalankan tes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tools.test_self_dev_git_audit tools.test_self_dev_prereview
```
