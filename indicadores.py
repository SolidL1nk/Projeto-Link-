# indicadores.py - cálculo de indicadores técnicos

import pandas as pd
import numpy as np


def calcular_rsi(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    delta = df['close'].diff()
    ganho = delta.clip(lower=0)
    perda = -delta.clip(upper=0)
    media_ganho = ganho.rolling(window=periodo).mean()
    media_perda = perda.rolling(window=periodo).mean()
    rs = media_ganho / media_perda
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calcular_ema(df: pd.DataFrame, periodo: int = 21) -> pd.Series:
    return df['close'].ewm(span=periodo, adjust=False).mean()


def calcular_macd(df: pd.DataFrame) -> pd.DataFrame:
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histograma = macd - signal
    return pd.DataFrame({
        'macd': macd,
        'signal': signal,
        'histograma': histograma
    })


def adicionar_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['rsi'] = calcular_rsi(df)
    df['ema21'] = calcular_ema(df, 21)
    macd_df = calcular_macd(df)
    df = pd.concat([df, macd_df], axis=1)
    return df
