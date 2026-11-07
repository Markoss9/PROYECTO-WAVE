"""
Módulo de Gestión de Waves y Zonificación (Unidades 4 y 6)
- WaveManager con Zonificación del Warehouse por Picker, Order Splitting y Quiebre de Stock.
"""
from estructuras import merge_sort
from modelos import Wave, LineaRecoleccion


class WaveManager:
    """
    Gestor de Waves con Zonificación del Warehouse por Picker,
    Fraccionamiento de Pedidos (Order Splitting) y Quiebre de Stock.
    """

    @staticmethod
    def _distancia_3d(prod, cx, cy):
        return abs(prod.x - cx) + abs(prod.y - cy) + prod.z

    @staticmethod
    def obtener_zonas_pickers(warehouse):
        """
        Divide el Warehouse en zonas equitativas sobre el eje X según la cantidad de Pickers,
        asignando cada sector al picker correspondiente según su posición inicial.
        Por ejemplo, con 2 pickers: mitad izquierda para el Picker 1 y mitad derecha para el Picker 2.
        """
        pickers = getattr(warehouse, 'pickers', [])
        if not pickers:
            return []

        pickers_ordenados = merge_sort(
            list(pickers),
            key=lambda p: (p.x_inicial, p.y_inicial, p.id_picker)
        )
        n = len(pickers_ordenados)
        ancho = max(1, warehouse.ancho_x)
        zonas = []

        for i, pk in enumerate(pickers_ordenados):
            x_min = (i * ancho) // n
            x_max = ((i + 1) * ancho) // n - 1 if i < n - 1 else ancho - 1

            if n == 1:
                nombre_zona = "Zona Única (Warehouse Completo)"
                sector_corto = "Zona Única"
            elif n == 2:
                lado = "Mitad Izquierda" if i == 0 else "Mitad Derecha"
                nombre_zona = f"Zona {i + 1} - {lado}"
                sector_corto = f"Z{i + 1} ({lado})"
            else:
                nombre_zona = f"Zona {i + 1} - Sector {i + 1}/{n}"
                sector_corto = f"Z{i + 1} (Sec. {i + 1}/{n})"

            racks_en_zona = [
                r.id_rack for r in getattr(warehouse, 'racks', [])
                if r.x <= x_max and (r.x + r.ancho - 1) >= x_min
            ]

            zonas.append({
                "picker": pk,
                "picker_id": pk.id_picker,
                "indice": i + 1,
                "nombre_zona": nombre_zona,
                "sector_corto": sector_corto,
                "x_min": x_min,
                "x_max": x_max,
                "rango_x": f"X: {x_min} a {x_max}",
                "racks": racks_en_zona
            })

        return zonas

    @staticmethod
    def obtener_zona_de_producto(prod, warehouse, zonas=None):
        """Determina a qué zona y picker pertenece un producto según su coordenada X."""
        if zonas is None:
            zonas = WaveManager.obtener_zonas_pickers(warehouse)
        if not zonas:
            return None

        for z in zonas:
            if z["x_min"] <= prod.x <= z["x_max"]:
                return z

        return min(zonas, key=lambda z: min(abs(prod.x - z["x_min"]), abs(prod.x - z["x_max"])))

    @staticmethod
    def _preparar_tareas_con_stock(pedidos_ordenados, warehouse, zonas=None):
        if zonas is None:
            zonas = WaveManager.obtener_zonas_pickers(warehouse)

        todos_prods = warehouse.productos.valores()
        stock_virtual = {p.id_prod: p.stock for p in todos_prods}

        por_nombre = {}
        for p in todos_prods:
            por_nombre.setdefault(p.nombre.strip().lower(), []).append(p)

        tareas_pendientes = []

        def registrar_tarea(ped, item, prod, cant):
            z_info = WaveManager.obtener_zona_de_producto(prod, warehouse, zonas)
            pk_id = z_info["picker_id"] if z_info else "AUTO"
            tareas_pendientes.append({
                'pedido': ped,
                'item_ref': item,
                'producto': prod,
                'cantidad_pendiente': cant,
                'picker_id': pk_id,
                'zona_info': z_info
            })

        for ped in pedidos_ordenados:
            for item in ped.items:
                faltante = item.cantidad_pendiente
                if faltante <= 0:
                    continue

                prod_orig = warehouse.productos.obtener(item.producto_id)
                if prod_orig is None:
                    continue

                disp_orig = stock_virtual.get(prod_orig.id_prod, 0)
                tomar_orig = min(faltante, disp_orig)
                if tomar_orig > 0:
                    stock_virtual[prod_orig.id_prod] -= tomar_orig
                    faltante -= tomar_orig
                    registrar_tarea(ped, item, prod_orig, tomar_orig)

                if faltante > 0:
                    clave_nom = prod_orig.nombre.strip().lower()
                    candidatos_alt = sorted(
                        por_nombre.get(clave_nom, []),
                        key=lambda alt: abs(alt.x - prod_orig.x) + abs(alt.y - prod_orig.y)
                    )
                    for alt in candidatos_alt:
                        if faltante <= 0:
                            break
                        disp_alt = stock_virtual.get(alt.id_prod, 0)
                        if disp_alt > 0:
                            tomar_alt = min(faltante, disp_alt)
                            stock_virtual[alt.id_prod] -= tomar_alt
                            faltante -= tomar_alt
                            registrar_tarea(ped, item, alt, tomar_alt)

                if faltante > 0:
                    registrar_tarea(ped, item, prod_orig, faltante)

        return tareas_pendientes

    @staticmethod
    def generar_waves(pedidos, warehouse, capacidad_max_pedidos=None,
                      max_productos_wave=None, peso_max_wave=None):
        max_ped = capacidad_max_pedidos or getattr(warehouse, 'wave_max_pedidos', 3)
        max_unid = max_productos_wave or getattr(warehouse, 'wave_max_productos', 15)

        lista_pedidos = []
        for p in pedidos:
            for it in p.items:
                it.cantidad_pendiente = it.cantidad_total
            p.estado = "PENDIENTE"
            if p.unidades_pendientes() > 0:
                lista_pedidos.append(p)

        if not lista_pedidos:
            return []

        zonas = WaveManager.obtener_zonas_pickers(warehouse)
        mapa_zonas = {z["picker_id"]: z for z in zonas}

        ordenados = merge_sort(lista_pedidos, key=lambda p: p.prioridad, reverso=True)
        tareas = WaveManager._preparar_tareas_con_stock(ordenados, warehouse, zonas)

        zonas_desp = getattr(warehouse, 'zonas_despacho', [])
        cap_max_zona = max((z.peso_max_kg for z in zonas_desp), default=500.0)
        limite_kg_wave = peso_max_wave if peso_max_wave is not None else cap_max_zona

        waves = []
        id_wave_num = 1

        while tareas:
            zn_ref = zonas_desp[(id_wave_num - 1) % len(zonas_desp)] if zonas_desp else None
            id_zona_ini = zn_ref.id_zona if zn_ref else "ZONA_A"
            limite_actual_kg = min(limite_kg_wave, zn_ref.peso_max_kg) if zn_ref else limite_kg_wave

            wave_actual = Wave(f"W{id_wave_num:02d}", picker_id="AUTO", zona_despacho_id=id_zona_ini)
            # Cada picker mantiene su propio centroide de recorrido dentro de su zona asignada
            coords_por_picker = {
                z["picker_id"]: [(z["picker"].x_inicial, z["picker"].y_inicial)]
                for z in zonas
            }
            peso_por_picker = {z["picker_id"]: 0.0 for z in zonas}
            progreso_en_wave = False

            while tareas and wave_actual.total_unidades < max_unid:
                mejor_idx = None
                mejor_puntaje = None
                mejor_cant_posible = 0

                pedidos_actuales = set(wave_actual.pedidos_involucrados)

                for idx, t in enumerate(tareas):
                    ped = t['pedido']
                    prod = t['producto']
                    pk_id = t['picker_id']

                    if ped.id_pedido not in pedidos_actuales and len(pedidos_actuales) >= max_ped:
                        continue

                    unid_libres = max_unid - wave_actual.total_unidades
                    peso_libre_wave = limite_actual_kg - wave_actual.peso_total

                    # Evaluar también la capacidad actual de viaje del picker de esa zona para priorizar balanceo
                    z_pk = mapa_zonas.get(pk_id)
                    cap_pk = z_pk["picker"].capacidad_carga_kg if z_pk else limite_actual_kg
                    peso_libre_pk = cap_pk - peso_por_picker.get(pk_id, 0.0)

                    if prod.peso > 0:
                        max_por_peso = int((peso_libre_wave + 1e-6) // prod.peso)
                    else:
                        max_por_peso = t['cantidad_pendiente']

                    cant_posible = min(t['cantidad_pendiente'], unid_libres, max_por_peso)
                    if cant_posible <= 0:
                        continue

                    coords_pk = coords_por_picker.get(pk_id) or [warehouse.zona_despacho]
                    cx = sum(c[0] for c in coords_pk) / len(coords_pk)
                    cy = sum(c[1] for c in coords_pk) / len(coords_pk)
                    dist_3d = WaveManager._distancia_3d(prod, cx, cy)

                    excede_turno_pk = 0 if peso_libre_pk >= prod.peso else 1
                    puntaje = (-ped.prioridad, excede_turno_pk, dist_3d, idx)

                    if mejor_puntaje is None or puntaje < mejor_puntaje:
                        mejor_puntaje = puntaje
                        mejor_idx = idx
                        mejor_cant_posible = cant_posible

                if mejor_idx is None:
                    break

                t_elegida = tareas[mejor_idx]
                ped_eleg = t_elegida['pedido']
                prod_eleg = t_elegida['producto']
                pk_id_eleg = t_elegida['picker_id']

                linea = LineaRecoleccion(
                    pedido_id=ped_eleg.id_pedido,
                    producto_id=prod_eleg.id_prod,
                    cantidad=mejor_cant_posible,
                    peso_unitario=prod_eleg.peso,
                    picker_id=pk_id_eleg
                )
                wave_actual.agregar_linea(linea)
                coords_por_picker.setdefault(pk_id_eleg, []).append((prod_eleg.x, prod_eleg.y))
                peso_por_picker[pk_id_eleg] = peso_por_picker.get(pk_id_eleg, 0.0) + linea.peso_total

                t_elegida['cantidad_pendiente'] -= mejor_cant_posible
                t_elegida['item_ref'].cantidad_pendiente -= mejor_cant_posible
                ped_eleg.estado = "EN_WAVE"
                progreso_en_wave = True

                if t_elegida['cantidad_pendiente'] <= 0:
                    tareas.pop(mejor_idx)

            if not progreso_en_wave and tareas:
                t_forzada = tareas[0]
                prod_f = t_forzada['producto']
                ped_f = t_forzada['pedido']
                pk_f = t_forzada['picker_id']
                linea_f = LineaRecoleccion(ped_f.id_pedido, prod_f.id_prod, 1, prod_f.peso, picker_id=pk_f)
                wave_actual.agregar_linea(linea_f)
                t_forzada['cantidad_pendiente'] -= 1
                t_forzada['item_ref'].cantidad_pendiente -= 1
                ped_f.estado = "EN_WAVE"
                if t_forzada['cantidad_pendiente'] <= 0:
                    tareas.pop(0)

            pks_en_wave = list(wave_actual.sublistas_pickers.keys())
            wave_actual.picker_id = ", ".join(pks_en_wave) if pks_en_wave else "1 Picker"
            waves.append(wave_actual)
            id_wave_num += 1

        return waves

    @staticmethod
    def dividir_waves_en_turnos(waves, warehouse):
        """
        Divide cada Wave en sublistas (turnos) estrictamente por la Zona de cada Picker.
        Garantiza que cada Picker recoja únicamente productos dentro de su zona asignada,
        respetando su capacidad máxima de carga en kg.
        """
        zonas = WaveManager.obtener_zonas_pickers(warehouse)
        if not zonas:
            return []

        mapa_zonas = {z["picker_id"]: z for z in zonas}
        turnos = []

        for wave in waves:
            lineas_por_picker = {}
            for lin in wave.lineas:
                pk_id = lin.picker_id
                if not pk_id or pk_id not in mapa_zonas:
                    prod = warehouse.productos.obtener(lin.producto_id)
                    z_prod = WaveManager.obtener_zona_de_producto(prod, warehouse, zonas) if prod else zonas[0]
                    pk_id = z_prod["picker_id"]
                    lin.picker_id = pk_id
                lineas_por_picker.setdefault(pk_id, []).append(lin)

            for z in zonas:
                pk_id = z["picker_id"]
                lineas_pk = lineas_por_picker.get(pk_id, [])
                if not lineas_pk:
                    continue

                cap_picker = max(1.0, z["picker"].capacidad_carga_kg)
                sub_idx = 1
                turno_actual = Wave(f"{wave.id_wave}-{pk_id}", picker_id=pk_id, zona_despacho_id=wave.zona_despacho_id)
                turno_actual.wave_madre_id = wave.id_wave
                turno_actual.picker_asignado_id = pk_id
                turno_actual.nombre_zona = z["nombre_zona"]

                for lin in lineas_pk:
                    restante = lin.cantidad
                    while restante > 0:
                        peso_disp = cap_picker - turno_actual.peso_total
                        max_peso_u = int((peso_disp + 1e-6) // lin.peso_unitario) if lin.peso_unitario > 0 else restante

                        if max_peso_u <= 0 and turno_actual.total_unidades > 0:
                            turnos.append(turno_actual)
                            sub_idx += 1
                            turno_actual = Wave(
                                f"{wave.id_wave}-{pk_id}.{sub_idx}",
                                picker_id=pk_id,
                                zona_despacho_id=wave.zona_despacho_id
                            )
                            turno_actual.wave_madre_id = wave.id_wave
                            turno_actual.picker_asignado_id = pk_id
                            turno_actual.nombre_zona = z["nombre_zona"]
                            peso_disp = cap_picker
                            max_peso_u = int((peso_disp + 1e-6) // lin.peso_unitario) if lin.peso_unitario > 0 else restante

                        tomar = min(restante, max(1, max_peso_u))
                        nueva_lin = LineaRecoleccion(lin.pedido_id, lin.producto_id, tomar, lin.peso_unitario, picker_id=pk_id)
                        turno_actual.agregar_linea(nueva_lin)
                        restante -= tomar

                if turno_actual.total_unidades > 0:
                    turnos.append(turno_actual)

        return turnos

    @staticmethod
    def obtener_sublistas_por_picker(warehouse, waves=None):
        """
        Construye el detalle de la sublista de productos asignada a cada Picker según su zona.
        Si aún no se generaron waves, proyecta la asignación zonal directamente desde los pedidos.
        """
        zonas = WaveManager.obtener_zonas_pickers(warehouse)
        resultado = {
            z["picker_id"]: {
                "zona": z,
                "items": [],
                "total_unidades": 0,
                "peso_total": 0.0
            }
            for z in zonas
        }
        if not zonas:
            return resultado

        if waves:
            for w in waves:
                for lin in w.lineas:
                    prod = warehouse.productos.obtener(lin.producto_id)
                    if not prod:
                        continue
                    z_prod = WaveManager.obtener_zona_de_producto(prod, warehouse, zonas)
                    pk_id = lin.picker_id if lin.picker_id in resultado else z_prod["picker_id"]
                    info_pk = resultado[pk_id]
                    info_pk["items"].append({
                        "wave_id": w.id_wave,
                        "pedido_id": lin.pedido_id,
                        "producto": prod,
                        "cantidad": lin.cantidad,
                        "peso_total": lin.peso_total
                    })
                    info_pk["total_unidades"] += lin.cantidad
                    info_pk["peso_total"] += lin.peso_total
        else:
            pedidos = warehouse.pedidos.valores()
            ordenados = merge_sort(list(pedidos), key=lambda p: p.prioridad, reverso=True)
            for ped in ordenados:
                for it in ped.items:
                    prod = warehouse.productos.obtener(it.producto_id)
                    if not prod:
                        continue
                    z_prod = WaveManager.obtener_zona_de_producto(prod, warehouse, zonas)
                    pk_id = z_prod["picker_id"]
                    peso_lin = it.cantidad_total * prod.peso
                    info_pk = resultado[pk_id]
                    info_pk["items"].append({
                        "wave_id": "Pendiente",
                        "pedido_id": ped.id_pedido,
                        "producto": prod,
                        "cantidad": it.cantidad_total,
                        "peso_total": peso_lin
                    })
                    info_pk["total_unidades"] += it.cantidad_total
                    info_pk["peso_total"] += peso_lin

        return resultado
