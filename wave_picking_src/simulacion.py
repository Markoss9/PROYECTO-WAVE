"""
Módulo de Simulación Interactiva
Aplicación Visual utilizando Tkinter para visualizar el Warehouse, Waves y Recorridos.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from algoritmos import WaveManager, Pathfinding

class AppVisual(tk.Tk):
    def __init__(self, warehouse):
        super().__init__()
        self.title("Simulador Wave Picking - Algoritmos II")
        self.warehouse = warehouse
        self.waves = []
        
        # Configuración visual
        self.celda_tam = 25
        self.ancho_canvas = (self.warehouse.num_pasillos * 3) * self.celda_tam
        self.alto_canvas = self.warehouse.largo * self.celda_tam
        
        self.camino_actual = []
        self.paso_actual = 0
        self.simulando = False
        self.pausado = False
        self.vel_simulacion = 0.1 # Segundos por paso
        self.nodos_recogidos = set()
        self.peso_actual_picker = 0.0
        self.pesos_pendientes = {}
        
        # Permitir redimensionar ventana
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        
        self._construir_ui()
        self._dibujar_warehouse()
        
    def _construir_ui(self):
        # Panel Izquierdo: Controles
        frame_ctrl = ttk.Frame(self, padding="10")
        frame_ctrl.grid(row=0, column=0, sticky="ns")
        
        ttk.Label(frame_ctrl, text="Controles de Simulación", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Botones Generar Waves
        ttk.Button(frame_ctrl, text="Generar Waves", command=self.cmd_generar_waves).pack(fill="x", pady=5)
        
        self.cmb_waves = ttk.Combobox(frame_ctrl, state="readonly")
        self.cmb_waves.pack(fill="x", pady=5)
        
        self.cmb_estrategia = ttk.Combobox(frame_ctrl, values=["Estrategia A - Orden", "Estrategia B - Cercanía", "Estrategia C - Pasillos"], state="readonly")
        self.cmb_estrategia.set("Estrategia A - Orden")
        self.cmb_estrategia.pack(fill="x", pady=5)
        
        ttk.Button(frame_ctrl, text="Calcular Ruta", command=self.cmd_calcular_ruta).pack(fill="x", pady=5)
        ttk.Button(frame_ctrl, text="📊 Comparar Estrategias", command=self.cmd_comparar_estrategias).pack(fill="x", pady=5)
        
        ttk.Separator(frame_ctrl, orient="horizontal").pack(fill="x", pady=15)
        
        ttk.Button(frame_ctrl, text="▶ Iniciar", command=self.cmd_iniciar).pack(fill="x", pady=2)
        ttk.Button(frame_ctrl, text="⏸ Pausar", command=self.cmd_pausar).pack(fill="x", pady=2)
        ttk.Button(frame_ctrl, text="⏯ Continuar", command=self.cmd_continuar).pack(fill="x", pady=2)
        ttk.Button(frame_ctrl, text="⏭ Paso a Paso", command=self.cmd_paso).pack(fill="x", pady=2)
        ttk.Button(frame_ctrl, text="🔄 Reiniciar", command=self.cmd_reiniciar).pack(fill="x", pady=2)
        
        # Métricas
        ttk.Separator(frame_ctrl, orient="horizontal").pack(fill="x", pady=15)
        self.lbl_metricas = ttk.Label(frame_ctrl, text="Métricas:\n-", justify="left")
        self.lbl_metricas.pack(fill="x")
        
        # Controles Adicionales (Zoom y Velocidad)
        ttk.Separator(frame_ctrl, orient="horizontal").pack(fill="x", pady=15)
        
        ttk.Label(frame_ctrl, text="Velocidad:").pack(anchor="w")
        self.scale_vel = ttk.Scale(frame_ctrl, from_=10, to=1000, orient="horizontal", command=self.cmd_cambiar_velocidad)
        self.scale_vel.set(100)
        self.scale_vel.pack(fill="x", pady=2)
        
        ttk.Label(frame_ctrl, text="Zoom (Tam. Celda):").pack(anchor="w")
        self.scale_zoom = ttk.Scale(frame_ctrl, from_=15, to=60, orient="horizontal", command=self.cmd_cambiar_zoom)
        self.scale_zoom.set(25)
        self.scale_zoom.pack(fill="x", pady=2)
        
        # Panel Derecho: Canvas
        self.canvas = tk.Canvas(self, width=self.ancho_canvas, height=self.alto_canvas, bg="lightgray")
        self.canvas.grid(row=0, column=1, padx=10, pady=10)
        
        # Elemento visual del picker
        self.picker_id = None
        self.picker_text_id = None
        
    def _dibujar_warehouse(self):
        self.canvas.delete("all")
        
        # Dibujar Cuadrícula y Racks
        for x in range(self.warehouse.num_pasillos * 3):
            for y in range(self.warehouse.largo):
                x1, y1 = x * self.celda_tam, y * self.celda_tam
                x2, y2 = x1 + self.celda_tam, y1 + self.celda_tam
                
                # Zonas
                color = "white" # Pasillo libre
                if x % 3 != 0 and 0 < y < self.warehouse.largo - 1:
                    color = "orange" # Racks
                
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="gray")
                
        # Zona Despacho
        dx, dy = self.warehouse.zona_despacho
        self.canvas.create_rectangle(dx*self.celda_tam, dy*self.celda_tam, 
                                     (dx+1)*self.celda_tam, (dy+1)*self.celda_tam, 
                                     fill="green")
        self.canvas.create_text(dx*self.celda_tam+12, dy*self.celda_tam+12, text="D", fill="white")

    def _dibujar_puntos_rojos(self, wave):
        colores = ["red", "blue", "green", "purple", "cyan", "magenta", "orange", "darkblue", "brown", "pink"]
        
        # Agrupar por coordenada
        ubicaciones = {}
        
        color_idx = 0
        orden_global = 1
        for pedido in wave.pedidos:
            color_pedido = colores[color_idx % len(colores)]
            color_idx += 1
            
            for prod_info in pedido.productos:
                prod = self.warehouse.productos.obtener(prod_info['id'])
                if prod:
                    coord = (prod.x, prod.y)
                    if coord not in ubicaciones:
                        ubicaciones[coord] = {
                            'orden': orden_global,
                            'color': color_pedido,
                            'z': getattr(prod, 'z', 1)
                        }
                        orden_global += 1
                        
        for (px, py), info in ubicaciones.items():
            ax, ay = self.warehouse.obtener_nodo_acceso(px, py)
            cx = px * self.celda_tam + self.celda_tam / 2
            cy = py * self.celda_tam + self.celda_tam / 2
            
            # El radio base depende del tamaño de la celda. Multiplicamos por Z para dar efecto de altura.
            radio_base = max(4, int(self.celda_tam * 0.15))
            r = radio_base + (info['z'] * 2) # A mayor Z, más grande el círculo
            
            font_size = max(6, int(self.celda_tam * 0.3))
            
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=info['color'], outline="black")
            
            if (ax, ay) not in self.nodos_recogidos:
                self.canvas.create_text(cx, cy, text=str(info['orden']), fill="white", font=("Arial", font_size, "bold"), tags=f"prod_txt_{ax}_{ay}")

    def cmd_cambiar_velocidad(self, val):
        self.vel_simulacion = float(val) / 1000.0

    def cmd_cambiar_zoom(self, val):
        nuevo_tam = int(float(val))
        if nuevo_tam != self.celda_tam:
            self.celda_tam = nuevo_tam
            self.ancho_canvas = (self.warehouse.num_pasillos * 3) * self.celda_tam
            self.alto_canvas = self.warehouse.largo * self.celda_tam
            self.canvas.config(width=self.ancho_canvas, height=self.alto_canvas)
            
            self._dibujar_warehouse()
            
            idx = self.cmb_waves.current()
            if idx != -1 and self.waves:
                self._dibujar_puntos_rojos(self.waves[idx])
                
            # Repintar rastro si ya hay ruta calculada
            for i in range(self.paso_actual):
                nx, ny = self.camino_actual[i]
                x_px, y_px = nx * self.celda_tam, ny * self.celda_tam
                of = self.celda_tam * 0.4
                self.canvas.create_rectangle(x_px+of, y_px+of, x_px+self.celda_tam-of, y_px+self.celda_tam-of, fill="lightblue", outline="")
                
            # Repintar picker actual
            if self.camino_actual:
                curr_paso = min(self.paso_actual, len(self.camino_actual) - 1)
                cx, cy = self.camino_actual[curr_paso]
                x_px, y_px = cx * self.celda_tam, cy * self.celda_tam
                self.picker_id = self.canvas.create_oval(x_px+5, y_px+5, x_px+self.celda_tam-5, y_px+self.celda_tam-5, fill="blue")
                if hasattr(self, 'peso_actual_picker'):
                    self.picker_text_id = self.canvas.create_text(x_px+self.celda_tam/2, y_px+self.celda_tam/2, text=f"{self.peso_actual_picker:.1f}", fill="white", font=("Arial", 8, "bold"))

    def cmd_generar_waves(self):
        pedidos = self.warehouse.pedidos.valores()
        if not pedidos:
            messagebox.showwarning("Atención", "No hay pedidos cargados.")
            return
            
        self.waves = WaveManager.generar_waves(pedidos, self.warehouse, capacidad_max_pedidos=3, peso_max_wave=50.0)
        self.cmb_waves['values'] = [w.id_wave for w in self.waves]
        if self.waves:
            self.cmb_waves.current(0)
            messagebox.showinfo("Éxito", f"Se generaron {len(self.waves)} waves.\nRevisa la consola para el reporte.")

    def cmd_calcular_ruta(self):
        if not self.waves: return
        idx = self.cmb_waves.current()
        if idx == -1: return
        
        wave = self.waves[idx]
        
        est = self.cmb_estrategia.get()
        if "Estrategia A" in est or "A -" in est:
            res = Pathfinding.estrategia_a_orden_pedidos(self.warehouse, wave)
        elif "Estrategia B" in est or "B -" in est:
            res = Pathfinding.estrategia_b_cercania(self.warehouse, wave)
        elif "Estrategia C" in est or "C -" in est:
            res = Pathfinding.estrategia_c_pasillos(self.warehouse, wave)
        else:
            res = Pathfinding.estrategia_b_cercania(self.warehouse, wave)
            
        self.camino_actual = res["camino"]
        self.paso_actual = 0
        self.nodos_recogidos = set()
        self._dibujar_warehouse() # Limpiar ruta previa del canvas
        self._dibujar_puntos_rojos(wave)
        
        texto_metricas = (f"Estrategia: {res['estrategia']}\n"
                          f"Distancia Total: {res['distancia']}\n"
                          f"Nodos Visitados: {res['nodos_visitados']}\n"
                          f"Tiempo de Ejecución:\n{res['tiempo_ms']:.3f} ms")
        self.lbl_metricas.config(text=texto_metricas)
        
        # Calcular pesos requeridos por nodo de acceso
        self.pesos_pendientes = {}
        for pedido in wave.pedidos:
            for prod_info in pedido.productos:
                prod = self.warehouse.productos.obtener(prod_info['id'])
                if prod:
                    ax, ay = self.warehouse.obtener_nodo_acceso(prod.x, prod.y)
                    self.pesos_pendientes[(ax, ay)] = self.pesos_pendientes.get((ax, ay), 0.0) + getattr(prod, 'peso', 1.0)
        
        self.peso_actual_picker = 0.0
        
        # Posicionar picker inicial
        if self.camino_actual:
            ix, iy = self.camino_actual[0]
            x_px, y_px = ix * self.celda_tam, iy * self.celda_tam
            self.picker_id = self.canvas.create_oval(x_px+5, y_px+5, x_px+self.celda_tam-5, y_px+self.celda_tam-5, fill="blue")
            self.picker_text_id = self.canvas.create_text(x_px+self.celda_tam/2, y_px+self.celda_tam/2, text="0.0", fill="white", font=("Arial", 8, "bold"))

    def mover_picker(self):
        if not self.camino_actual or self.paso_actual >= len(self.camino_actual):
            self.simulando = False
            return
            
        nx, ny = self.camino_actual[self.paso_actual]
        x_px, y_px = nx * self.celda_tam, ny * self.celda_tam
        
        # Descarga al llegar a la zona de despacho
        if (nx, ny) == self.warehouse.zona_despacho:
            self.peso_actual_picker = 0.0
            
        # Sumar peso si recogemos en este nodo
        if (nx, ny) in self.pesos_pendientes and (nx, ny) not in self.nodos_recogidos:
            self.peso_actual_picker += self.pesos_pendientes[(nx, ny)]
        
        # Marcar productos recogidos eliminando solo su número
        self.nodos_recogidos.add((nx, ny))
        self.canvas.delete(f"prod_txt_{nx}_{ny}")
        
        # Dejar rastro (breadcrumbs)
        of = self.celda_tam * 0.4
        self.canvas.create_rectangle(x_px+of, y_px+of, x_px+self.celda_tam-of, y_px+self.celda_tam-of, fill="lightblue", outline="")
        
        # Mover picker (círculo azul) al frente
        if self.picker_id:
            self.canvas.coords(self.picker_id, x_px+5, y_px+5, x_px+self.celda_tam-5, y_px+self.celda_tam-5)
            self.canvas.tag_raise(self.picker_id)
            
        # Mover texto de carga al frente
        if self.picker_text_id:
            self.canvas.coords(self.picker_text_id, x_px+self.celda_tam/2, y_px+self.celda_tam/2)
            self.canvas.itemconfig(self.picker_text_id, text=f"{self.peso_actual_picker:.1f}")
            self.canvas.tag_raise(self.picker_text_id)
        
        self.paso_actual += 1
        
        if self.simulando and not self.pausado:
            self.after(int(self.vel_simulacion * 1000), self.mover_picker)

    def cmd_iniciar(self):
        if self.camino_actual and not self.simulando:
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
        if self.camino_actual:
            self.simulando = False
            self.mover_picker()

    def cmd_reiniciar(self):
        self.simulando = False
        self.pausado = False
        self.paso_actual = 0
        self.cmd_calcular_ruta() # Reinicia calculando y redibujando todo

    def cmd_comparar_estrategias(self):
        if not self.waves:
            messagebox.showwarning("Atención", "No hay waves generadas.")
            return
        
        idx = self.cmb_waves.current()
        if idx == -1: return
        wave = self.waves[idx]
        
        res_a = Pathfinding.estrategia_a_orden_pedidos(self.warehouse, wave)
        res_b = Pathfinding.estrategia_b_cercania(self.warehouse, wave)
        res_c = Pathfinding.estrategia_c_pasillos(self.warehouse, wave)
        
        win = tk.Toplevel(self)
        win.title("📊 Comparación de Estrategias")
        win.geometry("550x250")
        
        cols = ("Estrategia", "Distancia", "Nodos Visitados", "Tiempo (ms)")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=130, anchor="center")
            
        tree.insert("", "end", values=("A (Orden Inteligente)", res_a['distancia'], res_a['nodos_visitados'], f"{res_a['tiempo_ms']:.3f}"))
        tree.insert("", "end", values=("B (Cercanía Greedy)", res_b['distancia'], res_b['nodos_visitados'], f"{res_b['tiempo_ms']:.3f}"))
        tree.insert("", "end", values=("C (Por Pasillos)", res_c['distancia'], res_c['nodos_visitados'], f"{res_c['tiempo_ms']:.3f}"))
        
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        mejor_res = min([res_a, res_b, res_c], key=lambda x: x['distancia'])
        ganador = mejor_res['estrategia']
        ttk.Label(win, text=f"🏆 Mejor estrategia para esta Wave: {ganador}", font=("Arial", 12, "bold")).pack(pady=10)
