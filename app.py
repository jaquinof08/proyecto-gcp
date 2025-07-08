# --- app.py (Versión Final y Completa) ---

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy.exc import IntegrityError
from datetime import datetime

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

# Modelo para los Usuarios
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Límite aumentado
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Nuevo Modelo para los Comentarios
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
        try:
            new_user = User(
                nombre=request.form['nombre'],
                apellido=request.form['apellido'],
                email=request.form['email']
            )
            new_user.set_password(request.form['password'])
            db.session.add(new_user)
            db.session.commit()

            # Enviar correo de confirmación
            try:
                remitente = "tu_correo_de_envio@gmail.com"  # <<< ¡TU CORREO DE GMAIL!
                password = "tu_contraseña_de_aplicacion"    # <<< ¡TU CONTRASEÑA DE APP!
                
                msg = MIMEMultipart()
                msg['From'] = remitente
                msg['To'] = new_user.email
                msg['Subject'] = "¡Cuenta Creada Exitosamente en la Plataforma!"
                cuerpo = f"Hola {new_user.nombre},\n\nTu cuenta ha sido creada exitosamente. Ya puedes iniciar sesión con tu correo y contraseña.\n\n¡Bienvenido!"
                msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))
                
                with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                    smtp.starttls()
                    smtp.login(remitente, password)
                    smtp.sendmail(remitente, new_user.email, msg.as_string())
            except Exception as e:
                print(f"Error enviando correo de confirmación: {e}")

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
    lista_de_libros = [
        {
            "titulo": "Libro de Plataformas Digitales",
            "descripcion": "Contenido del curso y material de estudio.",
            "archivo": "PlataformasDigitales.pdf"
        }
    ]
    # Obtener todos los comentarios de la base de datos
    comentarios = Comment.query.order_by(Comment.timestamp.desc()).all()
    return render_template('biblioteca.html', libros=lista_de_libros, comentarios=comentarios)

@app.route('/agregar_comentario', methods=['POST'])
@login_required
def agregar_comentario():
    contenido = request.form.get('contenido')
    nombre_libro = request.form.get('nombre_libro')
    if contenido and nombre_libro:
        nuevo_comentario = Comment(
            content=contenido,
            user_id=current_user.id,
            book_filename=nombre_libro
        )
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
            remitente = "tu_correo_de_envio@gmail.com"  # <<< ¡TU CORREO DE GMAIL!
            password = "tu_contraseña_de_aplicacion"    # <<< ¡TU CONTRASEÑA DE APP!
            
            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            cuerpo_completo = f"Este correo fue enviado desde la plataforma por {current_user.nombre} ({current_user.email}).\n\n---\n\n{cuerpo}"
            msg.attach(MIMEText(cuerpo_completo, 'plain', 'utf-8'))
            
            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.starttls()
                smtp.login(remitente, password)
                smtp.sendmail(remitente, destinatario, msg.as_string())
            
            flash('Correo enviado exitosamente.')
        except Exception as e:
            print(f"Error al enviar correo: {e}")
            flash('Error al enviar el correo. Revisa las credenciales o intenta más tarde.')
            
        return redirect(url_for('enviar_correo'))
        
    return render_template('enviar_correo.html')

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()

```html
<!-- templates/layout.html (Actualizado con nueva navegación) -->
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Proyecto Final{% endblock %}</title>
    <style>
        body { background-color: #1a1a1a; color: #e0e0e0; font-family: sans-serif; }
        .navbar { background-color: #121212; padding: 10px 20px; text-align: center; border-bottom: 1px solid #333; }
        .navbar a { color: #03dac6; text-decoration: none; margin: 0 15px; font-weight: bold; }
        .container { max-width: 800px; margin: 40px auto; padding: 25px; border: 1px solid #333; border-radius: 12px; background-color: #2c2c2c;}
        h2 { text-align: center; color: #ffffff; }
        label { display: block; margin-top: 20px; font-weight: bold; color: #bb86fc; }
        input, textarea { width: 100%; padding: 12px; margin-top: 8px; box-sizing: border-box; border-radius: 6px; border: 1px solid #444; background-color: #1a1a1a; color: #e0e0e0; font-size: 16px; }
        button { display: block; width: 100%; background-color: #bb86fc; color: #121212; padding: 12px; border: none; border-radius: 6px; cursor: pointer; margin-top: 25px; font-size: 16px; font-weight: bold;}
        a { color: #03dac6; }
        .flash { padding: 15px; margin-bottom: 20px; border-radius: 4px; color: #ffffff; background-color: #03dac6; text-align: center;}
    </style>
</head>
<body>
    {% if current_user.is_authenticated %}
    <div class="navbar">
        <a href="{{ url_for('biblioteca') }}">Biblioteca</a>
        <a href="{{ url_for('enviar_correo') }}">Enviar Correo</a>
        <a href="{{ url_for('logout') }}">Cerrar Sesión</a>
    </div>
    {% endif %}
    <div class="container">
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="flash">
              {{ messages[0] }}
            </div>
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```html
<!-- templates/biblioteca.html (Actualizado con comentarios) -->
{% extends "layout.html" %}
{% block title %}Biblioteca{% endblock %}
{% block content %}
    <h2>📚 Biblioteca de Libros</h2>
    <p>Bienvenido, {{ current_user.nombre }}!</p>
    
    {% for libro in libros %}
    <div style="border: 1px solid #444; padding: 20px; margin-top: 20px; border-radius: 8px;">
        <h3>{{ libro.titulo }}</h3>
        <p>{{ libro.descripcion }}</p>
        <a href="/static/pdfs/{{ libro.archivo }}" target="_blank">Ver PDF</a>
        
        <hr style="border-color: #444; margin: 20px 0;">

        <h4>Comentarios</h4>
        <!-- Formulario para añadir un nuevo comentario -->
        <form action="{{ url_for('agregar_comentario') }}" method="post">
            <input type="hidden" name="nombre_libro" value="{{ libro.archivo }}">
            <textarea name="contenido" rows="3" placeholder="Escribe un comentario..." required></textarea>
            <button type="submit" style="width: auto; padding: 8px 15px; margin-top: 10px;">Comentar</button>
        </form>

        <!-- Lista de comentarios existentes -->
        <div style="margin-top: 20px;">
            {% for comentario in comentarios if comentario.book_filename == libro.archivo %}
                <div style="border-top: 1px solid #444; padding-top: 10px; margin-top: 10px;">
                    <p><strong>{{ comentario.author.nombre }}:</strong> {{ comentario.content }}</p>
                    <small style="color: #888;">{{ comentario.timestamp.strftime('%d-%m-%Y %H:%M') }}</small>
                </div>
            {% else %}
                <p>No hay comentarios para este libro. ¡Sé el primero!</p>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
{% endblock %}
```html
<!-- templates/enviar_correo.html (Nuevo archivo) -->
{% extends "layout.html" %}
{% block title %}Enviar Correo{% endblock %}
{% block content %}
    <h2>✉️ Enviar un Correo</h2>
    <p>Desde aquí puedes enviar un correo a cualquier dirección de Gmail.</p>
    
    <form method="post">
        <label for="destinatario">Para (Email):</label>
        <input type="email" id="destinatario" name="destinatario" required>
        
        <label for="asunto">Asunto:</label>
        <input type="text" id="asunto" name="asunto" required>
        
        <label for="cuerpo">Mensaje:</label>
        <textarea id="cuerpo" name="cuerpo" rows="6" required></textarea>
        
        <button type="submit">Enviar Correo</button>
    </form>
{% endblock %}
