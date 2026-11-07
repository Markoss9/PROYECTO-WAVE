"""
Módulo del Warehouse
Modelado de la estructura física, grafo dirigido de circulación, grilla celular
y validación formal de restricciones estructurales y operativas.
"""
from estructuras import TablaHash


class GrafoWarehouse:
    """Grafo DIRIGIDO para representar los pasillos del Warehouse y sus sentidos."""
    def __init__(self, capacidad=3007):
        self.adj = TablaHash(capacidad)
        self.nodos = []

    def agregar_nodo(self, nodo):
        if not self.adj.contiene(nodo):
            self.adj.insertar(nodo, [])
            self.nodos.append(nodo)

    def agregar_arista(self, u, v, peso=1):
        vecinos = self.adj.obtener(u)
        if vecinos is not None and (v, peso) not in vecinos:
            vecinos.append((v, peso))


class Warehouse:
    """Representación geométrica y lógica del Almacén, inventario y pedidos."""
    def __init__(self, ancho_x=18, largo_y=16):
        self.ancho_x = int(ancho_x)
        self.largo_y = int(largo_y)

        self.grafo = GrafoWarehouse(max(3007, self.ancho_x * self.largo_y * 2))
        self.productos = TablaHash(1009)
        self.pedidos = TablaHash(1009)

        self.puertas = []
        self.zonas_despacho = []
        self.racks = []
        self.pasillos = []
        self.pickers = []

        self.wave_max_pedidos = 3
        self.wave_max_productos = 15

        self.grilla_tipo = {}
        self.grilla_sentido = {}
        self.nodos_transitables = set()
        self.zona_despacho = (0, 0)

    def construir_estructura(self):
        self.grafo = GrafoWarehouse(max(3007, self.ancho_x * self.largo_y * 2))
        self.grilla_tipo.clear()
        self.grilla_sentido.clear()

        for x in range(self.ancho_x):
            for y in range(self.largo_y):
                self.grilla_tipo[(x, y)] = "PASILLO"
                self.grilla_sentido[(x, y)] = "AMBOS"

        for pas in self.pasillos:
            for x in range(pas.x, pas.x + pas.ancho):
                for y in range(pas.y, pas.y + pas.alto):
                    if 0 <= x < self.ancho_x and 0 <= y < self.largo_y:
                        self.grilla_sentido[(x, y)] = pas.sentido

        for rack in self.racks:
            for x, y in rack.celdas():
                if 0 <= x < self.ancho_x and 0 <= y < self.largo_y:
                    self.grilla_tipo[(x, y)] = "RACK"

        for zona in self.zonas_despacho:
            for x, y in zona.celdas():
                if 0 <= x < self.ancho_x and 0 <= y < self.largo_y:
                    self.grilla_tipo[(x, y)] = "ZONA_DESPACHO"

        for puerta in self.puertas:
            if 0 <= puerta.x < self.ancho_x and 0 <= puerta.y < self.largo_y:
                self.grilla_tipo[(puerta.x, puerta.y)] = "PUERTA"

        for (x, y), tipo in self.grilla_tipo.items():
            if tipo == "PASILLO":
                self.grafo.agregar_nodo((x, y))

        for (x, y) in self.grafo.nodos:
            s_orig = self.grilla_sentido[(x, y)]
            for nx, ny, dir_mov in [(x, y+1, "N"), (x, y-1, "S"), (x+1, y, "E"), (x-1, y, "O")]:
                if self.grilla_tipo.get((nx, ny)) != "PASILLO":
                    continue
                s_dest = self.grilla_sentido[(nx, ny)]
                if self._movimiento_permitido(s_orig, s_dest, dir_mov):
                    self.grafo.agregar_arista((x, y), (nx, ny), peso=1)

        self._asegurar_conectividad_fuerte()
        self.zona_despacho = self.obtener_acceso_zona_despacho()

    def _movimiento_permitido(self, s_orig, s_dest, dir_mov):
        if dir_mov == "N" and (s_orig == "S" or s_dest == "S"): return False
        if dir_mov == "S" and (s_orig == "N" or s_dest == "N"): return False
        if dir_mov == "E" and (s_orig == "O" or s_dest == "O"): return False
        if dir_mov == "O" and (s_orig == "E" or s_dest == "E"): return False
        return True

    def _asegurar_conectividad_fuerte(self):
        """
        Verifica que los pasillos formen una red fuertemente conexa (con entrada y salida)
        y destraba esquinas donde dos pasillos de mano única choquen contra un borde.
        """
        if not self.grafo.nodos:
            return

        # Elegir semilla en el pasillo principal (posición del primer picker)
        semilla = self.grafo.nodos[0]
        if self.pickers:
            pos_pk = (self.pickers[0].x_inicial, self.pickers[0].y_inicial)
            if self.grafo.adj.contiene(pos_pk):
                semilla = pos_pk

        for _ in range(4):
            # 1. Nodos alcanzables desde la semilla (BFS hacia adelante)
            alc_adelante = {semilla}
            cola = [semilla]
            while cola:
                curr = cola.pop(0)
                for vec, _ in (self.grafo.adj.obtener(curr) or []):
                    if vec not in alc_adelante:
                        alc_adelante.add(vec)
                        cola.append(vec)

            # 2. Nodos que pueden volver a la semilla (BFS hacia atrás)
            inv = {n: [] for n in self.grafo.nodos}
            for u in self.grafo.nodos:
                for v, _ in (self.grafo.adj.obtener(u) or []):
                    inv[v].append(u)

            alc_atras = {semilla}
            cola = [semilla]
            while cola:
                curr = cola.pop(0)
                for orig in inv.get(curr, []):
                    if orig not in alc_atras:
                        alc_atras.add(orig)
                        cola.append(orig)

            fuertes = alc_adelante & alc_atras
            self.nodos_transitables = fuertes

            # Si algún nodo alcanzable quedó atrapado sin salida (pozo), abrir giro en su frontera
            trampas = (alc_adelante ^ alc_atras)
            if not trampas:
                break

            for (x, y) in trampas:
                for nx, ny in [(x, y+1), (x, y-1), (x+1, y), (x-1, y)]:
                    if (nx, ny) in fuertes or (nx, ny) in trampas:
                        self.grafo.agregar_arista((x, y), (nx, ny), peso=1)
                        self.grafo.agregar_arista((nx, ny), (x, y), peso=1)

    def es_nodo_valido(self, coord):
        if self.nodos_transitables:
            return coord in self.nodos_transitables
        return self.grafo.adj.contiene(coord)

    def obtener_acceso_zona_despacho(self):
        if not self.zonas_despacho:
            return next(iter(self.nodos_transitables)) if self.nodos_transitables else (0, 0)
        zona = self.zonas_despacho[0]
        # Priorizar el pasillo superior de la zona de despacho (hacia el interior del almacén)
        cx = zona.x + zona.ancho // 2
        for ny in (zona.y + zona.alto, zona.y - 1):
            if self.es_nodo_valido((cx, ny)):
                return (cx, ny)
        for x in range(zona.x, zona.x + zona.ancho):
            for ny in (zona.y + zona.alto, zona.y - 1):
                if self.es_nodo_valido((x, ny)):
                    return (x, ny)
        return next(iter(self.nodos_transitables)) if self.nodos_transitables else (0, 0)

    def obtener_nodo_acceso(self, x, y):
        """
        Determina la celda de pasillo adyacente desde la cual se accede al rack (Sección 3.2 y 3.6).
        Garantiza que la celda devuelta pertenezca a la red fuertemente conexa.
        """
        if self.es_nodo_valido((x, y)):
            return (x, y)

        for rack in self.racks:
            if rack.contiene_celda(x, y):
                if rack.ancho > rack.alto and rack.alto == 2:
                    # Rack horizontal: se accede desde las calles horizontales inferior o superior
                    cand = (x, y - 1) if y == rack.y else (x, y + 1)
                    if self.es_nodo_valido(cand):
                        return cand
                elif rack.ancho == 2:
                    # Rack vertical (o 2x2): se accede desde las calles verticales izquierda o derecha
                    cand = (x - 1, y) if x == rack.x else (x + 1, y)
                    if self.es_nodo_valido(cand):
                        return cand

        # Buscar en los 4 vecinos ortogonales adyacentes (y en espiral si fuera un rack especial)
        for radio in range(1, 6):
            for dx in range(-radio, radio + 1):
                for dy in range(-radio, radio + 1):
                    if abs(dx) + abs(dy) == radio:
                        cand = (x + dx, y + dy)
                        if self.es_nodo_valido(cand):
                            return cand

        return self.zona_despacho

    def registrar_producto(self, prod):
        self.productos.insertar(prod.id_prod, prod)

    def registrar_pedido(self, ped):
        self.pedidos.insertar(ped.id_pedido, ped)

    def obtener_pedidos_por_producto(self):
        """
        Retorna un diccionario {id_prod: [(id_pedido, cantidad_total, prioridad, estado), ...]}
        indicando a qué pedido(s) pertenece cada producto del almacén.
        """
        mapa = {}
        for ped in self.pedidos.valores():
            for item in ped.items:
                mapa.setdefault(item.producto_id, []).append(
                    (ped.id_pedido, item.cantidad_total, ped.prioridad, ped.estado)
                )
        return mapa

    def _celda_acceso_estricta(self, x, y, nodos_validos):
        """Obtiene la celda de pasillo adyacente desde la cual se accede a una celda (x, y) de un rack."""
        if (x, y) in nodos_validos:
            return (x, y)
        for rack in self.racks:
            if rack.contiene_celda(x, y):
                if rack.ancho > rack.alto and rack.alto == 2:
                    cand = (x, y - 1) if y == rack.y else (x, y + 1)
                    if cand in nodos_validos:
                        return cand
                elif rack.ancho == 2:
                    cand = (x - 1, y) if x == rack.x else (x + 1, y)
                    if cand in nodos_validos:
                        return cand
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            cand = (x + dx, y + dy)
            if cand in nodos_validos:
                return cand
        return None

    def validar_escenario(self):
        """
        Verifica formalmente que el Warehouse cumpla todas las restricciones estructurales y operativas:
        1. Todos los elementos están dentro de las dimensiones del Warehouse y no se solapan.
        2. Todos los racks tienen un lado de valor 2.
        3. Todas las puertas están sobre el borde.
        4. Frente a cada puerta hay una zona de despacho.
        5. Todos los productos están ubicados dentro de un rack.
        6. Las ubicaciones requeridas pueden ser alcanzadas desde la zona de despacho
           (y regresar a ella) respetando el sentido de circulación de los pasillos.
        """
        errores = []
        checks_ok = []

        # 1. Elementos dentro de los límites y sin solapamientos
        ocupacion = {}
        fuera_de_rango = False
        solapamientos = []

        def registrar_celda(cx, cy, etiqueta):
            nonlocal fuera_de_rango
            if not (0 <= cx < self.ancho_x and 0 <= cy < self.largo_y):
                fuera_de_rango = True
                errores.append(f"Elemento {etiqueta} fuera de límites en ({cx}, {cy}).")
                return
            prev = ocupacion.get((cx, cy))
            if prev is not None and prev != etiqueta:
                solapamientos.append(f"Solapamiento en ({cx}, {cy}) entre {prev} y {etiqueta}.")
            else:
                ocupacion[(cx, cy)] = etiqueta

        for p in self.puertas:
            registrar_celda(p.x, p.y, f"Puerta:{p.id_puerta}")
        for z in self.zonas_despacho:
            for cx, cy in z.celdas():
                registrar_celda(cx, cy, f"Zona:{z.id_zona}")
        for r in self.racks:
            for cx, cy in r.celdas():
                registrar_celda(cx, cy, f"Rack:{r.id_rack}")
        for pas in self.pasillos:
            for cx, cy in pas.celdas():
                registrar_celda(cx, cy, f"Pasillo:{pas.id_pasillo}")

        if solapamientos:
            errores.extend(solapamientos[:5])
        if not fuera_de_rango and not solapamientos:
            checks_ok.append(
                f"✔ Todos los elementos ({len(self.racks)} racks, {len(self.pasillos)} pasillos, "
                f"{len(self.zonas_despacho)} zonas, {len(self.puertas)} puertas) están dentro de "
                f"{self.ancho_x}x{self.largo_y} y sin solapamientos."
            )
