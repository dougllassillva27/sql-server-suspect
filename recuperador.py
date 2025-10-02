"""
Recuperador de Banco SQL Server - Suspect v1.4
Com controle automático de serviços SQL Server
Interface moderna e profissional aprimorada
Layout otimizado com grupos lado a lado
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
                             QRadioButton, QProgressBar, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon


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
        except:
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
    
    def remover_readonly(self, caminho_arquivo):
        try:
            if os.path.exists(caminho_arquivo):
                os.chmod(caminho_arquivo, stat.S_IWRITE | stat.S_IREAD)
                subprocess.run(f'attrib -R "{caminho_arquivo}"', shell=True, capture_output=True)
                self.log(f"   → Atributo READ-ONLY removido: {os.path.basename(caminho_arquivo)}")
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
                        os.remove(caminho_mdf_novo)
                        self.log(f"   ✅ MDF anterior removido")
                    except:
                        self.finished_signal.emit(False, f"Remova manualmente: {caminho_mdf_novo}")
                        return
                
                if os.path.exists(caminho_ldf_novo):
                    try:
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
                self.log("")
                self.log("🔧 Verificando permissões dos arquivos...")
                self.remover_readonly(caminho_mdf_novo)
                if os.path.exists(caminho_ldf_novo):
                    self.remover_readonly(caminho_ldf_novo)
                
                self.log("")
                self.log("🔧 ETAPA 3/6: ONLINE, EMERGENCY, SINGLE_USER...")
                self.progress_signal.emit(3)
                
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET ONLINE", esperar_erro=True)
                time.sleep(1)
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET EMERGENCY", esperar_erro=True)
                time.sleep(1)
                self.executar_sql(f"ALTER DATABASE [{nome_banco}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE", esperar_erro=True)
                time.sleep(1)
                
                self.log("✅ Comandos executados")
                self.log("")
                self.log("🔧 ETAPA 4/6: Verificando LDF...")
                self.progress_signal.emit(4)
                
                if os.path.exists(caminho_ldf_novo):
                    self.log("   ⚠️ LDF ainda existe, tentando remover...")
                    try:
                        os.remove(caminho_ldf_novo)
                        self.log("   ✅ LDF removido manualmente")
                    except Exception as e:
                        self.finished_signal.emit(False, f"LDF ainda existe: {e}")
                        return
                else:
                    self.log("✅ LDF foi excluído")
                
                self.log("")
                self.log("🔧 ETAPA 5/6: Reconstruindo LOG...")
                self.progress_signal.emit(5)
                
                self.remover_readonly(caminho_mdf_novo)
                
                sql_rebuild = f"""
