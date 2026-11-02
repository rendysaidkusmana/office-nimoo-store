import sqlite3
import os
import base64
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__, static_url_path='/static')
DB_NAME = 'nimoo_pos.db'
ATTENDANCE_FOLDER = os.path.join('static', 'attendance')

if not os.path.exists(ATTENDANCE_FOLDER):
    os.makedirs(ATTENDANCE_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tabel User
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'Karyawan'
        )
    ''')
    
    # 2. Tabel Absensi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            photo_path TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # 3. Tabel Master Produk (Inventory)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            barcode TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            hpp REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock_physical INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO users (username, password, full_name, role) VALUES ('admin', '123456', 'Karyawan Nimoo', 'Admin')")
    
    conn.commit()
    conn.close()

init_db()

# --- HALAMAN LOGIN & ABSENSI ---
@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login & Absensi - Nimoo Store</title>
        <style>
            * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
            body { background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 15px; }
            .card { background: #1e293b; padding: 25px; border-radius: 16px; width: 100%; max-width: 420px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); text-align: center; }
            h2 { color: #38bdf8; margin-bottom: 5px; }
            p { font-size: 14px; color: #94a3b8; margin-bottom: 20px; }
            input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; }
            button { width: 100%; padding: 12px; background: #0284c7; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 10px; }
            .camera-container { position: relative; width: 100%; border-radius: 12px; overflow: hidden; border: 2px solid #38bdf8; margin-top: 10px; background: #000; }
            video { width: 100%; display: block; transform: scaleX(-1); }
            canvas { display: none; }
            .live-timestamp { position: absolute; bottom: 10px; left: 10px; right: 10px; background: rgba(0,0,0,0.75); color: #00ffcc; font-family: monospace; font-size: 11px; padding: 6px; border-radius: 6px; text-align: left; }
            .hidden { display: none; }
        </style>
    </head>
    <body>

        <div class="card" id="loginCard">
            <h2>NIMOO STORE</h2>
            <p>Sistem POS & Presensi Karyawan</p>
            <input type="text" id="username" placeholder="Username (admin)">
            <input type="password" id="password" placeholder="Password (123456)">
            <button onclick="prosesLogin()">Lanjut ke Absen Selfie</button>
            <div id="loginMsg" style="color:#f87171; font-size:13px; margin-top:10px;"></div>
        </div>

        <div class="card hidden" id="absensiCard">
            <h2>ABSENSI SELFIE</h2>
            <p id="userGreeting">Halo!</p>
            <div class="camera-container">
                <video id="webcam" autoplay playsinline></video>
                <div class="live-timestamp" id="liveClock">NIMOO STORE | --/--/---- --:--:--</div>
            </div>
            <canvas id="canvas"></canvas>
            <button onclick="ambilFotoDanAbsen()" id="btnAbsen">📸 Take Selfie & Masuk Kasir</button>
            <div id="absenMsg" style="color:#4ade80; font-size:13px; margin-top:10px;"></div>
        </div>

        <script>
            let currentUser = null;
            function updateClock() {
                const now = new Date();
                const clockElem = document.getElementById('liveClock');
                if (clockElem) clockElem.innerText = "NIMOO STORE ABSEN | " + now.toLocaleString('id-ID');
            }
            setInterval(updateClock, 1000);

            async function prosesLogin() {
                const u = document.getElementById('username').value;
                const p = document.getElementById('password').value;
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    currentUser = data.user;
                    document.getElementById('loginCard').classList.add('hidden');
                    document.getElementById('absensiCard').classList.remove('hidden');
                    document.getElementById('userGreeting').innerText = `Halo, ${currentUser.full_name}! Silakan foto selfie untuk masuk.`;
                    startCamera();
                } else {
                    document.getElementById('loginMsg').innerText = data.message;
                }
            }

            function startCamera() {
                navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
                    .then(stream => { document.getElementById('webcam').srcObject = stream; updateClock(); })
                    .catch(err => { alert('Kamera tidak terdeteksi!'); });
            }

            async function ambilFotoDanAbsen() {
                const video = document.getElementById('webcam');
                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');

                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 480;
                ctx.translate(canvas.width, 0);
                ctx.scale(-1, 1);
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                ctx.setTransform(1, 0, 0, 1, 0, 0);

                const timeString = "NIMOO STORE ABSEN | " + new Date().toLocaleString('id-ID');
                ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
                ctx.fillRect(10, canvas.height - 40, canvas.width - 20, 30);
                ctx.font = "bold 16px Arial";
                ctx.fillStyle = "#00ffcc";
                ctx.fillText(timeString, 20, canvas.height - 20);

                const imageData = canvas.toDataURL('image/jpeg');
                const res = await fetch('/api/attendance', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: currentUser.user_id, full_name: currentUser.full_name, image: imageData })
                });

                const data = await res.json();
                if (data.status === 'success') {
                    document.getElementById('absenMsg').innerText = "✅ Absen Berhasil! Mengalihkan ke Dashboard...";
                    setTimeout(() => { window.location.href = '/pos'; }, 1000);
                }
            }
        </script>
    </body>
    </html>
    """

# --- HALAMAN DASHBOARD UTAMA KASIR ---
@app.route('/pos')
def pos_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DASHBOARD KASIR - NIMOO STORE</title>
        <style>
            * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
            body { background: #0f172a; color: #fff; margin: 0; padding: 20px; }
            .header { display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 15px 20px; border-radius: 12px; margin-bottom: 20px; }
            .header h2 { margin: 0; color: #38bdf8; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            @media(max-width: 768px) { .grid { grid-template-columns: 1fr; } }
            .card { background: #1e293b; padding: 20px; border-radius: 12px; }
            h3 { margin-top: 0; color: #f1f5f9; border-bottom: 1px solid #334155; padding-bottom: 10px; }
            input, button { width: 100%; padding: 10px; margin: 6px 0; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #fff; }
            button { background: #0284c7; font-weight: bold; cursor: pointer; border: none; }
            button:hover { background: #0369a1; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
            th, td { border: 1px solid #334155; padding: 8px; text-align: left; }
            th { background: #0f172a; color: #38bdf8; }
            .badge { background: #22c55e; color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
        </style>
    </head>
    <body>

        <div class="header">
            <h2>NIMOO STORE POS</h2>
            <div>Sistem Kasir & Kelola Stok</div>
        </div>

        <div class="grid">
            <!-- SEKTOR 1: TAMBAH PRODUK -->
            <div class="card">
                <h3>📦 Tambah Produk Baru</h3>
                <input type="text" id="sku" placeholder="SKU (cth: NMO-001)">
                <input type="text" id="barcode" placeholder="Barcode (cth: 899123456)">
                <input type="text" id="pname" placeholder="Nama Produk (cth: Kaos Oversize)">
                <input type="number" id="hpp" placeholder="HPP / Modal (Rp)">
                <input type="number" id="price" placeholder="Harga Jual (Rp)">
                <input type="number" id="stock" placeholder="Stok Physical">
                <button onclick="tambahProduk()">+ Simpan Produk ke Database</button>
                <div id="prodMsg" style="font-size:13px; margin-top:5px;"></div>
            </div>

            <!-- SEKTOR 2: STOK BARANG SAAT INI -->
            <div class="card">
                <h3>📊 Daftar Stok Barang</h3>
                <button onclick="loadProducts()" style="background:#334155; margin-bottom:10px;">🔄 Refresh Stok</button>
                <table>
                    <thead>
                        <tr>
                            <th>SKU / Nama</th>
                            <th>HPP</th>
                            <th>Harga Jual</th>
                            <th>Stok</th>
                        </tr>
                    </thead>
                    <tbody id="productTable">
                        <tr><td colspan="4">Memuat data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadProducts() {
                const res = await fetch('/api/products');
                const data = await res.json();
                const tbody = document.getElementById('productTable');
                tbody.innerHTML = '';
                
                if(data.data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4">Belum ada produk. Sila tambahkan di sebelah kiri.</td></tr>';
                    return;
                }

                data.data.forEach(p => {
                    tbody.innerHTML += `
                        <tr>
                            <td><b>${p.product_name}</b><br><small style="color:#94a3b8">${p.sku} | ${p.barcode}</small></td>
                            <td>Rp ${p.hpp.toLocaleString('id-ID')}</td>
                            <td>Rp ${p.selling_price.toLocaleString('id-ID')}</td>
                            <td><span class="badge">${p.stock_physical} pcs</span></td>
                        </tr>
                    `;
                });
            }

            async function tambahProduk() {
                const body = {
                    sku: document.getElementById('sku').value,
                    barcode: document.getElementById('barcode').value,
                    product_name: document.getElementById('pname').value,
                    hpp: parseFloat(document.getElementById('hpp').value),
                    selling_price: parseFloat(document.getElementById('price').value),
                    stock_physical: parseInt(document.getElementById('stock').value)
                };

                const res = await fetch('/api/products/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                const data = await res.json();
                
                if (data.status === 'success') {
                    document.getElementById('prodMsg').style.color = '#4ade80';
                    document.getElementById('prodMsg').innerText = "✅ Produk berhasil disimpan!";
                    loadProducts();
                    document.getElementById('sku').value = '';
                    document.getElementById('barcode').value = '';
                    document.getElementById('pname').value = '';
                    document.getElementById('hpp').value = '';
                    document.getElementById('price').value = '';
                    document.getElementById('stock').value = '';
                } else {
                    document.getElementById('prodMsg').style.color = '#f87171';
                    document.getElementById('prodMsg').innerText = "❌ Gagal: " + data.message;
                }
            }

            loadProducts();
        </script>
    </body>
    </html>
    """

# --- BACKEND API ENDPOINTS ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (data.get('username'), data.get('password'))).fetchone()
    conn.close()
    if user:
        return jsonify({"status": "success", "user": {"user_id": user["user_id"], "username": user["username"], "full_name": user["full_name"], "role": user["role"]}})
    return jsonify({"status": "error", "message": "Username / Password salah!"}), 401

@app.route('/api/attendance', methods=['POST'])
def attendance():
    data = request.get_json() or {}
    image_data = data.get('image')
    if not image_data:
        return jsonify({"status": "error", "message": "Foto selfie wajib ada!"}), 400
        
    _, encoded = image_data.split(",", 1)
    file_bytes = base64.b64decode(encoded)
    filename = f"absen_{data.get('user_id')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(ATTENDANCE_FOLDER, filename)
    
    with open(filepath, "wb") as f:
        f.write(file_bytes)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO attendance (user_id, full_name, photo_path) VALUES (?, ?, ?)', (data.get('user_id'), data.get('full_name'), filepath))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Absensi berhasil!"})

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY product_id DESC').fetchall()
    conn.close()
    return jsonify({"status": "success", "data": [dict(p) for p in products]})

@app.route('/api/products/add', methods=['POST'])
def add_product():
    data = request.get_json() or {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (sku, barcode, product_name, hpp, selling_price, stock_physical)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['sku'], data['barcode'], data['product_name'], data['hpp'], data['selling_price'], data['stock_physical']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Produk berhasil ditambahkan!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)