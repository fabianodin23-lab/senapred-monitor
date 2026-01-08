#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONITOR SENAPRED v5.4
- ID único basado en hash de URL (evita colisiones)
- Mejor captura de todas las alertas
"""

import argparse, json, time, os, sys, re, hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

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

CONFIG = {
    'url_alertas': 'https://senapred.cl/alertas/',
    'url_base': 'https://senapred.cl',
    'espera_react': 6,
    'espera_detalle': 4,
    'archivo_estado': 'estado_alertas.json',
    'archivo_html': 'dashboard_senapred.html',
    'archivo_datos_js': 'datos_alertas.js',
    'sonido_alerta': True,
}

REGIONES = [
    'Arica y Parinacota', 'Tarapacá', 'Antofagasta', 'Atacama', 'Coquimbo',
    'Valparaíso', 'Metropolitana', "O'Higgins", 'Maule', 'Ñuble', 'Biobío',
    'La Araucanía', 'Los Ríos', 'Los Lagos', 'Aysén', 'Magallanes'
]


def generar_id(url: str) -> str:
    """Genera ID único basado en hash MD5 de la URL completa"""
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
    
    def to_dict(self):
        return asdict(self)


@dataclass 
class Cambio:
    alerta_id: str
    tipo_cambio: str
    fecha_hora: str
    descripcion: str


def log(msg: str, nivel: str = "INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{nivel}] {msg}")


def notificar(titulo: str, mensaje: str, urgente: bool = False):
    if NOTIF_OK:
        try:
            notification.notify(title=titulo, message=mensaje[:200], app_name="SENAPRED", timeout=20 if urgente else 10)
        except: pass


def sonido(tipo: str = "nueva"):
    if not CONFIG['sonido_alerta']: return
    try:
        if sys.platform == 'win32':
            import winsound
            beeps = {'nueva': [(1000,400)]*3, 'actualizada': [(800,300)], 'cancelada': [(500,600)]}
            for freq, dur in beeps.get(tipo, []):
                winsound.Beep(freq, dur)
                time.sleep(0.1)
    except: print('\a')


class Scraper:
    def __init__(self, dias_max: int = 14):
        self.dias_max = dias_max
        self.driver = None
    
    def _crear_driver(self):
        opts = Options()
        for arg in ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--window-size=1920,1080', '--log-level=3']:
            opts.add_argument(arg)
        opts.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    def obtener_alertas(self) -> List[Alerta]:
        try:
            log("Iniciando navegador...")
            self.driver = self._crear_driver()
            urls = self._obtener_urls()
            log(f"URLs encontradas: {len(urls)}")
            
            alertas = []
            ids_procesados = set()
            
            for i, url in enumerate(urls):
                # Generar ID único basado en URL
                alerta_id = generar_id(url)
                
                # Evitar duplicados
                if alerta_id in ids_procesados:
                    continue
                ids_procesados.add(alerta_id)
                
                # Filtrar por antigüedad
                match = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
                if match:
                    try:
                        fecha_alerta = datetime(int(match[1]), int(match[2]), int(match[3]))
                        dias = (datetime.now() - fecha_alerta).days
                        if dias > self.dias_max:
                            continue
                    except:
                        pass
                
                log(f"  [{i+1}/{len(urls)}] {url[-55:]}")
                alerta = self._extraer_alerta(url, alerta_id)
                if alerta:
                    alertas.append(alerta)
                time.sleep(0.5)
            
            log(f"Total: {len(alertas)} alertas capturadas")
            return alertas
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            return []
        finally:
            if self.driver:
                try: self.driver.quit()
                except: pass
    
    def _obtener_urls(self) -> List[str]:
        urls = []
        try:
            self.driver.get(CONFIG['url_alertas'])
            time.sleep(CONFIG['espera_react'])
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            for link in BeautifulSoup(self.driver.page_source, 'html.parser').find_all('a', href=True):
                href = link['href']
                if '/alerta/' in href and 'alertas' not in href:
                    url = (CONFIG['url_base'] + href) if href.startswith('/') else href
                    if url.startswith('http') and url not in urls:
                        urls.append(url)
        except Exception as e:
            log(f"Error URLs: {e}", "ERROR")
        return urls
    
    def _extraer_alerta(self, url: str, alerta_id: str) -> Optional[Alerta]:
        try:
            self.driver.get(url)
            time.sleep(CONFIG['espera_detalle'])
            
            texto = BeautifulSoup(self.driver.page_source, 'html.parser').get_text(' ', strip=True)
            t = texto.lower()
            
            # Detectar tipo
            tipo = None
            if 'alerta roja' in t:
                tipo = 'roja'
            elif 'alerta amarilla' in t:
                tipo = 'amarilla'
            elif 'temprana' in t or 'preventiva' in t:
                tipo = 'temprana'
            
            if not tipo:
                log(f"    ⚠ Sin tipo detectado", "WARN")
                return None
            
            # Extraer fecha/hora de URL
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})', url)
            fecha = f"{match[3]}/{match[2]}/{match[1]}" if match else datetime.now().strftime("%d/%m/%Y")
            hora = f"{match[4]}:{match[5]}" if match else "--:--"
            
            # Región
            region = "No especificada"
            for r in REGIONES:
                if r.lower() in t:
                    region = r
                    break
            
            # Comuna
            m = re.search(r'comuna[s]?\s+de\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+por|\s+debido|,\s+por|\.)', texto, re.I)
            comuna = m[1].strip().title()[:50] if m else "No especificada"
            
            # Causa - ampliado
            causas = {
                'incendio': 'Incendio Forestal', 
                'calor': 'Calor Extremo', 
                'temperatura': 'Altas Temperaturas', 
                'sismo': 'Sismo', 
                'tsunami': 'Tsunami', 
                'temporal': 'Temporal',
                'tormenta': 'Tormenta Eléctrica',
                'eléctrica': 'Tormenta Eléctrica',
                'electrica': 'Tormenta Eléctrica',
                'volcán': 'Actividad Volcánica',
                'volcan': 'Actividad Volcánica',
                'volcánic': 'Actividad Volcánica',
                'aluvión': 'Aluvión',
                'aluvion': 'Aluvión',
                'inundación': 'Inundación',
                'inundacion': 'Inundación',
                'marejada': 'Marejada',
                'evento masivo': 'Evento Masivo',
                'material peligroso': 'Material Peligroso',
            }
            causa = "Emergencia"
            for k, v in causas.items():
                if k in t:
                    causa = v
                    break
            
            # Recursos
            recursos = []
            for p, n in [(r'(\d+)\s*brigada', 'brigadas'), (r'(\d+)\s*helic', 'helicópteros'), (r'(\d+)\s*avion', 'aviones')]:
                if m := re.search(p, t): recursos.append(f"{m[1]} {n}")
            
            # Superficie
            m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:hect|ha)', t)
            superficie = f"{m[1]} ha" if m else ""
            
            return Alerta(
                id=alerta_id,
                url=url, 
                tipo=tipo, 
                region=region, 
                comuna=comuna, 
                causa=causa,
                fecha=fecha, 
                hora=hora, 
                recursos=", ".join(recursos), 
                superficie=superficie,
                contenido_hash=hashlib.md5(texto[:500].encode()).hexdigest()[:16]
            )
        except Exception as e:
            log(f"    ✗ Error: {e}", "WARN")
            return None


class Dashboard:
    def generar(self, alertas: List[Alerta], cambios: List[Cambio], ultima_act: str):
        stats = {'total': len(alertas), 'rojas': sum(1 for a in alertas if a.tipo == 'roja'),
                 'amarillas': sum(1 for a in alertas if a.tipo == 'amarilla'),
                 'tempranas': sum(1 for a in alertas if a.tipo == 'temprana'), 'ultima_actualizacion': ultima_act}
        
        estado_regiones = {}
        for region in REGIONES:
            ar = [a for a in alertas if a.region == region]
            if not ar:
                estado_regiones[region] = {'estado': 'sin_alerta', 'rojas': 0, 'amarillas': 0, 'tempranas': 0}
            else:
                r, am, t = sum(1 for a in ar if a.tipo == 'roja'), sum(1 for a in ar if a.tipo == 'amarilla'), sum(1 for a in ar if a.tipo == 'temprana')
                estado_regiones[region] = {'estado': 'roja' if r else ('amarilla' if am else 'temprana'), 'rojas': r, 'amarillas': am, 'tempranas': t}
        
        por_causa = {}
        for a in alertas: por_causa[a.causa] = por_causa.get(a.causa, 0) + 1
        
        with open(CONFIG['archivo_datos_js'], 'w', encoding='utf-8') as f:
            f.write(f"const D={json.dumps({'alertas': [a.to_dict() for a in alertas], 'cambios': [asdict(c) for c in cambios[-50:]], 'stats': stats, 'estado_regiones': estado_regiones, 'por_causa': por_causa, 'regiones': REGIONES}, ensure_ascii=False)};")
        
        html = '''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>🚨 SENAPRED</title><script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);min-height:100vh;color:#fff;padding:15px}
.hdr{text-align:center;padding:15px;background:rgba(255,255,255,.1);border-radius:12px;margin-bottom:15px}
.hdr h1{font-size:1.8em;background:linear-gradient(45deg,#ff6b6b,#feca57,#48dbfb);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.upd{color:#48dbfb;font-size:.85em;margin-top:8px}.ar{background:rgba(72,219,251,.2);padding:4px 12px;border-radius:15px;display:inline-block;margin-top:8px;font-size:.85em}
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:15px}
.sc{background:rgba(255,255,255,.1);border-radius:12px;padding:15px;text-align:center}
.sc.r{border-left:4px solid #ff6b6b}.sc.a{border-left:4px solid #feca57}.sc.t{border-left:4px solid #48dbfb}.sc.tot{border-left:4px solid #a29bfe}
.sn{font-size:2em;font-weight:700}.sc.r .sn{color:#ff6b6b}.sc.a .sn{color:#feca57}.sc.t .sn{color:#48dbfb}.sc.tot .sn{color:#a29bfe}
.mg{display:grid;grid-template-columns:1fr 1fr;gap:15px}@media(max-width:1100px){.mg{grid-template-columns:1fr}}
.sec{background:rgba(255,255,255,.1);border-radius:12px;padding:15px;margin-bottom:15px}
.sec h2{color:#48dbfb;font-size:1.1em;margin-bottom:12px;border-bottom:2px solid rgba(72,219,251,.3);padding-bottom:8px}
.rg{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.ri{padding:10px 12px;border-radius:8px;font-size:.85em;display:flex;justify-content:space-between;align-items:center}
.ri.sin{background:rgba(46,204,113,.15);border-left:3px solid #2ecc71}
.ri.roja{background:rgba(255,107,107,.2);border-left:3px solid #ff6b6b}
.ri.amarilla{background:rgba(254,202,87,.2);border-left:3px solid #feca57}
.ri.temprana{background:rgba(72,219,251,.2);border-left:3px solid #48dbfb}
.rs{font-size:.75em;padding:2px 8px;border-radius:10px;font-weight:700}
.ri.sin .rs{background:#2ecc71;color:#000}.ri.roja .rs{background:#ff6b6b}.ri.amarilla .rs{background:#feca57;color:#000}.ri.temprana .rs{background:#48dbfb;color:#000}
.ley{display:flex;gap:15px;flex-wrap:wrap;padding:10px;background:rgba(0,0,0,.2);border-radius:8px;margin-bottom:12px;font-size:.8em}
.li{display:flex;align-items:center;gap:5px}.lc{width:12px;height:12px;border-radius:3px}
.lc.r{background:#ff6b6b}.lc.a{background:#feca57}.lc.t{background:#48dbfb}.lc.s{background:#2ecc71}
.al{max-height:500px;overflow-y:auto}
.ai{background:rgba(0,0,0,.25);border-radius:8px;padding:12px;margin-bottom:10px;border-left:4px solid}
.ai.roja{border-color:#ff6b6b}.ai.amarilla{border-color:#feca57}.ai.temprana{border-color:#48dbfb}
.ah{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px}
.at{padding:3px 10px;border-radius:12px;font-size:.75em;font-weight:700;text-transform:uppercase}
.at.roja{background:#ff6b6b}.at.amarilla{background:#feca57;color:#333}.at.temprana{background:#48dbfb;color:#333}
.af{color:#95a5a6;font-size:.8em}.au{font-weight:700;margin-bottom:4px}.ac{color:#bdc3c7;font-size:.85em;margin-bottom:4px}
.ad{font-size:.8em;color:#95a5a6}.ad a{color:#48dbfb;text-decoration:none}
.cg{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:600px){.cg{grid-template-columns:1fr}}
.cb{background:rgba(0,0,0,.2);border-radius:8px;padding:12px}.cb h3{color:#48dbfb;font-size:.9em;margin-bottom:8px}
.ci{padding:8px;margin-bottom:6px;border-radius:6px;font-size:.85em}
.ci.nueva{background:rgba(46,204,113,.2);border-left:3px solid #2ecc71}
.ci.actualizada{background:rgba(241,196,15,.2);border-left:3px solid #f1c40f}
.ci.cancelada{background:rgba(149,165,166,.2);border-left:3px solid #95a5a6}
.ft{text-align:center;padding:15px;color:#95a5a6;font-size:.8em}.ft a{color:#48dbfb}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:rgba(0,0,0,.2)}::-webkit-scrollbar-thumb{background:#48dbfb;border-radius:3px}
</style></head><body>
<div class="hdr"><h1>🚨 Monitor SENAPRED v5.4</h1><p>Servicio Nacional de Prevención y Respuesta ante Desastres</p>
<div class="upd"><span id="ua">Cargando...</span></div><div class="ar">🔄 <span id="cd">30</span>s</div></div>
<div class="sg">
<div class="sc tot"><h3>Total</h3><div class="sn" id="st">0</div></div>
<div class="sc r"><h3>🔴 Rojas</h3><div class="sn" id="sr">0</div></div>
<div class="sc a"><h3>🟡 Amarillas</h3><div class="sn" id="sa">0</div></div>
<div class="sc t"><h3>🟢 Tempranas</h3><div class="sn" id="se">0</div></div>
</div>
<div class="mg"><div>
<div class="sec"><h2>🗺️ Estado por Región</h2>
<div class="ley"><div class="li"><div class="lc r"></div>Roja</div><div class="li"><div class="lc a"></div>Amarilla</div><div class="li"><div class="lc t"></div>Temprana</div><div class="li"><div class="lc s"></div>Sin Alertas</div></div>
<div class="rg" id="mr"></div></div>
<div class="sec"><h2>📊 Estadísticas</h2><div class="cg">
<div class="cb"><h3>Por Tipo</h3><canvas id="ct"></canvas></div>
<div class="cb"><h3>Por Amenaza</h3><canvas id="cc"></canvas></div>
</div></div></div>
<div><div class="sec"><h2>📋 Alertas Activas</h2><div class="al" id="la">Cargando...</div></div>
<div class="sec"><h2>🔔 Cambios Recientes</h2><div id="lc">Sin cambios</div></div></div></div>
<div class="ft"><p>Fuente: <a href="https://senapred.cl/alertas/" target="_blank">senapred.cl</a> | 📞 CONAF 130 | Bomberos 132 | Carabineros 133</p></div>
<script src="datos_alertas.js"></script>
<script>
let ch={};function ld(){if(typeof D==='undefined'){setTimeout(ld,500);return}
document.getElementById('st').textContent=D.stats.total;
document.getElementById('sr').textContent=D.stats.rojas;
document.getElementById('sa').textContent=D.stats.amarillas;
document.getElementById('se').textContent=D.stats.tempranas;
document.getElementById('ua').textContent='Actualizado: '+D.stats.ultima_actualizacion;
let h='';D.regiones.forEach(r=>{let i=D.estado_regiones[r]||{estado:'sin_alerta'};
let e=i.estado==='sin_alerta'?'sin':i.estado;
let s=i.estado==='sin_alerta'?'✓ OK':[i.rojas&&i.rojas+'R',i.amarillas&&i.amarillas+'A',i.tempranas&&i.tempranas+'T'].filter(Boolean).join(' ');
h+='<div class="ri '+e+'"><span>'+r+'</span><span class="rs">'+s+'</span></div>';});
document.getElementById('mr').innerHTML=h;
h='';if(!D.alertas.length){h='<div style="text-align:center;padding:20px;color:#2ecc71">✅ Sin alertas</div>';}
else{D.alertas.sort((a,b)=>({roja:0,amarilla:1,temprana:2}[a.tipo]||3)-({roja:0,amarilla:1,temprana:2}[b.tipo]||3));
D.alertas.forEach(a=>{h+='<div class="ai '+a.tipo+'"><div class="ah"><span class="at '+a.tipo+'">'+a.tipo+'</span><span class="af">📅 '+a.fecha+' ⏰ '+a.hora+'</span></div><div class="au">📍 '+a.region+' - '+a.comuna+'</div><div class="ac">⚠️ '+a.causa+(a.superficie?' | 🔥 '+a.superficie:'')+'</div><div class="ad">'+(a.recursos?'🚒 '+a.recursos+'<br>':'')+'<a href="'+a.url+'" target="_blank">Ver detalle →</a></div></div>';});}
document.getElementById('la').innerHTML=h;
h='';if(!D.cambios.length){h='<div style="text-align:center;padding:10px;color:#95a5a6">Sin cambios</div>';}
else{D.cambios.slice(-10).reverse().forEach(c=>{let e={nueva:'🆕',actualizada:'🔄',cancelada:'❌'}[c.tipo_cambio]||'📌';
h+='<div class="ci '+c.tipo_cambio+'"><strong>'+e+' '+c.tipo_cambio.toUpperCase()+'</strong> - '+c.fecha_hora+'<br>'+c.descripcion+'</div>';});}
document.getElementById('lc').innerHTML=h;
let x=id=>document.getElementById(id).getContext('2d');
if(ch.t)ch.t.destroy();ch.t=new Chart(x('ct'),{type:'doughnut',data:{labels:['Roja','Amarilla','Temprana'],datasets:[{data:[D.stats.rojas,D.stats.amarillas,D.stats.tempranas],backgroundColor:['#ff6b6b','#feca57','#48dbfb']}]},options:{plugins:{legend:{labels:{color:'#fff'}}}}});
if(ch.c)ch.c.destroy();let cs=Object.entries(D.por_causa).sort((a,b)=>b[1]-a[1]);
ch.c=new Chart(x('cc'),{type:'bar',data:{labels:cs.map(c=>c[0].substring(0,12)),datasets:[{data:cs.map(c=>c[1]),backgroundColor:['#ff6b6b','#feca57','#48dbfb','#a29bfe','#fd79a8']}]},options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{y:{ticks:{color:'#fff'},grid:{display:false}},x:{ticks:{color:'#fff'},grid:{color:'rgba(255,255,255,0.1)'}}}}});}
let c=30;setInterval(()=>{c--;document.getElementById('cd').textContent=c;if(c<=0){c=30;location.reload();}},1000);ld();
</script></body></html>'''
        with open(CONFIG['archivo_html'], 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"📊 Dashboard actualizado: {CONFIG['archivo_html']}")


class Monitor:
    def __init__(self, intervalo: int = 300, con_sonido: bool = False, dias_max: int = 14):
        self.intervalo = intervalo
        self.con_sonido = con_sonido
        self.scraper = Scraper(dias_max)
        self.dashboard = Dashboard()
        self.alertas: Dict[str, Alerta] = {}
        self.cambios: List[Cambio] = []
        self.dias_max = dias_max
        self._cargar()
    
    def _cargar(self):
        try:
            if os.path.exists(CONFIG['archivo_estado']):
                with open(CONFIG['archivo_estado'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for a in data.get('alertas', []): self.alertas[a['id']] = Alerta(**a)
                    for c in data.get('cambios', []): self.cambios.append(Cambio(**c))
                log(f"Cargado: {len(self.alertas)} alertas previas")
        except: pass
    
    def _guardar(self):
        try:
            with open(CONFIG['archivo_estado'], 'w', encoding='utf-8') as f:
                json.dump({'alertas': [a.to_dict() for a in self.alertas.values()], 'cambios': [asdict(c) for c in self.cambios[-100:]]}, f, ensure_ascii=False)
        except: pass
    
    def _detectar_cambios(self, nuevas):
        n, u, c = [], [], []
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        ids = {a.id for a in nuevas}
        
        for a in nuevas:
            if a.id not in self.alertas:
                n.append(a); self.alertas[a.id] = a
                self.cambios.append(Cambio(a.id, "nueva", ahora, f"{a.tipo.upper()}: {a.region} - {a.causa}"))
            elif a.contenido_hash != self.alertas[a.id].contenido_hash:
                u.append(a); self.alertas[a.id] = a
                self.cambios.append(Cambio(a.id, "actualizada", ahora, f"{a.tipo.upper()}: {a.region}"))
        
        for id in list(self.alertas.keys()):
            if id not in ids and self.alertas[id].estado_monitor != "cancelada":
                self.alertas[id].estado_monitor = "cancelada"; c.append(self.alertas[id])
                self.cambios.append(Cambio(id, "cancelada", ahora, f"{self.alertas[id].tipo.upper()}: {self.alertas[id].region}"))
        return n, u, c
    
    def ejecutar(self):
        os.system('cls' if sys.platform == 'win32' else 'clear')
        print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚨 MONITOR SENAPRED v5.4 🚨                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
  ⏱️ Cada {self.intervalo//60} min | 📆 Últimos {self.dias_max} días | 🔊 {'ON' if self.con_sonido else 'OFF'}
  💡 Abre {CONFIG['archivo_html']} en tu navegador
        """)
        
        activas = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
        self.dashboard.generar(activas, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        while True:
            try:
                print(f"\n🔄 Consultando... [{datetime.now().strftime('%H:%M:%S')}]")
                alertas = self.scraper.obtener_alertas()
                n, u, c = self._detectar_cambios(alertas)
                
                if n:
                    print(f"🆕 {len(n)} NUEVA(S)")
                    for a in n: print(f"   🔴 {a.region} - {a.causa}")
                    if self.con_sonido: sonido("nueva")
                    for a in n: notificar(f"🆕 {a.tipo.upper()}", f"{a.region}\n{a.causa}", a.tipo=='roja')
                if u: 
                    print(f"🔄 {len(u)} ACTUALIZADA(S)")
                    if self.con_sonido: sonido("actualizada")
                if c: 
                    print(f"❌ {len(c)} CANCELADA(S)")
                    if self.con_sonido: sonido("cancelada")
                
                if not n and not u and not c:
                    print(f"✓ Sin cambios")
                
                self._guardar()
                activas = [a for a in self.alertas.values() if a.estado_monitor != 'cancelada']
                self.dashboard.generar(activas, self.cambios, datetime.now().strftime("%d/%m/%Y %H:%M"))
                print(f"📋 Total: {len(activas)} alertas activas")
                
                print(f"⏳ Próxima en {self.intervalo//60} min...")
                time.sleep(self.intervalo)
            except KeyboardInterrupt:
                print("\n👋 Detenido"); self._guardar(); break
            except Exception as e:
                log(f"Error: {e}", "ERROR"); time.sleep(60)


def main():
    p = argparse.ArgumentParser(description='Monitor SENAPRED v5.4')
    p.add_argument('--monitor', '-m', action='store_true')
    p.add_argument('--intervalo', '-i', type=int, default=300)
    p.add_argument('--sound', '-s', action='store_true')
    p.add_argument('--dias', '-d', type=int, default=14)
    args = p.parse_args()
    
    if not SELENIUM_OK or not BS4_OK:
        print("❌ pip install selenium webdriver-manager beautifulsoup4 plyer"); return
    
    CONFIG['sonido_alerta'] = args.sound
    
    if args.monitor:
        Monitor(args.intervalo, args.sound, args.dias).ejecutar()
    else:
        print(f"\n🔍 Consultando SENAPRED (últimos {args.dias} días)...\n")
        alertas = Scraper(args.dias).obtener_alertas()
        
        print(f"\n{'='*60}")
        print(f"🚨 {len(alertas)} ALERTAS ENCONTRADAS")
        print(f"{'='*60}\n")
        
        if alertas:
            for a in sorted(alertas, key=lambda x: (0 if x.tipo=='roja' else 1 if x.tipo=='amarilla' else 2)):
                print(f"{'🔴' if a.tipo=='roja' else '🟡' if a.tipo=='amarilla' else '🟢'} [{a.tipo.upper()}] {a.region}")
                print(f"   📅 {a.fecha} | ⚠️ {a.causa}")
                if a.superficie: print(f"   🔥 {a.superficie}")
                print()
        
        Dashboard().generar(alertas, [], datetime.now().strftime("%d/%m/%Y %H:%M"))
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
