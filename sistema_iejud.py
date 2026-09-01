import streamlit as st
import pandas as pd
import numpy as np
import datetime
import os
import json
import sqlite3
import io

# Set Page Config
st.set_page_config(
    page_title="Sistema IE-Jud 11ª Vara Cível",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# DATABASE & PERSISTENCE LAYER (SQLite for Cloud/Multi-user)
# ---------------------------------------------------------
DB_FILE = "sistema_iejud_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Audit Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            action TEXT,
            details TEXT
        )
    """)
    
    # IEJud History
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iejud_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_recorded TEXT,
            pp120 REAL,
            meta1 REAL,
            meta2 REAL,
            iad REAL,
            tcl REAL,
            tmt REAL,
            iejud_score REAL,
            updated_by TEXT
        )
    """)
    
    # Editable Metadata for Tasks (Providências / Prazos / Servidores)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_metadata (
            num_processo TEXT PRIMARY KEY,
            providencia TEXT,
            prazo TEXT,
            servidor_atribuido TEXT,
            updated_by TEXT,
            last_update DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Raw tables storage (JSON serialized for simplicity & instant persistence)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_tables (
            table_name TEXT PRIMARY KEY,
            data_json TEXT,
            last_updated TEXT,
            updated_by TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def log_audit(username, action, details=""):
    conn = get_db()
    conn.execute("INSERT INTO audit_logs (username, action, details) VALUES (?, ?, ?)",
                 (username, action, details))
    conn.commit()
    conn.close()

def save_data_table(table_name, df, username):
    # Ensure process column is string formatted (preserving leading zeroes)
    if "PROCESSOS" in df.columns:
        df["PROCESSOS"] = df["PROCESSOS"].astype(str).str.zfill(20)
    elif "Processo" in df.columns:
        df["Processo"] = df["Processo"].astype(str).str.zfill(20)
        
    conn = get_db()
    data_json = df.to_json(orient="records", date_format="iso")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO data_tables (table_name, data_json, last_updated, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(table_name) DO UPDATE SET
            data_json=excluded.data_json,
            last_updated=excluded.last_updated,
            updated_by=excluded.updated_by
    """, (table_name, data_json, now_str, username))
    conn.commit()
    conn.close()
    log_audit(username, f"Atualizou tabela {table_name}", f"Total de linhas: {len(df)}")

def load_data_table(table_name):
    conn = get_db()
    row = conn.execute("SELECT data_json FROM data_tables WHERE table_name=?", (table_name,)).fetchone()
    conn.close()
    if row and row["data_json"]:
        df = pd.read_json(io.StringIO(row["data_json"]))
        # Re-ensure leading zero string format
        if "PROCESSOS" in df.columns:
            df["PROCESSOS"] = df["PROCESSOS"].astype(str).str.zfill(20)
        elif "Processo" in df.columns:
            df["Processo"] = df["Processo"].astype(str).str.zfill(20)
        return df
    return pd.DataFrame()

def save_process_metadata(num_processo, providencia, prazo, servidor, username):
    conn = get_db()
    conn.execute("""
        INSERT INTO process_metadata (num_processo, providencia, prazo, servidor_atribuido, updated_by, last_update)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(num_processo) DO UPDATE SET
            providencia=excluded.providencia,
            prazo=excluded.prazo,
            servidor_atribuido=excluded.servidor_atribuido,
            updated_by=excluded.updated_by,
            last_update=CURRENT_TIMESTAMP
    """, (num_processo, providencia, prazo, servidor, username))
    conn.commit()
    conn.close()

def load_all_metadata():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM process_metadata", conn)
    conn.close()
    if not df.empty:
        df["num_processo"] = df["num_processo"].astype(str).str.zfill(20)
    return df

# ---------------------------------------------------------
# AUTHENTICATION & LOGIN SYSTEM
# ---------------------------------------------------------
USERS = {
    "admin": "1234",
    "gabinete": "1234",
    "secretaria": "1234",
    "servidor1": "1234",
    "servidor2": "1234",
    "servidor3": "1234",
    "servidor4": "1234"
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

def login_page():
    st.markdown("<h2 style='text-align: center;'>⚖️ Sistema IE-Jud - 11ª Vara Cível e Empresarial</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Controle de Acesso e Gestão de Indicadores</h4>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔑 Identificação do Usuário")
            user_input = st.text_input("Usuário").strip().lower()
            password_input = st.text_input("Senha", type="password").strip()
            submit = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if submit:
                if user_input in USERS and USERS[user_input] == password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    log_audit(user_input, "Login efetuado com sucesso")
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

if not st.session_state.logged_in:
    login_page()
    st.stop()

# ---------------------------------------------------------
# MAIN NAVIGATION & SIDEBAR
# ---------------------------------------------------------
st.sidebar.title(f"👤 {st.session_state.username.upper()}")
if st.sidebar.button("🚪 Sair / Logout"):
    log_audit(st.session_state.username, "Logout do sistema")
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.divider()
menu = st.sidebar.radio(
    "Navegação do Sistema:",
    [
        "📊 Dashboard & Histórico IE-Jud",
        "🔮 Previsão de TCL",
        "📂 TMT & Gestão de Acervo (4 Tabelas)",
        "⏳ Processos Parados (>120 Dias)",
        "📋 Histórico & Log de Alterações"
    ]
)

# HELPER MATH FUNCTIONS FOR IEJUD
def calc_iejud(pp, m1, m2, iad, tcl, tmt):
    n_pp = 1.0 if pp <= 5.0 else max(0.0, 1 - (pp - 5)/10)
    n_m1 = min(1.0, m1 / 100)
    n_m2 = min(1.0, m2 / 100)
    n_iad = 1.0 if iad >= 105.0 else max(0.0, iad / 105.0)
    n_tcl = max(0.0, min(1.0, 1 - ((tcl - 60) / 40)))
    n_tmt = max(0.0, min(1.0, 1 - ((tmt - 500) / 400)))
    score = ((2*n_pp + 2*n_m1 + 1*n_m2 + 2*n_iad + 1*n_tcl + 2*n_tmt) / 10) * 100
    return round(score, 2)

# =========================================================
# 1. DASHBOARD & HISTÓRICO IE-JUD
# =========================================================
if menu == "📊 Dashboard & Histórico IE-Jud":
    st.header("📊 Painel Geral de Eficiência & Histórico IE-Jud")
    st.caption("Atualizações diárias salvas permanentemente com rastreabilidade de usuário.")
    
    conn = get_db()
    history_df = pd.read_sql_query("SELECT * FROM iejud_history ORDER BY id DESC", conn)
    conn.close()
    
    with st.expander("➕ Cadastrar / Atualizar Dados Diários do IE-Jud", expanded=history_df.empty):
        with st.form("new_iejud_entry"):
            c1, c2, c3 = st.columns(3)
            data_reg = c1.date_input("Data do Registro", datetime.date.today())
            pp_val = c2.number_input("PP+120 (%)", value=2.48, step=0.01)
            m1_val = c3.number_input("Meta 1 (%)", value=132.43, step=0.01)
            
            c4, c5, c6 = st.columns(3)
            m2_val = c4.number_input("Meta 2 (%)", value=112.95, step=0.01)
            iad_val = c5.number_input("IAD (%)", value=120.42, step=0.01)
            tcl_val = c6.number_input("TCL (%)", value=66.43, step=0.01)
            
            tmt_val = st.number_input("TMT (Dias)", value=680, step=1)
            
            calc_preview = calc_iejud(pp_val, m1_val, m2_val, iad_val, tcl_val, tmt_val)
            st.info(f"💡 Pontuação Estimada do IE-Jud: **{calc_preview}%**")
            
            save_btn = st.form_submit_button("💾 Salvar Registro Diário")
            if save_btn:
                conn = get_db()
                conn.execute("""
                    INSERT INTO iejud_history (date_recorded, pp120, meta1, meta2, iad, tcl, tmt, iejud_score, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(data_reg), pp_val, m1_val, m2_val, iad_val, tcl_val, tmt_val, calc_preview, st.session_state.username))
                conn.commit()
                conn.close()
                log_audit(st.session_state.username, "Registrou dados do IE-Jud", f"Data: {data_reg}, IEJud: {calc_preview}%")
                st.success("Dados de IE-Jud salvos com sucesso!")
                st.rerun()

    if not history_df.empty:
        latest = history_df.iloc[0]
        st.subheader("📌 Últimos Indicadores Registrados")
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("IE-Jud", f"{latest['iejud_score']}%")
        k2.metric("PP+120", f"{latest['pp120']}%")
        k3.metric("Meta 1", f"{latest['meta1']}%")
        k4.metric("Meta 2", f"{latest['meta2']}%")
        k5.metric("IAD", f"{latest['iad']}%")
        k6.metric("TCL", f"{latest['tcl']}%")
        k7.metric("TMT", f"{latest['tmt']} dias")
        
        st.subheader("📈 Evolução Histórica dos Indicadores")
        st.dataframe(history_df[['date_recorded', 'iejud_score', 'pp120', 'meta1', 'meta2', 'iad', 'tcl', 'tmt', 'updated_by']], use_container_width=True)

# =========================================================
# 2. MÓDULO: PREVISÃO DE TCL
# =========================================================
elif menu == "🔮 Previsão de TCL":
    st.header("🔮 Simulador de Previsão Mensal da TCL")
    st.caption("Calcule estimativas de variação da Taxa de Congestionamento Líquida para o próximo mês.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📥 Dados Atuais do Acervo")
        pendentes_at = st.number_input("Casos Pendentes Atuais", value=5330, step=1)
        suspensos_at = st.number_input("Processos Suspensos Atuais", value=568, step=1)
        baixados_12m = st.number_input("Processos Baixados nos Últimos 12 Meses", value=2406, step=1)
        
        liq_atual = pendentes_at - suspensos_at
        tcl_atual_calc = (liq_atual / (liq_atual + baixados_12m)) * 100
        st.metric("TCL Atual Calculada", f"{tcl_atual_calc:.2f}%")
        
    with col2:
        st.subheader("⚙️ Variáveis de Projeção Mensal")
        baixas_descarte = st.number_input("Baixas a Perder (Mês de 1 ano atrás que sairá dos 12M)", value=292, step=1)
        novas_baixas_est = st.number_input("Estimativa de Novas Baixas no Mês", value=220, step=1)
        novos_processos_est = st.number_input("Novos Processos que Entrarão na Vara", value=160, step=1)
        suspensos_var = st.number_input("Variação de Suspensos (+ Novos Suspensos / - Dessuspensos)", value=0, step=1)

    # Calculation logic
    novos_baixados_12m = baixados_12m - baixas_descarte + novas_baixas_est
    novos_pendentes = pendentes_at + novos_processos_est - novas_baixas_est
    novos_suspensos = suspensos_at + suspensos_var
    novo_liq = novos_pendentes - novos_suspensos
    
    tcl_projetada = (novo_liq / (novo_liq + novos_baixados_12m)) * 100
    dif_tcl = tcl_projetada - tcl_atual_calc
    
    st.divider()
    st.subheader("📊 Resultado da Projeção")
    res1, res2, res3 = st.columns(3)
    res1.metric("Novo Acervo Líquido", f"{novo_liq} proc.")
    res2.metric("Baixas Acumuladas (12M)", f"{novos_baixados_12m} proc.")
    res3.metric("TCL Projetada", f"{tcl_projetada:.2f}%", delta=f"{dif_tcl:+.2f}%", delta_color="inverse")

# =========================================================
# 3. MÓDULO: TMT E GESTÃO DE ACERVO (4 TABELAS)
# =========================================================
elif menu == "📂 TMT & Gestão de Acervo (4 Tabelas)":
    st.header("📂 Gestão de TMT & Divisão do Acervo")
    st.caption("Upload inteligente: preserva providências, prazos e atribuições de servidores sem sobrescrever.")
    
    # Metadata map
    meta_df = load_all_metadata()
    meta_dict = {}
    if not meta_df.empty:
        for idx, r in meta_df.iterrows():
            meta_dict[str(r["num_processo"]).zfill(20)] = {
                "providencia": r.get("providencia", ""),
                "prazo": r.get("prazo", ""),
                "servidor": r.get("servidor_atribuido", "")
            }

    tab_upload, tab1, tab2, tab3, tab4, tab_top30 = st.tabs([
        "📤 Envio de Arquivos TMT",
        "🏢 Secretaria - Em Andamento",
        "⚖️ Secretaria - Julgados",
        "🏛️ Gabinete - A Ser Julgado",
        "✅ Gabinete - A Ser Baixado",
        "🏆 Top 30 Maiores TMTs"
    ])
    
    with tab_upload:
        st.subheader("Enviar/Atualizar Planilhas do TMT")
        u_sec = st.file_uploader("Upload Planilha TMT SECRETARIA", type=["xlsx", "xls"], key="sec_up")
        u_gab = st.file_uploader("Upload Planilha TMT GABINETE", type=["xlsx", "xls"], key="gab_up")
        
        if u_sec:
            df_s = pd.read_excel(u_sec, dtype=str)
            df_s["PROCESSOS"] = df_s["PROCESSOS"].astype(str).str.zfill(20)
            save_data_table("tmt_secretaria", df_s, st.session_state.username)
            st.success("Planilha de Secretaria carregada e salva com sucesso!")
            st.rerun()
            
        if u_gab:
            df_g = pd.read_excel(u_gab, dtype=str)
            df_g["PROCESSOS"] = df_g["PROCESSOS"].astype(str).str.zfill(20)
            save_data_table("tmt_gabinete", df_g, st.session_state.username)
            st.success("Planilha de Gabinete carregada e salva com sucesso!")
            st.rerun()

    # Load raw stored tables
    df_raw_sec = load_data_table("tmt_secretaria")
    df_raw_gab = load_data_table("tmt_gabinete")

    def enrich_table(df):
        if df.empty:
            return df
        df = df.copy()
        df["PROCESSOS"] = df["PROCESSOS"].astype(str).str.zfill(20)
        df["Providência"] = df["PROCESSOS"].apply(lambda x: meta_dict.get(x, {}).get("providencia", ""))
        df["Prazo"] = df["PROCESSOS"].apply(lambda x: meta_dict.get(x, {}).get("prazo", ""))
        df["Servidor Atribuído"] = df["PROCESSOS"].apply(lambda x: meta_dict.get(x, {}).get("servidor", ""))
        return df

    # Helper renderer and saver for data editors
    def render_editable_section(df_sub, key_prefix):
        if df_sub.empty:
            st.warning("Nenhum processo encontrado nesta categoria. Faça o upload da planilha.")
            return
        
        enriched = enrich_table(df_sub)
        cols_order = ["PROCESSOS", "TEMPO TRAMITAÇÃO", "SITUACAO", "Providência", "Prazo", "Servidor Atribuído", "CLASSE", "ASSUNTO", "DATA ÚLT MOVIMENTO"]
        existing_cols = [c for c in cols_order if c in enriched.columns]
        
        edited_df = st.data_editor(
            enriched[existing_cols],
            column_config={
                "PROCESSOS": st.column_config.TextColumn("Nº do Processo", disabled=True),
                "TEMPO TRAMITAÇÃO": st.column_config.NumberColumn("Tempo (Dias)", disabled=True),
                "SITUACAO": st.column_config.TextColumn("Situação", disabled=True),
                "Providência": st.column_config.TextColumn("Providência (Editável)"),
                "Prazo": st.column_config.TextColumn("Prazo (Editável)"),
                "Servidor Atribuído": st.column_config.SelectboxColumn(
                    "Servidor Atribuído",
                    options=["Servidor 1", "Servidor 2", "Servidor 3", "Servidor 4", "Não Atribuído"]
                )
            },
            key=f"editor_{key_prefix}",
            use_container_width=True,
            num_rows="fixed"
        )
        
        if st.button("💾 Salvar Alterações de Providências/Prazos", key=f"btn_{key_prefix}"):
            for idx, r in edited_df.iterrows():
                proc_num = str(r["PROCESSOS"]).zfill(20)
                prov = str(r["Providência"]) if pd.notna(r["Providência"]) else ""
                prz = str(r["Prazo"]) if pd.notna(r["Prazo"]) else ""
                srv = str(r["Servidor Atribuído"]) if pd.notna(r["Servidor Atribuído"]) else ""
                save_process_metadata(proc_num, prov, prz, srv, st.session_state.username)
            log_audit(st.session_state.username, f"Atualizou providências/prazos em {key_prefix}")
            st.success("Alterações salvas com sucesso!")
            st.rerun()

    with tab1:
        st.subheader("1. Secretaria - Processos Em Andamento")
        if not df_raw_sec.empty:
            sub = df_raw_sec[df_raw_sec["SITUACAO"].astype(str).str.upper().str.contains("ANDAMENTO")]
            render_editable_section(sub, "sec_andamento")

    with tab2:
        st.subheader("2. Secretaria - Processos Julgados (Aguardando Baixa)")
        if not df_raw_sec.empty:
            sub = df_raw_sec[df_raw_sec["SITUACAO"].astype(str).str.upper().str.contains("JULGADO")]
            render_editable_section(sub, "sec_julgado")

    with tab3:
        st.subheader("3. Gabinete - Processos a SER JULGADOS (Em Andamento)")
        if not df_raw_gab.empty:
            sub = df_raw_gab[df_raw_gab["SITUACAO"].astype(str).str.upper().str.contains("ANDAMENTO")]
            render_editable_section(sub, "gab_andamento")

    with tab4:
        st.subheader("4. Gabinete - Processos a Serem BAIXADOS (Julgados com Atribuição de Servidor)")
        if not df_raw_gab.empty:
            sub = df_raw_gab[df_raw_gab["SITUACAO"].astype(str).str.upper().str.contains("JULGADO")]
            render_editable_section(sub, "gab_julgado")

    with tab_top30:
        st.subheader("🏆 30 Maiores TMTs de Cada Setor")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top 30 - Gabinete")
            if not df_raw_gab.empty:
                df_gab_sort = df_raw_gab.copy()
                df_gab_sort["TEMPO TRAMITAÇÃO"] = pd.to_numeric(df_gab_sort["TEMPO TRAMITAÇÃO"], errors="coerce")
                top30_gab = df_gab_sort.sort_values(by="TEMPO TRAMITAÇÃO", ascending=False).head(30)
                st.dataframe(top30_gab[["PROCESSOS", "TEMPO TRAMITAÇÃO", "SITUACAO", "CLASSE"]], use_container_width=True)
        with c2:
            st.markdown("### Top 30 - Secretaria")
            if not df_raw_sec.empty:
                df_sec_sort = df_raw_sec.copy()
                df_sec_sort["TEMPO TRAMITAÇÃO"] = pd.to_numeric(df_sec_sort["TEMPO TRAMITAÇÃO"], errors="coerce")
                top30_sec = df_sec_sort.sort_values(by="TEMPO TRAMITAÇÃO", ascending=False).head(30)
                st.dataframe(top30_sec[["PROCESSOS", "TEMPO TRAMITAÇÃO", "SITUACAO", "CLASSE"]], use_container_width=True)

# =========================================================
# 4. PROCESSOS PARADOS A MAIS DE 120 DIAS
# =========================================================
elif menu == "⏳ Processos Parados (>120 Dias)":
    st.header("⏳ Processos Parados a Mais de 120 Dias (PP+120)")
    st.caption("Acompanhamento e atualização semanal de processos paralisados.")
    
    u_pp = st.file_uploader("Upload Planilha Atualizada de PP+120", type=["xlsx", "xls"], key="pp120_up")
    if u_pp:
        df_pp = pd.read_excel(u_pp, dtype=str)
        if "Processo" in df_pp.columns:
            df_pp["Processo"] = df_pp["Processo"].astype(str).str.zfill(20)
        save_data_table("pp120_table", df_pp, st.session_state.username)
        st.success("Planilha de PP+120 atualizada com sucesso!")
        st.rerun()

    df_pp_stored = load_data_table("pp120_table")
    if not df_pp_stored.empty:
        st.subheader("📋 Lista de Processos Paralisados (>120 Dias)")
        st.dataframe(df_pp_stored, use_container_width=True)
    else:
        st.info("Nenhuma planilha de PP+120 enviada ainda.")

# =========================================================
# 5. HISTÓRICO & LOG DE ALTERAÇÕES
# =========================================================
elif menu == "📋 Histórico & Log de Alterações":
    st.header("📋 Log de Auditoria e Alterações do Sistema")
    st.caption("Registro de quem realizou cada alteração (entradas, uploads, atualizações).")
    
    conn = get_db()
    logs_df = pd.read_sql_query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200", conn)
    conn.close()
    
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.info("Nenhum registro de alteração ainda.")
