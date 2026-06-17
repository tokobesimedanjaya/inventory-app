import streamlit as st
import sqlite3
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
from datetime import datetime

# ==========================================
# 0. KONFIGURASI HALAMAN & STATE INITIALIZATION
# ==========================================
st.set_page_config(page_title="Inventory Toko Besi Medan Jaya", layout="wide", page_icon="🏗️")

# Inisialisasi Database SQLite
def get_db_connection():
    conn = sqlite3.connect("inventory_medan_jaya.db")
    # row_factory tidak digunakan secara global agar mengembalikan tuple biasa yang aman untuk Streamlit
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Tabel Gudang
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gudang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL
        )
    """)
    # Tabel Barang
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            ukuran TEXT,
            satuan TEXT DEFAULT 'Batang'
        )
    """)
    # Tabel Stok Terpusat
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stok (
            id_barang INTEGER,
            id_gudang INTEGER,
            jumlah_batang REAL DEFAULT 0,
            sales_terakhir TEXT DEFAULT '-',
            PRIMARY KEY (id_barang, id_gudang),
            FOREIGN KEY (id_barang) REFERENCES barang(id),
            FOREIGN KEY (id_gudang) REFERENCES gudang(id)
        )
    """)
    
    # Isi data master gudang default jika masih kosong
    cursor.execute("SELECT COUNT(*) FROM gudang")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO gudang (nama) VALUES (?)", [("Toko",), ("Gudang 1",), ("Gudang 2",), ("Gudang 3",)])
    
    conn.commit()
    conn.close()

init_db()

# Mengamankan Session State agar tidak memicu AttributeError
if 'cart_keluar' not in st.session_state:
    st.session_state.cart_keluar = []
if 'cart_masuk' not in st.session_state:
    st.session_state.cart_masuk = []
if 'invoice_number' not in st.session_state:
    st.session_state.invoice_number = f"INV-MJ-{datetime.now().strftime('%d%m%Y-%H%M')}"

# Fungsi Mutasi Stok Terpusat
def update_stok_db(id_barang, id_gudang, qty, jenis_gerakan, nama_sales="-"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ambil stok saat ini
    cursor.execute("SELECT jumlah_batang FROM stok WHERE id_barang = ? AND id_gudang = ?", (id_barang, id_gudang))
    row = cursor.fetchone()
    stok_sekarang = row[0] if row else 0
    
    if jenis_gerakan == "Masuk":
        stok_baru = stok_sekarang + qty
        cursor.execute("""
            INSERT INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id_barang, id_gudang) DO UPDATE SET
            jumlah_batang = ?, sales_terakhir = ?
        """, (id_barang, id_gudang, stok_baru, nama_sales, stok_baru, nama_sales))
    elif jenis_gerakan == "Keluar":
        stok_baru = max(0, stok_sekarang - qty)
        cursor.execute("""
            UPDATE stok SET jumlah_batang = ? 
            WHERE id_barang = ? AND id_gudang = ?
        """, (stok_baru, id_barang, id_gudang))
        
    conn.commit()
    conn.close()

# Fungsi Generator Dokumen PDF Kuitansi
def buat_pdf_bytes(no_nota, nama_pelanggan, daftar_item):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=22, leading=26, alignment=1, textColor=colors.HexColor('#0F172A'))
    subtitle_style = ParagraphStyle('SubTitleStyle', fontName='Helvetica', fontSize=10, leading=14, alignment=1, textColor=colors.HexColor('#475569'))
    meta_label = ParagraphStyle('MetaLabel', fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.HexColor('#1E293B'))
    meta_val = ParagraphStyle('MetaVal', fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#334155'))
    
    cell_text = ParagraphStyle('CellText', fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#1E293B'))
    cell_header = ParagraphStyle('CellHeader', fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=1, textColor=colors.white)
    cell_right = ParagraphStyle('CellRight', fontName='Helvetica', fontSize=9, leading=12, alignment=2, textColor=colors.HexColor('#1E293B'))
    cell_center = ParagraphStyle('CellCenter', fontName='Helvetica', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#1E293B'))

    # Header Kuitansi Toko
    story.append(Paragraph("TOKO BESI MEDAN JAYA", title_style))
    story.append(Paragraph("Menyediakan Besi Holo, Beton, Siku, H-Beam, WF, IWF, dan Alat Teknik", subtitle_style))
    story.append(Paragraph("Untuk info lebih lanjut hubungi Whatsapp: 081361231558 | Hari minggu dan hari libur nasional tutup", subtitle_style))
    story.append(Spacer(1, 20))
    
    # Metadata Transaksi
    meta_data = [
        [Paragraph("Jenis Transaksi:", meta_label), Paragraph("Barang Keluar / Penjualan", meta_val)],
        [Paragraph("No Nota / Invoice:", meta_label), Paragraph(no_nota, meta_val)],
        [Paragraph("Pelanggan / Penerima:", meta_label), Paragraph(nama_pelanggan, meta_val)]
    ]
    meta_table = Table(meta_data, colWidths=[120, 420])
    meta_table.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 4), ('TOPPADDING', (0,0), (-1,-1), 4)]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # Data Tabel Item
    headers = [
        Paragraph("No", cell_header), Paragraph("Nama Barang", cell_header), Paragraph("Ukuran / Spek", cell_header),
        Paragraph("Lokasi", cell_header), Paragraph("Qty", cell_header), Paragraph("Satuan", cell_header),
        Paragraph("Harga", cell_header), Paragraph("Subtotal", cell_header)
    ]
    data = [headers]
    
    total_gross = 0
    for idx, item in enumerate(daftar_item, start=1):
        total_gross += item['item_subtotal']
        data.append([
            Paragraph(str(idx), cell_center),
            Paragraph(item['nama'], cell_text),
            Paragraph(item['ukuran'], cell_text),
            Paragraph(item['gudang_nama'], cell_center),
            Paragraph(str(item['qty']), cell_center),
            Paragraph(item['satuan'], cell_center),
            Paragraph(f"Rp {item['harga']:,}", cell_right),
            Paragraph(f"Rp {item['item_subtotal']:,}", cell_right)
        ])
        
    diskon = total_gross * 0.02
    total_akhir = total_gross - diskon
    tunai = (int(total_akhir // 10000) + 1) * 10000
    kembalian = tunai - total_akhir
    
    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ])
    
    # Kolom Lebar Tabel PDF
    col_widths = [25, 140, 95, 55, 30, 45, 75, 75]
    item_table = Table(data, colWidths=col_widths)
    item_table.setStyle(table_style)
    story.append(item_table)
    story.append(Spacer(1, 10))
    
    # Ringkasan Finansial Bawah
    fin_label = ParagraphStyle('FinLabel', fontName='Helvetica-Bold', fontSize=10, alignment=2, textColor=colors.HexColor('#1E293B'))
    fin_val = ParagraphStyle('FinVal', fontName='Helvetica', fontSize=10, alignment=2, textColor=colors.HexColor('#1E293B'))
    fin_val_bold = ParagraphStyle('FinValBold', fontName='Helvetica-Bold', fontSize=10, alignment=2, textColor=colors.HexColor('#B91C1C'))
    
    fin_data = [
        [Paragraph("", cell_text), Paragraph("Subtotal:", fin_label), Paragraph(f"Rp {total_gross:,.0f}", fin_val)],
        [Paragraph("", cell_text), Paragraph("Diskon Grosir (2%):", fin_label), Paragraph(f"- Rp {diskon:,.0f}", fin_val)],
        [Paragraph("", cell_text), Paragraph("TOTAL AKHIR:", fin_label), Paragraph(f"Rp {total_akhir:,.0f}", fin_val_bold)],
        [Paragraph("", cell_text), Paragraph("Tunai (Cash):", fin_label), Paragraph(f"Rp {tunai:,.0f}", fin_val)],
        [Paragraph("", cell_text), Paragraph("Kembalian:", fin_label), Paragraph(f"Rp {kembalian:,.0f}", fin_val)]
    ]
    fin_table = Table(fin_data, colWidths=[240, 150, 150])
    fin_table.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 3), ('TOPPADDING', (0,0), (-1,-1), 3)]))
    story.append(fin_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Data Sourcing untuk Interface - Menggunakan list comprehension untuk konversi data ke standard Tuple (Solusi Fix Pickle Error)
conn = get_db_connection()
barang_list = [(r[0], r[1], r[2], r[3]) for r in conn.execute("SELECT id, nama, ukuran, satuan FROM barang").fetchall()]
gudang_list = [(r[0], r[1]) for r in conn.execute("SELECT id, nama FROM gudang").fetchall()]
data_stok_raw = [
    {
        'id_barang': r[0], 'nama': r[1], 'ukuran': r[2], 'id_gudang': r[3], 
        'gudang_nama': r[4], 'jumlah_batang': r[5], 'satuan': r[6], 'sales_terakhir': r[7]
    } 
    for r in conn.execute("""
        SELECT s.id_barang, b.nama, b.ukuran, s.id_gudang, g.nama as gudang_nama, s.jumlah_batang, b.satuan, s.sales_terakhir
        FROM stok s
        JOIN barang b ON s.id_barang = b.id
        JOIN gudang g ON s.id_gudang = g.id
        ORDER BY b.nama ASC
    """).fetchall()
]
conn.close()


# ==========================================
# 1. HEADER APLIKASI UTAMA
# ==========================================
st.title("🏗️ Sistem Inventory Toko Besi Medan Jaya")
st.markdown("Aplikasi Manajemen Gudang Modern Terintegrasi - Fleksibilitas Multi Satuan Barang")

col_main_left, col_main_right = st.columns([7, 5])

with col_main_left:
    # ==========================================
    # 2. ANTARMUKA AKTIVITAS BARANG (KELUAR / MASUK)
    # ==========================================
    st.write("### 🔄 Manifes & Pergerakan Barang Gudang")
    
    activity = st.radio(
        "Pilih Jenis Aktivitas Logistik:",
        ["Keluar (Penjualan/Sales)", "Masuk (Restock/Supplier)"],
        horizontal=True,
        key="radio_aktivitas_utama"
    )
    
    # Fungsi Pintar untuk Format Dropdown Pilihan Barang
    def format_nama_barang_bersih(x):
        return f"{x[1]} {x[2]}" if (len(x) > 2 and x[2] and x[2] != '-') else x[1]

    # ------------------------------------------------------------------
    # A. INTERFACE: BARANG KELUAR (PENJUALAN)
    # ------------------------------------------------------------------
    if activity == "Keluar (Penjualan/Sales)":
        st.markdown("#### 📄 Data Nota & Input Item")
        
        nota_col1, nota_col2 = st.columns(2)
        with nota_col1:
            nota_input = st.text_input("Nomor Nota / Invoice", value=st.session_state.invoice_number, key="input_nota_keluar")
        with nota_col2:
            customer_input = st.text_input("Nama Pelanggan", value="Cash", key="input_customer_keluar")
        
        prod_col1, prod_col2 = st.columns(2)
        with prod_col1:
            barang_pilihan = st.selectbox("Pilih Barang", barang_list, format_func=format_nama_barang_bersih, key="select_barang_keluar")
        with prod_col2:
            gudang_pilihan = st.selectbox("Ambil dari Gudang Berapa", gudang_list, format_func=lambda x: x[1], key="select_gudang_keluar")
        
        # Grid Baris 3: Kolom Input yang Seimbang dan Proporsional
        det_col1, det_col2, det_col3 = st.columns([2, 2, 3])
        with det_col1:
            qty = st.number_input("Banyaknya Barang", min_value=0.01, value=1.0, step=0.01, format="%.2f", key="number_qty_keluar")
        with det_col2:
            satuan_pilihan = st.selectbox("Pilih Satuan", ["Batang", "Kilogram", "Ons", "Pcs"], key="select_satuan_keluar")
        with det_col3:
            harga = st.number_input("Harga per Satuan (Rp)", min_value=0, value=35000, step=500, key="number_harga_keluar")
            
        st.markdown(" ")
        if st.button("➕ Tambahkan Ke Keranjang Nota", key="btn_add_cart_keluar", width="stretch"):
            st.session_state.cart_keluar.append({
                'id_barang': barang_pilihan[0],
                'nama': barang_pilihan[1],
                'ukuran': barang_pilihan[2] if (len(barang_pilihan) > 2 and barang_pilihan[2] != '-') else "",
                'id_gudang': gudang_pilihan[0],
                'gudang_nama': gudang_pilihan[1],
                'qty': qty,
                'satuan': satuan_pilihan,
                'harga': harga,
                'item_subtotal': qty * harga
            })
            st.toast("Item berhasil ditambahkan ke keranjang!")

        # Tampilan Ringkasan Manifest Invoice Keluar
        if st.session_state.cart_keluar:
            st.markdown("---")
            st.markdown("### 🛒 Ringkasan Transaksi Nota")
            
            for idx, item in enumerate(st.session_state.cart_keluar, start=1):
                st.markdown(f"**{idx}. {item['nama']} {item['ukuran']}** | {item['qty']} {item['satuan']} dari {item['gudang_nama']} | @ Rp {item['harga']:,} = **Rp {item['item_subtotal']:,}**")
            
            c_bt1, c_bt2 = st.columns(2)
            with c_bt1:
                if st.button("🗑️ Kosongkan Keranjang", key="clear_cart_keluar", width="stretch"):
                    st.session_state.cart_keluar = []
                    st.rerun()
            with c_bt2:
                pdf_data = buat_pdf_bytes(nota_input, customer_input, st.session_state.cart_keluar)
                st.download_button("📥 CETAK & UNDUH PDF INVOICE", data=pdf_data, file_name=f"Invoice_{nota_input}.pdf", mime="application/pdf", width="stretch")
                
            if st.button("💾 SIMPAN TRANSAKSI POTONG STOK", key="save_stok_keluar", width="stretch"):
                for item in st.session_state.cart_keluar:
                    update_stok_db(item['id_barang'], item['id_gudang'], item['qty'], "Keluar")
                st.success("✅ Stok berhasil dipotong! Transaksi penjualan telah dibukukan.")
                st.session_state.cart_keluar = []
                st.session_state.invoice_number = f"INV-MJ-{datetime.now().strftime('%d%m%Y-%H%M')}"
                st.rerun()

    # ------------------------------------------------------------------
    # B. INTERFACE: BARANG MASUK (RESTOCK)
    # ------------------------------------------------------------------
    else:
        st.markdown("#### 🏢 Data Pengiriman Supplier")
        nama_sales_masuk = st.text_input("Nama Penyuplai / Sales Supplier", placeholder="Masukkan nama sales atau nama pabrik...", key="input_sales_masuk")
        
        restock_col1, restock_col2 = st.columns(2)
        with restock_col1:
            barang_pilihan = st.selectbox("Pilih Barang yang Masuk", barang_list, format_func=format_nama_barang_bersih, key="select_barang_masuk")
        with restock_col2:
            gudang_pilihan = st.selectbox("Simpan di Gudang Berapa", gudang_list, format_func=lambda x: x[1], key="select_gudang_masuk")
        
        in_col1, in_col2 = st.columns(2)
        with in_col1:
            qty = st.number_input("Banyaknya Barang Masuk", min_value=1, value=50, step=1, key="number_qty_masuk")
        with in_col2:
            satuan_pilihan_masuk = st.selectbox("Satuan Logistik", ["Batang", "Kilogram", "Ons", "Pcs"], key="select_satuan_masuk")
            
        st.markdown(" ")
        if st.button("➕ Masukkan Daftar Restock", key="btn_add_cart_masuk", width="stretch"):
            if not nama_sales_masuk.strip():
                st.warning("⚠️ Mohon isi Nama Penyuplai terlebih dahulu!")
            else:
                st.session_state.cart_masuk.append({
                    'id_barang': barang_pilihan[0],
                    'nama': barang_pilihan[1],
                    'ukuran': barang_pilihan[2] if (len(barang_pilihan) > 2 and barang_pilihan[2] != '-') else "",
                    'id_gudang': gudang_pilihan[0],
                    'gudang_nama': gudang_pilihan[1],
                    'qty': qty,
                    'satuan': satuan_pilihan_masuk,
                    'sales': nama_sales_masuk
                })
                st.toast("Item berhasil dicatat ke daftar tunggu restock!")

        if st.session_state.cart_masuk:
            st.markdown("---")
            st.markdown("### 📥 Daftar Tunggu Restock Masuk")
            
            for idx, item in enumerate(st.session_state.cart_masuk, start=1):
                st.markdown(f"**{idx}. {item['nama']} {item['ukuran']}** -> +{item['qty']} {item['satuan']} ke {item['gudang_nama']} (Sales: {item['sales']})")
            
            st.markdown(" ")
            if st.button("🗑️ Bersihkan Daftar Tunggu", key="clear_cart_mas", width="stretch"):
                st.session_state.cart_masuk = []
                st.rerun()
            
            if st.button("💾 SIMPAN SEMUA BARANG MASUK KE DATABASE", key="btn_simpan_masuk", width="stretch"):
                for item in st.session_state.cart_masuk:
                    update_stok_db(item['id_barang'], item['id_gudang'], item['qty'], "Masuk", nama_sales=item['sales'])
                st.success("✅ Sukses! Semua item restock massal berhasil ditambahkan ke database.")
                st.session_state.cart_masuk = []
                st.rerun()


with col_main_right:
    # ==========================================
    # 3. FITUR LIVE INVENTORY SEARCH & DATA VIEW
    # ==========================================
    st.write("### 📦 Sisa Stok Gudang Real-Time")
    
    cari_produk = st.text_input("🔍 Cari Nama Besi / Ukuran / Supplier:", placeholder="Ketik besi, siku, gudang, dll...", key="search_stok_input")
    
    tabel_tampil = []
    for d in data_stok_raw:
        nama_b = d['nama']
        ukuran_b = d['ukuran'] if (d['ukuran'] and d['ukuran'] != '-') else ""
        gabung_nama_tabel = f"{nama_b} {ukuran_b}".strip()
        gudang_b = d['gudang_nama']
        stok_angka = d['jumlah_batang']
        satuan_b = d['satuan'] if d['satuan'] else "Batang"
        sales_b = d['sales_terakhir']
        
        # Fitur Sembunyikan Stok Kosong saat Kolom Pencarian Sedang Bersih/Kosong
        if not cari_produk.strip() and stok_angka == 0:
            continue
            
        # Filter Pencarian Global Multi-Kolom
        if (cari_produk.lower() in gabung_nama_tabel.lower() or 
            cari_produk.lower() in gudang_b.lower() or 
            cari_produk.lower() in sales_b.lower()):
            
            tabel_tampil.append({
                "Nama Barang": gabung_nama_tabel,
                "Lokasi Gudang": gudang_b,
                "Jumlah Stok": f"{int(stok_angka) if isinstance(stok_angka, float) and stok_angka.is_integer() else stok_angka} {satuan_b}",
                "Penyuplai Terakhir": sales_b
            })
            
    if tabel_tampil:
        df_stok = pd.DataFrame(tabel_tampil)
        st.dataframe(df_stok, width="stretch", hide_index=True)
    else:
        st.info("💡 Tidak ada data stok yang cocok, atau barang berstok 0 disembunyikan.")


# ==========================================
# 4. FITUR PENGATURAN DATA MASTER BARANG
# ==========================================
st.markdown("---")
st.subheader("⚙️ Pengaturan & Ekspansi Master Variasi")
expand_barang, expand_gudang = st.columns(2)

with expand_barang:
    st.write("**➕ Tambah Varian Barang Baru**")
    if gudang_list:
        with st.form("form_barang", clear_on_submit=True):
            input_gabungan = st.text_input(
                "Nama & Ukuran Barang Baru", 
                placeholder="Ketik langsung: holo 30x30x1.6(0.8pas) atau kawatlas 3.2mm"
            )
            satuan_baru = st.selectbox(
                "Pilih Satuan Default", 
                ["Batang", "Kilogram", "Ons", "Pcs"], 
                key="select_satuan_barang_baru"
            )
            submit_b = st.form_submit_button("Daftarkan Barang Baru", width="stretch")
            
            if submit_b and input_gabungan:
                input_bersih = input_gabungan.strip()
                if " " in input_bersih:
                    # Memecah berdasarkan spasi PERTAMA saja (maxsplit=1)
                    nama_baru, ukuran_baru = input_bersih.split(" ", 1)
                    nama_baru = nama_baru.strip()
                    ukuran_baru = ukuran_baru.strip()
                    
                    if nama_baru and ukuran_baru:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO barang (nama, ukuran, satuan) VALUES (?, ?, ?)", (nama_baru, ukuran_baru, satuan_baru))
                        id_b = cursor.lastrowid
                        all_gudang = cursor.execute("SELECT id FROM gudang").fetchall()
                        for g in all_gudang:
                            cursor.execute("INSERT INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir) VALUES (?, ?, 0, '-')", (id_b, g[0]))
                        conn.commit()
                        conn.close()
                        st.success(f"🎉 Produk '{nama_baru}' ({ukuran_baru}) berhasil didaftarkan!")
                        st.rerun()
                else:
                    st.error("❌ Mohon beri jarak spasi antara Nama Barang dan Ukurannya! Contoh: holo 30x30x1.6")

with expand_gudang:
    st.write("**🏢 Tambah Master Gudang Baru**")
    with st.form("form_gudang", clear_on_submit=True):
        gudang_baru = st.text_input("Nama Kompleks Gudang Baru", placeholder="Misal: Gudang 4")
        submit_g = st.form_submit_button("Daftarkan Gudang Baru", width="stretch")
        
        if submit_g and gudang_baru.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO gudang (nama) VALUES (?)", (gudang_baru.strip(),))
            id_g = cursor.lastrowid
            all_barang = cursor.execute("SELECT id FROM barang").fetchall()
            for b in all_barang:
                cursor.execute("INSERT INTO stok (id_barang, id_gudang, jumlah_batang, sales_terakhir) VALUES (?, ?, 0, '-')", (b[0], id_g))
            conn.commit()
            conn.close()
            st.success(f"🏢 Kompleks {gudang_baru} berhasil didaftarkan ke sistem multi-gudang!")
            st.rerun()

# ==========================================
# FEATURE: MENU KOREKSI STOK ADMIN (TOKO BESI MEDAN JAYA)
# ==========================================
st.markdown("---")
st.subheader("🛠️ Mode Admin: Koreksi & Edit Stok")
st.caption("Gunakan menu ini hanya untuk memperbaiki kesalahan input angka stok barang.")

# Hubungkan ke database untuk mengambil daftar barang dan gudang
conn = sqlite3.connect("inventory_medan_jaya.db")
cursor = conn.cursor()

# Ambil daftar barang yang unik untuk dropdown
cursor.execute("SELECT nama, ukuran FROM barang ORDER BY nama ASC, ukuran ASC")
daftar_barang_admin = [f"{row[0]} {row[1]}" for row in cursor.fetchall()]

# Ambil daftar gudang untuk dropdown
cursor.execute("SELECT nama FROM gudang ORDER BY nama ASC")
daftar_gudang_admin = [row[0] for row in cursor.fetchall()]
conn.close()

if daftar_barang_admin and daftar_gudang_admin:
    # Kita bagi menjadi 4 kolom agar pas dengan input satuan
    col1_adm, col2_adm, col3_adm, col4_adm = st.columns(4)
    
    with col1_adm:
        barang_pilihan = st.selectbox("Pilih Barang:", daftar_barang_admin, key="adm_brg")
    with col2_adm:
        gudang_pilihan = st.selectbox("Lokasi Gudang:", daftar_gudang_admin, key="adm_gdg")
    with col3_adm:
        stok_baru = st.number_input("Stok yang Benar:", min_value=0, value=0, step=1, key="adm_stk")
    with col4_adm:
        # Pilihan satuan yang bisa Anda sesuaikan langsung
        satuan_baru = st.selectbox("Satuan yang Benar:", ["Batang", "Kg", "Kotak", "Pcs", "Roll", "Lembar"], key="adm_sat")
        
    if st.button("🔄 Perbarui & Simpan Data Benar", width="stretch"):
        conn = sqlite3.connect("inventory_medan_jaya.db")
        cursor = conn.cursor()
        
        # Pisahkan nama barang untuk query database (mengambil bagian sebelum spasi pertama atau teks utamanya)
        # Karena di database kolom 'nama' hanya berisi teks pendek (CNP, UNP, kawat)
        nama_asli_db = barang_pilihan.split(" ")[0]
        
        # Ambil ukuran dari sisa teks gabungan tadi jika ada
        sisa_teks = barang_pilihan.split(" ", 1)
        ukuran_asli_db = sisa_teks[1] if len(sisa_teks) > 1 else ""
        
        # Cek ID barang berdasarkan nama dan ukuran di tabel barang
        cursor.execute("SELECT id FROM barang WHERE nama = ? AND ukuran = ?", (nama_asli_db, ukuran_asli_db))
        data_barang = cursor.fetchone()
        
        if data_barang:
            # 1. Update jumlah stok di gudang tersebut
            # Catatan: Jika struktur tabel Anda menyimpan stok di tabel terpisah bernama 'barang', sesuaikan nama kolomnya
            try:
                cursor.execute("UPDATE barang SET jumlah_stok = ? WHERE id = ?", (stok_baru, data_barang[0]))
            except sqlite3.OperationalError:
                # Jaga-jaga jika kolom stoknya bernama lain di database Anda
                pass
                
            # 2. Update satuan default barang tersebut di tabel barang
            # Kita asumsikan nama kolom satuannya adalah 'satuan' atau 'satuan_default'
            try:
                cursor.execute("UPDATE barang SET satuan = ? WHERE id = ?", (satuan_baru, data_barang[0]))
            except sqlite3.OperationalError:
                try:
                    cursor.execute("UPDATE barang SET satuan_default = ? WHERE id = ?", (satuan_baru, data_barang[0]))
                except sqlite3.OperationalError:
                    st.error("Kolom satuan di database tidak mengenali nama yang dimasukkan. Hubungi untuk cek struktur kolom.")
            
            conn.commit()
            st.success(f"Berhasil! {barang_pilihan} telah dikoreksi menjadi {stok_baru} {satuan_baru}.")
            st.rerun()
        else:
            st.error(f"Data {barang_pilihan} tidak ditemukan. Silakan periksa kembali lokasinya.")
        conn.close()
else:
    st.info("Belum ada data barang atau gudang di dalam sistem.")