ALTER DATABASE [{nome_banco}] REBUILD LOG ON
(NAME = N'{nome_banco}_log', FILENAME = N'{caminho_ldf_novo}')
"""
                if not self.executar_sql(sql_rebuild):
                    self.finished_signal.emit(False, "Erro ao reconstruir LOG. Verifique permissões.")
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
        self.parametros_salvos = None
        self.servicos_parados = []
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle('Recuperador de Banco SQL Server - Suspect v1.4')
        self.setGeometry(100, 100, 1200, 750)
        
        # Definir ícone da janela
        icon_path = r"D:\OneDrive\Pessoal\Dodo\Programacao\Git\SQL Server\sql-server-suspect\assets\img\sql-server.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # ESTILO COM CURSOR POINTER
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 25px 15px 15px 15px;  /* top right bottom left */
                background-color: white;
                margin-top: 0px;
            }

            QLabel {
                color: #2d3748;
                font-size: 13px;
            }
            QLineEdit {
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: #ffffff;
                font-size: 13px;
                color: #2d3748;
            }
            QLineEdit:focus {
                border: 2px solid #4299e1;
                background-color: #f7fafc;
            }
            QLineEdit:disabled {
                background-color: #edf2f7;
                color: #a0aec0;
            }
            QTextEdit {
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                padding: 12px;
                background-color: #f7fafc;
                color: #2d3748;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11pt;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                color: white;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QPushButton:pressed {
                opacity: 0.8;
            }
            QPushButton:disabled {
                background-color: #cbd5e0;
                color: #a0aec0;
            }
            QRadioButton {
                spacing: 8px;
                font-size: 13px;
                color: #2d3748;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #a0aec0;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #4299e1;
                border: 2px solid #4299e1;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #4299e1;
            }
            QProgressBar {
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                text-align: center;
                color: #2d3748;
                background-color: #edf2f7;
                height: 24px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ed8936, stop:1 #f6ad55);
                border-radius: 5px;
            }
        """)

                # ESTILO PARA QMESSAGEBOX
        QApplication.instance().setStyleSheet(QApplication.instance().styleSheet() + """
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #2d3748;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4299e1, stop:1 #3182ce);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
                font-size: 13px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3182ce, stop:1 #2c5aa0);
            }
            QMessageBox QPushButton:pressed {
                background: #2c5aa0;
            }
        """)


        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Título principal
        titulo = QLabel("🔧 Recuperador de Banco SQL Server - Suspect v1.4")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 20px; font-weight: bold; color: #1a202c; margin-bottom: 8px; padding: 10px;")
        layout.addWidget(titulo)

        # === TÍTULOS DOS GRUPOS 1 E 2 NA MESMA LINHA ===
        h_titulos = QHBoxLayout()
        h_titulos.setSpacing(15)
        
        titulo_conexao = QLabel("1. Conexão SQL Server")
        titulo_conexao.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a202c; margin-top: 5px; margin-bottom: 5px;")
        h_titulos.addWidget(titulo_conexao)
        
        titulo_banco = QLabel("2. Configuração do Banco")
        titulo_banco.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a202c; margin-top: 5px; margin-bottom: 5px;")
        h_titulos.addWidget(titulo_banco)
        
        layout.addLayout(h_titulos)

        # === LAYOUT HORIZONTAL: GRUPO 1 E 2 LADO A LADO (MESMA ALTURA) ===
        h_grupos_top = QHBoxLayout()
        h_grupos_top.setSpacing(15)

        # === GRUPO 1: CONEXÃO ===
        grupo_conexao = QGroupBox()
        grupo_conexao.setMinimumHeight(250)
        self.aplicar_sombra(grupo_conexao)
        layout_conexao = QVBoxLayout()
        layout_conexao.setSpacing(12)

        h1 = QHBoxLayout()
        lbl_srv = QLabel("Servidor\\Instância:")
        lbl_srv.setMinimumWidth(110)
        h1.addWidget(lbl_srv)
        self.txt_servidor = QLineEdit("localhost\\")
        self.txt_servidor.setMinimumHeight(36)
        h1.addWidget(self.txt_servidor)
        layout_conexao.addLayout(h1)

        h2 = QHBoxLayout()
        self.radio_windows = QRadioButton("Auth Windows")
        self.radio_sql = QRadioButton("Auth SQL Server")
        self.radio_sql.setChecked(True)
        self.radio_windows.toggled.connect(self.toggle_auth)
        h2.addWidget(self.radio_windows)
        h2.addWidget(self.radio_sql)
        h2.addStretch()
        layout_conexao.addLayout(h2)

        h3 = QHBoxLayout()
        lbl_usr = QLabel("Usuário:")
        lbl_usr.setMinimumWidth(110)
        h3.addWidget(lbl_usr)
        self.txt_usuario = QLineEdit("sa")
        self.txt_usuario.setMinimumHeight(36)
        h3.addWidget(self.txt_usuario)
        layout_conexao.addLayout(h3)

        h3b = QHBoxLayout()
        lbl_pwd = QLabel("Senha:")
        lbl_pwd.setMinimumWidth(110)
        h3b.addWidget(lbl_pwd)
        self.txt_senha = QLineEdit("_43690")
        self.txt_senha.setEchoMode(QLineEdit.Password)
        self.txt_senha.setMinimumHeight(36)
        h3b.addWidget(self.txt_senha)
        layout_conexao.addLayout(h3b)

        layout_conexao.addSpacing(15)
        h_btn_testar = QHBoxLayout()
        h_btn_testar.addStretch()
        self.btn_testar = QPushButton("🔌 Testar Conexão")
        self.btn_testar.clicked.connect(self.testar_conexao)
        self.btn_testar.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4299e1, stop:1 #3182ce); padding: 8px 16px;")
        self.btn_testar.setCursor(Qt.PointingHandCursor)
        h_btn_testar.addWidget(self.btn_testar)
        h_btn_testar.addStretch()
        layout_conexao.addLayout(h_btn_testar)

        layout_conexao.addStretch()
        grupo_conexao.setLayout(layout_conexao)
        h_grupos_top.addWidget(grupo_conexao)

        # === GRUPO 2: BANCO ===
        grupo_banco = QGroupBox()
        grupo_banco.setMinimumHeight(250)
        self.aplicar_sombra(grupo_banco)
        layout_banco = QVBoxLayout()
        layout_banco.setSpacing(12)

        h4 = QHBoxLayout()
        lbl_db = QLabel("Nome do Banco:")
        lbl_db.setMinimumWidth(110)
        h4.addWidget(lbl_db)
        self.txt_nome_banco = QLineEdit()
        self.txt_nome_banco.setMinimumHeight(36)
        h4.addWidget(self.txt_nome_banco)
        layout_banco.addLayout(h4)

        h5 = QHBoxLayout()
        lbl_mdf = QLabel("Arquivo MDF:")
        lbl_mdf.setMinimumWidth(110)
        h5.addWidget(lbl_mdf)
        self.txt_mdf = QLineEdit()
        self.txt_mdf.setMinimumHeight(36)
        h5.addWidget(self.txt_mdf)
        
        btn_mdf = QPushButton("📂")
        btn_mdf.setFixedWidth(45)
        btn_mdf.setFixedHeight(38)
        btn_mdf.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4299e1, stop:1 #3182ce); padding: 0px;")
        btn_mdf.clicked.connect(self.selecionar_mdf)
        btn_mdf.setCursor(Qt.PointingHandCursor)
        h5.addWidget(btn_mdf)
        layout_banco.addLayout(h5)

        h6 = QHBoxLayout()
        lbl_ldf = QLabel("Arquivo LDF:")
        lbl_ldf.setMinimumWidth(110)
        h6.addWidget(lbl_ldf)
        self.txt_ldf = QLineEdit()
        self.txt_ldf.setMinimumHeight(36)
        h6.addWidget(self.txt_ldf)
        layout_banco.addLayout(h6)

        layout_banco.addStretch()
        grupo_banco.setLayout(layout_banco)
        h_grupos_top.addWidget(grupo_banco)

        layout.addLayout(h_grupos_top)

        # === GRUPO 3: PROGRESSO (LARGURA TOTAL) ===
        titulo_progresso = QLabel("3. Progresso da Recuperação")
        titulo_progresso.setStyleSheet("font-size: 13px; font-weight: 600; color: #1a202c; margin-top: 10px; margin-bottom: 5px;")
        layout.addWidget(titulo_progresso)
        
        grupo_progresso = QGroupBox()
        self.aplicar_sombra(grupo_progresso)
        layout_progresso = QVBoxLayout()
        layout_progresso.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(6)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout_progresso.addWidget(self.progress_bar)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(250)
        layout_progresso.addWidget(self.txt_log)

        grupo_progresso.setLayout(layout_progresso)
        layout.addWidget(grupo_progresso)

        # BOTÕES
        h7 = QHBoxLayout()
        h7.setSpacing(12)
        h7.addStretch()

        self.btn_iniciar = QPushButton("🚀 Iniciar Recuperação")
        self.btn_iniciar.clicked.connect(self.iniciar_recuperacao)
        self.btn_iniciar.setEnabled(False)
        self.btn_iniciar.setMaximumWidth(200)
        self.btn_iniciar.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4299e1, stop:1 #3182ce); padding: 10px 16px;")
        self.btn_iniciar.setCursor(Qt.PointingHandCursor)
        h7.addWidget(self.btn_iniciar)

        self.btn_parar_servicos = QPushButton("⏹️ Parar Serviços SQL")
        self.btn_parar_servicos.clicked.connect(self.parar_servicos)
        self.btn_parar_servicos.setVisible(False)
        self.btn_parar_servicos.setMaximumWidth(200)
        self.btn_parar_servicos.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f56565, stop:1 #fc8181); padding: 10px 16px;")
        self.btn_parar_servicos.setCursor(Qt.PointingHandCursor)
        h7.addWidget(self.btn_parar_servicos)

        self.btn_substituir = QPushButton("🔄 Substituir Arquivos")
        self.btn_substituir.clicked.connect(self.substituir_arquivos)
        self.btn_substituir.setVisible(False)
        self.btn_substituir.setMaximumWidth(200)
        self.btn_substituir.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4299e1, stop:1 #63b3ed); padding: 10px 16px;")
        self.btn_substituir.setCursor(Qt.PointingHandCursor)
        h7.addWidget(self.btn_substituir)

        self.btn_iniciar_servicos = QPushButton("▶️ Iniciar Serviços SQL")
        self.btn_iniciar_servicos.clicked.connect(self.iniciar_servicos)
        self.btn_iniciar_servicos.setVisible(False)
        self.btn_iniciar_servicos.setMaximumWidth(200)
        self.btn_iniciar_servicos.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #48bb78, stop:1 #68d391); padding: 10px 16px;")
        self.btn_iniciar_servicos.setCursor(Qt.PointingHandCursor)
        h7.addWidget(self.btn_iniciar_servicos)

        self.btn_continuar = QPushButton("➡️ Continuar Recuperação")
        self.btn_continuar.clicked.connect(self.continuar_recuperacao)
        self.btn_continuar.setVisible(False)
        self.btn_continuar.setMaximumWidth(200)
        self.btn_continuar.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #48bb78, stop:1 #68d391); padding: 10px 16px;")
        self.btn_continuar.setCursor(Qt.PointingHandCursor)
        h7.addWidget(self.btn_continuar)

        layout.addLayout(h7)

        self.adicionar_log("✅ Sistema pronto para recuperação")
        self.adicionar_log("")
        self.adicionar_log("📋 Instruções:")
        self.adicionar_log("   1. Teste a conexão com o SQL Server")
        self.adicionar_log("   2. Selecione o arquivo MDF corrompido")
        self.adicionar_log("   3. Clique em 'Iniciar Recuperação'")
    
    def aplicar_sombra(self, widget):
        """Aplica efeito de sombra ao widget"""
        sombra = QGraphicsDropShadowEffect()
        sombra.setBlurRadius(15)
        sombra.setColor(QColor(0, 0, 0, 30))
        sombra.setOffset(0, 2)
        widget.setGraphicsEffect(sombra)

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
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
    
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
        # INDICADORES VISUAIS
        self.setCursor(Qt.WaitCursor)
        self.btn_parar_servicos.setEnabled(False)
        self.btn_parar_servicos.setText("⏳ Parando...")
        
        self.adicionar_log("")
        self.adicionar_log("🔍 Buscando serviços SQL Server...")
        QApplication.processEvents()
        
        servicos = ServicosSQLManager.listar_servicos_sql()
        
        if not servicos:
            self.adicionar_log("⚠️ Nenhum serviço encontrado automaticamente")
            QApplication.processEvents()
            self.adicionar_log("")
            self.adicionar_log("📋 Ação manual necessária:")
            self.adicionar_log("   1. Windows + R → services.msc")
            self.adicionar_log("   2. Parar manualmente os serviços SQL")
            self.btn_parar_servicos.setVisible(False)
            self.btn_substituir.setVisible(True)
            self.setCursor(Qt.ArrowCursor)
            return
        
        self.adicionar_log(f"   Encontrados {len(servicos)} serviço(s)")
        QApplication.processEvents()
        
        self.servicos_parados = []
        sucesso_total = True
        
        for servico in servicos:
            estado = ServicosSQLManager.obter_estado_servico(servico)
            if estado == 'RUNNING':
                self.adicionar_log(f"   → Parando: {servico}...")
                QApplication.processEvents()
                
                if ServicosSQLManager.parar_servico(servico):
                    self.servicos_parados.append(servico)
                    self.adicionar_log(f"   ✅ Parado: {servico}")
                    QApplication.processEvents()
                else:
                    self.adicionar_log(f"   ⚠️ Falha: {servico}")
                    QApplication.processEvents()
                    sucesso_total = False
            else:
                self.adicionar_log(f"   ℹ️ Já parado: {servico}")
                QApplication.processEvents()
        
        if sucesso_total or self.servicos_parados:
            self.adicionar_log("")
            self.adicionar_log("✅ Serviços parados!")
            self.adicionar_log("")
            self.adicionar_log("📋 Clique em 'Substituir Arquivos'")
            QApplication.processEvents()
            self.btn_parar_servicos.setVisible(False)
            self.btn_substituir.setVisible(True)
        else:
            self.adicionar_log("")
            self.adicionar_log("❌ Execute como ADMINISTRADOR")
            QApplication.processEvents()
            QMessageBox.warning(self, "Permissão Negada", "Execute como ADMINISTRADOR")
        
        self.setCursor(Qt.ArrowCursor)
    
    def substituir_arquivos(self):
        # INDICADORES VISUAIS
        self.setCursor(Qt.WaitCursor)
        self.btn_substituir.setEnabled(False)
        self.btn_substituir.setText("⏳ Substituindo...")
        
        self.adicionar_log("")
        self.adicionar_log("🔄 Substituindo arquivos...")
        self.adicionar_log("   ⏳ Aguardando 5 segundos...")
        QApplication.processEvents()
        
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
                QApplication.processEvents()
                
                if os.path.exists(caminho_mdf_novo):
                    os.remove(caminho_mdf_novo)
                shutil.copy2(caminho_mdf_original, caminho_mdf_novo)
                tamanho = os.path.getsize(caminho_mdf_novo)
                self.adicionar_log(f"   ✅ MDF substituído ({tamanho / 1024 / 1024:.1f} MB)")
                QApplication.processEvents()
                sucesso = True
                break
            except Exception as e:
                if tentativa < 3:
                    self.adicionar_log(f"   ⏳ Aguardando...")
                    QApplication.processEvents()
                    time.sleep(3)
                else:
                    self.adicionar_log(f"   ❌ Erro: {str(e)}")
                    QApplication.processEvents()
                    QMessageBox.critical(self, "Erro", f"Falha:\n{str(e)}")
                    self.setCursor(Qt.ArrowCursor)
                    self.btn_substituir.setEnabled(True)
                    self.btn_substituir.setText("🔄 Substituir Arquivos")
                    return
        
        if not sucesso:
            self.setCursor(Qt.ArrowCursor)
            self.btn_substituir.setEnabled(True)
            self.btn_substituir.setText("🔄 Substituir Arquivos")
            return
        
        try:
            if os.path.exists(caminho_ldf_novo):
                os.remove(caminho_ldf_novo)
                self.adicionar_log(f"   ✅ LDF excluído")
                QApplication.processEvents()
        except Exception as e:
            self.adicionar_log(f"   ⚠️ Aviso: {e}")
            QApplication.processEvents()
        
        self.adicionar_log("")
        self.adicionar_log("✅ Substituição concluída!")
        self.adicionar_log("")
        self.adicionar_log("📋 Clique em '▶️ Iniciar Serviços SQL'")
        QApplication.processEvents()
        
        self.btn_substituir.setVisible(False)
        self.btn_iniciar_servicos.setVisible(True)
        self.setCursor(Qt.ArrowCursor)
    
    def iniciar_servicos(self):
        # INDICADORES VISUAIS
        self.setCursor(Qt.WaitCursor)
        self.btn_iniciar_servicos.setEnabled(False)
        self.btn_iniciar_servicos.setText("⏳ Iniciando...")
        
        self.adicionar_log("")
        self.adicionar_log("▶️ Iniciando serviços SQL Server...")
        QApplication.processEvents()
        
        if not self.servicos_parados:
            self.adicionar_log("   ℹ️ Inicie manualmente via services.msc")
            QApplication.processEvents()
        else:
            for servico in self.servicos_parados:
                self.adicionar_log(f"   → Iniciando: {servico}...")
                QApplication.processEvents()
                
                if ServicosSQLManager.iniciar_servico(servico):
                    self.adicionar_log(f"   ✅ Iniciado: {servico}")
                    QApplication.processEvents()
                else:
                    self.adicionar_log(f"   ⚠️ Falha: {servico}")
                    QApplication.processEvents()
            
            self.adicionar_log("")
            self.adicionar_log("✅ Serviços iniciados!")
            QApplication.processEvents()
        
        self.adicionar_log("")
        self.adicionar_log("⏳ Aguardando 10 segundos...")
        QApplication.processEvents()
        
        time.sleep(10)
        
        self.adicionar_log("")
        self.adicionar_log("📋 Clique em 'Continuar Recuperação'")
        QApplication.processEvents()
        
        self.btn_iniciar_servicos.setVisible(False)
        self.btn_continuar.setVisible(True)
        self.setCursor(Qt.ArrowCursor)
    
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
