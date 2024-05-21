from flask import Flask, request, render_template, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import numpy as np
import shutil

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    # 临床四诊信息
    sizhen = db.Column(db.String(1000), nullable=False)
    # 中医体质辨识
    tizhi = db.Column(db.String(1000), nullable=False)
    files = db.relationship('File', backref='user', cascade="all, delete-orphan")

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    filetype = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/')
def index():
    users = User.query.all()
    return render_template('index.html', users=users)

@app.route('/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        sizhen = request.form['sizhen']
        tizhi = request.form['tizhi']
        files = request.files.getlist('files')
        print(files)
        filetypes = request.form.getlist('filetypes')  # 确保获取正确的参数

        new_user = User(name=name, gender=gender, sizhen=sizhen, tizhi=tizhi)
        db.session.add(new_user)
        db.session.commit()

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(new_user.id))
        os.makedirs(user_folder, exist_ok=True)

        for file, filetype in zip(files, filetypes):  # 同时迭代文件和文件类型
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(user_folder, filename)
                file.save(file_path)
                new_file = File(filename=filename, filetype=filetype, user_id=new_user.id)  # 保存文件类型
                db.session.add(new_file)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_data.html')

@app.route('/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form['name']
        user.gender = request.form['gender']
        files = request.files.getlist('files')
        filetypes = request.form.getlist('filetypes')  # 确保获取正确的参数
        print(files)

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user.id))
        os.makedirs(user_folder, exist_ok=True)
        for file, filetype in zip(files, filetypes):  # 同时迭代文件和文件类型
            print(f'file: {file}')
            print(f'filetype: {filetype}')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                print(f'filename: {filename}')
                file_path = os.path.join(user_folder, filename)
                file.save(file_path)

                # 查找已有的同类型文件并删除
                existing_file = next((f for f in user.files if f.filetype == filetype), None)
                if existing_file:
                    old_file_path = os.path.join(user_folder, existing_file.filename)
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                    existing_file.filename = filename  # 更新文件名
                else:
                    new_file = File(filename=filename, filetype=filetype, user_id=user.id)  # 新文件保存文件类型
                    db.session.add(new_file)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit_data.html', user=user)

@app.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user.id))
    if os.path.exists(user_folder):
        for root, dirs, files in os.walk(user_folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(user_folder)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/export')
def export_data():
    users = User.query.all()
    data = {
        'users': [],
        'files': {}
    }
    
    for user in users:
        user_data = {
            'name': user.name,
            'gender': user.gender,
            'sizhen': user.sizhen,
            'tizhi': user.tizhi
        }
        data['users'].append(user_data)
        
        user_files = []
        for file in user.files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(user.id), file.filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    user_files.append({
                        'filename': file.filename,
                        'filetype': file.filetype,
                        'content': f.read()
                    })
        data['files'][user.id] = user_files

    temp_dir = 'temp_data'
    os.makedirs(temp_dir, exist_ok=True)
    npz_path = os.path.join(temp_dir, 'exported_data.npz')
    
    np.savez_compressed(npz_path, users=data['users'], files=data['files'])
    
    return {'status': 'success', 'message': '数据导出成功!'}, 200

if __name__ == '__main__':
    app.run(debug=True)
