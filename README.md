# ⚡ Monitor SENAPRED Chile v6.1

<p align="center">
  <strong>Sistema de monitoreo en tiempo real de alertas de emergencia de SENAPRED Chile</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/version-6.1-brightgreen.svg" alt="Version 6.1">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/SENAPRED-Chile-red.svg" alt="SENAPRED Chile">
</p>

---

## 📋 Descripción

**Monitor SENAPRED** es una herramienta que permite monitorear en tiempo real las alertas de emergencia emitidas por el [Servicio Nacional de Prevención y Respuesta ante Desastres (SENAPRED)](https://senapred.cl) de Chile.

### ¿Para quién es?
- 🌙 **Turnos nocturnos** de monitoreo de emergencias (NOC/SOC)
- 🏢 **Centros de operaciones** de emergencia
- 👨‍🚒 **Personal de respuesta** (bomberos, rescatistas)
- 📊 **Análisis de datos** de emergencias
- 🏠 **Ciudadanos** que quieran estar informados

---

## ✨ Características

| Característica | Descripción |
|----------------|-------------|
| 📡 **Monitoreo en tiempo real** | Consulta automática cada X minutos |
| 📊 **Dashboard Grafana-style** | Interfaz dark theme profesional |
| 🔔 **Notificaciones** | Alertas sonoras y de escritorio |
| 🔇 **Modo silencioso** | Sin sonido en horarios nocturnos |
| 🗺️ **16 regiones** | Estado visual de todo Chile |
| 📋 **Resumen diario** | Genera reporte HTML automático |
| ⚙️ **Configurable** | Archivo `config.json` sin tocar código |
| 📝 **Log persistente** | Historial completo en CSV |
| 🆕 **Detección de cambios** | Nueva, actualizada, cancelada |
| 🔍 **Filtros** | Por región y tipo de alerta |

### Información que extrae de cada alerta:
- 📍 Región y comunas afectadas
- ⚠️ Tipo de amenaza (calor, incendio, tsunami, etc.)
- 📆 Fecha y hora de la alerta
- 🔥 Superficie afectada (en incendios)
- 🚒 Recursos desplegados
- 🔗 Link al detalle oficial

---

## 🔧 Requisitos

- **Python 3.8+** → [Descargar](https://www.python.org/downloads/)
- **Google Chrome** → [Descargar](https://www.google.com/chrome/)

---

## 📦 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/fabianodin23-lab/senapred-monitor.git
cd senapred-monitor
```

### 2. Instalar dependencias

**Windows (CMD o PowerShell):**
```bash
pip install selenium webdriver-manager beautifulsoup4 plyer
```

**Linux/macOS:**
```bash
pip3 install selenium webdriver-manager beautifulsoup4 plyer
```

### 3. Verificar instalación

```bash
python monitor_senapred.py
```

---

## 🚀 Uso

### Consulta simple (una vez)

```bash
python monitor_senapred.py
```

### Monitoreo continuo con alertas sonoras

```bash
python monitor_senapred.py --monitor --sound
```

### Solo últimos 7 días, cada 2 minutos

```bash
python monitor_senapred.py --monitor --sound --dias 7 --intervalo 120
```

### Ver configuración actual

```bash
python monitor_senapred.py --config
```

### Generar resumen diario manual

```bash
python monitor_senapred.py --resumen
```

---

## ⚙️ Opciones disponibles

| Opción | Corto | Descripción | Default |
|--------|-------|-------------|---------|
| `--monitor` | `-m` | Monitoreo continuo | No |
| `--sound` | `-s` | Alertas sonoras | No |
| `--dias N` | `-d N` | Días de antigüedad | 14 |
| `--intervalo N` | `-i N` | Segundos entre consultas | 300 (5 min) |
| `--config` | `-c` | Ver configuración actual | - |
| `--resumen` | `-r` | Generar resumen diario | - |

### Ejemplos:

```bash
# Monitoreo básico
python monitor_senapred.py --monitor

# Con sonido, últimos 3 días
python monitor_senapred.py --monitor --sound --dias 3

# Consulta cada 1 minuto
python monitor_senapred.py --monitor --sound --intervalo 60

# Solo ver alertas actuales sin monitoreo
python monitor_senapred.py --dias 7
```

---

## ⚙️ Configuración (config.json)

Al ejecutar por primera vez se crea automáticamente `config.json`:

```json
{
  "general": {
    "intervalo_segundos": 300,
    "dias_antiguedad": 14,
    "espera_pagina": 6,
    "espera_detalle": 4
  },
  "notificaciones": {
    "sonido_activado": true,
    "notificacion_escritorio": true,
    "modo_silencioso": {
      "activado": false,
      "hora_inicio": "23:00",
      "hora_fin": "07:00"
    }
  },
  "filtros": {
    "regiones": [],
    "tipos_alerta": ["roja", "amarilla", "temprana"]
  },
  "resumen_diario": {
    "activado": true,
    "hora_generacion": "08:00",
    "formato": "html"
  }
}
```

### Ejemplos de configuración:

**Monitorear solo algunas regiones:**
```json
{
  "filtros": {
    "regiones": ["Metropolitana", "Valparaíso", "Biobío"]
  }
}
```

**Activar modo silencioso nocturno:**
```json
{
  "notificaciones": {
    "modo_silencioso": {
      "activado": true,
      "hora_inicio": "23:00",
      "hora_fin": "07:00"
    }
  }
}
```

**Solo alertas rojas y amarillas:**
```json
{
  "filtros": {
    "tipos_alerta": ["roja", "amarilla"]
  }
}
```

---

## 📊 Dashboard

El monitor genera un **dashboard HTML estilo Grafana** con tema oscuro profesional.

**Archivo:** `dashboard_senapred.html`

### Incluye:
- 📈 **Stat Cards** - Total, Rojas, Amarillas, Tempranas
- 📋 **Tabla de alertas** - Ordenadas por prioridad con links
- 🗺️ **Estado por región** - Grid de 16 regiones con indicador visual
- 📊 **Gráfico por tipo** - Distribución en dona
- ⚠️ **Gráfico por causa** - Barras horizontales
- 🔔 **Activity log** - Cambios recientes
- 🔄 **Auto-refresh** cada 30 segundos

### Regiones de Chile (norte a sur):
1. Arica y Parinacota
2. Tarapacá
3. Antofagasta
4. Atacama
5. Coquimbo
6. Valparaíso
7. Metropolitana
8. O'Higgins
9. Maule
10. Ñuble
11. Biobío
12. La Araucanía
13. Los Ríos
14. Los Lagos
15. Aysén
16. Magallanes

---

## 📁 Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `config.json` | Configuración del monitor |
| `dashboard_senapred.html` | Dashboard visual interactivo |
| `datos_alertas.js` | Datos JSON para el dashboard |
| `estado_alertas.json` | Persistencia del estado |
| `log_alertas.csv` | Historial de eventos |
| `resumen_diario_YYYY-MM-DD.html` | Resumen diario automático |

---

## 🔔 Tipos de Alerta SENAPRED

| Color | Nivel | Descripción |
|-------|-------|-------------|
| 🔴 | **Alerta Roja** | Emergencia máxima |
| 🟡 | **Alerta Amarilla** | Precaución elevada |
| 🔵 | **Alerta Temprana** | Monitoreo preventivo |
| ✅ | **Sin Alerta** | Región sin alertas vigentes |

---

## 📞 Números de Emergencia Chile

| Servicio | Número |
|----------|--------|
| 🌲 CONAF (Incendios) | **130** |
| 🚒 Bomberos | **132** |
| 👮 Carabineros | **133** |
| 🚑 Ambulancia | **131** |
| 🔍 PDI | **134** |

---

## 📝 Changelog

### v6.1 (Actual)
- 📊 **Dashboard Grafana-style** - Tema oscuro profesional
- 🔇 **Modo silencioso** - Sin sonido en horarios configurables
- 📋 **Resumen diario** - Genera reporte HTML automático
- ⚙️ **config.json** - Configuración sin tocar código
- 🗺️ **Filtro por región** - Monitorea solo las que necesitas
- 📝 **Log CSV** - Historial persistente de eventos
- 🧹 **Código limpio** - Eliminación de datos no utilizados

### v5.2
- 🗺️ Mapa de 16 regiones de Chile
- ✅ Indicador de regiones sin alertas
- 🎨 Dashboard mejorado

### v5.0
- 📦 Extracción completa de datos
- 🔄 Sistema de deduplicación
- 📊 Dashboard con Chart.js

### v4.0
- 💾 Persistencia de estado
- 🔔 Notificaciones de escritorio
- 🔊 Alertas sonoras diferenciadas

---

## 🤝 Contribuir

Las contribuciones son bienvenidas:

1. Fork el proyecto
2. Crea tu branch (`git checkout -b feature/nueva-funcion`)
3. Commit (`git commit -m 'Agregar nueva función'`)
4. Push (`git push origin feature/nueva-funcion`)
5. Abre un Pull Request

---

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE)

---

## ⚠️ Disclaimer

Este proyecto **no está afiliado oficialmente** con SENAPRED ni con el Gobierno de Chile. Es una herramienta independiente que obtiene información pública.

**Siempre verifica la información oficial** en [senapred.cl](https://senapred.cl)

---

<p align="center">
  Desarrollado con ❤️ para la seguridad de Chile 🇨🇱
</p>
