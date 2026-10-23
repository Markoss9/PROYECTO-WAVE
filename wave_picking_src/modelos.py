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

    def __repr__(self):
        return f"Puerta({self.id_puerta}, {self.tipo}, ({self.x},{self.y}))"


class ZonaDespacho(ElementoRectangular):
    def __init__(self, id_zona, puerta_id, x, y, ancho, alto, peso_max_kg=500.0):
        super().__init__(x, y, ancho, alto)
        self.id_zona = str(id_zona)
        self.puerta_id = str(puerta_id)
        self.peso_max_kg = float(peso_max_kg)

    def __repr__(self):
        return f"ZonaDespacho({self.id_zona}, Max:{self.peso_max_kg}kg)"


class Rack(ElementoRectangular):
    def __init__(self, id_rack, x, y, ancho, alto):
        super().__init__(x, y, ancho, alto)
        self.id_rack = str(id_rack)

    def __repr__(self):
        return f"Rack({self.id_rack}, ({self.x},{self.y}), {self.ancho}x{self.alto})"


class Pasillo(ElementoRectangular):
    def __init__(self, id_pasillo, x, y, ancho, alto, sentido="AMBOS"):
        super().__init__(x, y, ancho, alto)
        self.id_pasillo = str(id_pasillo)
        self.sentido = str(sentido).upper()  # N, S, E, O, AMBOS

    def __repr__(self):
        return f"Pasillo({self.id_pasillo}, Sentido:{self.sentido})"


class Picker:
    def __init__(self, id_picker, x_inicial, y_inicial, capacidad_carga_kg=150.0):
        self.id_picker = str(id_picker)
        self.x_inicial = int(x_inicial)
        self.y_inicial = int(y_inicial)
        self.capacidad_carga_kg = float(capacidad_carga_kg)

    @property
    def posicion_inicial(self):
        return (self.x_inicial, self.y_inicial)

    def __repr__(self):
        return f"Picker({self.id_picker}, Cap:{self.capacidad_carga_kg}kg)"


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

    def __repr__(self):
        return f"Prod({self.id_prod}, {self.nombre}, ({self.x},{self.y},{self.z}), {self.peso}kg)"


class ItemPedido:
    """Representa un ítem dentro de un pedido con control de saldo pendiente."""
    def __init__(self, producto_id, cantidad):
        self.producto_id = str(producto_id)
        self.cantidad_total = int(cantidad)
        self.cantidad_pendiente = int(cantidad)

    @property
    def completado(self):
        return self.cantidad_pendiente <= 0


class Pedido:
    """Pedido con soporte para fraccionamiento (Order Splitting)."""
    def __init__(self, id_pedido, prioridad, estado="PENDIENTE"):
        self.id_pedido = str(id_pedido)
        self.prioridad = int(prioridad)
        self.estado = str(estado).upper()  # PENDIENTE, PARCIAL, PREPARADO
        self.items = []  # Lista de ItemPedido

    def agregar_producto(self, id_prod, cantidad):
        self.items.append(ItemPedido(id_prod, cantidad))

    @property
    def productos(self):
        """Propiedad de compatibilidad con código anterior."""
        return [{'id': it.producto_id, 'cantidad': it.cantidad_total} for it in self.items]

    def unidades_pendientes(self):
        return sum(it.cantidad_pendiente for it in self.items)

    def unidades_totales(self):
        return sum(it.cantidad_total for it in self.items)

    def calcular_peso_pendiente(self, tabla_productos):
        peso = 0.0
        for it in self.items:
            if it.cantidad_pendiente > 0:
                prod = tabla_productos.obtener(it.producto_id)
                if prod is not None:
                    peso += prod.peso * it.cantidad_pendiente
        return peso

    def actualizar_estado(self):
        pend = self.unidades_pendientes()
        if pend == 0:
            self.estado = "PREPARADO"
        elif pend < self.unidades_totales():
            self.estado = "PARCIAL"
        else:
            self.estado = "PENDIENTE"

    def __repr__(self):
        return f"Pedido({self.id_pedido}, Prio:{self.prioridad}, Estado:{self.estado}, Pend:{self.unidades_pendientes()})"


class LineaRecoleccion:
    """Tarea atómica de recolección para una Wave."""
    def __init__(self, pedido_id, producto_id, cantidad, peso_unitario):
        self.pedido_id = str(pedido_id)
        self.producto_id = str(producto_id)
        self.cantidad = int(cantidad)
        self.peso_unitario = float(peso_unitario)

    @property
    def peso_total(self):
        return self.cantidad * self.peso_unitario


class Wave:
    """Wave basada en líneas de recolección (Order Splitting)."""
    def __init__(self, id_wave, picker_id=None, zona_despacho_id=None):
        self.id_wave = str(id_wave)
        self.picker_id = picker_id
        self.zona_despacho_id = zona_despacho_id
        self.lineas = []  # Lista de LineaRecoleccion
        self.peso_total = 0.0
        self.total_unidades = 0

    def agregar_linea(self, linea):
        self.lineas.append(linea)
        self.peso_total += linea.peso_total
        self.total_unidades += linea.cantidad

    @property
    def pedidos_involucrados(self):
        """Devuelve los IDs únicos de pedidos presentes en esta wave."""
        return list(dict.fromkeys(l.pedido_id for l in self.lineas))

    def __repr__(self):
        return f"Wave({self.id_wave}, Unidades:{self.total_unidades}, Peso:{self.peso_total:.2f}kg, Picker:{self.picker_id})"