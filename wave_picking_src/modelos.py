"""
Módulo de Modelos de Dominio
Entidades físicas del Warehouse y modelos lógicos de Pedidos y Waves con Order Splitting.
"""


class ElementoRectangular:
    """Clase base geométrica para racks, pasillos y zonas."""
    def __init__(self, x, y, ancho, alto):
        self.x = int(x)
        self.y = int(y)
        self.ancho = int(ancho)
        self.alto = int(alto)

    def contiene_celda(self, cx, cy):
        return (self.x <= cx < self.x + self.ancho) and (self.y <= cy < self.y + self.alto)

    def celdas(self):
        for ix in range(self.x, self.x + self.ancho):
            for iy in range(self.y, self.y + self.alto):
                yield (ix, iy)


class Puerta:
    def __init__(self, id_puerta, tipo, x, y):
        self.id_puerta = str(id_puerta)
        self.tipo = str(tipo).upper()  # INBOUND, OUTBOUND, AMBOS
        self.x = int(x)
        self.y = int(y)


class ZonaDespacho(ElementoRectangular):
    def __init__(self, id_zona, puerta_id, x, y, ancho, alto, peso_max_kg=500.0):
        super().__init__(x, y, ancho, alto)
        self.id_zona = str(id_zona)
        self.puerta_id = str(puerta_id)
        self.peso_max_kg = float(peso_max_kg)


class Rack(ElementoRectangular):
    def __init__(self, id_rack, x, y, ancho, alto):
        super().__init__(x, y, ancho, alto)
        self.id_rack = str(id_rack)


class Pasillo(ElementoRectangular):
    def __init__(self, id_pasillo, x, y, ancho, alto, sentido="AMBOS"):
        super().__init__(x, y, ancho, alto)
        self.id_pasillo = str(id_pasillo)
        self.sentido = str(sentido).upper()  # N, S, E, O, AMBOS


class Picker:
    def __init__(self, id_picker, x_inicial, y_inicial, capacidad_carga_kg=150.0):
        self.id_picker = str(id_picker)
        self.x_inicial = int(x_inicial)
        self.y_inicial = int(y_inicial)
        self.capacidad_carga_kg = float(capacidad_carga_kg)


class Producto:
    def __init__(self, id_prod, nombre, x, y, z, stock, peso=1.0, rack_id=None):
        self.id_prod = str(id_prod)
        self.nombre = str(nombre)
        self.rack_id = str(rack_id) if rack_id is not None else None
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.stock = int(stock)
        self.peso = float(peso)


class ItemPedido:
    """Representa un ítem dentro de un pedido con control de saldo pendiente."""
    def __init__(self, producto_id, cantidad):
        self.producto_id = str(producto_id)
        self.cantidad_total = int(cantidad)
        self.cantidad_pendiente = int(cantidad)


class Pedido:
    """Pedido con soporte para fraccionamiento (Order Splitting)."""
    def __init__(self, id_pedido, prioridad, estado="PENDIENTE"):
        self.id_pedido = str(id_pedido)
        self.prioridad = int(prioridad)
        self.estado = str(estado).upper()
        self.items = []

    def agregar_producto(self, id_prod, cantidad):
        self.items.append(ItemPedido(id_prod, cantidad))

    @property
    def productos(self):
        return [{'id': it.producto_id, 'cantidad': it.cantidad_total} for it in self.items]

    def unidades_pendientes(self):
        return sum(it.cantidad_pendiente for it in self.items)

    def unidades_totales(self):
        return sum(it.cantidad_total for it in self.items)


class LineaRecoleccion:
    """Tarea atómica de recolección para una Wave, asociada a un Picker según su zona."""
    def __init__(self, pedido_id, producto_id, cantidad, peso_unitario, picker_id=None):
        self.pedido_id = str(pedido_id)
        self.producto_id = str(producto_id)
        self.cantidad = int(cantidad)
        self.peso_unitario = float(peso_unitario)
        self.picker_id = picker_id

    @property
    def peso_total(self):
        return self.cantidad * self.peso_unitario


class Wave:
    """Wave basada en líneas de recolección con asignación zonal por Picker."""
    def __init__(self, id_wave, picker_id=None, zona_despacho_id=None):
        self.id_wave = str(id_wave)
        self.picker_id = picker_id
        self.zona_despacho_id = zona_despacho_id
        self.lineas = []
        self.peso_total = 0.0
        self.total_unidades = 0
        self.sublistas_pickers = {}  # {picker_id: [LineaRecoleccion, ...]}

    def agregar_linea(self, linea):
        self.lineas.append(linea)
        self.peso_total += linea.peso_total
        self.total_unidades += linea.cantidad
        if linea.picker_id:
            self.sublistas_pickers.setdefault(linea.picker_id, []).append(linea)

    @property
    def pedidos_involucrados(self):
        """Devuelve los IDs únicos de pedidos presentes en esta wave."""
        return list(dict.fromkeys(l.pedido_id for l in self.lineas))
