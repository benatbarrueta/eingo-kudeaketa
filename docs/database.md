# Base de datos de la agenda

La agenda dispone de persistencia SQLite, mediante `sqlite3` de Python. No requiere
instalar un servidor ni nuevas dependencias. Esta fase contiene exclusivamente
bolos: no implementa la escuela, usuarios, sesiones, roles ni facturas.

En este proyecto la agenda debe mantenerse sincronizada con Google Sheets y
Google Docs. La configuración de uso es `DATA_SOURCE=database` con
`GOOGLE_SYNC=true`. SQLite conserva los eventos y el estado de sincronización;
Sheets mantiene las nueve columnas y Docs las siete comunes. La conexión con
Google es necesaria también después de la importación inicial.

## Modelos y esquema

Las entidades están en `backend/app/models/database.py`. El esquema versionado
está en `backend/app/migrations/001_initial.sql`.

| Modelo | Tabla | Responsabilidad |
| --- | --- | --- |
| Event | events | UUID estable, nueve columnas, posición, versión, fechas de creación/modificación y borrado lógico |
| SyncConfiguration | sync_configurations | Año y vinculación con los archivos, pestaña y tabla de Google; nunca credenciales |
| SyncState | sync_states | Valores comunes verificados por evento y última posición observada en ambos archivos |
| SyncOperation | sync_operations | Plan pendiente, siguiente escritura prevista, progreso y errores recuperables |
| SyncConflict | sync_conflicts | Instantáneas de las tres fuentes y código de la incidencia; evento opcional si el conflicto es global |
| EventChange | event_changes | Alta, cambio o baja con valores anteriores y nuevos y origen conocido |

Las nueve columnas son DATA, HERRIA, NOR, ORDUA, FAKTURAZIOA, KONFIRM, AZALPENA,
WAWA y WEWE. La fecha tiene representación ISO y conserva también el texto de la
celda. Hora, facturación y confirmación conservan su representación original para
no perder valores heredados de Google. FAKTURAZIOA no es un modelo de factura ni
se utiliza para hacer cálculos monetarios en esta fase. El formulario sigue
utilizando selector horario y entrada numérica.

El historial registra `web`, `import` o `reconciliation`. Este último indica una
reconciliación de fuentes: no identifica a una persona ni permite reconstruir
ediciones intermedias. Los borrados son lógicos para conservar el historial.
Los cambios y su historial se confirman en una misma transacción. Cada escritura
comprueba la revisión de la agenda; la API admite además `expectedVersion`.

## Crear y activar la agenda sincronizada

Para crear una base nueva, desde la raíz del repositorio:

```bash
PYTHONPATH=backend .venv/bin/python -m app.database_cli init --year 2027
```

Esto crea `backend/.local-data/eingo.sqlite3`, inicialmente vacío, con los seis modelos y
las migraciones aplicadas. No lee ni escribe Google. El archivo y sus posibles
archivos auxiliares están excluidos de Git. La base de datos se crea con permisos
600 y el directorio nuevo con 700. Estos permisos no equivalen a cifrado.
Crear el esquema no importa los eventos: la importación se realiza en el primer
ciclo de sincronización. Si la base ya contiene eventos, consérvala; las migraciones
se aplican automáticamente al arrancar el backend.

Para ejecutar la aplicación con esa base de datos, configura en `backend/.env`
(sin eliminar el resto de tu configuración):

```dotenv
DATA_SOURCE=database
CALENDAR_YEAR=2027
DATABASE_PATH=.local-data/eingo.sqlite3
GOOGLE_SYNC=true
AUTO_SYNC=true
SYNC_INTERVAL_SECONDS=15
SYNC_STATE_PATH=.local-sync/state.json
```

Completa también las variables de acceso y archivos de Google del
`backend/.env.example`: `GOOGLE_CREDENTIALS_PATH`, `GOOGLE_DOCUMENT_ID`,
`GOOGLE_TAB_ID` cuando sea necesario, `GOOGLE_TABLE_INDEX`,
`GOOGLE_SPREADSHEET_ID`, `GOOGLE_SHEET_NAME` y `GOOGLE_SHEET_ID`.
Conserva los valores de los archivos ya configurados y el JSON de credenciales
exclusivamente en el servidor. Reinicia el backend después de cambiar el `.env`.

Arranca el backend desde la raíz como indica el README. Las rutas relativas de
DATABASE_PATH se resuelven siempre desde `backend/`, tanto en el servidor como en
el comando de base de datos. Cambiar de directorio de arranque no cambia de agenda.
También se admiten rutas absolutas. La web y la vista Excel presentan las nueve
columnas de la agenda; Documento consulta la tabla real de Google Docs, con sus
siete columnas. Ambas vistas permiten abrir el archivo de Google correspondiente.
Al abrir la web se sincronizan las fuentes antes de mostrar los datos. Si falla
la sincronización, hay que resolver la incidencia antes de continuar.

Los modos `mock`, `google` y `sheets` siguen disponibles sin cambiar su almacenamiento.
Cambiar el código no activa la migración de una instancia existente: hay que
seleccionar explícitamente el modo `database`. La escuela y el acceso de usuarios
continúan pendientes según las decisiones del proyecto.

