# Ringkasan Konteks Diskusi dan Status Skripsi

Dokumen ini merangkum seluruh konteks pengerjaan, metodologi, hasil empiris, keputusan revisi yang telah disepakati, serta daftar tindak lanjut dari penyusunan naskah Tugas Akhir Skripsi hingga versi **`Skripsi_71230994_7.docx`** dan arsip kode **`ta_2.txt`**.

---

## 1. Identitas Penelitian

* **Judul:** Implementasi Strategi Trading Berbasis Aturan pada Multi-Indeks Saham Amerika Serikat
* **Penulis:** Putu Gde Kenzie Carlen Mataram (NIM: 71230994)
* **Institusi:** Program Studi Informatika, Fakultas Teknologi Informasi, Universitas Kristen Duta Wacana (UKDW), Yogyakarta (2026)
* **Dosen Pembimbing I:** Yuan Lukito, S.Kom., M.Cs.
* **Dosen Pembimbing II:** Nugroho Agus Haryono, S.Si., M.Si.
* **Berkas Acuan Terakhir:** `Skripsi_71230994_7.docx` (naskah) dan `ta_2.txt` (arsip kode `ta.ipynb`, `param_grid_search.py`, `tools_index/resample_aapl.py`, dan log uji silang 3 preset optimal)

---

## 2. Rumusan Masalah, Tujuan, dan Batasan Penelitian

### Rumusan Masalah
1. Bagaimana merancang sistem perdagangan algoritmik simetris menggunakan pendekatan analisis *multi-timeframe*, indikator *EMA*, dan *ATR Trailing Stop*?
2. Bagaimana menerapkan metode *Grid Search* untuk memperoleh konfigurasi parameter optimal lintas indeks (`NASDAQ 100`, `S&P 500`, dan `DJIA`) serta memvalidasinya secara *out-of-sample* pada saham Apple (`AAPL`)?
3. Bagaimana kinerja sistem perdagangan algoritmik yang telah dioptimasi dalam membatasi risiko penyusutan modal apabila dibandingkan dengan strategi *Buy and Hold*?

### Batasan Masalah
1. **Data dan Periode:** Tiga indeks saham Amerika Serikat (`NASDAQ 100`, `S&P 500`, dan `DJIA`) dari Kaggle pada periode **19 Februari 2018 hingga 10 Mei 2024** sebagai data *in-sample* (2.272 hari kalender), serta saham tunggal Apple (`AAPL`) dari `yfinance` pada periode **26 November 2024 hingga 20 November 2026** sebagai validasi *out-of-sample* (724 hari kalender).
2. **Kerangka Waktu (*Multi-Timeframe*):** Grafik harian (`1D`) sebagai penentu arah tren makro dan grafik per jam (`1H`) sebagai penentu titik eksekusi transaksi mikro.
3. **Indikator Teknikal:** Dibatasi pada *Exponential Moving Average* (`EMA`) dan *Average True Range* (`ATR`) *Trailing Stop*.
4. **Ruang Pencarian *Grid Search*:** Enam parameter ($\delta$, $N_{\text{EMA}}$, $N_{\text{ATR}}$, $k$, $C$, dan $p_{\min}$) dengan ruang pencarian $15.000$ kombinasi per mode eksekusi, atau total $45.000$ evaluasi kombinasi ($135.000$ simulasi individual) untuk tiga mode (*long-only*, *short-only*, dan *combined*).

---

## 3. Ringkasan Metodologi dan Arsitektur Program

### 3.1 Sumber dan Spesifikasi Data Historis

| Instrumen | Kode Variabel | Sumber & Format | Rentang Evaluasi | Baris Bersih (`1D`) | Baris Bersih (`1H`) | Keterangan Khusus |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **S&P 500** | `SPY` | Kaggle (Parquet) | 2018-02-19 s.d. 2024-05-10 | 1.608 | 12.829 | Indeks 500 perusahaan lintas sektor |
| **NASDAQ 100** | `QQQ` | Kaggle (CSV) | 2018-02-19 s.d. 2024-05-10 | 1.600 | 12.769 | Indeks 100 emiten nonfinansial berbasis teknologi |
| **DJIA** | `DJI` | Kaggle (CSV) | 2018-02-19 s.d. 2024-05-10 | 1.609 | 12.850 | Indeks 30 perusahaan *blue-chip* konvensional |
| **Apple** | `AAPL` | `yfinance` v1.8.0 (CSV) | 2024-11-26 s.d. 2026-11-20 | 498 | 3.465 | `prepost=False` (09:30 s.d. 15:30 EST); `1D` hasil *resampling* `1H` |

