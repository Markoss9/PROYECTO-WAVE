"""
Módulo de Algoritmos (Unidades 4 y 6)
Implementa:
- Dijkstra sobre Grafo Dirigido con bloqueo dinámico de nodos.
- WaveManager con Fraccionamiento de Pedidos (Order Splitting), Quiebre de Stock por nombre y Cercanía.
- Pathfinding limpio (Estrategias A, B y C) con penalización por altura Z.
- CoordinadorMultiPicker con resolución de colisiones por Camino Alternativo (sin esperas).
"""
import time
from estructuras import ColaPrioridad, TablaHash, merge_sort
from modelos import Wave, LineaRecoleccion


def dijkstra(grafo, inicio, nodos_bloqueados=None):
    """
    Algoritmo de Dijkstra sobre Grafo Dirigido (Unidad 4).
    Calcula caminos mínimos respetando sentidos de pasillo y evitando 'nodos_bloqueados'.
    """
    cap = max(1031, len(grafo.nodos) * 2)
    distancias = TablaHash(cap)
    previos = TablaHash(cap)
    visitados = TablaHash(cap)

    bloqueados = set(nodos_bloqueados) if nodos_bloqueados else set()
    operaciones = 0

    for nodo in grafo.nodos:
        distancias.insertar(nodo, float('inf'))
        previos.insertar(nodo, None)

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
                dist_vecino = distancias.obtener(vecino, float('inf'))
                if nueva_dist < dist_vecino:
                    distancias.insertar(vecino, nueva_dist)
                    previos.insertar(vecino, nodo_actual)
                    pq.insertar(nueva_dist, vecino)
                    operaciones += 1

    grafo.ultimas_operaciones = operaciones
    return distancias, previos


def reconstruir_camino(previos, inicio, fin):
    """Reconstruye el camino mínimo desde 'inicio' hasta 'fin'."""
    if inicio == fin:
        return [inicio]
    camino = []
    actual = fin
    limite = len(previos) + 5

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