## Migración desde Sheets y Docs

Esta operación debe ejecutarse primero sobre copias autorizadas. La implementación
se prueba con conectores simulados; no sustituye una verificación real.

1. Detén la instancia anterior y conserva `.local-sync/state.json`. Si contiene
   un plan pendiente, complétalo con la versión anterior antes de migrar. El nuevo
   sincronizador lo detecta y bloquea la migración en vez de descartarlo.
2. Haz copia de los dos archivos de Google y de la base de datos si ya existe.
3. Configura `DATA_SOURCE=database`, `GOOGLE_SYNC=true` y los parámetros de Google
   que ya utiliza el proyecto. Conserva el mismo año y `SYNC_STATE_PATH`. Un único
   proceso debe tener acceso a los archivos y al estado de sincronización.
4. Si la base está vacía, el primer ciclo importa las nueve columnas después de
   comprobar que las siete comunes coinciden. Si existe una referencia antigua
   sin operaciones pendientes, comprueba su identidad y la utiliza para reconciliar
   las diferencias. No elimina ni modifica ese archivo de estado antiguo.
5. Una base local con eventos solo se vincula si sus nueve columnas coinciden con
   Sheets y las siete comunes con Docs. Una configuración ya vinculada no permite
   cambiar silenciosamente de archivos o desconectarlos en esa misma base.
6. Verifica recuentos, fechas, valores y WAWA/WEWE en la web y Sheets, y las siete
   columnas de Docs. Comprueba después un alta, edición y baja autorizados y un
   reinicio. No declares terminada la migración hasta verificar estas operaciones.

SQLite conserva los eventos de la agenda sincronizada. La web escribe
primero la transacción local y después intenta propagarla. Si falla la propagación,
la respuesta `database_sync_pending` informa de que el cambio ya está guardado;
no hay que repetirlo. El siguiente ciclo o el botón Sincronizar reanuda el plan.
Las escrituras web requieren sincronización previa: no hay edición offline de
Google en esta fase. Un mes de Docs sin bloque válido se rechaza antes de guardar
un alta web.

El motor compara el último estado común con SQLite, Sheets y Docs. Combina
modificaciones de campos distintos y detecta también conflictos de WAWA/WEWE
entre SQLite y Sheets. Antes de cada escritura remota guarda su intención; después
relee los archivos. Solo avanza la referencia común cuando ambos contienen el
resultado esperado. Una pérdida de confirmación se recupera únicamente cuando la
lectura coincide exactamente con el estado anterior o con la escritura prevista.
Una diferencia inesperada detiene el plan. Los separadores y estilos de Docs
siguen gestionados por su integración actual, sin reconstruir el documento.

Mantén `GOOGLE_SYNC=true` y `AUTO_SYNC=true` para el funcionamiento habitual:
las comprobaciones periódicas se ejecutan mientras el backend está encendido.
`AUTO_SYNC` controla el sondeo periódico; desactivarlo no equivale a desconectar
Google, ya que siguen funcionando la sincronización al abrir la web, el botón y
las comprobaciones de las escrituras. El bloqueo entre procesos se mantiene.

## Conflictos y límites

Una incidencia guarda sus instantáneas sin exponerlas en respuestas públicas.
La web muestra un panel para resolver conflictos de contenido, también cuando el
conflicto impide la carga inicial. Identifica el evento y el campo y presenta los
valores distintos de Sheets y Docs. Si la agenda contiene otro cambio distinto,
lo ofrece como una tercera opción. WAWA y WEWE solo pueden tener opciones de la
agenda y Sheets.

Selecciona explícitamente un valor para cada campo y pulsa **Guardar y
sincronizar**. La selección resuelve esos campos y conserva los demás cambios
compatibles. Ninguna opción se marca automáticamente. Antes de escribir, el
servidor relee las fuentes y comprueba la revisión de la agenda y las revisiones
de Google frente a la vista presentada. Si cambiaron, rechaza la elección y pide
actualizar las opciones. La resolución utiliza el mismo plan recuperable y las
mismas verificaciones de escritura que la sincronización habitual.

El panel se limita a cambios de contenido en eventos cuya fecha, localidad y orden
siguen siendo identificables. Altas, bajas, duplicados, cambios de identidad,
diferencias iniciales y planes pendientes requieren revisión o recuperación del
plan; no se ofrecen botones para sobrescribir fuentes completas. Un plan pendiente
continúa únicamente desde sus valores previstos; si alguien los ha cambiado,
requiere intervención técnica, sin forzar reintentos ni editar o borrar a ciegas
las tablas de estado. Para conflictos sin plan pendiente también se admite dejar
las fuentes con el resultado acordado y que la siguiente sincronización lo
reconozca.

`GET /api/sync/conflict` devuelve los campos y opciones de la revisión actual,
sin los identificadores de los archivos de Google ni las instantáneas internas.
`POST /api/sync/conflict/resolve` recibe su token de revisión y las selecciones por
campo. Ambas rutas utilizan el bloqueo del servicio; la escritura aplica además
el límite de frecuencia. Solo están disponibles en modo database con Google Sync.

