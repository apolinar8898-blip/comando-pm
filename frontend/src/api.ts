// Cliente de la API. El token es opcional (solo si el backend define APP_PASSWORD).

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("comando_pm_token");
  const respuesta = await fetch(ruta, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Token": token } : {}),
      ...opciones.headers,
    },
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail ?? `Error ${respuesta.status}`);
  }
  return respuesta.json();
}

export const api = {
  get: <T>(ruta: string) => pedir<T>(ruta),
  post: <T>(ruta: string, datos?: unknown) =>
    pedir<T>(ruta, { method: "POST", body: JSON.stringify(datos ?? {}) }),
  put: <T>(ruta: string, datos: unknown) =>
    pedir<T>(ruta, { method: "PUT", body: JSON.stringify(datos) }),
  patch: <T>(ruta: string, datos: unknown) =>
    pedir<T>(ruta, { method: "PATCH", body: JSON.stringify(datos) }),
  del: <T>(ruta: string) => pedir<T>(ruta, { method: "DELETE" }),
};
