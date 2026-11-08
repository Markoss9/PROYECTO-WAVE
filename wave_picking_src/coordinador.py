"""
Módulo Coordinador Multi-Picker
Motor de Simulación Continua Multi-Picker con Zonificación del Warehouse,
evasión dinámica de tráfico y cooperación opcional entre zonas.
"""
import time
from modelos import Wave, LineaRecoleccion
from algoritmos import WaveManager
from rutas import dijkstra, reconstruir_camino, Pathfinding


class CoordinadorMultiPicker:
    """
    Motor de Simulación Continua Multi-Picker con Zonificación y Cooperación Post-Zona opcional.
    Coordina todos los pickers asegurando que cada uno opere primero en su zona asignada y,
    si se habilita la opción de ayuda entre zonas, asista a otros pickers al terminar su propia zona.
    """

    @staticmethod
    def planificar_simulacion_continua(warehouse, waves, funcion_estrategia, permitir_ayuda_zonas=False):
        t0 = time.perf_counter()
        pickers = getattr(warehouse, 'pickers', [])
        if not pickers or not waves:
            return {"planes": [], "metricas": {}}

        zonas = WaveManager.obtener_zonas_pickers(warehouse)
        mapa_zonas = {z["picker_id"]: z for z in zonas}
        cola_turnos = WaveManager.dividir_waves_en_turnos(waves, warehouse)

        zonas_despacho = getattr(warehouse, 'zonas_despacho', [])
        cap_restante_zonas = {z.id_zona: float(z.peso_max_kg) for z in zonas_despacho}
        cap_max_zonas = {z.id_zona: float(z.peso_max_kg) for z in zonas_despacho}
        warehouse._cap_restante_zonas = cap_restante_zonas
        cap_zonas_por_paso = [dict(cap_restante_zonas)]

        nodos_entrega = set()
        for z in zonas_despacho:
            nodos_entrega.update(Pathfinding.obtener_celdas_acceso_zona(warehouse, z))
        nodos_entrega.add(warehouse.zona_despacho)

        def armar_mapa_acceso(turno):
            mapa = {}
            detalles_prod = []
            for lin in turno.lineas:
                prod = warehouse.productos.obtener(lin.producto_id)
                if prod:
                    ax, ay = warehouse.obtener_nodo_acceso(prod.x, prod.y)
                    mapa.setdefault((ax, ay), []).append(
                        (prod.id_prod, prod.nombre, lin.cantidad, lin.peso_total, lin.pedido_id, prod.x, prod.y, prod.z)
                    )
                    detalles_prod.append((prod.x, prod.y, prod.z, prod.id_prod, lin.pedido_id))
            return mapa, detalles_prod

        planes = []
        for pk in pickers:
            pos_ini = (pk.x_inicial, pk.y_inicial)
            if not warehouse.es_nodo_valido(pos_ini):
                pos_ini = warehouse.obtener_nodo_acceso(pos_ini[0], pos_ini[1])

            z_pk = mapa_zonas.get(pk.id_picker, {})
            planes.append({
                "picker": pk,
                "zona_info": z_pk,
                "pos_actual": pos_ini,
                "camino_restante": [],
                "turno_actual": None,
                "mapa_recoleccion": {},
                "prods_visuales": [],
                "peso_actual": 0.0,
                "zona_destino": "",
                "en_ayuda": False,
                "ayudando_a": None,
                "historial": [pos_ini],
                "estados_paso": [{
                    "wave_madre": None,
                    "turno_id": None,
                    "estado": "En espera en su zona",
                    "peso": 0.0,
                    "evento": "",
                    "limpiar_rastro": False,
                    "prods_activos": []
                }],
                "desvios": 0
            })

        operaciones_totales = 0
        costo_z_total = 0
        pasos_planta_total = 0

        def intentar_dividir_turno_activo_para_ayuda(plan_libre):
            """
            Cuando un picker terminó su zona y no hay turnos pendientes en cola,
            verifica si otro picker activo aún tiene recolecciones pendientes y toma
            parte de ellas respetando estrictamente la estrategia de ruteo elegida.
            """
            nonlocal operaciones_totales, costo_z_total
            pk_libre = plan_libre["picker"]
            cap_libre = pk_libre.capacidad_carga_kg

            mejor_otro = None
            max_pend = 0
            for op in planes:
                if op is plan_libre or op["turno_actual"] is None or not op["mapa_recoleccion"]:
                    continue
                cant_celdas = len(op["mapa_recoleccion"])
                pasos_rest = len(op["camino_restante"])
                if cant_celdas >= 2 or (cant_celdas == 1 and op["peso_actual"] > 0 and pasos_rest >= 6):
                    if pasos_rest > max_pend:
                        max_pend = pasos_rest
                        mejor_otro = op

            if mejor_otro is None:
                return False

            celda_inmediata = mejor_otro["camino_restante"][1] if len(mejor_otro["camino_restante"]) > 1 else None
            orden_visita = []
            for nodo_cam in mejor_otro["camino_restante"]:
                if nodo_cam in mejor_otro["mapa_recoleccion"] and nodo_cam not in orden_visita:
                    orden_visita.append(nodo_cam)
            for c_acc in mejor_otro["mapa_recoleccion"]:
                if c_acc not in orden_visita:
                    orden_visita.append(c_acc)

            candidatas = [c for c in orden_visita if c != celda_inmediata]
            if not candidatas:
                return False

            if len(mejor_otro["mapa_recoleccion"]) == 1:
                celdas_a_tomar = candidatas[:1]
            else:
                mitad = max(1, len(candidatas) // 2)
                celdas_a_tomar = candidatas[-mitad:]

            items_para_ayuda = []
            celdas_efectivas = []
            peso_acum = 0.0
            for c_acc in celdas_a_tomar:
                items_celda = mejor_otro["mapa_recoleccion"][c_acc]
                peso_celda = sum(it[3] for it in items_celda)
                if peso_acum + peso_celda <= cap_libre or not celdas_efectivas:
                    celdas_efectivas.append(c_acc)
                    items_para_ayuda.extend(items_celda)
                    peso_acum += peso_celda

            if not celdas_efectivas:
                return False

            w_madre = mejor_otro["turno_actual"].wave_madre_id
            otro_pk_id = mejor_otro["picker"].id_picker
            turno_ayuda = Wave(
                f"{w_madre}-Ayuda-{pk_libre.id_picker}",
                picker_id=pk_libre.id_picker,
                zona_despacho_id=mejor_otro["turno_actual"].zona_despacho_id
            )
            turno_ayuda.wave_madre_id = w_madre
            turno_ayuda.picker_asignado_id = pk_libre.id_picker

            for c_acc in celdas_efectivas:
                mejor_otro["mapa_recoleccion"].pop(c_acc, None)

            coords_quitadas = {(it[5], it[6]) for it in items_para_ayuda}
            mejor_otro["prods_visuales"] = [
                pv for pv in mejor_otro["prods_visuales"] if (pv[0], pv[1]) not in coords_quitadas
            ]

            for id_p, _, cant_p, peso_p, ped_id, _, _, _ in items_para_ayuda:
                peso_u = peso_p / max(1, cant_p)
                turno_ayuda.agregar_linea(
                    LineaRecoleccion(ped_id, id_p, cant_p, peso_u, picker_id=pk_libre.id_picker)
                )

            # Recalcular ruta restante del picker asistido usando la estrategia elegida
            turno_rest_otro = Wave(
                mejor_otro["turno_actual"].id_wave,
                picker_id=otro_pk_id,
                zona_despacho_id=mejor_otro["turno_actual"].zona_despacho_id
            )
            turno_rest_otro.wave_madre_id = w_madre
            for items_c in mejor_otro["mapa_recoleccion"].values():
                for id_p, _, cant_p, peso_p, ped_id, _, _, _ in items_c:
                    turno_rest_otro.agregar_linea(
                        LineaRecoleccion(ped_id, id_p, cant_p, peso_p / max(1, cant_p), picker_id=otro_pk_id)
                    )
            turno_rest_otro.peso_total += mejor_otro["peso_actual"]

            res_otro = funcion_estrategia(warehouse, turno_rest_otro, pos_inicio=mejor_otro["pos_actual"])
            operaciones_totales += res_otro.get("operaciones", 0)
            mejor_otro["camino_restante"] = list(res_otro["camino"])
            mejor_otro["zona_destino"] = res_otro.get("zona_despacho_id", mejor_otro["zona_destino"])

            turno_ayuda.peso_total += plan_libre["peso_actual"]
            res_ayuda = funcion_estrategia(warehouse, turno_ayuda, pos_inicio=plan_libre["pos_actual"])
            operaciones_totales += res_ayuda.get("operaciones", 0)
            costo_z_total += res_ayuda.get("costo_altura_z", 0)

            if mejor_otro["estados_paso"]:
                mejor_otro["estados_paso"][-1]["prods_activos"] = list(mejor_otro["prods_visuales"])

            mapa_rec, prods_vis = armar_mapa_acceso(turno_ayuda)
            plan_libre["turno_actual"] = turno_ayuda
            plan_libre["camino_restante"] = list(res_ayuda["camino"])
            plan_libre["mapa_recoleccion"] = mapa_rec
            plan_libre["prods_visuales"] = prods_vis
            plan_libre["zona_destino"] = res_ayuda.get("zona_despacho_id", turno_ayuda.zona_despacho_id)
            plan_libre["en_ayuda"] = True
            plan_libre["ayudando_a"] = otro_pk_id
            return True

        def asignar_siguiente_turno(plan):
            nonlocal operaciones_totales, costo_z_total
            pk_id = plan["picker"].id_picker
            idx_elegido = None
            es_ayuda = False
            ayudando_a = None

            # 1. Prioridad absoluta: productos pendientes dentro de su propia zona
            for idx, t in enumerate(cola_turnos):
                if getattr(t, "picker_asignado_id", None) == pk_id:
                    idx_elegido = idx
                    break

            # 2. Si ya no tiene productos en su zona y está habilitada la ayuda entre zonas
            if idx_elegido is None and permitir_ayuda_zonas:
                for idx, t in enumerate(cola_turnos):
                    if t.peso_total <= plan["picker"].capacidad_carga_kg:
                        idx_elegido = idx
                        es_ayuda = True
                        ayudando_a = getattr(t, "picker_asignado_id", "Otra Zona")
                        break
                if idx_elegido is None and cola_turnos:
                    idx_elegido = 0
                    es_ayuda = True
                    ayudando_a = getattr(cola_turnos[0], "picker_asignado_id", "Otra Zona")

            if idx_elegido is None:
                if permitir_ayuda_zonas and intentar_dividir_turno_activo_para_ayuda(plan):
                    return True
                plan["turno_actual"] = None
                plan["camino_restante"] = []
                plan["en_ayuda"] = False
                plan["ayudando_a"] = None
                return False

            turno = cola_turnos.pop(idx_elegido)
            res = funcion_estrategia(warehouse, turno, pos_inicio=plan["pos_actual"])
            operaciones_totales += res.get("operaciones", 0)
            costo_z_total += res.get("costo_altura_z", 0)

            mapa_rec, prods_vis = armar_mapa_acceso(turno)
            plan["turno_actual"] = turno
            plan["camino_restante"] = list(res["camino"])
            plan["mapa_recoleccion"] = mapa_rec
            plan["prods_visuales"] = prods_vis
            plan["peso_actual"] = 0.0
            plan["zona_destino"] = res.get("zona_despacho_id", turno.zona_despacho_id)
            plan["en_ayuda"] = es_ayuda
            plan["ayudando_a"] = ayudando_a
            return True

        # Primero asignamos a cada picker los turnos propios de su zona
        for plan in planes:
            pk_id = plan["picker"].id_picker
            tiene_propio = any(getattr(t, "picker_asignado_id", None) == pk_id for t in cola_turnos)
            if tiene_propio and asignar_siguiente_turno(plan):
                w_madre = plan["turno_actual"].wave_madre_id
                z_corto = plan["zona_info"].get("sector_corto", "Zona")
                celda_0 = plan["pos_actual"]
                ev_txt = f"Inicia {w_madre} en {z_corto}"
                if celda_0 in plan["mapa_recoleccion"]:
                    items_rec = plan["mapa_recoleccion"].pop(celda_0)
                    rec_coords = []
                    for _, _, _, peso_p, _, px, py, _ in items_rec:
                        plan["peso_actual"] += peso_p
                        rec_coords.append((px, py))
                    plan["prods_visuales"] = [
                        pv for pv in plan["prods_visuales"] if (pv[0], pv[1]) not in rec_coords
                    ]
                plan["estados_paso"][0] = {
                    "wave_madre": w_madre,
                    "turno_id": plan["turno_actual"].id_wave,
                    "estado": f"Recolectando {w_madre}",
                    "peso": plan["peso_actual"],
                    "evento": ev_txt,
                    "limpiar_rastro": True,
                    "prods_activos": list(plan["prods_visuales"])
                }

        # Si algún picker arrancó sin productos en su propia zona y la ayuda está activa, sale a ayudar
        if permitir_ayuda_zonas:
            for plan in planes:
                if plan["turno_actual"] is None and asignar_siguiente_turno(plan):
                    w_madre = plan["turno_actual"].wave_madre_id
                    ev_txt = f"🤝 Sin tareas en su zona ➔ Ayuda a {plan['ayudando_a']} ({w_madre})"
                    plan["estados_paso"][0] = {
                        "wave_madre": w_madre,
                        "turno_id": plan["turno_actual"].id_wave,
                        "estado": f"Ayudando a {plan['ayudando_a']} ({w_madre})",
                        "peso": plan["peso_actual"],
                        "evento": ev_txt,
                        "limpiar_rastro": True,
                        "prods_activos": list(plan["prods_visuales"])
                    }

        max_pasos = 3500
        paso = 0

        while paso < max_pasos:
            hay_activos = any(len(p["camino_restante"]) > 1 or p["peso_actual"] > 0 for p in planes)
            if not hay_activos and not cola_turnos:
                break

            pos_actuales = [p["historial"][-1] for p in planes]
            pos_confirmadas = {}

            for i, plan in enumerate(planes):
                limpiar_rastro_paso = False
                evento_paso = ""

                if len(plan["camino_restante"]) <= 1:
                    if plan["turno_actual"] is not None and plan["mapa_recoleccion"]:
                        # Si quedó algún producto pendiente por desvío de tráfico, recalcular ruta para recogerlo antes de entregar
                        turno_rem = Wave(
                            plan["turno_actual"].id_wave,
                            picker_id=plan["picker"].id_picker,
                            zona_despacho_id=plan["turno_actual"].zona_despacho_id
                        )
                        turno_rem.wave_madre_id = plan["turno_actual"].wave_madre_id
                        for items_c in plan["mapa_recoleccion"].values():
                            for id_p, _, cant_p, peso_p, ped_id, _, _, _ in items_c:
                                turno_rem.agregar_linea(
                                    LineaRecoleccion(ped_id, id_p, cant_p, peso_p / max(1, cant_p), picker_id=plan["picker"].id_picker)
                                )
                        turno_rem.peso_total += plan["peso_actual"]
                        res_rem = funcion_estrategia(warehouse, turno_rem, pos_inicio=pos_actuales[i])
                        operaciones_totales += res_rem.get("operaciones", 0)
                        if len(res_rem["camino"]) > 1:
                            plan["camino_restante"] = list(res_rem["camino"])
                            plan["zona_destino"] = res_rem.get("zona_despacho_id", plan["zona_destino"])

                if len(plan["camino_restante"]) <= 1:
                    if plan["turno_actual"] is not None:
                        w_ant = plan["turno_actual"].wave_madre_id
                        z_dest = plan["zona_destino"]
                        peso_entregado = plan["peso_actual"] if plan["peso_actual"] > 0 else plan["turno_actual"].peso_total
                        if z_dest in cap_restante_zonas:
                            cap_restante_zonas[z_dest] = max(0.0, round(cap_restante_zonas[z_dest] - peso_entregado, 2))
                            cap_disp = cap_restante_zonas[z_dest]
                            cap_max = cap_max_zonas.get(z_dest, 0.0)
                            evento_paso = (
                                f"📦 Entregó {w_ant} (-{peso_entregado:.1f} kg) en {z_dest} "
                                f"➔ Quedan {cap_disp:.1f}/{cap_max:.0f} kg"
                            )
                        else:
                            evento_paso = f"📦 Entregó {w_ant} (-{peso_entregado:.1f} kg) en {z_dest}"
                        plan["turno_actual"] = None
                        plan["peso_actual"] = 0.0
                        plan["en_ayuda"] = False
                        plan["ayudando_a"] = None

                    if asignar_siguiente_turno(plan):
                        limpiar_rastro_paso = True
                        w_nueva = plan["turno_actual"].wave_madre_id
                        if plan.get("en_ayuda"):
                            msg_ini = f"🤝 Finalizó su zona ➔ Ayuda a {plan['ayudando_a']} en {w_nueva}"
                        else:
                            msg_ini = f"Inicia {w_nueva}"
                        evento_paso = f"{evento_paso} | {msg_ini}".strip(" | ")

                if len(plan["camino_restante"]) <= 1:
                    plan["historial"].append(pos_actuales[i])
                    plan["estados_paso"].append({
                        "wave_madre": None,
                        "turno_id": None,
                        "estado": "En su zona (Libre)",
                        "peso": 0.0,
                        "evento": evento_paso,
                        "limpiar_rastro": limpiar_rastro_paso,
                        "prods_activos": []
                    })
                    continue

                sig_celda = plan["camino_restante"][1]
                conflicto = False

                if sig_celda not in nodos_entrega:
                    for j, pos_j_nueva in pos_confirmadas.items():
                        pos_j_vieja = pos_actuales[j]
                        if sig_celda == pos_j_nueva or (sig_celda == pos_j_vieja and pos_j_nueva == pos_actuales[i]):
                            conflicto = True
                            break

                if not conflicto:
                    plan["camino_restante"].pop(0)
                    nueva_pos = sig_celda
                    pos_confirmadas[i] = nueva_pos
                    pasos_planta_total += 1
                else:
                    celdas_ocupadas = set(pos_confirmadas.values()) | {sig_celda}
                    desvio_exitoso = None

                    # No saltar nunca una celda de recolección pendiente en camino_restante
                    primer_pick_idx = None
                    for k in range(1, len(plan["camino_restante"])):
                        if plan["camino_restante"][k] in plan["mapa_recoleccion"]:
                            primer_pick_idx = k
                            break

                    if primer_pick_idx == 1:
                        # La celda inmediatamente siguiente es donde debe recoger un producto:
                        # esperar un turno si no hay choque frontal, o rodear volviendo a idx_meta = 1
                        idx_meta = 1
                    elif primer_pick_idx is not None:
                        idx_meta = min(primer_pick_idx, 6)
                    else:
                        idx_meta = min(len(plan["camino_restante"]) - 1, 6)

                    nodo_meta = plan["camino_restante"][idx_meta]
                    if nodo_meta not in celdas_ocupadas:
                        _, prev_alt = dijkstra(warehouse.grafo, pos_actuales[i], nodos_bloqueados=celdas_ocupadas)
                        operaciones_totales += getattr(warehouse.grafo, 'ultimas_operaciones', 0)
                        tramo_alt = reconstruir_camino(prev_alt, pos_actuales[i], nodo_meta)
                        if len(tramo_alt) > 1 and tramo_alt[1] not in celdas_ocupadas:
                            desvio_exitoso = tramo_alt + plan["camino_restante"][idx_meta + 1:]

                    if desvio_exitoso is not None:
                        plan["camino_restante"] = desvio_exitoso
                        nueva_pos = plan["camino_restante"][1]
                        plan["camino_restante"].pop(0)
                        pos_confirmadas[i] = nueva_pos
                        plan["desvios"] += 1
                        pasos_planta_total += 1
                        evento_paso = f"🔀 Desvío en {sig_celda}"
                    else:
                        vecinos_libres = [
                            v for v, _ in (warehouse.grafo.adj.obtener(pos_actuales[i]) or [])
                            if v not in celdas_ocupadas
                        ]
                        movio_lateral = False
                        for paso_lat in vecinos_libres:
                            _, prev_rec = dijkstra(warehouse.grafo, paso_lat)
                            tramo_rec = reconstruir_camino(prev_rec, paso_lat, nodo_meta)
                            if len(tramo_rec) >= 1:
                                plan["camino_restante"] = tramo_rec + plan["camino_restante"][idx_meta + 1:]
                                nueva_pos = paso_lat
                                pos_confirmadas[i] = nueva_pos
                                plan["desvios"] += 1
                                pasos_planta_total += 1
                                evento_paso = f"🔀 Desvío lateral en {sig_celda}"
                                movio_lateral = True
                                break
                        if not movio_lateral:
                            nueva_pos = pos_actuales[i]
                            pos_confirmadas[i] = nueva_pos

                plan["pos_actual"] = nueva_pos
                plan["historial"].append(nueva_pos)

                if nueva_pos in plan["mapa_recoleccion"]:
                    items_rec = plan["mapa_recoleccion"].pop(nueva_pos)
                    rec_coords = []
                    textos_rec = []
                    for id_p, nom_p, cant_p, peso_p, ped_id, px, py, _ in items_rec:
                        plan["peso_actual"] += peso_p
                        rec_coords.append((px, py))
                        textos_rec.append(f"{cant_p}x {nom_p} [{id_p} ➔ {ped_id}]")
                    plan["prods_visuales"] = [
                        pv for pv in plan["prods_visuales"] if (pv[0], pv[1]) not in rec_coords
                    ]
                    msg_rec = " ; ".join(textos_rec)
                    evento_paso = f"{evento_paso} | 🛒 {msg_rec}".strip(" | ")

                    # Si acaba de recoger el último producto de su zona y la ayuda está activa,
                    # verifica si puede asistir inmediatamente a otro picker con su capacidad restante
                    pk_id_act = plan["picker"].id_picker
                    sin_mas_en_su_zona = not any(
                        getattr(t, "picker_asignado_id", None) == pk_id_act for t in cola_turnos
                    )
                    if (permitir_ayuda_zonas and not plan["mapa_recoleccion"]
                            and not plan.get("en_ayuda") and sin_mas_en_su_zona):
                        if intentar_dividir_turno_activo_para_ayuda(plan):
                            evento_paso = (
                                f"{evento_paso} | 🤝 Finalizó su zona ➔ Ayuda a {plan['ayudando_a']}"
                            ).strip(" | ")

                w_madre = plan["turno_actual"].wave_madre_id if plan["turno_actual"] else None
                t_id = plan["turno_actual"].id_wave if plan["turno_actual"] else None
                if plan["mapa_recoleccion"]:
                    if plan.get("en_ayuda"):
                        estado_txt = f"🤝 Ayudando a {plan['ayudando_a']} ({w_madre})"
                    else:
                        estado_txt = f"Recolectando {w_madre}"
                else:
                    estado_txt = f"Hacia {plan['zona_destino']} ({w_madre})"

                plan["estados_paso"].append({
                    "wave_madre": w_madre,
                    "turno_id": t_id,
                    "estado": estado_txt,
                    "peso": plan["peso_actual"],
                    "evento": evento_paso,
                    "limpiar_rastro": limpiar_rastro_paso,
                    "prods_activos": list(plan["prods_visuales"])
                })

            cap_zonas_por_paso.append(dict(cap_restante_zonas))
            paso += 1

        t1 = time.perf_counter()
        desvios_totales = sum(p["desvios"] for p in planes)
        nodos_unicos = set()
        for p in planes:
            nodos_unicos.update(p["historial"])

        metricas = {
            "makespan_pasos": paso,
            "distancia_total_flota": pasos_planta_total + costo_z_total,
            "pasos_planta_flota": pasos_planta_total,
            "costo_altura_z": costo_z_total,
            "nodos_visitados": len(nodos_unicos),
            "desvios_totales": desvios_totales,
            "operaciones": operaciones_totales,
            "tiempo_ms": (t1 - t0) * 1000.0
        }

        return {
            "planes": planes,
            "metricas": metricas,
            "cap_zonas_por_paso": cap_zonas_por_paso
        }

    @staticmethod
    def comparar_escenario_completo(warehouse, waves, permitir_ayuda_zonas=False):
        estrategias = [
            ("A - Orden de los Pedidos", Pathfinding.estrategia_a_orden_pedidos),
            ("B - Cercanía 3D (Greedy)", Pathfinding.estrategia_b_cercania),
            ("C - Barrido de Pasillos", Pathfinding.estrategia_c_pasillos)
        ]
        resultados = []
        for nombre, fn in estrategias:
            sim = CoordinadorMultiPicker.planificar_simulacion_continua(
                warehouse, waves, fn, permitir_ayuda_zonas=permitir_ayuda_zonas
            )
            m = sim["metricas"]
            resultados.append({
                "estrategia": nombre,
                "distancia_flota": m.get("distancia_total_flota", 0),
                "nodos_visitados": m.get("nodos_visitados", 0),
                "pasos_planta": m.get("pasos_planta_flota", 0),
                "operaciones": m.get("operaciones", 0),
                "tiempo_ms": m.get("tiempo_ms", 0.0)
            })
        return resultados