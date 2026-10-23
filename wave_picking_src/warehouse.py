"""
Módulo del Warehouse
Modelado de la estructura física, grilla celular y Grafo Dirigido (Unidad 4).
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
        self.largo = self.largo_y
        self.num_pasillos = max(1, self.ancho_x // 3)

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

        self.zona_despacho = self.obtener_acceso_zona_despacho()

    def _movimiento_permitido(self, s_orig, s_dest, dir_mov):
        if dir_mov == "N" and (s_orig == "S" or s_dest == "S"): return False
        if dir_mov == "S" and (s_orig == "N" or s_dest == "N"): return False
        if dir_mov == "E" and (s_orig == "O" or s_dest == "O"): return False
        if dir_mov == "O" and (s_orig == "E" or s_dest == "E"): return False
        return True

    def obtener_acceso_zona_despacho(self):
        if not self.zonas_despacho:
            return self.grafo.nodos[0] if self.grafo.nodos else (0, 0)
        zona = self.zonas_despacho[0]
        cx, cy = zona.x + zona.ancho // 2, zona.y + zona.alto
        if self.grilla_tipo.get((cx, cy)) == "PASILLO":
            return (cx, cy)
        for x in range(zona.x, zona.x + zona.ancho):
            for ny in (zona.y + zona.alto, zona.y - 1):
                if self.grilla_tipo.get((x, ny)) == "PASILLO":
                    return (x, ny)
        return self.grafo.nodos[0] if self.grafo.nodos else (0, 0)

    def obtener_nodo_acceso(self, x, y):
        if self.grilla_tipo.get((x, y)) == "PASILLO":
            return (x, y)
        for rack in self.racks:
            if rack.contiene_celda(x, y):
                if rack.ancho == 2:
                    cand = (x - 1, y) if x == rack.x else (x + 1, y)
                    if self.grilla_tipo.get(cand) == "PASILLO":
                        return cand
                elif rack.alto == 2:
                    cand = (x, y - 1) if y == rack.y else (x, y + 1)
                    if self.grilla_tipo.get(cand) == "PASILLO":
                        return cand
        for nx, ny in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if self.grilla_tipo.get((nx, ny)) == "PASILLO":
                return (nx, ny)
        return (x, y)

    def registrar_producto(self, prod):
        self.productos.insertar(prod.id_prod, prod)

    def registrar_pedido(self, ped):
        self.pedidos.insertar(ped.id_pedido, ped)