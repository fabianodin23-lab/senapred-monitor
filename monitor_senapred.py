#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONITOR SENAPRED v6.1
- Dashboard estilo Grafana (dark theme profesional)
- config.json para configuración
- Modo silencioso nocturno  
- Resumen diario automático
"""

import argparse, json, time, os, sys, re, hashlib, csv
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    from plyer import notification
    NOTIF_OK = True
except ImportError:
    NOTIF_OK = False

CONFIG_DEFAULT = {
    "general": {"intervalo_segundos": 300, "dias_antiguedad": 14, "espera_pagina": 6, "espera_detalle": 4},
    "notificaciones": {"sonido_activado": True, "notificacion_escritorio": True, 
                       "modo_silencioso": {"activado": False, "hora_inicio": "23:00", "hora_fin": "07:00"}},
    "filtros": {"regiones": [], "tipos_alerta": ["roja", "amarilla", "temprana"]},
    "resumen_diario": {"activado": True, "hora_generacion": "08:00", "formato": "html"},
    "archivos": {"estado": "estado_alertas.json", "dashboard": "dashboard_senapred.html", 
                 "datos_js": "datos_alertas.js", "log": "log_alertas.csv", "resumen": "resumen_diario"}
}

REGIONES = ['Arica y Parinacota', 'Tarapacá', 'Antofagasta', 'Atacama', 'Coquimbo', 'Valparaíso', 
            'Metropolitana', "O'Higgins", 'Maule', 'Ñuble', 'Biobío', 'La Araucanía', 'Los Ríos', 
            'Los Lagos', 'Aysén', 'Magallanes']

def cargar_config() -> dict:
    p = Path("config.json")
    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                for k, v in CONFIG_DEFAULT.items():
                    if k not in cfg: cfg[k] = v
                    elif isinstance(v, dict):
                        for kk, vv in v.items():
                            if kk not in cfg[k]: cfg[k][kk] = vv
                return cfg
        except: pass
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(CONFIG_DEFAULT, f, ensure_ascii=False, indent=2)
    print("📝 Creado config.json")
    return CONFIG_DEFAULT.copy()

CONFIG = cargar_config()

def generar_id(url: str) -> str:
    return hashlib.md5(url.lower().strip().encode()).hexdigest()[:16]

@dataclass
class Alerta:
    id: str
    url: str
    tipo: str
    region: str
    comuna: str
    causa: str
    fecha: str
    hora: str
    recursos: str
    superficie: str
    contenido_hash: str
    estado_monitor: str = "activa"
    def to_dict(self): return asdict(self)

@dataclass 
class Cambio:
    alerta_id: str
    tipo_cambio: str
    fecha_hora: str
    descripcion: str

def log(msg: str, nivel: str = "INFO"):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] [{nivel}] {msg}")
    try:
        lf = CONFIG["archivos"]["log"]
        ex = Path(lf).exists()
        with open(lf, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if not ex: w.writerow(['fecha', 'hora', 'nivel', 'mensaje'])
            w.writerow([datetime.now().strftime('%Y-%m-%d'), ts, nivel, msg])
    except: pass

def en_horario_silencioso() -> bool:
    cfg = CONFIG["notificaciones"]["modo_silencioso"]
    if not cfg["activado"]: return False
    try:
        ahora = datetime.now().time()
        ini = datetime.strptime(cfg["hora_inicio"], "%H:%M").time()
        fin = datetime.strptime(cfg["hora_fin"], "%H:%M").time()
        return (ini <= ahora <= fin) if ini <= fin else (ahora >= ini or ahora <= fin)
    except: return False

def notificar(titulo: str, mensaje: str, urgente: bool = False):
    if not CONFIG["notificaciones"]["notificacion_escritorio"]: return
    if en_horario_silencioso() and not urgente: return
    if NOTIF_OK:
        try: notification.notify(title=titulo, message=mensaje[:200], app_name="SENAPRED", timeout=20 if urgente else 10)
        except: pass

def sonido(tipo: str = "nueva"):
    if not CONFIG["notificaciones"]["sonido_activado"] or en_horario_silencioso(): return
    try:
        if sys.platform == 'win32':
            import winsound
            for f, d in {'nueva': [(1000,400)]*3, 'actualizada': [(800,300)], 'cancelada': [(500,600)]}.get(tipo, []):
                winsound.Beep(f, d); time.sleep(0.1)
    except: print('\a')

def filtrar_alertas(alertas: List[Alerta]) -> List[Alerta]:
    r = alertas
    if CONFIG["filtros"]["regiones"]: r = [a for a in r if a.region in CONFIG["filtros"]["regiones"]]
    if CONFIG["filtros"]["tipos_alerta"]: r = [a for a in r if a.tipo in CONFIG["filtros"]["tipos_alerta"]]
    return r


class Scraper:
    def __init__(self, dias_max: int = None):
        self.dias_max = dias_max or CONFIG["general"]["dias_antiguedad"]
        self.driver = None
    
    def _crear_driver(self):
        opts = Options()
        for a in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--window-size=1920,1080', '--log-level=3']:
            opts.add_argument(a)
        opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    def obtener_alertas(self) -> List[Alerta]:
        try:
            log("Iniciando navegador...")
            self.driver = self._crear_driver()
            urls = self._obtener_urls()
            log(f"URLs: {len(urls)}")
            alertas, ids = [], set()
            for i, url in enumerate(urls):
                aid = generar_id(url)
                if aid in ids: continue
                ids.add(aid)
                m = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
                if m:
                    try:
                        if (datetime.now() - datetime(int(m[1]), int(m[2]), int(m[3]))).days > self.dias_max: continue
                    except: pass
                log(f"  [{i+1}/{len(urls)}] {url[-55:]}")
                if a := self._extraer_alerta(url, aid): alertas.append(a)
                time.sleep(0.5)
            alertas = filtrar_alertas(alertas)
            log(f"Total: {len(alertas)}")
            return alertas
        except Exception as e: log(f"Error: {e}", "ERROR"); return []
        finally:
            if self.driver:
                try: self.driver.quit()
                except: pass
    
    def _obtener_urls(self) -> List[str]:
        urls = []
        try:
            self.driver.get('https://senapred.cl/alertas/')
            time.sleep(CONFIG["general"]["espera_pagina"])
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            for l in BeautifulSoup(self.driver.page_source, 'html.parser').find_all('a', href=True):
                h = l['href']
                if '/alerta/' in h and 'alertas' not in h:
                    u = ('https://senapred.cl' + h) if h.startswith('/') else h
                    if u.startswith('http') and u not in urls: urls.append(u)
        except Exception as e: log(f"Error URLs: {e}", "ERROR")
        return urls
    
    def _extraer_alerta(self, url: str, aid: str) -> Optional[Alerta]:
        try:
            self.driver.get(url)
            time.sleep(CONFIG["general"]["espera_detalle"])
            txt = BeautifulSoup(self.driver.page_source, 'html.parser').get_text(' ', strip=True)
            t = txt.lower()
            tipo = 'roja' if 'alerta roja' in t else ('amarilla' if 'alerta amarilla' in t else ('temprana' if 'temprana' in t or 'preventiva' in t else None))
            if not tipo: return None
            m = re.search(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})', url)
            fecha = f"{m[3]}/{m[2]}/{m[1]}" if m else datetime.now().strftime("%d/%m/%Y")
            hora = f"{m[4]}:{m[5]}" if m else "--:--"
            region = next((r for r in REGIONES if r.lower() in t), "No especificada")
            mc = re.search(r'comuna[s]?\s+de\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+por|\s+debido|,\s+por|\.)', txt, re.I)
            comuna = mc[1].strip().title()[:50] if mc else "No especificada"
            causas = {'incendio': 'Incendio Forestal', 'calor': 'Calor Extremo', 'temperatura': 'Altas Temperaturas',
                      'sismo': 'Sismo', 'tsunami': 'Tsunami', 'temporal': 'Temporal', 'tormenta': 'Tormenta Eléctrica',
                      'eléctrica': 'Tormenta Eléctrica', 'volcán': 'Actividad Volcánica', 'volcan': 'Actividad Volcánica',
                      'aluvión': 'Aluvión', 'inundación': 'Inundación', 'marejada': 'Marejada', 'evento masivo': 'Evento Masivo',
                      'material peligroso': 'Material Peligroso'}
            causa = next((v for k, v in causas.items() if k in t), "Emergencia")
            rec = []
            for p, n in [(r'(\d+)\s*brigada', 'brigadas'), (r'(\d+)\s*helic', 'helicópteros')]:
                if mr := re.search(p, t): rec.append(f"{mr[1]} {n}")
            ms = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:hect|ha)', t)
            sup = f"{ms[1]} ha" if ms else ""
            return Alerta(id=aid, url=url, tipo=tipo, region=region, comuna=comuna, causa=causa,
                         fecha=fecha, hora=hora, recursos=", ".join(rec), superficie=sup,
                         contenido_hash=hashlib.md5(txt[:500].encode()).hexdigest()[:16])
        except Exception as e: log(f"    ✗ {e}", "WARN"); return None


class Dashboard:
    def generar(self, alertas: List[Alerta], cambios: List[Cambio], ultima_act: str):
        # Estadísticas
        stats = {
            'total': len(alertas), 
            'rojas': sum(1 for a in alertas if a.tipo == 'roja'),
            'amarillas': sum(1 for a in alertas if a.tipo == 'amarilla'),
            'tempranas': sum(1 for a in alertas if a.tipo == 'temprana'), 
            'ultima_actualizacion': ultima_act,
            'regiones_afectadas': len(set(a.region for a in alertas))
        }
        
        # Estado por región
        estado_regiones = {}
        for region in REGIONES:
            ar = [a for a in alertas if a.region == region]
            if not ar: 
                estado_regiones[region] = {'estado': 'ok', 'total': 0, 'rojas': 0, 'amarillas': 0, 'tempranas': 0}
            else:
                r = sum(1 for a in ar if a.tipo == 'roja')
                am = sum(1 for a in ar if a.tipo == 'amarilla')
                t = sum(1 for a in ar if a.tipo == 'temprana')
                estado_regiones[region] = {
                    'estado': 'roja' if r else ('amarilla' if am else 'temprana'), 
                    'total': len(ar), 'rojas': r, 'amarillas': am, 'tempranas': t
                }
        
        # Por causa
        por_causa = {}
        for a in alertas: 
            por_causa[a.causa] = por_causa.get(a.causa, 0) + 1
        
        # Datos para JS
        datos = {
            'alertas': [a.to_dict() for a in alertas], 
            'cambios': [asdict(c) for c in cambios[-30:]], 
            'stats': stats, 
            'estado_regiones': estado_regiones, 
            'por_causa': por_causa,
            'regiones': REGIONES,
            'modo_silencioso': CONFIG["notificaciones"]["modo_silencioso"]["activado"]
        }
        
        with open(CONFIG["archivos"]["datos_js"], 'w', encoding='utf-8') as f:
            f.write(f"const DATA={json.dumps(datos, ensure_ascii=False)};")
        
        self._generar_html()
        print(f"📊 Dashboard: {CONFIG['archivos']['dashboard']}")
    
    def _generar_html(self):
        html = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SENAPRED Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #111217;
            --bg-panel: #181b1f;
            --bg-card: #1e2228;
            --border: #2a2e35;
            --text: #d8dadd;
            --text-dim: #8b8d91;
            --green: #73bf69;
            --yellow: #fade2a;
            --orange: #ff9830;
            --red: #f2495c;
            --blue: #5794f2;
            --purple: #b877d9;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            font-size: 14px;
        }
        
        /* Header */
        .header {
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .logo {
            font-size: 18px;
            font-weight: 600;
            color: var(--orange);
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            background: var(--bg-card);
            border-radius: 4px;
            font-size: 12px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: 16px;
            font-size: 12px;
            color: var(--text-dim);
        }
        
        /* Main Grid */
        .main {
            padding: 16px;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: auto auto 1fr;
            gap: 12px;
            max-width: 1800px;
            margin: 0 auto;
        }
        
        @media (max-width: 1200px) {
            .main { grid-template-columns: repeat(2, 1fr); }
        }
        
        @media (max-width: 768px) {
            .main { grid-template-columns: 1fr; }
        }
        
        /* Stat Cards */
        .stat-card {
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 16px;
        }
        
        .stat-card-header {
            font-size: 11px;
            text-transform: uppercase;
            color: var(--text-dim);
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .stat-card-value {
            font-size: 32px;
            font-weight: 500;
            line-height: 1;
        }
        
        .stat-card-value.red { color: var(--red); }
        .stat-card-value.yellow { color: var(--yellow); }
        .stat-card-value.blue { color: var(--blue); }
        .stat-card-value.green { color: var(--green); }
        
        .stat-card-sub {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 4px;
        }
        
        /* Panel */
        .panel {
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
        }
        
        .panel-header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-body {
            padding: 12px;
        }
        
        /* Tabla de alertas */
        .alerts-panel {
            grid-column: span 2;
            grid-row: span 2;
        }
        
        .alert-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .alert-table th {
            text-align: left;
            padding: 8px 12px;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--text-dim);
            font-weight: 500;
            border-bottom: 1px solid var(--border);
        }
        
        .alert-table td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }
        
        .alert-table tr:hover {
            background: var(--bg-card);
        }
        
        .alert-table tbody {
            display: block;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .alert-table thead, .alert-table tbody tr {
            display: table;
            width: 100%;
            table-layout: fixed;
        }
        
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge-roja { background: var(--red); color: #fff; }
        .badge-amarilla { background: var(--yellow); color: #000; }
        .badge-temprana { background: var(--blue); color: #fff; }
        
        .link {
            color: var(--blue);
            text-decoration: none;
        }
        
        .link:hover {
            text-decoration: underline;
        }
        
        /* Panel de regiones */
        .regions-panel {
            grid-column: span 2;
        }
        
        .region-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
        }
        
        @media (max-width: 1200px) {
            .region-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        .region-item {
            background: var(--bg-card);
            border-radius: 4px;
            padding: 10px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            border-left: 3px solid var(--green);
        }
        
        .region-item.roja { border-left-color: var(--red); background: rgba(242,73,92,0.1); }
        .region-item.amarilla { border-left-color: var(--yellow); background: rgba(250,222,42,0.1); }
        .region-item.temprana { border-left-color: var(--blue); background: rgba(87,148,242,0.1); }
        
        .region-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .region-count {
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
        }
        
        .region-item.ok .region-count { background: var(--green); color: #000; }
        .region-item.roja .region-count { background: var(--red); }
        .region-item.amarilla .region-count { background: var(--yellow); color: #000; }
        .region-item.temprana .region-count { background: var(--blue); }
        
        /* Charts */
        .charts-row {
            grid-column: span 2;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        
        @media (max-width: 768px) {
            .charts-row { grid-template-columns: 1fr; }
        }
        
        .chart-container {
            height: 200px;
            position: relative;
        }
        
        /* Activity log */
        .activity-panel {
            grid-column: span 2;
        }
        
        .activity-list {
            max-height: 250px;
            overflow-y: auto;
        }
        
        .activity-item {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }
        
        .activity-icon {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            flex-shrink: 0;
        }
        
        .activity-icon.nueva { background: rgba(115,191,105,0.2); color: var(--green); }
        .activity-icon.actualizada { background: rgba(255,152,48,0.2); color: var(--orange); }
        .activity-icon.cancelada { background: rgba(139,141,145,0.2); color: var(--text-dim); }
        
        .activity-content {
            flex: 1;
        }
        
        .activity-text {
            font-size: 13px;
        }
        
        .activity-time {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 2px;
        }
        
        /* Footer */
        .footer {
            padding: 16px 24px;
            text-align: center;
            font-size: 11px;
            color: var(--text-dim);
            border-top: 1px solid var(--border);
        }
        
        .footer a {
            color: var(--blue);
            text-decoration: none;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-dark); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }
        
        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-dim);
        }
        
        .empty-state-icon {
            font-size: 32px;
            margin-bottom: 12px;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <div class="logo">⚡ SENAPRED Monitor</div>
            <div class="status-badge">
                <span class="status-dot"></span>
                <span>Activo</span>
            </div>
        </div>
        <div class="header-right">
            <span id="last-update">Cargando...</span>
            <span>|</span>
            <span>Próxima actualización: <strong id="countdown">30</strong>s</span>
        </div>
    </header>
    
    <main class="main">
        <!-- Stat Cards Row -->
        <div class="stat-card">
            <div class="stat-card-header">Total Alertas</div>
            <div class="stat-card-value" id="stat-total">0</div>
            <div class="stat-card-sub" id="stat-regiones">0 regiones afectadas</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-card-header">Alertas Rojas</div>
            <div class="stat-card-value red" id="stat-rojas">0</div>
            <div class="stat-card-sub">Máxima prioridad</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-card-header">Alertas Amarillas</div>
            <div class="stat-card-value yellow" id="stat-amarillas">0</div>
            <div class="stat-card-sub">Prioridad media</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-card-header">Alertas Tempranas</div>
            <div class="stat-card-value blue" id="stat-tempranas">0</div>
            <div class="stat-card-sub">Preventivas</div>
        </div>
        
        <!-- Alerts Table -->
        <div class="panel alerts-panel">
            <div class="panel-header">
                <span>📋 Alertas Activas</span>
                <span id="alert-count" style="color: var(--text-dim)">0 alertas</span>
            </div>
            <div class="panel-body" style="padding: 0;">
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th style="width: 80px;">Tipo</th>
                            <th style="width: 140px;">Región</th>
                            <th>Causa</th>
                            <th style="width: 90px;">Fecha</th>
                            <th style="width: 60px;">Link</th>
                        </tr>
                    </thead>
                    <tbody id="alerts-body">
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Regions Panel -->
        <div class="panel regions-panel">
            <div class="panel-header">
                <span>🗺️ Estado por Región</span>
            </div>
            <div class="panel-body">
                <div class="region-grid" id="regions-grid">
                </div>
            </div>
        </div>
        
        <!-- Charts Row -->
        <div class="charts-row">
            <div class="panel">
                <div class="panel-header">Por Tipo de Alerta</div>
                <div class="panel-body">
                    <div class="chart-container">
                        <canvas id="chart-tipos"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">Por Tipo de Amenaza</div>
                <div class="panel-body">
                    <div class="chart-container">
                        <canvas id="chart-causas"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Activity Panel -->
        <div class="panel activity-panel">
            <div class="panel-header">
                <span>🔔 Actividad Reciente</span>
            </div>
            <div class="panel-body" style="padding: 0;">
                <div class="activity-list" id="activity-list">
                </div>
            </div>
        </div>
    </main>
    
    <footer class="footer">
        <p>Datos de <a href="https://senapred.cl/alertas/" target="_blank">SENAPRED</a> | 
           Emergencias: CONAF 130 • Bomberos 132 • Carabineros 133 • Ambulancia 131</p>
    </footer>
    
    <script src="datos_alertas.js"></script>
    <script>
        let charts = {};
        
        function init() {
            if (typeof DATA === 'undefined') {
                setTimeout(init, 500);
                return;
            }
            
            // Stats
            document.getElementById('stat-total').textContent = DATA.stats.total;
            document.getElementById('stat-rojas').textContent = DATA.stats.rojas;
            document.getElementById('stat-amarillas').textContent = DATA.stats.amarillas;
            document.getElementById('stat-tempranas').textContent = DATA.stats.tempranas;
            document.getElementById('stat-regiones').textContent = DATA.stats.regiones_afectadas + ' regiones afectadas';
            document.getElementById('last-update').textContent = 'Actualizado: ' + DATA.stats.ultima_actualizacion;
            document.getElementById('alert-count').textContent = DATA.stats.total + ' alertas';
            
            // Alerts table
            const tbody = document.getElementById('alerts-body');
            if (DATA.alertas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="empty-state-icon">✅</div><div>Sin alertas activas</div></div></td></tr>';
            } else {
                const sorted = DATA.alertas.sort((a, b) => {
                    const order = {roja: 0, amarilla: 1, temprana: 2};
                    return (order[a.tipo] || 3) - (order[b.tipo] || 3);
                });
                tbody.innerHTML = sorted.map(a => `
                    <tr>
                        <td><span class="badge badge-${a.tipo}">${a.tipo}</span></td>
                        <td>${a.region}</td>
                        <td>${a.causa}${a.superficie ? ' <span style="color:var(--text-dim)">(' + a.superficie + ')</span>' : ''}</td>
                        <td>${a.fecha}</td>
                        <td><a href="${a.url}" target="_blank" class="link">Ver →</a></td>
                    </tr>
                `).join('');
            }
            
            // Regions grid
            const rgrid = document.getElementById('regions-grid');
            rgrid.innerHTML = DATA.regiones.map(r => {
                const info = DATA.estado_regiones[r] || {estado: 'ok', total: 0};
                return `
                    <div class="region-item ${info.estado}">
                        <span class="region-name">${r}</span>
                        <span class="region-count">${info.estado === 'ok' ? '✓' : info.total}</span>
                    </div>
                `;
            }).join('');
            
            // Activity log
            const alist = document.getElementById('activity-list');
            if (DATA.cambios.length === 0) {
                alist.innerHTML = '<div class="empty-state"><div>Sin actividad reciente</div></div>';
            } else {
                const icons = {nueva: '➕', actualizada: '🔄', cancelada: '❌'};
                alist.innerHTML = DATA.cambios.slice().reverse().map(c => `
                    <div class="activity-item">
                        <div class="activity-icon ${c.tipo_cambio}">${icons[c.tipo_cambio] || '•'}</div>
                        <div class="activity-content">
                            <div class="activity-text">${c.descripcion}</div>
                            <div class="activity-time">${c.fecha_hora}</div>
                        </div>
                    </div>
                `).join('');
            }
            
            // Charts
            Chart.defaults.color = '#8b8d91';
            Chart.defaults.borderColor = '#2a2e35';
            
            const ctx1 = document.getElementById('chart-tipos').getContext('2d');
            if (charts.tipos) charts.tipos.destroy();
            charts.tipos = new Chart(ctx1, {
                type: 'doughnut',
                data: {
                    labels: ['Rojas', 'Amarillas', 'Tempranas'],
                    datasets: [{
                        data: [DATA.stats.rojas, DATA.stats.amarillas, DATA.stats.tempranas],
                        backgroundColor: ['#f2495c', '#fade2a', '#5794f2'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { boxWidth: 12, padding: 12 }
                        }
                    }
                }
            });
            
            const ctx2 = document.getElementById('chart-causas').getContext('2d');
            if (charts.causas) charts.causas.destroy();
            const causas = Object.entries(DATA.por_causa).sort((a, b) => b[1] - a[1]).slice(0, 6);
            charts.causas = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: causas.map(c => c[0].length > 15 ? c[0].substring(0, 15) + '...' : c[0]),
                    datasets: [{
                        data: causas.map(c => c[1]),
                        backgroundColor: ['#f2495c', '#ff9830', '#fade2a', '#73bf69', '#5794f2', '#b877d9'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: '#2a2e35' }, ticks: { stepSize: 1 } },
                        y: { grid: { display: false } }
                    }
                }
            });
        }
        
        // Countdown
        let count = 30;
        setInterval(() => {
            count--;
            document.getElementById('countdown').textContent = count;
            if (count <= 0) {
                count = 30;
                location.reload();
            }
        }, 1000);
        
        init();
    </script>
</body>
</html>'''
        
        with open(CONFIG["archivos"]["dashboard"], 'w', encoding='utf-8') as f:
            f.write(html)


class ResumenDiario:
    def __init__(self, alertas, cambios):
        self.alertas = alertas
        self.cambios = cambios
        self.fecha = datetime.now().strftime("%Y-%m-%d")
    
    def generar(self):
        if not CONFIG["resumen_diario"]["activado"]: return
        fn = f"{CONFIG['archivos']['resumen']}_{self.fecha}.html"
        r = sum(1 for a in self.alertas if a.tipo=='roja')
        am = sum(1 for a in self.alertas if a.tipo=='amarilla')
        t = sum(1 for a in self.alertas if a.tipo=='temprana')
        hoy = datetime.now().strftime("%d/%m/%Y")
        ch = [c for c in self.cambios if hoy in c.fecha_hora]
        
        html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Resumen {self.fecha}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.header {{ background: #1a1a2e; color: #fff; padding: 24px; border-radius: 8px; margin-bottom: 20px; }}
.header h1 {{ margin: 0 0 8px 0; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
.stat {{ background: #fff; padding: 16px; border-radius: 8px; text-align: center; }}
.stat-num {{ font-size: 28px; font-weight: 700; }}
.stat-num.r {{ color: #f2495c; }}
.stat-num.a {{ color: #fade2a; }}
.stat-num.t {{ color: #5794f2; }}
.section {{ background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
.section h2 {{ margin: 0 0 12px 0; font-size: 16px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-size: 12px; text-transform: uppercase; }}
.badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.badge.roja {{ background: #f2495c; color: #fff; }}
.badge.amarilla {{ background: #fade2a; }}
.badge.temprana {{ background: #5794f2; color: #fff; }}
</style></head>
<body>
<div class="header">
    <h1>📊 Resumen Diario SENAPRED</h1>
    <p>Fecha: {self.fecha}</p>
</div>
<div class="stats">
    <div class="stat"><div class="stat-num">{len(self.alertas)}</div><div>Total</div></div>
    <div class="stat"><div class="stat-num r">{r}</div><div>Rojas</div></div>
    <div class="stat"><div class="stat-num a">{am}</div><div>Amarillas</div></div>
    <div class="stat"><div class="stat-num t">{t}</div><div>Tempranas</div></div>
</div>
<div class="section">
    <h2>Alertas Activas</h2>
    <table>
        <tr><th>Tipo</th><th>Región</th><th>Causa</th><th>Fecha</th></tr>
        {''.join(f'<tr><td><span class="badge {a.tipo}">{a.tipo.upper()}</span></td><td>{a.region}</td><td>{a.causa}</td><td>{a.fecha}</td></tr>' for a in self.alertas) or '<tr><td colspan="4" style="text-align:center;color:#888;">Sin alertas</td></tr>'}
    </table>
</div>
<div class="section">
    <h2>Cambios del Día ({len(ch)})</h2>
    <table>
        <tr><th>Tipo</th><th>Hora</th><th>Descripción</th></tr>
        {''.join(f'<tr><td>{c.tipo_cambio}</td><td>{c.fecha_hora}</td><td>{c.descripcion}</td></tr>' for c in ch) or '<tr><td colspan="3" style="text-align:center;color:#888;">Sin cambios</td></tr>'}
    </table>
</div>
<p style="text-align:center;color:#888;font-size:12px;">Monitor SENAPRED v6.1</p>
</body></html>'''
        
        with open(fn, 'w', encoding='utf-8') as f: 
            f.write(html)
        log(f"📋 Resumen: {fn}")


class Monitor:
    def __init__(self, intervalo=None, con_sonido=None, dias_max=None):
        self.intervalo = intervalo or CONFIG["general"]["intervalo_segundos"]
        self.con_sonido = con_sonido if con_sonido is not None else CONFIG["notificaciones"]["sonido_activado"]
        self.dias_max = dias_max or CONFIG["general"]["dias_antiguedad"]
        self.scraper = Scraper(self.dias_max)
        self.dashboard = Dashboard()
        self.alertas: Dict[str, Alerta] = {}
        self.cambios: List[Cambio] = []
        self.ultimo_resumen = None
        self._cargar()
    
    def _cargar(self):
        try:
            ef = CONFIG["archivos"]["estado"]
            if Path(ef).exists():
                with open(ef, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    for a in d.get('alertas', []): 
                        self.alertas[a['id']] = Alerta(**a)
                    for c in d.get('cambios', []): 
                        self.cambios.append(Cambio(**c))
                log(f"Cargado: {len(self.alertas)} alertas")
        except: pass
    
    def _guardar(self):
        try:
            with open(CONFIG["archivos"]["estado"], 'w', encoding='utf-8') as f:
                json.dump({
                    'alertas': [a.to_dict() for a in self.alertas.values()], 
                    'cambios': [asdict(c) for c in self.cambios[-100:]]
                }, f, ensure_ascii=False)
        except: pass
    
    def _detectar_cambios(self, nuevas):
        n, u, c = [], [], []
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        ids = {a.id for a in nuevas}
        
        for a in nuevas:
            if a.id not in self.alertas:
                n.append(a)
                self.alertas[a.id] = a
                self.cambios.append(Cambio(a.id, "nueva", ahora, f"{a.tipo.upper()}: {a.region} - {a.causa}"))
            elif a.contenido_hash != self.alertas[a.id].contenido_hash:
                u.append(a)
                self.alertas[a.id] = a
                self.cambios.append(Cambio(a.id, "actualizada", ahora, f"{a.tipo.upper()}: {a.region}"))
        
        for id in list(self.alertas.keys()):
            if id not in ids and self.alertas[id].estado_monitor != "cancelada":
                self.alertas[id].estado_monitor = "cancelada"
                c.append(self.alertas[id])
                self.cambios.append(Cambio(id, "cancelada", ahora, f"{self.alertas[id].tipo.upper()}: {self.alertas[id].region}"))
        
        return n, u, c
    
    def _check_resumen(self):
        if not CONFIG["resumen_diario"]["activado"]: return
        try:
            hg = CONFIG["resumen_diario"]["hora_generacion"]
            ahora = datetime.now()
            ho = datetime.strptime(hg, "%H:%M").time()
            if self.ultimo_resumen == ahora.date(): return
            if ahora.time() >= ho:
                act = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
                ResumenDiario(act, self.cambios).generar()
                self.ultimo_resumen = ahora.date()
        except: pass
    
    def ejecutar(self):
        os.system('cls' if sys.platform == 'win32' else 'clear')
        sil = ""
        if CONFIG["notificaciones"]["modo_silencioso"]["activado"]:
            ms = CONFIG["notificaciones"]["modo_silencioso"]
            sil = f" | 🔇 {ms['hora_inicio']}-{ms['hora_fin']}"
        flt = f" | 🗺️ {len(CONFIG['filtros']['regiones'])} reg" if CONFIG["filtros"]["regiones"] else ""
        
        print(f'''
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ⚡ MONITOR SENAPRED v6.1 ⚡                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
  ⏱️  Intervalo: {self.intervalo//60} min | 📆 Días: {self.dias_max} | 🔊 Sonido: {'ON' if self.con_sonido else 'OFF'}{sil}{flt}
  📊 Dashboard: {CONFIG['archivos']['dashboard']}
        ''')
        
        act = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
        self.dashboard.generar(act, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        while True:
            try:
                self._check_resumen()
                st = " 🔇" if en_horario_silencioso() else ""
                print(f"\n🔄 Consultando...{st} [{datetime.now().strftime('%H:%M:%S')}]")
                
                alertas = self.scraper.obtener_alertas()
                n, u, c = self._detectar_cambios(alertas)
                
                if n:
                    print(f"🆕 {len(n)} NUEVA(S)")
                    for a in n: 
                        print(f"   {'🔴' if a.tipo=='roja' else '🟡' if a.tipo=='amarilla' else '🔵'} {a.region} - {a.causa}")
                    if self.con_sonido: sonido("nueva")
                    for a in n: 
                        notificar(f"🆕 {a.tipo.upper()}", f"{a.region}\n{a.causa}", a.tipo=='roja')
                
                if u: 
                    print(f"🔄 {len(u)} ACTUALIZADA(S)")
                    if self.con_sonido: sonido("actualizada")
                
                if c: 
                    print(f"❌ {len(c)} CANCELADA(S)")
                    if self.con_sonido: sonido("cancelada")
                
                if not n and not u and not c: 
                    print("✓ Sin cambios")
                
                self._guardar()
                act = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
                self.dashboard.generar(act, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
                
                print(f"📋 Total: {len(act)} alertas activas")
                print(f"⏳ Próxima consulta en {self.intervalo//60} min...")
                time.sleep(self.intervalo)
                
            except KeyboardInterrupt: 
                print("\n👋 Monitor detenido")
                self._guardar()
                break
            except Exception as e: 
                log(f"Error: {e}", "ERROR")
                time.sleep(60)


def main():
    p = argparse.ArgumentParser(description='Monitor SENAPRED v6.1')
    p.add_argument('--monitor', '-m', action='store_true', help='Modo monitoreo continuo')
    p.add_argument('--intervalo', '-i', type=int, help='Segundos entre consultas')
    p.add_argument('--sound', '-s', action='store_true', help='Activar sonido')
    p.add_argument('--dias', '-d', type=int, help='Días de antigüedad')
    p.add_argument('--resumen', '-r', action='store_true', help='Generar resumen ahora')
    p.add_argument('--config', '-c', action='store_true', help='Ver configuración')
    args = p.parse_args()
    
    if not SELENIUM_OK or not BS4_OK: 
        print("❌ Instalar: pip install selenium webdriver-manager beautifulsoup4 plyer")
        return
    
    if args.config: 
        print(json.dumps(CONFIG, ensure_ascii=False, indent=2))
        return
    
    if args.resumen:
        try:
            with open(CONFIG["archivos"]["estado"], 'r', encoding='utf-8') as f:
                d = json.load(f)
                al = [Alerta(**a) for a in d.get('alertas', []) if a.get('estado_monitor') != 'cancelada']
                cm = [Cambio(**c) for c in d.get('cambios', [])]
                ResumenDiario(al, cm).generar()
        except Exception as e: 
            print(f"Error: {e}")
        return
    
    if args.sound: 
        CONFIG["notificaciones"]["sonido_activado"] = True
    
    if args.monitor: 
        Monitor(args.intervalo, args.sound, args.dias).ejecutar()
    else:
        dias = args.dias or CONFIG['general']['dias_antiguedad']
        print(f"\n🔍 Consultando SENAPRED (últimos {dias} días)...\n")
        alertas = Scraper(dias).obtener_alertas()
        
        print(f"\n{'═'*60}")
        print(f"  ⚡ {len(alertas)} ALERTAS ENCONTRADAS")
        print(f"{'═'*60}\n")
        
        for a in sorted(alertas, key=lambda x: (0 if x.tipo=='roja' else 1 if x.tipo=='amarilla' else 2)):
            icon = '🔴' if a.tipo=='roja' else '🟡' if a.tipo=='amarilla' else '🔵'
            print(f"{icon} [{a.tipo.upper():8}] {a.region}")
            print(f"   📅 {a.fecha} | ⚠️  {a.causa}")
            if a.superficie:
                print(f"   🔥 {a.superficie}")
            print()
        
        Dashboard().generar(alertas, [], datetime.now().strftime("%d/%m/%Y %H:%M"))
        print(f"{'═'*60}")
        print(f"📊 Dashboard generado: {CONFIG['archivos']['dashboard']}")


if __name__ == "__main__": 
    main()
