"""
Módulo de Simulación Interactiva Completa (WMS Dashboard)
Visualiza en tiempo real la preparación continua de Waves, el desplazamiento Multi-Picker por Zonas
y el descuento dinámico de capacidad en las Zonas de Despacho.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from algoritmos import WaveManager
from rutas import Pathfinding
from coordinador import CoordinadorMultiPicker
from persistencia import PersistenciaJSON
from generador import GeneradorWarehouse


class AppVisual(tk.Tk):
    def __init__(self, warehouse):
        super().__init__()
        self.title("WMS Dashboard - Simulador de Centro de Distribución por Zonas")
        self.warehouse = warehouse
        self.waves = []

        # Adaptar geometría inicial al área útil de la pantalla (respetando barra de tareas)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1380, max(1000, screen_w - 40))
        win_h = min(780, max(620, screen_h - 90))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h - 50) // 2)
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.minsize(960, 600)

        self.factor_zoom = 1.0  # 1.0 = 100% ajustado a todo el espacio disponible del lienzo
        self.celda_w = 32.0
        self.celda_h = 32.0
        self.celda_tam = 32.0
        self._ultimo_tam_canvas = (0, 0)

        self.simulando = False
        self.pausado = False
        self.vel_simulacion = 0.12
        self.paso_actual = 0

        self.planes_activos = []
        self.metricas_actuales = {}
        self.modo_continuo = True
        self.waves_completadas = set()
        self.historial_log = []
        self._config_plan_actual = None

        # Capacidad disponible en tiempo real de cada Zona de Despacho
        self.cap_zonas_actual = {
            z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho
        }
        self.cap_zonas_por_paso = [dict(self.cap_zonas_actual)]
        self.txt_zonas_canvas = {}
        self.rect_zonas_canvas = {}

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        self._configurar_estilos()
        self._construir_ui()

        estado_guardado = getattr(self.warehouse, "estado_simulacion_guardado", None)
        if estado_guardado:
            self._restaurar_estado_simulacion(estado_guardado)
        else:
            self._mostrar_resumen_inicial()
        self.after(50, self._ajustar_y_redibujar)

    def _configurar_estilos(self):
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

        self.option_add("*TCombobox*Listbox.background", self.BG_PANEL)
        self.option_add("*TCombobox*Listbox.foreground", self.FG_TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", self.ACCENT_PRI)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

        style.configure(".", background=self.BG_APP, foreground=self.FG_TEXT, font=("Segoe UI", 9))
        style.configure("TFrame", background=self.BG_APP)

        style.configure("TLabelframe", background=self.BG_APP, foreground="#00a8ff", borderwidth=1, font=("Segoe UI", 9, "bold"))
        style.configure("TLabelframe.Label", background=self.BG_APP, foreground="#00a8ff")

        style.configure("TButton", padding=(6, 4), relief="flat", background=self.BG_BTN, foreground="white", font=("Segoe UI", 9, "bold"))
        style.map("TButton", background=[("active", "#dcdde1")], foreground=[("active", "black")])

        style.configure("Primary.TButton", background=self.ACCENT_PRI)
        style.map("Primary.TButton", background=[("active", "#00a8ff")])

        style.configure("Success.TButton", background=self.ACCENT_SEC)
        style.map("Success.TButton", background=[("active", "#4cd137")])

        style.configure("TCombobox", fieldbackground=self.BG_PANEL, background=self.BG_BTN, foreground="white", arrowcolor="white")
        style.map("TCombobox",
                  fieldbackground=[("readonly", self.BG_PANEL)],
                  selectbackground=[("readonly", self.ACCENT_PRI), ("focus", self.ACCENT_PRI)],
                  selectforeground=[("readonly", "white"), ("focus", "white")])

        style.configure("TScale", background=self.BG_APP, troughcolor=self.BG_PANEL)
        style.configure("Horizontal.TScrollbar", background=self.BG_PANEL, troughcolor=self.BG_APP)
        style.configure("Vertical.TScrollbar", background=self.BG_PANEL, troughcolor=self.BG_APP)

        style.configure("Treeview", background=self.BG_PANEL, foreground=self.FG_TEXT, fieldbackground=self.BG_PANEL, rowheight=25, borderwidth=0)
        style.map("Treeview", background=[("selected", self.ACCENT_PRI)], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=self.BG_BTN, foreground="white", font=("Segoe UI", 9, "bold"), borderwidth=1)

        style.configure("TNotebook", background=self.BG_APP)
        style.configure("TNotebook.Tab", background=self.BG_PANEL, foreground=self.FG_TEXT, padding=(12, 5))
        style.map("TNotebook.Tab", background=[("selected", self.ACCENT_PRI)])

    def _recalcular_dimensiones_celda(self):
        """
        Calcula el ancho y alto de cada celda para que al 100% de zoom el Warehouse
        ocupe la totalidad del espacio disponible del lienzo sin dejar bordes vacíos.
        """
        disp_w = max(320, self.canvas.winfo_width() - 4)
        disp_h = max(260, self.canvas.winfo_height() - 4)

        base_w = disp_w / max(1, self.warehouse.ancho_x)
        base_h = disp_h / max(1, self.warehouse.largo_y)

        self.celda_w = base_w * self.factor_zoom
        self.celda_h = base_h * self.factor_zoom
        self.celda_tam = min(self.celda_w, self.celda_h)

    def _al_redimensionar_canvas(self, event):
        nuevo_tam = (event.width, event.height)
        if abs(nuevo_tam[0] - self._ultimo_tam_canvas[0]) > 2 or abs(nuevo_tam[1] - self._ultimo_tam_canvas[1]) > 2:
            self._ultimo_tam_canvas = nuevo_tam
            self._ajustar_y_redibujar()

    def _ajustar_y_redibujar(self):
        self._recalcular_dimensiones_celda()
        self._actualizar_lienzo_completo()
        if self.planes_activos:
            paso_vis = max(0, self.paso_actual - 1)
            self._posicionar_pickers_iniciales()
            self._redibujar_rastros_hasta(paso_vis)
            self._renderizar_estado_paso(paso_vis, registrar_log=False)

    def _y_pantalla(self, y_modelo):
        return (self.warehouse.largo_y - 1) - y_modelo

    def _formatear_kg(self, valor):
        return f"{valor:.0f}" if abs(valor - round(valor)) < 0.05 else f"{valor:.1f}"

    def _texto_badge_zona(self, zona):
        disp = self.cap_zonas_actual.get(zona.id_zona, zona.peso_max_kg)
        return f"{zona.id_zona}\nDISP: {self._formatear_kg(disp)}/{zona.peso_max_kg:.0f}KG"

    def _construir_ui(self):
        # Panel Izquierdo compacto y adaptable para que nunca quede tapado por la barra de tareas
        frame_izq = ttk.Frame(self, padding=(10, 6, 8, 10))
        frame_izq.grid(row=0, column=0, sticky="nsew")
        frame_izq.columnconfigure(0, weight=1)
        frame_izq.rowconfigure(4, weight=1)  # El Log de Eventos se adapta dinámicamente a la altura de la pantalla

        # 1. Gestión de Escenario y Guardado de Simulación
        lf_gestion = ttk.LabelFrame(frame_izq, text=" 📁 Configuración CD ", padding=5)
        lf_gestion.grid(row=0, column=0, sticky="ew", pady=(0, 3))

        btn_frame_arch = ttk.Frame(lf_gestion)
        btn_frame_arch.pack(fill="x", pady=1)
        ttk.Button(btn_frame_arch, text="📂 Cargar Simulación", command=self.cmd_cargar_json).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame_arch, text="💾 Guardar Simulación", command=self.cmd_guardar_json).pack(side="left", expand=True, fill="x", padx=2)

        ttk.Button(
            lf_gestion,
            text="⚙️ Generar Warehouse Automático",
            command=self.cmd_generar_warehouse_auto,
            style="Success.TButton"
        ).pack(fill="x", padx=2, pady=(2, 1))

        ttk.Button(
            lf_gestion,
            text="📋 Stock & Waves (Pedidos, Zonas y Sublistas)",
            command=self.cmd_ver_inventario,
            style="Primary.TButton"
        ).pack(fill="x", padx=2, pady=(2, 1))

        # 2. Planificación y Estrategias
        lf_plan = ttk.LabelFrame(frame_izq, text=" ⚙️ Motor de WMS ", padding=5)
        lf_plan.grid(row=1, column=0, sticky="ew", pady=3)

        ttk.Button(
            lf_plan,
            text="1. Consolidar Waves (Por Zonas)",
            command=self.cmd_generar_waves,
            style="Primary.TButton"
        ).pack(fill="x", pady=1)

        ttk.Label(lf_plan, text="Algoritmo de Ruta:").pack(anchor="w", pady=(2, 1))
        self.cmb_estrategia = ttk.Combobox(
            lf_plan,
            values=[
                "Estrategia A - Orden de los Pedidos",
                "Estrategia B - Cercanía 3D (Greedy)",
                "Estrategia C - Barrido de Pasillos"
            ],
            state="readonly",
            width=36
        )
        self.cmb_estrategia.set("Estrategia B - Cercanía 3D (Greedy)")
        self.cmb_estrategia.pack(fill="x", pady=1)
        self.cmb_estrategia.bind("<<ComboboxSelected>>", self._al_cambiar_config_motor)

        self.var_ayuda_zonas = tk.BooleanVar(value=False)
        self.chk_ayuda_zonas = tk.Checkbutton(
            lf_plan,
            text="🤝 Ayudar en otras zonas al finalizar la propia",
            variable=self.var_ayuda_zonas,
            command=self._al_cambiar_config_motor,
            bg=self.BG_APP, fg="#55efc4", selectcolor=self.BG_PANEL,
            activebackground=self.BG_APP, activeforeground="#55efc4",
            font=("Segoe UI", 8, "bold"), anchor="w"
        )
        self.chk_ayuda_zonas.pack(fill="x", pady=(2, 2))

        ttk.Button(
            lf_plan,
            text="2. Despachar Flota (Operación Total)",
            command=self.cmd_calcular_operacion_completa,
            style="Primary.TButton"
        ).pack(fill="x", pady=1)

        ttk.Button(
            lf_plan,
            text="📊 Benchmarking de Algoritmos",
            command=self.cmd_comparar_estrategias
        ).pack(fill="x", pady=1)

        frame_insp = ttk.Frame(lf_plan)
        frame_insp.pack(fill="x", pady=(3, 0))
        self.cmb_waves = ttk.Combobox(frame_insp, state="readonly", width=22)
        self.cmb_waves.pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(frame_insp, text="🔍 Aislar Wave", command=self.cmd_calcular_ruta_individual).pack(side="right")

        # 3. Controles de Reproducción
        lf_ctrl = ttk.LabelFrame(frame_izq, text=" 🎮 Controles ", padding=5)
        lf_ctrl.grid(row=2, column=0, sticky="ew", pady=3)

        frame_sim = ttk.Frame(lf_ctrl)
        frame_sim.pack(fill="x")
        ttk.Button(frame_sim, text="▶ Iniciar", command=self.cmd_iniciar, style="Success.TButton").grid(row=0, column=0, sticky="ew", padx=2, pady=1)
        ttk.Button(frame_sim, text="⏸ Pausar", command=self.cmd_pausar).grid(row=0, column=1, sticky="ew", padx=2, pady=1)
        ttk.Button(frame_sim, text="⏯ Continuar", command=self.cmd_continuar, style="Success.TButton").grid(row=1, column=0, sticky="ew", padx=2, pady=1)
        ttk.Button(frame_sim, text="⏭ Paso a Paso", command=self.cmd_paso).grid(row=1, column=1, sticky="ew", padx=2, pady=1)
        frame_sim.columnconfigure(0, weight=1)
        frame_sim.columnconfigure(1, weight=1)

        ttk.Button(lf_ctrl, text="🔄 Resetear Telemetría", command=self.cmd_reiniciar).pack(fill="x", pady=2)

        frame_sliders = ttk.Frame(lf_ctrl)
        frame_sliders.pack(fill="x", pady=1)
        ttk.Label(frame_sliders, text="Velocidad (ms):").grid(row=0, column=0, sticky="w")
        self.scale_vel = ttk.Scale(frame_sliders, from_=20, to=700, orient="horizontal", command=self.cmd_cambiar_velocidad)
        self.scale_vel.set(120)
        self.scale_vel.grid(row=0, column=1, sticky="ew", padx=6)

        self.lbl_zoom = ttk.Label(frame_sliders, text="Zoom (100%):")
        self.lbl_zoom.grid(row=1, column=0, sticky="w")
        self.scale_zoom = ttk.Scale(frame_sliders, from_=100, to=250, orient="horizontal", command=self.cmd_cambiar_zoom)
        self.scale_zoom.set(100)
        self.scale_zoom.grid(row=1, column=1, sticky="ew", padx=6)
        frame_sliders.columnconfigure(1, weight=1)

        # 4. Handheld WMS: Monitor
        lf_monitor = ttk.LabelFrame(frame_izq, text=" 📡 Handheld WMS: Monitor ", padding=4)
        lf_monitor.grid(row=3, column=0, sticky="ew", pady=3)
        self.txt_monitor = tk.Text(
            lf_monitor, height=5, width=42, font=("Consolas", 8, "bold"),
            bg="#0b0f14", fg="#39ff14", state="disabled", relief="sunken", padx=6, pady=4,
            insertbackground="white", highlightthickness=1, highlightbackground="#353b48"
        )
        self.txt_monitor.pack(fill="x")

        # 5. Handheld WMS: Log Eventos (Se adapta al alto restante de la ventana sin cortarse)
        lf_eventos = ttk.LabelFrame(frame_izq, text=" 📝 Handheld WMS: Log Eventos ", padding=4)
        lf_eventos.grid(row=4, column=0, sticky="nsew", pady=(3, 4))
        lf_eventos.rowconfigure(0, weight=1)
        lf_eventos.columnconfigure(0, weight=1)

        self.txt_eventos = tk.Text(
            lf_eventos, height=5, width=42, font=("Consolas", 9),
            bg="#0b0f14", fg="#dfe6e9", state="disabled", relief="sunken",
            padx=6, pady=4, wrap="word", spacing1=2, spacing2=1, spacing3=2,
            insertbackground="white", highlightthickness=1, highlightbackground="#353b48"
        )
        scroll_log = ttk.Scrollbar(lf_eventos, orient="vertical", command=self.txt_eventos.yview)
        self.txt_eventos.configure(yscrollcommand=scroll_log.set)

        self.txt_eventos.grid(row=0, column=0, sticky="nsew")
        scroll_log.grid(row=0, column=1, sticky="ns")

        # Etiquetas de colores para lectura clara del Log de Eventos
        self.txt_eventos.tag_config("titulo", foreground="#00d2d3", font=("Consolas", 9, "bold"))
        self.txt_eventos.tag_config("subtitulo", foreground="#74b9ff", font=("Consolas", 9, "bold"))
        self.txt_eventos.tag_config("zona", foreground="#a29bfe", font=("Consolas", 9))
        self.txt_eventos.tag_config("item", foreground="#dfe6e9", font=("Consolas", 9))
        self.txt_eventos.tag_config("paso", foreground="#81ecec", font=("Consolas", 9, "bold"))
        self.txt_eventos.tag_config("pick", foreground="#55efc4", font=("Consolas", 9))
        self.txt_eventos.tag_config("entrega", foreground="#ffeaa7", font=("Consolas", 9, "bold"))
        self.txt_eventos.tag_config("desvio", foreground="#fab1a0", font=("Consolas", 9))
        self.txt_eventos.tag_config("ayuda", foreground="#fd79a8", font=("Consolas", 9, "bold"))
        self.txt_eventos.tag_config("exito", foreground="#00b894", font=("Consolas", 9, "bold"))

        # Panel Derecho: Canvas que ocupa todo el espacio disponible de la ventana
        frame_der = ttk.Frame(self)
        frame_der.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(8, 12))
        frame_der.rowconfigure(0, weight=1)
        frame_der.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(frame_der, bg="#111418", highlightthickness=2, highlightbackground="#7f8fa6")
        scroll_y = ttk.Scrollbar(frame_der, orient="vertical", command=self.canvas.yview)
        scroll_x = ttk.Scrollbar(frame_der, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.canvas.bind("<Configure>", self._al_redimensionar_canvas)

    def _resetear_capacidades_zonas(self):
        self.cap_zonas_actual = {
            z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho
        }
        self._actualizar_etiquetas_zonas_canvas()

    def _actualizar_etiquetas_zonas_canvas(self):
        for zona in self.warehouse.zonas_despacho:
            txt_id = self.txt_zonas_canvas.get(zona.id_zona)
            rect_id = self.rect_zonas_canvas.get(zona.id_zona)
            if txt_id:
                disp = self.cap_zonas_actual.get(zona.id_zona, zona.peso_max_kg)
                descargado = disp < zona.peso_max_kg - 1e-3
                color_txt = "#55efc4" if descargado else "#f1c40f"
                self.canvas.itemconfig(txt_id, text=self._texto_badge_zona(zona), fill=color_txt)
                if rect_id:
                    self.canvas.itemconfig(rect_id, outline=color_txt)

    def _resumen_docks_texto(self):
        partes = []
        for z in self.warehouse.zonas_despacho:
            disp = self.cap_zonas_actual.get(z.id_zona, z.peso_max_kg)
            partes.append(f"{z.id_zona}: {self._formatear_kg(disp)}/{z.peso_max_kg:.0f}kg")
        return " | ".join(partes) if partes else "N/A"

    def _mostrar_resumen_inicial(self):
        self._resetear_capacidades_zonas()
        zonas = WaveManager.obtener_zonas_pickers(self.warehouse)
        lineas_z = [f"• {z['picker_id']}: {z['nombre_zona']} ({z['rango_x']})" for z in zonas]

        self._actualizar_monitor_texto(
            f"LAYOUT: {self.warehouse.ancho_x}x{self.warehouse.largo_y} | "
            f"SKUs: {len(self.warehouse.productos)} | PEDIDOS: {len(self.warehouse.pedidos)}\n"
            f"DOCKS DISP: {self._resumen_docks_texto()}\n" +
            "\n".join(lineas_z) +
            "\n> Pulse '1. Consolidar Waves' o 'Stock & Waves'."
        )

        self._limpiar_eventos()
        self._agregar_linea_log("━━━ ZONIFICACIÓN DEL WAREHOUSE ━━━", "titulo")
        for z in zonas:
            racks_str = ", ".join(z["racks"]) if z["racks"] else "Sin racks"
            self._agregar_linea_log(f"▸ {z['picker_id']} ➔ {z['nombre_zona']}", "subtitulo")
            self._agregar_linea_log(f"  Sector {z['rango_x']} │ Racks: {racks_str}", "zona")

        if hasattr(self.warehouse, "validar_escenario"):
            es_valido, errores, checks_ok = self.warehouse.validar_escenario()
            self._agregar_linea_log("━━━ VALIDACIÓN DEL ESCENARIO ━━━", "titulo")
            for chk in checks_ok:
                self._agregar_linea_log(f"  {chk}", "pick")
            for err in errores:
                self._agregar_linea_log(f"  ✖ {err}", "desvio")

    def _actualizar_monitor_texto(self, texto):
        self.txt_monitor.configure(state="normal")
        self.txt_monitor.delete("1.0", tk.END)
        self.txt_monitor.insert(tk.END, texto)
        self.txt_monitor.configure(state="disabled")

    def _limpiar_eventos(self):
        self.historial_log.clear()
        self.txt_eventos.configure(state="normal")
        self.txt_eventos.delete("1.0", tk.END)
        self.txt_eventos.configure(state="disabled")

    def _agregar_linea_log(self, texto, tag="item", guardar_historial=True):
        if guardar_historial:
            self.historial_log.append([texto, tag])
        self.txt_eventos.configure(state="normal")
        self.txt_eventos.insert(tk.END, texto + "\n", tag)
        self.txt_eventos.see(tk.END)
        self.txt_eventos.configure(state="disabled")

    def _registrar_evento_simulacion(self, paso_idx, pk_id, sector_corto, ev):
        """Formatea de manera limpia y desglosada cada evento ocurrido en un paso."""
        partes = [p.strip() for p in ev.split("|") if p.strip()]
        if not partes:
            return

        self._agregar_linea_log(f"⏱ Paso {paso_idx:02d} │ {pk_id} [{sector_corto}]", "paso")
        for p in partes:
            if "🛒" in p:
                items_txt = p.replace("🛒", "").strip().split(";")
                for it_str in items_txt:
                    self._agregar_linea_log(f"   ✔ Recoge: {it_str.strip()}", "pick")
            elif "🤝" in p:
                self._agregar_linea_log(f"   {p}", "ayuda")
            elif "📦" in p:
                self._agregar_linea_log(f"   {p}", "entrega")
            elif "🔀" in p:
                self._agregar_linea_log(f"   {p}", "desvio")
            elif "Inicia" in p:
                self._agregar_linea_log(f"   ▶ {p}", "subtitulo")
            else:
                self._agregar_linea_log(f"   • {p}", "item")

    def _actualizar_lienzo_completo(self):
        ancho_px = self.warehouse.ancho_x * self.celda_w
        alto_px = self.warehouse.largo_y * self.celda_h
        self.canvas.config(scrollregion=(0, 0, ancho_px, alto_px))
        self._dibujar_warehouse()

    def _dibujar_warehouse(self):
        self.canvas.delete("all")
        self.txt_zonas_canvas.clear()
        self.rect_zonas_canvas.clear()

        tw = self.celda_w
        th = self.celda_h
        t = self.celda_tam
        simbolos = {"N": "↑", "S": "↓", "E": "→", "O": "←", "AMBOS": "·"}

        for x in range(self.warehouse.ancho_x):
            for y in range(self.warehouse.largo_y):
                yp = self._y_pantalla(y)
                x1, y1 = x * tw, yp * th
                x2, y2 = x1 + tw, y1 + th
                tipo = self.warehouse.grilla_tipo.get((x, y), "PASILLO")
                sentido = self.warehouse.grilla_sentido.get((x, y), "AMBOS")

                if tipo == "PASILLO":
                    color_piso = "#576574" if sentido == "AMBOS" else "#485460"
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill=color_piso, outline="")

                    if sentido != "AMBOS":
                        if sentido in ("N", "S"):
                            dash_v = (max(2, int(th / 3)), max(2, int(th / 3)))
                            self.canvas.create_line(x1 + 1, y1, x1 + 1, y2, fill="#f1c40f", dash=dash_v)
                            self.canvas.create_line(x2 - 1, y1, x2 - 1, y2, fill="#f1c40f", dash=dash_v)
                        elif sentido in ("E", "O"):
                            dash_h = (max(2, int(tw / 3)), max(2, int(tw / 3)))
                            self.canvas.create_line(x1, y1 + 1, x2, y1 + 1, fill="#f1c40f", dash=dash_h)
                            self.canvas.create_line(x1, y2 - 1, x2, y2 - 1, fill="#f1c40f", dash=dash_h)
                        if t >= 7:
                            self.canvas.create_text(
                                x1 + tw / 2, y1 + th / 2, text=simbolos.get(sentido, "·"),
                                fill="#d1ccc0", font=("Arial", max(7, int(t * 0.42)), "bold")
                            )

        for zona in self.warehouse.zonas_despacho:
            zx1 = zona.x * tw
            zy1 = self._y_pantalla(zona.y + zona.alto - 1) * th
            zx2 = (zona.x + zona.ancho) * tw
            zy2 = (self._y_pantalla(zona.y) + 1) * th
            self.canvas.create_rectangle(zx1, zy1, zx2, zy2, fill="#222f3e", outline="#f1c40f", width=2)

            cx = (zona.x + zona.ancho / 2) * tw
            cy = (self._y_pantalla(zona.y + zona.alto - 1) + zona.alto / 2) * th
            ancho_badge = min(zona.ancho * tw * 0.46, max(tw * 1.4, 58))
            alto_badge = min(zona.alto * th * 0.44, max(th * 0.62, 20))

            disp = self.cap_zonas_actual.get(zona.id_zona, zona.peso_max_kg)
            color_z_txt = "#55efc4" if disp < zona.peso_max_kg - 1e-3 else "#f1c40f"

            rect_id = self.canvas.create_rectangle(
                cx - ancho_badge, cy - alto_badge, cx + ancho_badge, cy + alto_badge,
                fill="#0b0f14", outline=color_z_txt, width=1.5
            )
            txt_id = self.canvas.create_text(
                cx, cy, text=self._texto_badge_zona(zona),
                fill=color_z_txt, font=("Consolas", max(7, int(t * 0.24)), "bold"), justify="center"
            )
            self.rect_zonas_canvas[zona.id_zona] = rect_id
            self.txt_zonas_canvas[zona.id_zona] = txt_id

            ax, ay = Pathfinding.obtener_acceso_zona(self.warehouse, zona)
            ayp = self._y_pantalla(ay)
            self.canvas.create_rectangle(
                ax * tw + 2, ayp * th + 2, (ax + 1) * tw - 2, (ayp + 1) * th - 2,
                outline="#00ff00", width=2, dash=(2, 2)
            )

        for rack in self.warehouse.racks:
            for rx, ry in rack.celdas():
                yp = self._y_pantalla(ry)
                rx1, ry1 = rx * tw, yp * th
                rx2, ry2 = rx1 + tw, ry1 + th
                self.canvas.create_rectangle(rx1, ry1, rx2, ry2, fill="#2d3436", outline="#7f8fa6", width=2)
                self.canvas.create_line(rx1 + 2, ry1 + 2, rx2 - 2, ry2 - 2, fill="#636e72", width=1)
                self.canvas.create_line(rx1 + 2, ry2 - 2, rx2 - 2, ry1 + 2, fill="#636e72", width=1)

            if t >= 12:
                cx = (rack.x + rack.ancho / 2) * tw
                cy = (self._y_pantalla(rack.y + rack.alto - 1) + rack.alto / 2) * th
                self.canvas.create_rectangle(cx - tw * 0.75, cy - th * 0.38, cx + tw * 0.75, cy + th * 0.38, fill="#b2bec3")
                self.canvas.create_text(cx, cy, text=rack.id_rack, fill="#2d3436", font=("Segoe UI", max(7, int(t * 0.34)), "bold"))

        for puerta in self.warehouse.puertas:
            yp = self._y_pantalla(puerta.y)
            px1, py1 = puerta.x * tw, yp * th
            px2, py2 = px1 + tw, py1 + th
            color_puerta = "#ff4757" if puerta.tipo == "OUTBOUND" else ("#2ed573" if puerta.tipo == "INBOUND" else "#1e90ff")
            self.canvas.create_rectangle(px1, py1, px2, py2, fill="#2f3542", outline=color_puerta, width=2)
            lbl = "OUT" if puerta.tipo == "OUTBOUND" else ("IN" if puerta.tipo == "INBOUND" else "MIX")
            self.canvas.create_rectangle(px1 + 2, py1 + th / 2 - 6, px2 - 2, py1 + th / 2 + 6, fill=color_puerta, outline="")
            self.canvas.create_text(px1 + tw / 2, py1 + th / 2, text=lbl, fill="white", font=("Segoe UI", max(6, int(t * 0.25)), "bold"))

        # Dibujar división visual de Zonas de Pickers en el Warehouse
        zonas_pk = WaveManager.obtener_zonas_pickers(self.warehouse)
        if len(zonas_pk) > 1:
            colores_zona = ["#00a8ff", "#9c88ff", "#e84118", "#44bd32", "#fbc531", "#e1b12c"]
            alto_total_px = self.warehouse.largo_y * th
            for idx, z in enumerate(zonas_pk):
                color_z = colores_zona[idx % len(colores_zona)]
                if idx < len(zonas_pk) - 1:
                    x_div = (z["x_max"] + 1) * tw
                    self.canvas.create_line(
                        x_div, 0, x_div, alto_total_px,
                        fill="#00d2d3", width=2, dash=(6, 4)
                    )
                if t >= 12:
                    cx_z = ((z["x_min"] + z["x_max"] + 1) / 2) * tw
                    etiqueta_z = f"{z['picker_id']} • {z['nombre_zona']} ({z['rango_x']})"
                    ancho_lbl = min((z["x_max"] - z["x_min"] + 1) * tw * 0.45, max(tw * 2.4, 95))
                    self.canvas.create_rectangle(
                        cx_z - ancho_lbl, 3, cx_z + ancho_lbl, 21,
                        fill="#111418", outline=color_z, width=1
                    )
                    self.canvas.create_text(
                        cx_z, 12, text=etiqueta_z,
                        fill=color_z, font=("Segoe UI", 8, "bold")
                    )

    def _obtener_funcion_estrategia(self):
        est = self.cmb_estrategia.get()
        if "A" in est:
            return Pathfinding.estrategia_a_orden_pedidos
        if "C" in est:
            return Pathfinding.estrategia_c_pasillos
        return Pathfinding.estrategia_b_cercania

    def _actualizar_estados_pedidos_simulacion(self, waves_en_prep, waves_terminadas):
        waves_por_pedido = {}
        for w in self.waves:
            for pid in w.pedidos_involucrados:
                waves_por_pedido.setdefault(pid, set()).add(w.id_wave)

        for ped in self.warehouse.pedidos.valores():
            w_ped = waves_por_pedido.get(ped.id_pedido, set())
            if not w_ped:
                ped.estado = "PENDIENTE"
            elif w_ped.issubset(waves_terminadas):
                ped.estado = "PREPARADO"
            elif w_ped & waves_terminadas:
                ped.estado = "PARCIAL"
            elif w_ped & waves_en_prep:
                ped.estado = "EN_PREPARACION"
            else:
                ped.estado = "EN_WAVE"

    def cmd_generar_waves(self):
        pedidos = self.warehouse.pedidos.valores()
        if not pedidos:
            messagebox.showwarning("Atención", "No hay pedidos cargados en el escenario.")
            return

        self.waves = WaveManager.generar_waves(pedidos, self.warehouse)
        self.waves_completadas.clear()
        self._resetear_capacidades_zonas()
        self.cmb_waves['values'] = [
            f"{w.id_wave} ({w.total_unidades}u | {w.peso_total:.0f}kg | {w.picker_id})"
            for w in self.waves
        ]

        zonas = WaveManager.obtener_zonas_pickers(self.warehouse)
        mapa_zonas = {z["picker_id"]: z for z in zonas}

        if self.waves:
            self.cmb_waves.current(0)
            self._limpiar_eventos()
            self._agregar_linea_log(f"━━━ WAVES CONSOLIDADAS ({len(self.waves)}) ━━━", "titulo")

            for w in self.waves:
                peds_str = ", ".join(w.pedidos_involucrados)
                self._agregar_linea_log(
                    f"▸ {w.id_wave} │ {w.total_unidades} u. │ {w.peso_total:.1f} kg │ Pedidos: {peds_str}",
                    "subtitulo"
                )
                for pk_id, lineas_pk in w.sublistas_pickers.items():
                    z_info = mapa_zonas.get(pk_id, {})
                    nom_z = z_info.get("sector_corto", "Zona")
                    unid_pk = sum(l.cantidad for l in lineas_pk)
                    peso_pk = sum(l.peso_total for l in lineas_pk)
                    self._agregar_linea_log(
                        f"  [{pk_id} - {nom_z}] Sublista ({unid_pk} u. | {peso_pk:.1f} kg):",
                        "zona"
                    )
                    for l in lineas_pk:
                        pr = self.warehouse.productos.obtener(l.producto_id)
                        nom_pr = pr.nombre if pr else l.producto_id
                        self._agregar_linea_log(
                            f"    • {l.cantidad}x {nom_pr} ({l.producto_id}) ➔ {l.pedido_id}",
                            "item"
                        )

            self._actualizar_monitor_texto(
                f"WAVES GENERADAS: {len(self.waves)} (Zonificación Activa)\n"
                f"DOCKS DISP: {self._resumen_docks_texto()}\n"
                f"PICKERS EN ZONA: {len(zonas)}\n"
                f"> LISTO. Pulse 'Iniciar' o 'Despachar Flota'."
            )

    def _al_cambiar_config_motor(self, _event=None):
        """
        Si ya hay un plan preparado en el paso inicial y el usuario cambia la estrategia
        o activa/desactiva la ayuda entre zonas, recalcula el plan automáticamente.
        """
        if self.planes_activos and not self.simulando and self.paso_actual == 0:
            if self.modo_continuo:
                self.cmd_calcular_operacion_completa()
            else:
                self.cmd_calcular_ruta_individual()

    def _preparar_planes_simulacion(self, waves_objetivo, modo_continuo, titulo_log):
        fn_est = self._obtener_funcion_estrategia()
        ayuda_activa = bool(self.var_ayuda_zonas.get())
        self._config_plan_actual = (self.cmb_estrategia.get(), ayuda_activa)

        sim = CoordinadorMultiPicker.planificar_simulacion_continua(
            self.warehouse,
            waves_objetivo,
            fn_est,
            permitir_ayuda_zonas=ayuda_activa
        )
        planes_coord = sim["planes"]
        self.metricas_actuales = sim["metricas"]
        self.cap_zonas_por_paso = sim.get("cap_zonas_por_paso", [
            {z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho}
        ])

        if not planes_coord:
            messagebox.showwarning("Atención", "No se pudieron planificar rutas para la flota.")
            return

        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        self.modo_continuo = modo_continuo
        self.waves_completadas.clear()
        self._resetear_capacidades_zonas()

        self._dibujar_warehouse()

        colores_pk = ["#00a8ff", "#9c88ff", "#e84118", "#44bd32", "#fbc531", "#e1b12c"]
        self.planes_activos = []

        for i, p in enumerate(planes_coord):
            pk = p["picker"]
            z_info = p.get("zona_info", {})
            self.planes_activos.append({
                "id_picker": pk.id_picker,
                "sector_corto": z_info.get("sector_corto", "Zona"),
                "cap_kg": pk.capacidad_carga_kg,
                "color": colores_pk[i % len(colores_pk)],
                "historial": p["historial"],
                "estados_paso": p["estados_paso"],
                "desvios": p["desvios"],
                "oval_id": None,
                "txt_id": None
            })

        m = self.metricas_actuales
        modo_z_txt = "HABILITADA (Respeta Estrategia)" if ayuda_activa else "DESHABILITADA (Zona Estricta)"
        self._limpiar_eventos()
        self._agregar_linea_log(f"━━━ {titulo_log} ━━━", "titulo")
        self._agregar_linea_log(
            f"• Distancia Total: {m.get('distancia_total_flota', 0)} │ Pasos: {m.get('pasos_planta_flota', 0)}",
            "item"
        )
        self._agregar_linea_log(
            f"• Nodos: {m.get('nodos_visitados', 0)} │ CPU: {m.get('tiempo_ms', 0.0):.2f} ms",
            "zona"
        )
        self._agregar_linea_log(
            f"• Ayuda Inter-Zona: {modo_z_txt}",
            "ayuda" if ayuda_activa else "zona"
        )
        self._agregar_linea_log("━━━ REGISTRO DE EVENTOS ━━━", "titulo")

        self._posicionar_pickers_iniciales()
        self._renderizar_estado_paso(0, registrar_log=False)

    def cmd_calcular_operacion_completa(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return
        self._preparar_planes_simulacion(
            self.waves,
            modo_continuo=True,
            titulo_log=f"OPERACIÓN FLOTA ({len(self.waves)} Wave(s))"
        )

    def cmd_calcular_ruta_individual(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return
        idx = max(0, self.cmb_waves.current())
        wave_elegida = self.waves[idx]
        self._preparar_planes_simulacion(
            [wave_elegida],
            modo_continuo=False,
            titulo_log=f"WAVE AISLADA: {wave_elegida.id_wave}"
        )

    def _coords_poligono_agv(self, x_px, y_px, tw, th):
        return [
            x_px + tw * 0.1, y_px + th * 0.2,
            x_px + tw * 0.7, y_px + th * 0.2,
            x_px + tw * 0.7, y_px + th * 0.3,
            x_px + tw * 1.0, y_px + th * 0.3,
            x_px + tw * 1.0, y_px + th * 0.4,
            x_px + tw * 0.7, y_px + th * 0.4,
            x_px + tw * 0.7, y_px + th * 0.6,
            x_px + tw * 1.0, y_px + th * 0.6,
            x_px + tw * 1.0, y_px + th * 0.7,
            x_px + tw * 0.7, y_px + th * 0.7,
            x_px + tw * 0.7, y_px + th * 0.8,
            x_px + tw * 0.1, y_px + th * 0.8
        ]

    def _posicionar_pickers_iniciales(self):
        tw, th, t = self.celda_w, self.celda_h, self.celda_tam
        for plan in self.planes_activos:
            if plan["historial"]:
                ix, iy = plan["historial"][0]
                yp = self._y_pantalla(iy)
                x_px, y_px = ix * tw, yp * th

                plan["oval_id"] = self.canvas.create_polygon(
                    *self._coords_poligono_agv(x_px, y_px, tw, th),
                    fill=plan["color"], outline="#ffffff", width=1.5
                )
                plan["txt_id"] = self.canvas.create_text(
                    x_px + tw * 0.4, y_px + th * 0.5, text=f"P{plan['id_picker'][-1]}",
                    fill="white", font=("Segoe UI", max(7, int(t * 0.28)), "bold")
                )

    def _redibujar_rastros_hasta(self, paso_limite):
        tw, th = self.celda_w, self.celda_h
        ofx, ofy = tw * 0.38, th * 0.38
        for plan in self.planes_activos:
            pk_id = plan["id_picker"]
            self.canvas.delete(f"rastro_{pk_id}")
            hist = plan["historial"]
            estados = plan["estados_paso"]
            if not hist or not estados:
                continue
            tope = min(paso_limite, len(hist) - 1, len(estados) - 1)
            inicio_tramo = 0
            for s in range(1, tope + 1):
                if estados[s].get("limpiar_rastro"):
                    inicio_tramo = s
            for s in range(inicio_tramo, tope + 1):
                if estados[s].get("wave_madre") is not None:
                    nx, ny = hist[s]
                    yp = self._y_pantalla(ny)
                    x_px, y_px = nx * tw, yp * th
                    self.canvas.create_rectangle(
                        x_px + ofx, y_px + ofy, x_px + tw - ofx, y_px + th - ofy,
                        fill=plan["color"], outline="#00ffff", width=1, tags=f"rastro_{pk_id}"
                    )

    def _renderizar_estado_paso(self, paso_idx, registrar_log=True):
        tw, th, t = self.celda_w, self.celda_h, self.celda_tam
        self.canvas.delete("prod_activo")

        if self.cap_zonas_por_paso:
            idx_cap = min(paso_idx, len(self.cap_zonas_por_paso) - 1)
            self.cap_zonas_actual = dict(self.cap_zonas_por_paso[idx_cap])
            self._actualizar_etiquetas_zonas_canvas()

        waves_activas_ahora = {}
        lineas_picker_monitor = []

        for plan in self.planes_activos:
            hist = plan["historial"]
            estados = plan["estados_paso"]
            idx = min(paso_idx, len(hist) - 1)
            nx, ny = hist[idx]
            est = estados[min(paso_idx, len(estados) - 1)]

            pk_id = plan["id_picker"]
            num_pk = pk_id[-2:]
            w_madre = est["wave_madre"]
            peso_act = est["peso"]

            if est.get("limpiar_rastro") and paso_idx > 0:
                self.canvas.delete(f"rastro_{pk_id}")

            ev = est.get("evento", "")
            if ev and paso_idx < len(estados):
                if "📦 Entregó" in ev:
                    for token in ev.split():
                        if token.startswith("W") and token[1:].isdigit():
                            self.waves_completadas.add(token)
                if registrar_log and any(k in ev for k in ("Inicia", "🤝", "🛒", "📦", "🔀")):
                    self._registrar_evento_simulacion(paso_idx, pk_id, plan["sector_corto"], ev)

            for px, py, pz, _, _ in est.get("prods_activos", []):
                yp_prod = self._y_pantalla(py)
                offset_x = (pz - 1) * int(tw * 0.14)
                offset_y = (pz - 1) * int(th * 0.14)
                cx = px * tw + tw / 2 + offset_x
                cy = yp_prod * th + th / 2 - offset_y

                ancho_tag = int(tw * 0.44)
                alto_tag = int(th * 0.32)

                color_bg = "#2ecc71" if pz == 1 else ("#f39c12" if pz == 2 else "#e74c3c")
                txt_z = f"P{num_pk[-1]}:z{pz}"

                self.canvas.create_rectangle(
                    cx - ancho_tag, cy - alto_tag, cx + ancho_tag, cy + alto_tag,
                    fill=color_bg, outline=plan["color"], width=2.5, tags="prod_activo"
                )
                if t >= 14:
                    self.canvas.create_text(
                        cx, cy, text=txt_z, fill="white" if pz != 2 else "black",
                        font=("Segoe UI", max(6, int(t * 0.21)), "bold"), tags="prod_activo"
                    )

            yp = self._y_pantalla(ny)
            x_px, y_px = nx * tw, yp * th

            if w_madre is not None:
                ofx = tw * 0.38
                ofy = th * 0.38
                self.canvas.create_rectangle(
                    x_px + ofx, y_px + ofy, x_px + tw - ofx, y_px + th - ofy,
                    fill=plan["color"], outline="#00ffff", width=1, tags=f"rastro_{pk_id}"
                )
                waves_activas_ahora.setdefault(w_madre, []).append(pk_id)

            if plan["oval_id"]:
                self.canvas.coords(plan["oval_id"], *self._coords_poligono_agv(x_px, y_px, tw, th))
                self.canvas.tag_raise(plan["oval_id"])

            if plan["txt_id"]:
                etiqueta = f"{int(peso_act)}k" if peso_act > 0 else f"P{num_pk[-1]}"
                self.canvas.coords(plan["txt_id"], x_px + tw * 0.4, y_px + th * 0.5)
                self.canvas.itemconfig(plan["txt_id"], text=etiqueta)
                self.canvas.tag_raise(plan["txt_id"])

            w_str = w_madre if w_madre else "---"
            lineas_picker_monitor.append(
                f"[{pk_id} | {plan['sector_corto']}] {w_str} > {peso_act:4.1f}/{plan['cap_kg']:.0f}kg - {est['estado']}"
            )

        waves_en_prep = set(waves_activas_ahora.keys())
        waves_realmente_listas = self.waves_completadas - waves_en_prep
        self._actualizar_estados_pedidos_simulacion(waves_en_prep, waves_realmente_listas)

        max_len = max((len(p["historial"]) for p in self.planes_activos), default=1) - 1
        if waves_activas_ahora:
            txt_waves = " | ".join(
                f"{w}: [{', '.join(pks)}]" for w, pks in sorted(waves_activas_ahora.items())
            )
        else:
            txt_waves = "NINGUNA (WAVES COMPLETADAS)"

        texto_tablero = (
            f"PASO: {min(paso_idx, max_len)}/{max_len} | "
            f"WAVES LISTAS: {len(waves_realmente_listas)}/{len(self.waves)}\n"
            f"DOCKS DISP: {self._resumen_docks_texto()}\n"
            f"EN CURSO: {txt_waves}\n" +
            "\n".join(lineas_picker_monitor)
        )
        self._actualizar_monitor_texto(texto_tablero)

    def mover_picker(self):
        if not self.planes_activos:
            self.simulando = False
            return

        max_len = max(len(p["historial"]) for p in self.planes_activos)
        if self.paso_actual >= max_len:
            self.simulando = False
            for ped in self.warehouse.pedidos.valores():
                if self.modo_continuo:
                    ped.estado = "PREPARADO"
            self._agregar_linea_log("✔ OPERACIÓN COMPLETADA EXITOSAMENTE.", "exito")
            return

        self._renderizar_estado_paso(self.paso_actual)
        self.paso_actual += 1

        if self.simulando and not self.pausado:
            self.after(int(self.vel_simulacion * 1000), self.mover_picker)

    def cmd_iniciar(self):
        cfg_actual = (self.cmb_estrategia.get(), bool(self.var_ayuda_zonas.get()))
        if not self.planes_activos or (self.paso_actual == 0 and self._config_plan_actual != cfg_actual):
            self.cmd_calcular_operacion_completa()
        if self.planes_activos and (not self.simulando or self.pausado):
            max_len = max(len(p["historial"]) for p in self.planes_activos)
            if self.paso_actual >= max_len:
                self.cmd_reiniciar()
            self.simulando = True
            self.pausado = False
            self.mover_picker()

    def cmd_pausar(self):
        self.pausado = True

    def cmd_continuar(self):
        if not self.planes_activos:
            return
        max_len = max(len(p["historial"]) for p in self.planes_activos)
        if self.paso_actual < max_len and (self.pausado or not self.simulando):
            self.simulando = True
            self.pausado = False
            self.mover_picker()

    def cmd_paso(self):
        cfg_actual = (self.cmb_estrategia.get(), bool(self.var_ayuda_zonas.get()))
        if not self.planes_activos or (self.paso_actual == 0 and self._config_plan_actual != cfg_actual):
            self.cmd_calcular_operacion_completa()
        if self.planes_activos:
            self.simulando = False
            self.pausado = True
            self.mover_picker()

    def cmd_reiniciar(self):
        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        self.waves_completadas.clear()
        self._resetear_capacidades_zonas()
        cfg_actual = (self.cmb_estrategia.get(), bool(self.var_ayuda_zonas.get()))
        if self.planes_activos and self._config_plan_actual == cfg_actual:
            self._dibujar_warehouse()
            self._posicionar_pickers_iniciales()
            self._limpiar_eventos()
            self._agregar_linea_log("━━━ TELEMETRÍA REINICIADA AL PASO 0 ━━━", "titulo")
            self._renderizar_estado_paso(0, registrar_log=False)
        else:
            self.cmd_calcular_operacion_completa()

    def cmd_cambiar_velocidad(self, val):
        self.vel_simulacion = float(val) / 1000.0

    def cmd_cambiar_zoom(self, val):
        porcentaje = int(float(val))
        nuevo_factor = porcentaje / 100.0
        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.config(text=f"Zoom ({porcentaje}%):")
        if abs(nuevo_factor - self.factor_zoom) > 0.01:
            self.factor_zoom = nuevo_factor
            self._ajustar_y_redibujar()

    def cmd_comparar_estrategias(self):
        if not self.waves:
            self.cmd_generar_waves()
            if not self.waves:
                return

        ayuda_activa = bool(self.var_ayuda_zonas.get())
        resultados = CoordinadorMultiPicker.comparar_escenario_completo(
            self.warehouse,
            self.waves,
            permitir_ayuda_zonas=ayuda_activa
        )

        modo_txt = "Con Ayuda Inter-Zona" if ayuda_activa else "Zona Estricta"
        win = tk.Toplevel(self)
        win.title(f"📊 Benchmarking de Algoritmos - {modo_txt} ({len(self.waves)} Waves)")
        win.geometry("840x310+180+150")
        win.configure(bg=self.BG_APP)

        ttk.Label(
            win,
            text=f"Métricas Oficiales con Zonificación ({modo_txt} | {len(self.waves)} Waves | {len(self.warehouse.pickers)} Pickers)",
            font=("Segoe UI", 11, "bold"),
            foreground=self.ACCENT_PRI,
            background=self.BG_APP
        ).pack(pady=(12, 6))

        cols = (
            "Algoritmo Utilizado", "Costo Total (Distancia)", "Nodos Visitados",
            "Aristas Recorridas", "Operaciones CPU", "Tiempo (ms)"
        )
        tree = ttk.Treeview(win, columns=cols, show="headings", height=5)
        for c in cols:
            tree.heading(c, text=c)
            ancho_c = 190 if c == "Algoritmo Utilizado" else 115
            tree.column(c, width=ancho_c, anchor="center")

        for r in resultados:
            tree.insert("", "end", values=(
                r['estrategia'], r['distancia_flota'], r['nodos_visitados'],
                r['pasos_planta'], r['operaciones'], f"{r['tiempo_ms']:.2f}"
            ))

        tree.pack(fill="both", expand=True, padx=15, pady=8)

        mejor = min(resultados, key=lambda x: (x['distancia_flota'], x['tiempo_ms']))
        ttk.Label(
            win,
            text=f"🏆 Algoritmo Óptimo: {mejor['estrategia']} "
                 f"(Score Global: {mejor['distancia_flota']} | Accesos: {mejor['nodos_visitados']})",
            font=("Segoe UI", 11, "bold"),
            foreground=self.ACCENT_SEC,
            background=self.BG_APP
        ).pack(pady=10)

    def _restaurar_estado_simulacion(self, estado):
        """
        Restaura el punto exacto de la simulación guardada (Waves, rutas, paso actual,
        capacidad de zonas de despacho, controles y log de eventos) para reanudar sin reconstruir.
        """
        self.simulando = False
        self.pausado = True

        est_nombre = estado.get("estrategia", "Estrategia B - Cercanía 3D (Greedy)")
        if est_nombre in self.cmb_estrategia["values"]:
            self.cmb_estrategia.set(est_nombre)

        ayuda_guardada = bool(estado.get("permitir_ayuda_zonas", False))
        self.var_ayuda_zonas.set(ayuda_guardada)
        self.modo_continuo = bool(estado.get("modo_continuo", True))

        self.vel_simulacion = float(estado.get("vel_simulacion", 0.12))
        self.scale_vel.set(int(self.vel_simulacion * 1000))

        self.factor_zoom = float(estado.get("factor_zoom", 1.0))
        porcentaje_zoom = int(round(self.factor_zoom * 100))
        self.scale_zoom.set(porcentaje_zoom)
        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.config(text=f"Zoom ({porcentaje_zoom}%):")

        self.waves = list(estado.get("waves", []))
        self.waves_completadas = set(estado.get("waves_completadas", []))
        if self.waves:
            self.cmb_waves["values"] = [
                f"{w.id_wave} ({w.total_unidades}u | {w.peso_total:.0f}kg | {w.picker_id})"
                for w in self.waves
            ]
            idx_w = min(max(0, int(estado.get("wave_seleccionada_idx", 0))), len(self.waves) - 1)
            self.cmb_waves.current(idx_w)
        else:
            self.cmb_waves.set("")
            self.cmb_waves["values"] = []

        cap_defecto = {z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho}
        self.cap_zonas_actual = dict(estado.get("cap_zonas_actual", cap_defecto))
        self.cap_zonas_por_paso = list(estado.get("cap_zonas_por_paso", [dict(self.cap_zonas_actual)]))
        self.metricas_actuales = dict(estado.get("metricas_actuales", {}))
        self.planes_activos = list(estado.get("planes_activos", []))
        self.paso_actual = int(estado.get("paso_actual", 0))
        self._config_plan_actual = (self.cmb_estrategia.get(), ayuda_guardada)

        self._limpiar_eventos()
        log_guardado = estado.get("log_eventos", [])
        if log_guardado:
            for item_log in log_guardado:
                if isinstance(item_log, (list, tuple)) and len(item_log) >= 2:
                    self._agregar_linea_log(str(item_log[0]), str(item_log[1]), guardar_historial=True)
                else:
                    self._agregar_linea_log(str(item_log), "item", guardar_historial=True)
        else:
            self._agregar_linea_log("━━━ SIMULACIÓN RECUPERADA ━━━", "titulo")

        self._recalcular_dimensiones_celda()
        self._actualizar_lienzo_completo()

        if self.planes_activos:
            paso_vis = max(0, self.paso_actual - 1)
            self._posicionar_pickers_iniciales()
            self._redibujar_rastros_hasta(paso_vis)
            self._renderizar_estado_paso(paso_vis, registrar_log=False)
            self._agregar_linea_log(
                f"💾 Simulación cargada en Paso {paso_vis}. Pulse '⏯ Continuar' o '▶ Iniciar' para reanudar.",
                "exito"
            )
        elif not self.waves:
            self._mostrar_resumen_inicial()
        else:
            zonas = WaveManager.obtener_zonas_pickers(self.warehouse)
            self._actualizar_monitor_texto(
                f"WAVES CARGADAS: {len(self.waves)} (Zonificación Activa)\n"
                f"DOCKS DISP: {self._resumen_docks_texto()}\n"
                f"PICKERS EN ZONA: {len(zonas)}\n"
                f"> Escenario recuperado. Pulse 'Iniciar' o 'Despachar Flota'."
            )

    def cmd_cargar_json(self):
        ruta = filedialog.askopenfilename(
            title="Cargar Escenario / Simulación Guardada",
            filetypes=[("Archivos de Simulación JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        if not ruta:
            return
        try:
            self.simulando = False
            self.pausado = False
            self.warehouse = PersistenciaJSON.cargar_escenario(ruta)
            estado_guardado = getattr(self.warehouse, "estado_simulacion_guardado", None)

            if estado_guardado:
                self._restaurar_estado_simulacion(estado_guardado)
            else:
                self.waves.clear()
                self.planes_activos.clear()
                self.waves_completadas.clear()
                self.paso_actual = 0
                self._config_plan_actual = None
                self.cmb_waves.set("")
                self.cmb_waves['values'] = []
                self.factor_zoom = 1.0
                self.scale_zoom.set(100)
                if hasattr(self, "lbl_zoom"):
                    self.lbl_zoom.config(text="Zoom (100%):")
                self.cap_zonas_por_paso = [
                    {z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho}
                ]
                self._mostrar_resumen_inicial()
                self._ajustar_y_redibujar()
        except Exception as e:
            messagebox.showerror("Error de Carga", f"Fallo al cargar la simulación o escenario:\n{e}")

    def cmd_guardar_json(self):
        if self.simulando and not self.pausado:
            self.pausado = True

        ruta = filedialog.asksaveasfilename(
            title="Guardar Simulación y Escenario",
            defaultextension=".json",
            filetypes=[("Archivos de Simulación JSON", "*.json")]
        )
        if not ruta:
            return
        try:
            estado_sim = {
                "paso_actual": self.paso_actual,
                "estrategia": self.cmb_estrategia.get(),
                "permitir_ayuda_zonas": bool(self.var_ayuda_zonas.get()),
                "modo_continuo": self.modo_continuo,
                "wave_seleccionada_idx": max(0, self.cmb_waves.current()) if self.waves else 0,
                "vel_simulacion": self.vel_simulacion,
                "factor_zoom": self.factor_zoom,
                "waves": self.waves,
                "waves_completadas": list(self.waves_completadas),
                "cap_zonas_actual": dict(self.cap_zonas_actual),
                "cap_zonas_por_paso": self.cap_zonas_por_paso,
                "metricas_actuales": self.metricas_actuales,
                "planes_activos": self.planes_activos,
                "log_eventos": self.historial_log
            }
            PersistenciaJSON.guardar_escenario(self.warehouse, ruta, estado_simulacion=estado_sim)
            paso_guardado = max(0, self.paso_actual - 1) if self.planes_activos else 0
            messagebox.showinfo(
                "Simulación Guardada",
                f"Escenario y estado de simulación (Paso {paso_guardado}) guardados exitosamente en:\n{ruta}\n\n"
                f"Al cargar este archivo podrá continuar la simulación directamente desde este punto."
            )
        except Exception as e:
            messagebox.showerror("Error al Guardar Simulación", str(e))

    def cmd_generar_warehouse_auto(self):
        """
        Abre el configurador para generar un Warehouse válido de manera automática,
        permitiendo parametrizar estantes, pasillos, productos, localización de productos,
        pedidos, máximo de productos por pedido y capacidad de las waves.
        """
        win = tk.Toplevel(self)
        win.title("⚙️ Generador Automático de Warehouse Válido")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w_dlg = min(680, screen_w - 60)
        h_dlg = min(670, screen_h - 90)
        pos_x = max(20, (screen_w - w_dlg) // 2)
        pos_y = max(20, (screen_h - h_dlg - 40) // 2)
        win.geometry(f"{w_dlg}x{h_dlg}+{pos_x}+{pos_y}")
        win.configure(bg=self.BG_APP)
        win.transient(self)
        win.grab_set()

        ubicaciones_custom = []

        # Contenedor principal
        main_frame = ttk.Frame(win, padding=12)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)

        ttk.Label(
            main_frame,
            text="🏗️ Configuración de Generación Automática de Warehouse",
            font=("Segoe UI", 11, "bold"),
            foreground="#00d2d3"
        ).pack(anchor="w", pady=(0, 6))

        # ------------------------------------------------------------------
        # 1. Estructura Física (Estantes, Pasillos, Puertas y Despacho)
        # ------------------------------------------------------------------
        lf_est = ttk.LabelFrame(main_frame, text=" 1. Estructura Física (Estantes, Pasillos y Despacho) ", padding=8)
        lf_est.pack(fill="x", pady=4)
        lf_est.columnconfigure(1, weight=1)
        lf_est.columnconfigure(3, weight=1)

        var_estantes = tk.IntVar(value=max(1, len(self.warehouse.racks) or 4))
        var_largo_est = tk.IntVar(value=6)
        var_pasillos = tk.IntVar(value=max(2, len(self.warehouse.pasillos) or 6))
        var_puertas = tk.IntVar(value=max(1, len(self.warehouse.puertas) or 2))
        var_peso_zona = tk.IntVar(value=500)

        def sincronizar_pasillos(*_args):
            try:
                n_r = max(1, int(var_estantes.get()))
                min_calles = n_r + 3
                if int(var_pasillos.get()) < min_calles:
                    var_pasillos.set(min_calles)
            except Exception:
                pass

        ttk.Label(lf_est, text="Cantidad de estantes (Racks):").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_est, from_=1, to=20, textvariable=var_estantes, width=8, command=sincronizar_pasillos,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_est, text="Largo de estante (lado fijo = 2):").grid(row=0, column=2, sticky="w", padx=8, pady=3)
        tk.Spinbox(
            lf_est, from_=2, to=12, textvariable=var_largo_est, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(lf_est, text="Cantidad de pasillos:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_est, from_=2, to=30, textvariable=var_pasillos, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_est, text="Orientación de estantes:").grid(row=1, column=2, sticky="w", padx=8, pady=3)
        cmb_orient = ttk.Combobox(
            lf_est,
            values=["Vertical (Ancho 2 x Largo N)", "Horizontal (Largo N x Alto 2)"],
            state="readonly", width=24
        )
        cmb_orient.current(0)
        cmb_orient.grid(row=1, column=3, sticky="ew", padx=4, pady=3)
        cmb_orient.bind("<<ComboboxSelected>>", sincronizar_pasillos)

        ttk.Label(lf_est, text="Sentido de pasillos:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        cmb_sentido = ttk.Combobox(
            lf_est,
            values=["Alternado Mano Única (↑/↓ o →/←)", "Doble Mano (AMBOS)"],
            state="readonly", width=24
        )
        cmb_sentido.current(0)
        cmb_sentido.grid(row=2, column=1, sticky="ew", padx=4, pady=3)

        ttk.Label(lf_est, text="Puertas / Zonas Despacho:").grid(row=2, column=2, sticky="w", padx=8, pady=3)
        frame_pz = ttk.Frame(lf_est)
        frame_pz.grid(row=2, column=3, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            frame_pz, from_=1, to=4, textvariable=var_puertas, width=4,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).pack(side="left")
        ttk.Label(frame_pz, text=" Cap(kg):").pack(side="left", padx=(6, 2))
        tk.Spinbox(
            frame_pz, from_=100, to=5000, increment=50, textvariable=var_peso_zona, width=6,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).pack(side="left")

        # ------------------------------------------------------------------
        # 2. Productos y Localización de los Productos
        # ------------------------------------------------------------------
        lf_prod = ttk.LabelFrame(main_frame, text=" 2. Inventario y Localización de los Productos ", padding=8)
        lf_prod.pack(fill="x", pady=4)
        lf_prod.columnconfigure(1, weight=1)
        lf_prod.columnconfigure(3, weight=1)

        var_productos = tk.IntVar(value=max(1, len(self.warehouse.productos) or 12))
        var_nivel_z = tk.IntVar(value=3)

        ttk.Label(lf_prod, text="Cantidad de productos (SKUs):").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_prod, from_=1, to=200, textvariable=var_productos, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_prod, text="Altura máx. estiba (Nivel Z):").grid(row=0, column=2, sticky="w", padx=8, pady=3)
        tk.Spinbox(
            lf_prod, from_=1, to=3, textvariable=var_nivel_z, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(lf_prod, text="Localización de los productos:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        cmb_loc = ttk.Combobox(
            lf_prod,
            values=GeneradorWarehouse.MODOS_LOCALIZACION,
            state="readonly"
        )
        cmb_loc.current(0)
        cmb_loc.grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=3)

        lbl_estado_custom = ttk.Label(
            lf_prod,
            text="Modo automático activo: todos los productos se ubican garantizados dentro de los racks.",
            foreground="#81ecec", font=("Segoe UI", 8)
        )
        lbl_estado_custom.grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=(2, 2))

        def abrir_editor_localizacion():
            """
            Permite asignar o ajustar manualmente en qué Rack y coordenada (x, y, z)
            se ubicará cada producto dentro del Warehouse a generar.
            """
            n_est = max(1, int(var_estantes.get()))
            l_est = max(2, int(var_largo_est.get()))
            orient_str = "HORIZONTAL" if cmb_orient.get().startswith("Horizontal") else "VERTICAL"
            n_pas = max(1, int(var_pasillos.get()))
            sent_str = "DOBLE" if "Doble" in cmb_sentido.get() else "ALTERNADO"
            n_pta = max(1, int(var_puertas.get()))
            n_prods = max(1, int(var_productos.get()))
            z_max_val = max(1, min(3, int(var_nivel_z.get())))

            _, _, _, _, racks_prev, _ = GeneradorWarehouse.calcular_geometria_layout(
                cant_estantes=n_est, largo_estante=l_est, orientacion=orient_str,
                cant_pasillos=n_pas, sentido_pasillos=sent_str, cant_puertas=n_pta
            )
            mapa_celdas_r = {r.id_rack: list(r.celdas()) for r in racks_prev}
            ids_racks = [r.id_rack for r in racks_prev]

            # Inicializar lista si está vacía o cambió la cantidad
            while len(ubicaciones_custom) < n_prods:
                idx_p = len(ubicaciones_custom)
                r_def = racks_prev[idx_p % len(racks_prev)]
                celdas_r = mapa_celdas_r[r_def.id_rack]
                cx_def, cy_def = celdas_r[idx_p % len(celdas_r)]
                ubicaciones_custom.append({
                    "rack_id": r_def.id_rack,
                    "x": cx_def,
                    "y": cy_def,
                    "z": (idx_p % z_max_val) + 1
                })
            del ubicaciones_custom[n_prods:]

            # Validar que cada entrada pertenezca a un rack válido actual
            for idx_p, ub in enumerate(ubicaciones_custom):
                if ub["rack_id"] not in mapa_celdas_r:
                    r_def = racks_prev[idx_p % len(racks_prev)]
                    ub["rack_id"] = r_def.id_rack
                celdas_validas = mapa_celdas_r[ub["rack_id"]]
                if (ub["x"], ub["y"]) not in celdas_validas:
                    ub["x"], ub["y"] = celdas_validas[idx_p % len(celdas_validas)]

            sub = tk.Toplevel(win)
            sub.title("📍 Configurar Localización de Productos en Racks")
            sub.geometry("620x440+160+120")
            sub.configure(bg=self.BG_APP)
            sub.transient(win)
            sub.grab_set()

            ttk.Label(
                sub,
                text="Seleccione un producto para asignarle su Estante (Rack), celda (X, Y) dentro del Rack y altura (Z):",
                font=("Segoe UI", 9, "bold"), foreground="#00d2d3"
            ).pack(anchor="w", padx=12, pady=(10, 4))

            frame_tabla = ttk.Frame(sub, padding=(12, 4))
            frame_tabla.pack(fill="both", expand=True)

            cols_ub = ("Producto", "Nombre", "Rack Asignado", "Coordenada (X, Y)", "Altura (Z)")
            tree_ub = ttk.Treeview(frame_tabla, columns=cols_ub, show="headings", height=10)
            for col in cols_ub:
                tree_ub.heading(col, text=col)
                tree_ub.column(col, width=110, anchor="center")
            sc_ub = ttk.Scrollbar(frame_tabla, orient="vertical", command=tree_ub.yview)
            tree_ub.configure(yscrollcommand=sc_ub.set)
            tree_ub.pack(side="left", fill="both", expand=True)
            sc_ub.pack(side="right", fill="y")

            def refrescar_tabla_ub():
                tree_ub.delete(*tree_ub.get_children())
                for i_p, ub in enumerate(ubicaciones_custom):
                    id_p = f"P{i_p + 1:03d}"
                    nom = GeneradorWarehouse.CATALOGO_NOMBRES[i_p % len(GeneradorWarehouse.CATALOGO_NOMBRES)]
                    tree_ub.insert("", "end", iid=str(i_p), values=(
                        id_p, nom, ub["rack_id"], f"({ub['x']}, {ub['y']})", f"z = {ub['z']}"
                    ))

            refrescar_tabla_ub()

            frame_ed = ttk.LabelFrame(sub, text=" Editar Producto Seleccionado ", padding=8)
            frame_ed.pack(fill="x", padx=12, pady=6)

            ttk.Label(frame_ed, text="Estante (Rack):").pack(side="left", padx=(4, 4))
            cmb_r_sel = ttk.Combobox(frame_ed, values=ids_racks, state="readonly", width=8)
            cmb_r_sel.current(0)
            cmb_r_sel.pack(side="left", padx=4)

            ttk.Label(frame_ed, text="Celda en Rack (X, Y):").pack(side="left", padx=(8, 4))
            cmb_xy_sel = ttk.Combobox(frame_ed, state="readonly", width=12)
            cmb_xy_sel.pack(side="left", padx=4)

            ttk.Label(frame_ed, text="Nivel Z:").pack(side="left", padx=(8, 4))
            cmb_z_sel = ttk.Combobox(frame_ed, values=["1", "2", "3"], state="readonly", width=5)
            cmb_z_sel.current(0)
            cmb_z_sel.pack(side="left", padx=4)

            def actualizar_celdas_combo(_ev=None):
                r_id = cmb_r_sel.get()
                celdas = mapa_celdas_r.get(r_id, [])
                cmb_xy_sel["values"] = [f"{cx},{cy}" for cx, cy in celdas]
                if celdas:
                    cmb_xy_sel.current(0)

            cmb_r_sel.bind("<<ComboboxSelected>>", actualizar_celdas_combo)
            actualizar_celdas_combo()

            def al_seleccionar_fila(_ev=None):
                sel = tree_ub.selection()
                if not sel:
                    return
                idx_s = int(sel[0])
                ub = ubicaciones_custom[idx_s]
                cmb_r_sel.set(ub["rack_id"])
                actualizar_celdas_combo()
                cmb_xy_sel.set(f"{ub['x']},{ub['y']}")
                cmb_z_sel.set(str(ub["z"]))

            tree_ub.bind("<<TreeviewSelect>>", al_seleccionar_fila)

            def aplicar_cambio_producto():
                sel = tree_ub.selection()
                if not sel:
                    return
                idx_s = int(sel[0])
                r_id = cmb_r_sel.get()
                xy_parts = cmb_xy_sel.get().split(",")
                cx_n, cy_n = int(xy_parts[0]), int(xy_parts[1])
                cz_n = int(cmb_z_sel.get())
                ubicaciones_custom[idx_s] = {"rack_id": r_id, "x": cx_n, "y": cy_n, "z": cz_n}
                refrescar_tabla_ub()
                tree_ub.selection_set(str(idx_s))

            ttk.Button(
                frame_ed, text="Aplicar al Producto", command=aplicar_cambio_producto, style="Primary.TButton"
            ).pack(side="left", padx=10)

            def confirmar_custom():
                cmb_loc.set("Personalizada (Asignación Manual por Producto)")
                lbl_estado_custom.config(
                    text=f"✔ Localización personalizada activa ({len(ubicaciones_custom)} productos ubicados en racks).",
                    foreground="#55efc4"
                )
                sub.destroy()

            ttk.Button(
                sub, text="✅ Confirmar Localización de Productos", command=confirmar_custom, style="Success.TButton"
            ).pack(fill="x", padx=12, pady=(2, 10))

        ttk.Button(
            lf_prod,
            text="📍 Personalizar Coordenadas...",
            command=abrir_editor_localizacion
        ).grid(row=2, column=3, sticky="e", padx=4, pady=2)

        # ------------------------------------------------------------------
        # 3. Pedidos, Capacidad de las Waves y Flota de Pickers
        # ------------------------------------------------------------------
        lf_ped = ttk.LabelFrame(main_frame, text=" 3. Pedidos, Capacidad de las Waves y Flota ", padding=8)
        lf_ped.pack(fill="x", pady=4)
        lf_ped.columnconfigure(1, weight=1)
        lf_ped.columnconfigure(3, weight=1)

        var_pedidos = tk.IntVar(value=max(1, len(self.warehouse.pedidos) or 6))
        var_max_prod_ped = tk.IntVar(value=4)
        var_max_unid_item = tk.IntVar(value=3)
        var_wave_ped = tk.IntVar(value=self.warehouse.wave_max_pedidos)
        var_wave_prod = tk.IntVar(value=self.warehouse.wave_max_productos)
        var_pickers = tk.IntVar(value=max(1, len(self.warehouse.pickers) or 2))
        var_cap_picker = tk.IntVar(value=150)

        ttk.Label(lf_ped, text="Cantidad de pedidos:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_ped, from_=1, to=100, textvariable=var_pedidos, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_ped, text="Máx. productos por pedido:").grid(row=0, column=2, sticky="w", padx=8, pady=3)
        tk.Spinbox(
            lf_ped, from_=1, to=30, textvariable=var_max_prod_ped, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(lf_ped, text="Capacidad Wave (Máx. Pedidos):").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_ped, from_=1, to=50, textvariable=var_wave_ped, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_ped, text="Capacidad Wave (Máx. Productos):").grid(row=1, column=2, sticky="w", padx=8, pady=3)
        tk.Spinbox(
            lf_ped, from_=1, to=500, textvariable=var_wave_prod, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(lf_ped, text="Unidades máx. por línea:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            lf_ped, from_=1, to=15, textvariable=var_max_unid_item, width=8,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(lf_ped, text="Flota de Pickers y Cap. (kg):").grid(row=2, column=2, sticky="w", padx=8, pady=3)
        frame_pk = ttk.Frame(lf_ped)
        frame_pk.grid(row=2, column=3, sticky="w", padx=4, pady=3)
        tk.Spinbox(
            frame_pk, from_=1, to=6, textvariable=var_pickers, width=4,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).pack(side="left")
        ttk.Label(frame_pk, text=" Cap(kg):").pack(side="left", padx=(6, 2))
        tk.Spinbox(
            frame_pk, from_=20, to=1000, increment=10, textvariable=var_cap_picker, width=6,
            bg=self.BG_PANEL, fg="white", insertbackground="white"
        ).pack(side="left")

        # ------------------------------------------------------------------
        # 4. Garantías de Validación Automática
        # ------------------------------------------------------------------
        lf_val = ttk.LabelFrame(main_frame, text=" 🛡️ Garantías de Validez Verificadas por el Sistema ", padding=6)
        lf_val.pack(fill="x", pady=4)
        garantias_txt = (
            "• Todos los elementos están dentro de las dimensiones del Warehouse y NO se solapan.\n"
            "• Todos los racks tienen un lado de valor 2 (2xN o Nx2) y todos los productos están dentro de un rack.\n"
            "• Todas las puertas están sobre el borde perimetral y frente a cada puerta hay una zona de despacho.\n"
            "• Todas las ubicaciones requeridas son alcanzables desde la zona de despacho respetando el sentido de los pasillos."
        )
        ttk.Label(
            lf_val, text=garantias_txt, foreground="#55efc4", font=("Consolas", 8)
        ).pack(anchor="w")

        def ejecutar_generacion():
            try:
                orient_val = "HORIZONTAL" if cmb_orient.get().startswith("Horizontal") else "VERTICAL"
                sent_val = "DOBLE" if "Doble" in cmb_sentido.get() else "ALTERNADO"
                modo_loc_val = cmb_loc.get()
                ub_arg = ubicaciones_custom if ("Personalizada" in modo_loc_val and ubicaciones_custom) else None

                nuevo_wh = GeneradorWarehouse.generar(
                    cant_estantes=int(var_estantes.get()),
                    largo_estante=int(var_largo_est.get()),
                    orientacion_estantes=orient_val,
                    cant_pasillos=int(var_pasillos.get()),
                    sentido_pasillos=sent_val,
                    cant_productos=int(var_productos.get()),
                    modo_localizacion=modo_loc_val,
                    nivel_z_max=int(var_nivel_z.get()),
                    ubicaciones_personalizadas=ub_arg,
                    cant_pedidos=int(var_pedidos.get()),
                    max_productos_por_pedido=int(var_max_prod_ped.get()),
                    max_unidades_por_item=int(var_max_unid_item.get()),
                    wave_max_pedidos=int(var_wave_ped.get()),
                    wave_max_productos=int(var_wave_prod.get()),
                    cant_pickers=int(var_pickers.get()),
                    cap_picker_kg=float(var_cap_picker.get()),
                    cant_puertas=int(var_puertas.get()),
                    peso_max_zona_kg=float(var_peso_zona.get())
                )

                es_valido, errores, _ = nuevo_wh.validar_escenario()
                if not es_valido:
                    messagebox.showerror(
                        "Error de Validación",
                        "El escenario generado no superó la validación:\n" + "\n".join(errores)
                    )
                    return

                self.simulando = False
                self.pausado = False
                self.warehouse = nuevo_wh
                self.waves.clear()
                self.planes_activos.clear()
                self.waves_completadas.clear()
                self.paso_actual = 0
                self._config_plan_actual = None
                self.cmb_waves.set("")
                self.cmb_waves["values"] = []
                self.factor_zoom = 1.0
                self.scale_zoom.set(100)
                if hasattr(self, "lbl_zoom"):
                    self.lbl_zoom.config(text="Zoom (100%):")
                self.cap_zonas_por_paso = [
                    {z.id_zona: float(z.peso_max_kg) for z in self.warehouse.zonas_despacho}
                ]

                self._mostrar_resumen_inicial()
                self._ajustar_y_redibujar()
                win.destroy()
            except Exception as ex:
                messagebox.showerror("Error al Generar Warehouse", str(ex))

        frame_btns = ttk.Frame(main_frame)
        frame_btns.pack(fill="x", pady=(8, 0))
        ttk.Button(frame_btns, text="Cancelar", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(
            frame_btns,
            text="✅ Generar y Validar Warehouse",
            command=ejecutar_generacion,
            style="Success.TButton"
        ).pack(side="right", fill="x", expand=True)

    def obtener_relacion_producto_pedidos(self):
        """
        Función que vincula cada producto del stock con los pedidos a los que pertenece,
        su cantidad solicitada y el Picker/Zona responsable de recolectarlo.
        """
        zonas = WaveManager.obtener_zonas_pickers(self.warehouse)
        pedidos_por_prod = self.warehouse.obtener_pedidos_por_producto()
        lista_detalle = []

        for pr in self.warehouse.productos.valores():
            z_info = WaveManager.obtener_zona_de_producto(pr, self.warehouse, zonas)
            zona_txt = f"{z_info['picker_id']} • {z_info['nombre_zona']}" if z_info else "Sin zona"
            asociados = pedidos_por_prod.get(pr.id_prod, [])
            if asociados:
                pedidos_txt = ", ".join(f"{pid} ({cant} u.)" for pid, cant, _, _ in asociados)
                total_solicitado = sum(cant for _, cant, _, _ in asociados)
            else:
                pedidos_txt = "Sin pedido asignado"
                total_solicitado = 0

            lista_detalle.append({
                "producto": pr,
                "zona_txt": zona_txt,
                "pedidos_asociados": asociados,
                "pedidos_txt": pedidos_txt,
                "total_solicitado": total_solicitado
            })
        return lista_detalle

    def cmd_ver_inventario(self):
        win = tk.Toplevel(self)
        win.title("📋 Control WMS: Stock, Pedidos por Producto, Sublistas por Picker y Zonas")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w_inv = min(1040, screen_w - 60)
        h_inv = min(640, screen_h - 100)
        win.geometry(f"{w_inv}x{h_inv}+80+40")
        win.configure(bg=self.BG_APP)

        zonas = WaveManager.obtener_zonas_pickers(self.warehouse)
        n_pk = len(zonas)

        # Panel explicativo superior sobre la división por zonas del Warehouse
        lf_info_zonas = ttk.LabelFrame(
            win,
            text=" 🗺️ División Zonal del Warehouse por Picker (Optimización de Eficiencia y Distancia) ",
            padding=8
        )
        lf_info_zonas.pack(fill="x", padx=12, pady=(8, 4))

        if n_pk == 2:
            desc_gral = (
                f"El Warehouse ({self.warehouse.ancho_x}x{self.warehouse.largo_y}) se divide exactamente a la mitad: "
                f"la mitad izquierda la toma {zonas[0]['picker_id']} y la otra mitad (derecha) la toma {zonas[1]['picker_id']}. "
                f"Así cada Picker trabaja siempre en su misma zona sin cruzar a la otra punta del almacén."
            )
        elif n_pk > 2:
            desc_gral = (
                f"El Warehouse ({self.warehouse.ancho_x}x{self.warehouse.largo_y}) se divide en {n_pk} sectores proporcionales "
                f"para que cada Picker trabaje exclusivamente en su zona más cercana y recorra la menor distancia posible."
            )
        else:
            desc_gral = "Un único Picker cubre la totalidad del Warehouse."

        ttk.Label(
            lf_info_zonas, text=desc_gral,
            foreground="#00d2d3", background=self.BG_APP, font=("Segoe UI", 9, "bold"), wraplength=w_inv - 50
        ).pack(anchor="w", pady=(0, 4))

        for z in zonas:
            racks_str = ", ".join(z["racks"]) if z["racks"] else "Ninguno"
            pk = z["picker"]
            txt_z = (
                f"  • {pk.id_picker} (Pos. Inicial: {pk.x_inicial},{pk.y_inicial} | Cap. Máx: {pk.capacidad_carga_kg:.0f} kg) "
                f"➔ {z['nombre_zona']} [{z['rango_x']}] │ Racks asignados: {racks_str}"
            )
            ttk.Label(lf_info_zonas, text=txt_z, foreground=self.FG_TEXT, background=self.BG_APP, font=("Consolas", 9)).pack(anchor="w")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=12, pady=6)

        # =========================================================================
        # TAB 1: Stock y a qué Pedido pertenece cada Producto
        # =========================================================================
        tab_p = ttk.Frame(nb, padding=8)
        nb.add(tab_p, text=f"📦 Stock y Pedido por Producto ({len(self.warehouse.productos)})")

        barra_filtro_p = ttk.Frame(tab_p)
        barra_filtro_p.pack(fill="x", pady=(0, 6))

        ttk.Label(
            barra_filtro_p,
            text="Consulte aquí a qué pedido(s) pertenece cada producto del almacén y qué Picker lo atiende según su zona:",
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        solo_con_pedido_var = tk.BooleanVar(value=False)

        cols_p = (
            "SKU_ID", "Producto", "Rack / Pos (x,y,z)",
            "Zona / Picker Asignado", "Stock Disp.", "Peso Unit.", "Pertenece a Pedido(s)"
        )
        tree_p = ttk.Treeview(tab_p, columns=cols_p, show="headings", height=11)
        anchos_p = {
            "SKU_ID": 75,
            "Producto": 145,
            "Rack / Pos (x,y,z)": 125,
            "Zona / Picker Asignado": 210,
            "Stock Disp.": 85,
            "Peso Unit.": 85,
            "Pertenece a Pedido(s)": 260
        }
        for col in cols_p:
            tree_p.heading(col, text=col)
            tree_p.column(col, width=anchos_p.get(col, 120), anchor="center")

        datos_prod_ped = self.obtener_relacion_producto_pedidos()

        def poblar_tabla_productos():
            tree_p.delete(*tree_p.get_children())
            for info in datos_prod_ped:
                if solo_con_pedido_var.get() and not info["pedidos_asociados"]:
                    continue
                pr = info["producto"]
                tree_p.insert("", "end", iid=pr.id_prod, values=(
                    pr.id_prod,
                    pr.nombre,
                    f"{pr.rack_id} ({pr.x},{pr.y},z={pr.z})",
                    info["zona_txt"],
                    pr.stock,
                    f"{pr.peso:.2f} kg",
                    info["pedidos_txt"]
                ))

        chk_filtro = tk.Checkbutton(
            barra_filtro_p,
            text="Mostrar solo productos con pedido asignado",
            variable=solo_con_pedido_var,
            command=poblar_tabla_productos,
            bg=self.BG_APP, fg="#55efc4", selectcolor=self.BG_PANEL,
            activebackground=self.BG_APP, activeforeground="#55efc4",
            font=("Segoe UI", 9, "bold")
        )
        chk_filtro.pack(side="right")

        tree_p.pack(fill="both", expand=True)

        lbl_detalle_prod = ttk.Label(
            tab_p,
            text="💡 Seleccione un producto en la tabla para ver el desglose completo de sus pedidos asociados.",
            foreground="#ffeaa7", font=("Consolas", 9, "bold")
        )
        lbl_detalle_prod.pack(fill="x", pady=(6, 2))

        def al_seleccionar_producto(_event):
            sel = tree_p.selection()
            if not sel:
                return
            id_sel = sel[0]
            for info in datos_prod_ped:
                if info["producto"].id_prod == id_sel:
                    pr = info["producto"]
                    if info["pedidos_asociados"]:
                        desglose = "  |  ".join(
                            f"Pedido {pid}: {cant} u. (Prioridad {prio}, Estado: {est})"
                            for pid, cant, prio, est in info["pedidos_asociados"]
                        )
                        lbl_detalle_prod.config(
                            text=f"🔍 {pr.id_prod} ({pr.nombre}) ➔ Solicitado en: {desglose} [Total: {info['total_solicitado']} u.]"
                        )
                    else:
                        lbl_detalle_prod.config(
                            text=f"🔍 {pr.id_prod} ({pr.nombre}) ➔ Actualmente no está incluido en ningún pedido."
                        )
                    break

        tree_p.bind("<<TreeviewSelect>>", al_seleccionar_producto)
        poblar_tabla_productos()

        # =========================================================================
        # TAB 2: Sublista de Productos de cada Picker
        # =========================================================================
        tab_sub = ttk.Frame(nb, padding=8)
        nb.add(tab_sub, text=f"👷 Sublista de Productos por Picker ({len(zonas)})")

        sublistas = WaveManager.obtener_sublistas_por_picker(self.warehouse, self.waves)

        barra_pk = ttk.Frame(tab_sub)
        barra_pk.pack(fill="x", pady=(0, 6))
        ttk.Label(barra_pk, text="Filtrar Sublista por Picker:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))

        opciones_pk = ["Todos los Pickers"] + [
            f"{z['picker_id']} - {z['nombre_zona']} ({z['rango_x']})" for z in zonas
        ]
        cmb_filtro_pk = ttk.Combobox(barra_pk, values=opciones_pk, state="readonly", width=42)
        cmb_filtro_pk.current(0)
        cmb_filtro_pk.pack(side="left")

        resumen_pk_txt = "   │   ".join(
            f"{pk_id} ({info['zona']['sector_corto']}): {len(info['items'])} líneas / {info['total_unidades']} u. ({info['peso_total']:.1f} kg)"
            for pk_id, info in sublistas.items()
        )
        ttk.Label(barra_pk, text=resumen_pk_txt, foreground="#55efc4", font=("Consolas", 9, "bold")).pack(side="right")

        cols_sub = (
            "Picker", "Zona Asignada", "Wave", "SKU_ID",
            "Producto", "Ubicación (Rack / x,y,z)", "Pedido Origen", "Cantidad", "Peso Subtotal"
        )
        tree_sub = ttk.Treeview(tab_sub, columns=cols_sub, show="headings", height=12)
        anchos_sub = {
            "Picker": 75,
            "Zona Asignada": 185,
            "Wave": 75,
            "SKU_ID": 75,
            "Producto": 140,
            "Ubicación (Rack / x,y,z)": 145,
            "Pedido Origen": 100,
            "Cantidad": 80,
            "Peso Subtotal": 100
        }
        for col in cols_sub:
            tree_sub.heading(col, text=col)
            tree_sub.column(col, width=anchos_sub.get(col, 100), anchor="center")
        tree_sub.pack(fill="both", expand=True)

        def poblar_sublistas(_event=None):
            tree_sub.delete(*tree_sub.get_children())
            filtro = cmb_filtro_pk.get()
            for pk_id, info in sublistas.items():
                if filtro != "Todos los Pickers" and not filtro.startswith(pk_id):
                    continue
                z = info["zona"]
                zona_label = f"{z['nombre_zona']} ({z['rango_x']})"
                for item in info["items"]:
                    pr = item["producto"]
                    tree_sub.insert("", "end", values=(
                        pk_id,
                        zona_label,
                        item["wave_id"],
                        pr.id_prod,
                        pr.nombre,
                        f"{pr.rack_id} ({pr.x},{pr.y},z={pr.z})",
                        item["pedido_id"],
                        f"{item['cantidad']} u.",
                        f"{item['peso_total']:.2f} kg"
                    ))

        cmb_filtro_pk.bind("<<ComboboxSelected>>", poblar_sublistas)
        poblar_sublistas()

        # =========================================================================
        # TAB 3: Órdenes de Cliente con sus Productos detallados
        # =========================================================================
        tab_o = ttk.Frame(nb, padding=8)
        nb.add(tab_o, text=f"🧾 Órdenes de Cliente ({len(self.warehouse.pedidos)})")
        cols_o = ("ID Orden", "Prioridad", "Estado WMS", "Unidades", "Pickers / Zonas Involucradas", "Productos del Pedido")
        tree_o = ttk.Treeview(tab_o, columns=cols_o, show="headings")
        anchos_o = {
            "ID Orden": 90,
            "Prioridad": 80,
            "Estado WMS": 115,
            "Unidades": 80,
            "Pickers / Zonas Involucradas": 210,
            "Productos del Pedido": 400
        }
        for col in cols_o:
            tree_o.heading(col, text=col)
            tree_o.column(col, width=anchos_o.get(col, 120), anchor="center")

        for ped in self.warehouse.pedidos.valores():
            prods_ped_txt = []
            zonas_ped = []
            for it in ped.items:
                pr = self.warehouse.productos.obtener(it.producto_id)
                nom_pr = pr.nombre if pr else it.producto_id
                z_pr = WaveManager.obtener_zona_de_producto(pr, self.warehouse, zonas) if pr else None
                pk_tag = z_pr["picker_id"] if z_pr else "?"
                if z_pr:
                    etiqueta_zp = f"{z_pr['picker_id']} ({z_pr['sector_corto']})"
                    if etiqueta_zp not in zonas_ped:
                        zonas_ped.append(etiqueta_zp)
                prods_ped_txt.append(f"{it.producto_id} {nom_pr} x{it.cantidad_total} [{pk_tag}]")

            tree_o.insert("", "end", values=(
                ped.id_pedido,
                ped.prioridad,
                ped.estado,
                ped.unidades_totales(),
                ", ".join(zonas_ped),
                "  |  ".join(prods_ped_txt)
            ))
        tree_o.pack(fill="both", expand=True)

        # =========================================================================
        # TAB 4: Waves Consolidadas y Reparto por Picker
        # =========================================================================
        tab_w = ttk.Frame(nb, padding=8)
        nb.add(tab_w, text=f"🌊 Waves Consolidadas ({len(self.waves)})")
        cols_w = ("Wave ID", "Pickers Asignados", "Órdenes (Split)", "Desglose de Sublistas por Picker", "Total Unidades", "Peso Total (kg)")
        tree_w = ttk.Treeview(tab_w, columns=cols_w, show="headings")
        anchos_w = {
            "Wave ID": 80,
            "Pickers Asignados": 130,
            "Órdenes (Split)": 160,
            "Desglose de Sublistas por Picker": 380,
            "Total Unidades": 100,
            "Peso Total (kg)": 110
        }
        for col in cols_w:
            tree_w.heading(col, text=col)
            tree_w.column(col, width=anchos_w.get(col, 120), anchor="center")

        for w in self.waves:
            desglose_pk = []
            for pk_id, lins in w.sublistas_pickers.items():
                prods_str = ", ".join(f"{l.producto_id} x{l.cantidad}" for l in lins)
                desglose_pk.append(f"{pk_id}: [{prods_str}]")
            tree_w.insert("", "end", values=(
                w.id_wave,
                w.picker_id,
                ", ".join(w.pedidos_involucrados),
                "  ||  ".join(desglose_pk),
                w.total_unidades,
                f"{w.peso_total:.2f}"
            ))
        tree_w.pack(fill="both", expand=True)