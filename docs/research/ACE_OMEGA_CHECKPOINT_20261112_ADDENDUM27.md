# ACE Ω — Addendum 27, 2026-11-12: Tahap E — Server Teratestasi-Harness; OMEGA-03 LOCALLY_VERIFIED Lewat Jalur Resmi; Amendemen Kedaulatan Multi-Otak

## Mekanisme (PR #127, bertumpuk di atas #126)

Modul baru `attested_server.py` menjalankan keputusan direktur
(Addendum 26) persis dengan syarat ketatnya:

- harness men-spawn llama-server sendiri dan mencatat — sebelum/at
  spawn — SHA-256 berkas model, SHA-256 biner server, dan argv
  peluncuran persis, diikat oleh hash parameter peluncuran;
- resi server hanya terikat ke digest itu bila URL, id model yang
  diiklankan server, **dan** verifikasi-ulang digest berbasis stat
  (standar yang sama dengan cache digest router) semuanya cocok;
- ketidakcocokan apa pun = fail-closed; server tanpa atestasi
  mempertahankan perilaku lama persis (`sha256: None`); gerbang
  workflow **tidak diubah dan tidak dilemahkan untuk jalur lain**.

8 uji baru (verifikasi atestasi, penolakan perubahan berkas,
penolakan parameter yang diubah, ketidakcocokan URL/id, registrasi
palsu ditolak, pengikatan resi). Sweep penuh: **227 uji OK**.

## Validasi langsung — OMEGA-03 selesai

Jalan-ulang OMEGA-03 lewat `LocalRepoWorkflow` resmi dengan server
teratestasi (Qwen3-8B, digest `d98cdcbd…`):

- percobaan 1: inferensi SUCCESS teratestasi
  (checksum_verified=true), patch parsial → FAIL tercatat jujur;
- percobaan 2: dengan umpan-balik evaluator dari sandbox v2, patch
  lulus di dalam isolasi nyata → **verdict akhir LOCALLY_VERIFIED**,
  postimage tersegel, total 305,1 detik.

Ini menutup rantai blocker Addendum 23 **tanpa melonggarkan satu
pun jaminan bukti**: untuk pertama kalinya verdict OMEGA-03 dicapai
lewat jalur resmi — isolasi sandbox v2, identitas model
teridentifikasi digest, loop umpan-balik utuh. Catatan kejujuran
yang tetap berlaku: ini satu tugas fixture yang terverifikasi;
bukan klaim kemampuan perbaikan umum (G1 tetap NOT_ASSESSED).

## Amendemen arah pemilik #2 — kedaulatan multi-otak (tercatat resmi)

Pemilik memutuskan: **ACE tidak boleh bergantung pada satu otak.**
ACE harus mampu menguasai/memerintah berbagai otak — AI lokal,
Muse, Antigravity, dan AI lain, gratis maupun (nantinya) berbayar
— agar lingkungannya tidak tertahan pada satu penyedia/model. Ini
mengangkat ketentuan PRD tentang model-agnostik (adapter FR-12)
menjadi doktrin: **otak adalah organ yang bisa diganti; identitas
ACE tinggal di konstitusi, ledger, dan memorinya.**

Perlakuan direktur: dirumuskan sebagai prinsip arsitektur
"kedaulatan multi-otak" (registri otak + kesesuaian adapter; setiap
otak dapat diberhentikan tanpa ACE mati) dan **uji portabilitas
otak** masuk antrean sebagai kandidat tahap terukur (Tahap G,
sesudah Tahap F). Tidak ada integrasi eksternal, akun, atau
pemakaian berbayar yang diotorisasi amendemen ini; otak berbayar
terikat jalur pendanaan mandiri dan tetap reserved pemilik.