class WaveManager:
    """
    Gestor de Waves con Fraccionamiento de Pedidos (Order Splitting),
    sustitución por Quiebre de Stock y agrupación por Cercanía Espacial.
    """

    @staticmethod
    def _distancia_3d(prod, cx, cy):
        """Distancia Manhattan en planta más penalización por altura Z."""
        return abs(prod.x - cx) + abs(prod.y - cy) + prod.z

    @staticmethod
    def _preparar_tareas_con_stock(pedidos_ordenados, warehouse):
        """
        Desglosa los pedidos en tareas individuales verificando el stock disponible en cada (x,y,z).
        Si un producto se agota en su coordenada original, busca otro producto con el MISMO NOMBRE
        en otro rack para completar el pedido.
        """
        todos_prods = warehouse.productos.valores()
        stock_virtual = {p.id_prod: p.stock for p in todos_prods}

        por_nombre = {}
        for p in todos_prods:
            por_nombre.setdefault(p.nombre.strip().lower(), []).append(p)

        tareas_pendientes = []
        for ped in pedidos_ordenados:
            for item in ped.items:
                faltante = item.cantidad_pendiente
                if faltante <= 0:
                    continue

                prod_orig = warehouse.productos.obtener(item.producto_id)
                if prod_orig is None:
                    continue

                # 1. Tomar del producto en su coordenada original
                disp_orig = stock_virtual.get(prod_orig.id_prod, 0)
                tomar_orig = min(faltante, disp_orig)
                if tomar_orig > 0:
                    stock_virtual[prod_orig.id_prod] -= tomar_orig
                    faltante -= tomar_orig
                    tareas_pendientes.append({
                        'pedido': ped,
                        'item_ref': item,
                        'producto': prod_orig,
                        'cantidad_pendiente': tomar_orig
                    })

                # 2. Si se agotó ahí, buscar sustitutos con el mismo nombre en otras ubicaciones
                if faltante > 0:
                    clave_nom = prod_orig.nombre.strip().lower()
                    alternativos = por_nombre.get(clave_nom, [])
                    for alt in alternativos:
                        if faltante <= 0:
                            break
                        disp_alt = stock_virtual.get(alt.id_prod, 0)
                        if disp_alt > 0:
                            tomar_alt = min(faltante, disp_alt)
                            stock_virtual[alt.id_prod] -= tomar_alt
                            faltante -= tomar_alt
                            tareas_pendientes.append({
                                'pedido': ped,
                                'item_ref': item,
                                'producto': alt,
                                'cantidad_pendiente': tomar_alt
                            })

                # 3. Respaldo si el stock global del escenario fuera menor al pedido
                if faltante > 0:
                    tareas_pendientes.append({
                        'pedido': ped,
                        'item_ref': item,
                        'producto': prod_orig,
                        'cantidad_pendiente': faltante
                    })

        return tareas_pendientes

    @staticmethod
    def generar_waves(pedidos, warehouse, capacidad_max_pedidos=None,
                      max_productos_wave=None, peso_max_wave=None):
        """
        Genera las Waves óptimas permitiendo fraccionar pedidos grandes entre varias Waves
        para maximizar el uso de capacidad del picker y minimizar el recorrido.
        """
        max_ped = capacidad_max_pedidos or getattr(warehouse, 'wave_max_pedidos', 3)
        max_unid = max_productos_wave or getattr(warehouse, 'wave_max_productos', 15)

        lista_pedidos = []
        for p in pedidos:
            for it in p.items:
                it.cantidad_pendiente = it.cantidad_total
            p.actualizar_estado()
            if p.unidades_pendientes() > 0:
                lista_pedidos.append(p)

        if not lista_pedidos:
            return []

        ordenados = merge_sort(lista_pedidos, key=lambda p: p.prioridad, reverso=True)
        tareas = WaveManager._preparar_tareas_con_stock(ordenados, warehouse)

        pickers = getattr(warehouse, 'pickers', [])
        zonas = getattr(warehouse, 'zonas_despacho', [])

        waves = []
        id_wave_num = 1

        print("\n=== REPORTE DE GENERACIÓN DE WAVES (ORDER SPLITTING) ===")

        while tareas:
            if pickers:
                pk = pickers[(id_wave_num - 1) % len(pickers)]
                id_picker = pk.id_picker
                cap_picker = peso_max_wave if peso_max_wave is not None else pk.capacidad_carga_kg
            else:
                id_picker = "PK_01"
                cap_picker = peso_max_wave if peso_max_wave is not None else 150.0

            if zonas:
                zn = zonas[(id_wave_num - 1) % len(zonas)]
                id_zona = zn.id_zona
                cap_zona = zn.peso_max_kg
            else:
                id_zona = "ZONA_A"
                cap_zona = float('inf')

            limite_kg = min(cap_picker, cap_zona)
            wave_actual = Wave(f"W{id_wave_num:02d}", picker_id=id_picker, zona_despacho_id=id_zona)

            coords_wave = [warehouse.zona_despacho]
            progreso_en_wave = False

            while tareas and wave_actual.total_unidades < max_unid:
                cx = sum(c[0] for c in coords_wave) / len(coords_wave)
                cy = sum(c[1] for c in coords_wave) / len(coords_wave)

                mejor_idx = None
                mejor_puntaje = None
                mejor_cant_posible = 0

                pedidos_actuales = set(wave_actual.pedidos_involucrados)

                for idx, t in enumerate(tareas):
                    ped = t['pedido']
                    prod = t['producto']

                    if ped.id_pedido not in pedidos_actuales and len(pedidos_actuales) >= max_ped:
                        continue

                    unid_libres = max_unid - wave_actual.total_unidades
                    peso_libre = limite_kg - wave_actual.peso_total

                    if prod.peso > 0:
                        max_por_peso = int((peso_libre + 1e-6) // prod.peso)
                    else:
                        max_por_peso = t['cantidad_pendiente']

                    cant_posible = min(t['cantidad_pendiente'], unid_libres, max_por_peso)
                    if cant_posible <= 0:
                        continue

                    dist_3d = WaveManager._distancia_3d(prod, cx, cy)
                    puntaje = (-ped.prioridad, dist_3d)

                    if mejor_puntaje is None or puntaje < mejor_puntaje:
                        mejor_puntaje = puntaje
                        mejor_idx = idx
                        mejor_cant_posible = cant_posible

                if mejor_idx is None:
                    break

                t_elegida = tareas[mejor_idx]
                ped_eleg = t_elegida['pedido']
                prod_eleg = t_elegida['producto']

                linea = LineaRecoleccion(
                    pedido_id=ped_eleg.id_pedido,
                    producto_id=prod_eleg.id_prod,
                    cantidad=mejor_cant_posible,
                    peso_unitario=prod_eleg.peso
                )
                wave_actual.agregar_linea(linea)
                coords_wave.append((prod_eleg.x, prod_eleg.y))

                t_elegida['cantidad_pendiente'] -= mejor_cant_posible
                t_elegida['item_ref'].cantidad_pendiente -= mejor_cant_posible
                ped_eleg.actualizar_estado()
                progreso_en_wave = True

                if t_elegida['cantidad_pendiente'] <= 0:
                    tareas.pop(mejor_idx)

            if not progreso_en_wave and tareas:
                t_forzada = tareas[0]
                prod_f = t_forzada['producto']
                ped_f = t_forzada['pedido']
                linea_f = LineaRecoleccion(ped_f.id_pedido, prod_f.id_prod, 1, prod_f.peso)
                wave_actual.agregar_linea(linea_f)
                t_forzada['cantidad_pendiente'] -= 1
                t_forzada['item_ref'].cantidad_pendiente -= 1
                ped_f.actualizar_estado()
                if t_forzada['cantidad_pendiente'] <= 0:
                    tareas.pop(0)

            waves.append(wave_actual)
            print(f"Wave {wave_actual.id_wave} | Picker: {id_picker} | Zona: {id_zona} | "
                  f"Pedidos: {wave_actual.pedidos_involucrados} | "
                  f"Unidades: {wave_actual.total_unidades}/{max_unid} | "
                  f"Peso: {wave_actual.peso_total:.2f}/{limite_kg:.0f} kg")

            for lin in wave_actual.lineas:
                print(f"  -> [Pedido {lin.pedido_id}] Prod {lin.producto_id} x{lin.cantidad} "
                      f"({lin.peso_total:.2f} kg)")

            id_wave_num += 1

        print("========================================================\n")
        return waves


class Pathfinding:
    """
    Estrategias de Recorrido (A, B y C) simplificadas con Order Splitting y costo vertical Z.
    """

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
    def _consultar_dijkstra(grafo, origen, cache, contador_ops):
        if origen not in cache:
            dist, prev = dijkstra(grafo, origen)
            cache[origen] = (dist, prev)
            contador_ops[0] += getattr(grafo, 'ultimas_operaciones', 0)
        return cache[origen]

    @staticmethod
    def _recorrer_lista_destinos(warehouse, coords_ordenadas, z_por_coord, nombre_estrategia):
        t0 = time.perf_counter()
        cache_dijkstra = {}
        contador_ops = [0]

        despacho = warehouse.zona_despacho
        actual = despacho
        camino_total = [actual]
        costo_altura_z = 0

        for coord in coords_ordenadas:
            nodo_acceso = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            costo_altura_z += max(0, z_por_coord.get(coord, 1) - 1)

            if actual != nodo_acceso:
                _, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_dijkstra, contador_ops)
                tramo = reconstruir_camino(previos, actual, nodo_acceso)
                if len(tramo) > 1:
                    camino_total.extend(tramo[1:])
                    actual = nodo_acceso

        if actual != despacho:
            _, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_dijkstra, contador_ops)
            tramo_ret = reconstruir_camino(previos, actual, despacho)
            if len(tramo_ret) > 1:
                camino_total.extend(tramo_ret[1:])

        t1 = time.perf_counter()
        pasos_planta = len(camino_total) - 1 if camino_total else 0
        distancia_total = pasos_planta + costo_altura_z

        return {
            "estrategia": nombre_estrategia,
            "camino": camino_total,
            "distancia": distancia_total,
            "aristas_recorridas": pasos_planta,
            "costo_altura_z": costo_altura_z,
            "nodos_visitados": len(set(camino_total)),
            "operaciones": contador_ops[0],
            "tiempo_ms": (t1 - t0) * 1000.0
        }

    @staticmethod
    def estrategia_a_orden_pedidos(warehouse, wave, peso_max_picker=None):
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)
        return Pathfinding._recorrer_lista_destinos(
            warehouse, ubicaciones_orden, z_por_coord, "A - Orden de Llegada"
        )

    @staticmethod
    def estrategia_b_cercania(warehouse, wave, peso_max_picker=None):
        t0 = time.perf_counter()
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)
        pendientes = set(ubicaciones_orden)

        cache_dijkstra = {}
        contador_ops = [0]

        despacho = warehouse.zona_despacho
        actual = despacho
        camino_total = [actual]
        costo_altura_z = 0

        while pendientes:
            distancias, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_dijkstra, contador_ops)

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

            if mejor_coord is None or mejor_costo_3d == float('inf'):
                break

            acceso_dest = warehouse.obtener_nodo_acceso(mejor_coord[0], mejor_coord[1])
            tramo = reconstruir_camino(previos, actual, acceso_dest)
            if len(tramo) > 1:
                camino_total.extend(tramo[1:])
                actual = acceso_dest

            costo_altura_z += max(0, z_por_coord.get(mejor_coord, 1) - 1)
            pendientes.remove(mejor_coord)

        if actual != despacho:
            _, previos = Pathfinding._consultar_dijkstra(warehouse.grafo, actual, cache_dijkstra, contador_ops)
            tramo_ret = reconstruir_camino(previos, actual, despacho)
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
            "tiempo_ms": (t1 - t0) * 1000.0
        }

    @staticmethod
    def estrategia_c_pasillos(warehouse, wave, peso_max_picker=None):
        ubicaciones_orden, z_por_coord = Pathfinding._extraer_objetivos_wave(warehouse, wave)

        def clave_pasillo(coord):
            ax, ay = warehouse.obtener_nodo_acceso(coord[0], coord[1])
            sentido = warehouse.grilla_sentido.get((ax, ay), "AMBOS")
            orden_y = -ay if sentido == "S" else ay
            return (ax, orden_y, z_por_coord.get(coord, 1))

        ordenadas = merge_sort(ubicaciones_orden, key=clave_pasillo)
        return Pathfinding._recorrer_lista_destinos(
            warehouse, ordenadas, z_por_coord, "C - Barrido de Pasillos"
        )


