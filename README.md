# Trading Algorítmico - Trabajo Práctico Final

## Descripción
Este proyecto implementa un sistema de procesamiento de datos de mercado para arbitraje FX basado en bonos argentinos, incluyendo funciones para mantener un order book actualizado, cálculo dinámico de comisiones, validación de balances, manejo de excepciones, y generación de reportes de control de riesgos.

### Características principales:
- **Cálculo de comisiones dinámicas:** El sistema ajusta las tarifas del mercado cobradas en pesos según el tipo de cambio final del día.
- **Validación de saldo:** Previene problemas de ejecución cuando los balances en ARS o USD son insuficientes para cubrir las operaciones.
- **Manejo robusto de excepciones:** Incluye reintentos automáticos para enviar órdenes vía FIX Protocol en caso de fallos.
- **Generación de reportes:** Documenta cada operación, incluyendo métricas como retornos, comisiones cobradas, balances iniciales y finales.

---

## Requisitos Previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

---

## Configuración del Entorno

### Paso 1: Crear un entorno virtual (recomendado)
```bash
# Crear el entorno virtual
python3 -m venv venv

# Activar el entorno virtual
# En macOS/Linux:
source venv/bin/activate

# En Windows:
# venv\Scripts\activate
```

### Paso 2: Instalar dependencias
```bash
# Asegúrate de estar en el directorio raíz del proyecto
pip install -r requirements.txt
```

### Paso 3: Verificar la instalación
```bash
# Verificar que Python está funcionando correctamente
python --version

# Verificar que las dependencias se instalaron correctamente
python -c "import pandas; import numpy; print('Dependencias instaladas correctamente')"
```

---

## Estructura del Proyecto

```
tpFinal/
├── data/                  # Archivos CSV con datos de mercado
│   ├── GFGC79115D_11_11.csv
│   ├── GFGV79115D_11_11.csv
│   └── ...
├── consignas/             # Consignas del trabajo práctico
├── fx_orderbook.py        # Módulo principal con funciones de FX
├── execute_trade.py       # Módulo para ejecución de trades y actualizaciones
├── strategy.py            # Lógica para implementar arbitraje triangular
├── requirements.txt       # Dependencias del proyecto
└── README.md              # Este archivo
```

---

## Uso

### Ejecutar el procesamiento de datos
```bash
# Desde el directorio raíz del proyecto
python orderbook.py
```

### Ejecutar la estrategia de arbitraje FX
```bash
# Desde el directorio raíz del proyecto
python strategy.py
```

---

## Funcionalidades

### **Lectura de market data**
Función para leer y parsear archivos CSV con datos de mercado.

### **Order Book**
Estructura de datos para mantener el libro de órdenes actualizado, incluyendo niveles de precios bid/offer con volúmenes.

### **Cálculo dinámico de comisiones**
Calcula tarifas cobradas en pesos ajustadas al tipo de cambio final del día, diferenciando operaciones en USD y ARS.

### **Validación de saldo**
Valida que los balances disponibles en ARS o USD sean suficientes para cubrir el costo total de la operación y las comisiones antes de ejecutarla.

### **Manejo de excepciones**
Implementa reintentos automáticos para enviar órdenes vía FIX Protocol en caso de fallos.

### **Generación de reportes**
Genera informes detallados tras cada operación, incluyendo:
- Balance inicial y final.
- Comisión cobrada.
- Retorno porcentual de la operación.

---

## Simulación y Pruebas
### Pruebas con datos históricos
1. Coloca archivos de pruebas en la carpeta `data/`.
2. Ajusta los parámetros de simulación en `strategy.py` para usar estos archivos.
3. Ejecuta el script y revisa los informes generados para validar las métricas de retorno.

### Validación de cambios recientes
Para probar:
- Cálculo de tarifas dinámicas, ejecuta `execute_trade.py`.
- Estrategia de arbitraje completa, ejecuta `strategy.py` con datos simulados.

---

## Notas
- Los archivos de datos deben estar en la carpeta `data/`.
- El formato de los archivos CSV incluye niveles de bid/offer con precios y cantidades.
- El sistema procesa los datos cronológicamente para mantener el estado del order book y evaluar oportunidades de arbitraje.

---

## Resultados de la simulación (ejecución reciente)

Resumen de métricas obtenidas al ejecutar la simulación con un capital inicial de 500.000.000 ARS:

- Trades ejecutados: 111
- Órdenes ejecutadas (legs): 444
- Latencia total (por arbitraje): 31.56 ms
- Latencia total (órdenes): 12.06 ms
- Latencia media por orden: 0.03 ms
- PnL total (ARS): 279,512,694.56
- PnL total (USD): -78,350.08
- Balance final ARS: 779,512,694.56
- Balance final USD: -78,350.08

Observaciones y recomendaciones:

- El run mostró un PnL positivo en ARS pero saldo USD negativo al final. Esto puede deberse a la secuencia de legs y al modelado simplificado del flujo de caja entre legs; si es inaceptable, consideramos aplicar una política conservadora que impida ejecutar arbitrajes que dejen el `USD` en negativo.
- Se detectaron excepciones de formato en los logs (uso de formatos tipo `% , .2f` pasados como argumentos a `logger`). 
- Métricas de latencia y PnL se guardan y muestran en consola; para auditoría continua se puede exportar `stats` a CSV/JSON desde `run_data.py`.

---
## Integrantes del grupo: 
Milagros Sirera, Jonathan David Fichelson, y Rodrigo Basavilbaso. 
```
