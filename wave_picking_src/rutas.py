"""
Módulo de Ruteo y Estrategias de Recorrido (Unidades 4 y 6)
- Algoritmo de Dijkstra con caché sobre Grafo Dirigido y bloqueo dinámico de nodos.
- Reconstrucción de caminos mínimos.
- Pathfinding (Estrategias A, B y C) con costo vertical Z y descarga en la Zona de Despacho más cercana.
"""
import time
from estructuras import ColaPrioridad, TablaHash, merge_sort


def dijkstra(grafo, inicio, nodos_bloqueados=None):
    """
    Algoritmo de Dijkstra sobre Grafo Dirigido (Unidad 4).
    Utiliza caché del grafo cuando no hay nodos bloqueados para velocidad instantánea.
    """
    if not nodos_bloqueados:
        if not hasattr(grafo, '_cache_dijkstra'):
            grafo._cache_dijkstra = {}
        if inicio in grafo._cache_dijkstra:
            dist, prev, ops = grafo._cache_dijkstra[inicio]
            grafo.ultimas_operaciones = ops
            return dist, prev

    cap = max(257, len(grafo.nodos) * 2)
    distancias = TablaHash(cap)
    previos = TablaHash(cap)
    visitados = TablaHash(cap)

    bloqueados = set(nodos_bloqueados) if nodos_bloqueados else set()
    operaciones = 0

    distancias.insertar(inicio, 0)
    pq = ColaPrioridad()
    pq.insertar(0, inicio)
    operaciones += 1

    while not pq.esta_vacia():
        dist_actual, nodo_actual = pq.extraer_min()
        operaciones += 1

        if visitados.contiene(nodo_actual):
            continue
        visitados.insertar(nodo_actual, True)

        vecinos = grafo.adj.obtener(nodo_actual)
        if vecinos:
            for vecino, peso in vecinos:
                operaciones += 1
                if vecino in bloqueados or visitados.contiene(vecino):
                    continue

                nueva_dist = dist_actual + peso
                if nueva_dist < distancias.obtener(vecino, float('inf')):
                    distancias.insertar(vecino, nueva_dist)
                    previos.insertar(vecino, nodo_actual)
                    pq.insertar(nueva_dist, vecino)
                    operaciones += 1

    grafo.ultimas_operaciones = operaciones
    if not nodos_bloqueados:
        grafo._cache_dijkstra[inicio] = (distancias, previos, operaciones)

    return distancias, previos


def reconstruir_camino(previos, inicio, fin):
    """Reconstruye el camino mínimo desde 'inicio' hasta 'fin'."""
    if inicio == fin:
        return [inicio]
    camino = []
    actual = fin
    limite = max(len(previos) + 5, 1000)

    while actual is not None and limite > 0:
        camino.append(actual)
        if actual == inicio:
            break
        actual = previos.obtener(actual)
        limite -= 1

    camino.reverse()
    if not camino or camino[0] != inicio:
        return []
    return camino


