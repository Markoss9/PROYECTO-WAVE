"""
Módulo de Simulación Interactiva Completa
Conecta la interfaz visual con Order Splitting, penalización Z y coordinación Multi-Picker.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from algoritmos import WaveManager, Pathfinding, CoordinadorMultiPicker
from persistencia import PersistenciaJSON


class AppVisual(tk.Tk):
    def __init__(self, warehouse, funcion_generador=None):
        super().__init__()
        self.title("Simulador Wave Picking - Algoritmos II")
        self.geometry("1280x820")
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
        self.info_nodos_acceso = {}  # (ax, ay) -> lista de (id_prod, nombre, cant, peso_total, pedido_id)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._construir_ui()
        self._actualizar_lienzo_completo()

    def _calcular_zoom_optimo(self):
        max_w = 880 // max(1, self.warehouse.ancho_x)
        max_h = 720 // max(1, self.warehouse.largo_y)
        return max(12, min(38, min(max_w, max_h)))

    def _y_pantalla(self, y_modelo):
        """Invierte el eje Y para que (0,0) quede abajo a la izquierda como en el PDF."""
        return (self.warehouse.largo_y - 1) - y_modelo

    def _construir_ui(self):
        frame_izq = ttk.Frame(self, padding="8")
        frame_izq.grid(row=0, column=0, sticky="ns")

        # 1. Gestión de Escenarios
        ttk.Label(frame_izq, text="Gestión de Escenario", font=("Arial", 12, "bold")).pack(pady=(2, 5))

        btn_frame_arch = ttk.Frame(frame_izq)
        btn_frame_arch.pack(fill="x", pady=2)
        ttk.Button(btn_frame_arch, text="📂 Cargar JSON", command=self.cmd_cargar_json).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(btn_frame_arch, text="💾 Guardar JSON", command=self.cmd_guardar_json).pack(side="left", expand=True, fill="x", padx=1)

        ttk.Button(frame_izq, text="⚙️ Generar Escenario Automático", command=self.cmd_abrir_generador).pack(fill="x", pady=2)
        ttk.Button(frame_izq, text="📋 Ver Productos y Pedidos", command=self.cmd_ver_inventario).pack(fill="x", pady=2)

        ttk.Separator(frame_izq, orient="horizontal").pack(fill="x", pady=8)

        # 2. Waves y Estrategias
        ttk.Label(frame_izq, text="Waves y Recorridos", font=("Arial", 12, "bold")).pack(pady=3)
        ttk.Button(frame_izq, text="1. Generar Waves (Order Splitting)", command=self.cmd_generar_waves).pack(fill="x", pady=3)

        ttk.Label(frame_izq, text="Seleccionar Wave:").pack(anchor="w")
        self.cmb_waves = ttk.Combobox(frame_izq, state="readonly", width=36)
        self.cmb_waves.pack(fill="x", pady=2)

        ttk.Label(frame_izq, text="Estrategia de Ruta:").pack(anchor="w")
        self.cmb_estrategia = ttk.Combobox(
            frame_izq,
            values=[
                "Estrategia A - Orden de Llegada",
                "Estrategia B - Cercanía 3D (Greedy)",
                "Estrategia C - Barrido de Pasillos"
            ],
            state="readonly"
        )
        self.cmb_estrategia.set("Estrategia B - Cercanía 3D (Greedy)")
        self.cmb_estrategia.pack(fill="x", pady=2)

        ttk.Button(frame_izq, text="2. Calcular Ruta (Wave Seleccionada)", command=self.cmd_calcular_ruta).pack(fill="x", pady=3)
        ttk.Button(frame_izq, text="👥 Simular Multi-Picker (Simultáneo)", command=self.cmd_calcular_multipicker).pack(fill="x", pady=3)
        ttk.Button(frame_izq, text="📊 Comparar Estrategias", command=self.cmd_comparar_estrategias).pack(fill="x", pady=3)

        ttk.Separator(frame_izq, orient="horizontal").pack(fill="x", pady=8)

        # 3. Controles de Simulación
        ttk.Label(frame_izq, text="Control de Simulación", font=("Arial", 12, "bold")).pack(pady=3)
        frame_sim = ttk.Frame(frame_izq)
        frame_sim.pack(fill="x")
        ttk.Button(frame_sim, text="▶ Iniciar", command=self.cmd_iniciar).grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏸ Pausar", command=self.cmd_pausar).grid(row=0, column=1, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏯ Continuar", command=self.cmd_continuar).grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(frame_sim, text="⏭ Paso a Paso", command=self.cmd_paso).grid(row=1, column=1, sticky="ew", padx=1, pady=1)
        frame_sim.columnconfigure(0, weight=1)
        frame_sim.columnconfigure(1, weight=1)

        ttk.Button(frame_izq, text="🔄 Reiniciar Simulación", command=self.cmd_reiniciar).pack(fill="x", pady=2)

        # 4. Controles de Velocidad y Zoom
        ttk.Label(frame_izq, text="Velocidad (ms por paso):").pack(anchor="w", pady=(6, 0))
        self.scale_vel = ttk.Scale(frame_izq, from_=20, to=800, orient="horizontal", command=self.cmd_cambiar_velocidad)
        self.scale_vel.set(120)
        self.scale_vel.pack(fill="x")

        ttk.Label(frame_izq, text="Zoom (Tamaño de Celda):").pack(anchor="w", pady=(4, 0))
        self.scale_zoom = ttk.Scale(frame_izq, from_=10, to=50, orient="horizontal", command=self.cmd_cambiar_zoom)
        self.scale_zoom.set(self.celda_tam)
        self.scale_zoom.pack(fill="x")

        ttk.Separator(frame_izq, orient="horizontal").pack(fill="x", pady=8)

        # 5. Métricas y Bitácora en Vivo
        self.lbl_metricas = ttk.Label(
            frame_izq,
            text=f"Escenario: {self.warehouse.ancho_x}x{self.warehouse.largo_y}\n"
                 f"Productos: {len(self.warehouse.productos)} | Pedidos: {len(self.warehouse.pedidos)}\n"
                 f"Presione '1. Generar Waves' para comenzar.",
            justify="left", font=("Consolas", 9)
        )
        self.lbl_metricas.pack(fill="x", pady=2)

        ttk.Label(frame_izq, text="Recolecciones y Eventos en Vivo:", font=("Arial", 9, "bold")).pack(anchor="w")
        self.txt_eventos = tk.Text(frame_izq, height=8, width=36, font=("Consolas", 8), state="disabled")
        self.txt_eventos.pack(fill="both", expand=True, pady=2)

        # Panel Derecho: Canvas con Scrollbars
        frame_der = ttk.Frame(self)
        frame_der.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        frame_der.rowconfigure(0, weight=1)
        frame_der.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(frame_der, bg="#e8ecef")
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
        self.txt_eventos.insert(tk.END, texto + "\n")
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

        # 1. Pasillos
        for x in range(self.warehouse.ancho_x):
            for y in range(self.warehouse.largo_y):
                yp = self._y_pantalla(y)
                x1, y1 = x * t, yp * t
                x2, y2 = x1 + t, y1 + t
                tipo = self.warehouse.grilla_tipo.get((x, y), "PASILLO")
                sentido = self.warehouse.grilla_sentido.get((x, y), "AMBOS")

                if tipo == "PASILLO":
                    color_fondo = "#ffffff" if sentido == "AMBOS" else "#f4f8fb"
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill=color_fondo, outline="#dcdcdc")
                    if t >= 16:
                        self.canvas.create_text(
                            x1 + t/2, y1 + t/2, text=simbolos.get(sentido, "·"),
                            fill="#7f8c8d" if sentido != "AMBOS" else "#bdc3c7",
                            font=("Arial", max(6, int(t*0.35)))
                        )

        # 2. Racks
        for rack in self.warehouse.racks:
            for rx, ry in rack.celdas():
                yp = self._y_pantalla(ry)
                self.canvas.create_rectangle(rx * t, yp * t, (rx + 1) * t, (yp + 1) * t, fill="#e67e22", outline="#a04000")
            if t >= 14:
                cx = (rack.x + rack.ancho / 2) * t
                cy = (self._y_pantalla(rack.y + rack.alto - 1) + rack.alto / 2) * t
                self.canvas.create_text(cx, cy, text=rack.id_rack, fill="white", font=("Arial", max(7, int(t*0.35)), "bold"))

        # 3. Zonas de Despacho
        for zona in self.warehouse.zonas_despacho:
            for zx, zy in zona.celdas():
                yp = self._y_pantalla(zy)
                self.canvas.create_rectangle(zx * t, yp * t, (zx + 1) * t, (yp + 1) * t, fill="#27ae60", outline="#1e8449")
            cx = (zona.x + zona.ancho / 2) * t
            cy = (self._y_pantalla(zona.y + zona.alto - 1) + zona.alto / 2) * t
            self.canvas.create_text(cx, cy, text=f"{zona.id_zona}\n({zona.peso_max_kg:.0f}kg)", fill="white", font=("Arial", max(6, int(t*0.26)), "bold"))

        # 4. Puertas (Decorativas sobre bordes)
        for puerta in self.warehouse.puertas:
            yp = self._y_pantalla(puerta.y)
            color_p = "#2980b9" if puerta.tipo == "OUTBOUND" else ("#8e44ad" if puerta.tipo == "INBOUND" else "#16a085")
            self.canvas.create_rectangle(puerta.x * t, yp * t, (puerta.x + 1) * t, (yp + 1) * t, fill=color_p, outline="black", width=2)
            self.canvas.create_text(puerta.x * t + t/2, yp * t + t/2, text="P", fill="white", font=("Arial", max(7, int(t*0.4)), "bold"))

        # 5. Celda de Acceso a Despacho Principal
        dx, dy = self.warehouse.zona_despacho
        dyp = self._y_pantalla(dy)
        self.canvas.create_rectangle(dx*t + 2, dyp*t + 2, (dx+1)*t - 2, (dyp+1)*t - 2, outline="#2ecc71", width=2)

    def _dibujar_productos_waves(self, lista_waves):
        """Dibuja en los racks las Líneas de Recolección de las Waves activas."""
        colores = ["#e74c3c", "#9b59b6", "#3498db", "#1abc9c", "#d35400", "#c0392b"]
        t = self.celda_tam
        self.info_nodos_acceso.clear()

        orden = 1
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
                    r = max(4, int(t * 0.22)) + min(4, prod.z)

                    self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color_w, outline="white", width=1.5)
                    if (ax, ay) not in self.nodos_recogidos and t >= 14:
                        self.canvas.create_text(
                            cx, cy, text=f"z{prod.z}", fill="white",
                            font=("Arial", max(6, int(t * 0.28)), "bold"),
                            tags=f"prod_txt_{ax}_{ay}"
                        )
                    orden += 1

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
            f"{w.id_wave} (Ped:{len(w.pedidos_involucrados)} | {w.total_unidades}u | {w.peso_total:.1f}kg | {w.picker_id})"
            for w in self.waves
        ]
        if self.waves:
            self.cmb_waves.current(0)
            self._registrar_evento(f"✅ {len(self.waves)} Waves generadas (Order Splitting):", limpiar=True)
            for w in self.waves:
                self._registrar_evento(f"• {w.id_wave} [{w.picker_id}]: Ped {w.pedidos_involucrados} ({w.peso_total:.1f}kg)")

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
            "color": "#2980b9",
            "historial": res["camino"],
            "eventos": ["Avanza"] * len(res["camino"]),
            "peso_actual": 0.0,
            "oval_id": None,
            "txt_id": None
        }]

        texto_metricas = (
            f"Modo: 1 Picker ({wave.id_wave})\n"
            f"Pedidos en Wave: {', '.join(wave.pedidos_involucrados)}\n"
            f"Estrategia: {res['estrategia']}\n"
            f"Costo Total (Pasos + Z): {res['distancia']}\n"
            f"Pasos en Planta: {res['aristas_recorridas']} | Costo Z: {res.get('costo_altura_z', 0)}\n"
            f"Nodos Visitados: {res['nodos_visitados']} | Ops: {res.get('operaciones', 0)}\n"
            f"Tiempo Algoritmo: {res['tiempo_ms']:.3f} ms"
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

        colores_pk = ["#2980b9", "#8e44ad", "#c0392b", "#16a085"]
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
            f"Modo: Multi-Picker ({len(self.planes_activos)} operarios)\n"
            f"Pasos Sincronizados: {max_dist}\n"
            f"Desvíos por Camino Alternativo: {total_desvios}\n"
            f"Colisiones ocurridas: 0 (Evitadas sin espera)"
        )
        self.lbl_metricas.config(text=texto_metricas)
        self._registrar_evento(
            f"Multi-Picker listo ({len(self.planes_activos)} pickers activos).\n"
            f"Desvíos calculados: {total_desvios}. Presione ▶ Iniciar.",
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
                plan["oval_id"] = self.canvas.create_oval(
                    x_px + 2, y_px + 2, x_px + t - 2, y_px + t - 2,
                    fill=plan["color"], outline="white", width=2
                )
                plan["txt_id"] = self.canvas.create_text(
                    x_px + t/2, y_px + t/2, text=plan["id_picker"][-2:],
                    fill="white", font=("Arial", max(7, int(t*0.32)), "bold")
                )

    def mover_picker(self):
        if not self.planes_activos:
            self.simulando = False
            return

        max_len = max(len(p["historial"]) for p in self.planes_activos)
        if self.paso_actual >= max_len:
            self.simulando = False
            self._registrar_evento("🏁 Recorrido finalizado y entregado en Zona de Despacho.")
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
                    self._registrar_evento(f"[{plan['id_picker']}] {ped_id}: +{cant_p} {nom_p} ({peso_p:.1f}kg)")

            if idx < len(plan["eventos"]):
                ev = plan["eventos"][idx]
                if "Desvío" in ev or "Maniobra" in ev:
                    self._registrar_evento(f"🔀 [{plan['id_picker']}] {ev} (Paso {self.paso_actual})")

            of = t * 0.36
            self.canvas.create_rectangle(
                x_px + of, y_px + of, x_px + t - of, y_px + t - of,
                fill=plan["color"], outline=""
            )

            if plan["oval_id"]:
                self.canvas.coords(plan["oval_id"], x_px + 2, y_px + 2, x_px + t - 2, y_px + t - 2)
                self.canvas.tag_raise(plan["oval_id"])
            if plan["txt_id"]:
                self.canvas.coords(plan["txt_id"], x_px + t/2, y_px + t/2)
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
        win.title(f"📊 Comparación de Estrategias - {wave.id_wave}")
        win.geometry("760x280+250+200")

        cols = ("Estrategia", "Costo Total (Dist+Z)", "Pasos Planta", "Costo Z", "Nodos Visitados", "Operaciones", "Tiempo (ms)")
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
            text=f"🏆 Mejor Estrategia: {mejor['estrategia']} (Costo Total: {mejor['distancia']})",
            font=("Arial", 11, "bold")
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
                text=f"Escenario: {self.warehouse.ancho_x}x{self.warehouse.largo_y}\n"
                     f"Productos: {len(self.warehouse.productos)} | Pedidos: {len(self.warehouse.pedidos)}"
            )
            self._registrar_evento(f"📂 Escenario cargado desde:\n{ruta}", limpiar=True)
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
            messagebox.showinfo("Guardado exitoso", f"Escenario guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def cmd_ver_inventario(self):
        win = tk.Toplevel(self)
        win.title("📋 Inventario de Productos y Pedidos")
        win.geometry("680x450+300+180")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        tab_p = ttk.Frame(nb)
        nb.add(tab_p, text=f"Productos ({len(self.warehouse.productos)})")
        cols_p = ("ID", "Nombre", "Rack", "Pos (x,y,z)", "Stock", "Peso (kg)")
        tree_p = ttk.Treeview(tab_p, columns=cols_p, show="headings")
        for col in cols_p:
            tree_p.heading(col, text=col)
            tree_p.column(col, width=105, anchor="center")
        for pr in self.warehouse.productos.valores():
            tree_p.insert("", "end", values=(pr.id_prod, pr.nombre, pr.rack_id, f"({pr.x},{pr.y},{pr.z})", pr.stock, pr.peso))
        tree_p.pack(fill="both", expand=True)

        tab_o = ttk.Frame(nb)
        nb.add(tab_o, text=f"Pedidos ({len(self.warehouse.pedidos)})")
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
        tree_o.pack(fill="both", expand=True)

    def cmd_abrir_generador(self):
        if not self.funcion_generador:
            messagebox.showinfo("Aviso", "Generador automático no disponible.")
            return

        win = tk.Toplevel(self)
        win.title("⚙️ Generador Automático de Escenarios")
        win.geometry("360x320+350+220")

        campos = [
            ("Cantidad de Racks:", "4"),
            ("Largo de Racks (Celdas Y):", "8"),
            ("Cantidad de Productos:", "30"),
            ("Cantidad de Pedidos:", "12"),
            ("Máx. Productos por Pedido:", "4"),
            ("Capacidad Wave (Máx. Pedidos):", "3")
        ]
        entradas = {}
        for i, (etiqueta, val_def) in enumerate(campos):
            ttk.Label(win, text=etiqueta).grid(row=i, column=0, padx=10, pady=6, sticky="w")
            ent = ttk.Entry(win, width=10)
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
                self._registrar_evento("⚙️ Nuevo escenario válido generado.", limpiar=True)
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Generar Escenario Válido", command=confirmar).grid(row=len(campos), column=0, columnspan=2, pady=15)