Se conservan los límites del conector: Docs necesita un bloque mensual reconocido,
no se aceptan estructuras ambiguas y Sheets carece de una precondición de revisión
equivalente a Docs. Persiste su ventana de carrera entre comprobación y escritura.
SQLite utiliza un solo escritor por vez y esta implementación utiliza un solo
proceso de sincronización. Para varias instancias de backend será necesario
revisar el motor de base de datos y la coordinación de trabajos.

La API añade `eventId` (UUID) y `version`. Las rutas de edición y borrado aceptan
el UUID; la web lo utiliza cuando está disponible. El campo `id` numérico conserva
su significado de posición de fila por compatibilidad con los modos anteriores.
Los UUID se conservan cuando una correspondencia es identificable; movimientos,
duplicados y reemplazos ambiguos bloquean la sincronización.

## Copias de seguridad

En modo `database`, las copias automáticas están activadas por defecto. El backend
crea una al arrancar si no hay una copia válida de la última hora y comprueba cada
minuto si corresponde hacer otra. Funcionan mientras el backend está encendido;
si estaba apagado, recupera la tarea pendiente al siguiente arranque sin generar
copias ficticias de las horas intermedias. La tarea es independiente del estado de
Google y también funciona si la sincronización está bloqueada por un conflicto.

La configuración, incluida en `backend/.env.example`, es:

```dotenv
AUTO_BACKUP=true
BACKUP_DIRECTORY=.local-data/backups
BACKUP_INTERVAL_SECONDS=3600
BACKUP_KEEP=48
```

La ruta relativa se resuelve desde `backend/`. Se conservan las 48 copias automáticas
más recientes por base de datos, aproximadamente dos días si el servicio permanece
encendido. El nombre incluye una referencia de la base y fecha UTC. Cambiar la
ruta de la base crea otro grupo de copias; no se retiran las del grupo anterior.
Las copias manuales y los demás archivos del directorio no entran en la rotación.

El directorio nuevo tiene permisos 700 y cada copia 600. Si se configura un
directorio existente accesible por otros usuarios, la tarea informa de error sin
cambiar sus permisos. El directorio predeterminado y los archivos SQLite están
excluidos de Git. Estas copias están en el mismo equipo: no protegen de la pérdida
del disco ni sustituyen una copia externa protegida.

La copia utiliza la API de backup de SQLite, comprueba el esquema, la integridad
y las relaciones, y publica el archivo completo sin sobrescribir destinos
existentes. Solo después de comprobar la nueva copia retira las versiones antiguas
de su propio grupo. Un fallo mantiene las copias anteriores. Un bloqueo de archivo
evita que dos procesos hagan la misma tarea a la vez. Los errores se registran sin
datos, credenciales ni rutas privadas.

`GET /api/backup/status` devuelve si la tarea está habilitada, el último éxito,
el código de error si existe, el intervalo y el número de copias conservadas.
No devuelve rutas ni contenido de la base. El estado se consulta al backend
encendido; no hay una pantalla de gestión de copias en la web.

Para una copia manual adicional, desde la raíz elige una ruta nueva y privada:

```bash
PYTHONPATH=backend .venv/bin/python -m app.database_cli backup backend/.local-data/backup-2027.sqlite3
```

El comando permite obtener una copia consistente con el backend activo y tampoco
sobrescribe archivos existentes.

### Verificación y restauración

Elige el archivo concreto que quieras verificar o recuperar. Estas operaciones
son locales, no arrancan el backend y no se conectan a Google. Las rutas de los
argumentos `source` y `destination` de estos comandos se interpretan desde el
directorio actual; `--path`, que selecciona la base activa para una copia manual,
se resuelve desde `backend/`.

```bash
PYTHONPATH=backend .venv/bin/python -m app.database_cli verify backend/.local-data/backup-2027.sqlite3
PYTHONPATH=backend .venv/bin/python -m app.database_cli restore backend/.local-data/backup-2027.sqlite3 backend/.local-data/restored-2027.sqlite3
```

`verify` comprueba el esquema, la integridad y las relaciones en modo de solo
lectura. `restore` crea otro archivo privado y verificado; nunca sustituye la base
activa ni sobrescribe un destino existente. Una copia incluye eventos, UUID,
versiones, historial, referencias, conflictos y operaciones pendientes: contiene
datos privados y debe protegerse como el original.

Antes de adoptar una restauración, detén el backend, conserva la base actual y
revisa la antigüedad de la copia y las diferencias respecto a los archivos de
Google. Al volver a conectar, una referencia antigua puede detectar cambios
remotos o conflictos; una restauración de SQLite no restaura ni rebobina Google.
Configura DATABASE_PATH con el archivo restaurado solo después de esa revisión y
reinicia el backend. No uses las pruebas de restauración para conectar una segunda
instancia de sincronización a los mismos archivos.

Las migraciones se aplican en orden y dentro de una transacción al abrir la base.
Una versión de esquema más reciente que el código bloquea el arranque. No se
implementan migraciones destructivas ni descensos automáticos de versión.
