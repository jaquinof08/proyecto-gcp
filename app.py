# --- app.py (Versión con Gestión de Libros para Admin) ---

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename # Para subidas de archivos seguras
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from functools import wraps

# --- CONFIGURACIÓN DE SUBIDA DE ARCHIVOS ---
UPLOAD_FOLDER = 'static/pdfs'
ALLOWED_EXTENSIONS = {'pdf'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- LÓGICA PARA CARGAR SECRETOS ---
if os.environ.get('GAE_ENV', '').startswith('standard'):
    try:
        from google.cloud import secretmanager
        def access_secret_version(project_id, secret_id, version_id="latest"):
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        project_id = "proyecto-de-plataformas-465221"
        sendgrid_api_key = access_secret_version(project_id, "SENDGRID_API_KEY")
        os.environ['SENDGRID_API_KEY'] = sendgrid_api_key
    except Exception as e:
        print(f"FALLO CRÍTICO al cargar clave de API: {e}")

# --- CONFIGURACIÓN INICIAL ---
app.config['SECRET_KEY'] = 'una-llave-secreta-muy-dificil-de-adivinar'
db_url = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."

# --- MODELOS DE LA BASE DE DATOS (CON ROL Y LIBROS) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(80), nullable=False, default='user')
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Nuevo Modelo para los Libros
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(200), nullable=False, unique=True)
    comments = db.relationship('Comment', backref='book', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso no autorizado. Se requieren permisos de administrador.')
            return redirect(url_for('biblioteca'))
        return f(*args, **kwargs)
    return decorated_function

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
            # Asignar rol de admin si es el primer usuario
            if User.query.count() == 0:
                new_user.role = 'admin'
            new_user.set_password(request.form['password'])
            db.session.add(new_user)
            db.session.commit()
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
    # AHORA LEE LOS LIBROS DESDE LA BASE DE DATOS
    libros = Book.query.all()
    return render_template('biblioteca.html', libros=libros)

@app.route('/agregar_comentario/<int:book_id>', methods=['POST'])
@login_required
def agregar_comentario(book_id):
    contenido = request.form.get('contenido')
    if contenido:
        # AHORA GUARDA EL COMENTARIO CON EL ID DEL LIBRO
        nuevo_comentario = Comment(content=contenido, user_id=current_user.id, book_id=book_id)
        db.session.add(nuevo_comentario)
        db.session.commit()
        flash('Comentario añadido.')
    return redirect(url_for('biblioteca'))

# --- RUTAS DE ADMINISTRACIÓN ---
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    comments = Comment.query.all()
    books = Book.query.all()
    return render_template('admin_dashboard.html', users=users, comments=comments, books=books)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/upload_pdf', methods=['POST'])
@login_required
@admin_required
def upload_pdf():
    if 'file' not in request.files:
        flash('No se encontró el archivo')
        return redirect(url_for('admin_dashboard'))
    file = request.files['file']
    if file.filename == '':
        flash('No se seleccionó ningún archivo')
        return redirect(url_for('admin_dashboard'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_book = Book(
            title=request.form['title'],
            description=request.form['description'],
            filename=filename
        )
        db.session.add(new_book)
        db.session.commit()
        flash('Libro subido y añadido a la biblioteca exitosamente.')
    else:
        flash('Formato de archivo no permitido. Solo se aceptan PDFs.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_book/<int:book_id>', methods=['POST'])
@login_required
@admin_required
def delete_book(book_id):
    book_to_delete = Book.query.get_or_404(book_id)
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], book_to_delete.filename))
    except OSError as e:
        print(f"Error borrando archivo físico: {e}")
    db.session.delete(book_to_delete)
    db.session.commit()
    flash('Libro eliminado exitosamente.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
@admin_required
def delete_comment(comment_id):
    comment_to_delete = Comment.query.get_or_404(comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    flash('Comentario eliminado exitosamente.')
    return redirect(url_for('admin_dashboard'))
# --- RUTA PARA ENVÍO DE CORREOS ---
@app.route('/enviar_correo', methods=['GET', 'POST'])
@login_required
def enviar_correo():
    if request.method == 'POST':
        try:
            # Obtener datos del formulario (ajustado para tu template)
            destinatario = request.form['destinatario']
            asunto = request.form['asunto']
            cuerpo = request.form['cuerpo']  # Tu template usa 'cuerpo' no 'contenido'
            
            # Crear el mensaje
            message = Mail(
                from_email='noreply@proyectosgpc.xyz',  # Cambia por tu email verificado en SendGrid
                to_emails=destinatario,
                subject=asunto,
                html_content=f"""
                <html>
                <body>
                    <h2>Mensaje desde la Plataforma Educativa</h2>
                    <p><strong>Enviado por:</strong> {current_user.nombre} {current_user.apellido} ({current_user.email})</p>
                    <hr>
                    <p>{cuerpo}</p>
                </body>
                </html>
                """
            )
            
            # Enviar el correo
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
            response = sg.send(message)
            
            flash('Correo enviado exitosamente.')
            return redirect(url_for('biblioteca'))
            
        except Exception as e:
            flash(f'Error al enviar el correo: {str(e)}')
    
    return render_template('enviar_correo.html')

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()