### 3.2 Lingkungan Komputasi dan Prapemrosesan
* **Perangkat Keras:** Intel Core i5-14400, RAM 32 GB, SSD.
* **Perangkat Lunak:** Windows 11, Python 3.12.7, `backtesting` v0.6.6 (`FractionalBacktest`, `fractional_unit=1e-4`), `pandas` v3.0.5 (dengan penyesuaian `pd.DataFrame.iteritems = pd.DataFrame.items`), `numpy` v2.2.6, `yfinance` v1.8.0, `pandas_ta` v0.4.71b0, `openpyxl` v3.1.5, dan `matplotlib` v3.11.1.
* **Tahapan Prapemrosesan (`load_clean_data`, `preprocess_asset_data`, dan `resample_aapl.py`):**
  1. Normalisasi nama kolom menjadi huruf kecil, lalu dikembalikan ke huruf kapital (`Open`, `High`, `Low`, `Close`, `Volume`) sesuai spesifikasi `Backtesting.py`.
  2. Eliminasi akhir pekan (`dayofweek < 5`) dan penyaringan jam bursa reguler (`09:00` hingga `16:00` EST pada `1H`).
  3. **Penghindaran *Lookahead Bias*:** Perhitungan $\text{EMA}_{12}$ dan $\text{EMA}_{26}$ pada `1D` penuh digeser mundur satu periode (`.shift(1)`) sebelum digabungkan (*left join* + *forward-fill*) ke data `1H`.
  4. Perhitungan `EMA_micro` dan `ATR` pada `1H` menggunakan `ewm(span=..., adjust=False).mean()`, dilanjutkan penghapusan baris `NaN`.

### 3.3 Arsitektur Strategi Simetris (`SymmetricMTFStrategy`)
* **Konfigurasi Simulasi:** Modal awal $1.000$ USD, alokasi $99{,}99\%$ (`size=0.9999`), komisi $0{,}03\%$ (`fee=0.0003`), eksekusi pada penutupan bar (`trade_on_close=True`), penutupan akhir otomatis (`finalize_trades=True`).
* **Prasyarat *Entry*:** Kecukupan *warm-up period* ($\text{len}(\text{data}) \ge N_{\text{EMA}}$), portofolio kosong (tanpa *pyramiding*, *averaging-down*, maupun *hedging*), pemenuhan *cooldown* ($\text{bars\_since\_exit} \ge C$), dan kesesuaian mode (`long_only`, `short_only`, `combined`).
* **Aturan Masuk (*Entry Rules*):**
  * **Posisi Beli (*Long*):** $\text{EMA}_{12}(1\text{D}) > \text{EMA}_{26}(1\text{D}) \times (1 + \delta)$, $L_{t-1} \le \text{EMA}_{\text{mikro},t-1}$, $C_t > \text{EMA}_{\text{mikro},t}$, dan $\text{EMA}_{\text{mikro},t} \ge \text{EMA}_{\text{mikro},t-1}$. Batas awal: $\text{TS}_{\text{awal}} = P_{\text{masuk}} - (k \times \text{ATR}_t)$.
  * **Posisi Jual (*Short*):** Simetris, yakni $\text{EMA}_{12}(1\text{D}) < \text{EMA}_{26}(1\text{D}) \times (1 - \delta)$, $H_{t-1} \ge \text{EMA}_{\text{mikro},t-1}$, $C_t < \text{EMA}_{\text{mikro},t}$, dan $\text{EMA}_{\text{mikro},t} \le \text{EMA}_{\text{mikro},t-1}$. Batas awal: $\text{TS}_{\text{awal}} = P_{\text{masuk}} + (k \times \text{ATR}_t)$.
