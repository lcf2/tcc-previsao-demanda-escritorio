import sys
import os
import subprocess
import json
import hashlib
import shutil
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
from benchmark import benchmark_request_payload, run_random_forest_benchmark
from forecaster import MaterialForecaster
import post_processing


def build_seasonal_forecast(history, horizon=12):
    monthly = history.copy()
    monthly["Data"] = pd.to_datetime(monthly["Data"]).dt.to_period("M").dt.to_timestamp()
    monthly = (
        monthly.groupby(["Setor", "Material", "Data"], as_index=False)[
            "Quantidade_Consumida"
        ]
        .sum()
        .sort_values(["Setor", "Material", "Data"])
    )
    observed = {
        (row.Setor, str(row.Material), row.Data): float(row.Quantidade_Consumida)
        for row in monthly.itertuples(index=False)
    }
    series = monthly[["Setor", "Material"]].drop_duplicates()
    future_dates = pd.date_range(
        monthly["Data"].max() + pd.offsets.MonthBegin(1),
        periods=horizon,
        freq="MS",
    )
    forecasts = []
    for date in future_dates:
        reference_date = date - pd.DateOffset(years=1)
        for row in series.itertuples(index=False):
            material = str(row.Material)
            forecasts.append({
                "Data": date,
                "Setor": row.Setor,
                "Material": material,
                "Data_Referencia": reference_date,
                "Quantidade_Referencia": observed.get(
                    (row.Setor, material, reference_date),
                    0.0,
                ),
            })
    return pd.DataFrame(forecasts)


# =================================================================
# UI/UX: CONFIGURAÇÃO DE TEMA E ESTILO PREMIUM
# =================================================================
st.set_page_config(
    page_title="Supply Chain Ergonômico - TCC UNIP",
    page_icon="🖥️",
    layout="wide"
)


@st.cache_resource
def _csharp_service_start_lock():
    return threading.Lock()


def ensure_local_csharp_service(endpoint):
    parsed_endpoint = urlparse(endpoint)
    if not (
        parsed_endpoint.scheme == "http"
        and parsed_endpoint.hostname in {"localhost", "127.0.0.1"}
        and parsed_endpoint.port == 5202
    ):
        return False

    health_url = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}/api/meta"

    def is_available():
        try:
            with urlopen(health_url, timeout=2):
                return True
        except HTTPError as error:
            raise RuntimeError(
                f"O serviço C# respondeu com HTTP {error.code} no endpoint de saúde."
            ) from error
        except URLError:
            return False

    if is_available():
        return False

    with _csharp_service_start_lock():
        if is_available():
            return False

        dotnet = shutil.which("dotnet")
        if dotnet is None:
            raise RuntimeError(
                "O dashboard C# não está ativo e o comando 'dotnet' não foi encontrado. "
                "Instale o SDK .NET ou inicie o C# manualmente."
            )

        project_dir = Path(__file__).resolve().parent / "projeto_benchmark_csharp"
        project_file = project_dir / "TccBenchmark.csproj"
        command = [
            dotnet,
            "run",
            "--project",
            str(project_file),
            "--no-launch-profile",
            "--urls",
            f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}",
        ]
        try:
            process = subprocess.Popen(command, cwd=project_dir)
        except OSError as error:
            raise RuntimeError(f"Não foi possível iniciar o serviço C#: {error}") from error

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    "O serviço C# encerrou durante a inicialização "
                    f"(código {process.returncode}). Confira a saída do terminal."
                )
            if is_available():
                return True
            time.sleep(0.5)

        raise TimeoutError(
            "O serviço C# não ficou pronto em 60 segundos. "
            "Confira a saída do terminal para ver o erro de inicialização."
        )


