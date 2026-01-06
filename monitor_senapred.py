#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MONITOR DE ALERTAS SENAPRED v5.0                          ║
║                                                                              ║
║  ✅ Extracción COMPLETA de información de cada alerta                        ║
║  ✅ Sin duplicados                                                           ║
║  ✅ Dashboard HTML detallado con toda la información                         ║
║  ✅ Detecta cambios de estado                                                ║
║  ✅ Notificaciones y sonidos                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import json
import time
import os
import sys
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Tuple, Set
from urllib.parse import urljoin
import hashlib

# ==============================================================================
# DEPENDENCIAS
# ==============================================================================

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
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


# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

CONFIG = {
    'url_alertas': 'https://senapred.cl/alertas/',
    'url_base': 'https://senapred.cl',
    'intervalo_default': 300,
    'espera_react': 6,
    'espera_detalle': 5,
    'archivo_estado': 'estado_alertas.json',
    'archivo_log': 'log_alertas.txt',
    'archivo_html': 'dashboard_senapred.html',
    'archivo_datos_js': 'datos_alertas.js',
    'sonido_alerta': True,
    'dias_antiguedad_maxima': 14,
}

REGIONES_CHILE = [
    'Arica y Parinacota', 'Tarapacá', 'Antofagasta', 'Atacama', 'Coquimbo',
    'Valparaíso', 'Metropolitana', "O'Higgins", 'Maule', 'Ñuble', 'Biobío',
    'La Araucanía', 'Los Ríos', 'Los Lagos', 'Aysén', 'Magallanes'
]

MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}


# ==============================================================================
# CLASE ALERTA - ESTRUCTURA COMPLETA
# ==============================================================================

@dataclass
class Alerta:
    """Estructura completa de una alerta SENAPRED con toda la información"""
    # Identificación
    id: str
    url: str
    
    # Tipo y nivel
    tipo: str                    # roja, amarilla, temprana
    nivel_alerta: str            # Alerta Roja, Alerta Amarilla, Alerta Temprana Preventiva
    
    # Ubicación
    region: str
    provincias: str              # Provincias afectadas
    comunas: str                 # Comunas afectadas
    zonas_afectadas: str         # Cordillera costa, valle, precordillera, etc.
    
    # Información del evento
    amenaza: str                 # Tipo de amenaza (calor intenso, incendio, etc.)
    causa: str                   # Causa detallada
    descripcion: str             # Descripción completa del evento
    
    # Fechas y vigencia
    fecha_declaracion: str       # Fecha de declaración
    hora_declaracion: str        # Hora de declaración
    fecha_inicio_evento: str     # Cuando inicia el evento
    fecha_fin_evento: str        # Cuando termina el evento
    vigencia: str                # Estado de vigencia
    
    # Información meteorológica
    aviso_meteorologico: str     # Número de aviso DMC
    temperaturas_esperadas: str  # Temperaturas proyectadas
    condiciones: str             # Condiciones meteorológicas
    
    # Recursos y respuesta
    recursos_desplegados: str    # Recursos movilizados
    acciones_realizadas: str     # Acciones tomadas
    
    # Recomendaciones
    recomendaciones: str         # Recomendaciones a la población
    
    # Información adicional
    superficie_afectada: str     # Hectáreas (para incendios)
    alertas_relacionadas: str    # Otras alertas vigentes
    fuente_informacion: str      # DMC, CONAF, etc.
    
    # Metadatos del monitor
    fecha_deteccion: str
    estado_monitor: str          # activa, actualizada, cancelada
    contenido_hash: str
    dias_antiguedad: int = 0
    
    def to_dict(self):
        return asdict(self)


@dataclass 
class CambioEstado:
    """Registro de cambio"""
    alerta_id: str
    tipo_cambio: str
    fecha_hora: str
    descripcion: str


# ==============================================================================
# UTILIDADES
# ==============================================================================

def log(mensaje: str, nivel: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] [{nivel}] {mensaje}"
    print(linea)
    try:
        with open(CONFIG['archivo_log'], 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except:
        pass


def parsear_fecha_desde_url(url: str) -> Tuple[str, str]:
    """Extrae fecha y hora de la URL de SENAPRED"""
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})$', url)
    if match:
        año, mes, dia, hora, minuto, segundo = match.groups()
        fecha = f"{dia}/{mes}/{año}"
        hora_str = f"{hora}:{minuto}"
        return fecha, hora_str
    return "", ""


def parsear_fecha_texto(texto: str) -> Tuple[str, str]:
    """Parsea fecha y hora del texto"""
    fecha_str = ""
    hora_str = ""
    
    hora_match = re.search(r'(\d{1,2}):(\d{2})', texto)
    if hora_match:
        hora_str = f"{int(hora_match.group(1)):02d}:{hora_match.group(2)}"
    
    fecha_match = re.search(r'(\d{1,2})\s*de\s*([a-záéíóú]+)\s*(?:de\s*)?(\d{4})', texto.lower())
    if fecha_match:
        dia = int(fecha_match.group(1))
        mes = MESES_ES.get(fecha_match.group(2), 1)
        año = int(fecha_match.group(3))
        fecha_str = f"{dia:02d}/{mes:02d}/{año}"
    
    return fecha_str, hora_str


def extraer_rango_fechas(texto: str) -> Tuple[str, str]:
    """Extrae rango de fechas del texto (inicio - fin del evento)"""
    inicio = ""
    fin = ""
    
    # Patrón: "entre el miércoles 07 y el viernes 09 de enero"
    match = re.search(r'entre\s+el\s+\w+\s+(\d{1,2})\s+y\s+el\s+\w+\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?', texto.lower())
    if match:
        dia_inicio = int(match.group(1))
        dia_fin = int(match.group(2))
        mes = MESES_ES.get(match.group(3), 1)
        año = int(match.group(4)) if match.group(4) else datetime.now().year
        inicio = f"{dia_inicio:02d}/{mes:02d}/{año}"
        fin = f"{dia_fin:02d}/{mes:02d}/{año}"
    
    # Patrón: "desde el 2 de noviembre"
    if not inicio:
        match = re.search(r'desde\s+el\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?', texto.lower())
        if match:
            dia = int(match.group(1))
            mes = MESES_ES.get(match.group(2), 1)
            año = int(match.group(3)) if match.group(3) else datetime.now().year
            inicio = f"{dia:02d}/{mes:02d}/{año}"
    
    return inicio, fin


