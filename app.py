from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
import pandas as pd
import io
import bcrypt
import logging
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'budget.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['APP_NAME'] = 'Yemi Wallet'
app.config['APP_TITLE'] = 'Yemi Wallet - Votre gestionnaire financier'
app.config['APP_DESCRIPTION'] = 'Gérez vos finances personnelles simplement et efficacement'
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.context_processor
def inject_app_config():
    return {
        'app_name': app.config['APP_NAME'],
        'app_title': app.config['APP_TITLE'],
        'app_description': app.config['APP_DESCRIPTION']
    }

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    phone_country = db.Column(db.String(2), nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    savings_accounts = db.relationship('SavingsAccount', backref='user', lazy=True)
    
    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    def check_password(self, password):
        if self.password_hash:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash)
        return False

@login_manager.user_loader
def load_user(user_id):
    logger.debug(f"Loading user {user_id}")
    return User.query.get(int(user_id))

class SavingsAccount(db.Model):
    __tablename__ = 'savings_account'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_amount = db.Column(db.Float, nullable=True)
    target_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'percentage': self.percentage,
            'current_amount': self.current_amount,
            'target_amount': self.target_amount,
            'target_date': self.target_date.strftime('%Y-%m-%d') if self.target_date else None,
            'is_active': self.is_active,
            'is_archived': self.is_archived,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    transactions = db.relationship('SavingsTransaction', backref='account', lazy=True)
    
    @property
    def progress_percentage(self):
        try:
            if self.target_amount is None or self.target_amount <= 0:
                return 0
            return min(100, (self.current_amount / self.target_amount) * 100)
        except (TypeError, ZeroDivisionError):
            return 0
    
    @property
    def days_remaining(self):
        try:
            if self.target_date is None:
                return 0
            today = date.today()
            if self.target_date <= today:
                return 0
            return (self.target_date - today).days
        except (TypeError, AttributeError):
            return 0
    
    @property
    def daily_saving_needed(self):
        try:
            if self.target_amount is None or self.target_date is None:
                return 0
            remaining_amount = self.target_amount - self.current_amount
            days = self.days_remaining
            if days <= 0 or remaining_amount <= 0:
                return 0
            return remaining_amount / days
        except (TypeError, ZeroDivisionError):
            return 0

class SavingsTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))
    account_id = db.Column(db.Integer, db.ForeignKey('savings_account.id'), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(10))
    description = db.Column(db.String(200))
    amount = db.Column(db.Float)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50))
    savings_account_id = db.Column(db.Integer, db.ForeignKey('savings_account.id'), nullable=True)

class AccountHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(200), nullable=False)

