import sys
import os
import subprocess

# Protocolo seguro de auto-inicialização do Streamlit (Anti-Looping)
try:
    import streamlit as st
    # st.runtime.exists() só retorna True se o script já estiver rodando dentro do servidor Streamlit
    is_running_under_streamlit = st.runtime.exists()
except (ImportError, AttributeError):
    is_running_under_streamlit = False

if not is_running_under_streamlit:
    print("=" * 60)
    print("🚀 INICIANDO INTERFACE GRÁFICA DO TCC (STREAMLIT)...")
    print(f"Interpretador Utilizado: {sys.executable}")
    print("=" * 60)
    
    try:
        # Usa sys.argv[0] para apontar dinamicamente para o próprio main.py
        subprocess.run([sys.executable, "-m", "streamlit", "run", sys.argv[0]])
    except Exception as e:
        print(f"❌ Erro ao tentar iniciar o Streamlit automaticamente: {e}")
        print("Por favor, tente executar manualmente com o comando:")
        print(f"streamlit run {sys.argv[0]}")
    sys.exit()

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# Importação dos módulos internos refinados
import data_loader
from forecaster import MaterialForecaster
import post_processing

# =================================================================
# UI/UX: CONFIGURAÇÃO DE TEMA E ESTILO PREMIUM
# =================================================================
st.set_page_config(
    page_title="Supply Chain Ergonômico - TCC UNIP",
    page_icon="🖥️",
    layout="wide"
)

