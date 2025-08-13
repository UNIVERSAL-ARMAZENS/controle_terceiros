import pandas as pd
from flask import Flask, request, jsonify, render_template


app = Flask(__name__)

df = pd.read_excel('Integração, ASO e Certificados -Terceiros - Atualizada.xlsx',
                   sheet_name='Dados', header=1, engine='openpyxl')


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
    cpf = ''.join(filter(str.isdigit, str(cpf)))  # remove qualquer caractere não numérico
    cpf = cpf.ljust(11, "_")  # completa com underscores até ter 11 caracteres
    return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"

def verificar_status_cpf(cpf):
    linha = df[df['CPF'] == cpf]
    if linha.empty:
       return "CPF não encontrado", [], '', ''
    
    nome = linha['Nome'].values[0] if 'Nome' in linha.columns else ''
    empresa = linha['Empresa'].values[0] if 'Empresa' in linha.columns else ''


    status_aso = limpar_status(linha['Status'].values[0])
    status_nr1 = str(linha['Status.1'].values[0]).strip().upper()  
    status_pgr = limpar_status(linha['STATUS'].values[0])
    status_pcms = limpar_status(linha['STATUS.1'].values[0])

    bloqueios = []

    if status_aso in ['VENCIDO','', '?']:
        bloqueios.append("ASO Vencido")
   
    if status_nr1 in ['VENCIDO','BLOQUEADO', '?', '']:
        bloqueios.append("Integração de Seguraça - NR1 Vencido ou Não Realizado")


    if status_pgr in ['VENCIDO', '', '?']:
        bloqueios.append("PGR Vencido")

    
    if status_pcms in ['VENCIDO', '', '?']:
        bloqueios.append("PCMSO Vencido")

    if bloqueios:
     return f"BLOQUEADO por: {', '.join(bloqueios)}", bloqueios, nome, empresa
    else:
      return "LIBERADO", [], nome, empresa



    
@app.route('/', methods=['GET', 'POST'])
def index():
    status = None
    bloqueios = []
    cpf = None
    nome = ''
    empresa = ''

    if request.method == 'POST':
        df['CPF'] = df['CPF'].apply(limpar_cpf)
        cpf = limpar_cpf(request.form.get('cpf', '').strip())
        status, bloqueios, nome, empresa = verificar_status_cpf(cpf)

    cpf_formatado = formatar_cpf(cpf)
    return render_template("index.html", cpf=cpf_formatado, nome=nome, empresa=empresa, status=status, bloqueios=bloqueios)


      

if __name__ == '__main__':
    app.run(debug=True)