def migrate_database():
    """Fonction pour migrer la base de données et renommer la colonne balance en current_amount"""
    try:
        with app.app_context():
            # Connexion directe à SQLite
            conn = sqlite3.connect('budget.db')
            cursor = conn.cursor()
            
            # Vérifier si la colonne balance existe
            cursor.execute("PRAGMA table_info(savings_account)")
            columns = cursor.fetchall()
            has_balance = any(col[1] == 'balance' for col in columns)
            has_current_amount = any(col[1] == 'current_amount' for col in columns)
            
            if has_balance and not has_current_amount:
                logger.info("Migration de la base de données...")
                
                # Créer une nouvelle table avec la nouvelle structure
                cursor.execute("""
                CREATE TABLE savings_account_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    percentage FLOAT NOT NULL,
                    current_amount FLOAT DEFAULT 0.0,
                    target_amount FLOAT,
                    target_date DATE,
                    is_active BOOLEAN DEFAULT 1,
                    is_archived BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL
                )
                """)
                
                # Copier les données de l'ancienne table vers la nouvelle
                cursor.execute("""
                INSERT INTO savings_account_new (id, name, percentage, current_amount, target_amount, target_date, is_active, is_archived, created_at, updated_at, user_id)
                SELECT id, name, percentage, balance, target_amount, target_date, is_active, 0, created_at, updated_at, user_id
                FROM savings_account
                """)
                
                # Supprimer l'ancienne table
                cursor.execute("DROP TABLE savings_account")
                
                # Renommer la nouvelle table
                cursor.execute("ALTER TABLE savings_account_new RENAME TO savings_account")
                
                # Valider les changements
                conn.commit()
                logger.info("Migration terminée avec succès")
            else:
                if has_current_amount:
                    logger.info("La colonne current_amount existe déjà")
                else:
                    logger.info("La colonne balance n'existe pas")
            
            conn.close()
            
    except Exception as e:
        logger.error(f"Erreur lors de la migration : {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise

@app.route('/')
@login_required
def index():
    logger.debug("Accessing index route")
    try:
        # Date du jour
        today = date.today()
        
        # Récupération des transactions
        transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date.desc()).all()
        
        # Calcul des statistiques
        total_income = sum(t.amount for t in transactions if t.transaction_type == 'income')
        total_expenses = sum(t.amount for t in transactions if t.transaction_type == 'expense')
        balance = total_income - total_expenses
        
        # Récupération des comptes d'épargne
        savings_accounts = SavingsAccount.query.filter_by(user_id=current_user.id, is_active=True).all()
        total_savings = sum(account.current_amount for account in savings_accounts)
        available_balance = balance - total_savings
        
        # Calcul des statistiques mensuelles
        current_month = datetime.now().month
        current_year = datetime.now().year
        monthly_transactions = [t for t in transactions if t.transaction_date.month == current_month and t.transaction_date.year == current_year]
        monthly_income = sum(t.amount for t in monthly_transactions if t.transaction_type == 'income')
        monthly_expenses = sum(t.amount for t in monthly_transactions if t.transaction_type == 'expense')
        
        logger.debug(f"Found {len(transactions)} transactions")
        
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        # Valeurs par défaut en cas d'erreur
        today = date.today()
        transactions = []
        total_income = 0
        total_expenses = 0
        balance = 0
        savings_accounts = []
        total_savings = 0
        available_balance = 0
        monthly_income = 0
        monthly_expenses = 0
    
    return render_template('index.html',
                         today=today,
                         transactions=transactions,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         balance=balance,
                         monthly_income=monthly_income,
                         monthly_expenses=monthly_expenses,
                         savings_accounts=savings_accounts,
                         total_savings=total_savings,
                         available_balance=available_balance,
                         current_user=current_user)

@app.route('/savings')
@login_required
def savings():
    try:
        logger.debug("Loading savings page")
        logger.debug(f"Current user: {current_user.id}")
        
        # Vérifier si l'utilisateur est connecté
        if not current_user.is_authenticated:
            logger.warning("User not authenticated")
            flash("Veuillez vous connecter pour accéder à cette page", 'warning')
            return redirect(url_for('login'))
            
        logger.debug("Fetching active savings accounts")
        # Récupérer les comptes d'épargne non archivés
        active_accounts = SavingsAccount.query.filter_by(
            user_id=current_user.id,
            is_archived=False
        ).order_by(SavingsAccount.created_at.desc()).all()
        logger.debug(f"Found {len(active_accounts)} active accounts")
        
        logger.debug("Fetching archived savings accounts")
        # Récupérer les comptes d'épargne archivés
        archived_accounts = SavingsAccount.query.filter_by(
            user_id=current_user.id,
            is_archived=True
        ).order_by(SavingsAccount.created_at.desc()).all()
        logger.debug(f"Found {len(archived_accounts)} archived accounts")
        
        # Calculer les statistiques uniquement pour les comptes actifs
        logger.debug("Calculating statistics")
        active_count = len([acc for acc in active_accounts if acc.is_active])
        total_savings = sum(acc.current_amount for acc in active_accounts if acc.is_active)
        
        # Calculer le total des objectifs (seulement pour les comptes avec un objectif)
        total_target = 0
        for acc in active_accounts:
            if acc.is_active and acc.target_amount is not None:
                total_target += acc.target_amount
        
        # Calculer le pourcentage global d'avancement
        global_progress = 0
        if total_target > 0:
            global_progress = (total_savings / total_target) * 100
            
        logger.debug(f"Statistics: active_count={active_count}, total_savings={total_savings}, total_target={total_target}, global_progress={global_progress}")
            
        # Ajouter le calcul du progrès pour chaque compte
        logger.debug("Processing individual accounts")
        for account in active_accounts + archived_accounts:
            logger.debug(f"Processing account {account.id}: {account.name}")
            try:
                # Calculer le progrès
                if account.target_amount and account.target_amount > 0:
                    account.progress = (account.current_amount / account.target_amount) * 100
                else:
                    account.progress = 0
                    
                # Calculer les jours restants si une date cible est définie
                if account.target_date:
                    today = date.today()
                    account.days_left = (account.target_date - today).days
                    if account.days_left > 0 and account.target_amount:
                        remaining_amount = account.target_amount - account.current_amount
                        account.daily_needed = remaining_amount / account.days_left if remaining_amount > 0 else 0
                    else:
                        account.daily_needed = 0
                else:
                    account.days_left = None
                    account.daily_needed = 0
                    
                logger.debug(f"Account {account.id} processed: progress={getattr(account, 'progress', 0)}, days_left={getattr(account, 'days_left', None)}, daily_needed={getattr(account, 'daily_needed', 0)}")
            except Exception as e:
                logger.error(f"Error processing account {account.id}: {str(e)}", exc_info=True)
                # Continue avec le compte suivant
                continue
        
        logger.debug("Rendering template")
        return render_template('savings.html',
                             active_accounts=active_accounts,
                             archived_accounts=archived_accounts,
                             active_count=active_count,
                             total_savings=total_savings,
                             total_target=total_target,
                             global_progress=global_progress,
                             today=date.today())
                             
    except Exception as e:
        logger.error(f"Error loading savings page: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors du chargement de la page.", 'danger')
        return redirect(url_for('index'))

