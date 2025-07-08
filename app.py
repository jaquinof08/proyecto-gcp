# --- app.py (Versión Final y Completa) ---

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime
# Nuevas importaciones para SendGrid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --- CONFIGURACIÓN INICIAL ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'una-llave-secreta-muy-dificil-de-adivinar'
db_url = os.environ.get("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."

# --- MODELOS DE LA BASE DE DATOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_filename = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/')
def index():
    return redirect(url_for('register'))

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
        try:
            new_user = User(
                nombre=request.form['nombre'],
                apellido=request.form['apellido'],
                email=request.form['email']
            )
            new_user.set_password(request.form['password'])
            db.session.add(new_user)
            db.session.commit()

            # --- LÓGICA DE CORREO ACTUALIZADA CON SENDGRID ---
            try:
                message = Mail(
                    from_email='tu_correo_verificado@example.com',  # <<< TU CORREO VERIFICADO EN SENDGRID
                    to_emails=new_user.email,
                    subject='¡Cuenta Creada Exitosamente en la Plataforma!',
                    html_content=f'Hola {new_user.nombre},<br><br>Tu cuenta ha sido creada. Ya puedes iniciar sesión.'
                )
                sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                response = sg.send(message)
                print(f"Correo de bienvenida enviado, código: {response.status_code}")
            except Exception as e:
                print(f"Error enviando correo con SendGrid: {e}")

            flash('¡Cuenta creada! Por favor, inicia sesión.')
            return redirect(url_for('login'))
        
        except IntegrityError:
            db.session.rollback()
            flash('Este correo electrónico ya ha sido registrado.')
            return redirect(url_for('register'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- RUTAS DE LA APLICACIÓN ---
@app.route('/biblioteca')
@login_required
def biblioteca():
    lista_de_libros = [{"titulo": "Libro de Plataformas Digitales", "descripcion": "Contenido del curso y material de estudio.", "archivo": "PlataformasDigitales.pdf"}]
    comentarios = Comment.query.order_by(Comment.timestamp.desc()).all()
    return render_template('biblioteca.html', libros=lista_de_libros, comentarios=comentarios)

@app.route('/agregar_comentario', methods=['POST'])
@login_required
def agregar_comentario():
    contenido = request.form.get('contenido')
    nombre_libro = request.form.get('nombre_libro')
    if contenido and nombre_libro:
        nuevo_comentario = Comment(content=contenido, user_id=current_user.id, book_filename=nombre_libro)
        db.session.add(nuevo_comentario)
        db.session.commit()
        flash('Comentario añadido.')
    return redirect(url_for('biblioteca'))

@app.route('/enviar_correo', methods=['GET', 'POST'])
@login_required
def enviar_correo():
    if request.method == 'POST':
        destinatario = request.form['destinatario']
        asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']
        try:
            message = Mail(
                from_email='tu_correo_verificado@example.com', # <<< TU CORREO VERIFICADO EN SENDGRID
                to_emails=destinatario,
                subject=asunto,
                html_content=f"<i>Este correo fue enviado desde la plataforma por {current_user.nombre}.</i><br><br>{cuerpo}"
            )
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
            response = sg.send(message)
            flash('Correo enviado exitosamente.')
        except Exception as e:
            print(f"Error al enviar correo: {e}")
            flash('Error al enviar el correo.')
    return render_template('enviar_correo.html')

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()
