import os
import time
import warnings
import itertools
import concurrent.futures
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm.auto import tqdm
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Kompatibilitas Pandas 2.x/3.x dengan Backtesting.py
warnings.filterwarnings("ignore")
pd.DataFrame.iteritems = pd.DataFrame.items

from backtesting import Strategy
from backtesting.lib import FractionalBacktest


# =============================================================================
# 1. KONFIGURASI UTAMA & JALUR BERKAS
# =============================================================================
# Ubah nilai STRATEGY_MODE langsung di sini sebelum menjalankan skrip:
# Pilihan valid: "long_only", "short_only", atau "combined"
STRATEGY_MODE = "combined"
VALID_MODES = ("long_only", "short_only", "combined")
if STRATEGY_MODE not in VALID_MODES:
    raise ValueError(f"STRATEGY_MODE tidak valid: '{STRATEGY_MODE}'. Pilih salah satu: {VALID_MODES}")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_index"
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR.parent / "TugasAkhir" / "data_index"

OUTPUT_EXCEL = BASE_DIR / f"Grid_Search_Optimization_{STRATEGY_MODE}.xlsx"
TARGET_INSTRUMENTS = ["SPY", "QQQ", "DJI"]

INITIAL_CAPITAL = 1000.0
FEE = 0.0003
EMA_MACRO_FAST = 12   # Mengikuti GLOBAL_PARAMS pada ta.ipynb
EMA_MACRO_SLOW = 26   # Mengikuti GLOBAL_PARAMS pada ta.ipynb
START_DATE = "2018-02-19"
END_DATE = "2024-05-10 23:59:59"


# =============================================================================
# 2. FUNGSI INDIKATOR & PRA-PEMROSESAN DATA MTF
# =============================================================================
def calc_ema_series(series, span):
    """Menghitung Exponential Moving Average (EMA) berbasis span."""
    return pd.Series(series).ewm(span=span, adjust=False).mean().values


def calc_atr_series(high, low, close, period=14):
    """Menghitung Average True Range (ATR) berbasis True Range EMA."""
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)
    close_prev = close_s.shift(1)
    tr = pd.concat(
        [high_s - low_s, (high_s - close_prev).abs(), (low_s - close_prev).abs()],
        axis=1,
    ).max(axis=1)
    return pd.Series(tr).ewm(span=period, adjust=False).mean().values


