"""
Módulo de Persistencia (Patrón Adaptador)
Se encarga de leer y escribir los archivos JSON de escenarios, aislando
al resto del sistema del formato externo de los datos.
"""
import json
from warehouse import Warehouse
from modelos import Puerta, ZonaDespacho, Rack, Pasillo, Picker, Producto, Pedido


class PersistenciaJSON:
    """Adaptador para la carga y guardado de escenarios en formato JSON."""

    @staticmethod
    def cargar_escenario(ruta_archivo):
        """
        Lee un archivo JSON de escenario, instancia el Warehouse con sus dimensiones
        dinámicas y carga puertas, zonas de despacho, racks, pasillos, pickers,
        productos, pedidos y configuración.
        """
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            data = json.load(f)

        wh_data = data.get("warehouse", {})
        dim = wh_data.get("dimensiones", {"ancho_x": 18, "largo_y": 16})

        # Inicializar el Warehouse con el tamaño exacto definido en el JSON
        wh = Warehouse(ancho_x=dim["ancho_x"], largo_y=dim["largo_y"])

        # 1. Cargar Puertas (decorativas/referenciales en los bordes)
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

        # 4. Cargar Pasillos con su sentido de circulación (N, S, E, O, AMBOS)
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

        # 5. Cargar Pickers con su posición inicial y capacidad de carga en kg
        for pk in data.get("pickers", []):
            pos = pk["posicion_inicial"]
            wh.pickers.append(Picker(
                id_picker=pk["id"],
                x_inicial=pos["x"],
                y_inicial=pos["y"],
                capacidad_carga_kg=pk.get("capacidad_carga_kg", 150.0)
            ))

        # 6. Cargar Productos con su ubicación (x, y, z), stock y peso unitario
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
            wh.registrar_pedido(nuevo_ped)

        # 8. Cargar parámetros de configuración general
        conf = data.get("configuracion", {})
        wh.wave_max_pedidos = conf.get("wave_max_pedidos", 3)
        wh.wave_max_productos = conf.get("wave_max_productos", 15)

        # Construir la grilla celular y el grafo dirigido del almacén
        wh.construir_estructura()
        return wh

    @staticmethod
    def guardar_escenario(warehouse, ruta_archivo):
        """
        Exporta el estado actual del Warehouse a un archivo JSON manteniendo
        exactamente la estructura oficial de los escenarios de la cátedra.
        """
        data = {
            "warehouse": {
                "dimensiones": {
                    "ancho_x": warehouse.ancho_x,
                    "largo_y": warehouse.largo_y
                },
                "puertas": [
                    {
                        "id": p.id_puerta,
                        "tipo": p.tipo,
                        "ubicacion": {"x": p.x, "y": p.y}
                    }
                    for p in warehouse.puertas
                ],
                "zonas_despacho": [
                    {
                        "id": z.id_zona,
                        "puerta_id": z.puerta_id,
                        "ubicacion": {"x": z.x, "y": z.y},
                        "ancho": z.ancho,
                        "alto": z.alto,
                        "peso_max_kg": z.peso_max_kg
                    }
                    for z in warehouse.zonas_despacho
                ],
                "racks": [
                    {
                        "id": r.id_rack,
                        "ubicacion": {"x": r.x, "y": r.y},
                        "ancho": r.ancho,
                        "alto": r.alto
                    }
                    for r in warehouse.racks
                ],
                "pasillos": [
                    {
                        "id": pas.id_pasillo,
                        "ubicacion": {"x": pas.x, "y": pas.y},
                        "ancho": pas.ancho,
                        "alto": pas.alto,
                        "sentido": pas.sentido
                    }
                    for pas in warehouse.pasillos
                ]
            },
            "pickers": [
                {
                    "id": pk.id_picker,
                    "posicion_inicial": {"x": pk.x_inicial, "y": pk.y_inicial},
                    "capacidad_carga_kg": pk.capacidad_carga_kg
                }
                for pk in warehouse.pickers
            ],
            "productos": [
                {
                    "id": pr.id_prod,
                    "nombre": pr.nombre,
                    "rack_id": pr.rack_id,
                    "ubicacion": {"x": pr.x, "y": pr.y, "z": pr.z},
                    "cantidad_disponible": pr.stock,
                    "peso_kg": pr.peso
                }
                for pr in warehouse.productos.valores()
            ],
            "pedidos": [
                {
                    "id": ped.id_pedido,
                    "prioridad": ped.prioridad,
                    "estado": ped.estado,
                    "items": [
                        {"producto_id": it["id"], "cantidad": it["cantidad"]}
                        for it in ped.productos
                    ]
                }
                for ped in warehouse.pedidos.valores()
            ],
            "configuracion": {
                "wave_max_pedidos": warehouse.wave_max_pedidos,
                "wave_max_productos": warehouse.wave_max_productos
            }
        }

        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)