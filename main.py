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
        sys.exit()
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
# PERSISTÊNCIA DAS BASES DE DADOS EM MEMÓRIA (SESSION STATE)
# =================================================================
# Inicializa as bases de dados apenas uma vez no início da sessão
if 'df_consumo' not in st.session_state or 'df_colaboradores' not in st.session_state:
    df_c_init, df_e_init = data_loader.generate_synthetic_data()
    st.session_state.df_consumo = df_c_init
    st.session_state.df_colaboradores = df_e_init

if 'produtos' not in st.session_state:
    st.session_state.produtos = [
        {"Material": "Canetas e Escrita", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Escrita e Marcadores"},
        {"Material": "Post-it e Clipes", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Mesa e Documentação"},
        {"Material": "Grampeadores e Tesouras", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Mesa e Documentação"},
        {"Material": "Pastas e Caixas", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Organização Física"},
        {"Material": "Papel Sulfite", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Organização Física"},
        {"Material": "Rotulador Brother Eletrônico", "Categoria": "Papelaria e Organização de Mesa", "Subcategoria": "Identificação"},
        {"Material": "Toners e Cartuchos", "Categoria": "Equipamentos e Suprimentos", "Subcategoria": "Impressão"},
        {"Material": "Mouses e Teclados", "Categoria": "Equipamentos e Suprimentos", "Subcategoria": "Informática Básica"},
        {"Material": "Fragmentadoras de Papel", "Categoria": "Equipamentos e Suprimentos", "Subcategoria": "Segurança e Manutenção"},
        {"Material": "Cadeiras Giratórias Ergonômicas", "Categoria": "Móveis Essenciais", "Subcategoria": "Postura e Conforto"},
        {"Material": "Mesas de Escritório", "Categoria": "Móveis Essenciais", "Subcategoria": "Área de Trabalho"},
        {"Material": "Gaveteiros e Armários", "Categoria": "Móveis Essenciais", "Subcategoria": "Armazenamento"},
    ]

# =================================================================
# BARRA LATERAL: CENTRAL DE SIMULAÇÃO
# =================================================================
st.sidebar.title("🖥️ Central de Simulação")
st.sidebar.info("Tema: ML na Previsão de Demanda de Materiais de Escritório e Indiretos Ergonômicos")

# 1. Formulário para Adicionar Novo Material (Simulação Reativa)
with st.sidebar.form("form_novo_material"):
    st.subheader("➕ Simular Novo Material")
    novo_mat = st.text_input("Nome do Material", placeholder="Ex: Telas de Proteção")
    
    # Busca setores dinamicamente da base persistente
    setores_disp = st.session_state.df_colaboradores['Setor'].unique()
    setor_selecionado = st.selectbox("Setor Alocado", setores_disp)
    
    # Consumo médio desejado para a simulação de Poisson
    consumo_medio = st.slider("Consumo Médio Desejado (Unidades)", 10, 500, 50)
    
    submitted = st.form_submit_button("Gerar Histórico e Treinar IA")
    
    if submitted:
        if novo_mat:
            # Geração de 24 meses de histórico decrescente
            historico_novo = []
            hoje = datetime.now().replace(day=1)
            
            for i in range(24):
                # Calcula a data retroativa
                data_mes = hoje - pd.DateOffset(months=i)
                
                # Lógica de Poisson: Quantidade = np.random.poisson(consumo_medio)
                quantidade = np.random.poisson(consumo_medio)
                
                historico_novo.append({
                    'Data': data_mes,
                    'Ano': data_mes.year,
                    'Mes': data_mes.month,
                    'Material': novo_mat,
                    'Categoria': 'Simulação',
                    'Subcategoria': 'Novos Itens',
                    'Setor': setor_selecionado,
                    'Quantidade_Consumida': quantidade
                })
            
            # Concatena o novo histórico na base em memória
            df_novo = pd.DataFrame(historico_novo)
            st.session_state.df_consumo = pd.concat([st.session_state.df_consumo, df_novo], ignore_index=True)
            
            # Adiciona ao catálogo para visualização em gráficos
            st.session_state.produtos.append({
                "Material": novo_mat,
                "Categoria": "Simulação",
                "Subcategoria": "Novos Itens"
            })
            
            st.sidebar.success(f"Sucesso! 24 meses de dados gerados para '{novo_mat}'.")
            st.rerun()
        else:
            st.error("Por favor, preencha o nome do material.")

# 2. Hiperparâmetros do Modelo (Sidebar)
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Parâmetros de Machine Learning")
n_trees = st.sidebar.slider("Árvores (Estimators)", 50, 500, 100)
depth = st.sidebar.slider("Profundidade Máxima", 2, 20, 10)

# =================================================================
# ORQUESTRADOR DO PIPELINE PRINCIPAL
# =================================================================
def main():
    try:
        # Consome os dados diretamente do Session State
        df_consumo = st.session_state.df_consumo
        df_colaboradores = st.session_state.df_colaboradores

        # Função de Treinamento com Cache de Recurso para otimização
        @st.cache_resource
        def run_ml_pipeline(df_c, df_colabs, _n_trees, _depth):
            forecaster = MaterialForecaster(n_estimators=_n_trees, max_depth=_depth)
            mae, X_test, y_test, y_pred = forecaster.train(df_c)
            df_future = forecaster.predict_next_3_months(df_c)
            df_inclusive = post_processing.apply_inclusive_rules(df_future, df_colabs)
            return mae, X_test, y_test, y_pred, df_future, df_inclusive

        mae, X_test, y_test, y_pred, df_future, df_inclusive = run_ml_pipeline(
            df_consumo, df_colaboradores, n_trees, depth
        )
        
        # TÍTULO E CARDS DE KPI (PAINEL SUPERIOR)
        st.title("🖥️ Supply Chain Inteligente & Ergonomia")
        st.markdown("#### Protótipo de TCC - Central de Simulação UNIP")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        total_prev = df_inclusive['Previsao_Bruta'].sum()
        total_active = len(df_colaboradores)
        pcd_rate = (len(df_colaboradores[df_colaboradores['Restricao_Ergonomica'] != "Nenhuma"]) / total_active) * 100
        total_adaptados = df_inclusive['Quantidade_Especial'].sum() if 'Quantidade_Especial' in df_inclusive.columns else 0
        
        c1.metric("Previsão Bruta (90d)", f"{total_prev} un.")
        c2.metric("Acurácia (MAE)", f"{mae:.2f}")
        c3.metric("Colaboradores Ativos", total_active)
        c4.metric("Taxa de Inclusão", f"{pcd_rate:.1f}%")
        c5.metric("Itens Adaptados", f"{total_adaptados} un.")

        # ABAS DE NAVEGAÇÃO
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Dashboard Preditivo", 
            "♿ Relatório Ergonômico", 
            "📄 Fundamentação Teórica", 
            "�️ Central de Edição de Dados"
        ])

        with tab1:
            st.subheader("Análise Preditiva de Consumo (Random Forest)")
            
            # Gráfico de Validação: Real vs Predito
            fig_val = go.Figure()
            fig_val.add_trace(go.Scatter(y=y_test.values, name="Real", line=dict(color="#1e3a8a", width=2)))
            fig_val.add_trace(go.Scatter(y=y_pred, name="Previsto", line=dict(color="#38bdf8", dash='dash')))
            fig_val.update_layout(title="Validação do Modelo (Conjunto de Teste)", template="plotly_dark")
            st.plotly_chart(fig_val, use_container_width=True)
            
            # Gráfico de Projeção Trimestral
            df_portfolio = pd.DataFrame(st.session_state.produtos)
            df_plot = df_future.merge(df_portfolio, on="Material", how="left").fillna("Simulado")
            
            fig_bar = px.bar(df_plot, x='Categoria', y='Previsao_Bruta', color='Subcategoria', 
                             barmode='group', title="Projeção Trimestral por Segmento", 
                             template="plotly_dark", hover_data=['Material'])
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab2:
            st.subheader("Relatório de Adequação Ergonômica (NR-17)")
            st.info("Ajustes automáticos baseados nas necessidades mapeadas pelo RH.")
            st.dataframe(df_inclusive, use_container_width=True)
            st.success(f"🛡️ Total de itens adaptados/ergonômicos identificados: {total_adaptados} unidades.")

        with tab3:
            st.subheader("Fundamentação Teórica & ESG")
            st.markdown("""
            **Capítulo 3: Desenvolvimento do Artefato Tecnológico**
            
            Este sistema integra a previsão de demanda (Machine Learning) com as diretrizes da **NR-17 (Ergonomia)** e pilares **ESG**.
            
            1. **Otimização de Recursos:** A IA evita o excesso de estoque, reduzindo custos e impacto ambiental.
            2. **Conformidade Legal:** O algoritmo cruza dados de RH para garantir que o material adequado (ex: Mouse Vertical) chegue ao colaborador com LER/DORT.
            3. **Supply Chain Inclusivo:** A tecnologia como facilitadora da acessibilidade corporativa.
            """)
            st.latex(r"MAE = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|")

        with tab4:
            st.subheader("🛠️ Central de Edição de Dados (Grid Interativa)")
            st.warning("Abaixo você pode editar as bases diretamente no estilo Excel. Clique no botão ao final para re-treinar a IA.")
            
            col_ed1, col_ed2 = st.columns(2)
            
            with col_ed1:
                st.write("**📝 Editar Histórico de Consumo**")
                # Editor interativo para consumo
                edited_consumo = st.data_editor(
                    st.session_state.df_consumo,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="editor_consumo"
                )
                
            with col_ed2:
                st.write("**👥 Editar Cadastro de RH**")
                # Editor interativo para colaboradores
                edited_colaboradores = st.data_editor(
                    st.session_state.df_colaboradores,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="editor_colaboradores"
                )
            
            # Botão para consolidar alterações e forçar re-treinamento
            if st.button("💾 Salvar Alterações e Re-treinar IA", use_container_width=True):
                # Sobrescreve as variáveis persistentes com os dados da grade
                st.session_state.df_consumo = edited_consumo
                st.session_state.df_colaboradores = edited_colaboradores
                
                # Limpa o cache para que o pipeline de ML execute novamente com novos dados
                st.cache_resource.clear()
                
                st.success("Alterações salvas! Re-treinando modelos preditivos...")
                st.rerun()

    except Exception as e:
        st.error(f"Erro no processamento do pipeline: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
