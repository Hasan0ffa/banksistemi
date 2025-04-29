# Onlayn Bank Sistemi - Flask ilə

# Lazımi kitabxanaların yüklənməsi
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import uuid

# Flask tətbiqinin yaradılması
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy obyektinin yaradılması
db = SQLAlchemy(app)

# İstifadəçi modeli
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    accounts = db.relationship('Account', backref='owner', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Hesab modeli
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Əməliyyat modeli
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer
    description = db.Column(db.String(200))
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    recipient_account = db.Column(db.String(20), nullable=True)  # Transfer zamanı
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Marşrutlar (Routes)

# Ana səhifə
@app.route('/')
def index():
    return render_template('index.html')

# Qeydiyyat
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        
        # Email ünvanının yoxlanılması
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Bu email artıq qeydiyyatdan keçib.')
            return redirect(url_for('register'))
        
        # İstifadəçinin yaradılması
        hashed_password = generate_password_hash(password)
        new_user = User(fullname=fullname, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        # İlk hesabın yaradılması
        account_number = f"ACC{uuid.uuid4().hex[:8].upper()}"
        new_account = Account(account_number=account_number, user_id=new_user.id)
        db.session.add(new_account)
        db.session.commit()
        
        flash('Qeydiyyat uğurla tamamlandı. İndi daxil ola bilərsiniz.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Giriş
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Uğurla daxil oldunuz.')
            return redirect(url_for('dashboard'))
        else:
            flash('Daxil olmaq alınmadı. Email və ya şifrə yanlışdır.')
    
    return render_template('login.html')

# Çıxış
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Sistemdən çıxdınız.')
    return redirect(url_for('index'))

# İdarə paneli
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    accounts = Account.query.filter_by(user_id=user.id).all()
    
    return render_template('dashboard.html', user=user, accounts=accounts)

# Hesab yaratma
@app.route('/create_account', methods=['POST'])
def create_account():
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account_number = f"ACC{uuid.uuid4().hex[:8].upper()}"
    new_account = Account(account_number=account_number, user_id=session['user_id'])
    db.session.add(new_account)
    db.session.commit()
    
    flash('Yeni hesab uğurla yaradıldı.')
    return redirect(url_for('dashboard'))

# Hesab məlumatları
@app.route('/account/<int:account_id>')
def account_details(account_id):
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account = Account.query.get_or_404(account_id)
    
    # Yalnız öz hesablarına baxmaq icazəsi
    if account.user_id != session['user_id']:
        flash('Bu hesaba baxmaq üçün icazəniz yoxdur.')
        return redirect(url_for('dashboard'))
    
    transactions = Transaction.query.filter_by(account_id=account_id).order_by(Transaction.timestamp.desc()).all()
    
    return render_template('account_details.html', account=account, transactions=transactions)

# Pul yatırma
@app.route('/deposit/<int:account_id>', methods=['GET', 'POST'])
def deposit(account_id):
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account = Account.query.get_or_404(account_id)
    
    # Yalnız öz hesablarına pul yatırmaq icazəsi
    if account.user_id != session['user_id']:
        flash('Bu hesaba pul yatırmaq üçün icazəniz yoxdur.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        
        if amount <= 0:
            flash('Məbləğ müsbət olmalıdır.')
            return redirect(url_for('deposit', account_id=account_id))
        
        # Hesab balansının yenilənməsi
        account.balance += amount
        
        # Əməliyyatın qeydə alınması
        transaction = Transaction(
            amount=amount,
            transaction_type='deposit',
            description=description,
            account_id=account_id
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'{amount} AZN uğurla hesaba əlavə edildi.')
        return redirect(url_for('account_details', account_id=account_id))
    
    return render_template('deposit.html', account=account)

# Pul çıxarma
@app.route('/withdraw/<int:account_id>', methods=['GET', 'POST'])
def withdraw(account_id):
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account = Account.query.get_or_404(account_id)
    
    # Yalnız öz hesablarından pul çıxarmaq icazəsi
    if account.user_id != session['user_id']:
        flash('Bu hesabdan pul çıxarmaq üçün icazəniz yoxdur.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description']
        
        if amount <= 0:
            flash('Məbləğ müsbət olmalıdır.')
            return redirect(url_for('withdraw', account_id=account_id))
        
        if amount > account.balance:
            flash('Hesabınızda kifayət qədər vəsait yoxdur.')
            return redirect(url_for('withdraw', account_id=account_id))
        
        # Hesab balansının yenilənməsi
        account.balance -= amount
        
        # Əməliyyatın qeydə alınması
        transaction = Transaction(
            amount=amount,
            transaction_type='withdrawal',
            description=description,
            account_id=account_id
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'{amount} AZN uğurla hesabdan çıxarıldı.')
        return redirect(url_for('account_details', account_id=account_id))
    
    return render_template('withdraw.html', account=account)

# Pul köçürmə
@app.route('/transfer/<int:account_id>', methods=['GET', 'POST'])
def transfer(account_id):
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account = Account.query.get_or_404(account_id)
    
    # Yalnız öz hesablarından köçürmə icazəsi
    if account.user_id != session['user_id']:
        flash('Bu hesabdan köçürmə üçün icazəniz yoxdur.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        recipient_account_number = request.form['recipient_account']
        description = request.form['description']
        
        if amount <= 0:
            flash('Məbləğ müsbət olmalıdır.')
            return redirect(url_for('transfer', account_id=account_id))
        
        if amount > account.balance:
            flash('Hesabınızda kifayət qədər vəsait yoxdur.')
            return redirect(url_for('transfer', account_id=account_id))
        
        # Alıcı hesabının tapılması
        recipient_account = Account.query.filter_by(account_number=recipient_account_number).first()
        
        if not recipient_account:
            flash('Alıcı hesabı tapılmadı.')
            return redirect(url_for('transfer', account_id=account_id))
        
        if recipient_account.id == account_id:
            flash('Öz hesabınıza köçürmə edə bilməzsiniz.')
            return redirect(url_for('transfer', account_id=account_id))
        
        # Göndərən hesabın balansının yenilənməsi
        account.balance -= amount
        
        # Alıcı hesabın balansının yenilənməsi
        recipient_account.balance += amount
        
        # Göndərən üçün əməliyyatın qeydə alınması
        sender_transaction = Transaction(
            amount=amount,
            transaction_type='transfer_out',
            description=description,
            account_id=account_id,
            recipient_account=recipient_account_number
        )
        
        # Alıcı üçün əməliyyatın qeydə alınması
        recipient_transaction = Transaction(
            amount=amount,
            transaction_type='transfer_in',
            description=f"Köçürmə: {account.account_number} hesabından",
            account_id=recipient_account.id
        )
        
        db.session.add(sender_transaction)
        db.session.add(recipient_transaction)
        db.session.commit()
        
        flash(f'{amount} AZN uğurla {recipient_account_number} hesabına köçürüldü.')
        return redirect(url_for('account_details', account_id=account_id))
    
    return render_template('transfer.html', account=account)
# Hesabı silmək
@app.route('/delete_account/<int:account_id>', methods=['POST'])
def delete_account(account_id):
    if 'user_id' not in session:
        flash('Zəhmət olmasa əvvəlcə daxil olun.')
        return redirect(url_for('login'))
    
    account = Account.query.get_or_404(account_id)
    
    # Yalnız istifadəçinin öz hesabını silməyə icazə
    if account.user_id != session['user_id']:
        flash('Bu hesabı silmək üçün icazəniz yoxdur.')
        return redirect(url_for('dashboard'))
    
    # Hesabla əlaqəli əməliyyatların silinməsi
    Transaction.query.filter_by(account_id=account_id).delete()
    
    # Hesabın silinməsi
    db.session.delete(account)
    db.session.commit()
    
    flash('Hesab uğurla silindi.')
    return redirect(url_for('dashboard'))

# HTML şablonları - templates qovluğunda yaradılmalıdır

# Verilənlər bazasının yaradılması üçün kontekst meneceri
with app.app_context():
    db.create_all()

# Tətbiqin işə salınması
if __name__ == '__main__':
    app.run(debug=True)