class CoordinadorMultiPicker:
    """
    Coordinador de múltiples Pickers en simultáneo.
    Resuelve colisiones recalcando inmediatamente un CAMINO ALTERNATIVO con Dijkstra.
    """

    @staticmethod
    def planificar_simulacion_multipicker(warehouse, waves, funcion_estrategia):
        pickers = getattr(warehouse, 'pickers', [])
        if not pickers or not waves:
            return []

        planes = []
        cant_activos = min(len(pickers), len(waves))

        for i in range(cant_activos):
            pk = pickers[i]
            wv = waves[i]
            res = funcion_estrategia(warehouse, wv)
            camino_base = list(res["camino"])

            pos_ini = (pk.x_inicial, pk.y_inicial)
            if camino_base and camino_base[0] != pos_ini:
                _, prev = dijkstra(warehouse.grafo, pos_ini)
                tramo_ini = reconstruir_camino(prev, pos_ini, camino_base[0])
                if len(tramo_ini) > 1:
                    camino_base = tramo_ini[:-1] + camino_base

            planes.append({
                "picker": pk,
                "wave": wv,
                "camino_restante": camino_base,
                "historial": [camino_base[0]] if camino_base else [pos_ini],
                "eventos": ["Inicio"],
                "esperas": 0,
                "desvios": 0
            })

        max_pasos = 2500
        paso = 0

        while paso < max_pasos:
            if not any(len(p["camino_restante"]) > 1 for p in planes):
                break

            pos_actuales = [p["historial"][-1] for p in planes]
            pos_confirmadas = {}

            for i, plan in enumerate(planes):
                if len(plan["camino_restante"]) <= 1:
                    pos_confirmadas[i] = pos_actuales[i]
                    plan["historial"].append(pos_actuales[i])
                    plan["eventos"].append("Fin")
                    continue

                sig_celda = plan["camino_restante"][1]
                conflicto = False

                for j, pos_j_nueva in pos_confirmadas.items():
                    pos_j_vieja = pos_actuales[j]
                    if sig_celda == pos_j_nueva or (sig_celda == pos_j_vieja and pos_j_nueva == pos_actuales[i]):
                        conflicto = True
                        break

                if not conflicto:
                    plan["camino_restante"].pop(0)
                    pos_confirmadas[i] = sig_celda
                    plan["historial"].append(sig_celda)
                    plan["eventos"].append("Avanza")
                else:
                    celdas_ocupadas = set(pos_confirmadas.values()) | {sig_celda}
                    _, prev_alt = dijkstra(warehouse.grafo, pos_actuales[i], nodos_bloqueados=celdas_ocupadas)

                    desvio_exitoso = None
                    for idx_obj in range(2, min(len(plan["camino_restante"]), 10)):
                        nodo_obj = plan["camino_restante"][idx_obj]
                        if nodo_obj in celdas_ocupadas:
                            continue
                        tramo_alt = reconstruir_camino(prev_alt, pos_actuales[i], nodo_obj)
                        if len(tramo_alt) > 1 and tramo_alt[1] not in celdas_ocupadas:
                            desvio_exitoso = tramo_alt + plan["camino_restante"][idx_obj + 1:]
                            break

                    if desvio_exitoso is not None:
                        plan["camino_restante"] = desvio_exitoso
                        nueva_sig = plan["camino_restante"][1]
                        plan["camino_restante"].pop(0)
                        pos_confirmadas[i] = nueva_sig
                        plan["historial"].append(nueva_sig)
                        plan["desvios"] += 1
                        plan["eventos"].append(f"Desvío alternativo por {sig_celda}")
                    else:
                        vecinos_libres = [
                            v for v, _ in (warehouse.grafo.adj.obtener(pos_actuales[i]) or [])
                            if v not in celdas_ocupadas
                        ]
                        if vecinos_libres:
                            paso_escape = vecinos_libres[0]
                            plan["camino_restante"].insert(0, paso_escape)
                            pos_confirmadas[i] = paso_escape
                            plan["historial"].append(paso_escape)
                            plan["desvios"] += 1
                            plan["eventos"].append(f"Maniobra evasiva en {sig_celda}")
                        else:
                            pos_confirmadas[i] = pos_actuales[i]
                            plan["historial"].append(pos_actuales[i])
                            plan["eventos"].append("Bloqueo físico total")

            paso += 1

        return planes