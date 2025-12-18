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
python fx_orderbook.py
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

## Créditos
Este proyecto fue realizado por mmsirera23 como parte de un trabajo práctico final de trading algorítmico. Se aceptan contribuciones a través de pull requests.

---

¿Te gustaría que aplique este cambio directamente o prefieres hacerlo manualmente? 😊
```
