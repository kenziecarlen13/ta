import os
import shutil
import re
import sys
import unicodedata

# Pastikan output console tidak gagal pada karakter unicode khusus
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Konfigurasi Path
SOURCE_DIR = r"E:\kultivasi_4_tahun\ta\Jurnal"
UTAMA_DIR = os.path.join(SOURCE_DIR, "Utama")
PENDUKUNG_DIR = os.path.join(SOURCE_DIR, "Pendukung")

# Daftar File Kategori Utama (11 file)
FILES_UTAMA = [
    "mathematics-14-02182-v3.pdf",
    "Application-of-machine-learning-in-algorithmic-investment-strategies-on-global-stock-markets.pdf",
    "Enhancing-Trading-Strategies-A-Multi-indicator-Analysis-for-Profitable-Algorithmic-Trading.pdf",
    "IARJSET.2025.12472.pdf",
    "dai2020.pdf",
    "10.3934_QFE.2024011.pdf",
    "Complexity - 2024 - Song - Improving the Machine Learning Stock Trading System  An N‐Period Volatility Labeling and.pdf",
    "3590837.3590875.pdf",
    "IJTech_EECE-4445_Generating-a-MultiTimeframe-Trading-Strategy-based.pdf",
    "s10462-025-11419-z.pdf",
    "Automated-Forex-Trading-Using-Exponential-Moving-Average-Method.pdf"
]

# Daftar File Kategori Pendukung (16 file)
FILES_PENDUKUNG = [
    "s44257-023-00007-6.pdf",
    "Downside-risk-reduction-using-regime-switching-signals-a-statistical-jump-model-approach.pdf",
    "dpab037.pdf",
    "lee2022.pdf",
    "Journal of Futures Markets - 2025 - Palazzi - Trading Games  Beating Passive Strategies in the Bullish Crypto Market.pdf",
    "Multi-Feature_Supervised_Reinforcement_Learning_for_Stock_Trading.pdf",
    "Pairs-Trading-Strategy-Optimization-Using-Proximal-Policy-Optimization-Algorithms.pdf",
    "A_Systematic_Survey_of_AI_Models_in_Financial_Market_Forecasting_for_Profitability_Analysis.pdf",
    "A_Mean-VaR_Based_Deep_Reinforcement_Learning_Framework_for_Practical_Algorithmic_Trading.pdf",
    "Deep_Reinforcement_Learning_Approach_for_Trading_Automation_in_the_Stock_Market.pdf",
    "Scientific Programming - 2022 - Li - Ensemble Investment Strategies Based on Reinforcement Learning.pdf",
    "Algorithmic-Trading-Financial-Markets-Using-Artificial-Intelligence.pdf",
    "A-study-on-signal-filtering-techniques-in-trend-following-strategies-with-LSTM-integration.pdf",
    "Applied Computational Intelligence and Soft Computing - 2026 - Kaur - A Hybrid Deep Reinforcement Learning Approach for.pdf",
    "Art._5_Issue_4_2024.pdf",
    "Optimizing-Algorithmic-Trading-by-Integrating-Sentiment-Analysis.pdf"
]

def normalize_text(text):
    """Normalisasi karakter unicode (seperti hyphen, dash, multiple spaces) untuk pencocokan toleran."""
    text = unicodedata.normalize('NFKD', text)
    # Ganti berbagai varian dash/hyphen unicode ke hyphen standar
    text = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', '-', text)
    # Rapatkan spasi berlebih
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()

def move_files(target_dir, file_list, category_name):
    print(f"\n=== Memproses Kategori: {category_name} ({len(file_list)} file) ===")
    os.makedirs(target_dir, exist_ok=True)
    
    # Ambil daftar file aktual di folder sumber dan target
    actual_files = [f for f in os.listdir(SOURCE_DIR) if os.path.isfile(os.path.join(SOURCE_DIR, f))]
    norm_actual_map = {normalize_text(f): f for f in actual_files}
    
    target_existing = [f for f in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, f))]
    norm_target_map = {normalize_text(f): f for f in target_existing}
    
    success_count = 0
    fail_count = 0
    
    for filename in file_list:
        try:
            norm_fn = normalize_text(filename)
            
            # Cek jika file sudah ada di target
            if norm_fn in norm_target_map or os.path.exists(os.path.join(target_dir, filename)):
                print(f"[SUDAH DI TARGET] File sudah berada di {category_name}: {filename}")
                success_count += 1
                continue
                
            actual_filename = None
            if os.path.exists(os.path.join(SOURCE_DIR, filename)):
                actual_filename = filename
            elif norm_fn in norm_actual_map:
                actual_filename = norm_actual_map[norm_fn]
                
            if actual_filename:
                src = os.path.join(SOURCE_DIR, actual_filename)
                dst = os.path.join(target_dir, actual_filename)
                shutil.move(src, dst)
                print(f"[BERHASIL] Dipindahkan: {actual_filename}")
                success_count += 1
                norm_actual_map.pop(normalize_text(actual_filename), None)
            else:
                print(f"[PERINGATAN] File tidak ditemukan di folder sumber: {filename}")
                fail_count += 1
        except Exception as e:
            print(f"[ERROR] Gagal memindahkan file '{filename}': {str(e)}")
            fail_count += 1
            
    print(f"Hasil {category_name}: {success_count} berhasil, {fail_count} gagal/dilewati.")

def main():
    print(f"Folder Sumber: {SOURCE_DIR}")
    print(f"Folder Utama: {UTAMA_DIR}")
    print(f"Folder Pendukung: {PENDUKUNG_DIR}")
    
    move_files(UTAMA_DIR, FILES_UTAMA, "Utama")
    move_files(PENDUKUNG_DIR, FILES_PENDUKUNG, "Pendukung")
    print("\nProses pengorganisasian file jurnal selesai.")

if __name__ == "__main__":
    main()