def load_clean_data(file_path, is_1h=False):
    """Membaca data CSV/Parquet, filter akhir pekan, dan jam RTH 09:00-16:00 (1H)."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Berkas data tidak ditemukan: {p}")

    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        with open(p, "r", encoding="utf-8") as f:
            sep = "\t" if "\t" in f.readline() else ","
        df = pd.read_csv(p, sep=sep)

    df.columns = [c.lower() for c in df.columns]
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
    elif "date" in df.columns:
        df["datetime"] = pd.to_datetime(df["date"])
        df.drop(columns=["date"], inplace=True, errors="ignore")
    elif "time" in df.columns:
        df["datetime"] = pd.to_datetime(df["time"])

    df.sort_values("datetime", inplace=True)
    df.set_index("datetime", inplace=True)
    df = df[df.index.dayofweek < 5]

    if is_1h:
        df = df[(df.index.hour >= 9) & (df.index.hour <= 16)]

    df["date"] = df.index.date
    return df


def get_asset_file_paths(asset):
    """Pemetaan berkas data 1D dan 1H per instrumen."""
    mapping = {
        "SPY": {"1d": DATA_DIR / "spy_US500_D1.parquet", "1h": DATA_DIR / "spy_US500_H1.parquet"},
        "QQQ": {"1d": DATA_DIR / "Nasdaq100_1d_data.csv", "1h": DATA_DIR / "Nasdaq100_1h_data.csv"},
        "DJI": {"1d": DATA_DIR / "Dow_Jones_1d_data.csv", "1h": DATA_DIR / "Dow_Jones_1h_data.csv"},
    }
    paths = mapping[asset]
    if not (paths["1d"].exists() and paths["1h"].exists()):
        raise FileNotFoundError(f"Data 1D/1H tidak lengkap untuk instrumen: {asset}")
    return paths


def prepare_optimization_data(asset):
    """Menyiapkan dataset gabungan 1H + EMA Makro 1D (shift 1 bar) bebas lookahead bias."""
    paths = get_asset_file_paths(asset)
    d1 = load_clean_data(paths["1d"], is_1h=False)
    h1 = load_clean_data(paths["1h"], is_1h=True)

    d1["ema_fast"] = pd.Series(calc_ema_series(d1["close"], EMA_MACRO_FAST), index=d1.index).shift(1)
    d1["ema_slow"] = pd.Series(calc_ema_series(d1["close"], EMA_MACRO_SLOW), index=d1.index).shift(1)
    d1["macro_bull_alive"] = d1["ema_fast"] >= d1["ema_slow"]
    d1["macro_bear_alive"] = d1["ema_fast"] <= d1["ema_slow"]

    h1 = h1[(h1.index >= pd.to_datetime(START_DATE)) & (h1.index <= pd.to_datetime(END_DATE))]

    d1_sub = d1[["date", "ema_fast", "ema_slow", "macro_bull_alive", "macro_bear_alive"]]
    df = pd.merge(h1.reset_index(), d1_sub, on="date", how="left")
    df.ffill(inplace=True)
    df.set_index("datetime", inplace=True)

    df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"},
        inplace=True,
    )
    df.dropna(inplace=True)
    return df


# =============================================================================
# 3. STRATEGI SIMETRIS & WORKER MULTIPROCESSING (WINDOWS-SAFE)
# =============================================================================
class OptMTFStrategy(Strategy):
    """Kelas strategi simetris penuh (identik dengan SymmetricMTFStrategy di ta.ipynb)."""

    mode = STRATEGY_MODE
    atr_mult = 6.0
    cooldown_bars = 7
    min_profit_pct = 0.010
    ema_micro_span = 33
    atr_period_span = 14

    def init(self):
        self.ema_micro = self.I(calc_ema_series, self.data.Close, self.ema_micro_span, overlay=True)
        self.atr = self.I(
            calc_atr_series, self.data.High, self.data.Low, self.data.Close, self.atr_period_span, overlay=False
        )
        self.macro_bullish = self.I(lambda: self.data.df["macro_bullish"].values, overlay=False)
        self.macro_bearish = self.I(lambda: self.data.df["macro_bearish"].values, overlay=False)
        self.macro_bull_alive = self.I(lambda: self.data.df["macro_bull_alive"].values, overlay=False)
        self.macro_bear_alive = self.I(lambda: self.data.df["macro_bear_alive"].values, overlay=False)
        self.bars_since_exit = 999
        self.trailing_sl = 0.0
        self.entry_price = 0.0

    def next(self):
        if len(self.data) < self.ema_micro_span:
            return

        if not self.position:
            self.bars_since_exit += 1
            if self.bars_since_exit >= self.cooldown_bars:
                long_allowed = self.mode in ["long_only", "combined"]
                short_allowed = self.mode in ["short_only", "combined"]

                long_trigger = (
                    long_allowed
                    and self.macro_bullish[-1]
                    and (self.data.Low[-2] <= self.ema_micro[-2])
                    and (self.data.Close[-1] > self.ema_micro[-1])
                    and (self.ema_micro[-1] >= self.ema_micro[-2])
                )
                short_trigger = (
                    short_allowed
                    and self.macro_bearish[-1]
                    and (self.data.High[-2] >= self.ema_micro[-2])
                    and (self.data.Close[-1] < self.ema_micro[-1])
                    and (self.ema_micro[-1] <= self.ema_micro[-2])
                )

                if long_trigger:
                    self.buy(size=0.9999)
                    self.entry_price = self.data.Close[-1]
                    self.trailing_sl = self.entry_price - (self.atr_mult * self.atr[-1])
                    return

                elif short_trigger:
                    self.sell(size=0.9999)
                    self.entry_price = self.data.Close[-1]
                    self.trailing_sl = self.entry_price + (self.atr_mult * self.atr[-1])
                    return
        else:
            if self.position.is_long:
                if self.data.Close[-1] >= (self.entry_price * (1.0 + self.min_profit_pct)):
                    new_sl = self.data.Close[-1] - (self.atr_mult * self.atr[-1])
                    self.trailing_sl = max(self.trailing_sl, new_sl)

                if self.data.Close[-1] <= self.trailing_sl:
                    self.position.close()
                    self.bars_since_exit = 0
                    return

                if not self.macro_bull_alive[-1]:
                    self.position.close()
                    self.bars_since_exit = 0
                    return

            elif self.position.is_short:
                if self.data.Close[-1] <= (self.entry_price * (1.0 - self.min_profit_pct)):
                    new_sl = self.data.Close[-1] + (self.atr_mult * self.atr[-1])
                    self.trailing_sl = min(self.trailing_sl, new_sl)

                if self.data.Close[-1] >= self.trailing_sl:
                    self.position.close()
                    self.bars_since_exit = 0
                    return

                if not self.macro_bear_alive[-1]:
                    self.position.close()
                    self.bars_since_exit = 0
                    return


PRELOADED_DATA = {}


def _safe_float(val, default=0.0):
    """Konversi aman ke float untuk mencegah NaN/Inf saat kombinasi menghasilkan 0 transaksi."""
    if pd.isna(val):
        return default
    f_val = float(np.nan_to_num(float(val), nan=default, posinf=default, neginf=default))
    return 0.0 if f_val == 0.0 else f_val


def init_worker(preloaded_dict):
    """Inisialisasi dataset bersama pada masing-masing worker proses."""
    global PRELOADED_DATA
    PRELOADED_DATA = preloaded_dict


def evaluate_combination_task(combo_tuple):
    """Mengevaluasi satu kombinasi parameter secara agregat pada SPY, QQQ, dan DJI."""
    p_spread, p_ema_micro, p_atr_period, p_atr_mult, p_cooldown, p_min_profit = combo_tuple

    class TargetStrat(OptMTFStrategy):
        mode = STRATEGY_MODE
        atr_mult = p_atr_mult
        cooldown_bars = p_cooldown
        min_profit_pct = p_min_profit
        ema_micro_span = p_ema_micro
        atr_period_span = p_atr_period

    asset_returns, asset_mdds, asset_trades = {}, {}, {}

    for asset in TARGET_INSTRUMENTS:
        base_df = PRELOADED_DATA[asset].copy(deep=False)
        base_df["macro_bullish"] = base_df["ema_fast"] > (base_df["ema_slow"] * (1.0 + p_spread))
        base_df["macro_bearish"] = base_df["ema_fast"] < (base_df["ema_slow"] * (1.0 - p_spread))

        bt = FractionalBacktest(
            base_df,
            TargetStrat,
            cash=INITIAL_CAPITAL,
            commission=FEE,
            trade_on_close=True,
            finalize_trades=True,
            fractional_unit=1e-4,
        )
        stats = bt.run()

        asset_returns[asset] = _safe_float(stats["Return [%]"], 0.0)
        asset_mdds[asset] = _safe_float(stats["Max. Drawdown [%]"], 0.0)
        asset_trades[asset] = int(_safe_float(stats["# Trades"], 0.0))

    avg_return = sum(asset_returns.values()) / len(TARGET_INSTRUMENTS)
    avg_mdd = sum(asset_mdds.values()) / len(TARGET_INSTRUMENTS)

    return {
        "macro_spread_threshold": p_spread,
        "ema_micro": p_ema_micro,
        "atr_period": p_atr_period,
        "atr_mult": p_atr_mult,
        "cooldown_bars": p_cooldown,
        "min_profit_pct": p_min_profit,
        "Avg_Total_Return": round(avg_return, 2),
        "Avg_Max_Drawdown": round(avg_mdd, 2),
        "SPY_Return (%)": round(asset_returns["SPY"], 2),
        "QQQ_Return (%)": round(asset_returns["QQQ"], 2),
        "DJI_Return (%)": round(asset_returns["DJI"], 2),
        "SPY_MaxDD (%)": round(asset_mdds["SPY"], 2),
        "QQQ_MaxDD (%)": round(asset_mdds["QQQ"], 2),
        "DJI_MaxDD (%)": round(asset_mdds["DJI"], 2),
        "SPY_Trades": asset_trades["SPY"],
        "QQQ_Trades": asset_trades["QQQ"],
        "DJI_Trades": asset_trades["DJI"],
    }


# =============================================================================
# 4. EKSPOR EXCEL TERFORMAT
# =============================================================================
def export_to_excel(df_optim_final, output_path):
    """Menyimpan seluruh peringkat dan Top 100 parameter ke Excel dengan styling standar."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_optim_final.to_excel(writer, sheet_name="Ranked_Universal_Parameters", index=False)
        df_optim_final.head(100).to_excel(writer, sheet_name="Top_100_Universal", index=False)

    wb = openpyxl.load_workbook(output_path)
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    for ws in wb.worksheets:
        ws.views.sheetView[0].showGridLines = True
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 13)

    wb.save(output_path)


