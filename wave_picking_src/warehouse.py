"""
Módulo del Warehouse
Modelado de la estructura física usando grafos (Unidad 4).
"""
from estructuras import TablaHash

class GrafoWarehouse:
    """
    Grafo no dirigido para representar los pasillos del Warehouse (Unidad 4).
    Nodos: Coordenadas (x, y) de los pasillos.
    Aristas: Conexiones entre nodos adyacentes de pasillo con peso de distancia.
    """
    def __init__(self):
        self.adj = TablaHash(1000) # Lista de adyacencia usando TablaHash propia
        self.nodos = []

    def agregar_nodo(self, nodo):
        if not self.adj.contiene(nodo):
            self.adj.insertar(nodo, [])
            self.nodos.append(nodo)

    def agregar_arista(self, u, v, peso=1):
        """Agrega una arista no dirigida entre u y v."""
        self.adj.obtener(u).append((v, peso))
        self.adj.obtener(v).append((u, peso))

class Warehouse:
    """
    Representación del Almacén, inventario, pedidos y zonas de despacho.
    """
    def __init__(self, num_pasillos, largo_pasillo):
        self.num_pasillos = num_pasillos
        self.largo = largo_pasillo
        self.grafo = GrafoWarehouse()
        self.productos = TablaHash(500)
        self.pedidos = TablaHash(500)
        self.zona_despacho = (0, 0)
        
        self._construir_grafo()

    def _construir_grafo(self):
        """
        Construye el grafo en base a una cuadrícula (grid).
        Los pasillos de movimiento se encuentran en x = 0, 3, 6, etc.
        Los racks se ubican en los espacios intermedios (x = 1, 2).
        """
        ancho_total = self.num_pasillos * 3
        
        # 1. Crear nodos y conexiones verticales (dentro del mismo pasillo)
        for x in range(0, ancho_total, 3):
            for y in range(self.largo):
                self.grafo.agregar_nodo((x, y))
                if y > 0:
                    self.grafo.agregar_arista((x, y-1), (x, y))

        # 2. Crear pasillos transversales (conexiones horizontales en extremos)
        # Permiten al picker cambiar de pasillo por arriba o por abajo.
        for x in range(0, ancho_total - 3, 3):
            # Transversal superior (y = 0)
            self.grafo.agregar_nodo((x+1, 0))
            self.grafo.agregar_nodo((x+2, 0))
            self.grafo.agregar_arista((x, 0), (x+1, 0))
            self.grafo.agregar_arista((x+1, 0), (x+2, 0))
            self.grafo.agregar_arista((x+2, 0), (x+3, 0))

            # Transversal inferior (y = largo - 1)
            self.grafo.agregar_nodo((x+1, self.largo-1))
            self.grafo.agregar_nodo((x+2, self.largo-1))
            self.grafo.agregar_arista((x, self.largo-1), (x+1, self.largo-1))
            self.grafo.agregar_arista((x+1, self.largo-1), (x+2, self.largo-1))
            self.grafo.agregar_arista((x+2, self.largo-1), (x+3, self.largo-1))

        # 3. Definir zona de despacho en el punto central del transversal inferior
        centro_x = ((ancho_total // 2) // 3) * 3
        self.zona_despacho = (centro_x, self.largo - 1)

    def obtener_nodo_acceso(self, x, y):
        """
        Dado un rack en (x, y), retorna el nodo del pasillo adyacente para poder accederlo.
        """
        if x % 3 == 1:
            return (x - 1, y) # El pasillo está a la izquierda
        if x % 3 == 2:
            ancho_total = self.num_pasillos * 3
            if x + 1 >= ancho_total:
                return (x - 2, y) # No hay pasillo a la derecha, acceder por la izquierda
            return (x + 1, y) # El pasillo está a la derecha
        return (x, y) # Ya es una coordenada de pasillo

    def registrar_producto(self, prod):
        self.productos.insertar(prod.id_prod, prod)

    def registrar_pedido(self, ped):
        self.pedidos.insertar(ped.id_pedido, ped)
