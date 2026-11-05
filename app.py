import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
import time
from pathlib import Path

# =================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO (UI/UX DESIGN)
# =================================================================
st.set_page_config(
    page_title="Supply Chain Inclusivo - TCC UNIP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização clara para captura e impressão
st.markdown("""
    <style>
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stMain"] {
        background-color: #ffffff;
        color: #111111;
    }
    [data-testid="stSidebar"] {
        background-color: #f5f5f5;
        border-right: 1px solid #cccccc;
    }
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] h1,
    [data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3,
    [data-testid="stAppViewContainer"] h4,
    [data-testid="stAppViewContainer"] h5,
    [data-testid="stAppViewContainer"] h6,
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] {
        color: #111111;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
        color: #111111;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1rem;
        color: #444444;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #b8b8b8;
        box-shadow: none;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #f2f2f2;
        border-radius: 8px 8px 0px 0px;
        color: #333333;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #111111 !important;
        border-bottom: 3px solid #333333 !important;
    }
    [data-baseweb="select"] > div,
    [data-baseweb="select"] input {
        background-color: #ffffff !important;
        color: #111111 !important;
        border-color: #999999 !important;
    }
    [data-testid="stAlert"] {
        background-color: #f2f2f2;
        border: 1px solid #bbbbbb;
    }
    button[data-testid="stBaseButton-primary"] {
        background-color: #333333;
        color: #ffffff;
        border-color: #333333;
    }
    .js-plotly-plot .bg { fill: #ffffff !important; }
    .js-plotly-plot .gtitle,
    .js-plotly-plot .xtick text,
    .js-plotly-plot .ytick text,
    .js-plotly-plot .legend text {
        fill: #111111 !important;
    }
    .js-plotly-plot .gridlayer path { stroke: #dddddd !important; }
    @media print {
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stSidebar"] {
            background: #ffffff !important;
            color: #000000 !important;
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
        }
        [data-testid="stSidebar"] { border-right: 1px solid #999999; }
        .stMetric { box-shadow: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. GERAÇÃO DE DADOS SINTÉTICOS (BACKEND)
# =================================================================

@st.cache_data
def generate_synthetic_data():
    """
    Gera dados de consumo históricos e cadastro de RH para simulação.
    Utiliza Distribuição de Poisson e lógica de sazonalidade.
    """
    # 2.1 Histórico de Consumo (24 meses)
    dates = pd.date_range(end=datetime.now(), periods=24, freq='MS')
    epis = ['Luva Nitrílica G', 'Luva Nitrílica M', 'Bota de Segurança', 'Óculos de Proteção']
    setores = ['Produção', 'Logística', 'Manutenção', 'Qualidade']
    
    data = []
    for date in dates:
        # Lógica de Sazonalidade (Ex: Aumento no inverno para certos itens)
        # Usamos uma função seno para oscilar a demanda ao longo do ano
        seasonality = 1 + 0.2 * np.sin(2 * np.pi * (date.month - 1) / 12)
        
        for epi in epis:
            base_demand = {
                'Luva Nitrílica G': 60, 
                'Luva Nitrílica M': 55, 
                'Bota de Segurança': 15, 
                'Óculos de Proteção': 20
            }[epi]
            
            for setor in setores:
                # Distribuição de Poisson para simular flutuações reais
                # Lambda da Poisson = base * sazonalidade * fator_setor
                setor_factor = {'Produção': 1.5, 'Logística': 1.0, 'Manutenção': 0.8, 'Qualidade': 0.5}[setor]
                avg_demand = base_demand * seasonality * setor_factor
                demand = np.random.poisson(avg_demand)
                data.append([date, epi, setor, demand])
    
    df_history = pd.DataFrame(data, columns=['Data', 'EPI', 'Setor', 'Quantidade'])
    
    # 2.2 Cadastro de RH Inclusivo (150 Colaboradores)
    n_colabs = 150
    pcd_rate = 0.08 # 8% conforme solicitado
    
    colaboradores = []
    for i in range(n_colabs):
        is_pcd = np.random.random() < pcd_rate
        restricao = "Nenhuma"
        lado = "N/A"
        
        if is_pcd:
            tipo = np.random.choice([
                "Amputação Mão Esquerda", 
                "Amputação Mão Direita", 
                "Calçado Ortopédico (Impacto)", 
                "Amputação Parcial de Dedos"
            ])
            restricao = tipo
            if "Esquerda" in tipo: lado = "Esquerdo"
            elif "Direita" in tipo: lado = "Direito"
            else: lado = "Ambos"

        colaboradores.append({
            'ID': f'ID-{1000+i}',
            'Nome': f'Colaborador {i+1}',
            'Setor': np.random.choice(setores),
            'Tamanho_Luva': np.random.choice(['P', 'M', 'G', 'GG']),
            'Tamanho_Bota': np.random.randint(35, 45),
            'PCD': 'Sim' if is_pcd else 'Não',
            'Restricao_Ergonomica': restricao,
            'Lado_Afetado': lado
        })
    
    df_rh = pd.DataFrame(colaboradores)
    return df_history, df_rh

# =================================================================
# 3. MOTOR DE INTELIGÊNCIA ARTIFICIAL (MACHINE LEARNING)
# =================================================================

def run_ml_pipeline(df_history, target_epi, n_estimators, max_depth):
    """
    Treina o Random Forest e gera previsões para os próximos 3 meses.
    """
    try:
        # Agregando por mês para o EPI alvo
        df = df_history[df_history['EPI'] == target_epi].groupby('Data')['Quantidade'].sum().reset_index()
        df = df.sort_values('Data')

        # Feature Engineering (Engenharia de Atributos)
        df['Mes'] = df['Data'].dt.month
        df['Ano'] = df['Data'].dt.year
        df['Lag_1'] = df['Quantidade'].shift(1)
        df['Lag_2'] = df['Quantidade'].shift(2)
        
        df_ml = df.dropna().copy()
        
        # Variáveis preditoras e alvo
        X = df_ml[['Mes', 'Ano', 'Lag_1', 'Lag_2']]
        y = df_ml['Quantidade']
        
        # Divisão Temporal (80% treino, 20% teste)
        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        
        # Modelo Random Forest Regressor
        model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        model.fit(X_train, y_train)
        
        # Métricas
        preds_test = model.predict(X_test)
        mae_rf = mean_absolute_error(y_test, preds_test)
        
        # Baseline (Média Móvel de 3 meses)
        baseline = df['Quantidade'].rolling(window=3).mean().shift(1).iloc[X_test.index]
        mae_base = mean_absolute_error(y_test, baseline.fillna(y_train.mean()))
        
        # Previsão Recursiva (Próximos 3 meses)
        future_dates = []
        future_preds = []
        
        last_row = df.iloc[-1]
        curr_qty = last_row['Quantidade']
        curr_lag1 = last_row['Lag_1']
        curr_date = last_row['Data']
        
        for _ in range(3):
            next_date = curr_date + pd.DateOffset(months=1)
            features = pd.DataFrame([[next_date.month, next_date.year, curr_qty, curr_lag1]], 
                                    columns=['Mes', 'Ano', 'Lag_1', 'Lag_2'])
            
            pred = model.predict(features)[0]
            future_dates.append(next_date)
            future_preds.append(round(pred))
            
            # Atualiza estados para o próximo mês
            curr_lag1 = curr_qty
            curr_qty = pred
            curr_date = next_date
            
        df_future = pd.DataFrame({'Data': future_dates, 'Previsao': future_preds})
        
        return df, df_future, mae_rf, mae_base
    
    except Exception as e:
        st.error(f"Erro no pipeline de ML: {e}")
        return None, None, 0, 0

# =================================================================
# 4. INTERFACE STREAMLIT (UI PRINCIPAL)
# =================================================================

def main():
    # BARRA LATERAL (SIDEBAR)
    st.sidebar.image(
        str(Path(__file__).resolve().parent / "assets" / "logo-unip.webp"),
        width=150,
    )
    st.sidebar.title("Configurações")
    
    data_mode = st.sidebar.selectbox(
        "Origem dos Dados:",
        ["1. Simular Dados de Teste (NumPy)", "2. Carregar Planilha Excel Real (Pandas)"]
    )
    
    if "1." in data_mode:
        df_history, df_rh = generate_synthetic_data()
        st.sidebar.success("✅ Dados Sintéticos Ativos")
    else:
        up_hist = st.sidebar.file_uploader("Histórico de Consumo (.xlsx)", type=['xlsx'])
        up_rh = st.sidebar.file_uploader("Cadastro de RH (.xlsx)", type=['xlsx'])
        
        if up_hist and up_rh:
            df_history = pd.read_excel(up_hist)
            df_rh = pd.read_excel(up_rh)
            st.sidebar.success("✅ Arquivos Carregados")
        else:
            st.sidebar.info("Aguardando upload. Usando dados de teste...")
            df_history, df_rh = generate_synthetic_data()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Ajuste do Modelo (RF)")
    n_trees = st.sidebar.slider("Nº de Árvores:", 10, 200, 100)
    max_d = st.sidebar.slider("Profundidade Máxima:", 2, 20, 10)
    
    selected_epi = st.sidebar.selectbox("EPI para Análise:", df_history['EPI'].unique())

    # CABEÇALHO PRINCIPAL
    st.title("🛡️ Supply Chain Inclusivo: Previsão & Ergonomia")
    st.markdown("##### Protótipo de TCC - Ciência da Computação - UNIP São José do Rio Preto")
    
    # Executar Inteligência Artificial
    df_hist_plot, df_pred, mae_rf, mae_base = run_ml_pipeline(df_history, selected_epi, n_trees, max_d)
    
    if df_hist_plot is not None:
        # CARDS DE MÉTRICAS (TOP)
        m1, m2, m3, m4 = st.columns(4)
        
        total_prev = df_pred['Previsao'].sum()
        precisao_ganho = ((mae_base - mae_rf) / mae_base) * 100
        total_colabs = len(df_rh)
        taxa_inc = (len(df_rh[df_rh['PCD'] == 'Sim']) / total_colabs) * 100
        
        m1.metric("Volume Previsto (3m)", f"{int(total_prev)} un.")
        m2.metric("Ganho de Precisão", f"{precisao_ganho:.1f}%", delta=f"-{mae_rf:.2f} MAE", delta_color="inverse")
        m3.metric("Total Colaboradores", total_colabs)
        m4.metric("Taxa de Inclusão", f"{taxa_inc:.1f}%")

        # ABAS DE CONTEÚDO
        tab1, tab2, tab3 = st.tabs(["📈 Previsão de Demanda (ML)", "♿ Ergonomia & Inclusão (RH)", "📂 Base de Dados Bruta"])

        with tab1:
            st.subheader(f"Projeção de Consumo: {selected_epi}")
            
            # Gráfico Plotly: Histórico vs Previsão
            fig = go.Figure()
            
            # Linha histórica sólida e previsão tracejada para diferenciar na impressão.
            fig.add_trace(go.Scatter(
                x=df_hist_plot['Data'], y=df_hist_plot['Quantidade'],
                name='Consumo Real', line=dict(color='#222222', width=3),
                mode="lines+markers", marker=dict(symbol="circle")
            ))
            
            # Conectar o último ponto real ao primeiro previsto
            full_dates = [df_hist_plot['Data'].iloc[-1]] + list(df_pred['Data'])
            full_preds = [df_hist_plot['Quantidade'].iloc[-1]] + list(df_pred['Previsao'])
            
            fig.add_trace(go.Scatter(
                x=full_dates, y=full_preds,
                name='Previsão (IA)', line=dict(color='#777777', width=3, dash='dot'),
                mode="lines+markers", marker=dict(symbol="x")
            ))
            
            fig.update_layout(
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color="#111111",
                xaxis_title="Meses",
                yaxis_title="Quantidade",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True, theme=None)
            
            st.write("#### Detalhamento da Previsão")
            st.table(df_pred.assign(Data=df_pred['Data'].dt.strftime('%m/%Y')))

        with tab2:
            st.subheader("Análise de Acessibilidade e Relatório Inteligente")
            
            c1, c2 = st.columns([1, 2])
            
            with c1:
                # Gráfico de Pizza: Restrições
                restricoes_counts = df_rh[df_rh['PCD'] == 'Sim']['Restricao_Ergonomica'].value_counts()
                fig_pcd = px.pie(
                    values=restricoes_counts.values, 
                    names=restricoes_counts.index,
                    title="Perfil de Restrições na Planta",
                    hole=0.4,
                    color_discrete_sequence=["#222222", "#555555", "#888888", "#bbbbbb"]
                )
                fig_pcd.update_layout(
                    template="plotly_white",
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font_color="#111111",
                )
                st.plotly_chart(fig_pcd, use_container_width=True, theme=None)
            
            with c2:
                st.info("💡 **Relatório de Compras Customizado:** O sistema ajusta o volume bruto previsto para atender necessidades específicas, reduzindo desperdício de pares completos.")
                
                # Lógica Inclusiva (Exemplo para Luvas)
                if "Luva" in selected_epi:
                    pcds_luva = df_rh[(df_rh['PCD'] == 'Sim') & (df_rh['Restricao_Ergonomica'].str.contains("Amputação"))]
                    esq = len(pcds_luva[pcds_luva['Lado_Afetado'] == 'Direito']) # Usa só a esquerda
                    dir = len(pcds_luva[pcds_luva['Lado_Afetado'] == 'Esquerdo']) # Usa só a direita
                    
                    st.write(f"**Recomendação de Mix de Compra ({selected_epi}):**")
                    for _, row in df_pred.iterrows():
                        vol = int(row['Previsao'])
                        st.write(f"- **{row['Data'].strftime('%m/%Y')}**: Comprar {vol - (esq+dir)} pares completos + {esq} luvas avulsas (ESQ) + {dir} luvas avulsas (DIR).")
                else:
                    st.write("**Recomendação:** Seguir volume previsto. Para calçados PCD, verificar medidas ortopédicas no RH.")

        with tab3:
            st.subheader("Dados de Suporte")
            st.write("**Histórico de Consumo (Amostra):**")
            st.dataframe(df_history.head(10), use_container_width=True)
            st.write("**Cadastro de RH (Amostra):**")
            st.dataframe(df_rh.head(10), use_container_width=True)

    # RODAPÉ
    st.markdown("---")
    st.markdown(f"© {datetime.now().year} - TCC UNIP - Ciência da Computação - Engenharia de Dados & IA")

if __name__ == "__main__":
    main()