* **Mekanisme *Ratchet Trailing Stop* & Penutupan Posisi (*Exit Rules*):**
  * Pergeseran searah (*ratchet*) baru aktif setelah keuntungan berjalan mencapai ambang $p_{\min}$: $\text{TS}_{\text{final}} = \max(\text{TS}_{\text{lama}}, C_t - k \times \text{ATR}_t)$ untuk *long*, dan $\text{TS}_{\text{final}} = \min(\text{TS}_{\text{lama}}, C_t + k \times \text{ATR}_t)$ untuk *short*.
  * Posisi ditutup jika terjadi **Trailing Stop Hit** ($C_t \le \text{TS}_{\text{final}}$ untuk *long*; $C_t \ge \text{TS}_{\text{final}}$ untuk *short*), **Macro Trend Reversal** ($\text{EMA}_{12}(1\text{D}) < \text{EMA}_{26}(1\text{D})$ untuk *long*; sebaliknya untuk *short*), atau **End of Data**. Setelah keluar, `bars_since_exit` direset ke $0$.

### 3.4 Optimasi *Full Grid Search* dan Metrik Evaluasi
* **Skrip Terpisah (`param_grid_search.py`):** Dieksekusi paralel menggunakan `ProcessPoolExecutor` pada ketiga indeks *in-sample* (`AAPL` tidak dilibatkan).
* **Ruang Pencarian ($5 \times 5 \times 5 \times 6 \times 5 \times 4 = 15.000$ kombinasi per mode):**
  * $\delta \in \{0{,}002;\; 0{,}007;\; 0{,}012;\; 0{,}017;\; 0{,}022\}$
  * $N_{\text{EMA}} \in \{14;\; 22;\; 30;\; 38;\; 46\}$
  * $N_{\text{ATR}} \in \{7;\; 11;\; 15;\; 19;\; 23\}$
  * $k \in \{4{,}0;\; 5{,}2;\; 6{,}4;\; 7{,}6;\; 8{,}8;\; 10{,}0\}$
  * $C \in \{3;\; 6;\; 9;\; 12;\; 15\}$
  * $p_{\min} \in \{0{,}005;\; 0{,}011;\; 0{,}017;\; 0{,}023\}$
* **Fungsi Objektif:** Pemeringkatan menurun berdasarkan rata-rata *Total Return* 3 indeks sebagai prioritas utama dan rata-rata *Maximum Drawdown* 3 indeks sebagai pemecah seri (*tie-breaker*).
* **Metrik Evaluasi:** 10 metrik portofolio (`Total Return`, `CAGR`, `Max Drawdown`, `Calmar Ratio`, `Sharpe Ratio`, `Sortino Ratio`, `Win Rate`, `Profit Factor`, `Total Trades`, `Exposure Time`) berbasis *daily resampling* dengan faktor $\sqrt{252}$ ($R_f = 0$, *target downside deviation* $= 0$), serta rekonsiliasi log transaksi 18 kolom bebas `NaN` (`reconcile_trades`) untuk durasi penahanan, *Payoff Ratio*, `MAE`, `MFE` (dihitung dari `entry_bar + 1` hingga `exit_bar` guna mencegah *look-behind bias*), dan distribusi alasan keluar.

---

## 4. Ringkasan Hasil Empiris Utama (Bab IV)

### 4.1 Tiga Konfigurasi Parameter Optimal Hasil *Grid Search*

| Parameter / Metrik Agregat 3 Indeks | `OPT_LONG_ONLY` (Utama) | `OPT_SHORT_ONLY` | `OPT_COMBINED` |
| :--- | :---: | :---: | :---: |
| $\delta$ / $N_{\text{EMA}}$ / $N_{\text{ATR}}$ / $k$ / $C$ / $p_{\min}$ | $0{,}002$ / $46$ / $23$ / $5{,}2$ / $6$ / $2{,}3\%$ | $0{,}007$ / $30$ / $7$ / $4{,}0$ / $15$ / $1{,}1\%$ | $0{,}002$ / $46$ / $23$ / $5{,}2$ / $3$ / $2{,}3\%$ |
| Rata-rata *Total Return* 3 Indeks (%) | $50{,}30$ | $2{,}04$ | $34{,}34$ |
| Rata-rata *Max Drawdown* 3 Indeks (%) | $-16{,}61$ | $-20{,}87$ | $-27{,}60$ |

