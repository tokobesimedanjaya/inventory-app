import streamlit as st
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
import os

# ==========================================
# 1. MANAGEMENT DATABASE (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('inventory_medan_jaya.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS barang (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        nama TEXT, 
                        ukuran TEXT, 
                        satuan TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS gudang (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        nama TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS stok (
                        id_barang INTEGER, 
                        id_gudang INTEGER, 
                        jumlah_batang INTEGER DEFAULT 0, 
                        sales_terakhir TEXT DEFAULT '-',
                        PRIMARY KEY(id_barang, id_gudang))''')
    
    try:
        cursor.execute("SELECT sales_terakhir FROM stok LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE stok ADD COLUMN sales_terakhir TEXT DEFAULT '-'")
        conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM gudang")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO gudang (id, nama) VALUES (?, ?)", 
                           [(1, 'Gudang 1'), 
                            (2, 'Gudang 2'), 
                            (3, 'Gudang 3')])
        
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect('inventory_medan_jaya.db')

def ambil_data_stok():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.id, b.nama, b.ukuran, g.id, g.nama, IFNULL(s.jumlah_batang, 0), IFNULL(s.sales_terakhir, '-')
        FROM barang b
        CROSS JOIN gudang g
        LEFT JOIN stok s ON b.id = s.id_barang AND g.id = s.id_gudang
        ORDER BY b.nama, g.nama
    ''')
    data = cursor.fetchall()
    conn.close()
    return data

def update_stok_db(id_barang, id_gudang, jumlah, jenis, nama_sales=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT jumlah_batang, sales_terakhir FROM stok WHERE id_barang = ? AND id_gudang = ?", (id_barang, id_gudang))
    row = cursor.fetchone()
    
    stok_sekarang = row[0] if row else 0
    sales_lama = row[1] if row else '-'
    
    if jenis == "Masuk":
        stok_baru = stok_sekarang + jumlah
        sales_baru = nama_sales if nama_sales else sales_lama
    else: 
        if stok_sekarang < jumlah:
            conn.close()
            return False, stok_sekarang
        stok_baru = stok_sekarang - jumlah
        sales_baru = sales_lama 
        
    cursor.execute("INSERT OR REPLACE INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir) VALUES (?, ?, ?, ?)", 
                   (id_barang, id_gudang, stok_baru, sales_baru))
    conn.commit()
    conn.close()
    return True, stok_baru

# ==========================================
# 2. GENERATOR INVOICE PDF 
# ==========================================
def buat_pdf_bytes(no_invoice, nama_pelanggan, item_nama, item_ukuran, qty, harga, jenis_transaksi, gudang_nama, subtotal, nominal_diskon, total_akhir, cash_input, kembalian):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, spaceAfter=4)
    sub_style = ParagraphStyle('Sub', alignment=1, spaceAfter=2, fontSize=9, leading=12)
    note_style = ParagraphStyle('Note', alignment=1, spaceAfter=15, fontSize=8, textColor=colors.gray)
    
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=9)
    cell_right = ParagraphStyle('CellRight', parent=styles['Normal'], fontSize=9, alignment=2)
    cell_bold_right = ParagraphStyle('CellBoldRight', parent=styles['Normal'], fontSize=9, alignment=2, fontName='Helvetica-Bold')
    
    story.append(Paragraph("<b>TOKO BESI MEDAN JAYA</b>", title_style))
    story.append(Paragraph("Menyediakan Besi Holo, Beton, Siku, H-Beam, WF, IWF, dan Alat Teknik", sub_style))
    story.append(Paragraph("Untuk info lebih lanjut hubungi Whatsapp: 081361231558 | Hari minggu dan hari libur nasional tutup", note_style))
    story.append(Spacer(1, 5))
    
    story.append(Paragraph(f"<b>Jenis Transaksi:</b> Barang {jenis_transaksi}", styles['Normal']))
    story.append(Paragraph(f"<b>No Nota:</b> {no_invoice}", styles['Normal']))
    story.append(Paragraph(f"<b>Pelanggan / Penerima:</b> {nama_pelanggan}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    data = [
        [Paragraph("<b>Nama Barang</b>", cell_style), Paragraph("<b>Ukuran</b>", cell_style), Paragraph("<b>Lokasi</b>", cell_style), Paragraph("<b>Qty</b>", cell_style), Paragraph("<b>Satuan</b>", cell_style), Paragraph("<b>Harga</b>", cell_right), Paragraph("<b>Subtotal</b>", cell_right)],
        [item_nama, item_ukuran, gudang_nama, str(qty), "Batang", f"Rp {harga:,}", f"Rp {subtotal:,}"],
        ["", "", "", "", "", Paragraph("<b>Subtotal:</b>", cell_bold_right), Paragraph(f"Rp {subtotal:,}", cell_right)],
        ["", "", "", "", "", Paragraph("<b>Diskon:</b>", cell_bold_right), Paragraph(f"- Rp {nominal_diskon:,}", cell_right)],
        ["", "", "", "", "", Paragraph("<b>TOTAL AKHIR:</b>", cell_bold_right), Paragraph(f"Rp {total_akhir:,}", cell_bold_right)]
    ]
    
    if cash_input > 0:
        data.append(["", "", "", "", "", Paragraph("<b>Tunai (Cash):</b>", cell_bold_right), Paragraph(f"Rp {cash_input:,}", cell_right)])
        data.append(["", "", "", "", "", Paragraph("<b>Kembalian:</b>", cell_bold_right), Paragraph(f"Rp {kembalian:,}", cell_bold_right)])
    
    table = Table(data, colWidths=[140, 80, 60, 40, 50, 95, 95])
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,1), 'LEFT'),
        ('ALIGN', (5,1), (6,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,1), 0.5, colors.grey),
        ('LINEABOVE', (5,2), (6,2), 1, colors.black),
    ]
    table.setStyle(TableStyle(t_style))
    
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 3. TAMPILAN INTERFACES WEB (Streamlit)
# ==========================================
init_db()

