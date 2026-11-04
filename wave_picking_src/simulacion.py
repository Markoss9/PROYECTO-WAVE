"""
Módulo de Simulación Interactiva Completa (Rediseño UI/UX - Correcciones WMS Realista)
Conecta la interfaz visual con Order Splitting, penalización Z y coordinación Multi-Picker.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from algoritmos import WaveManager, Pathfinding, CoordinadorMultiPicker
from persistencia import PersistenciaJSON


class AppVisual(tk.Tk):
    def __init__(self, warehouse, funcion_generador=None):
        super().__init__()
        self.title("WMS Dashboard - Simulador Wave Picking Multi-Picker")
        self.geometry("1400x900")
        self.warehouse = warehouse
        self.funcion_generador = funcion_generador
        self.waves = []

        self.celda_tam = self._calcular_zoom_optimo()
        self.simulando = False
        self.pausado = False
        self.vel_simulacion = 0.12
        self.paso_actual = 0

        self.planes_activos = []
        self.nodos_recogidos = set()
        self.info_nodos_acceso = {}

        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._configurar_estilos()
        self._construir_ui()
        self._actualizar_lienzo_completo()

    def _configurar_estilos(self):
        """Aplica una paleta Dark/Slate UI y CORRIGE los bugs visuales de Tkinter."""
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.BG_APP = "#1e272e"       
        self.BG_PANEL = "#2f3640"     
        self.FG_TEXT = "#f5f6fa"      
        self.ACCENT_PRI = "#0097e6"   
        self.ACCENT_SEC = "#44bd32"   
        self.BG_BTN = "#718093"       

        self.configure(bg=self.BG_APP)

        # Configuraciones globales
        style.configure(".", background=self.BG_APP, foreground=self.FG_TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.BG_APP)
        style.configure("TLabel", background=self.BG_APP, foreground=self.FG_TEXT)
        
        style.configure("TLabelframe", background=self.BG_APP, foreground="#00a8ff", borderwidth=1, font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe.Label", background=self.BG_APP, foreground="#00a8ff")

        # Botones
        style.configure("TButton", padding=5, relief="flat", background=self.BG_BTN, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map("TButton", background=[("active", "#dcdde1")], foreground=[("active", "black")])
        style.configure("Primary.TButton", background=self.ACCENT_PRI)
        style.map("Primary.TButton", background=[("active", "#00a8ff")])

        # CORRECCIÓN: Combobox legibles (Evita letras blancas sobre fondo blanco)
        style.configure("TCombobox", fieldbackground=self.BG_PANEL, background=self.BG_BTN, foreground=self.FG_TEXT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", self.BG_PANEL)],
                  selectbackground=[("readonly", self.ACCENT_PRI)],
                  foreground=[("readonly", self.FG_TEXT)])

        # CORRECCIÓN: Treeview (Tablas de Inventario/Waves) para que no sean invisibles
        style.configure("Treeview", background=self.BG_PANEL, foreground=self.FG_TEXT, rowheight=25, fieldbackground=self.BG_PANEL)
        style.map("Treeview", background=[("selected", self.ACCENT_PRI)], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=self.BG_APP, foreground="#f1c40f", font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[("active", self.BG_PANEL)])

        # Notebooks (Pestañas)
        style.configure("TNotebook", background=self.BG_APP)
        style.configure("TNotebook.Tab", background=self.BG_PANEL, foreground=self.FG_TEXT)
        style.map("TNotebook.Tab", background=[("selected", self.ACCENT_PRI)])

        style.configure("TScale", background=self.BG_APP, troughcolor=self.BG_PANEL)
        style.configure("Horizontal.TScrollbar", background=self.BG_PANEL, troughcolor=self.BG_APP)
        style.configure("Vertical.TScrollbar", background=self.BG_PANEL, troughcolor=self.BG_APP)

    def _calcular_zoom_optimo(self):
        max_w = 880 // max(1, self.warehouse.ancho_x)
        max_h = 720 // max(1, self.warehouse.largo_y)
        return max(12, min(38, min(max_w, max_h)))

    def _y_pantalla(self, y_modelo):
        return (self.warehouse.largo_y - 1) - y_modelo

    def _construir_ui(self):
        # Reducción de padding general para evitar que se corte por abajo
        frame_izq = ttk.Frame(self, padding="8")
        frame_izq.grid(row=0, column=0, sticky="ns")

        # 1. Gestión de Escenarios
        lf_gestion = ttk.LabelFrame(frame_izq, text=" 📁 Configuración CD ", padding=6)
        lf_gestion.pack(fill="x", pady=(0, 4))

        btn_frame_arch = ttk.Frame(lf_gestion)
        btn_frame_arch.pack(fill="x", pady=1)
        ttk.Button(btn_frame_arch, text="📂 Cargar JSON", command=self.cmd_cargar_json).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(btn_frame_arch, text="💾 Guardar JSON", command=self.cmd_guardar_json).pack(side="left", expand=True, fill="x", padx=1)

        ttk.Button(lf_gestion, text="⚙️ Generar Escenario Auto", command=self.cmd_abrir_generador).pack(fill="x", pady=2)
        ttk.Button(lf_gestion, text="📋 Ver Productos y Pedidos", command=self.cmd_ver_inventario).pack(fill="x", pady=2)

        # 2. Waves y Estrategias
        lf_plan = ttk.LabelFrame(frame_izq, text=" ⚙️ Motor de WMS ", padding=6)
        lf_plan.pack(fill="x", pady=4)

        ttk.Button(lf_plan, text="1. Generar Waves (Order Splitting)", command=self.cmd_generar_waves, style="Primary.TButton").pack(fill="x", pady=2)

        ttk.Label(lf_plan, text="Seleccionar Wave:").pack(anchor="w", pady=(2,0))
        self.cmb_waves = ttk.Combobox(lf_plan, state="readonly", width=36)
        self.cmb_waves.pack(fill="x", pady=1)

        ttk.Label(lf_plan, text="Estrategia de Ruta:").pack(anchor="w", pady=(2,0))
        self.cmb_estrategia = ttk.Combobox(
            lf_plan,
            values=[
                "Estrategia A - Orden de Llegada",
                "Estrategia B - Cercanía 3D (Greedy)",
                "Estrategia C - Barrido de Pasillos"
            ],
            state="readonly"
        )
        self.cmb_estrategia.set("Estrategia B - Cercanía 3D (Greedy)")
        self.cmb_estrategia.pack(fill="x", pady=1)

        ttk.Button(lf_plan, text="2. Calcular Ruta (Aislar Wave)", command=self.cmd_calcular_ruta).pack(fill="x", pady=2)
        ttk.Button(lf_plan, text="👥 Simular Multi-Picker (Flota)", command=self.cmd_calcular_multipicker, style="Primary.TButton").pack(fill="x", pady=2)
        ttk.Button(lf_plan, text="📊 Benchmarking Estrategias", command=self.cmd_comparar_estrategias).pack(fill="x", pady=2)

        # 3. Controles de Simulación
        lf_ctrl = ttk.LabelFrame(frame_izq, text=" 🎮 Controles ", padding=6)
        lf_ctrl.pack(fill="x", pady=4)

        frame_sim = ttk.Frame(lf_ctrl)
        frame_sim.pack(fill="x")
        ttk.Button(frame_sim, text="▶ Iniciar", command=self.cmd_iniciar).grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏸ Pausar", command=self.cmd_pausar).grid(row=0, column=1, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏯ Continuar", command=self.cmd_continuar).grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏭ Paso a Paso", command=self.cmd_paso).grid(row=1, column=1, sticky="ew", padx=1, pady=1)
        frame_sim.columnconfigure(0, weight=1)
        frame_sim.columnconfigure(1, weight=1)

        ttk.Button(lf_ctrl, text="🔄 Resetear Telemetría", command=self.cmd_reiniciar).pack(fill="x", pady=(2, 2))

        ttk.Label(lf_ctrl, text="Velocidad (ms):").pack(anchor="w")
        self.scale_vel = ttk.Scale(lf_ctrl, from_=20, to=800, orient="horizontal", command=self.cmd_cambiar_velocidad)
        self.scale_vel.set(120)
        self.scale_vel.pack(fill="x")

        ttk.Label(lf_ctrl, text="Zoom Global:").pack(anchor="w")
        self.scale_zoom = ttk.Scale(lf_ctrl, from_=10, to=50, orient="horizontal", command=self.cmd_cambiar_zoom)
        self.scale_zoom.set(self.celda_tam)
        self.scale_zoom.pack(fill="x")

        # 4. Handhelds Rugerizadas (Compactadas para mejor visión)
        lf_monitor = ttk.LabelFrame(frame_izq, text=" 📡 Handheld WMS: Monitor ", padding=3)
        lf_monitor.pack(fill="x", pady=2)
        
        self.lbl_metricas = tk.Label(
            lf_monitor, 
            text=f"SYSTEM BOOT...\nLAYOUT: {self.warehouse.ancho_x}x{self.warehouse.largo_y}\nSKUs: {len(self.warehouse.productos)} | ORD: {len(self.warehouse.pedidos)}\n> WAITING FOR CONSOLIDATION...",
            justify="left", font=("Consolas", 10, "bold"),
            bg="#000000", fg="#39ff14", relief="sunken", padx=6, pady=4,
            highlightthickness=1, highlightbackground="#353b48"
        )
        self.lbl_metricas.pack(fill="x")

        lf_eventos = ttk.LabelFrame(frame_izq, text=" 📝 Handheld WMS: Log Eventos ", padding=3)
        lf_eventos.pack(fill="both", expand=True, pady=2)

        # Altura reducida de 7 a 5 líneas para asegurar que no se corte por abajo
        self.txt_eventos = tk.Text(
            lf_eventos, height=5, width=38, font=("Courier", 10, "bold"),
            bg="#000000", fg="#ffb300", state="disabled", relief="sunken", padx=6, pady=4,
            insertbackground="white", highlightthickness=1, highlightbackground="#353b48"
        )
        self.txt_eventos.pack(fill="both", expand=True)

        # Panel Derecho: Canvas con Scrollbars
        frame_der = ttk.Frame(self)
        frame_der.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)
        frame_der.rowconfigure(0, weight=1)
        frame_der.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(frame_der, bg="#111418", highlightthickness=2, highlightbackground="#7f8fa6")
        scroll_y = ttk.Scrollbar(frame_der, orient="vertical", command=self.canvas.yview)
        scroll_x = ttk.Scrollbar(frame_der, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

    def _registrar_evento(self, texto, limpiar=False):
        self.txt_eventos.configure(state="normal")
        if limpiar:
            self.txt_eventos.delete("1.0", tk.END)
        self.txt_eventos.insert(tk.END, "> " + texto + "\n")
        self.txt_eventos.see(tk.END)
        self.txt_eventos.configure(state="disabled")

    def _actualizar_lienzo_completo(self):
        ancho_px = self.warehouse.ancho_x * self.celda_tam
        alto_px = self.warehouse.largo_y * self.celda_tam
        self.canvas.config(scrollregion=(0, 0, ancho_px, alto_px))
        self._dibujar_warehouse()

    def _dibujar_warehouse(self):
        self.canvas.delete("all")
        t = self.celda_tam
        simbolos = {"N": "↑", "S": "↓", "E": "→", "O": "←", "AMBOS": "·"}

        for x in range(self.warehouse.ancho_x):
            for y in range(self.warehouse.largo_y):
                yp = self._y_pantalla(y)
                x1, y1 = x * t, yp * t
                x2, y2 = x1 + t, y1 + t
                tipo = self.warehouse.grilla_tipo.get((x, y), "PASILLO")
                sentido = self.warehouse.grilla_sentido.get((x, y), "AMBOS")

                if tipo == "PASILLO":
                    color_fondo = "#576574" if sentido == "AMBOS" else "#485460"
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill=color_fondo, outline="")
                    
                    if sentido != "AMBOS":
                        self.canvas.create_line(x1+1, y1, x1+1, y2, fill="#f1c40f", dash=(int(t/3), int(t/3)))
                        self.canvas.create_line(x2-1, y1, x2-1, y2, fill="#f1c40f", dash=(int(t/3), int(t/3)))
                        if t >= 16:
                            self.canvas.create_text(
                                x1 + t/2, y1 + t/2, text=simbolos.get(sentido, "·"),
                                fill="#d1ccc0", font=("Arial", max(8, int(t*0.5)), "bold")
                            )

        for rack in self.warehouse.racks:
            for rx, ry in rack.celdas():
                yp = self._y_pantalla(ry)
                rx1, ry1 = rx * t, yp * t
                rx2, ry2 = rx1 + t, ry1 + t
                
                self.canvas.create_rectangle(rx1, ry1, rx2, ry2, fill="#2d3436", outline="#7f8fa6", width=2)
                self.canvas.create_line(rx1+2, ry1+2, rx2-2, ry2-2, fill="#636e72", width=1)
                self.canvas.create_line(rx1+2, ry2-2, rx2-2, ry1+2, fill="#636e72", width=1)
                
            if t >= 14:
                cx = (rack.x + rack.ancho / 2) * t
                cy = (self._y_pantalla(rack.y + rack.alto - 1) + rack.alto / 2) * t
                self.canvas.create_rectangle(cx - t*0.8, cy - t*0.4, cx + t*0.8, cy + t*0.4, fill="#b2bec3")
                self.canvas.create_text(cx, cy, text=rack.id_rack, fill="#2d3436", font=("Segoe UI", max(7, int(t*0.35)), "bold"))

        for zona in self.warehouse.zonas_despacho:
            for zx, zy in zona.celdas():
                yp = self._y_pantalla(zy)
                bx1, by1 = zx * t, yp * t
                bx2, by2 = bx1 + t, by1 + t
                
                self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#222f3e", outline="")
                espacio = int(t / 4) if t >= 12 else 4
                for i in range(0, int(t * 2), espacio):
                    self.canvas.create_line(bx1 + i, by1, bx1, by1 + i, fill="#f1c40f", width=max(1, int(t/10)))
                    
            cx = (zona.x + zona.ancho / 2) * t
            cy = (self._y_pantalla(zona.y + zona.alto - 1) + zona.alto / 2) * t
            self.canvas.create_rectangle(cx - t*1.2, cy - t*0.6, cx + t*1.2, cy + t*0.6, fill="#000000", outline="#f1c40f")
            self.canvas.create_text(
                cx, cy, text=f"{zona.id_zona}\nMAX {zona.peso_max_kg:.0f}KG",
                fill="#f1c40f", font=("Courier", max(6, int(t*0.22)), "bold")
            )

        for puerta in self.warehouse.puertas:
            yp = self._y_pantalla(puerta.y)
            px1, py1 = puerta.x * t, yp * t
            px2, py2 = px1 + t, py1 + t
            
            color_p = "#ff4757" if puerta.tipo == "OUTBOUND" else ("#2ed573" if puerta.tipo == "INBOUND" else "#1e90ff")
            self.canvas.create_rectangle(px1, py1, px2, py2, fill="#2f3542", outline=color_p, width=2)
            
            for i in range(1, int(t), max(3, int(t/6))):
                self.canvas.create_line(px1, py1+i, px2, py1+i, fill="#747d8c", width=1)
                
            lbl = "OUT" if puerta.tipo == "OUTBOUND" else ("IN" if puerta.tipo == "INBOUND" else "MIX")
            self.canvas.create_rectangle(px1 + 2, py1 + t/2 - 6, px2 - 2, py1 + t/2 + 6, fill=color_p, outline="")
            self.canvas.create_text(px1 + t/2, py1 + t/2, text=lbl, fill="white", font=("Segoe UI", max(6, int(t*0.25)), "bold"))

        dx, dy = self.warehouse.zona_despacho
        dyp = self._y_pantalla(dy)
        self.canvas.create_rectangle(dx*t + 2, dyp*t + 2, (dx+1)*t - 2, (dyp+1)*t - 2, outline="#00ff00", width=2, dash=(2, 2))

    def _dibujar_productos_waves(self, lista_waves):
        colores = ["#e74c3c", "#9b59b6", "#3498db", "#1abc9c", "#d35400", "#c0392b"]
        t = self.celda_tam
        self.info_nodos_acceso.clear()

        for w_idx, wave in enumerate(lista_waves):
            color_w = colores[w_idx % len(colores)]
            for linea in getattr(wave, 'lineas', []):
                prod = self.warehouse.productos.obtener(linea.producto_id)
                if prod is not None:
                    ax, ay = self.warehouse.obtener_nodo_acceso(prod.x, prod.y)
                    self.info_nodos_acceso.setdefault((ax, ay), []).append(
                        (prod.id_prod, prod.nombre, linea.cantidad, linea.peso_total, linea.pedido_id)
                    )

                    yp = self._y_pantalla(prod.y)
                    cx = prod.x * t + t / 2
                    cy = yp * t + t / 2
                    
                    ancho_tag = int(t * 0.45)
                    alto_tag = int(t * 0.25)
                    
                    color_bg = "#2ecc71" if prod.z == 1 else ("#f39c12" if prod.z == 2 else "#e74c3c")
                    txt_z = f"z{prod.z}" if prod.z < 3 else "⚠ z3"
                    color_txt = "black" if prod.z == 2 else "white"

                    self.canvas.create_rectangle(
                        cx - ancho_tag, cy - alto_tag, cx + ancho_tag, cy + alto_tag,
                        fill=color_bg, outline="#ffffff", width=1.5
                    )
                    if (ax, ay) not in self.nodos_recogidos and t >= 14:
                        self.canvas.create_text(
                            cx, cy, text=txt_z, fill=color_txt,
                            font=("Segoe UI", max(6, int(t * 0.22)), "bold"),
                            tags=f"prod_txt_{ax}_{ay}"
                        )

    def _obtener_funcion_estrategia(self):
        est = self.cmb_estrategia.get()
        if "A" in est:
            return Pathfinding.estrategia_a_orden_pedidos
        if "C" in est:
            return Pathfinding.estrategia_c_pasillos
        return Pathfinding.estrategia_b_cercania

    def cmd_generar_waves(self):
        pedidos = self.warehouse.pedidos.valores()
        if not pedidos:
            messagebox.showwarning("Atención", "No hay pedidos cargados en el escenario.")
            return

        self.waves = WaveManager.generar_waves(pedidos, self.warehouse)
        self.cmb_waves['values'] = [
            f"{w.id_wave} (Ped:{len(w.pedidos_involucrados)} | {w.total_unidades}u | {w.peso_total:.1f}kg)"
            for w in self.waves
        ]
        if self.waves:
            self.cmb_waves.current(0)
            self._registrar_evento(f"OK: {len(self.waves)} Waves generadas (Splitting):", limpiar=True)
            for w in self.waves:
                self._registrar_evento(f" {w.id_wave} [{w.picker_id}]: ({w.peso_total:.1f}kg)")

    def cmd_calcular_ruta(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return

        idx = max(0, self.cmb_waves.current())
        wave = self.waves[idx]

        fn_est = self._obtener_funcion_estrategia()
        res = fn_est(self.warehouse, wave)

        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        self.nodos_recogidos.clear()

        self._dibujar_warehouse()
        self._dibujar_productos_waves([wave])

        self.planes_activos = [{
            "id_picker": wave.picker_id or "PK_01",
            "color": "#00a8ff",
            "historial": res["camino"],
            "eventos": ["Avanza"] * len(res["camino"]),
            "peso_actual": 0.0,
            "oval_id": None,
            "txt_id": None
        }]

        texto_metricas = (
            f"MODO: 1 Picker AISLADO ({wave.id_wave})\n"
            f"ESTRATEGIA: {res['estrategia']}\n"
            f"COSTO T (Pasos+Z): {res['distancia']}\n"
            f"PASOS: {res['aristas_recorridas']} | Z-PENAL: {res.get('costo_altura_z', 0)}\n"
            f"NODOS V: {res['nodos_visitados']} | CPU: {res['tiempo_ms']:.2f} ms"
        )
        self.lbl_metricas.config(text=texto_metricas)
        self._registrar_evento(f"Ruta lista para {wave.id_wave}. Presione ▶ Iniciar.", limpiar=True)
        self._posicionar_pickers_iniciales()

    def cmd_calcular_multipicker(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return

        fn_est = self._obtener_funcion_estrategia()
        planes_coord = CoordinadorMultiPicker.planificar_simulacion_multipicker(
            self.warehouse, self.waves, fn_est
        )
        if not planes_coord:
            messagebox.showwarning("Atención", "No se pudieron planificar rutas multi-picker.")
            return

        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        self.nodos_recogidos.clear()

        waves_activas = [p["wave"] for p in planes_coord]
        self._dibujar_warehouse()
        self._dibujar_productos_waves(waves_activas)

        colores_pk = ["#00a8ff", "#9c88ff", "#e84118", "#44bd32", "#fbc531", "#e1b12c"]
        self.planes_activos = []
        total_desvios = 0
        max_dist = 0

        for i, p in enumerate(planes_coord):
            pk_id = p["picker"].id_picker
            self.planes_activos.append({
                "id_picker": pk_id,
                "color": colores_pk[i % len(colores_pk)],
                "historial": p["historial"],
                "eventos": p["eventos"],
                "peso_actual": 0.0,
                "oval_id": None,
                "txt_id": None
            })
            total_desvios += p["desvios"]
            max_dist = max(max_dist, len(p["historial"]) - 1)

        texto_metricas = (
            f"MODO: FLOTA MULTI-PICKER ({len(self.planes_activos)} AGVs)\n"
            f"PASOS SYNC: {max_dist}\n"
            f"DESVÍOS WMS: {total_desvios}\n"
            f"COLISIONES: 0 (Evasión Auto)"
        )
        self.lbl_metricas.config(text=texto_metricas)
        self._registrar_evento(
            f"FLOTA LISTA ({len(self.planes_activos)} AGVs activos).\n"
            f"Desvíos pre-calculados: {total_desvios}. Presione ▶.",
            limpiar=True
        )
        self._posicionar_pickers_iniciales()

    def _posicionar_pickers_iniciales(self):
        t = self.celda_tam
        for plan in self.planes_activos:
            if plan["historial"]:
                ix, iy = plan["historial"][0]
                yp = self._y_pantalla(iy)
                x_px, y_px = ix * t, yp * t
                
                # CORRECCIÓN: Polígono de AGV más grande y geométrico simulando forma real
                puntos_agv = [
                    x_px + t*0.05, y_px + t*0.1,   # Sup Izq
                    x_px + t*0.65, y_px + t*0.1,   # Sup Der (Cuerpo)
                    x_px + t*0.65, y_px + t*0.25,  # Baja a Horquilla 1
                    x_px + t*0.95, y_px + t*0.25,  # Punta Horquilla 1
                    x_px + t*0.95, y_px + t*0.4,   # Grosor Horquilla 1
                    x_px + t*0.65, y_px + t*0.4,   # Vuelve a cuerpo
                    x_px + t*0.65, y_px + t*0.6,   # Salto a Horquilla 2
                    x_px + t*0.95, y_px + t*0.6,   # Punta Horquilla 2
                    x_px + t*0.95, y_px + t*0.75,  # Grosor Horquilla 2
                    x_px + t*0.65, y_px + t*0.75,  # Vuelve a cuerpo
                    x_px + t*0.65, y_px + t*0.9,   # Inf Der (Cuerpo)
                    x_px + t*0.05, y_px + t*0.9    # Inf Izq
                ]
                
                plan["oval_id"] = self.canvas.create_polygon(
                    *puntos_agv, fill=plan["color"], outline="#ffffff", width=1.5
                )
                
                # CORRECCIÓN: Texto centrado en el cuerpo ancho del AGV y fuente ampliada
                tam_fuente = max(6, int(t * 0.28))
                plan["txt_id"] = self.canvas.create_text(
                    x_px + t*0.32, y_px + t*0.5, text="0k",
                    fill="white", font=("Consolas", tam_fuente, "bold")
                )

    def mover_picker(self):
        if not self.planes_activos:
            self.simulando = False
            return

        max_len = max(len(p["historial"]) for p in self.planes_activos)
        if self.paso_actual >= max_len:
            self.simulando = False
            self._registrar_evento("SYSTEM HALT: OPERACIÓN TOTAL COMPLETADA.")
            return

        t = self.celda_tam
        for plan in self.planes_activos:
            hist = plan["historial"]
            idx = min(self.paso_actual, len(hist) - 1)
            nx, ny = hist[idx]
            yp = self._y_pantalla(ny)
            x_px, y_px = nx * t, yp * t

            if (nx, ny) in self.info_nodos_acceso and (nx, ny) not in self.nodos_recogidos:
                self.nodos_recogidos.add((nx, ny))
                self.canvas.delete(f"prod_txt_{nx}_{ny}")
                for id_p, nom_p, cant_p, peso_p, ped_id in self.info_nodos_acceso[(nx, ny)]:
                    plan["peso_actual"] += peso_p
                    self._registrar_evento(f"[{plan['id_picker']}] +{cant_p} {nom_p} ({peso_p:.1f}k)")

            if idx < len(plan["eventos"]):
                ev = plan["eventos"][idx]
                if "Desvío" in ev or "Maniobra" in ev:
                    self._registrar_evento(f"🔀 [{plan['id_picker']}] {ev}")

            # Rastro Luminoso GPS
            of = t * 0.4
            self.canvas.create_rectangle(
                x_px + of, y_px + of, x_px + t - of, y_px + t - of,
                fill=plan["color"], outline="#00ffff", width=1.5, tags=f"rastro_{plan['id_picker']}"
            )

            # Actualizar Posición del Polígono AGV
            if plan["oval_id"]:
                pts = [
                    x_px + t*0.05, y_px + t*0.1,   
                    x_px + t*0.65, y_px + t*0.1,   
                    x_px + t*0.65, y_px + t*0.25,  
                    x_px + t*0.95, y_px + t*0.25,  
                    x_px + t*0.95, y_px + t*0.4,   
                    x_px + t*0.65, y_px + t*0.4,   
                    x_px + t*0.65, y_px + t*0.6,   
                    x_px + t*0.95, y_px + t*0.6,   
                    x_px + t*0.95, y_px + t*0.75,  
                    x_px + t*0.65, y_px + t*0.75,  
                    x_px + t*0.65, y_px + t*0.9,   
                    x_px + t*0.05, y_px + t*0.9    
                ]
                self.canvas.coords(plan["oval_id"], *pts)
                self.canvas.tag_raise(plan["oval_id"])
                
            if plan["txt_id"]:
                self.canvas.coords(plan["txt_id"], x_px + t*0.32, y_px + t*0.5)
                # Formato corto (e.g. "45k") para que entre perfecto
                self.canvas.itemconfig(plan["txt_id"], text=f"{plan['peso_actual']:.0f}k")
                self.canvas.tag_raise(plan["txt_id"])

        self.paso_actual += 1

        if self.simulando and not self.pausado:
            self.after(int(self.vel_simulacion * 1000), self.mover_picker)

    def cmd_iniciar(self):
        if not self.planes_activos:
            self.cmd_calcular_ruta()
        if self.planes_activos and not self.simulando:
            self.simulando = True
            self.pausado = False
            self.mover_picker()

    def cmd_pausar(self):
        self.pausado = True

    def cmd_continuar(self):
        if self.simulando and self.pausado:
            self.pausado = False
            self.mover_picker()

    def cmd_paso(self):
        if not self.planes_activos:
            self.cmd_calcular_ruta()
        if self.planes_activos:
            self.simulando = False
            self.mover_picker()

    def cmd_reiniciar(self):
        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        if len(self.planes_activos) > 1:
            self.cmd_calcular_multipicker()
        else:
            self.cmd_calcular_ruta()

    def cmd_cambiar_velocidad(self, val):
        self.vel_simulacion = float(val) / 1000.0

    def cmd_cambiar_zoom(self, val):
        nuevo_tam = int(float(val))
        if nuevo_tam != self.celda_tam:
            self.celda_tam = nuevo_tam
            self._actualizar_lienzo_completo()

    def cmd_comparar_estrategias(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return

        idx = max(0, self.cmb_waves.current())
        wave = self.waves[idx]

        res_a = Pathfinding.estrategia_a_orden_pedidos(self.warehouse, wave)
        res_b = Pathfinding.estrategia_b_cercania(self.warehouse, wave)
        res_c = Pathfinding.estrategia_c_pasillos(self.warehouse, wave)

        win = tk.Toplevel(self)
        win.title(f"📊 Benchmarking - {wave.id_wave}")
        win.geometry("760x280+250+200")
        win.configure(bg=self.BG_APP)

        cols = ("Estrategia", "Costo Total", "Pasos Planta", "Costo Z", "Nodos Visitados", "Operaciones", "Tiempo (ms)")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=105, anchor="center")

        for r in (res_a, res_b, res_c):
            tree.insert("", "end", values=(
                r['estrategia'], r['distancia'], r['aristas_recorridas'],
                r.get('costo_altura_z', 0), r['nodos_visitados'],
                r.get('operaciones', 0), f"{r['tiempo_ms']:.3f}"
            ))

        tree.pack(fill="both", expand=True, padx=10, pady=10)
        mejor = min([res_a, res_b, res_c], key=lambda x: (x['distancia'], x['tiempo_ms']))
        ttk.Label(
            win,
            text=f"🏆 Mejor Estrategia: {mejor['estrategia']} (Costo: {mejor['distancia']})",
            font=("Segoe UI", 11, "bold"), background=self.BG_APP, foreground=self.ACCENT_SEC
        ).pack(pady=8)

    def cmd_cargar_json(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar escenario JSON",
            filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        if not ruta:
            return
        try:
            self.warehouse = PersistenciaJSON.cargar_escenario(ruta)
            self.waves.clear()
            self.planes_activos.clear()
            self.cmb_waves.set("")
            self.cmb_waves['values'] = []
            self.celda_tam = self._calcular_zoom_optimo()
            self.scale_zoom.set(self.celda_tam)
            self._actualizar_lienzo_completo()
            self.lbl_metricas.config(
                text=f"LAYOUT LOADED: {self.warehouse.ancho_x}x{self.warehouse.largo_y}\n"
                     f"SKUs: {len(self.warehouse.productos)} | ORD: {len(self.warehouse.pedidos)}\n"
                     f"> READY."
            )
            self._registrar_evento(f"JSON IMPORTADO:\n{ruta}", limpiar=True)
        except Exception as e:
            messagebox.showerror("Error al cargar JSON", f"No se pudo cargar el escenario:\n{e}")

    def cmd_guardar_json(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar escenario JSON",
            defaultextension=".json",
            filetypes=[("Archivos JSON", "*.json")]
        )
        if not ruta:
            return
        try:
            PersistenciaJSON.guardar_escenario(self.warehouse, ruta)
            messagebox.showinfo("Exportación WMS", f"Escenario exportado exitosamente en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def cmd_ver_inventario(self):
        win = tk.Toplevel(self)
        win.title("📋 Inventario WMS y Órdenes")
        win.geometry("740x480+300+180")
        win.configure(bg=self.BG_APP)

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        tab_p = ttk.Frame(nb)
        nb.add(tab_p, text=f"Master SKUs ({len(self.warehouse.productos)})")
        cols_p = ("ID", "Nombre", "Rack", "Pos (x,y,z)", "Stock", "Peso (kg)")
        tree_p = ttk.Treeview(tab_p, columns=cols_p, show="headings")
        for col in cols_p:
            tree_p.heading(col, text=col)
            tree_p.column(col, width=110, anchor="center")
        for pr in self.warehouse.productos.valores():
            tree_p.insert("", "end", values=(pr.id_prod, pr.nombre, pr.rack_id, f"({pr.x},{pr.y},{pr.z})", pr.stock, pr.peso))
        
        scroll_p = ttk.Scrollbar(tab_p, orient="vertical", command=tree_p.yview)
        tree_p.configure(yscrollcommand=scroll_p.set)
        tree_p.pack(side="left", fill="both", expand=True)
        scroll_p.pack(side="right", fill="y")

        tab_o = ttk.Frame(nb)
        nb.add(tab_o, text=f"Órdenes ({len(self.warehouse.pedidos)})")
        cols_o = ("ID Pedido", "Prioridad", "Estado", "Unid. Totales", "Unid. Pendientes")
        tree_o = ttk.Treeview(tab_o, columns=cols_o, show="headings")
        for col in cols_o:
            tree_o.heading(col, text=col)
            tree_o.column(col, width=120, anchor="center")
        for ped in self.warehouse.pedidos.valores():
            tree_o.insert("", "end", values=(
                ped.id_pedido, ped.prioridad, ped.estado,
                ped.unidades_totales(), ped.unidades_pendientes()
            ))
            
        scroll_o = ttk.Scrollbar(tab_o, orient="vertical", command=tree_o.yview)
        tree_o.configure(yscrollcommand=scroll_o.set)
        tree_o.pack(side="left", fill="both", expand=True)
        scroll_o.pack(side="right", fill="y")

    def cmd_abrir_generador(self):
        if not self.funcion_generador:
            messagebox.showinfo("Aviso", "Generador automático no disponible.")
            return

        win = tk.Toplevel(self)
        win.title("⚙️ Generador Aleatorio WMS")
        win.geometry("380x320+350+220")
        win.configure(bg=self.BG_APP)

        campos = [
            ("Cantidad de Racks:", "4"),
            ("Largo de Racks (Celdas Y):", "8"),
            ("Cantidad de SKUs:", "30"),
            ("Cantidad de Pedidos:", "12"),
            ("Máx. Productos por Pedido:", "4"),
            ("Capacidad Wave (Máx. Pedidos):", "3")
        ]
        entradas = {}
        for i, (etiqueta, val_def) in enumerate(campos):
            ttk.Label(win, text=etiqueta, background=self.BG_APP, foreground=self.FG_TEXT).grid(row=i, column=0, padx=10, pady=6, sticky="w")
            ent = tk.Entry(
                win, width=14, 
                bg="#2f3640", fg="#f5f6fa", 
                insertbackground="white", 
                relief="solid", highlightthickness=1,
                highlightbackground="#718093", highlightcolor="#0097e6",
                font=("Consolas", 10, "bold")
            )
            ent.insert(0, val_def)
            ent.grid(row=i, column=1, padx=10, pady=6)
            entradas[etiqueta] = ent

        def confirmar():
            try:
                vals = [int(entradas[k].get()) for k, _ in campos]
                self.warehouse = self.funcion_generador(
                    num_racks=vals[0], largo_rack=vals[1], cant_productos=vals[2],
                    cant_pedidos=vals[3], max_prod_por_pedido=vals[4], cap_wave_pedidos=vals[5]
                )
                self.waves.clear()
                self.planes_activos.clear()
                self.celda_tam = self._calcular_zoom_optimo()
                self.scale_zoom.set(self.celda_tam)
                self._actualizar_lienzo_completo()
                self._registrar_evento("SYS: Entorno regenerado.", limpiar=True)
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Construir Centro de Distribución", command=confirmar, style="Success.TButton").grid(row=len(campos), column=0, columnspan=2, pady=18)