# CSS Customizado: Dark Slate Theme
st.markdown("""
    <style>
    .main { background-color: #0f172a; color: #f8fafc; }
    .stMetric {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricValue"] { color: #38bdf8; font-weight: 800; }
    div[data-testid="stMetricLabel"] { color: #94a3b8; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #1e293b; border-radius: 8px 8px 0px 0px;
        color: #94a3b8; font-weight: 600; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a8a !important; color: #38bdf8 !important;
        border-bottom: 3px solid #38bdf8 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# ORQUESTRADOR DO PIPELINE
# =================================================================
def main():
    st.sidebar.title("🖥️ Configurações do TCC")
    st.sidebar.info("Tema: ML na Previsão de Demanda de Materiais de Escritório e Indiretos Ergonômicos")
    
    # 1. Carregamento de Dados
    source = st.sidebar.radio("Origem dos Dados:", ["Sintético (Padrão)", "Upload Excel/CSV"])
    
    if source == "Sintético (Padrão)":
        df_consumo, df_colaboradores = data_loader.generate_synthetic_data()
        st.sidebar.success("Dados sintéticos ativos.")
    else:
        file_c = st.sidebar.file_uploader("Histórico de Consumo", type=['xlsx', 'csv'])
        file_e = st.sidebar.file_uploader("Cadastro de RH", type=['xlsx', 'csv'])
        if file_c and file_e:
            df_consumo, df_colaboradores = data_loader.load_from_excel(file_c, file_e)
        else:
            st.warning("Aguardando upload. Usando sintéticos.")
            df_consumo, df_colaboradores = data_loader.generate_synthetic_data()

    # 2. Parâmetros do Modelo
    st.sidebar.markdown("---")
    st.sidebar.subheader("Hiperparâmetros RF")
    n_trees = st.sidebar.slider("Árvores (Estimators)", 50, 500, 100)
    depth = st.sidebar.slider("Profundidade Máxima", 2, 20, 10)

    # 3. Execução do ML
    try:
        forecaster = MaterialForecaster(n_estimators=n_trees, max_depth=depth)
        mae, X_test, y_test, y_pred = forecaster.train(df_consumo)
        df_future = forecaster.predict_next_3_months(df_consumo)
        df_inclusive = post_processing.apply_inclusive_rules(df_future, df_colaboradores)
        
        # TÍTULO E CARDS
        st.title("🖥️ Previsão de Demanda: Materiais de Escritório & Ergonomia")
        st.markdown("#### Protótipo de TCC - UNIP São José do Rio Preto")
        
        c1, c2, c3, c4 = st.columns(4)
        total_prev = df_inclusive['Previsao_Bruta'].sum()
        total_active = len(df_colaboradores)
        pcd_rate = (len(df_colaboradores[df_colaboradores['Restricao_Ergonomica'] != "Nenhuma"]) / total_active) * 100
        
        c1.metric("Previsão Bruta (90d)", f"{total_prev} un.")
        c2.metric("Acurácia (MAE)", f"{mae:.2f}")
        c3.metric("Colaboradores Ativos", total_active)
        c4.metric("Taxa de Inclusão/NR-17", f"{pcd_rate:.1f}%")

        # ABAS
        tab1, tab2, tab3, tab4 = st.tabs(["📈 ML & Projeções", "♿ Relatório Ergonômico", "📄 Fundamentação Teórica", "📂 Database"])

        with tab1:
            st.subheader("Análise Preditiva de Consumo")
            
            # Gráfico de Validação (Real vs Predito no Teste)
            fig_val = go.Figure()
            fig_val.add_trace(go.Scatter(y=y_test.values, name="Real", line=dict(color="#1e3a8a", width=2)))
            fig_val.add_trace(go.Scatter(y=y_pred, name="Previsto", line=dict(color="#38bdf8", dash='dash')))
            fig_val.update_layout(title="Validação do Modelo (Conjunto de Teste)", template="plotly_dark")
            st.plotly_chart(fig_val, use_container_width=True)
            
            # Gráfico de Barras Projeção
            df_grouped = df_future.groupby('Material')['Previsao_Bruta'].sum().reset_index()
            fig_bar = px.bar(df_grouped, x='Material', y='Previsao_Bruta', color='Material', 
                             title="Volume Previsto por Material (Próximos 3 Meses)", template="plotly_dark")
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab2:
            st.subheader("Relatório de Adequação Ergonômica (NR-17)")
            st.info("Ajustes automáticos baseados nas necessidades de saúde ocupacional mapeadas pelo RH.")
            st.dataframe(df_inclusive, use_container_width=True)
            
            # KPI de Itens Adaptados
            total_adaptados = df_inclusive['Itens_Adaptados_Extra'].sum()
            st.success(f"🛡️ Total de itens adaptados/ergonômicos identificados: {total_adaptados} unidades para conformidade NR-17.")

        with tab3:
            st.subheader("Fundamentação Teórica & ESG")
            st.markdown("""
            **Contextualização do Software:**
            Este sistema integra a previsão de demanda (Machine Learning) com as diretrizes da **NR-17 (Ergonomia)** e pilares **ESG (Environmental, Social, and Governance)**.
            
            **Principais Conceitos:**
            1. **Previsão de Demanda:** Utiliza Random Forest para evitar o excesso de estoque e obsolescência de materiais administrativos.
            2. **NR-17:** O sistema identifica proativamente colaboradores com diagnósticos de LER/DORT ou deficiências visuais, ajustando a ordem de compra para incluir mouses verticais e teclados adaptados.
            3. **Supply Chain Inclusivo:** Garante que a acessibilidade não seja uma exceção, mas parte do fluxo automatizado de suprimentos.
            
            **Arquitetura:**
            - **Backend:** Random Forest Regressor para séries temporais.
            - **Filtro Inclusivo:** Algoritmo prescritivo que cruza `Material` vs `Restrição Ergonômica`.
            """)
            st.latex(r"MAE = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|")

        with tab4:
            st.subheader("Inspecionar Bases de Dados")
            st.write("**Histórico de Consumo Administrativo:**")
            st.dataframe(df_consumo.head(100), use_container_width=True)
            st.write("**Cadastro de Colaboradores (Saúde Ocupacional):**")
            st.dataframe(df_colaboradores, use_container_width=True)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
