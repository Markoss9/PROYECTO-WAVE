"""
Módulo de Estructuras de Datos
Contiene las implementaciones requeridas por el programa de la materia (Unidad 2, 3 y 6).
Se evitan librerías avanzadas, implementando la lógica manualmente.
"""

class NodoHash:
    """Nodo para manejar colisiones en la Tabla Hash por encadenamiento."""
    def __init__(self, clave, valor):
        self.clave = clave
        self.valor = valor
        self.siguiente = None

class TablaHash:
    """
    Implementación de Diccionario con Tabla Hash (Unidad 3).
    Utiliza redireccionamiento abierto/encadenamiento para las colisiones.
    """
    def __init__(self, capacidad=100):
        self.capacidad = capacidad
        self.tamano = 0
        self.tabla = [None] * capacidad

    def _hash(self, clave):
        """Función hash simple para strings e ints."""
        h = 0
        for char in str(clave):
            h = (h * 31 + ord(char)) % self.capacidad
        return h

    def insertar(self, clave, valor):
        """Inserta o actualiza un valor en la tabla."""
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual:
            if actual.clave == clave:
                actual.valor = valor
                return
            actual = actual.siguiente
        nuevo_nodo = NodoHash(clave, valor)
        nuevo_nodo.siguiente = self.tabla[indice]
        self.tabla[indice] = nuevo_nodo
        self.tamano += 1

    def obtener(self, clave):
        """Devuelve el valor asociado a la clave, o None si no existe."""
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual:
            if actual.clave == clave:
                return actual.valor
            actual = actual.siguiente
        return None

    def contiene(self, clave):
        """Verifica si la clave existe en la tabla."""
        return self.obtener(clave) is not None

    def valores(self):
        """Retorna una lista con todos los valores almacenados."""
        resultado = []
        for nodo in self.tabla:
            actual = nodo
            while actual:
                resultado.append(actual.valor)
                actual = actual.siguiente
        return resultado

class ColaPrioridad:
    """
    Implementación de Min-Heap para la Cola de Prioridad del Algoritmo de Dijkstra (Unidad 2/4).
    """
    def __init__(self):
        self.heap = []

    def _padre(self, i): return (i - 1) // 2
    def _hijo_izq(self, i): return 2 * i + 1
    def _hijo_der(self, i): return 2 * i + 2

    def insertar(self, prioridad, elemento):
        """Inserta un elemento manteniendo la propiedad de min-heap."""
        self.heap.append((prioridad, elemento))
        self._flotar(len(self.heap) - 1)

    def extraer_min(self):
        """Extrae el elemento con la menor prioridad."""
        if not self.heap: return None
        if len(self.heap) == 1: return self.heap.pop()
        raiz = self.heap[0]
        self.heap[0] = self.heap.pop()
        self._hundir(0)
        return raiz

    def _flotar(self, i):
        while i > 0 and self.heap[self._padre(i)][0] > self.heap[i][0]:
            p = self._padre(i)
            self.heap[i], self.heap[p] = self.heap[p], self.heap[i]
            i = p

    def _hundir(self, i):
        min_idx = i
        izq = self._hijo_izq(i)
        der = self._hijo_der(i)
        n = len(self.heap)
        
        if izq < n and self.heap[izq][0] < self.heap[min_idx][0]:
            min_idx = izq
        if der < n and self.heap[der][0] < self.heap[min_idx][0]:
            min_idx = der
            
        if min_idx != i:
            self.heap[i], self.heap[min_idx] = self.heap[min_idx], self.heap[i]
            self._hundir(min_idx)

    def esta_vacia(self):
        return len(self.heap) == 0

def merge_sort(lista, key=lambda x: x, reverso=False):
    """
    Algoritmo de ordenamiento Divide y Vencerás (Unidad 6).
    """
    if len(lista) <= 1:
        return lista
    
    medio = len(lista) // 2
    izq = merge_sort(lista[:medio], key, reverso)
    der = merge_sort(lista[medio:], key, reverso)
    
    return _merge(izq, der, key, reverso)

def _merge(izq, der, key, reverso):
    resultado = []
    i = j = 0
    while i < len(izq) and j < len(der):
        val_izq = key(izq[i])
        val_der = key(der[j])
        
        condicion = val_izq >= val_der if reverso else val_izq <= val_der
        
        if condicion:
            resultado.append(izq[i])
            i += 1
        else:
            resultado.append(der[j])
            j += 1
            
    resultado.extend(izq[i:])
    resultado.extend(der[j:])
    return resultado
