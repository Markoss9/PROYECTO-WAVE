"""
Módulo de Algoritmos (Unidad 4 y 6)
Contiene Dijkstra, generación de Waves (Divide & Conquer/Greedy) y estrategias de recorrido.
"""
from estructuras import ColaPrioridad, TablaHash, merge_sort
from modelos import Wave
import time

def dijkstra(grafo, inicio):
    """
    Algoritmo de Dijkstra (Unidad 4).
    Calcula los caminos mínimos desde el nodo 'inicio' al resto del grafo.
    Devuelve la tabla de distancias y la de previos para reconstruir rutas.
    """
    distancias = TablaHash(1000)
    previos = TablaHash(1000)
    
    for nodo in grafo.nodos:
        distancias.insertar(nodo, float('inf'))
        previos.insertar(nodo, None)
        
    distancias.insertar(inicio, 0)
    pq = ColaPrioridad()
    pq.insertar(0, inicio)
    
    visitados = TablaHash(1000)
    
    while not pq.esta_vacia():
        dist_actual, nodo_actual = pq.extraer_min()
        
        if visitados.contiene(nodo_actual): 
            continue
            
        visitados.insertar(nodo_actual, True)
        
        vecinos = grafo.adj.obtener(nodo_actual)
        if vecinos:
            for vecino, peso in vecinos:
                if visitados.contiene(vecino): 
                    continue
                
                nueva_dist = dist_actual + peso
                if nueva_dist < distancias.obtener(vecino):
                    distancias.insertar(vecino, nueva_dist)
                    previos.insertar(vecino, nodo_actual)
                    pq.insertar(nueva_dist, vecino)
                    
    return distancias, previos

def reconstruir_camino(previos, inicio, fin):
    """Reconstruye el camino desde el inicio hasta el fin utilizando la tabla de previos."""
    camino = []
    actual = fin
    while actual is not None:
        camino.append(actual)
        if actual == inicio: break
        actual = previos.obtener(actual)
        
    camino.reverse()
    if not camino or camino[0] != inicio:
        return [] # No hay camino válido
    return camino

class WaveManager:
    """Clase encargada de gestionar y generar las Waves."""
    @staticmethod
    def generar_waves(pedidos, warehouse, capacidad_max_pedidos, peso_max_wave=50.0):
        """
        Estrategia Greedy (Unidad 6):
        Ordena los pedidos pendientes por prioridad y los agrupa secuencialmente en Waves,
        considerando el límite de capacidad de pedidos y el límite de peso total de la Wave.
        """
        pendientes = [p for p in pedidos if p.estado == "PENDIENTE"]
        
        # Ordenamiento Divide y Vencerás (Merge Sort) basado en prioridad (descendente)
        pendientes_ordenados = merge_sort(pendientes, key=lambda p: p.prioridad, reverso=True)
        
        def obtener_peso_pedido(pedido):
            peso = 0
            for p_info in pedido.productos:
                prod = warehouse.productos.obtener(p_info['id'])
                if prod:
                    peso += getattr(prod, 'peso', 1.0) # asume cant = 1 o usa el peso base por producto
            return peso

        waves = []
        id_wave = 1
        wave_actual = Wave(f"W{id_wave}")
        peso_actual_wave = 0.0
        
        print("\n=== REPORTE DE GENERACIÓN DE WAVES ===")
        
        for pedido in pendientes_ordenados:
            peso_pedido = obtener_peso_pedido(pedido)
            
            # Si el pedido entra en la wave (por num de pedidos y peso) o si la wave esta vacia (para evitar estancamiento)
            if len(wave_actual.pedidos) == 0 or (len(wave_actual.pedidos) < capacidad_max_pedidos and (peso_actual_wave + peso_pedido) <= peso_max_wave):
                wave_actual.agregar_pedido(pedido)
                peso_actual_wave += peso_pedido
            else:
                waves.append(wave_actual)
                
                # Imprimir Reporte
                print(f"Wave {wave_actual.id_wave} | Pedidos: {len(wave_actual.pedidos)} | Peso Total: {peso_actual_wave:.2f}")
                for ped in wave_actual.pedidos:
                    print(f"  -> Pedido {ped.id_pedido} | Prioridad: {ped.prioridad} | Peso: {obtener_peso_pedido(ped):.2f}")
                    for p_info in ped.productos:
                        prod = warehouse.productos.obtener(p_info['id'])
                        print(f"      - {prod.nombre} (ID: {prod.id_prod}) [Peso/u: {getattr(prod, 'peso', 1.0):.2f}]")
                
                id_wave += 1
                wave_actual = Wave(f"W{id_wave}")
                wave_actual.agregar_pedido(pedido)
                peso_actual_wave = peso_pedido
                
        if len(wave_actual.pedidos) > 0:
            waves.append(wave_actual)
            print(f"Wave {wave_actual.id_wave} | Pedidos: {len(wave_actual.pedidos)} | Peso Total: {peso_actual_wave:.2f}")
            for ped in wave_actual.pedidos:
                print(f"  -> Pedido {ped.id_pedido} | Prioridad: {ped.prioridad} | Peso: {obtener_peso_pedido(ped):.2f}")
                for p_info in ped.productos:
                    prod = warehouse.productos.obtener(p_info['id'])
                    print(f"      - {prod.nombre} (ID: {prod.id_prod}) [Peso/u: {getattr(prod, 'peso', 1.0):.2f}]")
                    
        print("======================================\n")
        return waves

