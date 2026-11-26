import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def muat_data_kinerja(filepath_excel):
    """
    Membaca data evaluasi kinerja dari berkas Excel secara dinamis.
    """
    if not os.path.exists(filepath_excel):
        alt_path = os.path.join("Trades_dan_Kinerja", "opt_combined", "Ringkasan_Kinerja_Semua_Instrumen_combined.xlsx")
        if os.path.exists(alt_path):
            filepath_excel = alt_path
        else:
            raise FileNotFoundError(f"Berkas data tidak ditemukan pada: {filepath_excel} maupun {alt_path}")

    print(f"Membaca data evaluasi dari berkas: {filepath_excel}")
    xl = pd.ExcelFile(filepath_excel)
    
    daftar_instrumen = ['SPY', 'QQQ', 'DJI', 'AAPL']
    data_mdd = {}
    data_return = {}
    mode_kolom = ['Buy & Hold', 'Long-Only', 'Short-Only', 'Combined']
    
    for inst in daftar_instrumen:
        df_sheet = xl.parse(inst, index_col=0)
        
        mdd_row = df_sheet.loc['Max Drawdown (%)', mode_kolom]
        ret_row = df_sheet.loc['Total Return (%)', mode_kolom]
        
        data_mdd[inst] = [float(mdd_row[m]) for m in mode_kolom]
        data_return[inst] = [float(ret_row[m]) for m in mode_kolom]
        
    return data_mdd, data_return, mode_kolom

def buat_grafik_grouped_bar(data_dict, mode_list, nama_metrik, judul_grafik, label_sumbu_y, output_filename, batas_y=None):
    """
    Menghasilkan grafik batang berkelompok standar publikasi 300 DPI.
    """
    instrumen_keys = ['SPY', 'QQQ', 'DJI', 'AAPL']
    label_sumbu_x = ['S&P 500\n(SPY)', 'NASDAQ 100\n(QQQ)', 'DJIA\n(DJI)', 'Apple (AAPL)\n[Out-of-Sample]']
    
    # Palet warna colorblind-safe baku (Wong Palette)
    palet_warna = {
        'Buy & Hold':  '#999999',  # Abu-abu
        'Long-Only':   '#009E73',  # Hijau
        'Short-Only':  '#D55E00',  # Oranye
        'Combined':    '#0072B2'   # Biru
    }
    
    n_instrumen = len(instrumen_keys)
    n_mode = len(mode_list)
    
    x = np.arange(n_instrumen)
    lebar_batang = 0.18
    
    fig, ax = plt.subplots(figsize=(10.5, 6), dpi=300)
    ax.set_axisbelow(True)
    
    # Grid latar belakang berupa garis putus-putus tipis pada sumbu nilai
    ax.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)
    
    # Garis ekuilibrium horizontal pada y=0
    ax.axhline(0, color='#cccccc', linewidth=1.0, zorder=1)
    
    for i, mode in enumerate(mode_list):
        nilai_per_mode = [data_dict[inst][i] for inst in instrumen_keys]
        posisi_x = x + (i - (n_mode - 1) / 2) * lebar_batang
        
        bars = ax.bar(
            posisi_x,
            nilai_per_mode,
            width=lebar_batang,
            label=mode,
            color=palet_warna[mode],
            edgecolor='none',
            zorder=3
        )
        
        # Anotasi angka persentase (1 desimal, format "X.X%")
        for bar in bars:
            val = bar.get_height()
            x_pos = bar.get_x() + bar.get_width() / 2.0
            
            if val < 0:
                ax.annotate(
                    f"{val:.1f}%",
                    xy=(x_pos, val),
                    xytext=(0, -12),
                    textcoords="offset points",
                    ha='center',
                    va='top',
                    fontsize=8,
                    fontweight='normal',
                    color='#222222'
                )
            else:
                ax.annotate(
                    f"{val:.1f}%",
                    xy=(x_pos, val),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    fontweight='normal',
                    color='#222222'
                )
                
    ax.set_title(judul_grafik, fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel("Instrumen Pengujian", fontsize=10, fontweight='bold', labelpad=10)
    ax.set_ylabel(label_sumbu_y, fontsize=10, fontweight='bold', labelpad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(label_sumbu_x, fontsize=10, fontweight='bold')
    
    if batas_y is not None:
        ax.set_ylim(batas_y)
    
    ax.legend(
        frameon=True,
        framealpha=0.9,
        edgecolor='#cccccc',
        fontsize=9,
        loc='upper right' if nama_metrik == 'Total Return (%)' else 'lower right'
    )
    
    plt.tight_layout()
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Grafik berhasil disimpan: {output_filename} (Resolusi: 300 DPI)")

def main():
    target_excel = "Ringkasan_Kinerja_Semua_Instrumen.xlsx"
    if len(sys.argv) > 1:
        target_excel = sys.argv[1]
        
    data_mdd, data_ret, mode_list = muat_data_kinerja(target_excel)
    
    # 1. Pembuatan Grafik Maximum Drawdown (MDD)
    buat_grafik_grouped_bar(
        data_dict=data_mdd,
        mode_list=mode_list,
        nama_metrik="Max Drawdown (%)",
        judul_grafik="Perbandingan Maximum Drawdown (MDD) Antarmode Pengujian dan Buy & Hold",
        label_sumbu_y="Maximum Drawdown (%)",
        output_filename="grafik_perbandingan_mdd.png",
        batas_y=(-48, 5)
    )
    
    # 2. Pembuatan Grafik Total Return (%)
    buat_grafik_grouped_bar(
        data_dict=data_ret,
        mode_list=mode_list,
        nama_metrik="Total Return (%)",
        judul_grafik="Perbandingan Total Return (%) Antarmode Pengujian dan Buy & Hold",
        label_sumbu_y="Total Return (%)",
        output_filename="grafik_perbandingan_total_return.png",
        batas_y=(-35, 195)
    )

if __name__ == '__main__':
    main()
