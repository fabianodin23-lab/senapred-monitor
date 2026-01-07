# 🚨 Monitor SENAPRED v5.2

Sistema de monitoreo en tiempo real de alertas del Servicio Nacional de Prevención y Respuesta ante Desastres de Chile (SENAPRED).

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Características

- 🔴🟡🟢 **Monitoreo de alertas**: Roja, Amarilla y Temprana/Preventiva
- 🗺️ **Mapa de 16 regiones**: Visualiza el estado de todas las regiones de Chile
- 📊 **Dashboard interactivo**: Gráficos y estadísticas en tiempo real
- 🔔 **Notificaciones**: Alertas de escritorio en Windows
- 🔊 **Sonido**: Alertas audibles para nuevas emergencias
- 🔄 **Auto-refresh**: Dashboard se actualiza cada 30 segundos
- 💾 **Persistencia**: Guarda estado entre ejecuciones
- 📋 **Historial de cambios**: Registro de alertas nuevas, actualizadas y canceladas

## 📋 Requisitos

```bash
pip install selenium webdriver-manager beautifulsoup4 plyer
```

## 🚀 Uso

### Consulta única
```bash
python monitor_senapred.py --dias 7
```

### Modo monitor continuo
```bash
python monitor_senapred.py --monitor --sound --dias 7 --intervalo 120
```

### Parámetros

| Parámetro | Corto | Descripción | Default |
|-----------|-------|-------------|---------|
| `--monitor` | `-m` | Modo monitoreo continuo | False |
| `--sound` | `-s` | Activar sonido en alertas | False |
| `--dias` | `-d` | Días de antigüedad máxima | 14 |
| `--intervalo` | `-i` | Segundos entre consultas | 300 |

## 📊 Dashboard

El script genera `dashboard_senapred.html` que muestra:

- **Resumen**: Total de alertas por tipo
- **Mapa de regiones**: Las 16 regiones con su estado (verde = sin alertas)
- **Lista de alertas**: Detalle de cada alerta activa
- **Gráficos**: Distribución por tipo y por amenaza
- **Cambios recientes**: Historial de modificaciones

Abre el archivo en tu navegador para visualizar.

## 📁 Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `dashboard_senapred.html` | Dashboard visual |
| `datos_alertas.js` | Datos para el dashboard |
| `estado_alertas.json` | Estado persistente |

## 🔔 Tipos de alerta

| Tipo | Color | Descripción |
|------|-------|-------------|
| Roja | 🔴 | Emergencia mayor |
| Amarilla | 🟡 | Precaución |
| Temprana | 🟢 | Preventiva |

## 📞 Números de emergencia Chile

- **CONAF**: 130
- **Bomberos**: 132
- **Carabineros**: 133
- **Ambulancia**: 131

## 📝 Changelog

### v5.2 (Actual)
- ✂️ Código optimizado (-25% tamaño)
- 🗺️ Mapa de 16 regiones de Chile
- ✅ Indicador de regiones sin alertas
- 🎨 Dashboard mejorado

### v5.0
- 📦 Extracción completa de datos
- 🔄 Sistema de deduplicación
- 📊 Dashboard con gráficos

### v4.0
- 💾 Persistencia de estado
- 🔔 Notificaciones de escritorio
- 🔊 Alertas sonoras

## 📄 Licencia

MIT License

## 🔗 Fuente

Datos obtenidos de [SENAPRED](https://senapred.cl/alertas/)
