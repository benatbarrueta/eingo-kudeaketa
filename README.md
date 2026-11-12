# EINGO Kudeaketa

Aplicación web en euskera para la **gestión de EINGO**, tanto de sus **bolos y actuaciones** como de su **escuela**.

La versión actual permite gestionar la agenda de bolos, con altas, edición y eliminación de eventos, fechas en euskera y sincronización entre Google Sheets y Google Docs. La gestión de la escuela forma parte del alcance previsto del proyecto y está pendiente de desarrollo.

React y TypeScript ofrecen la interfaz y FastAPI gestiona las operaciones y la integración con Google Workspace. Sheets conserva los datos completos y Docs presenta las columnas compartidas. El modo demo funciona con datos de ejemplo en memoria.

## Arranque local

Requisitos: Python 3.12 o superior, Node.js 22 o superior y npm. Desde la raíz:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
npm --prefix frontend ci
```

En dos terminales, desde la raíz:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload
```

```bash
npm --prefix frontend run dev -- --host 127.0.0.1
```

Abre [la agenda](http://127.0.0.1:5173/) o [OpenAPI](http://127.0.0.1:8000/docs). Vite redirige las llamadas a `/api` hacia FastAPI. Si alojas la API en otro origen, copia `frontend/.env.example` a `frontend/.env`, configura `VITE_API_URL` y ajusta `FRONTEND_ORIGIN` en el backend.

## Demostración

El modo predeterminado es `DATA_SOURCE=mock`. En **Ekitaldia gehitu**, elige el 12 de febrero de 2027, escribe **Gernika** y guarda. En **Ekitaldiak** aparecerá al principio del bloque de febrero; en **Dokumentua** podrás ver la fila junto a los separadores. **Berrezarri demoa** repone los datos iniciales. Reiniciar el backend también elimina las altas de la demo.

## Conectar la copia real

Sigue [la guía de Google Cloud y prueba de escritura](docs/google-cloud.md). Configura la fuente de datos, el año, los identificadores de los archivos y la ruta al JSON de la cuenta de servicio. Las credenciales de Google se utilizan desde el backend.

Por decisión del proyecto, esta fase permite las operaciones sin token administrativo ni login. El inicio de sesión y los permisos por rol se implementarán cuando el usuario defina su funcionamiento. Se mantienen la validación de datos, los límites de frecuencia y las protecciones de sincronización.

## Organización

| Ruta | Responsabilidad |
| --- | --- |
| `backend/app/api`, `schemas`, `core` | API, validación, configuración y autorización |
| `backend/app/services`, `models`, `utils` | Calendario, fechas en euskera y reglas cronológicas |
| `backend/app/repositories`, `data` | Acceso a Google Docs o datos de ejemplo en memoria |
| `backend/app/integrations/google` | Autenticación, pestañas, lectura de tablas y escritura |
| `backend/tests` | Pruebas de reglas, API y fallos del conector |
| `frontend/src/pages`, `components`, `styles` | Pantallas, componentes compartidos y estilos por vista |
| `frontend/src/api`, `hooks`, `lib` | Cliente HTTP, estado de la agenda y utilidades |
| `docs` | Configuración de Google Cloud y verificación manual |

La navegación superior permite abrir el panel en `/`, los eventos en `/events`, el calendario mensual en `/calendar`, la hoja de cálculo con todas las columnas en `/spreadsheet` y el documento en `/document`. El calendario permite abrir la edición de un evento y crear uno con la fecha del día seleccionado. Si alojas la compilación fuera de Vite, configura el servidor para servir `index.html` en las rutas de la interfaz y dirigir `/api` a FastAPI.

## API

| Método y ruta | Resultado |
| --- | --- |
| GET `/api/health` | Estado del proceso |
| GET `/api/config` | Fuente, año y enlace a la copia si corresponde |
| GET `/api/events` | Eventos y columnas |
| POST `/api/events` | Inserta y devuelve el evento y la tabla; devuelve 200 si el evento ya existe |
| GET `/api/document/structure` | Tabla y tipos de fila |
| GET `/api/document/status` | Conexión y estado de escritura |
| POST `/api/demo/reset` | Restablece la demo; solo disponible en modo mock |

Ejemplo de alta: `{"date":"2027-02-12","town":"GERNIKA","fields":{"EKITALDIA":"Kalejira"}}`. Usa los nombres de columnas devueltos por la API para `fields`. Los errores tienen la forma `{"error":{"code":"month_without_block"}}`. Los códigos incluyen 409 (estructura o revisión), 422 (datos), 429 (límite) y 502 (Google no disponible o sin permisos).

## Pruebas

```bash
(cd backend && ../.venv/bin/python -m pytest -q)
npm --prefix frontend run build
```

Las pruebas no necesitan conexión a Google ni credenciales. Cubren lectura, separadores, combinaciones de celdas, múltiples tablas y pestañas, orden, empates, duplicados, errores del proveedor y conflictos entre escrituras. La guía de Google Cloud incluye la comprobación que debe hacerse sobre la copia real.

## Límites

- Un año por instancia. Las fechas de las filas deben usar el formato `OTSAILAK 12`. Un mes sin eventos no tiene un bloque comprobable y no se modifica.
- Se espera una primera fila con encabezados de texto únicos que incluyan `DATA` y `HERRIA`. Un separador se reconoce si está vacío y sus celdas tienen fondo gris; se admite la combinación horizontal. Filas de eventos combinadas, filas desconocidas y desorden bloquean la escritura.
- El contenido existente, los anchos y los separadores se mantienen sin reconstruir la tabla. La fila nueva toma el fondo, los márgenes internos y la alineación de una fila de evento, además de estilos compatibles de párrafo y texto y altura mínima cuando se especifica. Los bordes los determina la inserción de Docs: no se reescriben porque comparten aristas con celdas existentes. Los estilos mixtos o complejos no se reproducen exactamente. La vista web es una representación de lectura.
- El alta requiere dos operaciones. Si la primera crea una fila y la segunda no puede completarse con seguridad, puede quedar una fila vacía. No se borra ni se reintenta automáticamente. En caso de `manual_review`, inspecciona la copia, corrige la fila si hace falta y reinicia el backend para quitar el bloqueo. Una fila vacía que no sea un separador reconocido sigue bloqueando la escritura al reiniciar.
- Fecha, localidad y todas las celdas iguales identifican un evento ya existente. Si dos eventos coinciden en esos campos, usa una columna adicional para distinguirlos. Los identificadores de respuesta son posiciones de fila y pueden cambiar al insertar.

Evolución posible: varios años y documentos, acceso con cuentas individuales y reglas explícitas para crear nuevos bloques mensuales.

## Google Sheets como fuente de verdad

Configura estas variables en `backend/.env` y habilita Google Sheets API en el proyecto de la cuenta de servicio. Comparte también la hoja como Editor con esa cuenta.

```dotenv
DATA_SOURCE=sheets
GOOGLE_SPREADSHEET_ID=ID_DE_TU_HOJA
GOOGLE_SHEET_NAME=Hoja 1
GOOGLE_SHEET_ID=0
```

La fila 1 debe contener DATA, HERRIA, NOR, ORDUA, FAKTURAZIOA, KONFIRM, AZALPENA, WAWA y WEWE, en ese orden. La web y Sheets usan las nueve columnas. La vista del documento consulta la tabla real de Google Docs y muestra las siete primeras. WAWA y WEWE se conservan exclusivamente en Sheets y la web.

Con la hoja vacía, pulsa **Inportatu Docs-eko ekitaldiak** y confirma para copiar los eventos de Docs a Sheets. La importación rellena las dos columnas adicionales con valores vacíos. Se admite reanudar una importación parcial cuando los eventos de Sheets coinciden con el comienzo del documento. Hasta que ambas fuentes coincidan, las modificaciones se bloquean.

Las altas, ediciones y eliminaciones de la web escriben primero en Sheets y después actualizan la fila correspondiente de Docs. Si falla el segundo paso, el mensaje indica que Sheets ya está guardado y debes pulsar **Sinkronizatu dokumentua**. Ese botón permite recuperar una única modificación pendiente, también tras reiniciar. Diferencias mayores requieren revisión de los datos. Google Docs conserva sus separadores y su formato.

`GET /api/calendar` devuelve las nueve columnas de la fuente principal. `GET /api/document/structure` devuelve la tabla real de Docs. `POST /api/sheets/import-document` importa eventos y `POST /api/document/sync` intenta reanudar la proyección pendiente. Ambas rutas aplican las mismas validaciones y límites que las escrituras de eventos.

El lector admite fechas en euskera, ISO o día/mes/año, y hasta 9998 eventos en una hoja sin filas vacías entre eventos. Rechaza fórmulas dentro de los datos. Las fechas deben estar ordenadas.

## Sincronización automática en ambos sentidos

Con `DATA_SOURCE=sheets` y `AUTO_SYNC=true`, el backend comprueba ambos archivos cada 15 segundos. La web también refresca sus datos automáticamente. El servicio debe permanecer encendido para propagar los cambios. El intervalo se configura con `SYNC_INTERVAL_SECONDS` y tiene un mínimo de 10 segundos.

La primera ejecución exige que las siete columnas comunes coincidan. El servicio guarda el último estado común en `.local-sync/state.json`, con permisos privados y excluido de Git. El archivo se vincula a los IDs, pestaña, tabla y año configurados. Conserva ese archivo entre reinicios. Las operaciones parcialmente aplicadas guardan un plan recuperable.

Los cambios de Google Docs se llevan a Sheets conservando WAWA y WEWE. Los cambios de Sheets se llevan a las siete columnas de Docs. Los cambios simultáneos en campos diferentes se combinan. Si ambas partes modifican de forma distinta el mismo campo o si se borra un evento que fue modificado en la otra parte, se detiene la sincronización y la web muestra un aviso. Para resolverlo, deja las siete columnas comunes con el resultado deseado en ambos archivos. La siguiente comprobación reconocerá el acuerdo.

Se admiten cambios de contenido y altas o bajas identificables. Los eventos duplicados y los movimientos de filas que no se puedan identificar con seguridad detienen el proceso. No cambies los encabezados o separadores desde los archivos. Mantén las fechas ordenadas al editar directamente. Ejecuta un solo proceso del backend: un bloqueo de archivo evita dos sincronizadores sobre el mismo estado.

Google Docs usa `requiredRevisionId`. Sheets comprueba su contenido antes de escribir, pero su API no ofrece una precondición equivalente en estas operaciones. Sigue existiendo una ventana de carrera si alguien cambia Sheets exactamente mientras el servicio escribe. Por eso esta versión funciona mediante comprobaciones periódicas y detección conservadora de conflictos.

`GET /api/sync/status` devuelve si el servicio automático está habilitado, el último éxito y el código de la incidencia actual.

## Comprobaciones en GitHub

El workflow `.github/workflows/ci.yml` se ejecuta en cada push y pull request, y también puede lanzarse manualmente desde Actions.

- **Backend tests** instala las dependencias con Python 3.12, ejecuta Pytest en modo mock y comprueba la sintaxis de Python.
- **Frontend build** instala las dependencias con `npm ci`, comprueba TypeScript y compila la web con Node.js 22.

Las comprobaciones usan permisos de lectura del repositorio y datos de prueba locales. Después de la primera ejecución en GitHub, selecciona **Backend tests** y **Frontend build** en **Require status checks to pass** del ruleset de `master`.

### Títulos y etiquetas de pull requests

El check **PR title** valida el formato `tipo(ámbito opcional): descripción` y se vuelve a ejecutar al editar el título. Tipos permitidos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` y `revert`. El ámbito es opcional y `!` permite señalar cambios incompatibles. Ejemplos: `feat: añadir calendario`, `fix(sync): corregir conflictos` y `chore!: actualizar configuración`. El ruleset de `master` debe exigir también **PR title** para impedir merges con títulos inválidos.

El workflow **PR labels** usa [actions/labeler](https://github.com/actions/labeler) y las rutas de `.github/labeler.yml` para asignar `frontend`, `backend`, `google`, `i18n`, `tests`, `documentation`, `ci` y `dependencies`. Una PR puede recibir varias etiquetas. Al cambiar los archivos se retiran las etiquetas configuradas que ya no correspondan; las demás etiquetas se conservan. Puede crear las etiquetas que falten con permiso `issues: write`.

El etiquetado utiliza la configuración de la rama base sin descargar ni ejecutar código de la PR. Empezará a funcionar una vez incorporado este workflow a `master`; la PR que lo introduce no ejecuta todavía el etiquetado automático.

El workflow **PR assignment** asigna la PR a su autor al abrirla o reabrirla, conservando las demás personas asignadas. Omite las PR creadas por bots y no hace cambios si el autor ya está asignado. Utiliza únicamente metadatos de GitHub, sin descargar ni ejecutar código de la PR. Empezará a funcionar tras incorporar su workflow a `master`; no asigna retroactivamente las PR que ya estén abiertas.

### Cambios desde la última visita

Al abrir la web o volver a una pestaña que estaba oculta se solicita la sincronización de Sheets y Docs antes de cargar los datos. Si falla, se muestra el error y se puede reintentar. El backend debe estar encendido.

La web compara los eventos con la última copia vista en ese navegador y muestra altas, bajas y campos modificados. La primera visita establece la referencia; no depende de que el backend haya estado apagado. La copia se guarda en el almacenamiento local del navegador e incluye los datos de los eventos. Al borrar ese almacenamiento o cambiar de navegador se pierde la referencia. Se muestran diferencias finales, sin atribuir autores ni reconstruir ediciones intermedias. Un cambio de fecha o de localidad puede aparecer como baja y alta.
