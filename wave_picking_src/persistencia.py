"""
Módulo de Persistencia (Patrón Adaptador)
Se encarga de leer y escribir los archivos JSON de escenarios y estados de simulación,
permitiendo guardar una simulación en un punto específico y reanudarla posteriormente
sin necesidad de reconstruir manualmente el escenario.
"""
import json
from warehouse import Warehouse
from modelos import (
    Puerta, ZonaDespacho, Rack, Pasillo,
    Picker, Producto, Pedido, Wave, LineaRecoleccion
)


class PersistenciaJSON:
    """Adaptador para la carga y guardado de escenarios y simulaciones en formato JSON."""

    @staticmethod
    def cargar_escenario(ruta_archivo):
        """
        Lee un archivo JSON de escenario o de simulación guardada, instancia el Warehouse
        con sus dimensiones dinámicas y restaura puertas, zonas de despacho, racks, pasillos,
        pickers, productos, pedidos, configuración y estado de simulación (si existe).
        """
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            data = json.load(f)

        wh_data = data.get("warehouse", {})
        dim = wh_data.get("dimensiones", {"ancho_x": 18, "largo_y": 16})

        wh = Warehouse(ancho_x=dim["ancho_x"], largo_y=dim["largo_y"])

        # 1. Cargar Puertas
        for p in wh_data.get("puertas", []):
            ub = p["ubicacion"]
            wh.puertas.append(Puerta(
                id_puerta=p["id"],
                tipo=p.get("tipo", "AMBOS"),
                x=ub["x"],
                y=ub["y"]
            ))

        # 2. Cargar Zonas de Despacho y su peso máximo soportado
        for z in wh_data.get("zonas_despacho", []):
            ub = z["ubicacion"]
            wh.zonas_despacho.append(ZonaDespacho(
                id_zona=z["id"],
                puerta_id=z.get("puerta_id", ""),
                x=ub["x"],
                y=ub["y"],
                ancho=z["ancho"],
                alto=z["alto"],
                peso_max_kg=z.get("peso_max_kg", 500.0)
            ))

        # 3. Cargar Racks
        for r in wh_data.get("racks", []):
            ub = r["ubicacion"]
            wh.racks.append(Rack(
                id_rack=r["id"],
                x=ub["x"],
                y=ub["y"],
                ancho=r["ancho"],
                alto=r["alto"]
            ))

        # 4. Cargar Pasillos con su sentido de circulación
        for pas in wh_data.get("pasillos", []):
            ub = pas["ubicacion"]
            wh.pasillos.append(Pasillo(
                id_pasillo=pas["id"],
                x=ub["x"],
                y=ub["y"],
                ancho=pas["ancho"],
                alto=pas["alto"],
                sentido=pas.get("sentido", "AMBOS")
            ))

        # 5. Cargar Pickers
        for pk in data.get("pickers", []):
            pos = pk["posicion_inicial"]
            wh.pickers.append(Picker(
                id_picker=pk["id"],
                x_inicial=pos["x"],
                y_inicial=pos["y"],
                capacidad_carga_kg=pk.get("capacidad_carga_kg", 150.0)
            ))

        # 6. Cargar Productos
        for prod in data.get("productos", []):
            ub = prod["ubicacion"]
            nuevo_prod = Producto(
                id_prod=prod["id"],
                nombre=prod["nombre"],
                x=ub["x"],
                y=ub["y"],
                z=ub.get("z", 1),
                stock=prod.get("cantidad_disponible", 0),
                peso=prod.get("peso_kg", 1.0),
                rack_id=prod.get("rack_id")
            )
            wh.registrar_producto(nuevo_prod)

        # 7. Cargar Pedidos y sus ítems requeridos
        for ped in data.get("pedidos", []):
            nuevo_ped = Pedido(
                id_pedido=ped["id"],
                prioridad=ped.get("prioridad", 1),
                estado=ped.get("estado", "PENDIENTE")
            )
            for item in ped.get("items", []):
                nuevo_ped.agregar_producto(
                    id_prod=item["producto_id"],
                    cantidad=item["cantidad"]
                )
                if "cantidad_pendiente" in item and nuevo_ped.items:
                    nuevo_ped.items[-1].cantidad_pendiente = int(item["cantidad_pendiente"])
            wh.registrar_pedido(nuevo_ped)

        # 8. Cargar parámetros de configuración general
        conf = data.get("configuracion", {})
        wh.wave_max_pedidos = conf.get("wave_max_pedidos", 3)
        wh.wave_max_productos = conf.get("wave_max_productos", 15)

        wh.construir_estructura()

        # 9. Restaurar estado de simulación guardado (si el JSON incluye una simulación en curso)
        sim_data = data.get("simulacion")
        if sim_data:
            waves_restauradas = []
            for w_dict in sim_data.get("waves", []):
                w_obj = Wave(
                    id_wave=w_dict["id_wave"],
                    picker_id=w_dict.get("picker_id", "AUTO"),
                    zona_despacho_id=w_dict.get("zona_despacho_id", "ZONA_A")
                )
                for l_dict in w_dict.get("lineas", []):
                    lin = LineaRecoleccion(
                        pedido_id=l_dict["pedido_id"],
                        producto_id=l_dict["producto_id"],
                        cantidad=l_dict["cantidad"],
                        peso_unitario=l_dict["peso_unitario"],
                        picker_id=l_dict.get("picker_id")
                    )
                    w_obj.agregar_linea(lin)
                waves_restauradas.append(w_obj)

            planes_restaurados = []
            for p_dict in sim_data.get("planes_activos", []):
                hist = [tuple(coord) for coord in p_dict.get("historial", [])]
                estados = []
                for est in p_dict.get("estados_paso", []):
                    estados.append({
                        "wave_madre": est.get("wave_madre"),
                        "turno_id": est.get("turno_id"),
                        "estado": est.get("estado", ""),
                        "peso": float(est.get("peso", 0.0)),
                        "evento": est.get("evento", ""),
                        "limpiar_rastro": bool(est.get("limpiar_rastro", False)),
                        "prods_activos": [tuple(pa) for pa in est.get("prods_activos", [])]
                    })
                planes_restaurados.append({
                    "id_picker": p_dict["id_picker"],
                    "sector_corto": p_dict.get("sector_corto", "Zona"),
                    "cap_kg": float(p_dict.get("cap_kg", 150.0)),
                    "color": p_dict.get("color", "#00a8ff"),
                    "historial": hist,
                    "estados_paso": estados,
                    "desvios": int(p_dict.get("desvios", 0)),
                    "oval_id": None,
                    "txt_id": None
                })

            wh.estado_simulacion_guardado = {
                "waves": waves_restauradas,
                "planes_activos": planes_restaurados,
                "paso_actual": int(sim_data.get("paso_actual", 0)),
                "estrategia": sim_data.get("estrategia", "Estrategia B - Cercanía 3D (Greedy)"),
                "permitir_ayuda_zonas": bool(sim_data.get("permitir_ayuda_zonas", False)),
                "modo_continuo": bool(sim_data.get("modo_continuo", True)),
                "wave_seleccionada_idx": int(sim_data.get("wave_seleccionada_idx", 0)),
                "vel_simulacion": float(sim_data.get("vel_simulacion", 0.12)),
                "factor_zoom": float(sim_data.get("factor_zoom", 1.0)),
                "waves_completadas": set(sim_data.get("waves_completadas", [])),
                "cap_zonas_actual": {
                    k: float(v) for k, v in sim_data.get("cap_zonas_actual", {}).items()
                },
                "cap_zonas_por_paso": [
                    {k: float(v) for k, v in paso_d.items()}
                    for paso_d in sim_data.get("cap_zonas_por_paso", [])
                ],
                "metricas_actuales": sim_data.get("metricas_actuales", {}),
                "log_eventos": sim_data.get("log_eventos", [])
            }
        else:
            wh.estado_simulacion_guardado = None

        return wh