def calcular_antiguedad_dias(fecha_str: str) -> int:
    try:
        if '/' in fecha_str:
            dia, mes, año = map(int, fecha_str.split('/'))
            fecha = datetime(año, mes, dia)
            return (datetime.now() - fecha).days
    except:
        pass
    return 0


def generar_id_desde_url(url: str) -> str:
    partes = url.rstrip('/').split('/')
    if partes:
        return partes[-1][:80]
    return hashlib.md5(url.encode()).hexdigest()[:12]


def notificar(titulo: str, mensaje: str, urgente: bool = False):
    if NOTIF_OK:
        try:
            notification.notify(title=titulo, message=mensaje[:200], 
                              app_name="SENAPRED", timeout=20 if urgente else 10)
        except:
            pass


def sonido(tipo: str = "nueva"):
    if not CONFIG['sonido_alerta']:
        return
    try:
        if sys.platform == 'win32':
            import winsound
            if tipo == "nueva":
                for _ in range(3):
                    winsound.Beep(1000, 400)
                    time.sleep(0.1)
            elif tipo == "actualizada":
                winsound.Beep(800, 300)
            elif tipo == "cancelada":
                winsound.Beep(500, 600)
    except:
        print('\a')


# ==============================================================================
# SCRAPER MEJORADO CON EXTRACCIÓN COMPLETA
# ==============================================================================