# CSS para impressão e captura em escala de cinza
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
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #b8b8b8;
        box-shadow: none;
    }
    div[data-testid="stMetricValue"] { color: #111111; font-weight: 800; }
    div[data-testid="stMetricLabel"] { color: #444444; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #f2f2f2; border-radius: 8px 8px 0px 0px;
        color: #333333; font-weight: 600; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important; color: #111111 !important;
        border-bottom: 3px solid #333333 !important;
    }
    [data-testid="stDataFrame"],
    [data-testid="stTable"] { background-color: #ffffff; }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
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
# PERSISTÊNCIA DAS BASES DE DADOS EM MEMÓRIA (SESSION STATE)
# =================================================================
# Inicializa os dados de teste uma vez para permitir alternar entre as fontes.
if 'df_consumo_sintetico' not in st.session_state:
    df_c_init, df_e_init = data_loader.generate_synthetic_data()
    st.session_state.df_consumo_sintetico = df_c_init
    st.session_state.df_colaboradores_sinteticos = df_e_init
    st.session_state.modo_dados_aplicado = "Dados sintéticos"

if 'df_consumo' not in st.session_state or 'df_colaboradores' not in st.session_state:
    df_c_init = st.session_state.df_consumo_sintetico
    df_e_init = st.session_state.df_colaboradores_sinteticos
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

if 'produtos_sinteticos' not in st.session_state:
    st.session_state.produtos_sinteticos = [dict(produto) for produto in st.session_state.produtos]

if st.session_state.get("benchmark_result_version") != 6:
    st.session_state.pop("resultado_benchmark", None)
    st.session_state["benchmark_result_version"] = 6

# =================================================================
# BARRA LATERAL: CENTRAL DE SIMULAÇÃO
# =================================================================
st.sidebar.image(
    str(Path(__file__).resolve().parent / "assets" / "logo-unip.webp"),
    width=150,
)
st.sidebar.title("🖥️ Central de Simulação")
st.sidebar.info("Tema: ML na Previsão de Demanda de Materiais de Escritório e Indiretos Ergonômicos")

arquivo_local = Path(__file__).resolve().parent / "dados_privados" / "base_real.xlsx"
modo_dados = st.sidebar.selectbox(
    "Origem dos dados",
    ["Dados sintéticos", "Planilha Excel real"],
    index=1 if arquivo_local.is_file() else 0,
    key="modo_dados"
)

if modo_dados == "Dados sintéticos":
    if st.session_state.modo_dados_aplicado != modo_dados:
        st.session_state.df_consumo = st.session_state.df_consumo_sintetico.copy()
        st.session_state.df_colaboradores = st.session_state.df_colaboradores_sinteticos.copy()
        st.session_state.produtos = [dict(produto) for produto in st.session_state.produtos_sinteticos]
        st.session_state.modo_dados_aplicado = modo_dados
        st.session_state.pop("resultado_benchmark", None)
    dados_reais_ativos = False
    st.sidebar.success("Dados sintéticos ativos")
else:
    arquivo_excel = st.sidebar.file_uploader(
        "Arquivo Excel completo (.xlsx)",
        type=["xlsx"],
        key="arquivo_planilha9"
    )
    if arquivo_excel is not None or arquivo_local.is_file():
        try:
            if arquivo_excel is not None:
                conteudo_arquivo = arquivo_excel.getvalue()
                fingerprint = hashlib.sha256(conteudo_arquivo).hexdigest()
                arquivo_para_importar = arquivo_excel
            else:
                with arquivo_local.open("rb") as arquivo:
                    conteudo_arquivo = arquivo.read()
                fingerprint = hashlib.sha256(conteudo_arquivo).hexdigest()
                arquivo_para_importar = arquivo_local
            df_real, df_rh_real = data_loader.load_real_consumption_excel(
                arquivo_para_importar
            )
        except (ValueError, ImportError, OSError) as error:
            st.sidebar.error(f"Não foi possível importar a planilha: {error}")
            st.stop()

        if st.session_state.get("arquivo_benchmark_fingerprint") != fingerprint:
            st.session_state.pop("resultado_benchmark", None)
            st.session_state["arquivo_benchmark_fingerprint"] = fingerprint
        st.session_state.df_consumo = df_real
        st.session_state.df_colaboradores = df_rh_real
        st.session_state.produtos = (
            df_real[["Material", "Categoria", "Subcategoria"]]
            .drop_duplicates()
            .to_dict("records")
        )
        st.session_state.modo_dados_aplicado = modo_dados
    elif st.session_state.modo_dados_aplicado != modo_dados:
        st.sidebar.info(
            "Envie o Excel acima ou coloque uma planilha em "
            "'dados_privados\\base_real.xlsx' para carregar os dados reais."
        )
        st.stop()

    dados_reais_ativos = True
    fonte_dados = st.session_state.df_consumo.attrs.get("fonte_importacao", "")
    rotulo_fonte = (
        "movimentações SAP"
        if str(fonte_dados).strip().lower() in {"mb51", "planilha2"}
        else "Excel tabular"
    )
    st.sidebar.success(
        f"Base real ativa: {st.session_state.df_consumo['Material'].nunique()} materiais "
        f"({rotulo_fonte})"
    )
    conferencia = st.session_state.df_consumo.attrs.get("conferencia_planilha9")
    if conferencia is not None:
        if conferencia["divergencias"] == 0:
            st.sidebar.success(
                f"Planilha9 conferida: {conferencia['agrupamentos_conferidos']} "
                "material/mês coincidem com a MB51. Os dados resumidos não são somados de novo."
            )
        else:
            st.sidebar.warning(
                f"Planilha9 e MB51 diferem em {conferencia['divergencias']} dos "
                f"{conferencia['agrupamentos_conferidos']} agrupamentos comparados. "
                "A previsão usa apenas as movimentações detalhadas da MB51."
            )
    st.sidebar.warning(
        "A planilha não contém cadastro de RH; a previsão usa o setor 'Geral' "
        "e não aplica regras inclusivas."
    )

# 1. Formulário para Adicionar Novo Material (Simulação Reativa)
with st.sidebar.form("form_novo_material"):
    st.subheader("➕ Simular Novo Material")
    novo_mat = st.text_input(
        "Nome do Material",
        placeholder="Ex: Telas de Proteção",
        disabled=dados_reais_ativos
    )
    
    # Busca setores dinamicamente da base persistente
    setores_disp = st.session_state.df_consumo['Setor'].unique()
    setor_selecionado = st.selectbox(
        "Setor Alocado",
        setores_disp,
        disabled=dados_reais_ativos
    )
    
    # Consumo médio desejado para a simulação de Poisson
    consumo_medio = st.slider(
        "Consumo Médio Desejado (Unidades)",
        10,
        500,
        50,
        disabled=dados_reais_ativos
    )
    
    submitted = st.form_submit_button(
        "Gerar Histórico e Treinar IA",
        disabled=dados_reais_ativos
    )
    
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
        def run_ml_pipeline(df_c, df_colabs, n_estimators, max_depth):
            forecaster = MaterialForecaster(
                n_estimators=n_estimators,
                max_depth=max_depth,
            )
            mae, X_test, y_test, y_pred = forecaster.train(df_c)
            df_future = forecaster.predict_next_3_months(df_c)
            df_inclusive = post_processing.apply_inclusive_rules(df_future, df_colabs)
            return mae, X_test, y_test, y_pred, df_future, df_inclusive

        mae, X_test, y_test, y_pred, df_future, df_inclusive = run_ml_pipeline(
            df_consumo, df_colaboradores, n_trees, depth
        )
        
        with st.container(key="dashboard_header"):
            st.title("🖥️ Supply Chain Inteligente & Ergonomia")
            st.markdown("#### Protótipo de TCC - Central de Simulação UNIP")
            if dados_reais_ativos:
                if st.session_state.df_consumo.attrs.get("movimentos_sap_classificados"):
                    st.info(
                        "Movimentos SAP 201/261 tratados como consumo e 202/262 como estorno; "
                        "o saldo mensal líquido é convertido em consumo não negativo. "
                        "Os registros são agregados por material/mês."
                    )
                else:
                    st.info(
                        "Dados reais da tabela Excel, organizados e somados por material/mês. "
                        "A quantidade foi convertida em valor absoluto conforme a regra "
                        "selecionada para esta planilha. Sem tipo de movimento, "
                        "a importação não separa consumo de estornos."
                    )
                st.caption("A planilha não fornece setor ou cadastro de RH.")

            c1, c2, c3, c4 = st.columns(4)
            total_prev = df_inclusive['Previsao_Bruta'].sum()
            pcd_rate = (
                len(df_colaboradores[df_colaboradores['Restricao_Ergonomica'] != "Nenhuma"])
                / len(df_colaboradores) * 100
                if len(df_colaboradores) else 0
            )
            total_adaptados = df_inclusive['Quantidade_Especial'].sum() if 'Quantidade_Especial' in df_inclusive.columns else 0

            c1.metric("Previsão Bruta (90d)", f"{total_prev} un.")
            c2.metric("Acurácia (MAE)", f"{mae:.2f}")
            c3.metric("Taxa de Inclusão", f"{pcd_rate:.1f}%")
            c4.metric("Itens Adaptados", f"{total_adaptados} un.")

        # ABAS DE NAVEGAÇÃO
        tab1, tab_sazonal, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 Dashboard Preditivo", 
            "📅 Dashboard Sazonal Manual",
            "♿ Relatório Ergonômico", 
            "📄 Fundamentação Teórica", 
            "🛠️ Central de Edição de Dados",
            "⚖️ RF × FastTree × sazonal manual",
            "📚 Base Organizada"
        ])

        with tab6:
            st.subheader("Dados organizados usados pelo dashboard")
            st.caption(
                "Visualização local da base já processada após a importação. "
                "Os registros são agrupados por material e mês."
            )
            base_organizada = df_consumo.copy()
            base_organizada["Data"] = (
                pd.to_datetime(base_organizada["Data"])
                .dt.to_period("M")
                .dt.to_timestamp()
            )

            if base_organizada.empty:
                st.info("Não há registros para exibir.")
            else:
                meses_disponiveis = sorted(base_organizada["Data"].dropna().unique())
                materiais_disponiveis = sorted(
                    base_organizada["Material"].dropna().astype(str).unique()
                )
                filtro_material, filtro_inicio, filtro_fim = st.columns([2, 1, 1])
                with filtro_material:
                    materiais_selecionados = st.multiselect(
                        "Materiais (vazio = todos)",
                        options=materiais_disponiveis,
                        placeholder="Todos os materiais",
                    )
                with filtro_inicio:
                    mes_inicio = st.selectbox(
                        "Mês inicial",
                        options=meses_disponiveis,
                        index=0,
                        format_func=lambda value: pd.Timestamp(value).strftime("%m/%Y"),
                    )
                with filtro_fim:
                    mes_fim = st.selectbox(
                        "Mês final",
                        options=meses_disponiveis,
                        index=len(meses_disponiveis) - 1,
                        format_func=lambda value: pd.Timestamp(value).strftime("%m/%Y"),
                    )

                if mes_inicio > mes_fim:
                    st.warning("O mês inicial deve ser anterior ou igual ao mês final.")
                else:
                    dados_filtrados = base_organizada[
                        base_organizada["Data"].between(mes_inicio, mes_fim)
                    ].copy()
                    if materiais_selecionados:
                        dados_filtrados = dados_filtrados[
                            dados_filtrados["Material"].astype(str).isin(materiais_selecionados)
                        ]

                    resumo1, resumo2, resumo3 = st.columns(3)
                    resumo1.metric("Registros", f"{len(dados_filtrados):,}")
                    resumo2.metric(
                        "Materiais",
                        f"{dados_filtrados['Material'].nunique():,}",
                    )
                    resumo3.metric(
                        "Consumo total (filtros)",
                        f"{dados_filtrados['Quantidade_Consumida'].sum():,.0f} un.",
                    )
                    st.caption(
                        "Soma da quantidade consumida nos meses selecionados, para os "
                        "materiais filtrados (ou todos, se nenhum material for selecionado)."
                    )

                    modo_visualizacao = st.radio(
                        "Visualização",
                        ["Detalhes mensais", "Resumo por material/mês"],
                        horizontal=True,
                    )
                    if modo_visualizacao == "Resumo por material/mês":
                        dados_filtrados = (
                            dados_filtrados.groupby(
                                ["Material", "Data"], as_index=False
                            )
                            .agg(
                                Quantidade_Consumida=("Quantidade_Consumida", "sum"),
                                Setor=("Setor", "first"),
                                Categoria=("Categoria", "first"),
                                Subcategoria=("Subcategoria", "first"),
                            )
                            .sort_values(["Data", "Material"])
                        )
                    else:
                        dados_filtrados = dados_filtrados.sort_values(
                            ["Data", "Material", "Setor"]
                        )

                    st.dataframe(
                        dados_filtrados.reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True,
                        height=500,
                    )
                    if dados_reais_ativos and st.session_state.df_consumo.attrs.get(
                        "movimentos_sap_classificados"
                    ):
                        st.caption(
                            "Movimentos SAP 201/261 tratados como consumo e 202/262 "
                            "como estornos antes da consolidação mensal."
                        )
                    elif dados_reais_ativos:
                        st.caption(
                            "A planilha não contém tipo de movimento; quantidades "
                            "foram organizadas conforme a regra de importação da origem."
                        )
                    else:
                        st.caption(
                            "Dados sintéticos organizados mensalmente por material e setor."
                        )

        with tab1:
            st.subheader("Análise Preditiva de Consumo (Random Forest)")

            materiais_dashboard = sorted(
                df_consumo["Material"].dropna().astype(str).unique()
            )
            material_dashboard = st.selectbox(
                "Material analisado",
                options=materiais_dashboard,
                key="dashboard_material_selecionado",
            )
            historico_material = (
                df_consumo[
                    df_consumo["Material"].astype(str) == material_dashboard
                ]
                .assign(Data=lambda frame: pd.to_datetime(frame["Data"]))
                .groupby("Data", as_index=False)["Quantidade_Consumida"]
                .sum()
                .sort_values("Data")
            )
            previsao_material = (
                df_future[df_future["Material"].astype(str) == material_dashboard]
                .groupby("Data", as_index=False)["Previsao_Bruta"]
                .sum()
                .sort_values("Data")
            )

            fig_demanda_material = go.Figure()
            fig_demanda_material.add_trace(go.Scatter(
                x=historico_material["Data"],
                y=historico_material["Quantidade_Consumida"],
                name="Consumo real",
                mode="lines+markers",
                line=dict(color="#222222", width=2),
            ))
            datas_previsao = previsao_material["Data"].tolist()
            quantidades_previsao = previsao_material["Previsao_Bruta"].tolist()
            if not historico_material.empty and datas_previsao:
                datas_previsao.insert(0, historico_material["Data"].iloc[-1])
                quantidades_previsao.insert(
                    0, historico_material["Quantidade_Consumida"].iloc[-1]
                )
            fig_demanda_material.add_trace(go.Scatter(
                x=datas_previsao,
                y=quantidades_previsao,
                name="Previsão Random Forest (90d)",
                mode="lines+markers",
                line=dict(color="#777777", dash="dash", width=2),
            ))
            fig_demanda_material.update_layout(
                title=f"Histórico e previsão de demanda: {material_dashboard}",
                xaxis_title="Mês",
                yaxis_title="Unidades",
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color="#111111",
                legend_title_text="Série",
            )
            st.plotly_chart(
                fig_demanda_material,
                use_container_width=True,
                theme=None,
            )

            validacao_material = X_test.copy()
            validacao_material["Real"] = np.asarray(y_test)
            validacao_material["Previsto"] = y_pred
            validacao_mensal = (
                validacao_material[
                    validacao_material["Material"].astype(str) == material_dashboard
                ]
                .assign(Data=lambda frame: pd.to_datetime(frame["Data"]))
                .groupby("Data", as_index=False)[["Real", "Previsto"]]
                .sum()
            )
            fig_val = go.Figure()
            fig_val.add_trace(go.Scatter(
                x=validacao_mensal["Data"],
                y=validacao_mensal["Real"],
                name="Real agregado",
                line=dict(color="#222222", width=2),
                mode="lines+markers",
                marker=dict(symbol="circle"),
            ))
            fig_val.add_trace(go.Scatter(
                x=validacao_mensal["Data"],
                y=validacao_mensal["Previsto"],
                name="Previsto agregado",
                line=dict(color="#777777", dash="dash"),
                mode="lines+markers",
                marker=dict(symbol="x"),
            ))
            fig_val.update_layout(
                title=f"Validação temporal por mês: {material_dashboard} (80/20)",
                xaxis_title="Mês",
                yaxis_title="Unidades",
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color="#111111",
            )
            st.plotly_chart(fig_val, use_container_width=True, theme=None)
            
            # Gráfico de Projeção Trimestral
            df_portfolio = pd.DataFrame(st.session_state.produtos)
            df_plot = df_future.merge(df_portfolio, on="Material", how="left").fillna("Simulado")
            
            fig_bar = px.bar(df_plot, x='Categoria', y='Previsao_Bruta', color='Subcategoria', 
                             barmode='group', title="Projeção Trimestral por Segmento",
                             color_discrete_sequence=["#222222", "#555555", "#888888", "#bbbbbb"],
                             template="plotly_white", hover_data=['Material'])
            fig_bar.update_layout(
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color="#111111",
            )
            st.plotly_chart(fig_bar, use_container_width=True, theme=None)

        with tab_sazonal:
            st.subheader("Previsão sazonal manual")
            st.caption(
                "A cada mês, a previsão repete o consumo observado no mesmo mês do ano "
                "anterior. Se não existir registro para o mês de referência, considera zero."
            )
            previsoes_sazonais = build_seasonal_forecast(df_consumo)
            materiais_sazonais = sorted(
                previsoes_sazonais["Material"].dropna().astype(str).unique()
            )
            material_sazonal = st.selectbox(
                "Material analisado",
                options=materiais_sazonais,
                key="dashboard_material_sazonal",
            )
            historico_sazonal = (
                df_consumo[df_consumo["Material"].astype(str) == material_sazonal]
                .assign(Data=lambda frame: pd.to_datetime(frame["Data"]))
                .groupby("Data", as_index=False)["Quantidade_Consumida"]
                .sum()
                .sort_values("Data")
            )
            previsao_sazonal = (
                previsoes_sazonais[
                    previsoes_sazonais["Material"].astype(str) == material_sazonal
                ]
                .groupby("Data", as_index=False)
                .agg(
                    Quantidade_Prevista=("Quantidade_Referencia", "sum"),
                    Referencia=("Data_Referencia", "first"),
                )
                .sort_values("Data")
            )

            seasonal_total, seasonal_average = st.columns(2)
            seasonal_total.metric(
                "Previsão sazonal (12 meses)",
                f"{previsao_sazonal['Quantidade_Prevista'].sum():,.0f} un.",
            )
            seasonal_average.metric(
                "Média mensal prevista",
                f"{previsao_sazonal['Quantidade_Prevista'].mean():,.1f} un.",
            )

            fig_sazonal = go.Figure()
            fig_sazonal.add_trace(go.Scatter(
                x=historico_sazonal["Data"],
                y=historico_sazonal["Quantidade_Consumida"],
                name="Consumo real",
                mode="lines+markers",
                line=dict(color="#222222", width=2),
            ))
            datas_sazonais = previsao_sazonal["Data"].tolist()
            quantidades_sazonais = previsao_sazonal["Quantidade_Prevista"].tolist()
            if not historico_sazonal.empty and datas_sazonais:
                datas_sazonais.insert(0, historico_sazonal["Data"].iloc[-1])
                quantidades_sazonais.insert(
                    0, historico_sazonal["Quantidade_Consumida"].iloc[-1]
                )
            fig_sazonal.add_trace(go.Scatter(
                x=datas_sazonais,
                y=quantidades_sazonais,
                name="Previsão sazonal manual",
                mode="lines+markers",
                line=dict(color="#777777", dash="dash", width=2),
            ))
            fig_sazonal.update_layout(
                title=f"Histórico e previsão sazonal: {material_sazonal}",
                xaxis_title="Mês",
                yaxis_title="Unidades",
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color="#111111",
                legend_title_text="Série",
            )
            st.plotly_chart(fig_sazonal, use_container_width=True, theme=None)

            tabela_sazonal = previsao_sazonal.rename(columns={
                "Data": "Mês previsto",
                "Referencia": "Mês de referência",
                "Quantidade_Prevista": "Quantidade prevista",
            }).copy()
            tabela_sazonal["Mês previsto"] = pd.to_datetime(
                tabela_sazonal["Mês previsto"]
            ).dt.strftime("%m/%Y")
            tabela_sazonal["Mês de referência"] = pd.to_datetime(
                tabela_sazonal["Mês de referência"]
            ).dt.strftime("%m/%Y")
            st.dataframe(
                tabela_sazonal[
                    [
                        "Mês previsto",
                        "Mês de referência",
                        "Quantidade prevista",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

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
            st.latex(
                r"\mathrm{MAPE} = \frac{100\%}{n} "
                r"\sum_{i=1}^{n} \left|\frac{y_i - \hat{y}_i}{y_i}\right|"
            )

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

        with tab5:
            st.subheader("Benchmark temporal: Random Forest × FastTree × sazonal manual")
            modo_captura = st.checkbox(
                "Modo captura de tela (ocultar a barra lateral e os dados do arquivo)",
                key="benchmark_modo_captura",
            )
            if modo_captura:
                st.markdown(
                    """
                    <style>
                    section[data-testid="stSidebar"] {display: none;}
                    div[data-testid="stAppViewBlockContainer"] {
                        max-width: 100%;
                        padding-top: 0.5rem;
                    }
                    div[data-testid="stForm"],
                    div[data-testid="stExpander"] {
                        display: none;
                    }
                    .st-key-dashboard_header {
                        display: none;
                    }
                    div[data-testid="stTabs"] [role="tablist"] {
                        display: none;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
            if not modo_captura:
                st.write(
                    "Os dois modelos recebem a mesma série mensal, treinam até a data de corte "
                    "e preveem os mesmos doze meses seguintes. A comparação usa os valores reais "
                    "desses meses, sem embaralhar o histórico. A tela mostra apenas resultados "
                    "agregados: não exibe textos, nomes ou códigos presentes na planilha."
                )
            with st.expander("Auditoria da base usada no benchmark", expanded=False):
                dados_auditoria = df_consumo.copy()
                dados_auditoria["Data"] = (
                    pd.to_datetime(dados_auditoria["Data"])
                    .dt.to_period("M")
                    .dt.to_timestamp()
                )
                resumo_mensal = (
                    dados_auditoria.groupby("Data", as_index=False)
                    .agg(
                        Consumo_Importado=("Quantidade_Consumida", "sum"),
                        Materiais=("Material", "nunique"),
                        Registros=("Material", "size"),
                    )
                    .sort_values("Data")
                )
                data_minima = dados_auditoria["Data"].min().strftime("%m/%Y")
                data_maxima = dados_auditoria["Data"].max().strftime("%m/%Y")
                st.write(
                    f"**Período:** {data_minima} a {data_maxima} · "
                    f"**Materiais:** {dados_auditoria['Material'].nunique()} · "
                    f"**Registros material/mês:** {len(dados_auditoria)}"
                )
                st.caption(
                    "Resumo mensal agregado. Nenhum nome, código ou texto da planilha é exibido."
                )
                grafico_historico = go.Figure(go.Bar(
                    x=resumo_mensal["Data"].dt.strftime("%m/%Y"),
                    y=resumo_mensal["Consumo_Importado"],
                    marker_color="#555555",
                    name="Consumo agregado",
                    hovertemplate="%{x}<br>Consumo: %{y:,.0f}<extra></extra>",
                ))
                grafico_historico.update_layout(
                    title="Consumo mensal agregado",
                    xaxis_title="Mês",
                    yaxis_title="Unidades",
                    showlegend=False,
                    margin=dict(t=55, b=35),
                    template="plotly_white",
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font_color="#111111",
                )
                st.plotly_chart(
                    grafico_historico,
                    use_container_width=True,
                    config={"displayModeBar": False},
                    theme=None,
                )
            if not modo_captura:
                st.info(
                    "Base real selecionada. A apresentação contém somente métricas e totais agregados."
                    if dados_reais_ativos else
                    "Base sintética selecionada. Para uma comparação operacional, selecione a base real."
                )
            else:
                st.caption(
                    "Base real importada; identificadores e conteúdos da planilha não são exibidos."
                    if dados_reais_ativos else
                    "Base sintética."
                )

            datas_disponiveis = sorted(
                pd.to_datetime(df_consumo["Data"]).dt.to_period("M").dt.to_timestamp().unique()
            )
            horizonte = 12
            meses_por_serie = [
                set(pd.to_datetime(group["Data"]).dt.to_period("M").dt.to_timestamp())
                for _, group in df_consumo.groupby(["Setor", "Material"])
            ]
            datas_corte = [
                cutoff
                for cutoff in datas_disponiveis[11:-horizonte]
                if all(
                    any(month <= pd.Timestamp(cutoff) for month in months)
                    and set(pd.date_range(
                        pd.Timestamp(cutoff) + pd.offsets.MonthBegin(1),
                        periods=horizonte,
                        freq="MS",
                    )).issubset(months)
                    for months in meses_por_serie
                )
            ]
            if not len(datas_corte):
                st.error(
                    "Não há um corte com dados de treino para cada material/setor "
                    "e doze meses completos de teste."
                )
            else:
                with st.form("form_benchmark_temporal"):
                    endpoint_csharp = st.text_input(
                        "Endpoint do dashboard C#",
                        value="http://localhost:5202/api/benchmark"
                    )
                    corte = st.selectbox(
                        "Treinar até (inclusive)",
                        options=datas_corte,
                        index=len(datas_corte) - 1,
                        format_func=lambda value: pd.Timestamp(value).strftime("%m/%Y")
                    )
                    st.caption(
                        "Se o serviço C# local ainda não estiver ativo, será iniciado "
                        "automaticamente ao executar o benchmark. "
                    )
                    st.caption(
                        f"Período avaliado ({horizonte} meses após o corte): " + ", ".join(
                            date.strftime("%m/%Y")
                            for date in pd.date_range(
                                pd.Timestamp(corte) + pd.offsets.MonthBegin(1),
                                periods=horizonte,
                                freq="MS",
                            )
                        )
                    )
                    executar_benchmark = st.form_submit_button(
                        "▶ Executar os dois modelos",
                        type="primary",
                        use_container_width=True
                    )

                if executar_benchmark:
                    st.session_state.pop("resultado_benchmark", None)
                    try:
                        with st.spinner("Treinando e medindo Random Forest e FastTree..."):
                            csharp_iniciado = ensure_local_csharp_service(endpoint_csharp)
                            resultado_python = run_random_forest_benchmark(
                                df_consumo,
                                corte,
                                horizon=horizonte,
                                n_estimators=n_trees,
                                max_depth=depth,
                            )
                            payload = benchmark_request_payload(
                                df_consumo,
                                corte,
                                horizonte,
                                n_trees,
                                depth,
                            )
                            request = Request(
                                endpoint_csharp,
                                data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                                headers={"Content-Type": "application/json"},
                                method="POST",
                            )
                            with urlopen(request, timeout=180) as response:
                                resultado_csharp = json.loads(response.read().decode("utf-8"))
                        if csharp_iniciado:
                            st.success("Serviço C# iniciado automaticamente para esta comparação.")
                        if resultado_csharp["pontosTeste"] != resultado_python["pontos_teste"]:
                            raise ValueError(
                                "Os modelos não compararam a mesma quantidade de material-mês."
                            )
                        if not np.isclose(
                            resultado_csharp["totalReal"],
                            resultado_python["total_real"],
                            rtol=0,
                            atol=1e-4,
                        ):
                            raise ValueError(
                                "Os valores reais usados pelos dois modelos não coincidem."
                            )
                        if not np.isclose(
                            resultado_csharp["maeSazonalManual"],
                            resultado_python["manual_mae"],
                            rtol=0,
                            atol=1e-4,
                        ):
                            raise ValueError(
                                "A comparação sazonal manual diferiu entre Python e C#."
                            )
                        if not np.isclose(
                            resultado_csharp["rmseSazonalManual"],
                            resultado_python["manual_rmse"],
                            rtol=0,
                            atol=1e-4,
                        ):
                            raise ValueError(
                                "O RMSE sazonal manual diferiu entre Python e C#."
                            )
                        if not np.isclose(
                            resultado_csharp["totalSazonalManual"],
                            resultado_python["manual_total_previsto"],
                            rtol=0,
                            atol=1e-4,
                        ):
                            raise ValueError(
                                "O total sazonal manual diferiu entre Python e C#."
                            )
                        python_actual = pd.DataFrame(resultado_python["previsoes"])[
                            ["Data", "Setor", "Material", "Quantidade_Consumida"]
                        ].rename(columns={"Quantidade_Consumida": "Real_Python"})
                        csharp_actual = pd.DataFrame(resultado_csharp["previsoes"]).rename(
                            columns={
                                "data": "Data",
                                "setor": "Setor",
                                "material": "Material",
                                "real": "Real_CSharp",
                            }
                        )
                        python_actual["Data"] = pd.to_datetime(python_actual["Data"])
                        csharp_actual["Data"] = pd.to_datetime(csharp_actual["Data"])
                        actual_check = python_actual.merge(
                            csharp_actual[["Data", "Setor", "Material", "Real_CSharp"]],
                            on=["Data", "Setor", "Material"],
                            validate="one_to_one",
                        )
                        if len(actual_check) != resultado_python["pontos_teste"] or not np.allclose(
                            actual_check["Real_Python"],
                            actual_check["Real_CSharp"],
                            rtol=0,
                            atol=1e-4,
                        ):
                            raise ValueError(
                                "Os modelos não receberam os mesmos valores reais por material/mês."
                            )
                        st.session_state["resultado_benchmark"] = {
                            "python": resultado_python,
                            "csharp": resultado_csharp,
                            "parametros": {
                                "random_forest": {
                                    "arvores": n_trees,
                                    "profundidade_maxima": depth,
                                },
                                "fasttree": {
                                    "arvores": payload["arvores"],
                                    "folhas": payload["folhas"],
                                    "minLeaf": payload["minLeaf"],
                                    "lr": payload["lr"],
                                },
                            },
                            "corte": pd.Timestamp(corte).strftime("%m/%Y"),
                            "meses_teste": [
                                date.strftime("%m/%Y")
                                for date in pd.date_range(
                                    pd.Timestamp(corte) + pd.offsets.MonthBegin(1),
                                    periods=horizonte,
                                    freq="MS",
                                )
                            ],
                        }
                    except HTTPError as error:
                        detalhe = error.read().decode("utf-8", errors="replace")
                        st.error(
                            f"O serviço C# respondeu com HTTP {error.code}: {detalhe}"
                        )
                    except URLError as error:
                        st.error(
                            "Não consegui acessar o C#; confirme que o dashboard está "
                            f"aberto em http://localhost:5202. Detalhe: {error.reason}"
                        )
                    except RuntimeError as error:
                        st.error(str(error))
                    except (ValueError, KeyError, OSError) as error:
                        st.error(f"Não foi possível concluir o benchmark: {error}")

            resultado = st.session_state.get("resultado_benchmark")
            if resultado is not None:
                rf = resultado["python"]
                ft = resultado["csharp"]
                st.markdown(
                    f"**Treino até:** {resultado['corte']} · "
                    f"**Período de teste ({len(resultado['meses_teste'])} meses):** "
                    f"{', '.join(resultado['meses_teste'])} · "
                    f"**Pontos avaliados:** {rf['pontos_teste']}"
                )
                st.info(
                    "Cada modelo prevê o consumo mensal de cada combinação de material e setor. "
                    "O gráfico soma essas quantidades de todas as combinações em cada mês "
                    "(não é média). “Consumo real” é a soma observada no período de teste; "
                    "Random Forest e FastTree são as respectivas somas previstas. "
                    "A terceira comparação é sazonal e manual: para cada material/setor, "
                    "repete o valor do mesmo mês do ano anterior; se não houver "
                    "registro daquele mês, considera consumo zero."
                )
                parametros = resultado["parametros"]
                st.caption(
                    "Configuração desta execução · Random Forest: "
                    f"{parametros['random_forest']['arvores']} árvores, profundidade "
                    f"{parametros['random_forest']['profundidade_maxima']} · FastTree: "
                    f"{parametros['fasttree']['arvores']} árvores, "
                    f"{parametros['fasttree']['folhas']} folhas, "
                    f"mínimo {parametros['fasttree']['minLeaf']} exemplos/folha, "
                    f"LR {parametros['fasttree']['lr']:.2f}"
                )
                total_real = rf["total_real"]
                total_rf = rf["total_previsto"]
                total_ft = ft["totalPrevisto"]
                placar_mae = {
                    "Random Forest": rf["mae"],
                    "FastTree": ft["mae"],
                    "Método sazonal manual (ano anterior)": rf["manual_mae"],
                }
                vencedor = min(placar_mae, key=placar_mae.get)
                st.success(
                    f"Menor MAE neste recorte: **{vencedor}** "
                    f"({placar_mae[vencedor]:,.2f} unidades). "
                    f"Random Forest: {rf['mae']:,.2f} · FastTree: {ft['mae']:,.2f} · "
                    f"sazonal manual: {rf['manual_mae']:,.2f}. "
                    "Resultado restrito ao período avaliado."
                )
                format_wape = lambda value: (
                    f"{value:.1%}" if value is not None else "n/d (volume real zero)"
                )
                st.caption(
                    "WAPE (erro absoluto / volume real): "
                    f"Random Forest {format_wape(rf['wape'])} · "
                    f"FastTree {format_wape(ft['wape'])} · "
                    f"sazonal manual {format_wape(rf['manual_wape'])}."
                )
                if modo_captura:
                    st.caption(
                        f"Totais: real {total_real:,.0f} un. · "
                        f"Random Forest {total_rf:,.0f} un. "
                        f"({total_rf - total_real:+,.0f}) · "
                        f"FastTree {total_ft:,.0f} un. ({total_ft - total_real:+,.0f}) · "
                        f"sazonal manual {rf['manual_total_previsto']:,.0f} un."
                    )

                previsoes = pd.DataFrame(rf["previsoes"]).rename(columns={
                    "Data": "Data",
                    "Quantidade_Consumida": "Real",
                    "Previsao": "Random Forest",
                })
                fasttree_rows = pd.DataFrame(ft["previsoes"]).rename(columns={
                    "data": "Data",
                    "setor": "Setor",
                    "material": "Material",
                    "real": "Real_FastTree",
                    "previsto": "FastTree",
                })
                if not previsoes.empty and not fasttree_rows.empty:
                    previsoes["Data"] = pd.to_datetime(previsoes["Data"])
                    fasttree_rows["Data"] = pd.to_datetime(fasttree_rows["Data"])
                    detalhamento = previsoes.merge(
                        fasttree_rows,
                        on=["Data", "Setor", "Material"],
                        validate="one_to_one",
                    )
                    detalhamento["Erro RF"] = detalhamento["Random Forest"] - detalhamento["Real"]
                    detalhamento["Erro FastTree"] = detalhamento["FastTree"] - detalhamento["Real"]
                    mensal = (
                        detalhamento.groupby("Data", as_index=False)
                        .agg({
                            "Real": "sum",
                            "Random Forest": "sum",
                            "FastTree": "sum",
                            "Sazonal_Manual": "sum",
                        })
                        .sort_values("Data")
                    )
                    rotulos_meses = mensal["Data"].dt.strftime("%m/%Y")
                    metricas_figura = go.Figure()
                    metricas_figura.add_trace(go.Bar(
                        name="Random Forest",
                        x=["MAE ↓", "RMSE ↓"],
                        y=[rf["mae"], rf["rmse"]],
                        marker_color="#777777",
                        text=[f"{rf['mae']:.2f}", f"{rf['rmse']:.2f}"],
                        textposition="outside",
                    ))
                    metricas_figura.add_trace(go.Bar(
                        name="FastTree",
                        x=["MAE ↓", "RMSE ↓"],
                        y=[ft["mae"], ft["rmse"]],
                        marker_color="#333333",
                        text=[f"{ft['mae']:.2f}", f"{ft['rmse']:.2f}"],
                        textposition="outside",
                    ))
                    metricas_figura.add_trace(go.Bar(
                        name="Sazonal manual (mesmo mês do ano anterior)",
                        x=["MAE ↓", "RMSE ↓"],
                        y=[rf["manual_mae"], rf["manual_rmse"]],
                        marker_color="#bbbbbb",
                        text=[
                            f"{rf['manual_mae']:.2f}",
                            f"{rf['manual_rmse']:.2f}",
                        ],
                        textposition="outside",
                    ))
                    metricas_figura.update_layout(
                        title="Erro de previsão (menor é melhor)",
                        barmode="group",
                        yaxis_title="Erro médio em unidades",
                        legend_title="Modelo",
                        height=280,
                        margin=dict(t=55, b=35),
                        template="plotly_white",
                        paper_bgcolor="#ffffff",
                        plot_bgcolor="#ffffff",
                        font_color="#111111",
                    )
                    totais_figura = go.Figure()
                    for nome, coluna, cor in (
                        ("Consumo real", "Real", "#222222"),
                        ("Random Forest", "Random Forest", "#777777"),
                        ("FastTree", "FastTree", "#444444"),
                        (
                            "Sazonal manual (mesmo mês do ano anterior)",
                            "Sazonal_Manual",
                            "#bbbbbb",
                        ),
                    ):
                        totais_figura.add_trace(go.Bar(
                            name=nome,
                            x=rotulos_meses,
                            y=mensal[coluna],
                            marker_color=cor,
                            text=mensal[coluna].round().astype(int),
                            textposition="outside",
                        ))
                    totais_figura.update_layout(
                        title="Consumo real e previsto por mês (soma de materiais e setores)",
                        barmode="group",
                        xaxis_title="Mês",
                        yaxis_title="Unidades consumidas (soma mensal)",
                        legend_title="Série",
                        margin=dict(t=55, b=35),
                        template="plotly_white",
                        paper_bgcolor="#ffffff",
                        plot_bgcolor="#ffffff",
                        font_color="#111111",
                    )
                    st.plotly_chart(
                        metricas_figura,
                        use_container_width=True,
                        config={"displayModeBar": False},
                        theme=None,
                    )
                    if not modo_captura:
                        st.plotly_chart(
                            totais_figura,
                            use_container_width=True,
                            config={"displayModeBar": False},
                            theme=None,
                        )

                    if not modo_captura:
                        totais_colunas = st.columns(4)
                        totais_colunas[0].metric("Consumo real", f"{total_real:,.0f} un.")
                        totais_colunas[1].metric(
                            "Previsto · Random Forest",
                            f"{total_rf:,.0f} un.",
                            delta=f"{total_rf - total_real:+,.0f} un. vs real",
                        )
                        totais_colunas[2].metric(
                            "Previsto · FastTree",
                            f"{total_ft:,.0f} un.",
                            delta=f"{total_ft - total_real:+,.0f} un. vs real",
                        )
                        totais_colunas[3].metric(
                            "Previsto · Sazonal manual",
                            f"{rf['manual_total_previsto']:,.0f} un.",
                            delta=f"{rf['manual_total_previsto'] - total_real:+,.0f} un. vs real",
                        )

                    with st.expander("Desempenho computacional desta execução"):
                        colunas_modelos = st.columns(2)
                        for coluna, nome, treino, previsao, cpu, memoria in (
                            (
                                colunas_modelos[0], "Random Forest",
                                rf["treino_segundos"], rf["previsao_segundos"],
                                rf["cpu_segundos"], rf["aumento_pico_memoria_mb"],
                            ),
                            (
                                colunas_modelos[1], "FastTree",
                                ft["tempoTreinamentoMs"] / 1000,
                                ft["tempoPrevisaoMs"] / 1000,
                                ft["tempoCpuMs"] / 1000,
                                ft["aumentoPicoMemoriaMb"],
                            ),
                        ):
                            with coluna:
                                st.markdown(f"**{nome}**")
                                st.caption(
                                    f"Treino: {treino:.3f} s · Previsão: {previsao:.3f} s · "
                                    f"CPU: {cpu:.3f} s · RAM estimada: {memoria:.1f} MB"
                                )
                        st.caption(
                            "A RAM é uma estimativa amostrada do processo inteiro, não do algoritmo "
                            "isolado. Repita e compare medianas para reduzir o ruído."
                        )

    except Exception as e:
        st.error(f"Erro no processamento do pipeline: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
