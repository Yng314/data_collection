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
    sizhen = db.Column(db.String(1000), nullable=False)
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

        file_inputs = ['ruoci_files', 'maizhen_files', 'shezhen_files', 'hongwai_files', 'junqun_files', 'daixie_files', 'vaginoscope_files', 'bingbian_files']
        file_counter = {input_name: 0 for input_name in file_inputs}

        new_user = User(name=name, gender=gender, sizhen=sizhen, tizhi=tizhi)
        db.session.add(new_user)
        db.session.commit()

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(new_user.id))
        os.makedirs(user_folder, exist_ok=True)

        for input_name in file_inputs:
            files = request.files.getlist(input_name)
            for file in files:
                if file and allowed_file(file.filename):
                    file_counter[input_name] += 1
                    extension = file.filename.rsplit('.', 1)[1].lower()
                    new_filename = f"{input_name.split('_')[0]}_{file_counter[input_name]}.{extension}"
                    file_path = os.path.join(user_folder, new_filename)
                    file.save(file_path)
                    new_file = File(filename=new_filename, filetype=input_name, user_id=new_user.id)
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
        user.sizhen = request.form['sizhen']
        user.tizhi = request.form['tizhi']

        file_inputs = ['ruoci_files', 'maizhen_files', 'shezhen_files', 'hongwai_files', 'junqun_files', 'daixie_files', 'vaginoscope_files', 'bingbian_files']
        file_counter = {input_name: 0 for input_name in file_inputs}

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user.id))
        os.makedirs(user_folder, exist_ok=True)

        for input_name in file_inputs:
            files = request.files.getlist(input_name)
            cleared = False
            for file in files:
                if file and allowed_file(file.filename):
                    file_counter[input_name] += 1
                    extension = file.filename.rsplit('.', 1)[1].lower()
                    new_filename = f"{input_name.split('_')[0]}_{file_counter[input_name]}.{extension}"
                    file_path = os.path.join(user_folder, new_filename)

                    # 删除现有的同类型文件
                    if not cleared:
                        existing_files = [f for f in user.files if f.filetype == input_name]
                        for existing_file in existing_files:
                            old_file_path = os.path.join(user_folder, existing_file.filename)
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)
                            db.session.delete(existing_file)
                        cleared = True

                    file.save(file_path)
                    # 添加新的文件记录
                    new_file = File(filename=new_filename, filetype=input_name, user_id=user.id)
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
