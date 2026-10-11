"""O tempo, pelo Open-Meteo: grátis, sem cadastro e sem chave.

A cidade não fica chumbada em lugar nenhum: o Claude tira da memória do Léo
("Eu moro em Florianópolis…") e passa como argumento. Coordenadas ficam em
cache na memória do processo; a previsão, por 10 minutos.
"""

from __future__ import annotations

import datetime as dt
import time

import requests

_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_PREVISAO = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO do Open-Meteo, em português falado.
_CEU = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado",
        45: "neblina", 48: "neblina", 51: "garoa fraca", 53: "garoa", 55: "garoa forte",
        61: "chuva fraca", 63: "chuva", 65: "chuva forte", 66: "chuva congelante",
        67: "chuva congelante", 71: "neve fraca", 73: "neve", 75: "neve forte",
        80: "pancadas de chuva fracas", 81: "pancadas de chuva", 82: "pancadas de chuva fortes",
        95: "trovoada", 96: "trovoada com granizo", 99: "trovoada com granizo"}

_coords: dict[str, tuple[float, float, str]] = {}
_previsoes: dict[tuple[float, float], tuple[float, dict]] = {}


class ErroDoClima(RuntimeError):
    pass


def _onde(cidade: str) -> tuple[float, float, str]:
    chave = cidade.strip().lower()
    if chave in _coords:
        return _coords[chave]
    # "Florianópolis, Pantanal": o geocoding acha a cidade; o bairro não muda
    # a previsão de forma que importe.
    nome = cidade.split(",")[0].strip()
    try:
        r = requests.get(_GEO, params={"name": nome, "count": 1, "language": "pt",
                                       "countryCode": "BR"}, timeout=10)
        r.raise_for_status()
        res = (r.json().get("results") or [None])[0]
    except (requests.RequestException, ValueError) as e:
        raise ErroDoClima(f"não consegui achar {nome}: {e.__class__.__name__}") from e
    if not res:
        raise ErroDoClima(f"não achei a cidade {nome}")
    _coords[chave] = (res["latitude"], res["longitude"], res["name"])
    return _coords[chave]


def _previsao(lat: float, lon: float) -> dict:
    chave = (round(lat, 2), round(lon, 2))
    if chave in _previsoes and time.monotonic() - _previsoes[chave][0] < 600:
        return _previsoes[chave][1]
    try:
        r = requests.get(_PREVISAO, params={
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
            "current": "temperature_2m,weather_code,apparent_temperature",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max",
        }, timeout=10)
        r.raise_for_status()
        dados = r.json()
    except (requests.RequestException, ValueError) as e:
        raise ErroDoClima(f"não consegui a previsão: {e.__class__.__name__}") from e
    _previsoes[chave] = (time.monotonic(), dados)
    return dados


def descrever(cidade: str, dia: dt.date) -> str:
    """Texto para o Claude ler e falar do jeito dele."""
    lat, lon, nome = _onde(cidade)
    d = _previsao(lat, lon)
    diario = d["daily"]
    datas = diario["time"]
    iso = dia.isoformat()
    if iso not in datas:
        return f"{nome}: sem previsão para {iso} (só há 7 dias)."
    i = datas.index(iso)
    texto = (f"{nome}, {iso}: {_CEU.get(diario['weather_code'][i], 'tempo variado')}, "
             f"mínima {round(diario['temperature_2m_min'][i])}°C, "
             f"máxima {round(diario['temperature_2m_max'][i])}°C, "
             f"chance de chuva {diario['precipitation_probability_max'][i]}%.")
    if dia == dt.date.today():
        agora = d["current"]
        texto += (f" Agora: {round(agora['temperature_2m'])}°C "
                  f"(sensação {round(agora['apparent_temperature'])}°C), "
                  f"{_CEU.get(agora['weather_code'], 'tempo variado')}.")
    return texto