st.set_page_config(page_title="Inventory Toko Besi Medan Jaya", layout="wide")
st.title("🏗️ Sistem Inventory Toko Besi Medan Jaya")
st.caption("Aplikasi Manajemen Multi-Gudang & Pelacakan Supplier Bergaya Inflow")
st.markdown("---")

col1, col2 = st.columns([1.1, 0.9])

with col2:
    st.header("📦 Sisa Stok Gudang Real-Time")
    cari_produk = st.text_input("🔍 Cari Nama Besi / Ukuran / Supplier:", "", placeholder="Ketik besi, ukuran, gudang, atau nama sales...", key="input_cari_stok")
    
    data_stok = ambil_data_stok()
    tabel_tampil = []
    
    for d in data_stok:
        nama_barang = d[1]
        ukuran_barang = d[2]
        gudang_barang = d[4]
        jumlah_stok = f"{d[5]} Batang"
        sales_terakhir = d[6]
        
        if (cari_produk.lower() in nama_barang.lower() or 
            cari_produk.lower() in ukuran_barang.lower() or 
            cari_produk.lower() in gudang_barang.lower() or
            cari_produk.lower() in sales_terakhir.lower()):
            
            tabel_tampil.append({
                "Nama Barang": nama_barang,
                "Ukuran / Spek": ukuran_barang,
                "Lokasi Gudang": gudang_barang,
                "Jumlah Stok": jumlah_stok,
                "Penyuplai Terakhir": sales_terakhir
            })
            
    if tabel_tampil:
        st.table(tabel_tampil)
    else:
        st.info("💡 Belum ada data stok barang. Silakan daftarkan varian besi baru pada formulir Pengaturan di bawah terlebih dahulu.")

