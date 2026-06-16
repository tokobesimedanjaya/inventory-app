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
def buat_pdf_bytes(no_invoice, nama_pelanggan, item_nama, item_ukuran, qty, harga, jenis_transaksi, gudang_nama):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, spaceAfter=4)
    sub_style = ParagraphStyle('Sub', alignment=1, spaceAfter=2, fontSize=9, leading=12)
    note_style = ParagraphStyle('Note', alignment=1, spaceAfter=15, fontSize=8, textColor=colors.gray)
    
    story.append(Paragraph("<b>TOKO BESI MEDAN JAYA</b>", title_style))
    story.append(Paragraph("Menyediakan Besi Holo, Beton, Siku, H-Beam, WF, IWF, dan lain-lain", sub_style))
    story.append(Paragraph("Untuk info lebih lanjut hubungi Whatsapp: 081361231558 | Hari minggu dan hari libur nasional tutup", note_style))
    story.append(Spacer(1, 5))
    
    story.append(Paragraph(f"<b>Jenis Transaksi:</b> Barang {jenis_transaksi}", styles['Normal']))
    story.append(Paragraph(f"<b>No Nota:</b> {no_invoice}", styles['Normal']))
    story.append(Paragraph(f"<b>Pelanggan / Sales Lapangan:</b> {nama_pelanggan}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    total = qty * harga
    
    data = [
        ["Nama Barang", "Ukuran", "Lokasi", "Qty", "Satuan", "Harga", "Subtotal"],
        [item_nama, item_ukuran, gudang_nama, str(qty), "Batang", f"Rp {harga:,}", f"Rp {total:,}"],
        ["", "", "", "", "", "TOTAL:", f"RP {total:,}"]
    ]
    
    table = Table(data, colWidths=[140, 80, 60, 40, 50, 70, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('LINEABOVE', (5,-1), (6,-1), 1, colors.black),
        ('FONTNAME', (5,-1), (6,-1), 'Helvetica-Bold'),
    ]))
    
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

col1, col2 = st.columns([1.0, 1.0])

with col2:
    st.header("📦 Sisa Stok Gudang Real-Time")
    cari_produk = st.text_input("🔍 Cari Nama Besi / Ukuran / Supplier:", "", placeholder="Ketik besi, ukuran, gudang, atau nama sales...")
    
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
        st.info("👇 Silakan gulir ke bagian paling bawah halaman pada bagian **'Tambah Varian Barang Baru'** untuk mendaftarkan nama dan ukuran besi terlebih dahulu sebelum melakukan transaksi.")
    else:
        jenis_transaksi = st.radio("Aktivitas Barang", ["Keluar (Penjualan/Sales)", "Masuk (Restock/Supplier)"])
        jenis_db = "Keluar" if "Keluar" in jenis_transaksi else "Masuk"
        
        if jenis_db == "Keluar":
            no_inv = st.text_input("Nomor Nota / Invoice", "INV-MJ-001")
            pelanggan = st.text_input("Nama Pelanggan / Sales Lapangan", "Toko Bangunan Sumber Rezeki")
            
            barang_pilihan = st.selectbox("Pilih Barang", barang_list, format_func=lambda x: f"{x[1]} ({x[2]})")
            gudang_pilihan = st.selectbox("Ambil dari Gudang Berapa", gudang_list, format_func=lambda x: x[1])
            
            qty = st.number_input("Banyaknya Barang (Batang)", min_value=1, value=5, step=1)
            harga = st.number_input("Harga Jual per Batang (Rp)", min_value=0, value=65000, step=500)
            
            proses_tombol = st.button("Proses Pengeluaran Barang & Cetak Nota")
            
            if proses_tombol:
                sukses, info = update_stok_db(barang_pilihan[0], gudang_pilihan[0], qty, jenis_db)
                if sukses:
                    st.success(f"✅ Stok {barang_pilihan[1]} di {gudang_pilihan[1]} berhasil dikurangi!")
                    pdf_data = buat_pdf_bytes(no_inv, pelanggan, barang_pilihan[1], barang_pilihan[2], qty, harga, jenis_db, gudang_pilihan[1])
                    st.download_button(label="📥 Unduh PDF Invoice Nota", data=pdf_data, file_name=f"Invoice_{no_inv}.pdf", mime="application/pdf")
                else:
                    st.error(f"❌ Stok tidak cukup! Sisa di {gudang_pilihan[1]} hanya {info} batang.")
                    
        else:
            nama_sales_masuk = st.text_input("Nama Penyuplai / Sales Supplier", placeholder="Masukkan nama sales atau nama pabrik...")
            
            barang_pilihan = st.selectbox("Pilih Barang yang Masuk", barang_list, format_func=lambda x: f"{x[1]} ({x[2]})")
            gudang_pilihan = st.selectbox("Simpan di Gudang Berapa", gudang_list, format_func=lambda x: x[1])
            
            qty = st.number_input("Banyaknya Barang (Batang)", min_value=1, value=50, step=1)
            
            proses_tombol = st.button("Simpan Stok Masuk")
            
            if proses_tombol:
                if not nama_sales_masuk.strip():
                    st.warning("⚠️ Mohon isi Nama Penyuplai terlebih dahulu agar riwayat pencatatan tersimpan!")
                else:
                    sukses, info = update_stok_db(barang_pilihan[0], gudang_pilihan[0], qty, jenis_db, nama_sales=nama_sales_masuk)
                    if sukses:
                        st.success(f"✅ Berhasil! Stok {barang_pilihan[1]} di {gudang_pilihan[1]} bertambah menjadi {info} Batang. Tercatat Penyuplai: {nama_sales_masuk}")
                        st.rerun()

# ==========================================
# 4. FITUR TAMBAH BARANG & GUDANG BARU
# ==========================================
st.markdown("---")
st.subheader("⚙️ Pengaturan & Ekspansi Data Toko")
expand_barang, expand_gudang = st.columns(2)

with expand_barang:
    st.write("**➕ Tambah Varian Barang Baru**")
    if not gudang_list:
        st.error("Gudang tidak terdeteksi")
    else:
        with st.form("form_barang", clear_on_submit=True):
            nama_baru = st.text_input("Nama Barang Baru", placeholder="Misal: Besi Beton Polos 10mm")
            ukuran_baru = st.text_input("Ukuran / Spesifikasi Panjang", placeholder="Misal: 10mm x 12m")
            gudang_pilihan_baru = st.selectbox("Lokasi Gudang Awal", gudang_list, format_func=lambda x: x[1])
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
                st.success(f"🎉 Produk '{nama_baru}' ({ukuran_baru}) berhasil didaftarkan di sistem!")
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
# 5. BERKAS UTILITY BACKUP DATABASE (BARU)
# ==========================================
st.markdown("---")
st.subheader("💾 Sistem Keselamatan Data (Backup)")
col_back1, col_back2 = st.columns([1.5, 1.0])

with col_back1:
    st.info("💡 **Tips Keamanan:** Lakukan backup database ini setiap sore hari setelah toko tutup. File hasil download ini bisa disimpan di laptop/HP Anda sebagai cadangan jika sewaktu-waktu server cloud mengalami penyegaran otomatis.")

with col_back2:
    if os.path.exists('inventory_medan_jaya.db'):
        with open('inventory_medan_jaya.db', 'rb') as f:
            db_bytes = f.read()
        
        st.download_button(
            label="📥 Download Database Backup (.db)",
            data=db_bytes,
            file_name="inventory_medan_jaya_backup.db",
            mime="application/octet-stream"
        )
    else:
        st.error("Berkas database belum terbentuk.")