# =============================================================================
# 5. EKSEKUSI UTAMA FULL GRID SEARCH (15.000 KOMBINASI)
# =============================================================================
def main():
    # Ruang pencarian Coarse Grid (5 x 5 x 5 x 6 x 5 x 4 = 15.000 kombinasi)
    macro_spread_threshold_range = np.round(np.arange(0.002, 0.022 + 0.0005, 0.005), 3).tolist()
    ema_micro_range = list(range(14, 47, 8))
    atr_period_range = list(range(7, 24, 4))
    atr_mult_range = np.round(np.arange(4.0, 10.0 + 0.05, 1.2), 1).tolist()
    cooldown_bars_range = list(range(3, 16, 3))
    min_profit_pct_range = np.round(np.arange(0.005, 0.023 + 0.0005, 0.006), 3).tolist()

    active_combinations = list(
        itertools.product(
            macro_spread_threshold_range,
            ema_micro_range,
            atr_period_range,
            atr_mult_range,
            cooldown_bars_range,
            min_profit_pct_range,
        )
    )
    assert len(active_combinations) == 15000, f"Jumlah kombinasi harus 15.000, ditemukan: {len(active_combinations)}"

    cpu_cores = os.cpu_count() or 4
    print("=" * 85)
    print(f"FULL GRID SEARCH PARAMETER OPTIMIZATION [{STRATEGY_MODE.upper()}] (15.000 KOMBINASI)")
    print(f"Instrumen Target  : {TARGET_INSTRUMENTS} | Mode: {STRATEGY_MODE}")
    print(f"EMA Makro (1D)    : Fast={EMA_MACRO_FAST}, Slow={EMA_MACRO_SLOW}")
    print(f"Total Kombinasi   : {len(active_combinations):,} | CPU Workers: {cpu_cores} Cores")
    print(f"Berkas Output     : {OUTPUT_EXCEL}")
    print("=" * 85)

    # Pre-load data ke memori agar worker bebas disk I/O
    preloaded_data = {asset: prepare_optimization_data(asset) for asset in TARGET_INSTRUMENTS}
    for asset, df_a in preloaded_data.items():
        print(f"  * {asset}: {len(df_a):,} bar 1H siap dievaluasi")

    results_list = []
    start_time = time.time()

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=cpu_cores,
        initializer=init_worker,
        initargs=(preloaded_data,),
    ) as executor:
        futures = [executor.submit(evaluate_combination_task, combo) for combo in active_combinations]
        for fut in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc=f"Full Grid Search ({STRATEGY_MODE})",
            unit="combo",
        ):
            results_list.append(fut.result())

    elapsed_min = (time.time() - start_time) / 60.0
    print(f"\nOptimasi selesai dalam {elapsed_min:.2f} menit ({len(results_list):,} kombinasi).")

    df_optim = pd.DataFrame(results_list)
    df_optim.fillna(0.0, inplace=True)
    df_optim.sort_values(by=["Avg_Total_Return", "Avg_Max_Drawdown"], ascending=[False, False], inplace=True)
    df_optim.reset_index(drop=True, inplace=True)

    final_columns = [
        "Avg_Total_Return", "Avg_Max_Drawdown",
        "SPY_Return (%)", "QQQ_Return (%)", "DJI_Return (%)",
        "SPY_MaxDD (%)", "QQQ_MaxDD (%)", "DJI_MaxDD (%)",
        "macro_spread_threshold", "ema_micro", "atr_period", "atr_mult",
        "cooldown_bars", "min_profit_pct",
        "SPY_Trades", "QQQ_Trades", "DJI_Trades",
    ]
    df_optim_final = df_optim[final_columns]
    export_to_excel(df_optim_final, OUTPUT_EXCEL)

    print(f"\nHasil tersimpan: {OUTPUT_EXCEL}")
    print(f"\n>>> TOP 10 PARAMETER UNIVERSAL TERBAIK ({STRATEGY_MODE.upper()}):")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    print(df_optim_final.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