class Pathfinding:
    """
    Estrategias de Recorrido (A, B y C) con costo vertical Z y descarga automática
    en la Zona de Despacho más cercana (Secciones 8, 9 y 10).
    """

    @staticmethod
    def obtener_celdas_acceso_zona(warehouse, zona):
        """Devuelve todas las celdas de pasillo válidas ortogonalmente adyacentes a una ZonaDespacho."""
        celdas = []
        for x in range(zona.x, zona.x + zona.ancho):
            for ny in (zona.y + zona.alto, zona.y - 1):
                if warehouse.es_nodo_valido((x, ny)):
                    celdas.append((x, ny))
        for y in range(zona.y, zona.y + zona.alto):
            for nx in (zona.x - 1, zona.x + zona.ancho):
                if warehouse.es_nodo_valido((nx, y)):
                    celdas.append((nx, y))
        return celdas if celdas else [warehouse.zona_despacho]

    @staticmethod
    def obtener_acceso_zona(warehouse, zona):
        celdas = Pathfinding.obtener_celdas_acceso_zona(warehouse, zona)
        cx = zona.x + zona.ancho // 2
        celdas.sort(key=lambda c: (0 if c[1] >= zona.y + zona.alto else 1, abs(c[0] - cx)))
        return celdas[0]

    @staticmethod
    def obtener_zona_despacho_mas_cercana(warehouse, distancias_dijkstra, peso_lote=0.0):
        zonas = getattr(warehouse, 'zonas_despacho', [])
        if not zonas:
            return warehouse.zona_despacho, "ZONA_A"

        cap_dinamica = getattr(warehouse, '_cap_restante_zonas', None)
        if cap_dinamica:
            candidatas = [z for z in zonas if cap_dinamica.get(z.id_zona, z.peso_max_kg) >= peso_lote]
        else:
            candidatas = [z for z in zonas if z.peso_max_kg >= peso_lote]

        if not candidatas:
            candidatas = zonas

        mejor_nodo = warehouse.zona_despacho
        mejor_id = candidatas[0].id_zona
        mejor_dist = float('inf')

        for z in candidatas:
            for nodo_z in Pathfinding.obtener_celdas_acceso_zona(warehouse, z):
                d = distancias_dijkstra.obtener(nodo_z, float('inf'))
                if d < mejor_dist:
                    mejor_dist = d
                    mejor_nodo = nodo_z
                    mejor_id = z.id_zona

        return mejor_nodo, mejor_id

    @staticmethod
    def _extraer_objetivos_wave(warehouse, wave):
        ubicaciones_orden = []
        z_por_coord = {}

        for linea in getattr(wave, 'lineas', []):
            prod = warehouse.productos.obtener(linea.producto_id)
            if prod is not None:
                coord = (prod.x, prod.y)
                if coord not in z_por_coord:
                    ubicaciones_orden.append(coord)
                    z_por_coord[coord] = prod.z
                else:
                    z_por_coord[coord] = max(z_por_coord[coord], prod.z)

        return ubicaciones_orden, z_por_coord

    @staticmethod
    def _consultar_dijkstra(grafo, origen, cache_local, contador_ops):
        if origen not in cache_local:
            dist, prev = dijkstra(grafo, origen)
            cache_local[origen] = (dist, prev)
            contador_ops[0] += getattr(grafo, 'ultimas_operaciones', 0)
        return cache_local[origen]

    @staticmethod
    def _recorrer_lista_destinos(warehouse, coords_ordenadas, z_por_coord,
                                 nombre_estrategia, peso_wave=0.0, pos_inicio=None):
        t0 = time.perf_counter()
        cache_local = {}
        contador_ops = [0]

        actual = pos_inicio if pos_inicio is not None else warehouse.zona_despacho
        if not warehouse.es_nodo_valido(actual):
            actual = warehouse.obtener_nodo_acceso(actual[0], actual[1])

        camino_total = [actual]
        costo_altura_z = 0

        for coord in coords_ordenadas:
            nodo_acceso = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            costo_altura_z += max(0, z_por_coord.get(coord, 1) - 1)

            if actual != nodo_acceso:
                _, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_local, contador_ops)
                tramo = reconstruir_camino(previos, actual, nodo_acceso)
                if len(tramo) > 1:
                    camino_total.extend(tramo[1:])
                    actual = nodo_acceso

        dist_final, previos_final = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_local, contador_ops)
        nodo_despacho, id_zona = Pathfinding.obtener_zona_despacho_mas_cercana(warehouse, dist_final, peso_wave)

        if actual != nodo_despacho:
            tramo_ret = reconstruir_camino(previos_final, actual, nodo_despacho)
            if len(tramo_ret) > 1:
                camino_total.extend(tramo_ret[1:])

        t1 = time.perf_counter()
        pasos_planta = len(camino_total) - 1 if camino_total else 0

        return {
            "estrategia": nombre_estrategia,
            "camino": camino_total,
            "distancia": pasos_planta + costo_altura_z,
            "aristas_recorridas": pasos_planta,
            "costo_altura_z": costo_altura_z,
            "nodos_visitados": len(set(camino_total)),
            "operaciones": contador_ops[0],
            "tiempo_ms": (t1 - t0) * 1000.0,
            "zona_despacho_id": id_zona,
            "nodo_despacho": nodo_despacho
        }

    @staticmethod
    def estrategia_a_orden_pedidos(warehouse, wave, peso_max_picker=None, pos_inicio=None):
        """Estrategia A: Visita las ubicaciones en el orden exacto en que aparecen en los pedidos."""
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)
        return Pathfinding._recorrer_lista_destinos(
            warehouse, ubicaciones_orden, z_por_coord,
            "A - Orden de los Pedidos", getattr(wave, 'peso_total', 0.0), pos_inicio
        )

    @staticmethod
    def estrategia_b_cercania(warehouse, wave, peso_max_picker=None, pos_inicio=None):
        """Estrategia B: En cada paso selecciona la ubicación no visitada a menor distancia 3D (Grafo + Z)."""
        t0 = time.perf_counter()
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)
        pendientes = list(ubicaciones_orden)

        cache_local = {}
        contador_ops = [0]

        actual = pos_inicio if pos_inicio is not None else warehouse.zona_despacho
        if not warehouse.es_nodo_valido(actual):
            actual = warehouse.obtener_nodo_acceso(actual[0], actual[1])

        camino_total = [actual]
        costo_altura_z = 0

        while pendientes:
            distancias, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_local, contador_ops)

            mejor_coord = None
            mejor_costo_3d = float('inf')

            for coord in pendientes:
                acceso = warehouse.obtener_nodo_acceso(coord[0], coord[1])
                d_planta = distancias.obtener(acceso, float('inf'))
                penalizacion_z = max(0, z_por_coord.get(coord, 1) - 1)
                costo_3d = d_planta + penalizacion_z

                if costo_3d < mejor_costo_3d:
                    mejor_costo_3d = costo_3d
                    mejor_coord = coord

            if mejor_coord is None:
                mejor_coord = pendientes[0]

            acceso_dest = warehouse.obtener_nodo_acceso(mejor_coord[0], mejor_coord[1])
            if actual != acceso_dest:
                tramo = reconstruir_camino(previos, actual, acceso_dest)
                if len(tramo) > 1:
                    camino_total.extend(tramo[1:])
                    actual = acceso_dest

            costo_altura_z += max(0, z_por_coord.get(mejor_coord, 1) - 1)
            pendientes.remove(mejor_coord)

        dist_final, previos_final = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_local, contador_ops)
        nodo_despacho, id_zona = Pathfinding.obtener_zona_despacho_mas_cercana(
            warehouse, dist_final, getattr(wave, 'peso_total', 0.0)
        )

        if actual != nodo_despacho:
            tramo_ret = reconstruir_camino(previos_final, actual, nodo_despacho)
            if len(tramo_ret) > 1:
                camino_total.extend(tramo_ret[1:])

        t1 = time.perf_counter()
        pasos_planta = len(camino_total) - 1 if camino_total else 0

        return {
            "estrategia": "B - Cercanía 3D (Greedy)",
            "camino": camino_total,
            "distancia": pasos_planta + costo_altura_z,
            "aristas_recorridas": pasos_planta,
            "costo_altura_z": costo_altura_z,
            "nodos_visitados": len(set(camino_total)),
            "operaciones": contador_ops[0],
            "tiempo_ms": (t1 - t0) * 1000.0,
            "zona_despacho_id": id_zona,
            "nodo_despacho": nodo_despacho
        }

    @staticmethod
    def estrategia_c_pasillos(warehouse, wave, peso_max_picker=None, pos_inicio=None):
        """
        Estrategia C (Barrido por Pasillos / S-Shape):
        Agrupa los productos por el pasillo que los atiende (tomando ambas caras del pasillo
        en una sola pasada gracias al desplazamiento lateral permitido en Sección 3.5)
        y ordena el avance a favor del sentido del pasillo (vertical: N -> +y, S -> -y;
        horizontal: E -> +x, O -> -x).
        """
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)

        def clave_pasillo(coord):
            ax, ay = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            sentido = warehouse.grilla_sentido.get((ax, ay), "AMBOS")
            es_horizontal = sentido in ("E", "O")
            id_pas_x = ax // 4
            bloque_y = ay // 4
            for pas in warehouse.pasillos:
                if pas.contiene_celda(ax, ay):
                    id_pas_x = pas.x
                    bloque_y = pas.y
                    if sentido == "AMBOS":
                        es_horizontal = pas.ancho > pas.alto
                    break
            if es_horizontal:
                orden_avance = -ax if sentido == "O" else ax
                return (bloque_y, id_pas_x, orden_avance, z_por_coord.get(coord, 1))
            orden_avance = -ay if sentido == "S" else ay
            return (bloque_y, id_pas_x, orden_avance, z_por_coord.get(coord, 1))

        ordenadas = merge_sort(ubicaciones_orden, key=clave_pasillo)
        return Pathfinding._recorrer_lista_destinos(
            warehouse, ordenadas, z_por_coord,
            "C - Barrido de Pasillos", getattr(wave, 'peso_total', 0.0), pos_inicio
        )

