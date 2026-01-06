# 🚨 Monitor SENAPRED v5.0

Sistema de monitoreo de alertas de emergencia de SENAPRED Chile.

## 📦 Instalación Rápida (Windows)

1. **Descomprime** esta carpeta donde quieras (ej: `C:\senapred-monitor`)
2. **Doble clic** en `INSTALAR.bat`
3. ¡Listo!

## 🚀 Uso

### Opción 1: Doble clic (más fácil)
- `VER_ALERTAS.bat` → Consulta las alertas una vez
- `INICIAR_MONITOR.bat` → Monitoreo continuo con sonido

### Opción 2: Línea de comandos
```cmd
cd C:\senapred-monitor

# Ver alertas actuales
python monitor_senapred.py

# Monitoreo continuo con sonido
python monitor_senapred.py --monitor --sound

# Solo últimos 7 días
python monitor_senapred.py --dias 7

# Monitoreo cada 2 minutos
python monitor_senapred.py --monitor --sound --dias 7 --intervalo 120
```

## 📊 Dashboard

Después de ejecutar el monitor, abre en tu navegador:
- `dashboard_senapred.html`

El dashboard se actualiza automáticamente cada 30 segundos.

## 📋 Archivos Generados

| Archivo | Descripción |
|---------|-------------|
| `dashboard_senapred.html` | Dashboard visual |
| `datos_alertas.js` | Datos para el dashboard |
| `estado_alertas.json` | Estado del monitor |
| `log_alertas.txt` | Registro de actividad |

## ⚙️ Opciones

| Opción | Descripción |
|--------|-------------|
| `--monitor` o `-m` | Monitoreo continuo |
| `--sound` o `-s` | Alertas sonoras |
| `--dias N` o `-d N` | Últimos N días (default: 14) |
| `--intervalo N` o `-i N` | Segundos entre consultas (default: 300) |

## 📞 Emergencias Chile

- 🌲 CONAF: **130**
- 🚒 Bomberos: **132**
- 👮 Carabineros: **133**
- 🚑 Ambulancia: **131**

## 🔧 Requisitos

- Python 3.8+
- Google Chrome instalado
- Conexión a Internet

---
Desarrollado para monitoreo de emergencias 🇨🇱
