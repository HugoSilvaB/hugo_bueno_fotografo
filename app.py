import os
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_from_directory, flash, session, abort
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOAD_FOLDER = os.path.join(STATIC_DIR, 'uploads')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'troque_essa_chave')

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Helpers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.context_processor
def inject_site_name():
    return {'site_name': 'Hugo Fotógrafo'}

# ---- ROTAS ----

@app.route('/')
def index():
    q = request.args.get('q', '').strip().lower()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    albums = []
    for d in os.listdir(app.config['UPLOAD_FOLDER']):
        album_path = os.path.join(app.config['UPLOAD_FOLDER'], d)
        if os.path.isdir(album_path):
            # procura capa
            capa_url = None
            for ext in app.config['ALLOWED_EXTENSIONS']:
                candidate = os.path.join(album_path, f'capa.{ext}')
                if os.path.exists(candidate):
                    capa_url = url_for('uploaded_file', album=d, filename=f'capa.{ext}')
                    break
            if not capa_url:
                capa_url = url_for('static', filename='default_capa.jpg')

            albums.append({
                'nome': d,
                'capa': capa_url
            })

    if q:
        albums = [a for a in albums if q in a['nome'].lower()]

    albums.sort(key=lambda x: x['nome'].lower())
    return render_template('home.html', albums=albums, query=q)

@app.route('/album/<name>')
def album(name):
    album_path = os.path.join(app.config['UPLOAD_FOLDER'], name)
    if not os.path.exists(album_path):
        abort(404)
    photos = [f for f in os.listdir(album_path) if allowed_file(f) and not f.startswith('capa')]
    photos.sort()
    return render_template('album.html', album=name, photos=photos)

@app.route('/uploads/<album>/<filename>')
def uploaded_file(album, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], album), filename)

# --- ADMIN ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if pwd == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Senha incorreta', 'error')
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin'))

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    albums = [d for d in os.listdir(app.config['UPLOAD_FOLDER'])
              if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], d))]
    albums.sort()
    return render_template('admin_dashboard.html', albums=albums)

@app.route('/admin/create_album', methods=['POST'])
def create_album():
    if not session.get('admin'):
        abort(403)
    name = secure_filename(request.form.get('album_name', 'album'))
    if name.strip() == '':
        name = 'album'
    path = os.path.join(app.config['UPLOAD_FOLDER'], name)
    os.makedirs(path, exist_ok=True)
    flash(f'Álbum "{name}" criado.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload', methods=['POST'])
def admin_upload():
    if not session.get('admin'):
        abort(403)
    album = secure_filename(request.form.get('album_select') or request.form.get('album_name') or 'album')
    if album.strip() == '':
        album = 'album'
    path = os.path.join(app.config['UPLOAD_FOLDER'], album)
    os.makedirs(path, exist_ok=True)
    files = request.files.getlist('photos')
    saved = 0
    for f in files:
        if f and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            dest = os.path.join(path, filename)
            f.save(dest)
            saved += 1
    flash(f'{saved} fotos salvas no álbum {album}.', 'info')
    return redirect(url_for('admin_dashboard'))

# --- Upload de capa ---
@app.route('/admin/upload_capa', methods=['POST'])
def upload_capa():
    if not session.get('admin'):
        abort(403)

    album = secure_filename(request.form.get('album'))
    file = request.files.get('capa')

    if not album or not file:
        flash('Selecione o álbum e o arquivo da capa.', 'error')
        return redirect(url_for('admin_dashboard'))

    if not allowed_file(file.filename):
        flash('Formato de imagem não permitido.', 'error')
        return redirect(url_for('admin_dashboard'))

    album_path = os.path.join(app.config['UPLOAD_FOLDER'], album)
    os.makedirs(album_path, exist_ok=True)

    # remove capas antigas
    for ext in app.config['ALLOWED_EXTENSIONS']:
        old_capa = os.path.join(album_path, f'capa.{ext}')
        if os.path.exists(old_capa):
            os.remove(old_capa)

    ext = file.filename.rsplit('.', 1)[1].lower()
    capa_path = os.path.join(album_path, f'capa.{ext}')
    file.save(capa_path)

    flash(f'Capa do álbum "{album}" atualizada com sucesso!', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_photo', methods=['POST'])
def delete_photo():
    if not session.get('admin'):
        abort(403)
    album = secure_filename(request.form.get('album'))
    filename = secure_filename(request.form.get('filename'))
    path = os.path.join(app.config['UPLOAD_FOLDER'], album, filename)
    if os.path.exists(path):
        os.remove(path)
        flash('Foto removida.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Logout efetuado.', 'info')
    return redirect(url_for('admin'))

import shutil  # já no topo do arquivo

@app.route('/admin/delete_album', methods=['POST'])
def delete_album():
    if not session.get('admin'):
        abort(403)
    album = secure_filename(request.form.get('album'))
    path = os.path.join(app.config['UPLOAD_FOLDER'], album)
    if os.path.exists(path):
        shutil.rmtree(path)  # exclui o álbum inteiro
        flash(f'Álbum "{album}" excluído.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/rename_album', methods=['POST'])
def rename_album():
    if not session.get('admin'):
        abort(403)
    old_name = secure_filename(request.form.get('old_name'))
    new_name = secure_filename(request.form.get('new_name')).strip()
    if not new_name:
        flash('O novo nome não pode estar vazio.', 'error')
        return redirect(url_for('admin_dashboard'))

    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_name)
    new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_name)

    if os.path.exists(old_path):
        if os.path.exists(new_path):
            flash(f'Já existe um álbum com o nome "{new_name}".', 'error')
        else:
            os.rename(old_path, new_path)
            flash(f'Álbum "{old_name}" renomeado para "{new_name}".', 'info')
    else:
        flash('Álbum não encontrado.', 'error')
    return redirect(url_for('admin_dashboard'))



# --- Rodar ---
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='127.0.0.1', port=5050)
