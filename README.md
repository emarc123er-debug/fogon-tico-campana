# El Fogón de Doña Tere: Landing + MCP + Zernio

Entregable del taller **Marketing y Ventas con IA**. Es el mismo flujo de la clase, aplicado a un restaurante de comida típica costarricense.
*Negocio y cifras ficticios.*

```
Landing captura leads → MCP los expone → Claude analiza y escribe → Zernio publica → más tráfico a la landing
```

## 1 · Landing de temporada

**Cena Navideña Tica para 2**: 2 tamales de cerdo, gallos de chicharrón, ensalada rusa, queque navideño y 2 rompopes.

| | |
|---|---|
| Precio ancla | ~~₡28.000~~ |
| Precio oferta | **₡17.900 por pareja** (ahorro 36%) |
| Cupos reales | 8 mesas por día, viernes a domingo: 4‑6, 11‑13 y 18‑20 de diciembre (72 mesas) |
| Fecha límite | Reservas hasta el jueves 17 de diciembre |
| Formulario | Nombre, WhatsApp (celular de CR), personas (2‑6), día |

- Los cupos se calculan desde la base de datos. Si un día está lleno, el servidor rechaza la reserva aunque alguien manipule el formulario.
- Tiene validación del lado del servidor y un campo trampa (*honeypot*) contra bots.

## 2 · Servidor MCP (FastMCP)

Se sirve por Streamable HTTP en `https://<dominio>/<MCP_PATH>`. Todas las herramientas son de solo lectura.

| Herramienta | Para qué sirve |
|---|---|
| `estado_campana` | Oferta, mesas ocupadas y libres, % de ocupación, ingreso proyectado, días que faltan |
| `cupos_por_dia` | Disponibilidad por día (`agotado` / `últimas mesas` / `disponible`) |
| `dias_vacios` | Días con más mesas libres y una sugerencia de cuál promocionar |
| `listar_leads` | Reservas recientes con **WhatsApp enmascarado** (`+506 ****-1234`) y nombre abreviado |
| `resumen_campana` | Reporte completo: top días, días vacíos, reservas en 24 h y 7 días, `datos_para_post` |
| `datos_para_publicacion` | Datos reales para un post (día, mesas libres, precio, URL) y las reglas de aprobación |

**Ejemplo:** Doña Tere pregunta *"¿Qué días siguen vacíos?"*. Claude responde con `dias_vacios`, por ejemplo *"el domingo 13 tiene 7 de 8 mesas libres"*, y propone un post.

## 3 · Zernio

Zernio es el segundo conector de Claude. Claude usa `datos_para_publicacion` y propone el texto del post. **Nada se publica sin aprobación**, y solo en una cuenta de prueba.

## Seguridad

- **No hay claves en el código.** Todo va en variables de entorno (ver [`.env.example`](.env.example)).
- `.env` y las bases locales están en `.gitignore`.
- El MCP no expone datos personales completos: los teléfonos van enmascarados y los apellidos se reducen a la inicial.
- La ruta del MCP se puede cambiar con `MCP_PATH` para que no sea fácil de adivinar.

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Postgres de Railway (`${{Postgres.DATABASE_URL}}`). Si no existe, se usa SQLite local |
| `LANDING_URL` | URL pública de la landing, la usa el MCP en los posts |
| `MCP_PATH` | Ruta del servidor MCP (por defecto `mcp`) |

## Correr en local

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt pytest
python -m scripts.seed_demo      # reservas ficticias de demostración
uvicorn app.main:app --reload    # http://localhost:8000  ·  MCP en /mcp
pytest -q
```

## Desplegar en Railway

1. Crear un proyecto nuevo desde este repositorio y agregarle una base **Postgres**.
2. En el servicio, configurar las variables `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `LANDING_URL` y `MCP_PATH`.
3. Generar un dominio público. `railway.json` ya define el comando de inicio y el chequeo `/health`.
4. En Claude, ir a **Configuración → Conectores → Agregar conector personalizado** y pegar `https://<dominio>/<MCP_PATH>`.

## Estructura

```
app/
  config.py       datos de la campaña (sin secretos)
  db.py           base de datos y cupos
  landing.py      página y API del formulario
  mcp_server.py   herramientas MCP
  analytics.py    consultas de solo lectura
  main.py         une landing + MCP en una sola app
templates/ static/  diseño de la landing
scripts/seed_demo.py  datos ficticios
tests/            pruebas de las herramientas MCP
```
