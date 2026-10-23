"""
Módulo de Estructuras de Datos (Unidades 2, 3 y 6)
Implementaciones propias de Tabla Hash auto-redimensionable,
Cola de Prioridad (Min-Heap) y Merge Sort.
"""

class NodoHash:
    """Nodo para manejar colisiones en la Tabla Hash por encadenamiento."""
    __slots__ = ('clave', 'valor', 'siguiente')

    def __init__(self, clave, valor, siguiente=None):
        self.clave = clave
        self.valor = valor
        self.siguiente = siguiente


class TablaHash:
    """
    Diccionario con Tabla Hash auto-redimensionable (Unidad 3).
    Mantiene factor de carga <= 0.75 para garantizar operaciones O(1) promedio.
    """
    def __init__(self, capacidad_inicial=1031):
        self.capacidad = max(11, capacidad_inicial)
        self.tamano = 0
        self.tabla = [None] * self.capacidad

    def _hash(self, clave):
        """Dispersión rápida para tuplas (x, y) y polinómica para strings/enteros."""
        if isinstance(clave, tuple) and len(clave) == 2:
            return ((clave[0] * 73856093) ^ (clave[1] * 19349663)) % self.capacidad
        if isinstance(clave, int):
            return (clave * 2654435761) % self.capacidad

        h = 0
        for char in str(clave):
            h = (h * 31 + ord(char)) % self.capacidad
        return h

    def _redimensionar(self):
        """Duplica la capacidad de la tabla cuando supera el 75% de ocupación."""
        tabla_vieja = self.tabla
        self.capacidad = (self.capacidad * 2) + 1
        self.tabla = [None] * self.capacidad
        self.tamano = 0

        for nodo in tabla_vieja:
            actual = nodo
            while actual is not None:
                self._insertar_sin_redimensionar(actual.clave, actual.valor)
                actual = actual.siguiente

    def _insertar_sin_redimensionar(self, clave, valor):
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual is not None:
            if actual.clave == clave:
                actual.valor = valor
                return
            actual = actual.siguiente
        self.tabla[indice] = NodoHash(clave, valor, self.tabla[indice])
        self.tamano += 1

    def insertar(self, clave, valor):
        """Inserta o actualiza un valor, redimensionando si es necesario."""
        if self.tamano >= self.capacidad * 0.75:
            self._redimensionar()
        self._insertar_sin_redimensionar(clave, valor)

    def obtener(self, clave, por_defecto=None):
        """Devuelve el valor asociado a la clave, o por_defecto si no existe."""
        indice = self._hash(clave)
        actual = self.tabla[indice]
        while actual is not None:
            if actual.clave == clave:
                return actual.valor
            actual = actual.siguiente
        return por_defecto

    def eliminar(self, clave):
        """Elimina una clave de la tabla si existe."""
        indice = self._hash(clave)
        actual = self.tabla[indice]
        previo = None
        while actual is not None:
            if actual.clave == clave:
                if previo is None:
                    self.tabla[indice] = actual.siguiente
                else:
                    previo.siguiente = actual.siguiente
                self.tamano -= 1
                return True
            previo = actual
            actual = actual.siguiente
        return False

    def contiene(self, clave):
        return self.obtener(clave) is not None

    def valores(self):
        """Retorna una lista con todos los valores almacenados."""
        resultado = []
        for nodo in self.tabla:
            actual = nodo
            while actual is not None:
                resultado.append(actual.valor)
                actual = actual.siguiente
        return resultado

    def claves(self):
        """Retorna una lista con todas las claves almacenadas."""
        resultado = []
        for nodo in self.tabla:
            actual = nodo
            while actual is not None:
                resultado.append(actual.clave)
                actual = actual.siguiente
        return resultado

    def __len__(self):
        return self.tamano

    def __contains__(self, clave):
        return self.contiene(clave)


class ColaPrioridad:
    """Implementación de Min-Heap binario para Dijkstra (Unidad 2 y 4)."""
    def __init__(self):
        self.heap = []

    def insertar(self, prioridad, elemento):
        self.heap.append((prioridad, elemento))
        self._flotar(len(self.heap) - 1)

    def extraer_min(self):
        if not self.heap:
            return None
        if len(self.heap) == 1:
            return self.heap.pop()
        raiz = self.heap[0]
        self.heap[0] = self.heap.pop()
        self._hundir(0)
        return raiz

    def _flotar(self, i):
        heap = self.heap
        while i > 0:
            padre = (i - 1) // 2
            if heap[padre][0] > heap[i][0]:
                heap[i], heap[padre] = heap[padre], heap[i]
                i = padre
            else:
                break

    def _hundir(self, i):
        heap = self.heap
        n = len(heap)
        while True:
            min_idx = i
            izq = 2 * i + 1
            der = 2 * i + 2

            if izq < n and heap[izq][0] < heap[min_idx][0]:
                min_idx = izq
            if der < n and heap[der][0] < heap[min_idx][0]:
                min_idx = der

            if min_idx != i:
                heap[i], heap[min_idx] = heap[min_idx], heap[i]
                i = min_idx
            else:
                break

    def esta_vacia(self):
        return len(self.heap) == 0

    def __len__(self):
        return len(self.heap)


def merge_sort(lista, key=lambda x: x, reverso=False):
    """Algoritmo de ordenamiento Divide y Vencerás en O(N log N) (Unidad 6)."""
    if len(lista) <= 1:
        return lista

    medio = len(lista) // 2
    izq = merge_sort(lista[:medio], key, reverso)
    der = merge_sort(lista[medio:], key, reverso)

    return _merge(izq, der, key, reverso)


def _merge(izq, der, key, reverso):
    resultado = []
    i = j = 0
    len_izq, len_der = len(izq), len(der)

    while i < len_izq and j < len_der:
        val_izq = key(izq[i])
        val_der = key(der[j])
        condicion = (val_izq >= val_der) if reverso else (val_izq <= val_der)
        if condicion:
            resultado.append(izq[i])
            i += 1
        else:
            resultado.append(der[j])
            j += 1

    if i < len_izq:
        resultado.extend(izq[i:])
    if j < len_der:
        resultado.extend(der[j:])
    return resultado