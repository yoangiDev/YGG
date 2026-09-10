# 0006 · Access token en memoria y refresh token en cookie httpOnly

**Estado:** aceptada · **Fases:** 3 y 5 · **Resuelve:** P5

## Contexto

La API emitía un único JWT de 30 minutos con `python-jose` (sin mantenimiento), sin refresh ni
revocación. En Flutter Web el token vivía en `shared_preferences`, que en el navegador es
`localStorage`: cualquier XSS podía leerlo y usarlo desde otra máquina. Tampoco había límite de intentos
en el login.

## Decisión

- **Access token** JWT de 15 minutos (PyJWT) que el cliente guarda **solo en memoria** y envía en
  `Authorization: Bearer`.
- **Refresh token opaco** en una cookie `httpOnly; Secure; SameSite=Lax; Path=/auth`. En la base de datos
  se guarda su hash SHA-256, se **rota en cada uso** y, si se presenta uno ya usado, se **revoca la familia
  entera** (señal de robo).
- Contraseñas con bcrypt, política de 10 caracteres a 72 bytes y comparación contra un hash de relleno
  cuando el email no existe, para no revelar qué cuentas existen por tiempo de respuesta.
- Rate limiting en Redis para login (por IP y por email), registro y refresh.
- En la web, el cliente generado intercepta los 401, pide un refresh y repite la petición. Los refresh
  concurrentes **comparten una única petición**: dos rotaciones en paralelo parecerían reutilización y
  cerrarían la sesión.

## Alternativas

- **JWT en `localStorage`.** Lo más sencillo y lo que había: expuesto a cualquier XSS.
- **Sesión solo por cookie**, sin cabecera `Authorization`. Todas las peticiones con cookie necesitarían
  protección CSRF. Con la cookie limitada a `/auth`, el resto de la API no se autentica por cookie y la
  superficie CSRF se reduce a refresh y logout, cuya respuesta no puede leer otro origen por CORS.
- **BFF** (servidor intermedio que guarda los tokens). Más seguro todavía, pero añade un servicio.

## Consecuencias

- Un XSS puede usar la sesión mientras la pestaña está abierta, pero no llevarse un token de larga duración.
- Recargar la página cuesta una petición de refresh; la sesión sobrevive (probado en
  `e2e/real-api.spec.ts` contra la API real).
- **La web y la API deben compartir *site*** (mismo dominio registrable) para que viaje la cookie
  `SameSite=Lax`: en producción, `ygg.tudominio.dev` y `api.ygg.tudominio.dev` (ver
  [`deploy.md`](../deploy.md)).
- CORS con credenciales exige orígenes explícitos; nunca `*`.
