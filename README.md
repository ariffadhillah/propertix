Mantap 🔥 sekarang kita bahas cara menjalankan CLI dengan struktur yang sudah kamu buat.

Kamu menjalankan via:

py -m scripts.cli

Berikut semua skenario yang kamu punya sekarang 👇

✅ 1️⃣ Production Mode (JSONL only)

Menulis ke:

out/

state/

Jalankan site normal
py -m scripts.cli --start bali-home-immo
Dengan limit 10
py -m scripts.cli --start bali-home-immo --limit 10
Snapshot mode (tulis semua termasuk unchanged)
py -m scripts.cli --start bali-home-immo --mode snapshot
Force JSONL sink
py -m scripts.cli --start bali-home-immo --sink jsonl
✅ 2️⃣ Test / Development Mode

Menulis ke:

out_test/

state_test/

atau SQLite (tergantung sink)

Basic test run
py -m scripts.cli --start-test bali-home-immo --limit 10

Default behavior:

env=test

sink=auto → biasanya SQLite atau both (sesuai CLI kamu)

✅ 3️⃣ Test Mode + SQLite Only
py -m scripts.cli --start-test bali-home-immo --limit 10 --sink sqlite

Output:

state_test/bali-home-immo.sqlite

tidak peduli file jsonl

✅ 4️⃣ Test Mode + JSONL + SQLite (Recommended 🔥)

Kalau kamu sudah pakai MultiSink:

py -m scripts.cli --start-test bali-home-immo --limit 10 --sink both

Ini akan:

simpan ke SQLite

simpan ke JSONL

kamu bisa cek struktur JSONL tanpa buka database

✅ 5️⃣ Snapshot Mode di Test (Supaya JSONL Tidak Kosong)

Kalau kamu ingin file JSONL selalu ada isi walaupun unchanged:

py -m scripts.cli --start-test bali-home-immo --limit 10 --sink both --mode snapshot
✅ 6️⃣ Dry Run (Debug Tanpa Commit State)
py -m scripts.cli --start-test bali-home-immo --limit 10 --dry-run
🔎 Cara Cek SQLite Cepat

Command line:

sqlite3 state_test\bali-home-immo.sqlite
.tables
select listing_key,last_change_type from listings limit 5;

Atau via Python:

py -c "import sqlite3; c=sqlite3.connect('state_test/bali-home-immo.sqlite'); print(c.execute('select count(*) from listings').fetchone())"
🔥 Workflow Paling Ideal Untuk Kamu
Development:
py -m scripts.cli --start-test bali-home-immo --limit 10 --sink both --mode snapshot
Production:
py -m scripts.cli --start bali-home-immo --mode delta

Kalau kamu mau, next step kita bisa bikin:

--start propertia

dan kamu tinggal tambah 1 entry di SITE_REGISTRY.

Kalau mau, kirim isi cli.py kamu sekarang — aku cek sekalian apakah sudah 100% clean untuk multi-site scaling 🚀



Cara jalanin yang “benar” sekarang
PROD full run (tulis JSONL only)
py -m scripts.cli --start bali-home-immo
TEST full run (tulis ke SQLite + JSONL)
py -m scripts.cli --start-test bali-home-immo
Snapshot mode (supaya JSONL selalu ada isinya setiap run)
py -m scripts.cli --start-test bali-home-immo --mode snapshot