"""Directorios externos (PIQ, CANACINTRA…): guardarlos en pq_directorio y empatarlos con la base.

El empate (teléfono exacto o nombre con rapidfuzz) es regla pura en
app/dominio/prospeccion.py; aquí solo se leen candidatos y se escribe el resultado.
"""
from __future__ import annotations

import json
from collections import Counter

from ..dominio.prospeccion import empatar, nombres_candidato


def candidatos(con) -> list[dict]:
    """Empresas vigentes con todos sus teléfonos y nombres (de cada sucursal)."""
    filas = con.execute("""
        select e.empresa_id, e.cve_mun, e.telefono_principal, s.nom_estab, s.raz_social, s.telefono_e164
        from pq_empresas e join pq_establecimientos s using (empresa_id)
        where e.vigente and s.vigente
    """).fetchall()
    por_empresa: dict[str, dict] = {}
    sucursales: dict[str, list[dict]] = {}
    for empresa_id, cve_mun, tel_principal, nom, razon, tel in filas:
        c = por_empresa.setdefault(empresa_id, {"empresa_id": empresa_id, "cve_mun": cve_mun, "telefonos": set()})
        c["telefonos"].update(t for t in (tel_principal, tel) if t)
        sucursales.setdefault(empresa_id, []).append({"nom_estab": nom, "raz_social": razon})
    for empresa_id, c in por_empresa.items():
        c["nombres"] = nombres_candidato(sucursales[empresa_id])
    return list(por_empresa.values())


def importar(con, fuente: str, registros: list[dict], cve_mun: str | None = None) -> Counter:
    """Guarda los registros de un directorio y los empata con la base.

    registros: [{'nombre', 'giro', 'telefono' (E.164), 'direccion', 'datos': {...}}].
    Re-correrlo es seguro: lo 'empatado' y 'descartado' se conserva; lo
    'pendiente' y 'sin_match' se vuelve a intentar (la base pudo crecer).
    Devuelve el conteo por estado.
    """
    lista = candidatos(con)
    conteo: Counter = Counter()
    with con.transaction():
        previos = dict(con.execute("select nombre, estado from pq_directorio where fuente = %s", (fuente,)).fetchall())
        for r in registros:
            if previos.get(r["nombre"]) in ("empatado", "descartado"):
                conteo[previos[r["nombre"]]] += 1
                continue
            m = empatar(r, lista, cve_mun)
            conteo[m["estado"]] += 1
            con.execute("""
                insert into pq_directorio (fuente, nombre, giro, telefono, direccion, datos, empresa_id, confianza, metodo, estado)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (fuente, nombre) do update set
                    giro = excluded.giro, telefono = excluded.telefono, direccion = excluded.direccion,
                    datos = excluded.datos, empresa_id = excluded.empresa_id, confianza = excluded.confianza,
                    metodo = excluded.metodo, estado = excluded.estado
            """, (fuente, r["nombre"], r.get("giro", ""), r.get("telefono", ""), r.get("direccion", ""),
                  json.dumps(r.get("datos", {}), ensure_ascii=False), m["empresa_id"], m["confianza"], m["metodo"], m["estado"]))
        # La marca vive en la empresa: directorios = {piq_2024, …}. Solo con empate seguro.
        con.execute("""
            update pq_empresas e set directorios = array_append(e.directorios, %(f)s), actualizado = now()
            from pq_directorio d
            where d.fuente = %(f)s and d.estado = 'empatado' and d.empresa_id = e.empresa_id
              and not (%(f)s = any(e.directorios))
        """, {"f": fuente})
        if fuente == "canacintra":
            con.execute("""update pq_empresas e set afiliado_canacintra = true, actualizado = now()
                           from pq_directorio d
                           where d.fuente = 'canacintra' and d.estado = 'empatado'
                             and d.empresa_id = e.empresa_id and not e.afiliado_canacintra""")
    return conteo
