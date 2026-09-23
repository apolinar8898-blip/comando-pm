# Ideas para prospección (no pedidas; anotadas para decidir después)

- **¿Fijo o celular?** Desde 2019 los números son de 10 dígitos para todo.
  El plan de numeración del IFT (que desde 2025 administra la CRT) sí dice si
  cada rango es móvil o fijo. Su servidor de descarga
  (sns.ift.org.mx:8081) no respondió el 22/09/2026. Si vuelve a publicarse,
  basta con un CSV de rangos para llenar `parece_celular`.
- **Penalizar cadenas en el score (Fase 3):** Walmart, Starbucks, bancos,
  Farmacias Guadalajara, etc. entran por tamaño de sucursal, pero no son PyMEs
  ni deciden en Querétaro. Propuesta: restar puntos si `num_establecimientos`
  es mayor de ~5 o si el dominio es de un corporativo nacional.
- **Otros parques industriales:** además del PIQ, revisar si Bernardo
  Quintana, El Marqués, Aeropuerto, Querétaro Park o Finsa publican
  directorios. Se cargarían con el mismo `directorios.importar`.
- **Cola de revisión manual en el dashboard:** mostrar los `pq_directorio`
  pendientes con botones de "Es esta" y "No es" (Fase 6).
