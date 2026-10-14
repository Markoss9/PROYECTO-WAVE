"""
Módulo Principal - Punto de entrada del Sistema de Wave Picking.
Genera datos de prueba pseudoaleatorios y lanza la simulación visual.
"""
from warehouse import Warehouse
from modelos import Producto, Pedido
from simulacion import AppVisual
import random

def cargar_datos_prueba(wh):
    """Genera productos y pedidos sintéticos para la simulación."""
    
    # 1. Generar Productos (Se ubican en los racks: x=1,2, 4,5, 7,8...)
    id_p = 1
    for i in range(30): # 30 productos de prueba
        # Elegir un pasillo al azar
        pasillo = random.randint(0, wh.num_pasillos - 1)
        # Offset 1 o 2 para caer justo en las columnas de racks
        x = (pasillo * 3) + random.choice([1, 2])
        # "y" no puede ser 0 ni largo-1 (porque son transversales de movimiento)
        y = random.randint(1, wh.largo - 2)
        
        p = Producto(f"P{id_p:03d}", f"Item {id_p}", x, y, z=random.randint(1, 4), stock=50, peso=round(random.uniform(1.0, 5.0), 2))
        wh.registrar_producto(p)
        id_p += 1

    productos_lista = wh.productos.valores()
    
    # 2. Generar Pedidos
    for i in range(1, 15):
        prioridad = random.randint(1, 5) # 1 a 5 (5 mayor prioridad)
        ped = Pedido(f"PED-{i:03d}", prioridad)
        
        # Asignar entre 1 y 4 productos aleatorios al pedido
        cant_prods = random.randint(1, 4)
        seleccionados = random.sample(productos_lista, cant_prods)
        
        for prod in seleccionados:
            ped.agregar_producto(prod.id_prod, random.randint(1, 5))
            
        wh.registrar_pedido(ped)

if __name__ == "__main__":
    # Inicializar Warehouse: 4 pasillos y racks. Largo de 15 posiciones.
    wh = Warehouse(num_pasillos=4, largo_pasillo=15)
    
    # Llenar con datos sintéticos para no tener que cargarlos a mano
    cargar_datos_prueba(wh)
    
    print("Warehouse modelado con éxito.")
    print("Ejecutando interfaz de simulación interactiva...")
    
    # Iniciar GUI (Tkinter)
    app = AppVisual(wh)
    app.mainloop()
