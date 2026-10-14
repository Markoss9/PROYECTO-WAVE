"""
Módulo de Modelos de Dominio
Contiene las clases Producto, Pedido y Wave.
"""

class Producto:
    def __init__(self, id_prod, nombre, x, y, z, stock, peso=1.0):
        self.id_prod = id_prod
        self.nombre = nombre
        self.x = x
        self.y = y
        self.z = z
        self.stock = stock
        self.peso = peso

    def __repr__(self):
        return f"Prod({self.id_prod}, {self.nombre})"

class Pedido:
    def __init__(self, id_pedido, prioridad):
        self.id_pedido = id_pedido
        self.productos = []  # Lista de dicts: {'id': id_prod, 'cantidad': cant}
        self.prioridad = prioridad
        self.estado = "PENDIENTE" # PENDIENTE, EN_WAVE, EN_PREPARACION, PREPARADO

    def agregar_producto(self, id_prod, cantidad):
        self.productos.append({'id': id_prod, 'cantidad': cantidad})

    def __repr__(self):
        return f"Pedido({self.id_pedido}, Prio:{self.prioridad})"

class Wave:
    def __init__(self, id_wave):
        self.id_wave = id_wave
        self.pedidos = []

    def agregar_pedido(self, pedido):
        self.pedidos.append(pedido)
        pedido.estado = "EN_WAVE"

    def __repr__(self):
        return f"Wave({self.id_wave}, Pedidos:{len(self.pedidos)})"
