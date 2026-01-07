# 🚨 Monitor SENAPRED Chile v5.2

<p align="center">
  <strong>Sistema de monitoreo en tiempo real de alertas de emergencia de SENAPRED Chile</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/version-5.2-brightgreen.svg" alt="Version 5.2">
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
| 🗺️ **Mapa de 16 regiones** | Visualiza el estado de todo Chile |
| 🔔 **Notificaciones** | Alertas sonoras y de escritorio |
| 📊 **Dashboard HTML** | Gráficos interactivos auto-actualizables |
| 🔍 **Información completa** | Extrae todos los detalles de cada alerta |
| 🆕 **Detección de cambios** | Nueva, actualizada, cancelada |
| 📅 **Filtro por fecha** | Solo alertas de los últimos N días |
| ✅ **Estado por región** | Verde = sin alertas, colores = alertas activas |

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

---

## ⚙️ Opciones disponibles

| Opción | Corto | Descripción | Default |
|--------|-------|-------------|---------|
| `--monitor` | `-m` | Monitoreo continuo | No |
| `--sound` | `-s` | Alertas sonoras | No |
| `--dias N` | `-d N` | Días de antigüedad | 14 |
| `--intervalo N` | `-i N` | Segundos entre consultas | 300 (5 min) |

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

## 📊 Dashboard

El monitor genera un **dashboard HTML interactivo** que se abre en tu navegador.

**Archivo:** `dashboard_senapred.html`

### Incluye:
- 🗺️ **Mapa de 16 regiones** con estado de cada una
- ✅ **Regiones sin alertas** en verde
- 📈 Gráfico por tipo de alerta (dona)
- ⚠️ Gráfico por tipo de amenaza (barras)
- 📋 Lista detallada de alertas activas
- 🔔 Historial de cambios recientes
- 🔄 Auto-refresh cada 30 segundos

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
| `dashboard_senapred.html` | Dashboard visual interactivo |
| `datos_alertas.js` | Datos JSON para el dashboard |
| `estado_alertas.json` | Persistencia del estado del monitor |

---

## 🔔 Tipos de Alerta SENAPRED

| Color | Nivel | Descripción |
|-------|-------|-------------|
| 🔴 | **Alerta Roja** | Emergencia máxima |
| 🟡 | **Alerta Amarilla** | Precaución elevada |
| 🟢 | **Alerta Temprana Preventiva** | Monitoreo preventivo |
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

### v5.2 (Actual)
- ✂️ **Código optimizado** - 25% más liviano
- 🗺️ **Mapa de 16 regiones** - Visualiza todo Chile
- ✅ **Indicador sin alertas** - Regiones en verde
- 🎨 **Dashboard mejorado** - Mejor organización visual
- 🧹 **Limpieza de código** - Eliminación de campos no utilizados

### v5.0
- 📦 Extracción completa de datos de cada alerta
- 🔄 Sistema de deduplicación de alertas
- 📊 Dashboard con gráficos Chart.js

### v4.0
- 💾 Persistencia de estado entre ejecuciones
- 🔔 Notificaciones de escritorio Windows
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
