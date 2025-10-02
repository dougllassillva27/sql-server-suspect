"""
Recuperador de Banco SQL Server - Suspect v1.3
Com correção de permissões READ-ONLY
"""

import sys
import os
import time
import shutil
import pyodbc
import subprocess
import stat
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QGroupBox,
                             QRadioButton, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


class ServicosSQLManager:
    """Gerenciador de serviços SQL Server"""
    
    @staticmethod
    def listar_servicos_sql():
        try:
            servicos = []
            
            padroes = [
                'MSSQL', 'SQLBrowser', 'SQLSERVERAGENT', 'SQLWriter',
                'SQLTELEMETRY', 'MSSQLFDLauncher', 'SSASTELEMETRY',
                'SSISTELEMETRY', 'SQLServerReportingServices', 'MSSQLServerOLAPService'
            ]
            
            for padrao in padroes:
                cmd = f'sc query type= service state= all | findstr /i "{padrao}"'
                resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp850', errors='ignore')
                
                linhas = resultado.stdout.split('\n')
                for linha in linhas:
                    if 'SERVICE_NAME:' in linha:
                        nome_servico = linha.split('SERVICE_NAME:')[1].strip()
                        if nome_servico and nome_servico not in servicos:
                            servicos.append(nome_servico)
            
            if not servicos:
                cmd_ps = 'powershell -Command "Get-Service | Where-Object {$_.DisplayName -like \'*SQL*\'} | Select-Object -ExpandProperty Name"'
                resultado_ps = subprocess.run(cmd_ps, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                
                if resultado_ps.returncode == 0:
                    linhas_ps = resultado_ps.stdout.strip().split('\n')
                    for linha in linhas_ps:
                        nome = linha.strip()
                        if nome and nome not in servicos:
                            servicos.append(nome)
            
            return servicos
            
        except Exception as e:
            return []
    
    @staticmethod
    def obter_estado_servico(nome_servico):
        try:
            cmd = f'sc query "{nome_servico}"'
            resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp850', errors='ignore')
            
            if 'RUNNING' in resultado.stdout:
                return 'RUNNING'
            elif 'STOPPED' in resultado.stdout:
                return 'STOPPED'
            elif 'PAUSED' in resultado.stdout:
                return 'PAUSED'
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'
    
    @staticmethod
    def parar_servico(nome_servico):
        try:
            cmd = f'net stop "{nome_servico}" /y'
            subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp850', errors='ignore')
            time.sleep(1)
            
            estado = ServicosSQLManager.obter_estado_servico(nome_servico)
            if estado == 'STOPPED':
                return True
            
            cmd = f'sc stop "{nome_servico}"'
            subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp850', errors='ignore')
            time.sleep(2)
            
            estado = ServicosSQLManager.obter_estado_servico(nome_servico)
            return estado == 'STOPPED'
        except:
            return False
    
    @staticmethod
    def iniciar_servico(nome_servico):
        try:
            cmd = f'net start "{nome_servico}"'
            subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp850', errors='ignore')
            time.sleep(2)
            
            estado = ServicosSQLManager.obter_estado_servico(nome_servico)
            return estado == 'RUNNING'
        except:
            return False


class WorkerThread(QThread):
    """Thread para executar comandos SQL sem travar a interface"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, parametros, etapa):
        super().__init__()
        self.parametros = parametros
        self.etapa = etapa
    
    def log(self, mensagem):
        self.log_signal.emit(mensagem)
    
    def executar_sql(self, sql, esperar_erro=False):
        try:
            conn_str = self.obter_connection_string()
            conexao = pyodbc.connect(conn_str, timeout=30, autocommit=True)
            cursor = conexao.cursor()
            cursor.execute(sql)
            conexao.close()
            return True
        except Exception as e:
            if esperar_erro:
                return True
            self.log(f"❌ Erro: {str(e)}")
            return False
    
    def obter_connection_string(self):
        servidor = self.parametros['servidor']
        if self.parametros['auth_windows']:
            return (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server={servidor};"
                f"Database=master;"
                f"Trusted_Connection=yes;"
            )
        else:
            usuario = self.parametros['usuario']
            senha = self.parametros['senha']
            return (
                f"Driver={{ODBC Driver 17 for SQL Server}};"
                f"Server={servidor};"
                f"Database=master;"
                f"UID={usuario};"
                f"PWD={senha};"
            )
    
    def verificar_banco_existe(self, nome_banco):
        try:
            conn_str = self.obter_connection_string()
            conexao = pyodbc.connect(conn_str, timeout=10)
            cursor = conexao.cursor()
            cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{nome_banco}'")
            resultado = cursor.fetchone()
            conexao.close()
            return resultado is not None
        except:
            return False
    
    def remover_readonly(self, caminho):
        """Remove atributo READ-ONLY de arquivo"""
        try:
            if os.path.exists(caminho):
                # Remover atributo READ-ONLY
                os.chmod(caminho, stat.S_IWRITE | stat.S_IREAD)
                
                # Método alternativo via attrib
                subprocess.run(f'attrib -R "{caminho}"', shell=True, capture_output=True)
                
                return True
        except Exception as e:
            self.log(f"   ⚠️ Aviso ao remover READ-ONLY: {e}")
            return False
    
    def run(self):
        try:
            nome_banco = self.parametros['nome_banco']
            caminho_mdf_original = self.parametros['caminho_mdf'].replace('/', '\\')
            caminho_ldf_original = self.parametros['caminho_ldf'].replace('/', '\\')
            
            dir_base = os.path.dirname(caminho_mdf_original)
            caminho_mdf_novo = os.path.join(dir_base, f"{nome_banco}_recuperado.mdf")
            caminho_ldf_novo = os.path.join(dir_base, f"{nome_banco}_recuperado_log.ldf")
            
            if self.etapa == 1:
                self.log("🔧 ETAPA 1/6: Preparando ambiente...")
                self.progress_signal.emit(1)
                
                if self.verificar_banco_existe(nome_banco):
                    self.log(f"   ⚠️ Banco [{nome_banco}] já existe")
                    self.log(f"   → Tentando remover...")
                    
                    self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET OFFLINE WITH ROLLBACK IMMEDIATE", esperar_erro=True)
                    time.sleep(2)
                    self.executar_sql(f"DROP DATABASE [{nome_banco}]", esperar_erro=True)
                    time.sleep(2)
                    
                    if self.verificar_banco_existe(nome_banco):
                        self.finished_signal.emit(False, "Banco já existe. Remova manualmente.")
                        return
                    self.log(f"   ✅ Banco existente removido")
                
                if os.path.exists(caminho_mdf_novo):
                    try:
                        self.remover_readonly(caminho_mdf_novo)
                        os.remove(caminho_mdf_novo)
                        self.log(f"   ✅ MDF anterior removido")
                    except:
                        self.finished_signal.emit(False, f"Remova manualmente: {caminho_mdf_novo}")
                        return
                
                if os.path.exists(caminho_ldf_novo):
                    try:
                        self.remover_readonly(caminho_ldf_novo)
                        os.remove(caminho_ldf_novo)
                        self.log(f"   ✅ LDF anterior removido")
                    except:
                        pass
                
                if not os.path.exists(caminho_mdf_original):
                    self.finished_signal.emit(False, "MDF original não encontrado")
                    return
                
                tamanho = os.path.getsize(caminho_mdf_original)
                self.log(f"   → MDF original: {tamanho / 1024 / 1024:.1f} MB")
                
                self.log("")
                self.log("🔧 Criando banco em branco...")
                
                sql = f"""
CREATE DATABASE [{nome_banco}]
ON (NAME = N'{nome_banco}',
    FILENAME = N'{caminho_mdf_novo}',
    SIZE = 10MB)
LOG ON (NAME = N'{nome_banco}_log',
        FILENAME = N'{caminho_ldf_novo}',
        SIZE = 5MB)
"""
                if not self.executar_sql(sql):
                    self.finished_signal.emit(False, "Erro ao criar banco temporário")
                    return
                
                self.log(f"✅ Banco [{nome_banco}] criado")
                
                self.log("")
                self.log("🔧 ETAPA 2/6: Configurando OFFLINE...")
                self.progress_signal.emit(2)
                
                if not self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET READ_ONLY"):
                    self.finished_signal.emit(False, "Erro ao definir READ_ONLY")
                    return
                
                if not self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET OFFLINE"):
                    self.finished_signal.emit(False, "Erro ao definir OFFLINE")
                    return
                
                self.log("✅ Banco OFFLINE")
                self.log("")
                self.log("=" * 70)
                self.log("⏸️ PRÓXIMO PASSO")
                self.log("=" * 70)
                self.log("")
                self.log("Clique no botão '⏹️ Parar Serviços SQL' abaixo")
                self.log("")
                
                self.finished_signal.emit(True, "aguardando_parada")
            
            elif self.etapa == 2:
                self.log("🔧 ETAPA 3/6: ONLINE, EMERGENCY, SINGLE_USER...")
                self.progress_signal.emit(3)
                
                # Remover READ-ONLY do arquivo físico
                self.log("   → Removendo atributo READ-ONLY do MDF...")
                self.remover_readonly(caminho_mdf_novo)
                
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET ONLINE", esperar_erro=True)
                time.sleep(1)
                
                # Tentar remover READ_ONLY do banco
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET READ_WRITE WITH ROLLBACK IMMEDIATE", esperar_erro=True)
                time.sleep(1)
                
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET EMERGENCY", esperar_erro=True)
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE", esperar_erro=True)
                
                self.log("✅ Comandos executados")
                
                self.log("")
                self.log("🔧 ETAPA 4/6: Verificando LDF...")
                self.progress_signal.emit(4)
                
                if os.path.exists(caminho_ldf_novo):
                    self.finished_signal.emit(False, "LDF ainda existe!")
                    return
                
                self.log("✅ LDF foi excluído")
                
                self.log("")
                self.log("🔧 ETAPA 5/6: Reconstruindo LOG...")
                self.progress_signal.emit(5)
                
                # Garantir que não está READ-ONLY antes do REBUILD
                self.log("   → Verificando permissões do arquivo...")
                self.remover_readonly(caminho_mdf_novo)
                
                sql_rebuild = f"""
ALTER DATABASE [{nome_banco}] REBUILD LOG ON
(NAME = N'{nome_banco}_log', FILENAME = N'{caminho_ldf_novo}')
"""
                
                if not self.executar_sql(sql_rebuild):
                    # Tentar método alternativo
                    self.log("   → Tentando método alternativo...")
                    
                    # Forçar READ_WRITE no banco
                    self.executar_sql(f"EXEC sp_dboption '{nome_banco}', 'read only', 'FALSE'", esperar_erro=True)
                    time.sleep(2)
                    
                    # Tentar novamente
                    if not self.executar_sql(sql_rebuild):
                        self.finished_signal.emit(False, "Erro ao reconstruir LOG. Verifique permissões da pasta.")
                        return
                
                self.log("✅ LOG reconstruído")
                
                self.log("")
                self.log("🔧 ETAPA 6/6: MULTI_USER...")
                self.progress_signal.emit(6)
                
                if not self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET MULTI_USER"):
                    self.finished_signal.emit(False, "Erro ao definir MULTI_USER")
                    return
                
                self.log("✅ MULTI_USER")
                self.log("")
                self.log("=" * 70)
                self.log("🎉 RECUPERAÇÃO CONCLUÍDA!")
                self.log("=" * 70)
                self.log("")
                
                self.finished_signal.emit(True, "concluido")
        
        except Exception as e:
            self.log(f"❌ Erro: {str(e)}")
            self.finished_signal.emit(False, str(e))


class RecuperadorSQL(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.aguardando_manual = False
        self.parametros_salvos = None
        self.servicos_parados = []
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle('Recuperador de Banco SQL Server - Suspect v1.3')
        self.setGeometry(100, 100, 950, 750)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        grupo_conexao = QGroupBox("1. Conexão SQL Server")
        layout_conexao = QVBoxLayout()
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Servidor\\Instância:"))
        self.txt_servidor = QLineEdit("localhost")
        h1.addWidget(self.txt_servidor)
        layout_conexao.addLayout(h1)
        
        h2 = QHBoxLayout()
        self.radio_windows = QRadioButton("Autenticação Windows")
        self.radio_windows.toggled.connect(self.toggle_auth)
        self.radio_sql = QRadioButton("Autenticação SQL Server")
        self.radio_sql.setChecked(True)
        h2.addWidget(self.radio_windows)
        h2.addWidget(self.radio_sql)
        layout_conexao.addLayout(h2)
        
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Usuário:"))
        self.txt_usuario = QLineEdit("sa")
        h3.addWidget(self.txt_usuario)
        h3.addWidget(QLabel("Senha:"))
        self.txt_senha = QLineEdit("_43690")
        self.txt_senha.setEchoMode(QLineEdit.Password)
        h3.addWidget(self.txt_senha)
        layout_conexao.addLayout(h3)
        
        self.btn_testar = QPushButton("Testar Conexão")
        self.btn_testar.clicked.connect(self.testar_conexao)
        layout_conexao.addWidget(self.btn_testar)
        
        grupo_conexao.setLayout(layout_conexao)
        layout.addWidget(grupo_conexao)
        
        grupo_banco = QGroupBox("2. Configuração do Banco")
        layout_banco = QVBoxLayout()
        
        h4 = QHBoxLayout()
        h4.addWidget(QLabel("Nome do Banco:"))
        self.txt_nome_banco = QLineEdit()
        h4.addWidget(self.txt_nome_banco)
        layout_banco.addLayout(h4)
        
        h5 = QHBoxLayout()
        h5.addWidget(QLabel("Arquivo MDF Original:"))
        self.txt_mdf = QLineEdit()
        h5.addWidget(self.txt_mdf)
        btn_mdf = QPushButton("...")
        btn_mdf.clicked.connect(self.selecionar_mdf)
        h5.addWidget(btn_mdf)
        layout_banco.addLayout(h5)
        
        h6 = QHBoxLayout()
        h6.addWidget(QLabel("Arquivo LDF Original:"))
        self.txt_ldf = QLineEdit()
        h6.addWidget(self.txt_ldf)
        layout_banco.addLayout(h6)
        
        grupo_banco.setLayout(layout_banco)
        layout.addWidget(grupo_banco)
        
        grupo_progresso = QGroupBox("3. Progresso da Recuperação")
        layout_progresso = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(6)
        self.progress_bar.setValue(0)
        layout_progresso.addWidget(self.progress_bar)
        
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Courier New", 9))
        layout_progresso.addWidget(self.txt_log)
        
        grupo_progresso.setLayout(layout_progresso)
        layout.addWidget(grupo_progresso)
        
        h7 = QHBoxLayout()
        h7.addStretch()
        
        self.btn_iniciar = QPushButton("Iniciar Recuperação")
        self.btn_iniciar.clicked.connect(self.iniciar_recuperacao)
        self.btn_iniciar.setEnabled(False)
        self.btn_iniciar.setStyleSheet("QPushButton { background-color: #ff9800; color: white; font-weight: bold; padding: 10px; }")
        h7.addWidget(self.btn_iniciar)
        
        self.btn_parar_servicos = QPushButton("⏹️ Parar Serviços SQL")
        self.btn_parar_servicos.clicked.connect(self.parar_servicos)
        self.btn_parar_servicos.setVisible(False)
        self.btn_parar_servicos.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 10px; }")
        h7.addWidget(self.btn_parar_servicos)
        
        self.btn_substituir = QPushButton("Substituir Arquivos")
        self.btn_substituir.clicked.connect(self.substituir_arquivos)
        self.btn_substituir.setVisible(False)
        self.btn_substituir.setStyleSheet("QPushButton { background-color: #2196f3; color: white; font-weight: bold; padding: 10px; }")
        h7.addWidget(self.btn_substituir)
        
        self.btn_iniciar_servicos = QPushButton("▶️ Iniciar Serviços SQL")
        self.btn_iniciar_servicos.clicked.connect(self.iniciar_servicos)
        self.btn_iniciar_servicos.setVisible(False)
        self.btn_iniciar_servicos.setStyleSheet("QPushButton { background-color: #4caf50; color: white; font-weight: bold; padding: 10px; }")
        h7.addWidget(self.btn_iniciar_servicos)
        
        self.btn_continuar = QPushButton("Continuar Recuperação")
        self.btn_continuar.clicked.connect(self.continuar_recuperacao)
        self.btn_continuar.setVisible(False)
        self.btn_continuar.setStyleSheet("QPushButton { background-color: #4caf50; color: white; font-weight: bold; padding: 10px; }")
        h7.addWidget(self.btn_continuar)
        
        layout.addLayout(h7)
        
        self.adicionar_log("✓ Sistema pronto")
        self.adicionar_log("")
        self.adicionar_log("📋 PROCESSO:")
        self.adicionar_log("   1. Teste a conexão")
        self.adicionar_log("   2. Selecione o MDF original")
        self.adicionar_log("   3. Inicie a recuperação")
    
    def toggle_auth(self):
        windows = self.radio_windows.isChecked()
        self.txt_usuario.setEnabled(not windows)
        self.txt_senha.setEnabled(not windows)
    
    def selecionar_mdf(self):
        arquivo, _ = QFileDialog.getOpenFileName(self, "Selecione o MDF", "", "Arquivos MDF (*.mdf)")
        if arquivo:
            self.txt_mdf.setText(arquivo)
            self.txt_ldf.setText(arquivo.replace('.mdf', '.ldf'))
            if not self.txt_nome_banco.text():
                self.txt_nome_banco.setText(os.path.splitext(os.path.basename(arquivo))[0])
    
    def adicionar_log(self, mensagem):
        self.txt_log.append(mensagem)
    
    def testar_conexao(self):
        try:
            parametros = self.obter_parametros()
            servidor = parametros['servidor']
            
            if parametros['auth_windows']:
                conn_str = f"Driver={{ODBC Driver 17 for SQL Server}};Server={servidor};Database=master;Trusted_Connection=yes;"
            else:
                conn_str = f"Driver={{ODBC Driver 17 for SQL Server}};Server={servidor};Database=master;UID={parametros['usuario']};PWD={parametros['senha']};"
            
            self.adicionar_log("")
            self.adicionar_log("🔌 Testando...")
            conexao = pyodbc.connect(conn_str, timeout=10)
            conexao.close()
            self.adicionar_log("✅ Conexão OK!")
            self.btn_iniciar.setEnabled(True)
        except Exception as e:
            self.adicionar_log(f"❌ Erro: {str(e)}")
    
    def obter_parametros(self):
        return {
            'servidor': self.txt_servidor.text().strip(),
            'auth_windows': self.radio_windows.isChecked(),
            'usuario': self.txt_usuario.text().strip(),
            'senha': self.txt_senha.text(),
            'nome_banco': self.txt_nome_banco.text().strip(),
            'caminho_mdf': self.txt_mdf.text().strip(),
            'caminho_ldf': self.txt_ldf.text().strip()
        }
    
    def iniciar_recuperacao(self):
        if not self.txt_mdf.text().strip() or not os.path.exists(self.txt_mdf.text().strip()):
            QMessageBox.warning(self, "Atenção", "Selecione o MDF")
            return
        
        self.btn_iniciar.setEnabled(False)
        self.adicionar_log("")
        self.adicionar_log("🚀 INICIANDO")
        
        self.parametros_salvos = self.obter_parametros()
        self.worker = WorkerThread(self.parametros_salvos, etapa=1)
        self.worker.log_signal.connect(self.adicionar_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_etapa1_concluida)
        self.worker.start()
    
    def on_etapa1_concluida(self, sucesso, mensagem):
        if sucesso and mensagem == "aguardando_parada":
            self.btn_iniciar.setVisible(False)
            self.btn_parar_servicos.setVisible(True)
        elif not sucesso:
            QMessageBox.critical(self, "Erro", mensagem)
            self.btn_iniciar.setEnabled(True)
    
    def parar_servicos(self):
        self.adicionar_log("")
        self.adicionar_log("🔍 Buscando serviços SQL Server...")
        
        servicos = ServicosSQLManager.listar_servicos_sql()
        
        if not servicos:
            self.adicionar_log("⚠️ Nenhum serviço encontrado automaticamente")
            self.adicionar_log("")
            self.adicionar_log("📋 Ação manual necessária:")
            self.adicionar_log("   1. Windows + R → services.msc")
            self.adicionar_log("   2. Parar manualmente os serviços SQL")
            
            self.btn_parar_servicos.setVisible(False)
            self.btn_substituir.setVisible(True)
            return
        
        self.adicionar_log(f"   Encontrados {len(servicos)} serviço(s)")
        self.servicos_parados = []
        sucesso_total = True
        
        for servico in servicos:
            estado = ServicosSQLManager.obter_estado_servico(servico)
            
            if estado == 'RUNNING':
                self.adicionar_log(f"   → Parando: {servico}...")
                if ServicosSQLManager.parar_servico(servico):
                    self.servicos_parados.append(servico)
                    self.adicionar_log(f"   ✅ Parado: {servico}")
                else:
                    self.adicionar_log(f"   ⚠️ Falha ao parar: {servico}")
                    sucesso_total = False
            else:
                self.adicionar_log(f"   ℹ️ Já parado: {servico}")
        
        if sucesso_total or self.servicos_parados:
            self.adicionar_log("")
            self.adicionar_log("✅ Serviços parados com sucesso!")
            self.adicionar_log("")
            self.adicionar_log("📋 Próximo passo:")
            self.adicionar_log("   Clique em 'Substituir Arquivos'")
            
            self.btn_parar_servicos.setVisible(False)
            self.btn_substituir.setVisible(True)
        else:
            self.adicionar_log("")
            self.adicionar_log("❌ Não foi possível parar os serviços")
            self.adicionar_log("")
            self.adicionar_log("💡 Execute o programa como ADMINISTRADOR")
            QMessageBox.warning(
                self,
                "Permissão Negada",
                "Não foi possível parar os serviços.\n\n" +
                "Execute o programa como ADMINISTRADOR:\n" +
                "• Botão direito no .exe\n" +
                "• Executar como administrador"
            )
    
    def substituir_arquivos(self):
        self.adicionar_log("")
        self.adicionar_log("🔄 Substituindo arquivos...")
        self.adicionar_log("   ⏳ Aguardando 5 segundos...")
        time.sleep(5)
        
        nome_banco = self.parametros_salvos['nome_banco']
        caminho_mdf_original = self.parametros_salvos['caminho_mdf'].replace('/', '\\')
        dir_base = os.path.dirname(caminho_mdf_original)
        caminho_mdf_novo = os.path.join(dir_base, f"{nome_banco}_recuperado.mdf")
        caminho_ldf_novo = os.path.join(dir_base, f"{nome_banco}_recuperado_log.ldf")
        
        sucesso = False
        for tentativa in range(1, 4):
            try:
                self.adicionar_log(f"   → Tentativa {tentativa}/3...")
                
                if os.path.exists(caminho_mdf_novo):
                    # Remover READ-ONLY antes de deletar
                    os.chmod(caminho_mdf_novo, stat.S_IWRITE | stat.S_IREAD)
                    subprocess.run(f'attrib -R "{caminho_mdf_novo}"', shell=True, capture_output=True)
                    os.remove(caminho_mdf_novo)
                
                shutil.copy2(caminho_mdf_original, caminho_mdf_novo)
                
                # Remover READ-ONLY do arquivo copiado
                os.chmod(caminho_mdf_novo, stat.S_IWRITE | stat.S_IREAD)
                subprocess.run(f'attrib -R "{caminho_mdf_novo}"', shell=True, capture_output=True)
                
                tamanho = os.path.getsize(caminho_mdf_novo)
                self.adicionar_log(f"   ✅ MDF substituído ({tamanho / 1024 / 1024:.1f} MB)")
                self.adicionar_log(f"   ✅ Permissões ajustadas")
                sucesso = True
                break
                
            except Exception as e:
                if tentativa < 3:
                    self.adicionar_log(f"   ⏳ Falhou, aguardando...")
                    time.sleep(3)
                else:
                    self.adicionar_log(f"   ❌ Erro: {str(e)}")
                    QMessageBox.critical(self, "Erro", f"Falha:\n{str(e)}")
                    return
        
        if not sucesso:
            return
        
        try:
            if os.path.exists(caminho_ldf_novo):
                os.chmod(caminho_ldf_novo, stat.S_IWRITE | stat.S_IREAD)
                os.remove(caminho_ldf_novo)
                self.adicionar_log(f"   ✅ LDF excluído")
        except Exception as e:
            self.adicionar_log(f"   ⚠️ Erro ao excluir LDF: {e}")
        
        self.adicionar_log("")
        self.adicionar_log("✅ Substituição concluída!")
        self.adicionar_log("")
        self.adicionar_log("📋 Próximo passo:")
        self.adicionar_log("   Clique em '▶️ Iniciar Serviços SQL'")
        
        self.btn_substituir.setVisible(False)
        self.btn_iniciar_servicos.setVisible(True)
    
    def iniciar_servicos(self):
        self.adicionar_log("")
        self.adicionar_log("▶️ Iniciando serviços SQL Server...")
        
        if not self.servicos_parados:
            self.adicionar_log("   ℹ️ Nenhum serviço foi parado automaticamente")
            self.adicionar_log("")
            self.adicionar_log("📋 Ação manual necessária:")
            self.adicionar_log("   1. Windows + R → services.msc")
            self.adicionar_log("   2. Iniciar os serviços SQL Server")
        else:
            for servico in self.servicos_parados:
                self.adicionar_log(f"   → Iniciando: {servico}...")
                if ServicosSQLManager.iniciar_servico(servico):
                    self.adicionar_log(f"   ✅ Iniciado: {servico}")
                else:
                    self.adicionar_log(f"   ⚠️ Falha ao iniciar: {servico}")
            
            self.adicionar_log("")
            self.adicionar_log("✅ Serviços iniciados!")
        
        self.adicionar_log("")
        self.adicionar_log("⏳ Aguardando 10 segundos...")
        time.sleep(10)
        
        self.adicionar_log("")
        self.adicionar_log("📋 Próximo passo:")
        self.adicionar_log("   Clique em 'Continuar Recuperação'")
        
        self.btn_iniciar_servicos.setVisible(False)
        self.btn_continuar.setVisible(True)
    
    def continuar_recuperacao(self):
        self.btn_continuar.setEnabled(False)
        self.adicionar_log("")
        self.adicionar_log("▶️ CONTINUANDO")
        
        self.worker = WorkerThread(self.parametros_salvos, etapa=2)
        self.worker.log_signal.connect(self.adicionar_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_recuperacao_concluida)
        self.worker.start()
    
    def on_recuperacao_concluida(self, sucesso, mensagem):
        if sucesso:
            QMessageBox.information(self, "Sucesso", "Recuperação concluída!\n\nExecute DBCC CHECKDB.")
            self.btn_continuar.setVisible(False)
            self.btn_iniciar.setVisible(True)
            self.btn_iniciar.setEnabled(True)
            self.progress_bar.setValue(0)
        else:
            QMessageBox.critical(self, "Erro", mensagem)
            self.btn_continuar.setEnabled(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    janela = RecuperadorSQL()
    janela.show()
    sys.exit(app.exec_())