class SenapredScraper:
    """Scraper que extrae TODA la información de cada alerta"""
    
    def __init__(self, headless: bool = True, dias_max: int = 14):
        self.headless = headless
        self.dias_max = dias_max
        self.driver = None
    
    def _crear_driver(self):
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--log-level=3')
        
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    
    def obtener_alertas(self) -> List[Alerta]:
        """Obtiene alertas con información completa"""
        try:
            log("Iniciando navegador...")
            self.driver = self._crear_driver()
            
            # Paso 1: Obtener lista de URLs
            urls_alertas = self._obtener_lista_urls()
            log(f"Encontradas {len(urls_alertas)} URLs de alertas")
            
            if not urls_alertas:
                return []
            
            # Paso 2: Obtener detalles completos de cada alerta
            alertas = []
            urls_procesadas: Set[str] = set()
            
            for i, url in enumerate(urls_alertas):
                url_normalizada = url.rstrip('/').lower()
                if url_normalizada in urls_procesadas:
                    continue
                urls_procesadas.add(url_normalizada)
                
                # Filtrar por fecha
                fecha_url, _ = parsear_fecha_desde_url(url)
                if fecha_url:
                    dias = calcular_antiguedad_dias(fecha_url)
                    if dias > self.dias_max:
                        continue
                
                log(f"  [{i+1}/{len(urls_alertas)}] Extrayendo: {url[-60:]}")
                alerta = self._extraer_detalle_completo(url)
                
                if alerta and not any(a.id == alerta.id for a in alertas):
                    alertas.append(alerta)
                
                time.sleep(0.5)
            
            log(f"Total alertas extraídas: {len(alertas)}")
            return alertas
            
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            return []
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
    
    def _obtener_lista_urls(self) -> List[str]:
        """Obtiene URLs de alertas desde la página principal"""
        urls = []
        
        try:
            log(f"Cargando {CONFIG['url_alertas']}...")
            self.driver.get(CONFIG['url_alertas'])
            time.sleep(CONFIG['espera_react'])
            
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/alerta/' in href and 'alertas' not in href:
                    if href.startswith('/'):
                        url_completa = CONFIG['url_base'] + href
                    elif href.startswith('http'):
                        url_completa = href
                    else:
                        continue
                    
                    if url_completa not in urls:
                        urls.append(url_completa)
            
        except Exception as e:
            log(f"Error obteniendo lista: {e}", "ERROR")
        
        return urls
    
    def _extraer_detalle_completo(self, url: str) -> Optional[Alerta]:
        """Extrae TODA la información de una alerta"""
        try:
            self.driver.get(url)
            time.sleep(CONFIG['espera_detalle'])
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            texto_completo = soup.get_text(separator='\n', strip=True)
            
            # Guardar HTML para debug
            with open('ultimo_detalle.html', 'w', encoding='utf-8') as f:
                f.write(html)
            
            # Fecha y hora desde URL
            fecha_url, hora_url = parsear_fecha_desde_url(url)
            
            # Detectar tipo
            tipo = self._detectar_tipo(texto_completo)
            if not tipo:
                return None
            
            # Extraer toda la información
            alerta = Alerta(
                # Identificación
                id=generar_id_desde_url(url),
                url=url,
                
                # Tipo y nivel
                tipo=tipo,
                nivel_alerta=self._extraer_nivel_alerta(texto_completo),
                
                # Ubicación
                region=self._extraer_region(texto_completo),
                provincias=self._extraer_provincias(texto_completo),
                comunas=self._extraer_comunas(texto_completo),
                zonas_afectadas=self._extraer_zonas(texto_completo),
                
                # Información del evento
                amenaza=self._extraer_amenaza(texto_completo),
                causa=self._extraer_causa_detallada(texto_completo),
                descripcion=self._extraer_descripcion(texto_completo),
                
                # Fechas y vigencia
                fecha_declaracion=fecha_url or datetime.now().strftime("%d/%m/%Y"),
                hora_declaracion=hora_url or "--:--",
                fecha_inicio_evento=self._extraer_fecha_inicio(texto_completo),
                fecha_fin_evento=self._extraer_fecha_fin(texto_completo),
                vigencia=self._extraer_vigencia(texto_completo),
                
                # Información meteorológica
                aviso_meteorologico=self._extraer_aviso_dmc(texto_completo),
                temperaturas_esperadas=self._extraer_temperaturas(texto_completo),
                condiciones=self._extraer_condiciones(texto_completo),
                
                # Recursos y respuesta
                recursos_desplegados=self._extraer_recursos(texto_completo),
                acciones_realizadas=self._extraer_acciones(texto_completo),
                
                # Recomendaciones
                recomendaciones=self._extraer_recomendaciones(texto_completo),
                
                # Información adicional
                superficie_afectada=self._extraer_superficie(texto_completo),
                alertas_relacionadas=self._extraer_alertas_relacionadas(texto_completo),
                fuente_informacion=self._extraer_fuente(texto_completo),
                
                # Metadatos
                fecha_deteccion=datetime.now().strftime("%d/%m/%Y %H:%M"),
                estado_monitor="activa",
                contenido_hash=hashlib.md5(texto_completo[:1000].encode()).hexdigest()[:16],
                dias_antiguedad=calcular_antiguedad_dias(fecha_url) if fecha_url else 0
            )
            
            return alerta
            
        except Exception as e:
            log(f"Error extrayendo {url}: {e}", "WARN")
            return None
    
    # =========================================================================
    # MÉTODOS DE EXTRACCIÓN ESPECÍFICOS
    # =========================================================================
    
    def _detectar_tipo(self, texto: str) -> Optional[str]:
        t = texto.lower()
        if 'alerta roja' in t:
            return 'roja'
        elif 'alerta amarilla' in t:
            return 'amarilla'
        elif 'alerta temprana' in t or 'preventiva' in t:
            return 'temprana'
        return None
    
    def _extraer_nivel_alerta(self, texto: str) -> str:
        t = texto.lower()
        if 'alerta roja' in t:
            return "Alerta Roja"
        elif 'alerta amarilla' in t:
            return "Alerta Amarilla"
        elif 'alerta temprana preventiva' in t:
            return "Alerta Temprana Preventiva"
        return "No especificado"
    
    def _extraer_region(self, texto: str) -> str:
        t = texto.lower()
        for region in REGIONES_CHILE:
            if region.lower() in t:
                return region
        # Buscar patrón "Región del/de la X"
        match = re.search(r'regi[oó]n\s+(?:del?|de\s+la)\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s\']+?)(?:\s+por|\s*,|\s*\.)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "No especificada"
    
    def _extraer_provincias(self, texto: str) -> str:
        provincias = []
        # Buscar "provincias de X, Y y Z"
        match = re.search(r'provincia[s]?\s+(?:de\s+)?([^\.]+?)(?:\s+por|\s*\.)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
        return ""
    
    def _extraer_comunas(self, texto: str) -> str:
        # Buscar "comuna de X" o "comunas de X, Y, Z"
        match = re.search(r'comuna[s]?\s+(?:de\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ,\s]+?)(?:\s+por|\s+debido|\s*\.)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
        return ""
    
    def _extraer_zonas(self, texto: str) -> str:
        zonas = []
        zonas_posibles = [
            'cordillera de la costa', 'cordillera costa', 'litoral', 
            'valle', 'valles', 'precordillera', 'costa', 'interior',
            'valles interiores', 'sectores costeros', 'zona cordillerana'
        ]
        t = texto.lower()
        for zona in zonas_posibles:
            if zona in t:
                zonas.append(zona.title())
        return ", ".join(set(zonas)) if zonas else ""
    
    def _extraer_amenaza(self, texto: str) -> str:
        amenazas = {
            'calor extremo': 'Calor Extremo',
            'calor intenso': 'Calor Intenso',
            'altas temperaturas': 'Altas Temperaturas',
            'incendio forestal': 'Incendio Forestal',
            'incendios forestales': 'Incendios Forestales',
            'tsunami': 'Tsunami',
            'sismo': 'Sismo',
            'terremoto': 'Terremoto',
            'marejadas': 'Marejadas',
            'temporal': 'Temporal',
            'lluvias intensas': 'Lluvias Intensas',
            'vientos fuertes': 'Vientos Fuertes',
            'nevazón': 'Nevazón',
            'actividad volcánica': 'Actividad Volcánica',
            'aluvión': 'Aluvión',
            'deslizamiento': 'Deslizamiento',
        }
        t = texto.lower()
        for clave, valor in amenazas.items():
            if clave in t:
                return valor
        return "Emergencia"
    
    def _extraer_causa_detallada(self, texto: str) -> str:
        # Buscar "por X" después de alerta
        match = re.search(r'(?:alerta\s+\w+)\s+(?:para\s+[^,]+)?\s*por\s+([^\.]+)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:300]
        return self._extraer_amenaza(texto)
    
    def _extraer_descripcion(self, texto: str) -> str:
        # Buscar párrafos descriptivos
        parrafos = []
        
        # Patrón: "De acuerdo con..."
        match = re.search(r'(De acuerdo con[^\.]+\.)', texto)
        if match:
            parrafos.append(match.group(1))
        
        # Patrón: "En consideración a..."
        match = re.search(r'(En consideraci[oó]n a[^\.]+\.)', texto)
        if match:
            parrafos.append(match.group(1))
        
        # Patrón con información de DMC
        match = re.search(r'((?:la\s+)?Direcci[oó]n Meteorol[oó]gica[^\.]+\.)', texto)
        if match:
            parrafos.append(match.group(1))
        
        if parrafos:
            return " ".join(parrafos)[:800]
        
        # Fallback: primeros 500 caracteres relevantes
        return texto[100:600] if len(texto) > 100 else texto[:500]
    
    def _extraer_fecha_inicio(self, texto: str) -> str:
        inicio, _ = extraer_rango_fechas(texto)
        if inicio:
            return inicio
        
        # Buscar "a partir del día X"
        match = re.search(r'a\s+partir\s+del?\s+(?:d[ií]a\s+)?(\d{1,2})\s+de\s+(\w+)', texto.lower())
        if match:
            dia = int(match.group(1))
            mes = MESES_ES.get(match.group(2), 1)
            return f"{dia:02d}/{mes:02d}/{datetime.now().year}"
        return ""
    
    def _extraer_fecha_fin(self, texto: str) -> str:
        _, fin = extraer_rango_fechas(texto)
        if fin:
            return fin
        
        # Buscar "hasta el día X"
        match = re.search(r'hasta\s+el?\s+(?:d[ií]a\s+)?(\d{1,2})\s+de\s+(\w+)', texto.lower())
        if match:
            dia = int(match.group(1))
            mes = MESES_ES.get(match.group(2), 1)
            return f"{dia:02d}/{mes:02d}/{datetime.now().year}"
        return ""
    
    def _extraer_vigencia(self, texto: str) -> str:
        t = texto.lower()
        if 'cancelada' in t or 'se cancela' in t:
            return "Cancelada"
        if 'vigente' in t:
            # Buscar "vigente desde/hasta"
            match = re.search(r'vigente\s+(desde[^\.]+|hasta[^\.]+)', t)
            if match:
                return f"Vigente {match.group(1)}"
            return "Vigente"
        return "Activa"
    
    def _extraer_aviso_dmc(self, texto: str) -> str:
        # Buscar "Aviso Meteorológico A7/2026" o similar
        match = re.search(r'[Aa]viso\s+[Mm]eteorol[oó]gico\s+([A-Z]?\d+[-/]?\d*/?(?:\d{4})?)', texto)
        if match:
            return match.group(1)
        
        # Buscar "Aviso A7/2026"
        match = re.search(r'[Aa]viso\s+([A-Z]\d+[-/]\d+)', texto)
        if match:
            return match.group(1)
        
        # Buscar "Alerta Meteorológica AA..."
        match = re.search(r'[Aa]lerta\s+[Mm]eteorol[oó]gica\s+([A-Z]+\d+[-/]?\d*)', texto)
        if match:
            return match.group(1)
        
        return ""
    
    def _extraer_temperaturas(self, texto: str) -> str:
        temps = []
        
        # Buscar rangos de temperatura
        matches = re.findall(r'(\d{1,2})\s*(?:a|y|-)\s*(\d{1,2})\s*°?\s*[Cc]', texto)
        for m in matches:
            temps.append(f"{m[0]}-{m[1]}°C")
        
        # Buscar temperaturas individuales
        matches = re.findall(r'(\d{1,2})\s*°\s*[Cc]', texto)
        for m in matches:
            t = f"{m}°C"
            if t not in temps and not any(m in x for x in temps):
                temps.append(t)
        
        # Buscar "máximas de X grados"
        match = re.search(r'm[aá]ximas?\s+(?:de\s+)?(?:hasta\s+)?(\d{1,2})', texto)
        if match:
            temps.append(f"Máx {match.group(1)}°C")
        
        return ", ".join(temps[:5]) if temps else ""
    
    def _extraer_condiciones(self, texto: str) -> str:
        condiciones = []
        
        keywords = [
            'evento de altas temperaturas', 'ola de calor', 'calor extremo',
            'calor intenso', 'dorsal en altura', 'condición de estabilidad',
            'aire caliente', 'viento norte', 'baja humedad'
        ]
        
        t = texto.lower()
        for kw in keywords:
            if kw in t:
                condiciones.append(kw.title())
        
        return ", ".join(condiciones) if condiciones else ""
    
    def _extraer_recursos(self, texto: str) -> str:
        recursos = []
        
        patrones = [
            (r'(\d+)\s*brigada', 'brigadas'),
            (r'(\d+)\s*helic[oó]ptero', 'helicópteros'),
            (r'(\d+)\s*avi[oó]n', 'aviones'),
            (r'(\d+)\s*carro[s]?\s+bomba', 'carros bomba'),
            (r'(\d+)\s*cami[oó]n', 'camiones'),
            (r'(\d+)\s*bombero', 'bomberos'),
            (r'(\d+)\s*(?:efectivo|personal)', 'efectivos'),
            (r'(\d+)\s*voluntario', 'voluntarios'),
        ]
        
        t = texto.lower()
        for patron, nombre in patrones:
            match = re.search(patron, t)
            if match:
                recursos.append(f"{match.group(1)} {nombre}")
        
        return ", ".join(recursos) if recursos else ""
    
    def _extraer_acciones(self, texto: str) -> str:
        acciones = []
        
        keywords = [
            'se movilizarán todos los recursos',
            'se alistarán escalonadamente',
            'mesa técnica',
            'coordinación con',
            'monitoreo permanente',
            'reforzamiento de vigilancia'
        ]
        
        t = texto.lower()
        for kw in keywords:
            if kw in t:
                acciones.append(kw.title())
        
        return "; ".join(acciones) if acciones else ""
    
    def _extraer_recomendaciones(self, texto: str) -> str:
        recomendaciones = []
        
        # Buscar sección de recomendaciones
        match = re.search(r'recomienda[^:]*:?\s*([^\.]+(?:\.[^\.]+){0,3})', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:500]
        
        # Keywords de recomendaciones
        keywords = [
            'hidratación', 'beber líquido', 'evitar exposición al sol',
            'población vulnerable', 'limitar exposición', 'mantenerse informado',
            'evitar actividades al aire libre', 'protegerse del calor'
        ]
        
        t = texto.lower()
        for kw in keywords:
            if kw in t:
                recomendaciones.append(kw.title())
        
        return "; ".join(recomendaciones) if recomendaciones else ""
    
    def _extraer_superficie(self, texto: str) -> str:
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:hect[aá]rea|ha)', texto, re.IGNORECASE)
        if match:
            return f"{match.group(1)} ha"
        return ""
    
    def _extraer_alertas_relacionadas(self, texto: str) -> str:
        alertas = []
        
        # Buscar menciones de otras alertas vigentes
        if 'alerta temprana preventiva nacional' in texto.lower():
            alertas.append("Alerta Temprana Preventiva Nacional")
        if 'alerta temprana preventiva regional' in texto.lower():
            alertas.append("Alerta Temprana Preventiva Regional")
        if 'amenaza de incendios forestales' in texto.lower():
            alertas.append("Amenaza Incendios Forestales")
        
        return ", ".join(alertas) if alertas else ""
    
    def _extraer_fuente(self, texto: str) -> str:
        fuentes = []
        
        if 'dirección meteorológica' in texto.lower() or 'dmc' in texto.lower():
            fuentes.append("DMC")
        if 'conaf' in texto.lower():
            fuentes.append("CONAF")
        if 'ministerio de salud' in texto.lower():
            fuentes.append("MINSAL")
        if 'delegación presidencial' in texto.lower():
            fuentes.append("Delegación Presidencial")
        
        return ", ".join(fuentes) if fuentes else "SENAPRED"


# ==============================================================================
# GENERADOR HTML MEJORADO
# ==============================================================================

class GeneradorHTML:
    """Genera dashboard HTML con información completa"""
    
    def generar(self, alertas: List[Alerta], cambios: List[CambioEstado], ultima_act: str):
        self._generar_datos_js(alertas, cambios, ultima_act)
        self._generar_html()
        log(f"Dashboard actualizado: {CONFIG['archivo_html']}")
    
    def _generar_datos_js(self, alertas: List[Alerta], cambios: List[CambioEstado], ultima_act: str):
        stats = {
            'total': len(alertas),
            'rojas': sum(1 for a in alertas if a.tipo == 'roja'),
            'amarillas': sum(1 for a in alertas if a.tipo == 'amarilla'),
            'tempranas': sum(1 for a in alertas if a.tipo == 'temprana'),
            'ultima_actualizacion': ultima_act,
        }
        
        por_region = {}
        for a in alertas:
            por_region[a.region] = por_region.get(a.region, 0) + 1
        
        por_amenaza = {}
        for a in alertas:
            por_amenaza[a.amenaza] = por_amenaza.get(a.amenaza, 0) + 1
        
        datos = {
            'alertas': [a.to_dict() for a in alertas],
            'cambios': [asdict(c) for c in cambios[-50:]],
            'stats': stats,
            'por_region': por_region,
            'por_amenaza': por_amenaza,
        }
        
        with open(CONFIG['archivo_datos_js'], 'w', encoding='utf-8') as f:
            f.write(f"const DATOS_SENAPRED = {json.dumps(datos, ensure_ascii=False, indent=2)};")
    
    def _generar_html(self):
        html = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚨 Monitor SENAPRED v5</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0f1a, #1a1a2e, #16213e);
            min-height: 100vh; color: #fff; padding: 15px;
        }
        .header {
            text-align: center; padding: 15px;
            background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 15px;
        }
        .header h1 {
            font-size: 1.8em;
            background: linear-gradient(45deg, #ff6b6b, #feca57, #48dbfb);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .update-info { color: #48dbfb; font-size: 0.85em; margin-top: 8px; }
        .auto-refresh {
            background: rgba(72,219,251,0.2); padding: 4px 12px;
            border-radius: 15px; display: inline-block; margin-top: 8px; font-size: 0.85em;
        }
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px; margin-bottom: 15px;
        }
        .stat-card {
            background: rgba(255,255,255,0.08); border-radius: 10px;
            padding: 12px; text-align: center;
        }
        .stat-card h3 { font-size: 0.85em; color: #aaa; }
        .stat-number { font-size: 2em; font-weight: bold; }
        .stat-card.roja .stat-number { color: #ff6b6b; }
        .stat-card.amarilla .stat-number { color: #feca57; }
        .stat-card.temprana .stat-number { color: #48dbfb; }
        .stat-card.total .stat-number { color: #a29bfe; }
        
        .content { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        @media (max-width: 1100px) { .content { grid-template-columns: 1fr; } }
        
        .section {
            background: rgba(255,255,255,0.05); border-radius: 12px;
            padding: 15px; margin-bottom: 15px;
        }
        .section h2 { 
            color: #48dbfb; font-size: 1.1em; margin-bottom: 12px;
            border-bottom: 2px solid rgba(72,219,251,0.3); padding-bottom: 8px;
        }
        
        /* TARJETA DE ALERTA DETALLADA */
        .alert-card {
            background: rgba(0,0,0,0.3); border-radius: 10px;
            padding: 15px; margin-bottom: 12px; border-left: 4px solid;
        }
        .alert-card.roja { border-color: #ff6b6b; }
        .alert-card.amarilla { border-color: #feca57; }
        .alert-card.temprana { border-color: #48dbfb; }
        
        .alert-header {
            display: flex; justify-content: space-between; align-items: flex-start;
            flex-wrap: wrap; gap: 8px; margin-bottom: 10px;
        }
        .alert-tipo {
            padding: 4px 12px; border-radius: 15px; font-size: 0.75em;
            font-weight: bold; text-transform: uppercase;
        }
        .alert-tipo.roja { background: #ff6b6b; }
        .alert-tipo.amarilla { background: #feca57; color: #333; }
        .alert-tipo.temprana { background: #48dbfb; color: #333; }
        
        .alert-fecha { color: #888; font-size: 0.8em; }
        
        .alert-title {
            font-size: 1em; font-weight: bold; margin-bottom: 8px;
            color: #fff;
        }
        
        .alert-info-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
            font-size: 0.85em; margin-bottom: 10px;
        }
        @media (max-width: 600px) { .alert-info-grid { grid-template-columns: 1fr; } }
        
        .info-item {
            background: rgba(255,255,255,0.05); padding: 8px;
            border-radius: 6px;
        }
        .info-label { color: #888; font-size: 0.8em; display: block; margin-bottom: 2px; }
        .info-value { color: #fff; }
        
        .alert-description {
            background: rgba(255,255,255,0.03); padding: 10px;
            border-radius: 6px; font-size: 0.85em; color: #ccc;
            margin-bottom: 10px; line-height: 1.5;
        }
        
        .alert-extras {
            display: flex; flex-wrap: wrap; gap: 8px;
            font-size: 0.8em;
        }
        .extra-tag {
            background: rgba(72,219,251,0.15); color: #48dbfb;
            padding: 3px 8px; border-radius: 10px;
        }
        
        .alert-link {
            display: inline-block; margin-top: 10px;
            color: #48dbfb; font-size: 0.85em; text-decoration: none;
        }
        .alert-link:hover { text-decoration: underline; }
        
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        @media (max-width: 600px) { .charts-row { grid-template-columns: 1fr; } }
        .chart-box { background: rgba(0,0,0,0.2); border-radius: 8px; padding: 12px; }
        .chart-box h3 { color: #48dbfb; font-size: 0.9em; margin-bottom: 8px; }
        
        .cambio-item { padding: 8px; margin-bottom: 6px; border-radius: 6px; font-size: 0.85em; }
        .cambio-item.nueva { background: rgba(46,204,113,0.2); border-left: 3px solid #2ecc71; }
        .cambio-item.actualizada { background: rgba(241,196,15,0.2); border-left: 3px solid #f1c40f; }
        .cambio-item.cancelada { background: rgba(149,165,166,0.2); border-left: 3px solid #95a5a6; }
        
        .footer { text-align: center; padding: 15px; color: #666; font-size: 0.8em; margin-top: 15px; }
        .footer a { color: #48dbfb; }
        
        .no-data { text-align: center; padding: 30px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 Monitor SENAPRED v5</h1>
        <p>Servicio Nacional de Prevención y Respuesta ante Desastres</p>
        <div class="update-info"><span id="ultima-act">Cargando...</span></div>
        <div class="auto-refresh">🔄 Auto-refresh: <span id="countdown">30</span>s</div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card total"><h3>Total</h3><div class="stat-number" id="s-total">0</div></div>
        <div class="stat-card roja"><h3>🔴 Rojas</h3><div class="stat-number" id="s-rojas">0</div></div>
        <div class="stat-card amarilla"><h3>🟡 Amarillas</h3><div class="stat-number" id="s-amarillas">0</div></div>
        <div class="stat-card temprana"><h3>🟢 Tempranas</h3><div class="stat-number" id="s-tempranas">0</div></div>
    </div>
    
    <div class="content">
        <div>
            <div class="section">
                <h2>📋 Alertas Activas - Información Completa</h2>
                <div id="lista-alertas"><div class="no-data">Cargando...</div></div>
            </div>
        </div>
        <div>
            <div class="section">
                <h2>📊 Estadísticas</h2>
                <div class="charts-row">
                    <div class="chart-box"><h3>Por Tipo</h3><canvas id="c-tipos"></canvas></div>
                    <div class="chart-box"><h3>Por Amenaza</h3><canvas id="c-amenaza"></canvas></div>
                </div>
                <div class="charts-row" style="margin-top:12px">
                    <div class="chart-box"><h3>Por Región</h3><canvas id="c-region"></canvas></div>
                </div>
            </div>
            <div class="section">
                <h2>🔔 Cambios Recientes</h2>
                <div id="lista-cambios"><div class="no-data">Sin cambios</div></div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>Fuente: <a href="https://senapred.cl/alertas/" target="_blank">senapred.cl</a> | 
        📞 CONAF 130 | Bomberos 132 | Carabineros 133 | Ambulancia 131</p>
    </div>
    
    <script src="datos_alertas.js"></script>
    <script>
        let charts = {};
        
        function cargar() {
            if (typeof DATOS_SENAPRED === 'undefined') { setTimeout(cargar, 500); return; }
            const d = DATOS_SENAPRED;
            
            // Stats
            document.getElementById('s-total').textContent = d.stats.total;
            document.getElementById('s-rojas').textContent = d.stats.rojas;
            document.getElementById('s-amarillas').textContent = d.stats.amarillas;
            document.getElementById('s-tempranas').textContent = d.stats.tempranas;
            document.getElementById('ultima-act').textContent = 'Actualizado: ' + d.stats.ultima_actualizacion;
            
            // Alertas con información completa
            let html = '';
            d.alertas.sort((a,b) => {
                const ord = {roja:0, amarilla:1, temprana:2};
                return (ord[a.tipo]||3) - (ord[b.tipo]||3);
            }).forEach(a => {
                html += `
                <div class="alert-card ${a.tipo}">
                    <div class="alert-header">
                        <span class="alert-tipo ${a.tipo}">${a.nivel_alerta || a.tipo}</span>
                        <span class="alert-fecha">📅 ${a.fecha_declaracion} ⏰ ${a.hora_declaracion}</span>
                    </div>
                    
                    <div class="alert-title">📍 ${a.region} ${a.comunas ? '- ' + a.comunas : ''}</div>
                    
                    <div class="alert-info-grid">
                        <div class="info-item">
                            <span class="info-label">⚠️ Amenaza</span>
                            <span class="info-value">${a.amenaza || a.causa}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">📌 Estado</span>
                            <span class="info-value">${a.vigencia || 'Activa'}</span>
                        </div>
                        ${a.zonas_afectadas ? `
                        <div class="info-item">
                            <span class="info-label">🗺️ Zonas Afectadas</span>
                            <span class="info-value">${a.zonas_afectadas}</span>
                        </div>` : ''}
                        ${a.temperaturas_esperadas ? `
                        <div class="info-item">
                            <span class="info-label">🌡️ Temperaturas</span>
                            <span class="info-value">${a.temperaturas_esperadas}</span>
                        </div>` : ''}
                        ${a.fecha_inicio_evento ? `
                        <div class="info-item">
                            <span class="info-label">📆 Período del Evento</span>
                            <span class="info-value">${a.fecha_inicio_evento}${a.fecha_fin_evento ? ' al ' + a.fecha_fin_evento : ''}</span>
                        </div>` : ''}
                        ${a.aviso_meteorologico ? `
                        <div class="info-item">
                            <span class="info-label">📋 Aviso DMC</span>
                            <span class="info-value">${a.aviso_meteorologico}</span>
                        </div>` : ''}
                        ${a.superficie_afectada ? `
                        <div class="info-item">
                            <span class="info-label">🔥 Superficie</span>
                            <span class="info-value">${a.superficie_afectada}</span>
                        </div>` : ''}
                        ${a.recursos_desplegados ? `
                        <div class="info-item">
                            <span class="info-label">🚒 Recursos</span>
                            <span class="info-value">${a.recursos_desplegados}</span>
                        </div>` : ''}
                    </div>
                    
                    ${a.descripcion ? `
                    <div class="alert-description">
                        ${a.descripcion.substring(0, 400)}${a.descripcion.length > 400 ? '...' : ''}
                    </div>` : ''}
                    
                    <div class="alert-extras">
                        ${a.alertas_relacionadas ? `<span class="extra-tag">🔗 ${a.alertas_relacionadas}</span>` : ''}
                        ${a.fuente_informacion ? `<span class="extra-tag">📰 ${a.fuente_informacion}</span>` : ''}
                    </div>
                    
                    <a href="${a.url}" target="_blank" class="alert-link">Ver detalle completo en SENAPRED →</a>
                </div>`;
            });
            document.getElementById('lista-alertas').innerHTML = html || '<div class="no-data">Sin alertas activas</div>';
            
            // Cambios
            html = '';
            d.cambios.slice(-10).reverse().forEach(c => {
                const em = {nueva:'🆕', actualizada:'🔄', cancelada:'❌'}[c.tipo_cambio]||'📌';
                html += `<div class="cambio-item ${c.tipo_cambio}">
                    <strong>${em} ${c.tipo_cambio.toUpperCase()}</strong> - ${c.fecha_hora}<br>
                    ${c.descripcion}
                </div>`;
            });
            document.getElementById('lista-cambios').innerHTML = html || '<div class="no-data">Sin cambios recientes</div>';
            
            // Gráficos
            const ctx = (id) => document.getElementById(id).getContext('2d');
            
            if(charts.tipos) charts.tipos.destroy();
            charts.tipos = new Chart(ctx('c-tipos'), {
                type: 'doughnut',
                data: { 
                    labels: ['Roja','Amarilla','Temprana'], 
                    datasets: [{
                        data: [d.stats.rojas, d.stats.amarillas, d.stats.tempranas],
                        backgroundColor: ['#ff6b6b','#feca57','#48dbfb']
                    }] 
                },
                options: { plugins: { legend: { labels: { color: '#fff' }}}}
            });
            
            if(charts.amenaza) charts.amenaza.destroy();
            const amenazas = Object.entries(d.por_amenaza).sort((a,b)=>b[1]-a[1]);
            charts.amenaza = new Chart(ctx('c-amenaza'), {
                type: 'pie',
                data: { 
                    labels: amenazas.map(x=>x[0]), 
                    datasets: [{
                        data: amenazas.map(x=>x[1]),
                        backgroundColor: ['#ff6b6b','#feca57','#48dbfb','#a29bfe','#fd79a8','#00b894']
                    }] 
                },
                options: { plugins: { legend: { labels: { color: '#fff', font:{size:10} }}}}
            });
            
            if(charts.region) charts.region.destroy();
            const regs = Object.entries(d.por_region).sort((a,b)=>b[1]-a[1]).slice(0,8);
            charts.region = new Chart(ctx('c-region'), {
                type: 'bar',
                data: { 
                    labels: regs.map(r=>r[0].substring(0,12)), 
                    datasets: [{data: regs.map(r=>r[1]), backgroundColor: '#48dbfb'}] 
                },
                options: { 
                    indexAxis: 'y',
                    plugins:{legend:{display:false}}, 
                    scales: { 
                        x:{ticks:{color:'#fff'},grid:{color:'rgba(255,255,255,0.1)'}},
                        y:{ticks:{color:'#fff'},grid:{display:false}} 
                    }
                }
            });
        }
        
        let count = 30;
        setInterval(() => {
            count--;
            document.getElementById('countdown').textContent = count;
            if(count <= 0) { count = 30; location.reload(); }
        }, 1000);
        
        cargar();
    </script>
</body>
</html>'''
        
        with open(CONFIG['archivo_html'], 'w', encoding='utf-8') as f:
            f.write(html)


# ==============================================================================
# MONITOR
# ==============================================================================

class MonitorSenapred:
    """Monitor con detección de cambios"""
    
    def __init__(self, intervalo: int = 300, con_sonido: bool = False, dias_max: int = 14):
        self.intervalo = intervalo
        self.con_sonido = con_sonido
        self.dias_max = dias_max
        self.alertas: Dict[str, Alerta] = {}
        self.cambios: List[CambioEstado] = []
        self.scraper = SenapredScraper(headless=True, dias_max=dias_max)
        self.html = GeneradorHTML()
        self._cargar_estado()
    
    def _cargar_estado(self):
        try:
            if os.path.exists(CONFIG['archivo_estado']):
                with open(CONFIG['archivo_estado'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for a in data.get('alertas', []):
                        self.alertas[a['id']] = Alerta(**a)
                    for c in data.get('cambios', []):
                        self.cambios.append(CambioEstado(**c))
                log(f"Estado cargado: {len(self.alertas)} alertas")
        except Exception as e:
            log(f"Sin estado previo: {e}", "WARN")
    
    def _guardar_estado(self):
        try:
            with open(CONFIG['archivo_estado'], 'w', encoding='utf-8') as f:
                json.dump({
                    'alertas': [a.to_dict() for a in self.alertas.values()],
                    'cambios': [asdict(c) for c in self.cambios[-100:]]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log(f"Error guardando: {e}", "WARN")
    
    def _detectar_cambios(self, nuevas_alertas: List[Alerta]):
        nuevas, actualizadas, canceladas = [], [], []
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        ids_actuales = {a.id for a in nuevas_alertas}
        
        for alerta in nuevas_alertas:
            if alerta.id not in self.alertas:
                nuevas.append(alerta)
                self.alertas[alerta.id] = alerta
                self.cambios.append(CambioEstado(
                    alerta.id, "nueva", ahora,
                    f"{alerta.nivel_alerta}: {alerta.region} - {alerta.amenaza}"
                ))
            elif alerta.contenido_hash != self.alertas[alerta.id].contenido_hash:
                actualizadas.append(alerta)
                self.alertas[alerta.id] = alerta
                self.cambios.append(CambioEstado(
                    alerta.id, "actualizada", ahora,
                    f"{alerta.nivel_alerta}: {alerta.region}"
                ))
        
        for id_alerta in list(self.alertas.keys()):
            if id_alerta not in ids_actuales:
                alerta = self.alertas[id_alerta]
                if alerta.estado_monitor != "cancelada":
                    alerta.estado_monitor = "cancelada"
                    canceladas.append(alerta)
                    self.cambios.append(CambioEstado(
                        id_alerta, "cancelada", ahora,
                        f"{alerta.nivel_alerta}: {alerta.region}"
                    ))
        
        return nuevas, actualizadas, canceladas
    
    def ejecutar(self):
        os.system('cls' if sys.platform == 'win32' else 'clear')
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚨 MONITOR SENAPRED v5.0 🚨                               ║
║                    Extracción Completa de Información                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
  📅 {datetime.now().strftime('%d/%m/%Y %H:%M')} | ⏱️ Cada {self.intervalo//60} min | 📆 Últimos {self.dias_max} días
  🔊 Sonido: {'ON' if self.con_sonido else 'OFF'} | 📊 Dashboard: {CONFIG['archivo_html']}
        """)
        
        activas = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
        self.html.generar(activas, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        while True:
            try:
                print(f"\n🔄 Consultando SENAPRED... [{datetime.now().strftime('%H:%M:%S')}]")
                
                alertas = self.scraper.obtener_alertas()
                nuevas, actualizadas, canceladas = self._detectar_cambios(alertas)
                
                if nuevas or actualizadas or canceladas:
                    if nuevas:
                        print(f"\n🆕 {len(nuevas)} NUEVA(S):")
                        for a in nuevas:
                            print(f"   🔴 {a.region} | {a.amenaza}")
                            print(f"      🌡️ {a.temperaturas_esperadas}" if a.temperaturas_esperadas else "")
                        if self.con_sonido: sonido("nueva")
                        for a in nuevas:
                            notificar(f"🆕 {a.nivel_alerta}", 
                                     f"{a.region}\n{a.amenaza}", a.tipo=='roja')
                    
                    if actualizadas:
                        print(f"\n🔄 {len(actualizadas)} ACTUALIZADA(S)")
                        if self.con_sonido: sonido("actualizada")
                    
                    if canceladas:
                        print(f"\n❌ {len(canceladas)} CANCELADA(S)")
                        if self.con_sonido: sonido("cancelada")
                    
                    self._guardar_estado()
                    activas = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
                    self.html.generar(activas, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
                    print(f"\n✅ Dashboard actualizado ({len(activas)} alertas)")
                else:
                    activas = len([a for a in self.alertas.values() if a.estado_monitor != 'cancelada'])
                    print(f"✓ Sin cambios ({activas} alertas activas)")
                
                print(f"\n⏳ Próxima consulta en {self.intervalo//60} min...")
                time.sleep(self.intervalo)
                
            except KeyboardInterrupt:
                print("\n\n👋 Monitor detenido")
                self._guardar_estado()
                break
            except Exception as e:
                log(f"Error: {e}", "ERROR")
                time.sleep(60)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Monitor SENAPRED v5 - Información Completa')
    parser.add_argument('--monitor', '-m', action='store_true')
    parser.add_argument('--intervalo', '-i', type=int, default=300)
    parser.add_argument('--sound', '-s', action='store_true')
    parser.add_argument('--dias', '-d', type=int, default=14)
    args = parser.parse_args()
    
    if not SELENIUM_OK or not BS4_OK:
        print("❌ Instala: pip install selenium webdriver-manager beautifulsoup4 plyer")
        return
    
    CONFIG['sonido_alerta'] = args.sound
    
    if args.monitor:
        MonitorSenapred(args.intervalo, args.sound, args.dias).ejecutar()
    else:
        print(f"\n🔍 Consultando SENAPRED (últimos {args.dias} días)...\n")
        scraper = SenapredScraper(dias_max=args.dias)
        alertas = scraper.obtener_alertas()
        
        if alertas:
            print(f"\n{'='*70}")
            print(f"🚨 {len(alertas)} ALERTAS ENCONTRADAS")
            print(f"{'='*70}\n")
            
            for a in sorted(alertas, key=lambda x: (0 if x.tipo=='roja' else 1 if x.tipo=='amarilla' else 2)):
                em = {'roja':'🔴','amarilla':'🟡','temprana':'🟢'}.get(a.tipo,'⚪')
                print(f"{em} {a.nivel_alerta}")
                print(f"   📍 Región: {a.region}")
                if a.comunas:
                    print(f"   🏘️  Comunas: {a.comunas}")
                if a.zonas_afectadas:
                    print(f"   🗺️  Zonas: {a.zonas_afectadas}")
                print(f"   ⚠️  Amenaza: {a.amenaza}")
                if a.temperaturas_esperadas:
                    print(f"   🌡️  Temperaturas: {a.temperaturas_esperadas}")
                if a.fecha_inicio_evento:
                    print(f"   📆 Evento: {a.fecha_inicio_evento} - {a.fecha_fin_evento}")
                if a.aviso_meteorologico:
                    print(f"   📋 Aviso DMC: {a.aviso_meteorologico}")
                print(f"   📅 Declarada: {a.fecha_declaracion} {a.hora_declaracion}")
                print(f"   🔗 {a.url}")
                print()
            
            GeneradorHTML().generar(alertas, [], datetime.now().strftime("%d/%m/%Y %H:%M"))
            print(f"{'='*70}")
            print(f"✅ Dashboard generado: {CONFIG['archivo_html']}")
        else:
            print("📋 No se encontraron alertas")


if __name__ == "__main__":
    main()
