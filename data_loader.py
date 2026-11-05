import pandas as pd
import numpy as np
from datetime import datetime
import unicodedata

def generate_synthetic_data():
    """
    Gera dados sintéticos para simular o consumo de EPIs e o cadastro de colaboradores.
    Retorna dois DataFrames: df_consumo e df_colaboradores.
    """
    np.random.seed(42)
    
    # 1. Gerar Histórico de Consumo (mínimo 24 meses)
    # Colunas: Data, Material, Categoria, Subcategoria, Setor, Quantidade_Consumida
    start_date = datetime(2024, 1, 1)
    dates = pd.date_range(start_date, periods=24, freq='MS')
    
    sectors = ['Administrativo', 'Financeiro', 'RH', 'TI', 'Operações']
    
    # Novo Portfólio de Materiais
    catalog = {
        'Papelaria e Organização de Mesa': {
            'Escrita e Marcadores': ['Canetas e Escrita'],
            'Mesa e Documentação': ['Post-it e Clipes', 'Grampeadores e Tesouras'],
            'Organização Física': ['Pastas e Caixas', 'Papel Sulfite'],
            'Identificação': ['Rotulador Brother Eletrônico']
        },
        'Equipamentos e Suprimentos': {
            'Impressão': ['Toners e Cartuchos'],
            'Informática Básica': ['Mouses e Teclados'],
            'Segurança e Manutenção': ['Fragmentadoras de Papel']
        },
        'Móveis Essenciais': {
            'Postura e Conforto': ['Cadeiras Giratórias Ergonômicas'],
            'Área de Trabalho': ['Mesas de Escritório'],
            'Armazenamento': ['Gaveteiros e Armários']
        }
    }
    
    consumption_data = []
    for date in dates:
        seasonality = 1 + 0.15 * np.sin(2 * np.pi * date.month / 12)
        for sector in sectors:
            for cat, subcats in catalog.items():
                for subcat, materials in subcats.items():
                    for material in materials:
                        base_lambda = {
                            'Canetas e Escrita': 30,
                            'Post-it e Clipes': 20,
                            'Grampeadores e Tesouras': 5,
                            'Pastas e Caixas': 15,
                            'Papel Sulfite': 50,
                            'Rotulador Brother Eletrônico': 2,
                            'Toners e Cartuchos': 8,
                            'Mouses e Teclados': 12,
                            'Fragmentadoras de Papel': 1,
                            'Cadeiras Giratórias Ergonômicas': 3,
                            'Mesas de Escritório': 2,
                            'Gaveteiros e Armários': 2
                        }.get(material, 10)
                        
                        sector_factor = {
                            'Administrativo': 1.4, 
                            'Financeiro': 1.2, 
                            'RH': 1.1, 
                            'TI': 0.9, 
                            'Operações': 0.7
                        }[sector]
                        
                        lambda_val = base_lambda * sector_factor * seasonality
                        quantity = np.random.poisson(lambda_val)
                        
                        consumption_data.append({
                            'Data': date,
                            'Material': material,
                            'Categoria': cat,
                            'Subcategoria': subcat,
                            'Setor': sector,
                            'Quantidade_Consumida': quantity
                        })
    
    df_consumo = pd.DataFrame(consumption_data)
    
    # 2. Gerar Cadastro de Colaboradores (Equipe Ativa)
    n_colabs = 200
    colabs_data = []
    
    restrictions_pool = [
        "Diagnóstico de LER/DORT (Necessita de Mouse Vertical Ergonômico)",
        "Deficiência Visual/Baixa Visão (Necessita de Teclado Ampliado com Alto Contraste)",
        "Canhoto (Necessita de Teclado/Mouse adaptado)",
        "Restrição de Postura NR-17 (Necessita de Suporte Ortopédico de Punho)"
    ]
    
    for i in range(1, n_colabs + 1):
        is_pcd_or_restricted = np.random.random() < 0.15 
        restricao = np.random.choice(restrictions_pool) if is_pcd_or_restricted else "Nenhuma"
        
        colabs_data.append({
            'Colaborador_ID': f'COLAB-{i:03d}',
            'Nome': f'Colaborador Nome {i}',
            'Setor': np.random.choice(sectors),
            'Restricao_Ergonomica': restricao
        })
        
    df_colaboradores = pd.DataFrame(colabs_data)
    
    return df_consumo, df_colaboradores