with col1:
    st.header("📝 Formulir Gerakan Barang")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    raw_barang = cursor.execute("SELECT id, nama, ukuran FROM barang").fetchall()
    gudang_list = cursor.execute("SELECT id, nama FROM gudang").fetchall()
    conn.close()
    
    barang_list = [(row[0], row[1], row[2]) for row in raw_barang]
    
    if not barang_list:
        st.warning("⚠️ Sistem mendeteksi data master barang Anda masih kosong bersih.")
    else:
        # Perbaikan Struktural: Menggunakan index langsung untuk memastikan kondisi terbaca sempurna
        opsi_aktivitas = ["Keluar (Penjualan/Sales)", "Masuk (Restock/Supplier)"]
        jenis_transaksi = st.radio("Aktivitas Barang", opsi_aktivitas, key="radio_jenis_transaksi")
        
        # Jauh lebih aman: Jika user memilih opsi pertama (index 0), otomatis masuk mode Keluar
        jika_barang_keluar = (jenis_transaksi == opsi_aktivitas[0])
        
        if jika_barang_keluar:
            no_inv = st.text_input("Nomor Nota / Invoice", "INV-MJ-001", key="input_no_invoice")
            pelanggan = st.text_input("Nama Pelanggan / Sales Lapangan", "Toko Bangunan Sumber Rezeki", key="input_nama_pelanggan")
            
            barang_pilihan = st.selectbox("Pilih Barang", barang_list, format_func=lambda x: f"{x[1]} ({x[2]})", key="select_barang_keluar")
            gudang_pilihan = st.selectbox("Ambil dari Gudang Berapa", gudang_list, format_func=lambda x: x[1], key="select_gudang_keluar")
            
            qty = st.number_input("Banyaknya Barang (Batang)", min_value=1, value=5, step=1, key="number_qty_keluar")
            harga = st.number_input("Harga Jual per Batang (Rp)", min_value=0, value=35000, step=500, key="number_harga_keluar")
            
            # BLOK KASIR & DISKON (Dipaksa keluar tanpa kompromi)
            st.markdown("---")
            st.markdown("##### 💰 Potongan Harga & Pembayaran (Kasir)")
            
            tipe_diskon = st.selectbox("Jenis Diskon", ["Tanpa Diskon", "Persentase (%)", "Nominal (Rupiah)"], key="select_tipe_diskon")
            
            nominal_diskon = 0
            subtotal_kalkulasi = qty * harga
            
            if tipe_diskon == "Persentase (%)":
                persen_diskon = st.number_input("Masukkan Persen (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="number_persen_diskon")
                nominal_diskon = int(subtotal_kalkulasi * (persen_diskon / 100))
            elif tipe_diskon == "Nominal (Rupiah)":
                nominal_diskon = st.number_input("Masukkan Potongan Rupiah (Rp)", min_value=0, max_value=subtotal_kalkulasi, value=0, step=1000, key="number_nominal_diskon")
                
            total_akhir = subtotal_kalkulasi - nominal_diskon
            
            st.markdown(f"**Subtotal:** Rp {subtotal_kalkulasi:,} | **Diskon:** Rp {nominal_diskon:,} | **Total Tagihan:** :green[**Rp {total_akhir:,}**]")
            
            cash_input = st.number_input("Uang Tunai / Cash dari Pembeli (Optional - Rp)", min_value=0, value=0, step=5000, key="number_cash_input")
            
            kembalian = 0
            if cash_input > 0:
                if cash_input < total_akhir:
                    st.warning(f"⚠️ Uang tunai kurang sebesar: Rp {total_akhir - cash_input:,}")
                else:
                    kembalian = cash_input - total_akhir
                    st.info(f"💵 **Uang Kembalian:** :blue[**Rp {kembalian:,}**]")
            
            st.markdown("---")
            proses_tombol = st.button("Proses Pengeluaran Barang & Cetak Nota", key="btn_proses_keluar")
            
            if proses_tombol:
                if cash_input > 0 and cash_input < total_akhir:
                    st.error("❌ Transaksi gagal! Jumlah uang cash kurang dari total tagihan.")
                else:
                    sukses, info = update_stok_db(barang_pilihan[0], gudang_pilihan[0], qty, "Keluar")
                    if sukses:
                        st.success(f"✅ Stok {barang_pilihan[1]} di {gudang_pilihan[1]} berhasil dikurangi!")
                        pdf_data = buat_pdf_bytes(
                            no_inv, pelanggan, barang_pilihan[1], barang_pilihan[2], qty, harga, "Keluar", gudang_pilihan[1],
                            subtotal_kalkulasi, nominal_diskon, total_akhir, cash_input, kembalian
                        )
                        st.download_button(label="📥 Unduh PDF Invoice Nota Terbaru", data=pdf_data, file_name=f"Invoice_{no_inv}.pdf", mime="application/pdf", key="btn_download_pdf")
                    else:
                        st.error(f"❌ Stok tidak cukup! Sisa di {gudang_pilihan[1]} hanya {info} batang.")
                    
        else:
            nama_sales_masuk = st.text_input("Nama Penyuplai / Sales Supplier", placeholder="Masukkan nama sales atau nama pabrik...", key="input_sales_masuk")
            
            barang_pilihan = st.selectbox("Pilih Barang yang Masuk", barang_list, format_func=lambda x: f"{x[1]} ({x[2]})", key="select_barang_masuk")
            gudang_pilihan = st.selectbox("Simpan di Gudang Berapa", gudang_list, format_func=lambda x: x[1], key="select_gudang_masuk")
            
            qty = st.number_input("Banyaknya Barang (Batang)", min_value=1, value=50, step=1, key="number_qty_masuk")
            
            proses_tombol = st.button("Simpan Stok Masuk", key="btn_simpan_masuk")
            
            if proses_tombol:
                if not nama_sales_masuk.strip():
                    st.warning("⚠️ Mohon isi Nama Penyuplai terlebih dahulu!")
                else:
                    sukses, info = update_stok_db(barang_pilihan[0], gudang_pilihan[0], qty, "Masuk", nama_sales=nama_sales_masuk)
                    if sukses:
                        st.success(f"✅ Berhasil! Stok {barang_pilihan[1]} di {gudang_pilihan[1]} bertambah menjadi {info} Batang.")
                        st.rerun()

# ==========================================
# 4. FITUR TAMBAH BARANG & GUDANG BARU
# ==========================================
st.markdown("---")
st.subheader("⚙️ Pengaturan & Ekspansi Data Toko")
expand_barang, expand_gudang = st.columns(2)

with expand_barang:
    st.write("**➕ Tambah Varian Barang Baru**")
    if gudang_list:
        with st.form("form_barang", clear_on_submit=True):
            nama_baru = st.text_input("Nama Barang Baru", placeholder="Misal: Besi Beton Polos 10mm")
            ukuran_baru = st.text_input("Ukuran / Spesifikasi Panjang", placeholder="Misal: 10mm x 12m")
            submit_b = st.form_submit_button("Daftarkan Barang Baru")
            
            if submit_b and nama_baru and ukuran_baru:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO barang (nama, ukuran, satuan) VALUES (?, ?, 'Batang')", (nama_baru, ukuran_baru))
                id_b = cursor.lastrowid
                all_gudang = cursor.execute("SELECT id FROM gudang").fetchall()
                for g in all_gudang:
                    cursor.execute("INSERT INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir) VALUES (?, ?, 0, '-')", (id_b, g[0]))
                conn.commit()
                conn.close()
                st.success(f"🎉 Produk '{nama_baru}' berhasil didaftarkan!")
                st.rerun()

with expand_gudang:
    st.write("**🏢 Tambah Lokasi Gudang Baru**")
    with st.form("form_gudang", clear_on_submit=True):
        nama_g_baru = st.text_input("Nama Gudang Baru", placeholder="Misal: Gudang 4")
        submit_g = st.form_submit_button("Daftarkan Gudang")
        
        if submit_g and nama_g_baru:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM gudang WHERE nama = ?", (nama_g_baru,))
            if cursor.fetchone():
                st.error("Nama gudang sudah ada!")
            else:
                cursor.execute("INSERT INTO gudang (nama) VALUES (?)", (nama_g_baru,))
                id_g = cursor.lastrowid
                all_b = cursor.execute("SELECT id FROM barang").fetchall()
                for b in all_b:
                    cursor.execute("INSERT INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir) VALUES (?, ?, 0, '-')", (b[0], id_g))
                conn.commit()
                st.success(f"🎉 {nama_g_baru} berhasil ditambahkan!")
                st.rerun()
            conn.close()

# ==========================================
# 5. BERKAS UTILITY BACKUP DATABASE
# ==========================================
st.markdown("---")
st.subheader("💾 Sistem Keselamatan Data (Backup)")
if os.path.exists('inventory_medan_jaya.db'):
    with open('inventory_medan_jaya.db', 'rb') as f:
        db_bytes = f.read()
    st.download_button(label="📥 Download Database Backup (.db)", data=db_bytes, file_name="inventory_medan_jaya_backup.db", mime="application/octet-stream", key="btn_backup_db")
