import os
import pandas as pd

def sanitize_aapl_dataset():
    # Menentukan direktori dasar dan path file
    base_dir = os.path.abspath(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "data_index", "validasi-aapl")
    path_1h = os.path.join(data_dir, "aapl_1h.csv")
    path_1d = os.path.join(data_dir, "aapl_1d.csv")

    if not os.path.exists(path_1h):
        raise FileNotFoundError(f"File data 1H tidak ditemukan di: {path_1h}")

    print("=" * 80)
    print("PROSES SANITASI DAN STANDARISASI DATASET AAPL (1H & 1D)")
    print("=" * 80)

    # 1. Pemuatan Data Mentah
    print(f"Membaca file input 1H: {path_1h}")
    df_raw_1h = pd.read_csv(path_1h)
    
    # Deteksi dan standarisasi nama kolom waktu
    time_col = None
    for col in df_raw_1h.columns:
        if col.lower() in ['date', 'datetime', 'time', 'timestamp']:
            time_col = col
            break
    if time_col is None:
        raise ValueError(f"Kolom waktu tidak ditemukan pada file: {path_1h}")

    # Standardisasi nama kolom OHLCV
    col_map = {}
    for col in df_raw_1h.columns:
        if col.lower() in ['open', 'high', 'low', 'close', 'volume']:
            col_map[col] = col.capitalize()
    
    df_1h = df_raw_1h[[time_col] + list(col_map.keys())].copy()
    df_1h.rename(columns=col_map, inplace=True)
    df_1h['Date'] = pd.to_datetime(df_1h[time_col])
    df_1h.set_index('Date', inplace=True)
    df_1h.sort_index(inplace=True)

    rows_1h_awal = len(df_1h)
    rows_1d_awal = len(pd.read_csv(path_1d)) if os.path.exists(path_1d) else 0

    print(f"- Jumlah baris 1H sebelum sanitasi : {rows_1h_awal:,}")
    if rows_1d_awal > 0:
        print(f"- Jumlah baris 1D sebelum sanitasi : {rows_1d_awal:,}")

    # 2. Pembersihan Akhir Pekan (Weekend Elimination)
    df_1h_nowk = df_1h[df_1h.index.dayofweek < 5].copy()
    rows_weekend_removed = rows_1h_awal - len(df_1h_nowk)
    print(f"- Baris akhir pekan (Sabtu/Minggu) dibuang : {rows_weekend_removed:,}")

    # 3. Filter Jam Bursa Reguler (RTH Extraction 09:00 - 16:00)
    df_1h_rth = df_1h_nowk[(df_1h_nowk.index.hour >= 9) & (df_1h_nowk.index.hour <= 16)].copy()
    rows_non_rth_removed = len(df_1h_nowk) - len(df_1h_rth)
    print(f"- Baris jam non-reguler (Non-RTH) dibuang  : {rows_non_rth_removed:,}")

    # 4. Rekalkulasi Data Harian (1D RTH Aggregation)
    print("Merekalkulasi data harian (1D) dari bar 1H RTH...")
    agg_rules = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    df_1d_rth = df_1h_rth.resample('D').agg(agg_rules).dropna()
    # Format index harian menjadi YYYY-MM-DD
    df_1d_rth.index = df_1d_rth.index.strftime('%Y-%m-%d')
    df_1d_rth.index.name = 'Date'

    # Format index 1H
    df_1h_rth.index.name = 'Date'

    rows_1h_akhir = len(df_1h_rth)
    rows_1d_akhir = len(df_1d_rth)

    # 5. Penimpaan File (Overwrite In-Place)
    print("Menyimpan hasil sanitasi secara in-place...")
    df_1h_rth.to_csv(path_1h)
    print(f"- Berhasil menimpa: {path_1h} ({rows_1h_akhir:,} baris)")
    df_1d_rth.to_csv(path_1d)
    print(f"- Berhasil menimpa: {path_1d} ({rows_1d_akhir:,} baris)")

    # 6. Verifikasi dan Pelaporan
    check_weekend = (df_1h_rth.index.dayofweek >= 5).sum()
    check_hours = ((df_1h_rth.index.hour < 9) | (df_1h_rth.index.hour > 16)).sum()

    print("\n" + "=" * 80)
    print("VERIFIKASI HASIL SANITASI AAPL")
    print("=" * 80)
    print(f"File 1H : {path_1h}")
    print(f"- Rentang Waktu        : {df_1h_rth.index.min()} s.d. {df_1h_rth.index.max()}")
    print(f"- Baris Awal vs Akhir  : {rows_1h_awal:,} -> {rows_1h_akhir:,} (Reduksi: {(rows_1h_awal - rows_1h_akhir):,})")
    print(f"- Sisa Data Weekend    : {check_weekend} bar (Wajib 0)")
    print(f"- Sisa Data Non-RTH    : {check_hours} bar (Wajib 0)")
    print(f"- Jam Perdagangan Aktif: {sorted(df_1h_rth.index.hour.unique().tolist())}")

    print(f"\nFile 1D : {path_1d}")
    print(f"- Rentang Waktu        : {df_1d_rth.index.min()} s.d. {df_1d_rth.index.max()}")
    print(f"- Baris Awal vs Akhir  : {rows_1d_awal:,} -> {rows_1d_akhir:,}")

    if check_weekend == 0 and check_hours == 0:
        print("\nSTATUS: SANITASI BERHASIL SEMPURNA (100% RTH & BEBAS ARTEFAK AKHIR PEKAN).")
    else:
        print("\nSTATUS: PERINGATAN - MASIH TERDAPAT ARTEFAK TIDAK SESUAI.")
    print("=" * 80)

if __name__ == "__main__":
    sanitize_aapl_dataset()