def load_from_excel(file_path_consumption, file_path_employees):
    """
    Carregamento de planilhas reais via Pandas.
    """
    try:
        df_consumo = pd.read_excel(file_path_consumption)
        df_colaboradores = pd.read_excel(file_path_employees)
        return df_consumo, df_colaboradores
    except Exception as e:
        print(f"Erro ao carregar arquivos: {e}")
        return None, None


def _normalize_header(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return "".join(char.lower() for char in value if char.isalnum())


def _month_number(value):
    if pd.isna(value):
        return None

    month = _normalize_header(value)
    if month.isdigit():
        number = int(month)
        return number if 1 <= number <= 12 else None

    months = {
        "jan": 1, "janeiro": 1,
        "fev": 2, "fevereiro": 2,
        "mar": 3, "marco": 3,
        "abr": 4, "abril": 4,
        "mai": 5, "maio": 5,
        "jun": 6, "junho": 6,
        "jul": 7, "julho": 7,
        "ago": 8, "agosto": 8,
        "set": 9, "setembro": 9,
        "out": 10, "outubro": 10,
        "nov": 11, "novembro": 11,
        "dez": 12, "dezembro": 12,
    }
    return months.get(month)


def _material_code(value):
    if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
        if float(value).is_integer():
            return str(int(value))
    return str(value).strip()


def _find_sheet_columns(raw, required_headers, sheet_name):
    for row_index, row in raw.iterrows():
        columns = {
            _normalize_header(value): column_index
            for column_index, value in row.items()
            if not pd.isna(value)
        }
        if required_headers.issubset(columns):
            return row_index, columns
    raise ValueError(f"Não encontrei as colunas necessárias na aba '{sheet_name}'.")


def _read_monthly_summary(excel, sheet_name):
    raw = pd.read_excel(excel, sheet_name=sheet_name, header=None)
    header_row, columns = _find_sheet_columns(
        raw,
        {"material", "ano", "mes", "somadequantidade"},
        sheet_name
    )
    records = raw.iloc[header_row + 1:]
    summary = pd.DataFrame({
        "Material": records.iloc[:, columns["material"]],
        "Ano": records.iloc[:, columns["ano"]],
        "Mes": records.iloc[:, columns["mes"]],
        "Quantidade_Assinada": records.iloc[:, columns["somadequantidade"]],
    }).dropna(subset=["Material"])
    summary["Material"] = summary["Material"].map(_material_code)
    summary = summary[summary["Material"].ne("")]
    summary = summary[
        ~(summary["Ano"].isna() & summary["Mes"].isna())
    ].copy()
    summary["Ano"] = pd.to_numeric(summary["Ano"], errors="coerce")
    summary["Mes"] = summary["Mes"].map(_month_number)
    summary["Quantidade_Assinada"] = pd.to_numeric(
        summary["Quantidade_Assinada"], errors="coerce"
    )
    invalid_rows = summary[["Ano", "Mes", "Quantidade_Assinada"]].isna().any(axis=1)
    if invalid_rows.any():
        excel_row = int(summary.index[invalid_rows][0]) + 1
        raise ValueError(
            f"Registro inválido na linha {excel_row} da aba '{sheet_name}'."
        )
    summary["Data"] = pd.to_datetime({
        "year": summary["Ano"].astype(int),
        "month": summary["Mes"].astype(int),
        "day": 1,
    })
    return summary.groupby(["Material", "Data"])["Quantidade_Assinada"].sum()


def _read_mb51(excel, sheet_name):
    raw = pd.read_excel(excel, sheet_name=sheet_name, header=None)
    header_row, columns = _find_sheet_columns(
        raw,
        {"tipodemovimento", "material", "quantidade", "mes", "ano"},
        sheet_name
    )
    records = raw.iloc[header_row + 1:]
    transactions = pd.DataFrame({
        "Tipo_Movimento": records.iloc[:, columns["tipodemovimento"]],
        "Material": records.iloc[:, columns["material"]],
        "Quantidade_Assinada": records.iloc[:, columns["quantidade"]],
        "Mes": records.iloc[:, columns["mes"]],
        "Ano": records.iloc[:, columns["ano"]],
    })
    transactions = transactions.dropna(subset=["Material", "Tipo_Movimento"])
    transactions["Tipo_Movimento"] = transactions["Tipo_Movimento"].astype(str).str.strip()
    transactions = transactions[transactions["Tipo_Movimento"].ne("")]
    transactions["Material"] = transactions["Material"].map(_material_code)
    transactions["Ano"] = pd.to_numeric(transactions["Ano"], errors="coerce")
    transactions["Mes"] = transactions["Mes"].map(_month_number)
    transactions["Quantidade_Assinada"] = pd.to_numeric(
        transactions["Quantidade_Assinada"], errors="coerce"
    )
    invalid_rows = transactions[["Ano", "Mes", "Quantidade_Assinada"]].isna().any(axis=1)
    if invalid_rows.any():
        excel_row = int(transactions.index[invalid_rows][0]) + 1
        raise ValueError(
            f"Movimentação inválida na linha {excel_row} da aba '{sheet_name}'."
        )
    transactions["Data"] = pd.to_datetime({
        "year": transactions["Ano"].astype(int),
        "month": transactions["Mes"].astype(int),
        "day": 1,
    })
    return transactions.groupby(["Material", "Data"])["Quantidade_Assinada"].sum()


def load_real_consumption_excel(file):
    """
    Importa o histórico detalhado da aba MB51 e usa Planilha9 para conferência.

    Linhas de subtotal sem tipo de movimento são ignoradas. Os movimentos
    líquidos por material/mês são convertidos em consumo positivo; Planilha9
    nunca é somada novamente, pois é uma agregação das mesmas transações.
    """
    excel = pd.ExcelFile(file)
    sheets_by_name = {
        _normalize_header(name): name
        for name in excel.sheet_names
    }

    transaction_sheet = sheets_by_name.get("mb51")
    summary_sheet = sheets_by_name.get("planilha9")
    if transaction_sheet:
        monthly = _read_mb51(excel, transaction_sheet)
        source = transaction_sheet
    elif summary_sheet:
        monthly = _read_monthly_summary(excel, summary_sheet)
        source = summary_sheet
    else:
        raise ValueError("O arquivo não contém a aba MB51 nem a aba Planilha9.")

    if monthly.empty:
        raise ValueError(f"A aba '{source}' não contém registros de consumo.")

    comparison = None
    if transaction_sheet and summary_sheet:
        summary = _read_monthly_summary(excel, summary_sheet)
        shared_keys = monthly.index.intersection(summary.index)
        differences = (monthly.loc[shared_keys] - summary.loc[shared_keys]).abs()
        comparison = {
            "agrupamentos_conferidos": len(shared_keys),
            "divergencias": int(differences.gt(1e-6).sum()),
        }

    monthly = (-monthly).clip(lower=0).rename("Quantidade_Consumida").reset_index()
    last_month = monthly["Data"].max()
    material_starts = monthly.groupby("Material")["Data"].min()
    complete_index = pd.MultiIndex.from_tuples(
        [
            (material, date)
            for material, first_month in material_starts.items()
            for date in pd.date_range(first_month, last_month, freq="MS")
        ],
        names=["Material", "Data"],
    )
    df_consumo = (
        monthly.set_index(["Material", "Data"])["Quantidade_Consumida"]
        .reindex(complete_index, fill_value=0)
        .reset_index()
    )
    df_consumo["Categoria"] = "Não informado"
    df_consumo["Subcategoria"] = "Não informado"
    df_consumo["Setor"] = "Geral"
    df_consumo = df_consumo[
        ["Data", "Material", "Categoria", "Subcategoria", "Setor", "Quantidade_Consumida"]
    ]
    df_consumo.attrs["fonte_importacao"] = source
    df_consumo.attrs["conferencia_planilha9"] = comparison

    df_colaboradores = pd.DataFrame(columns=[
        "Colaborador_ID", "Nome", "Setor", "Restricao_Ergonomica"
    ])
    return df_consumo, df_colaboradores