@app.route('/add_savings', methods=['POST'])
@login_required
def add_savings():
    logger.debug("Processing add_savings request")
    try:
        # Récupérer les données du formulaire
        name = request.form.get('name', '').strip()
        percentage = request.form.get('percentage', '0')
        target_amount = request.form.get('target_amount', '')
        target_date = request.form.get('target_date', '')
        
        logger.debug(f"Raw form data: name='{name}', percentage='{percentage}', target_amount='{target_amount}', target_date='{target_date}'")
        
        # Validation du nom
        if not name:
            logger.warning("Name validation failed: empty name")
            flash('Le nom du compte est requis.', 'danger')
            return redirect(url_for('savings'))
            
        # Validation et conversion du pourcentage
        try:
            percentage = float(percentage)
            if percentage < 0 or percentage > 100:
                logger.warning(f"Percentage validation failed: {percentage} not between 0 and 100")
                flash('Le pourcentage doit être entre 0 et 100.', 'danger')
                return redirect(url_for('savings'))
        except ValueError as e:
            logger.warning(f"Percentage conversion failed: {str(e)}")
            flash('Le pourcentage doit être un nombre valide.', 'danger')
            return redirect(url_for('savings'))
            
        # Validation et conversion du montant cible
        if target_amount and target_amount.strip():
            try:
                target_amount = float(target_amount)
                if target_amount <= 0:
                    logger.warning(f"Target amount validation failed: {target_amount} not positive")
                    flash('L\'objectif doit être supérieur à 0.', 'danger')
                    return redirect(url_for('savings'))
            except ValueError as e:
                logger.warning(f"Target amount conversion failed: {str(e)}")
                flash('L\'objectif doit être un nombre valide.', 'danger')
                return redirect(url_for('savings'))
        else:
            target_amount = None
            
        # Validation et conversion de la date cible
        if target_date and target_date.strip():
            try:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                if target_date <= date.today():
                    logger.warning(f"Target date validation failed: {target_date} not in future")
                    flash('La date cible doit être dans le futur.', 'danger')
                    return redirect(url_for('savings'))
            except ValueError as e:
                logger.warning(f"Target date conversion failed: {str(e)}")
                flash('La date cible n\'est pas valide.', 'danger')
                return redirect(url_for('savings'))
        else:
            target_date = None
            
        # Si on a un montant cible mais pas de date cible
        if target_amount and not target_date:
            logger.warning("Missing target date for target amount")
            flash('Veuillez spécifier une date cible pour votre objectif.', 'danger')
            return redirect(url_for('savings'))
            
        # Si on a une date cible mais pas de montant cible
        if target_date and not target_amount:
            logger.warning("Missing target amount for target date")
            flash('Veuillez spécifier un montant cible pour votre objectif.', 'danger')
            return redirect(url_for('savings'))
        
        logger.info(f"Creating savings account: name='{name}', percentage={percentage}, target_amount={target_amount}, target_date={target_date}")
        
        # Créer le compte d'épargne
        savings_account = SavingsAccount(
            name=name,
            percentage=percentage,
            target_amount=target_amount,
            current_amount=0.0,
            target_date=target_date,
            user_id=current_user.id,
            is_active=True,
            is_archived=False
        )
        
        db.session.add(savings_account)
        db.session.commit()
        
        flash('Compte d\'épargne créé avec succès !', 'success')
        logger.info(f"Created savings account {savings_account.id} for user {current_user.id}")
        
    except Exception as e:
        logger.error(f"Error creating savings account: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('Une erreur est survenue lors de la création du compte d\'épargne.', 'danger')
    
    return redirect(url_for('savings'))

@app.route('/update_savings/<int:savings_id>', methods=['POST'])
@login_required
def update_savings(savings_id):
    logger.debug(f"Processing update_savings request for savings_id {savings_id}")
    try:
        savings = SavingsAccount.query.get_or_404(savings_id)
        
        # Vérifier que le compte appartient à l'utilisateur
        if savings.user_id != current_user.id:
            logger.warning(f"Unauthorized access to savings account {savings_id} by user {current_user.id}")
            flash('Accès non autorisé.', 'error')
            return redirect(url_for('savings'))
            
        current_amount = float(request.form.get('current_amount', 0))
        savings.current_amount = current_amount
        
        db.session.commit()
        logger.info(f"Updated savings account {savings_id}: current_amount = {current_amount}")
        
        flash('Compte d\'épargne mis à jour avec succès !', 'success')
    except Exception as e:
        logger.error(f"Error updating savings account: {str(e)}")
        db.session.rollback()
        flash('Une erreur est survenue lors de la mise à jour du compte d\'épargne.', 'error')
    
    return redirect(url_for('savings'))

@app.route('/delete_savings/<int:savings_id>', methods=['POST'])
@login_required
def delete_savings(savings_id):
    logger.debug(f"Processing delete_savings request for savings_id {savings_id}")
    try:
        savings = SavingsAccount.query.get_or_404(savings_id)
        
        # Vérifier que le compte appartient à l'utilisateur
        if savings.user_id != current_user.id:
            logger.warning(f"Unauthorized access to savings account {savings_id} by user {current_user.id}")
            flash('Accès non autorisé.', 'error')
            return redirect(url_for('savings'))
        
        savings.is_active = False
        db.session.commit()
        logger.info(f"Deactivated savings account {savings_id}")
        
        flash('Compte d\'épargne supprimé avec succès !', 'success')
    except Exception as e:
        logger.error(f"Error deleting savings account: {str(e)}")
        db.session.rollback()
        flash('Une erreur est survenue lors de la suppression du compte d\'épargne.', 'error')
    
    return redirect(url_for('savings'))

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    transaction_type = request.form.get('type')
    description = request.form.get('description')
    amount = float(request.form.get('amount'))
    
    transaction = Transaction(
        transaction_type=transaction_type,
        description=description,
        amount=amount,
        user_id=current_user.id
    )
    db.session.add(transaction)
    
    # Si c'est une entrée d'argent, répartir dans les comptes épargne actifs
    if transaction_type == 'income':
        savings_accounts = SavingsAccount.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        for account in savings_accounts:
            savings_amount = (amount * account.percentage) / 100
            if savings_amount > 0:
                account.current_amount += savings_amount
                savings_transaction = SavingsTransaction(
                    amount=savings_amount,
                    description=f"Épargne automatique ({account.percentage}% de {description})",
                    account_id=account.id
                )
                db.session.add(savings_transaction)
    
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.debug("Accessing register route")
    if current_user.is_authenticated:
        logger.debug("User already authenticated, redirecting to index")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        logger.debug("Processing register POST request")
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        phone_country = request.form.get('phone_country')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        currency = request.form.get('currency', 'EUR')

        logger.debug(f"Received registration data: username={username}, email={email}")

        if not all([first_name, last_name, username, email, phone, phone_country, password, confirm_password]):
            logger.warning("Missing required fields")
            flash('Tous les champs sont obligatoires.', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            logger.warning("Passwords do not match")
            flash('Les mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            logger.warning(f"Username {username} already exists")
            flash('Ce nom d\'utilisateur est déjà utilisé.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            logger.warning(f"Email {email} already exists")
            flash('Cette adresse email est déjà utilisée.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(phone=phone).first():
            logger.warning(f"Phone {phone} already exists")
            flash('Ce numéro de téléphone est déjà utilisé.', 'error')
            return redirect(url_for('register'))

        try:
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                phone=phone,
                phone_country=phone_country,
                currency=currency
            )
            user.set_password(password)
            logger.debug(f"Created user object: {user.username}")

            db.session.add(user)
            db.session.commit()
            logger.info(f"Successfully registered user: {user.username}")

            login_user(user)
            flash('Inscription réussie !', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            db.session.rollback()
            flash('Une erreur est survenue lors de l\'inscription.', 'error')
            return redirect(url_for('register'))

    # Pour la méthode GET, on passe today pour le template
    return render_template('register.html', 
                         today=date.today(),
                         total_income=0,
                         total_expenses=0,
                         monthly_income=0,
                         monthly_expenses=0,
                         balance=0,
                         available_balance=0,
                         total_savings=0,
                         savings_accounts=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    logger.debug("Accessing login route")
    if current_user.is_authenticated:
        logger.debug("User already authenticated, redirecting to index")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        logger.debug("Processing login POST request")
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        logger.debug(f"Found user: {user is not None}")
        
        if user and user.check_password(password):
            logger.debug("Password check successful")
            login_user(user)
            flash('Connexion réussie !', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            logger.debug("Invalid username or password")
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
    
    logger.debug("Rendering login template")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté.', 'success')
    return redirect(url_for('login'))

@app.route('/settings')
@login_required
def settings():
    history = AccountHistory.query.filter_by(user_id=current_user.id).order_by(AccountHistory.timestamp.desc()).all()
    archived_accounts = SavingsAccount.query.filter_by(user_id=current_user.id, is_archived=True).all()
    return render_template('settings.html', history=history, archived_accounts=archived_accounts)

@app.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    try:
        # Récupération des données du formulaire
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        phone_country = request.form.get('phone_country')
        currency = request.form.get('currency')

        # Vérification des champs obligatoires
        if not all([first_name, last_name, email, phone, phone_country, currency]):
            flash('Tous les champs sont obligatoires.', 'error')
            return redirect(url_for('settings'))

        # Vérification que l'email n'est pas déjà utilisé par un autre utilisateur
        existing_user = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_user:
            flash('Cette adresse email est déjà utilisée.', 'error')
            return redirect(url_for('settings'))

        # Vérification que le numéro de téléphone n'est pas déjà utilisé par un autre utilisateur
        existing_user = User.query.filter(User.phone == phone, User.id != current_user.id).first()
        if existing_user:
            flash('Ce numéro de téléphone est déjà utilisé.', 'error')
            return redirect(url_for('settings'))

        # Enregistrement des modifications
        changes = []
        if current_user.first_name != first_name:
            changes.append(f"Prénom modifié de '{current_user.first_name}' à '{first_name}'")
            current_user.first_name = first_name

        if current_user.last_name != last_name:
            changes.append(f"Nom modifié de '{current_user.last_name}' à '{last_name}'")
            current_user.last_name = last_name

        if current_user.email != email:
            changes.append(f"Email modifié de '{current_user.email}' à '{email}'")
            current_user.email = email

        if current_user.phone != phone or current_user.phone_country != phone_country:
            changes.append(f"Téléphone modifié de '{current_user.phone}' à '{phone}'")
            current_user.phone = phone
            current_user.phone_country = phone_country

        if current_user.currency != currency:
            changes.append(f"Devise modifiée de '{current_user.currency}' à '{currency}'")
            current_user.currency = currency

        if changes:
            details = '. '.join(changes)
            history_entry = AccountHistory(
                user_id=current_user.id,
                action='update_settings',
                details=details
            )
            db.session.add(history_entry)
            db.session.commit()
            flash('Vos paramètres ont été mis à jour avec succès.', 'success')
        else:
            flash('Aucune modification n\'a été effectuée.', 'info')

        return redirect(url_for('settings'))

    except Exception as e:
        db.session.rollback()
        flash('Une erreur est survenue lors de la mise à jour de vos paramètres.', 'error')
        return redirect(url_for('settings'))

@app.route('/export_transactions')
@login_required
def export_transactions():
    user = User.query.get(session['user_id'])
    transactions = Transaction.query.filter_by(user_id=session['user_id']).order_by(Transaction.transaction_date.desc()).all()
    
    # Création du DataFrame pour les transactions
    transactions_data = []
    for t in transactions:
        transactions_data.append({
            'Date': t.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'Type': 'Entrée' if t.transaction_type == 'income' else 'Dépense',
            'Description': t.description,
            'Montant': t.amount,
            'Devise': user.currency
        })
    
    df_transactions = pd.DataFrame(transactions_data)
    
    # Création du DataFrame pour les comptes épargne
    savings_accounts = SavingsAccount.query.filter_by(user_id=session['user_id']).all()
    savings_data = []
    for account in savings_accounts:
        savings_data.append({
            'Nom du compte': account.name,
            'Solde': account.current_amount,
            'Pourcentage': f"{account.percentage}%",
            'Objectif': account.target_amount if account.target_amount else 'Non défini',
            'Date limite': account.target_date.strftime('%Y-%m-%d') if account.target_date else 'Non définie',
            'Statut': 'Actif' if account.is_active else 'Inactif',
            'Devise': user.currency
        })
    
    df_savings = pd.DataFrame(savings_data)
    
    # Création du fichier Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Onglet Résumé
        summary_data = {
            'Métrique': ['Solde total', 'Total entrées', 'Total dépenses', 'Total épargne', 'Montant disponible'],
            'Montant': [
                sum(t.amount for t in transactions if t.transaction_type == 'income') - sum(t.amount for t in transactions if t.transaction_type == 'expense'),
                sum(t.amount for t in transactions if t.transaction_type == 'income'),
                sum(t.amount for t in transactions if t.transaction_type == 'expense'),
                sum(account.current_amount for account in savings_accounts),
                sum(t.amount for t in transactions if t.transaction_type == 'income') - 
                sum(t.amount for t in transactions if t.transaction_type == 'expense') - 
                sum(account.current_amount for account in savings_accounts)
            ],
            'Devise': [user.currency] * 5
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Résumé', index=False)
        
        # Onglet Transactions
        df_transactions.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Onglet Comptes Épargne
        df_savings.to_excel(writer, sheet_name='Comptes Épargne', index=False)
        
        # Mise en forme
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                length = max(len(str(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'rapport_budget_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/delete_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def delete_transaction(transaction_id):
    logger.debug(f"Processing delete_transaction request for transaction_id {transaction_id}")
    try:
        transaction = Transaction.query.get_or_404(transaction_id)
        
        # Vérifier que la transaction appartient à l'utilisateur
        if transaction.user_id != current_user.id:
            logger.warning(f"Unauthorized access to transaction {transaction_id} by user {current_user.id}")
            flash('Accès non autorisé.', 'error')
            return redirect(url_for('index'))
        
        db.session.delete(transaction)
        db.session.commit()
        logger.info(f"Deleted transaction {transaction_id}")
        
        flash('Transaction supprimée avec succès !', 'success')
    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        db.session.rollback()
        flash('Une erreur est survenue lors de la suppression de la transaction.', 'error')
    
    return redirect(url_for('index'))

@app.route('/savings/toggle/<int:savings_id>', methods=['POST'])
@login_required
def toggle_savings(savings_id):
    savings = SavingsAccount.query.get_or_404(savings_id)
    if savings.user_id != current_user.id:
        abort(403)
    
    savings.is_active = not savings.is_active
    db.session.commit()
    
    flash(f"Le compte d'épargne a été {'activé' if savings.is_active else 'désactivé'}", 'success')
    return redirect(url_for('savings'))

@app.route('/savings/archive/<int:savings_id>', methods=['POST'])
@login_required
def archive_savings(savings_id):
    savings = SavingsAccount.query.get_or_404(savings_id)
    if savings.user_id != current_user.id:
        abort(403)
    
    if savings.is_active:
        flash("Impossible d'archiver un compte actif. Désactivez-le d'abord.", 'danger')
    else:
        savings.is_archived = True
        db.session.commit()
        flash("Le compte d'épargne a été archivé", 'success')
    
    return redirect(url_for('savings'))

@app.route('/add_to_savings/<int:savings_id>', methods=['POST'])
@login_required
def add_to_savings(savings_id):
    try:
        logger.debug(f"Tentative d'ajout d'argent au compte {savings_id}")
        account = SavingsAccount.query.get_or_404(savings_id)
        logger.debug(f"Compte trouvé: {account.name}")
        
        # Vérifier que le compte appartient à l'utilisateur
        if account.user_id != current_user.id:
            logger.warning(f"Tentative d'accès non autorisé au compte {savings_id} par l'utilisateur {current_user.id}")
            flash("Vous n'avez pas accès à ce compte d'épargne.", 'danger')
            return redirect(url_for('savings'))
            
        # Récupérer le montant à ajouter
        amount_str = request.form.get('amount', '0')
        logger.debug(f"Montant reçu (brut): {amount_str}")
        
        # Convertir la chaîne en nombre en gérant le format français (virgule)
        amount_str = amount_str.replace(',', '.')
        amount = float(amount_str)
        logger.debug(f"Montant converti: {amount}")
        
        if amount <= 0:
            logger.warning(f"Tentative d'ajout d'un montant invalide: {amount}")
            flash("Le montant doit être supérieur à 0.", 'warning')
            return redirect(url_for('savings'))
            
        # Ajouter le montant au compte
        previous_amount = account.current_amount
        account.current_amount += amount
        logger.debug(f"Nouveau montant: {account.current_amount} (précédent: {previous_amount})")
        
        # Mettre à jour le pourcentage
        if account.target_amount and account.target_amount > 0:
            account.percentage = min((account.current_amount / account.target_amount) * 100, 100)
            logger.debug(f"Nouveau pourcentage: {account.percentage}%")
            
            # Vérifier si l'objectif est atteint
            if account.current_amount >= account.target_amount:
                account.is_active = False
                logger.info(f"Compte épargne {account.name} désactivé car l'objectif est atteint")
                flash(f"Félicitations ! L'objectif du compte '{account.name}' est atteint. Le compte a été automatiquement désactivé.", 'success')
            
        # Créer une transaction pour l'historique
        transaction = Transaction(
            user_id=current_user.id,
            amount=amount,
            transaction_type="SAVINGS_DEPOSIT",
            description=f"Dépôt manuel sur le compte épargne '{account.name}'",
            category="Épargne",
            transaction_date=datetime.now(),
            savings_account_id=account.id
        )
        logger.debug(f"Création de la transaction: {transaction}")
        db.session.add(transaction)
        
        db.session.commit()
        if not account.is_active:  # Si le compte vient d'être désactivé, on ne montre pas le message d'ajout
            logger.info(f"Ajout réussi de {amount:.2f} € au compte {account.name} et objectif atteint")
        else:
            flash(f"Ajout de {amount:.2f} € à l'épargne '{account.name}' effectué avec succès.", 'success')
            logger.info(f"Ajout réussi de {amount:.2f} € au compte {account.name}")
        
    except ValueError as e:
        logger.error(f"Erreur de conversion du montant: {str(e)}", exc_info=True)
        flash("Le montant saisi n'est pas valide.", 'danger')
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout à l'épargne: {str(e)}", exc_info=True)
        flash("Une erreur s'est produite lors de l'ajout à l'épargne.", 'danger')
        db.session.rollback()
        
    return redirect(url_for('savings'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 4999)))
        logger.info("Base de données existante supprimée")
    
    with app.app_context():
        # Supprimer toutes les tables existantes
        db.drop_all()
        logger.info("Toutes les tables ont été supprimées")
        
        # Créer toutes les tables
        db.create_all()
        logger.info("Nouvelles tables créées")
        
        # Créer un utilisateur de test
        test_user = User(
            username='test',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            phone='1234567890',
            phone_country='FR',
            currency='EUR'
        )
        test_user.set_password('test123')
        db.session.add(test_user)
        
        # Créer un compte d'épargne de test
        test_savings = SavingsAccount(
            name='Épargne Vacances',
            percentage=10.0,
            current_amount=1000.0,
            target_amount=5000.0,
            target_date=date(2025, 12, 31),
            user_id=1,
            is_active=True,
            is_archived=False
        )
        db.session.add(test_savings)
        
        db.session.commit()
        logger.info("Utilisateur et compte d'épargne de test créés")
        
        # Vérifier la structure de la table User
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('user')
        logger.info("Structure de la table User:")
        for column in columns:
            logger.info(f"- {column['name']}: {column['type']}")
    
    app.run(host='127.0.0.1', port=4964, debug=True)
