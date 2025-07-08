import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURACIÓN INICIAL ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'una-llave-secreta-muy-dificil-de-adivinar'
db_url = os.environ.get("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELO DE LA BASE DE DATOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS DE LA APLICACIÓN ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('biblioteca'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('biblioteca'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('biblioteca'))
        flash('Email o contraseña inválidos.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('biblioteca'))
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash('Este correo electrónico ya ha sido registrado.')
            return redirect(url_for('register'))
        
        new_user = User(
            nombre=request.form['nombre'],
            apellido=request.form['apellido'],
            email=request.form['email']
        )
        new_user.set_password(request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        
        try:
            remitente = "tu_correo_de_envio@gmail.com"  # <<< ¡TU CORREO DE GMAIL!
            password = "tu_contraseña_de_aplicacion"    # <<< ¡TU CONTRASEÑA DE APP!
            
            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['To'] = new_user.email
            msg['Subject'] = "¡Cuenta Creada Exitosamente!"
            cuerpo = f"Hola {new_user.nombre},\n\nTu cuenta ha sido creada en nuestra plataforma. Ahora puedes iniciar sesión.\n\nGracias."
            msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))
            
            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.starttls()
                smtp.login(remitente, password)
                smtp.sendmail(remitente, new_user.email, msg.as_string())
        except Exception as e:
            print(f"Error enviando correo de confirmación: {e}")
            
        flash('¡Cuenta creada! Por favor, inicia sesión.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- RUTA DE LA BIBLIOTECA (ACTUALIZADA) ---
@app.route('/biblioteca')
@login_required
def biblioteca():
    lista_de_libros = [
        {
            "titulo": "Libro de Plataformas Digitales",
            "descripcion": "Contenido del curso y material de estudio.",
            "archivo": "PlataformasDigitales.pdf"  # <-- Nombre actualizado de tu archivo
        }
        # Si añades más PDFs, puedes agregarlos aquí
    ]
    return render_template('biblioteca.html', libros=lista_de_libros)

# --- CREAR LA BASE DE DATOS ---
with app.app_context():
    db.create_all()
