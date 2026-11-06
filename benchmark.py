import ctypes
import os
import threading
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _working_set_bytes():
    if os.name != "nt":
        raise OSError("A medição de memória do benchmark está disponível no Windows.")

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessMemoryCounters), ctypes.c_ulong]
    get_memory_info.restype = ctypes.c_int
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    process = get_current_process()
    success = get_memory_info(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    if not success:
        raise OSError("Não foi possível medir o uso de memória do processo.")
    return counters.WorkingSetSize


def _measure_peak_working_set(stop_event, samples):
    while not stop_event.wait(0.02):
        samples.append(_working_set_bytes())


def run_random_forest_benchmark(
    history,
    cutoff,
    horizon=12,
    n_estimators=100,
    max_depth=10,
):
    if os.name != "nt":
        raise OSError("O benchmark de memória está configurado para Windows.")

    cutoff = pd.Timestamp(cutoff).to_period("M").to_timestamp()
    forecast_dates = pd.date_range(
        cutoff + pd.offsets.MonthBegin(1),
        periods=horizon,
        freq="MS",
    )
    history = history.copy()
    history["Data"] = pd.to_datetime(history["Data"]).dt.to_period("M").dt.to_timestamp()
    training = history[history["Data"] <= cutoff].copy()
    actual = history[history["Data"].isin(forecast_dates)].copy()

    if training.empty:
        raise ValueError("Não há dados de treinamento até o mês de corte.")

    series_keys = ["Setor", "Material"]
    expected = len(training[series_keys].drop_duplicates()) * horizon
    if len(actual) != expected or actual.duplicated(series_keys + ["Data"]).any():
        raise ValueError(
            "O período de teste não tem dados completos para todos os materiais e setores."
        )

    training = training.sort_values(series_keys + ["Data"]).reset_index(drop=True)
    prepared = training.copy()
    prepared["Mes"] = prepared["Data"].dt.month
    prepared["Ano"] = prepared["Data"].dt.year
    prepared["Lag_1"] = prepared.groupby(series_keys)["Quantidade_Consumida"].shift(1)
    prepared["Lag_2"] = prepared.groupby(series_keys)["Quantidade_Consumida"].shift(2)
    for column in ("Lag_1", "Lag_2"):
        prepared[column] = prepared.groupby(series_keys)[column].transform(
            lambda values: values.fillna(values.mean()).fillna(0)
        )

    columns_to_drop = [
        column for column in (
            "Data", "Quantidade_Consumida", "Categoria", "Subcategoria"
        ) if column in prepared.columns
    ]
    train_features = pd.get_dummies(
        prepared.drop(columns=columns_to_drop),
        columns=["Setor", "Material"],
    )
    target = prepared["Quantidade_Consumida"].astype(float)
    feature_columns = train_features.columns
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42,
        n_jobs=1,
    )

    memory_before = _working_set_bytes()
    samples = [memory_before]
    stop_event = threading.Event()
    monitor = threading.Thread(
        target=_measure_peak_working_set,
        args=(stop_event, samples),
        daemon=True,
    )
    monitor.start()
    cpu_start = time.process_time()

    try:
        fit_start = time.perf_counter()
        model.fit(train_features, target)
        training_seconds = time.perf_counter() - fit_start

        forecast_start = time.perf_counter()
        generated = []
        manual_generated = []
        rolling_values = {
            key: group.sort_values("Data")["Quantidade_Consumida"].astype(float).tolist()
            for key, group in training.groupby(series_keys, sort=True)
        }
        manual_values = {
            key: {
                row.Data: float(row.Quantidade_Consumida)
                for row in group.sort_values("Data").itertuples(index=False)
            }
            for key, group in training.groupby(series_keys, sort=True)
        }
        for date in forecast_dates:
            rows = []
            manual_rows = []
            for (sector, material), values in rolling_values.items():
                lag_1 = values[-1]
                lag_2 = values[-2] if len(values) > 1 else lag_1
                rows.append({
                    "Data": date,
                    "Ano": date.year,
                    "Mes": date.month,
                    "Setor": sector,
                    "Material": material,
                    "Lag_1": lag_1,
                    "Lag_2": lag_2,
                })
                previous_year = date - pd.DateOffset(years=1)
                previous_value = manual_values[(sector, material)].get(previous_year, 0.0)
                manual_rows.append({
                    "Data": date,
                    "Setor": sector,
                    "Material": material,
                    "Sazonal_Manual": previous_value,
                })

            future_features = pd.DataFrame(rows)
            future_features = pd.get_dummies(
                future_features,
                columns=["Setor", "Material"],
            ).reindex(columns=feature_columns, fill_value=0)
            predictions = np.rint(np.maximum(model.predict(future_features), 0))
            for row, prediction in zip(rows, predictions):
                quantity = float(prediction)
                rolling_values[(row["Setor"], row["Material"])].append(quantity)
                generated.append({
                    "Data": date,
                    "Setor": row["Setor"],
                    "Material": row["Material"],
                    "Previsao": quantity,
                })
            for row in manual_rows:
                manual_values[(row["Setor"], row["Material"])][row["Data"]] = (
                    row["Sazonal_Manual"]
                )
                manual_generated.append(row)
        forecast_seconds = time.perf_counter() - forecast_start
    finally:
        stop_event.set()
        monitor.join()

    predictions = pd.DataFrame(generated)
    comparison = actual[["Data", "Setor", "Material", "Quantidade_Consumida"]].merge(
        predictions,
        on=["Data", "Setor", "Material"],
        validate="one_to_one",
    )
    manual_predictions = pd.DataFrame(manual_generated)
    comparison = comparison.merge(
        manual_predictions,
        on=["Data", "Setor", "Material"],
        validate="one_to_one",
    )
    errors = comparison["Previsao"] - comparison["Quantidade_Consumida"]
    manual_errors = comparison["Sazonal_Manual"] - comparison["Quantidade_Consumida"]
    real_volume = float(comparison["Quantidade_Consumida"].abs().sum())
    wape = float(errors.abs().sum() / real_volume) if real_volume else None
    manual_wape = (
        float(manual_errors.abs().sum() / real_volume) if real_volume else None
    )
    peak_working_set = max(samples)

    return {
        "modelo": "Random Forest (scikit-learn)",
        "mae": float(mean_absolute_error(comparison["Quantidade_Consumida"], comparison["Previsao"])),
        "rmse": float(np.sqrt(mean_squared_error(comparison["Quantidade_Consumida"], comparison["Previsao"]))),
        "wape": wape,
        "manual_mae": float(mean_absolute_error(
            comparison["Quantidade_Consumida"], comparison["Sazonal_Manual"]
        )),
        "manual_rmse": float(np.sqrt(mean_squared_error(
            comparison["Quantidade_Consumida"], comparison["Sazonal_Manual"]
        ))),
        "manual_wape": manual_wape,
        "manual_total_previsto": float(comparison["Sazonal_Manual"].sum()),
        "vies": float(errors.mean()),
        "total_real": float(comparison["Quantidade_Consumida"].sum()),
        "total_previsto": float(comparison["Previsao"].sum()),
        "sobreprevisoes": int((errors > 0).sum()),
        "subprevisoes": int((errors < 0).sum()),
        "pontos_teste": len(comparison),
        "treino_segundos": training_seconds,
        "previsao_segundos": forecast_seconds,
        "cpu_segundos": time.process_time() - cpu_start,
        "memoria_base_mb": memory_before / (1024 * 1024),
        "pico_memoria_mb": peak_working_set / (1024 * 1024),
        "aumento_pico_memoria_mb": max(0, peak_working_set - memory_before) / (1024 * 1024),
        "previsoes": comparison.assign(
            Data=comparison["Data"].dt.strftime("%Y-%m-%d")
        ).to_dict("records"),
    }


def benchmark_request_payload(history, cutoff, horizon, n_estimators, max_depth):
    observations = history[
        ["Data", "Material", "Setor", "Quantidade_Consumida"]
    ].copy()
    observations["Data"] = pd.to_datetime(observations["Data"]).dt.strftime("%Y-%m-%d")
    return {
        "historico": observations.rename(columns={
            "Quantidade_Consumida": "quantidadeConsumida"
        }).to_dict("records"),
        "corte": pd.Timestamp(cutoff).strftime("%Y-%m-%d"),
        "horizonte": int(horizon),
        "arvores": int(n_estimators),
        "folhas": 20,
        "minLeaf": 5,
        "lr": 0.2,
        "profundidadeRandomForest": int(max_depth),
    }
