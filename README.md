# WMS Wave Picking & Multi-Picker Simulation System 

Simulador interactivo y optimizador logístico para centros de distribución (*Warehouse Management Systems* - WMS). Implementa la preparación de pedidos mediante la técnica de **Wave Picking (Agrupamiento por Olas)**, zonificación espacial del almacén, algoritmos de enrutamiento sobre grafos dirigidos (2D/3D) y un motor de simulación multi-agente con evasión reactiva de tráfico.

---

## Tabla de Contenidos
- [Descripción del Proyecto](#-descripción-del-proyecto)
- [Características Principales](#-características-principales)
- [Requisitos del Sistema](#-requisitos-del-sistema)
- [Instalación](#-instalación)
- [Ejecución](#-ejecución)
- [Guía Rápida de Uso del Simulador](#-guía-rápida-de-uso-del-simulador)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Estrategias de Ruteo Disponibles](#-estrategias-de-ruteo-disponibles)
- [Créditos y Licencia](#-créditos-y-licencia)

---

## Descripción del Proyecto

El sistema modela un centro de distribución real compuesto por estanterías (*racks*), pasillos de circulación de sentido único o doble, puertas de carga y zonas de despacho con control dinámico de peso. 

A partir de una cartera de pedidos de clientes, el software:
1. **Agrupa y fracciona pedidos (*Wave Batching & Order Splitting*)** respetando límites de peso, unidades y prioridades.
2. **Gestiona quiebres de stock** sustituyendo automáticamente productos por ubicaciones alternativas.
3. **Zonifica el almacén** dividiendo el espacio equitativamente entre los *pickers* asignados.
4. **Calcula rutas óptimas de recolección** evaluando distancias en planta y penalizaciones por altura vertical ($Z$).
5. **Simula en tiempo real** la operación paralela de la flota, resolviendo choques frontales e interbloqueos mediante desvíos dinámicos en el grafo y descarga en la zona de despacho más cercana.

---

## Características Principales

- **Algoritmos y Estructuras Nativas**: Implementación propia de **Tabla Hash** auto-redimensionable ($\alpha \le 0.75$), **Cola de Prioridad** (Min-Heap binario) y **Merge Sort** ($O(N \log N)$), sin dependencias externas pesadas.
- **Topología Celular y Conectividad Fuerte**: Grafo dirigido con verificación automática de accesibilidad en pasillos de mano única.
- **Validación Formal de Escenarios**: Comprobación rigurosa de 6 reglas de diseño arquitectónico y operativo.
- **Evasión Dinámica de Tráfico**: Detección de colisiones y recálculo en tiempo real mediante Dijkstra con bloqueo temporal de celdas.
- **Cooperación Inter-Zona (*Dynamic Helping*)**: Los operarios que finalizan sus tareas pueden asistir a zonas contiguas para reducir el tiempo total (*makespan*).
- **Interfaz Gráfica WMS Dashboard**: Lienzo vectorial interactivo con zoom responsivo, control de velocidad, trazabilidad por pedido y comparativa de métricas.
- **Persistencia Completa**: Carga y guardado de escenarios y estados de simulación en formato JSON (soporta pausar y reanudar).

---

## Requisitos del Sistema

- **Python**: Versión **3.10 o superior** (compatible con Python 3.10, 3.11, 3.12 y 3.14).
- **Sistema Operativo**: Windows 10/11, Linux (Ubuntu, Debian, Fedora, etc.) o macOS.
- **Librerías Externas**: **Ninguna**. El proyecto está desarrollado exclusivamente con la biblioteca estándar de Python (`math`, `random`, `time`, `json`, `os`, `tkinter`).

> [!NOTE]
> En entornos **Linux**, la librería gráfica `tkinter` suele venir empaquetada de forma separada al intérprete base. Si no la tienes instalada, consulta la sección de [Instalación](#-instalación).

---

## Instalación

1. **Clonar o descargar el repositorio**:
   ```bash
   git clone <URL-DEL-REPOSITORIO>
   cd PROYECTO-WAVE
   ```

2. **Verificar la versión de Python instalada**:
   ```bash
   python --version
   # o en Linux / macOS:
   python3 --version
   ```

3. **(Opcional) Usuarios de Linux / Ubuntu / Debian**:
   Si al ejecutar el sistema recibes un error indicando que `tkinter` no está disponible, instálalo con:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk
   ```

---

## Ejecución

Para iniciar el simulador visual, ejecuta el archivo principal `main.py`.

### Opción 1: Ejecutar desde la raíz del proyecto
```bash
python wave_picking_src/main.py
```
*(En Linux / macOS: `python3 wave_picking_src/main.py`)*

### Opción 2: Ingresar a la carpeta de código fuente
```bash
cd wave_picking_src
python main.py
```
*(En Linux / macOS: `python3 main.py`)*

Al iniciar, el sistema cargará automáticamente el escenario por defecto (`data/escenario_basico.json`) y desplegará el panel de control WMS.

---

## Guía Rápida de Uso del Simulador

1. **Elegir Escenario**:
   - En el panel superior, haz clic en **"Cargar Escenario JSON"** para abrir un archivo desde la carpeta `data/` (`escenario_basico.json` o `escenario_grande.json`), o selecciona **"⚙ Generar Escenario Automático"** para configurar dimensiones y cantidades personalizadas.
2. **Seleccionar Estrategia de Ruteo**:
   - En el menú desplegable, escoge entre:
     - **Estrategia A**: Orden de Pedidos (Secuencial).
     - **Estrategia B**: Cercanía 3D (Heurística Greedy + Altura $Z$).
     - **Estrategia C**: Barrido por Pasillos (S-Shape bilateral optimizado).
3. **Controles de Simulación**:
   - **Iniciar / Reanudar**: Comienza la animación continua del movimiento de los *pickers*.
   - **Pausar**: Detiene la marcha en el paso actual para inspeccionar el estado.
   - **Paso a Paso**: Avanza exactamente un ciclo de reloj para analizar desvíos y eventos.
   - **Reiniciar**: Regresa a todos los operarios y capacidades a su estado inicial.
   - **Control de Velocidad**: Deslizador para acelerar o ralentizar la animación en pantalla.
4. **Inspección de Datos**:
   - **Pestaña Zonas y Pickers**: Muestra el rango de columnas asignado a cada operario y su sublista de productos.
   - **Pestaña Comparativa**: Ejecuta y compara en una sola tabla el tiempo, operaciones y distancia total de las tres estrategias.
   - **Pestaña Trazabilidad**: Estado de cada pedido (`PENDIENTE`, `EN_WAVE`, `COMPLETADO`).

---

## Estructura del Proyecto

```text
PROYECTO-WAVE/
│
├── data/                                 # Escenarios preconfigurados
│   ├── escenario_basico.json             # Almacén de 18x16 con 4 racks y 2 pickers
│   └── escenario_grande.json             # Almacén de escala ampliada
│
├── wave_picking_src/                     # Código fuente del sistema
│   ├── main.py                           # Punto de entrada de la aplicación
│   ├── estructuras.py                    # TablaHash, ColaPrioridad (Min-Heap) y MergeSort
│   ├── modelos.py                        # Modelos del dominio (Rack, Pasillo, Wave, Pedido, etc.)
│   ├── warehouse.py                      # Topología del almacén, grafo dirigido y validación
│   ├── algoritmos.py                     # WaveManager, zonificación y Order Splitting
│   ├── rutas.py                          # Dijkstra con caché/bloqueos y estrategias A, B y C
│   ├── coordinador.py                    # Motor multi-picker y evasión reactiva de colisiones
│   ├── persistencia.py                   # Adaptador JSON (lectura, escritura y snapshots)
│   ├── generador.py                      # Generador procedural de escenarios válidos
│   └── simulacion.py                     # Interfaz gráfica de usuario en Tkinter (WMS Dashboard)
│
└── README.md                             # Documentación y manual de inicio
```

---

## Estrategias de Ruteo Disponibles

| Estrategia | Descripción | Ventajas Principales |
| :--- | :--- | :--- |
| **A - Orden de Pedidos** | Sigue estrictamente la secuencia de llegada de los ítems en el pedido del cliente. | Línea base de comparación; orden cronológico simple. |
| **B - Cercanía 3D (Greedy)** | Selecciona en cada paso el producto más cercano en el grafo penalizando la altura vertical del estante ($Z$). | Reduce sustancialmente la distancia en almacenes con dispersión uniforme. |
| **C - Barrido de Pasillos (S-Shape)** | Agrupa la recolección por pasillos en patrón zig-zag, tomando ambos lados del pasillo en una pasada. | **Máxima eficiencia**: minimiza giros, reduce congestión entre pickers y acorta el *makespan*. |

---

## Créditos y Licencia

- **Proyecto**: Sistema de Optimización de Wave Picking y Simulación Multi-Picker.
- **Desarrollo**: Código modular bajo estándares de arquitectura limpia y principios SOLID.
- **Licencia**: Proyecto académico y demostrativo de libre uso y distribución educativa.

