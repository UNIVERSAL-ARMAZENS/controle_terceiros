from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import rules
from wtforms import PasswordField
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import click
from flask.cli import with_appcontext
from flask_migrate import Migrate

# --- App e DB ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Login ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- User model ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    must_change_password = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
     
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Admin ---
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class UserAdmin(ModelView):
    column_exclude_list = ['password_hash']
    form_excluded_columns = ['password_hash']
    form_extra_fields = {
        'password': PasswordField('Senha')
    }

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

    def on_model_change(self, form, model, is_created):
        if is_created:
            model.must_change_password = True  
        if form.password.data:
            model.set_password(form.password.data)

admin = Admin(app, index_view=MyAdminIndexView())
admin.add_view(UserAdmin(User, db.session))

# --- Funções utilitárias ---
def get_df():
    return pd.read_excel(
        'Integração, ASO e Certificados -Terceiros - Atualizada.xlsx',
        sheet_name='Dados', header=1, engine='openpyxl'
    )

def limpar_status(valor):
    if pd.isna(valor):
        return 'OK'
    valor = str(valor).strip().upper()
    if valor in ['?', '', 'N/A']:
        return 'OK'
    return valor

def limpar_cpf(cpf):
    return ''.join(filter(str.isdigit, str(cpf)))

def formatar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, str(cpf)))[:11].ljust(11, "_")
    return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"

def verificar_status_cpf(cpf):
    df_local = get_df()
    df_local['CPF'] = df_local['CPF'].apply(limpar_cpf)

    linha = df_local[df_local['CPF'] == cpf]
    if linha.empty:
        return "CPF não encontrado", [], '', ''
    
    nome = linha['Nome'].values[0] if 'Nome' in linha.columns else ''
    empresa = linha['Empresa'].values[0] if 'Empresa' in linha.columns else ''
    status_aso = limpar_status(linha['Status'].values[0])
    status_nr1 = str(linha['Status.1'].values[0]).strip().upper()
    status_pgr = limpar_status(linha['STATUS'].values[0])
    status_pcms = limpar_status(linha['STATUS.1'].values[0])

    bloqueios = []
    if status_aso in ['VENCIDO', '', '?']:
        bloqueios.append("ASO Vencido")
    if status_nr1 in ['VENCIDO', 'BLOQUEADO', '?', '']:
        bloqueios.append("Integração de Segurança - NR1 Vencido ou Não Realizado")
    if status_pgr in ['VENCIDO', '', '?']:
        bloqueios.append("PGR Vencido")
    if status_pcms in ['VENCIDO', '', '?']:
        bloqueios.append("PCMSO Vencido")

    if bloqueios:
        return f"BLOQUEADO por: {', '.join(bloqueios)}", bloqueios, nome, empresa
    return "LIBERADO", [], nome, empresa

# --- Rotas ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("Usuário não encontrado", "danger")
        elif not user.check_password(password):
            flash("Senha incorreta", "danger")
        else:
            login_user(user)
            if user.must_change_password:
                return redirect(url_for('change_password'))
            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')

        if not current_user.check_password(senha_atual):
            flash("Senha atual incorreta.", "danger")
        elif nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "danger")
        else:
            current_user.set_password(nova_senha)
            current_user.must_change_password = False
            db.session.commit()
            flash("Senha alterada com sucesso!", "success")
            return redirect(url_for('index'))

    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for('login'))
#TEST
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    status = None
    bloqueios = []
    cpf = None
    nome = ''
    empresa = ''

    if request.method == 'POST':
        cpf_input = request.form.get('cpf', '').strip()
        cpf = limpar_cpf(cpf_input)
        status, bloqueios, nome, empresa = verificar_status_cpf(cpf)

    cpf_formatado = formatar_cpf(cpf) if cpf else ''
    return render_template("index.html", usuario=current_user, cpf=cpf_formatado, nome=nome, empresa=empresa, status=status, bloqueios=bloqueios)

# --- CLI para criar admin ---
@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
@with_appcontext
def create_admin(username, password):
    if User.query.filter_by(username=username).first():
        click.echo(f"Usuário {username} já existe!")
        return
    admin_user = User(username=username, is_admin=True)
    admin_user.set_password(password)
    db.session.add(admin_user)
    db.session.commit()
    click.echo(f"Admin {username} criado com sucesso!")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
