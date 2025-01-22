from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import os
import qrcode

# Inisialisasi Aplikasi Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

# Inisialisasi Database
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Model Database
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_amount = db.Column(db.Integer, nullable=False)
    payment_status = db.Column(db.String(50), default="pending")
    orders = db.relationship('Order', backref='transaction', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Integer, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Endpoint: Halaman Utama
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

# Endpoint: Tambah ke Keranjang
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if product and product.stock > 0:
        cart_item = Cart.query.filter_by(product_id=product_id).first()
        if cart_item:
            if product.stock >= cart_item.quantity + 1:
                cart_item.quantity += 1
            else:
                flash('Jumlah melebihi stok yang tersedia!', 'warning')
                return redirect(url_for('index'))
        else:
            cart_item = Cart(product_id=product_id, quantity=1)
            db.session.add(cart_item)
        product.stock -= 1
        db.session.commit()
        flash('Produk berhasil ditambahkan ke keranjang!', 'success')
    else:
        flash('Stok produk habis atau produk tidak ditemukan!', 'danger')
    return redirect(url_for('index'))

# Endpoint: Lihat Keranjang
@app.route('/cart')
def view_cart():
    cart_items = Cart.query.all()
    total = 0
    cart_details = []
    for item in cart_items:
        product = Product.query.get(item.product_id)
        if product:
            cart_details.append({
                'id': item.id,
                'name': product.name,
                'price': product.price,
                'quantity': item.quantity
            })
            total += product.price * item.quantity
    return render_template('cart.html', cart=cart_details, total=total)

# Endpoint: Checkout - Proses Pembayaran
# Endpoint: Checkout - Proses Pembayaran
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        cart_items = Cart.query.all()
        if not cart_items:
            flash('Keranjang kosong! Tidak ada yang bisa di-checkout.', 'warning')
            return redirect(url_for('view_cart'))

        total_amount = 0
        for item in cart_items:
            product = Product.query.get(item.product_id)
            if product:
                total_amount += product.price * item.quantity

        # Simulasi Pembayaran
        transaction = Transaction(total_amount=total_amount)
        db.session.add(transaction)
        db.session.commit()

        flash('Transaksi dibuat! Silakan lakukan pembayaran.', 'info')
        return redirect(url_for('payment', transaction_id=transaction.id))

    # Menampilkan daftar barang yang ada di keranjang
    cart_items = Cart.query.all()
    total = 0
    cart_details = []
    for item in cart_items:
        product = Product.query.get(item.product_id)
        if product:
            cart_details.append({
                'id': item.id,
                'name': product.name,
                'price': product.price,
                'quantity': item.quantity
            })
            total += product.price * item.quantity

    return render_template('checkout.html', cart=cart_details, total=total)


# Endpoint: Halaman Pembayaran
@app.route('/payment/<int:transaction_id>', methods=['GET', 'POST'])
def payment(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        flash('Transaksi tidak ditemukan.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        transaction.payment_status = "paid"
        db.session.commit()
        flash('Pembayaran berhasil! Barang akan segera diproses.', 'success')

        # Pindahkan produk ke order dan hapus dari keranjang
        cart_items = Cart.query.all()
        for item in cart_items:
            product = Product.query.get(item.product_id)
            if product:
                total_price = product.price * item.quantity
                order = Order(product_id=product.id, name=product.name, price=product.price,
                              quantity=item.quantity, total_price=total_price, transaction_id=transaction.id)
                db.session.add(order)
                db.session.delete(item)
        db.session.commit()

        return redirect(url_for('index'))

    # Generate QR Code
    if not os.path.exists('static/qr_codes'):
        os.makedirs('static/qr_codes')
    payment_url = f"https://payment-link.com/payment?id={transaction.id}"
    qr = qrcode.make(payment_url)
    qr_path = f"static/qr_codes/{transaction.id}.png"
    qr.save(qr_path)

    return render_template('payment.html', transaction=transaction, qr_code=qr_path)
    
    # Admin: Menambah Produk
@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if not session.get('admin_logged_in'):
        flash('Silakan login terlebih dahulu!', 'warning')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        stock = request.form['stock']

        if not name or not price or not stock:
            flash('Semua field harus diisi!', 'danger')
            return redirect(url_for('add_product'))

        new_product = Product(name=name, price=int(price), stock=int(stock))
        db.session.add(new_product)
        db.session.commit()
        flash(f'Produk {name} berhasil ditambahkan!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_product.html')

# Admin: Menghapus Produk
@app.route('/admin/delete_product/<int:product_id>', methods=['GET'])
def delete_product(product_id):
    if not session.get('admin_logged_in'):
        flash('Silakan login terlebih dahulu!', 'warning')
        return redirect(url_for('admin_login'))

    product = Product.query.get(product_id)
    if product:
        db.session.delete(product)
        db.session.commit()
        flash(f'Produk {product.name} berhasil dihapus!', 'success')
    else:
        flash('Produk tidak ditemukan!', 'danger')

    return redirect(url_for('admin_dashboard'))


# Admin: Login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Username atau password salah!', 'danger')
    return render_template('admin_login.html')

# Admin: Dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('Silakan login terlebih dahulu!', 'warning')
        return redirect(url_for('admin_login'))
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)

# Admin: Logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logout berhasil!', 'success')
    return redirect(url_for('admin_login'))

# Admin: Hapus dari Keranjang
@app.route('/remove_from_cart/<int:cart_id>', methods=['GET'])
def remove_from_cart(cart_id):
    cart_item = Cart.query.get(cart_id)
    if cart_item:
        product = Product.query.get(cart_item.product_id)
        if product:
            product.stock += cart_item.quantity
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item berhasil dihapus dari keranjang.', 'success')
    else:
        flash('Item tidak ditemukan di keranjang.', 'danger')
    return redirect(url_for('view_cart'))

# CLI: Buat Database
@app.cli.command('create-db')
def create_db():
    db.create_all()
    print('Database berhasil dibuat!')

# CLI: Buat Admin
@app.cli.command('create-admin')
def create_admin():
    """Perintah CLI untuk membuat admin baru."""
    username = input('Masukkan username: ')
    password = input('Masukkan password: ')
    if not username or not password:
        print("Username dan password tidak boleh kosong!")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
    if Admin.query.filter_by(username=username).first():
        print('Admin dengan username tersebut sudah ada!')
    else:
        admin = Admin(username=username, password=hashed_password)
        db.session.add(admin)
        db.session.commit()
        print(f'Admin {username} berhasil dibuat!')

# CLI: Tambahkan Data Dummy
@app.cli.command('add-dummy-data')
def add_dummy_data():
    if not Product.query.first():
        products = [
            Product(name="Produk A", price=10000, stock=10),
            Product(name="Produk B", price=20000, stock=5),
            Product(name="Produk C", price=30000, stock=3),
        ]
        db.session.add_all(products)
        db.session.commit()
        print("Data dummy berhasil ditambahkan.")
    else:
        print("Data dummy sudah ada di database.")

if __name__ == '__main__':
    app.run(debug=True, port=5001)
