from functools import wraps
from secrets import token_hex, compare_digest
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from src.models.model_usuario import Usuario

auth_c = Blueprint('auth_c', __name__, template_folder='../templates')

USUARIO_LONGITUD = (3, 80)
PASSWORD_LONGITUD_MINIMA = 8


def login_required(vista):
  @wraps(vista)
  def envoltura(*args, **kwargs):
    if not session.get('user'):
      flash('Inicia sesión para continuar.', 'warning')
      return redirect(url_for('auth_c.login'))
    return vista(*args, **kwargs)
  return envoltura


def _csrf_valido():
  return bool(session.get('csrf_token')) and compare_digest(session.get('csrf_token', ''), request.form.get('csrf_token', ''))


@auth_c.route('/login', methods=['GET', 'POST'])
def login():
  session.setdefault('csrf_token', token_hex(32))
  if request.method == 'POST':
    if not _csrf_valido():
      flash('El formulario expiró. Recarga la página e inténtalo nuevamente.', 'danger')
      return redirect(url_for('auth_c.login'))
    user = request.form.get('user', '').strip()
    password = request.form.get('password', '')
    try:
      if Usuario.verificar_credenciales(user, password):
        csrf_token = session.get('csrf_token')
        session.clear()
        session['user'] = user
        session['csrf_token'] = csrf_token
        session.permanent = True
        return redirect(url_for('productos_c.obtener_productos'))
      flash('Usuario o contraseña incorrectos.', 'danger')
    except Exception:
      current_app.logger.exception('No se pudo validar el inicio de sesión')
      flash('No se pudo iniciar sesión. Intenta de nuevo.', 'danger')
  return render_template('login.html')


@auth_c.route('/registro', methods=['GET', 'POST'])
def registro():
  session.setdefault('csrf_token', token_hex(32))
  if request.method == 'POST':
    if not _csrf_valido():
      flash('El formulario expiró. Recarga la página e inténtalo nuevamente.', 'danger')
      return redirect(url_for('auth_c.registro'))
    user = request.form.get('user', '').strip()
    password = request.form.get('password', '')
    largo_min, largo_max = USUARIO_LONGITUD
    try:
      if not (largo_min <= len(user) <= largo_max):
        raise ValueError(f'El usuario debe tener entre {largo_min} y {largo_max} caracteres.')
      if len(password) < PASSWORD_LONGITUD_MINIMA:
        raise ValueError(f'La contraseña debe tener al menos {PASSWORD_LONGITUD_MINIMA} caracteres.')
      Usuario.crear_usuario(user, password)
      flash('Cuenta creada con éxito. Ya puedes iniciar sesión.', 'success')
      return redirect(url_for('auth_c.login'))
    except ValueError as error:
      flash(str(error), 'warning')
    except Exception:
      current_app.logger.exception('No se pudo crear el usuario')
      flash('No se pudo crear la cuenta. Intenta de nuevo.', 'danger')
  return render_template('registro.html')


@auth_c.route('/logout', methods=['POST'])
def logout():
  if _csrf_valido():
    session.clear()
    flash('Sesión cerrada.', 'success')
  return redirect(url_for('auth_c.login'))