class Pathfinding:
    """Clase con las estrategias de recorrido obligatorias por la cátedra."""
    
    @staticmethod
    def estrategia_a_orden_pedidos(warehouse, wave, peso_max_picker=20.0):
        """
        Estrategia A (Orden de los pedidos mejorada con límite de peso): 
        Busca el destino en orden numérico, recogiendo de paso. Si el límite
        de peso se supera, regresa a la zona de despacho a descargar.
        """
        inicio_tiempo = time.perf_counter()
        nodos_visitados_totales = 0
        
        camino_total = []
        actual = warehouse.zona_despacho
        camino_total.append(actual)
        
        ubicaciones_info = {} # coord -> total peso
        ubicaciones_orden = [] # mantener el orden
        for pedido in wave.pedidos:
            for prod_info in pedido.productos:
                prod = warehouse.productos.obtener(prod_info['id'])
                if prod:
                    coord = (prod.x, prod.y)
                    if coord not in ubicaciones_info:
                        ubicaciones_info[coord] = 0
                        ubicaciones_orden.append(coord)
                    ubicaciones_info[coord] += getattr(prod, 'peso', 1.0)
                        
        destinos_pendientes = {} # coord -> acceso
        for coord in ubicaciones_orden:
            destinos_pendientes[coord] = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            
        peso_actual = 0.0
        
        for coord in ubicaciones_orden:
            if coord not in destinos_pendientes:
                continue # Ya fue recogido "de paso"
                
            destino = destinos_pendientes[coord]
            peso_requerido = ubicaciones_info[coord]
            
            # 1. Retorno a despacho si supera capacidad
            if peso_actual + peso_requerido > peso_max_picker and actual != warehouse.zona_despacho:
                _, previos = dijkstra(warehouse.grafo, actual)
                camino_ret = reconstruir_camino(previos, actual, warehouse.zona_despacho)
                if camino_ret and len(camino_ret) > 1:
                    camino_total.extend(camino_ret[1:])
                    nodos_visitados_totales += len(camino_ret) - 1
                actual = warehouse.zona_despacho
                peso_actual = 0.0
            
            # 2. Ir al destino
            _, previos = dijkstra(warehouse.grafo, actual)
            camino = reconstruir_camino(previos, actual, destino)
            
            if camino and len(camino) > 1:
                for paso in camino[1:]:
                    camino_total.append(paso)
                    nodos_visitados_totales += 1
                    actual = paso
                    
                    # 3. Recolección de paso
                    recogidos_aqui = [c for c, acc in destinos_pendientes.items() if acc == actual]
                    for c in recogidos_aqui:
                        peso_c = ubicaciones_info[c]
                        if c == coord or (peso_actual + peso_c <= peso_max_picker):
                            peso_actual += peso_c
                            del destinos_pendientes[c]
                    
        # Retorno final a despacho
        if actual != warehouse.zona_despacho:
            _, previos = dijkstra(warehouse.grafo, actual)
            camino_retorno = reconstruir_camino(previos, actual, warehouse.zona_despacho)
            if camino_retorno and len(camino_retorno) > 1:
                camino_total.extend(camino_retorno[1:])
                nodos_visitados_totales += len(camino_retorno) - 1
             
        fin_tiempo = time.perf_counter()
        
        return {
            "estrategia": "A - Orden (Capacidad Dinámica)",
            "camino": camino_total,
            "distancia": len(camino_total) - 1 if camino_total else 0,
            "nodos_visitados": nodos_visitados_totales,
            "tiempo_ms": (fin_tiempo - inicio_tiempo) * 1000
        }

    @staticmethod
    def estrategia_b_cercania(warehouse, wave, peso_max_picker=20.0):
        """
        Estrategia B (Cercanía / Vecino más cercano Greedy con capacidad de carga):
        Desde la posición actual (inicia en zona_despacho), calcula el camino mínimo
        a todas las ubicaciones pendientes mediante Dijkstra y selecciona la más cercana.
        Avanza hacia ella recogiendo de paso los productos intermedios si el peso lo permite.
        Si la carga máxima (peso_max_picker) se excede, regresa a la zona de despacho a descargar.
        """
        inicio_tiempo = time.perf_counter()
        nodos_visitados_totales = 0
        
        ubicaciones_info = {}
        for pedido in wave.pedidos:
            for prod_info in pedido.productos:
                prod = warehouse.productos.obtener(prod_info['id'])
                if prod:
                    coord = (prod.x, prod.y)
                    ubicaciones_info[coord] = ubicaciones_info.get(coord, 0) + getattr(prod, 'peso', 1.0)
                    
        destinos_pendientes = dict(ubicaciones_info) # coord -> peso_requerido
        
        camino_total = []
        actual = warehouse.zona_despacho
        camino_total.append(actual)
        peso_actual = 0.0
        
        while destinos_pendientes:
            distancias, previos = dijkstra(warehouse.grafo, actual)
            
            min_dist = float('inf')
            mejor_destino_coord = None
            mejor_acceso = None
            
            # Buscar el destino pendiente con menor distancia desde 'actual'
            for coord, peso_req in destinos_pendientes.items():
                dest = warehouse.obtener_nodo_acceso(coord[0], coord[1])
                d = distancias.obtener(dest)
                if d is not None:
                    if d < min_dist:
                        min_dist = d
                        mejor_destino_coord = coord
                        mejor_acceso = dest
                    elif d == min_dist and mejor_destino_coord is not None:
                        # Desempate determinista: menor coordenada para evitar sesgo
                        if dest < mejor_acceso:
                            mejor_destino_coord = coord
                            mejor_acceso = dest
                            
            if mejor_destino_coord is None:
                break
                
            peso_requerido = destinos_pendientes[mejor_destino_coord]
            
            # 1. Retorno a despacho si supera capacidad
            if peso_actual + peso_requerido > peso_max_picker and actual != warehouse.zona_despacho:
                camino_ret = reconstruir_camino(previos, actual, warehouse.zona_despacho)
                if camino_ret and len(camino_ret) > 1:
                    camino_total.extend(camino_ret[1:])
                    nodos_visitados_totales += len(camino_ret) - 1
                actual = warehouse.zona_despacho
                peso_actual = 0.0
                continue # Reevaluar distancias desde el despacho
                
            # 2. Desplazarse al mejor destino paso a paso recogiendo de paso
            camino = reconstruir_camino(previos, actual, mejor_acceso)
            
            if camino and len(camino) > 1:
                for paso in camino[1:]:
                    camino_total.append(paso)
                    nodos_visitados_totales += 1
                    actual = paso
                    
                    # 3. Recolección de paso
                    recogidos_aqui = [c for c in list(destinos_pendientes.keys()) if warehouse.obtener_nodo_acceso(c[0], c[1]) == actual]
                    for c in recogidos_aqui:
                        peso_c = destinos_pendientes[c]
                        if c == mejor_destino_coord or (peso_actual + peso_c <= peso_max_picker):
                            peso_actual += peso_c
                            del destinos_pendientes[c]
            else:
                peso_actual += peso_requerido
                if mejor_destino_coord in destinos_pendientes:
                    del destinos_pendientes[mejor_destino_coord]
                
        if actual != warehouse.zona_despacho:
            _, previos = dijkstra(warehouse.grafo, actual)
            camino_retorno = reconstruir_camino(previos, actual, warehouse.zona_despacho)
            if camino_retorno and len(camino_retorno) > 1:
                camino_total.extend(camino_retorno[1:])
                nodos_visitados_totales += len(camino_retorno) - 1
             
        fin_tiempo = time.perf_counter()
        
        return {
            "estrategia": "B - Cercanía Greedy (Peso)",
            "camino": camino_total,
            "distancia": len(camino_total) - 1 if camino_total else 0,
            "nodos_visitados": nodos_visitados_totales,
            "tiempo_ms": (fin_tiempo - inicio_tiempo) * 1000
        }

    @staticmethod
    def estrategia_c_pasillos(warehouse, wave, peso_max_picker=20.0):
        """
        Estrategia C (Pasillos - Far First con Peso):
        Ordena ubicando primero los pasillos lejanos. Si excede capacidad, regresa a despacho.
        """
        inicio_tiempo = time.perf_counter()
        nodos_visitados_totales = 0
        
        camino_total = []
        actual = warehouse.zona_despacho
        camino_total.append(actual)
        
        ubicaciones_info = {} 
        for pedido in wave.pedidos:
            for prod_info in pedido.productos:
                prod = warehouse.productos.obtener(prod_info['id'])
                if prod:
                    coord = (prod.x, prod.y)
                    ubicaciones_info[coord] = ubicaciones_info.get(coord, 0) + getattr(prod, 'peso', 1.0)
                        
        def sort_key(coord):
            ax, ay = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            return (-ax, ay)
            
        ubicaciones_ordenadas = sorted(list(ubicaciones_info.keys()), key=sort_key)
        
        destinos_pendientes = {}
        for coord in ubicaciones_ordenadas:
            destinos_pendientes[coord] = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            
        peso_actual = 0.0
        
        for coord in ubicaciones_ordenadas:
            if coord not in destinos_pendientes:
                continue 
                
            destino = destinos_pendientes[coord]
            peso_requerido = ubicaciones_info[coord]
            
            # Chequeo de peso
            if peso_actual + peso_requerido > peso_max_picker and actual != warehouse.zona_despacho:
                _, previos = dijkstra(warehouse.grafo, actual)
                camino_ret = reconstruir_camino(previos, actual, warehouse.zona_despacho)
                if camino_ret and len(camino_ret) > 1:
                    camino_total.extend(camino_ret[1:])
                    nodos_visitados_totales += len(camino_ret) - 1
                actual = warehouse.zona_despacho
                peso_actual = 0.0
            
            _, previos = dijkstra(warehouse.grafo, actual)
            camino = reconstruir_camino(previos, actual, destino)
            
            if camino and len(camino) > 1:
                for paso in camino[1:]:
                    camino_total.append(paso)
                    nodos_visitados_totales += 1
                    actual = paso
                    
                    recogidos_aqui = [c for c, acc in destinos_pendientes.items() if acc == actual]
                    for c in recogidos_aqui:
                        peso_c = ubicaciones_info[c]
                        if c == coord or (peso_actual + peso_c <= peso_max_picker):
                            peso_actual += peso_c
                            del destinos_pendientes[c]
                        
        if actual != warehouse.zona_despacho:
            _, previos = dijkstra(warehouse.grafo, actual)
            camino_retorno = reconstruir_camino(previos, actual, warehouse.zona_despacho)
            if camino_retorno and len(camino_retorno) > 1:
                camino_total.extend(camino_retorno[1:])
                nodos_visitados_totales += len(camino_retorno) - 1
             
        fin_tiempo = time.perf_counter()
        
        return {
            "estrategia": "C - Por Pasillos (Peso)",
            "camino": camino_total,
            "distancia": len(camino_total) - 1 if camino_total else 0,
            "nodos_visitados": nodos_visitados_totales,
            "tiempo_ms": (fin_tiempo - inicio_tiempo) * 1000
        }
