# 🗄️ Recuperador de Banco SQL Server - Suspect Database Recovery

![Version](https://img.shields.io/badge/version-1.3-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

Ferramenta automatizada para recuperação de bancos de dados SQL Server em estado **Suspect** ou **Emergency**. Interface gráfica moderna com PyQt5 que automatiza todo o processo de recuperação seguindo as melhores práticas.

---

## 📋 Índice

- [Características](#-características)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação](#-instalação)
- [Como Usar](#-como-usar)
- [Gerar Executável](#-gerar-executável-exe)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Troubleshooting](#-troubleshooting)
- [Licença](#-licença)

---

## ✨ Características

- ✅ **Interface Gráfica Intuitiva** - Fácil de usar, mesmo para não técnicos
- ✅ **Controle Automático de Serviços SQL** - Para/inicia serviços automaticamente
- ✅ **Correção Automática de Permissões** - Remove atributos READ-ONLY
- ✅ **Log Detalhado** - Acompanhe cada etapa do processo
- ✅ **Validação de Permissões** - Verifica permissões antes de cada operação
- ✅ **Suporte a Autenticação Windows e SQL** - Flexibilidade de conexão
- ✅ **Barra de Progresso** - Visualize o andamento da recuperação
- ✅ **Tratamento de Erros Robusto** - Mensagens claras e ações corretivas

---

## 🔧 Pré-requisitos

### Software Necessário

1. **Python 3.8 ou superior**

   - Download: https://www.python.org/downloads/
   - ⚠️ Durante a instalação, marque "Add Python to PATH"

2. **Microsoft ODBC Driver 17 for SQL Server**

   - Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Necessário para conexão com SQL Server

3. **SQL Server** (qualquer versão)
   - Express, Standard, Enterprise ou Developer Edition

### Permissões Necessárias

- **Administrador do Windows** - Para parar/iniciar serviços SQL
- **Permissões SQL Server** - `sysadmin` ou permissões de criação de banco
- **Permissões na Pasta** - Leitura e escrita no diretório dos arquivos MDF/LDF

---

## 📥 Instalação

### Opção 1: Executável Pronto (.exe)

1. Baixe o arquivo `RecuperadorSQL.exe` da seção [Releases](../../releases)
2. Execute como **Administrador** (botão direito → "Executar como administrador")
3. Pronto! Não precisa instalar Python ou dependências

### Opção 2: Executar via Python

1. **Clone o repositório**
   git clone https://github.com/seu-usuario/recuperador-sql-server.git
   cd recuperador-sql-server

2. **Crie um ambiente virtual (recomendado)**
   python -m venv venv

Windows
venv\Scripts\activate

Linux/Mac
source venv/bin/activate

3. **Instale as dependências**
   pip install -r requirements.txt

4. **Execute a aplicação**
   python recuperador.py

---

## 🚀 Como Usar

### Passo a Passo Completo

---

## ⚠️ Avisos Importantes

1. **⚠️ Backup:** Sempre faça backup dos arquivos MDF/LDF antes de iniciar a recuperação
2. **⚠️ Administrador:** Execute sempre como Administrador para evitar problemas de permissão
3. **⚠️ Validação:** Após a recuperação, execute `DBCC CHECKDB` para validar a integridade
4. **⚠️ Ambiente de Produção:** Teste primeiro em ambiente de desenvolvimento/homologação

---

#### 1️⃣ **Configurar Conexão**

- Abra o programa
- Preencha o campo **Servidor\Instância** (ex: `localhost`, `.\SQLEXPRESS`)
- Escolha o tipo de autenticação:
  - **Windows**: Usa suas credenciais atuais
  - **SQL Server**: Digite usuário (ex: `sa`) e senha
- Clique em **"Testar Conexão"**
- ✅ Aguarde a mensagem "Conexão OK!"

#### 2️⃣ **Selecionar Banco**

- Clique em **"..."** ao lado de "Arquivo MDF Original"
- Navegue até o arquivo `.mdf` corrompido
- O campo "Nome do Banco" será preenchido automaticamente
- O campo "Arquivo LDF" também será preenchido

#### 3️⃣ **Iniciar Recuperação**

- Clique em **"Iniciar Recuperação"**
- Acompanhe o log:
  - Etapa 1/6: Preparando ambiente
  - Etapa 2/6: Configurando OFFLINE
- Aguarde a mensagem: "Clique no botão 'Parar Serviços SQL'"

#### 4️⃣ **Parar Serviços SQL**

- Clique em **"⏹️ Parar Serviços SQL"**
- O programa irá:
  - Detectar automaticamente serviços SQL
  - Parar cada serviço encontrado
- ✅ Aguarde: "Serviços parados com sucesso!"

#### 5️⃣ **Substituir Arquivos**

- Clique em **"Substituir Arquivos"**
- O programa irá:
  - Aguardar 5 segundos
  - Copiar o MDF original sobre o temporário
  - Excluir o LDF temporário
- ✅ Aguarde: "Substituição concluída!"

#### 6️⃣ **Iniciar Serviços SQL**

- Clique em **"▶️ Iniciar Serviços SQL"**
- O programa irá reiniciar todos os serviços parados
- Aguarda 10 segundos para estabilização
- ✅ Aguarde: "Serviços iniciados!"

#### 7️⃣ **Continuar Recuperação**

- Clique em **"Continuar Recuperação"**
- O programa irá:
  - Etapa 3/6: ONLINE, EMERGENCY, SINGLE_USER
  - Etapa 4/6: Verificando LDF
  - Etapa 5/6: Reconstruindo LOG (cria novo LDF)
  - Etapa 6/6: MULTI_USER
- 🎉 Mensagem: "Recuperação concluída!"

#### 8️⃣ **Validar Banco (Recomendado)**

- Abra o SQL Server Management Studio (SSMS)
- Execute:
  ```
  USE [NomeDoBanco];
  DBCC CHECKDB WITH NO_INFOMSGS;
  ```
- Verifique se há erros de consistência

---

## 🔨 Gerar Executável (.exe)

### Passo 1: Instalar PyInstaller

pip install pyinstaller

### Passo 2: Gerar o Executável

**Versão Simples (sem ícone):**
pyinstaller --onefile --windowed --name="RecuperadorSQL" recuperador.py

**Versão com Ícone Personalizado:**
pyinstaller --onefile --windowed --name="RecuperadorSQL" --icon=icone.ico recuperador.py

### Passo 3: Localizar o Executável

O arquivo `RecuperadorSQL.exe` estará em:
dist/RecuperadorSQL.exe

### Opções do PyInstaller

| Opção        | Descrição                                              |
| ------------ | ------------------------------------------------------ |
| `--onefile`  | Gera um único arquivo .exe (sem pasta de dependências) |
| `--windowed` | Oculta o console (janela preta) ao executar            |
| `--name`     | Define o nome do executável                            |
| `--icon`     | Define o ícone do executável (arquivo .ico)            |
| `--add-data` | Adiciona arquivos extras (se necessário)               |

### Testar o Executável

Executar diretamente
dist\RecuperadorSQL.exe

Executar como Administrador (recomendado)
Botão direito no arquivo → "Executar como administrador"

---

## 📁 Estrutura do Projeto

```
recuperador-sql-server/
│
├── recuperador.py # Código principal da aplicação
├── requirements.txt # Dependências Python
├── README.md # Este arquivo
├── LICENSE # Licença do projeto
├── icone.ico # Ícone do executável (opcional)
│
├── dist/ # Pasta gerada pelo PyInstaller
│ └── RecuperadorSQL.exe # Executável final
│
├── build/ # Arquivos temporários do PyInstaller
│ └── ...
│
└── venv/ # Ambiente virtual Python (se criado)
└── ...
```

---

## 📦 Dependências (requirements.txt)

```
PyQt5==5.15.10
pyodbc==5.0.1
pyinstaller==6.3.0
```

### Instalação Manual das Dependências

```
pip install PyQt5==5.15.10
pip install pyodbc==5.0.1
pip install pyinstaller==6.3.0
```

---

## ❓ Troubleshooting

### Problema: "Não foi possível parar os serviços"

**Causa:** Falta de permissões de Administrador

**Solução:**

1. Feche o programa
2. Botão direito no executável
3. Clique em **"Executar como administrador"**

---

### Problema: "Erro ao reconstruir LOG" (Etapa 5)

**Causa:** Arquivo MDF com atributo READ-ONLY

**Solução Automática:** A versão 1.3+ já remove automaticamente

**Solução Manual:**
No prompt de comando (como Admin)

```
attrib -R "C:\caminho\do\arquivo.mdf"
```

---

### Problema: "ODBC Driver não encontrado"

**Causa:** Driver SQL Server não instalado

**Solução:**

1. Baixe: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
2. Instale o **ODBC Driver 17 for SQL Server**
3. Reinicie o computador

---

### Problema: "LDF ainda existe" (Etapa 4)

**Causa:** Serviços SQL não foram parados corretamente

**Solução:**

1. Abra `services.msc`
2. Localize serviços que começam com **"SQL"**
3. Pare manualmente cada serviço
4. Clique em "Continuar Recuperação"

---

### Problema: Executável não abre ou fecha imediatamente

**Causa:** Faltam dependências do sistema

**Solução:**

1. Instale **Visual C++ Redistributable**:
   - https://aka.ms/vs/17/release/vc_redist.x64.exe
2. Instale **.NET Framework 4.8**:
   - https://dotnet.microsoft.com/download/dotnet-framework/net48

---

## 📝 Changelog

### v1.3 (Atual)

- ✅ Correção automática de permissões READ-ONLY
- ✅ Verificação de permissões antes do REBUILD LOG
- ✅ Log detalhado de atributos de arquivo
- ✅ Melhor tratamento de erros na Etapa 5

### v1.2

- ✅ Controle automático de serviços SQL
- ✅ Gerenciador de serviços SQL Server
- ✅ Interface com botões coloridos

### v1.1

- ✅ Interface gráfica PyQt5
- ✅ Barra de progresso
- ✅ Log em tempo real

### v1.0

- ✅ Versão inicial
- ✅ Recuperação manual passo a passo

---

## 📄 Licença

Este projeto está licenciado sob a **MIT License** - veja o arquivo [LICENSE](LICENSE) para detalhes.