### 4.2 Kinerja Konfigurasi Utama (`OPT_LONG_ONLY`) Mode *Long-Only* vs. *Buy & Hold*

| Instrumen | *Total Return* (%) (Strategi vs. B&H) | *Max Drawdown* (%) (Strategi vs. B&H) | Reduksi MDD Relatif | *Sharpe Ratio* (Strategi vs. B&H) | *Win Rate* / *Profit Factor* | *Exposure Time* (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SPY`** (*In-Sample*) | $42{,}44$ vs. $91{,}68$ | $-14{,}46$ vs. $-34{,}67$ | $58{,}29\%$ | $0{,}67$ vs. $0{,}66$ | $53{,}03\%$ / $1{,}68$ | $49{,}16$ |
| **`QQQ`** (*In-Sample*) | $90{,}78$ vs. $167{,}51$ | $-12{,}07$ vs. $-37{,}25$ | $67{,}60\%$ | $0{,}92$ vs. $0{,}80$ | $61{,}33\%$ / $2{,}04$ | $48{,}51$ |
| **`DJI`** (*In-Sample*) | $17{,}69$ vs. $56{,}42$ | $-23{,}31$ vs. $-37{,}63$ | $38{,}05\%$ | $0{,}34$ vs. $0{,}48$ | $49{,}15\%$ / $1{,}32$ | $46{,}39$ |
| **`AAPL`** (*Out-of-Sample*) | $3{,}41$ vs. $46{,}22$ | $-18{,}91$ vs. $-33{,}32$ | $43{,}25\%$ | $0{,}19$ vs. $0{,}80$ | $57{,}14\%$ / $1{,}20$ | $39{,}86$ |

### 4.3 Temuan Kunci Pembahasan
1. **Proteksi Modal Konsisten:** Mode *Long-Only* mereduksi *Maximum Drawdown* sebesar $38{,}05\%$ hingga $67{,}60\%$ di seluruh instrumen, serta melampaui efisiensi risiko *Buy and Hold* (*Sharpe*, *Sortino*, *Calmar*) pada `SPY` dan `QQQ`. *Total Return* absolut lebih rendah karena modal hanya terekspos sekitar $46\%$ hingga $49\%$ waktu pada indeks dan sifat *lagging* `EMA`.
2. **Asimetri Pasar pada Arsitektur Simetris:** Mode *Short-Only* pada `OPT_LONG_ONLY` merugi di seluruh instrumen ($-3{,}31\%$ hingga $-19{,}86\%$) akibat bias naik jangka panjang (*long-term upward drift*) pasar saham AS, durasi posisi *short* yang lebih pendek ($10{,}09$ hingga $11{,}21$ hari vs. $14{,}60$ hingga $20{,}26$ hari pada *long*), serta *tail risk* ekstrem (kerugian tunggal $-18{,}33\%$ dan `MAE` $-18{,}51\%$ pada `QQQ`). Nilai *Sharpe* dan *Sortino* sebesar $0{,}00$ pada `SPY` *Short-Only* adalah valid secara matematis (rata-rata *return* aritmetika $+0{,}0061\%$ dengan *Profit Factor* $1{,}00$, sementara *Total Return* majemuk $-3{,}31\%$ akibat *volatility drag*).
3. **Dominasi *ATR Trailing Stop*:** Dari $344$ total transaksi (`OPT_LONG_ONLY` *Combined*), $97{,}67\%$ ($336$) ditutup melalui *Trailing Stop Hit*, $2{,}03\%$ ($7$) melalui *Macro Trend Reversal*, dan $0{,}29\%$ ($1$) melalui *End of Data*.
4. **Generalisasi dan Keterbatasan pada `AAPL`:** Proteksi modal tetap bekerja di luar sampel, tetapi profitabilitas terdegradasi tajam (`CAGR` $1{,}71\%$ vs. $21{,}12\%$) karena *Payoff Ratio* turun ke $0{,}90$ (rata-rata untung $4{,}45\%$ lebih kecil daripada rata-rata rugi $-4{,}96\%$) dan rata-rata `MAE` melonjak ke $-3{,}37\%$ (terburuk $-7{,}86\%$) akibat risiko idiosinkratik dan *price gap* saham tunggal. Pada uji silang, setelan ketat `OPT_SHORT_ONLY` pada mode *Long-Only* `AAPL` justru mencatat hasil lebih baik (*Total Return* $6{,}42\%$, `MDD` $-14{,}47\%$, *Sharpe* $0{,}32$).

---

## 5. Alur Bab dan Status Penyelesaian Dokumen

| Bagian Dokumen | Isi / Cakupan Utama | Status di `Skripsi_71230994_7.docx` |
| :--- | :--- | :--- |
| **Halaman Depan & Kata Pengantar** | Cover, Pernyataan, Persetujuan, Pengesahan, Persembahan/Moto, Kata Pengantar | Belum final (masih ada teks instruksi *template*, placeholder, dan typo `pengembagan`) |
| **Daftar Isi, Tabel, Gambar** | Sinkronisasi judul bab, sub-bab, 16 tabel, dan 5 gambar | Sudah diperbarui dan sinkron penuh |
| **Intisari & *Abstract*** | Ringkasan 3 paragraf (maks. 300 kata) bahasa Indonesia & Inggris | Belum dikerjakan (masih *Lorem ipsum*) |
| **BAB I (Pendahuluan)** | 1.1 Latar Belakang (termasuk profil 4 instrumen), 1.2–1.7 | Selesai & konsisten penuh |
| **BAB II (Tinjauan Pustaka & Landasan Teori)** | 2.1 (5 pustaka + Tabel 2.1), 2.2 (OHLCV, MTF, EMA, ATR & Trailing Stop simetris, Rule-Based, Grid Search, Backtesting & metrik) | Selesai secara struktur (perlu cek 1 keterangan tanda MDD & validasi PDF sitasi) |
| **BAB III (Metodologi Penelitian)** | 3.1 Alur + Gambar 3.1, 3.2 Kebutuhan (Tabel 3.1–3.2), 3.3 Data + Tabel 3.3, 3.4 Aturan + Gambar 3.2, 3.5 Grid Search + Tabel 3.4, 3.6 Evaluasi + Tabel 3.5 | Selesai secara struktur (perlu cek simbol akar $\sqrt{252}$ di 3.6) |
| **BAB IV (Implementasi & Pembahasan)** | 4.1 Implementasi (Kode 4.1–4.2), 4.2 Grid Search (Kode 4.3, Tabel 4.1), 4.3 Pengujian (Tabel 4.2–4.9), 4.4 Pembahasan (4.4.1–4.4.5) | Selesai & angka 100% cocok dengan `ta_2.txt` (perlu cek simbol akar $\sqrt{252}$ di 4.1.3) |
| **BAB V (Kesimpulan & Saran)** | 5.1 Kesimpulan (menjawab 3 rumusan masalah), 5.2 Saran | Belum dikerjakan (ditunda hingga pasca-bimbingan Bab I–IV) |
| **Daftar Pustaka** | 17 referensi jurnal/prosiding (2020–2026) | Sinkron 100% dengan sitasi teks, tetapi wajib diverifikasi isi terhadap PDF asli |
| **Lampiran A–D** | A: Kode Program, B–C: Kartu Konsultasi, D: Tabel Uji Silang `OPT_SHORT_ONLY` & `OPT_COMBINED` | Belum diisi (Lampiran A masih berisi kode contoh `incmatrix`; Lampiran D masih kosong) |

---

## 6. Keputusan Revisi dan Gaya Penulisan yang Telah Disepakati

1. **Gaya Bahasa Akademik:** Menggunakan bahasa Indonesia baku, formal, ringkas, dan lugas sesuai standar bidang Informatika. Istilah algoritma, indikator, dan metrik bahasa Inggris dipertahankan dalam cetak miring (*italic*). Penggunaan *em-dash* berlebihan dan pola kalimat khas AI dihindari.
2. **Format Angka:** Menggunakan pemisah desimal koma dengan dua angka di belakang koma (termasuk `100,00` pada *Exposure Time*) dan pemisah ribuan titik.
3. **Pemecahan Tabel 4.2:** Tabel hasil pengujian *in-sample* dipecah menjadi tiga tabel terpisah: **Tabel 4.2 (`SPY`)**, **Tabel 4.3 (`QQQ`)**, dan **Tabel 4.4 (`DJI`)**, diikuti **Tabel 4.5 (Validasi *Out-of-Sample* Saham `AAPL`)** dan **Tabel 4.6 hingga Tabel 4.9** untuk karakteristik transaksi individual.
4. **Struktur Narasi Sub-bab 4.3.3:** Tidak menggunakan penomoran sub-poin (1, 2, 3, 4), melainkan dihubungkan menggunakan paragraf transisi yang mengalir antar-tabel (Tabel 4.6 hingga Tabel 4.9).
5. **Penanganan Gambar:**
   * **Gambar 2.2** tidak diganti, tetapi ditambahkan penjelasan pada narasi Sub-bab 2.2.2 bahwa garis merah *trailing stop* adalah ilustrasi jarak toleransi volatilitas sesaat sebelum aturan *ratchet* dan ambang keuntungan minimum diterapkan.
   * **Gambar 3.1** telah diperbarui mengikuti sumber Kaggle & `yfinance`, rentang waktu terpisah (`2018 s.d. 2024` dan `2024 s.d. 2026`), serta *Full Grid Search* $3 \times 15.000$ kombinasi.
   * **Gambar 3.2** telah diperbarui dengan penambahan percabangan `Akhir Data?` dan pemisahan jalur panah *loop* pada sisi kiri diagram.
6. **Penyeragaman Istilah:** Nama indeks diseragamkan menjadi `NASDAQ 100`, `S&P 500`, `DJIA`, dan saham `Apple (AAPL)`. Istilah validasi diseragamkan menjadi *out-of-sample* (tanpa kata *double* pada judul dan narasi Bab I–IV).

---

## 7. Catatan Penting dan Daftar Tindak Lanjut

### A. Perbaikan Teknis Cepat (Sebelum Konsultasi Online)
1. **Simbol Akar Faktor Penyetahunan (Sub-bab 3.6 dan 4.1.3):** Ubah teks `faktor penyetahunan 252` menjadi `faktor penyetahunan` $\sqrt{252}$ agar sesuai dengan implementasi `np.sqrt(252)` pada `extract_metrics`.
2. **Konvensi Tanda Negatif *Maximum Drawdown* (Sub-bab 2.2.7):** Tambahkan keterangan bahwa meskipun rumus literatur ditulis bernilai positif, pada pelaporan sistem dan `Backtesting.py`, nilai MDD ditampilkan bertanda negatif (selaras dengan Sub-bab 3.5 dan Tabel Bab IV).
3. **Bug Komentar Demo Program (`ta.ipynb` Cell 2):** Hapus tanda `#` pada baris `# ACTIVE_PARAM_SET = "OPT_LONG_ONLY"` agar notebook tidak memunculkan galat `NameError` saat dijalankan ulang (*Run All*) ketika demo konsultasi.
4. **Dokumentasi Tambahan Opsional (Sub-bab 4.1.1):** Sebutkan nama skrip utilitas `resample_aapl.py` (beserta aturan agregasi `OHLCV`) serta tambahkan komentar normalisasi huruf kapital pada `Kode 4.1`.

### B. Audit Sitasi Terhadap PDF Jurnal Asli (Prioritas Tinggi)
Karena berkas PDF jurnal tidak tersimpan dalam sesi ini, verifikasi silang terhadap PDF asli perlu segera dilakukan terutama pada empat referensi paling rawan berikut:
* **`Palazzi (2025)`:** Jurnal membahas pasar kripto (*Bullish Crypto Market*), namun disitasi di Sub-bab 2.2.1 untuk perbandingan indeks saham vs. *price gap* saham tunggal korporasi (juga disitasi pada 2.2.5 dan 2.2.6).
* **`Lyukevich et al. (2020)`:** Judul di Sub-bab 2.1.3 memotong frasa *and a Stochastic Oscillator*, serta penulisan nama di Daftar Pustaka (`Igorevna, G. I., & Grigorievich, R. D.`) memakai patronimik Rusia sebagai nama belakang.
* **`Kabbani & Duman (2022)`:** Jurnal berbasis *Deep Reinforcement Learning*, namun disitasi pada Bab I untuk aturan matematis pasti dan Tabel 2.1 untuk perbandingan eksekusi manual dengan metrik *win rate*.
* **`Fonseca (2026)`:** Menopang 4 klaim inti sekaligus (ATR Trailing Stop, *shift* 1 bar, dan *parameter plateau*); pastikan PDF asli dan tautan DOI (`10.3390/math14122182`) valid dan relevan.
* **Cek Sekunder:** Verifikasi kecocokan klaim spesifik pada `Saravanan & Devi (2025)` (penggunaan `AAPL`, SMA vs. EMA), `Sukma & Namahoot (2025)` (fungsi *pullback* MTF di 2.2.3), `Lee et al. (2022)` (filter jam *intraday*), `Fu et al. (2023)` (*Grid Search*), dan `Chanda et al. (2024)` (guncangan ekonomi global).

### C. Antisipasi Pertanyaan Dosen Pembimbing / Penguji Sidang
1. **Mengapa fungsi objektif *Grid Search* memprioritaskan *Total Return* daripada *Max Drawdown*?** Menjadikan `MDD` sebagai prioritas pertama berisiko memilih kombinasi ekstrem yang menghasilkan $0$ atau sangat sedikit transaksi sehingga *drawdown* nyaris $0\%$ tanpa imbal hasil. Memaksimalkan *return* di dalam sistem yang dipagari *ATR Trailing Stop* menjaga strategi tetap aktif dan menguntungkan sekaligus terkendali risikonya.
2. **Mengapa tidak ada pemisahan *train-test* waktu pada 3 indeks?** Risiko *overfitting* ditekan dengan memaksa satu set parameter bekerja lintas tiga indeks berkarakteristik berbeda, lalu ketahanannya diuji pada instrumen dan periode baru (`AAPL` 2024–2026) tanpa optimasi ulang. Keterbatasan parameter statis telah diakui di Sub-bab 4.4.5.
3. **Mengapa ukuran sampel `AAPL` hanya 14 transaksi (*Long-Only*) / 724 hari?** Dibatasi oleh kebijakan jendela historis data *intraday* `1H` dari `yfinance` (~2 tahun terakhir), sehingga evaluasi difokuskan pada metrik ternormalisasi waktu (`CAGR`, *Sharpe*, *Sortino*, *Calmar*) melawan *Buy and Hold* `AAPL` pada periode yang sama.
4. **Mengapa nilai `CAGR` strategi aktif sedikit berbeda dari perhitungan manual berbasis 365,25 hari kalender?** Di `extract_metrics`, `Buy & Hold` menggunakan pembagi $365{,}25$ hari kalender, sedangkan strategi aktif mengambil `Return (Ann.) [%]` milik `Backtesting.py` berbasis $252$ hari bursa (selisih minor, misalnya `SPY` $5{,}70\%$ vs. $5{,}85\%$).
5. **Mengapa `pandas_ta` tercantum di Tabel 3.2 padahal `EMA` dan `ATR` dihitung dengan `ewm()`?** Implementasi manual berbasis `ewm()` dipilih agar rumus perataan dan pergeseran `.shift(1)` terkontrol dan transparan untuk diaudit.
6. **Bagaimana inisialisasi `EMA 26` harian pada `AAPL` tanpa riwayat pra-November 2024?** `AAPL` tidak memiliki data pra-2024 di berkas `yfinance`, sehingga *warm-up period* $46$ bar `1H` menahan pembukaan transaksi selama sekitar 6 hingga 7 hari bursa pertama.

### D. Rencana Kerja Setelah Bimbingan Online
1. Menerapkan masukan dari dosen pembimbing untuk Bab I–IV (serta hasil pengecekan PDF jurnal).
2. Menyusun **Bab V (Kesimpulan dan Saran)** yang menjawab langsung ketiga rumusan masalah.
3. Menyusun **Intisari** (bahasa Indonesia) dan ***Abstract*** (bahasa Inggris) maksimal 300 kata.
4. Mengisi **Lampiran A** (kode aktual `ta.ipynb`, `param_grid_search.py`, `resample_aapl.py`) dan **Lampiran D** (tabel lengkap uji silang `OPT_SHORT_ONLY` dan `OPT_COMBINED`).
5. Merapikan halaman depan, Kata Pengantar, Lampiran B–C, dan menjalankan *Update Field* terakhir pada Daftar Isi, Daftar Tabel, dan Daftar Gambar.