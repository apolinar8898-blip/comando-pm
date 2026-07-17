"""Ruta crítica del Gantt (CPM simplificado por duraciones y dependencias)."""
from __future__ import annotations

from ..modelos import Tarea


def _duracion(tarea: Tarea) -> int:
    if tarea.es_hito:
        return 0
    return (tarea.fecha_fin - tarea.fecha_inicio).days + 1


def ruta_critica(tareas: list[Tarea]) -> set[str]:
    """Ids de las tareas en el camino más largo del grafo de dependencias.

    Camino más largo por duración acumulada (CPM sin holguras: suficiente
    para resaltar visualmente qué cadena manda en la fecha de fin).
    Dependencias hacia tareas inexistentes o ciclos se ignoran con gracia.
    """
    por_id = {t.id: t for t in tareas}

    # Orden topológico (Kahn); los nodos en ciclo quedan fuera.
    grado: dict[str, int] = {t.id: 0 for t in tareas}
    sucesores: dict[str, list[str]] = {t.id: [] for t in tareas}
    for t in tareas:
        for dep in t.dependencias:
            if dep in por_id:
                grado[t.id] += 1
                sucesores[dep].append(t.id)

    cola = [tid for tid, g in grado.items() if g == 0]
    orden: list[str] = []
    while cola:
        nodo = cola.pop()
        orden.append(nodo)
        for suc in sucesores[nodo]:
            grado[suc] -= 1
            if grado[suc] == 0:
                cola.append(suc)

    if not orden:
        return set()

    # Distancia más larga hasta cada nodo y predecesor que la logra.
    dist: dict[str, int] = {}
    previo: dict[str, str | None] = {}
    for tid in orden:
        tarea = por_id[tid]
        mejor_dist, mejor_prev = 0, None
        for dep in tarea.dependencias:
            if dep in dist and dist[dep] > mejor_dist:
                mejor_dist, mejor_prev = dist[dep], dep
        dist[tid] = mejor_dist + _duracion(tarea)
        previo[tid] = mejor_prev

    # Retroceder desde el nodo con mayor distancia acumulada.
    final = max(dist, key=lambda tid: dist[tid])
    criticas: set[str] = set()
    actual: str | None = final
    while actual is not None:
        criticas.add(actual)
        actual = previo[actual]
    return criticas
