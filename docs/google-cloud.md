# Conectar una copia de Google Docs

1. Crea o selecciona un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita **Google Docs API** en [la biblioteca de APIs](https://console.cloud.google.com/apis/library/docs.googleapis.com). No hace falta habilitar Drive API.
3. En **IAM y administración → Cuentas de servicio**, crea una cuenta dedicada. No necesita roles amplios en el proyecto ni delegación de todo el dominio. Consulta la [guía oficial de cuentas de servicio](https://cloud.google.com/iam/docs/service-accounts-create).
4. Si la política de la organización lo permite, crea una clave JSON para esa cuenta desde **Claves → Añadir clave → Crear clave nueva**. Consulta la [guía de claves](https://cloud.google.com/iam/docs/keys-create-delete).
5. Guarda el JSON fuera del repositorio, en una ruta local accesible solo para el usuario que ejecuta el backend. No lo pegues en la web ni lo compartas por chat.
6. En Google Docs, abre **la copia de pruebas**. Compártela como **Editor** con el correo `client_email` de la cuenta de servicio. No compartas el original con esa cuenta.
7. Copia el identificador entre `/document/d/` y `/edit` de la URL de la copia. Si hay varias pestañas, abre la del calendario y toma el valor de `tab` de su URL. El índice de tabla empieza en cero y cuenta las tablas de nivel superior del cuerpo de esa pestaña.
8. Configura `backend/.env` con los identificadores y la ruta a las credenciales.

   ```dotenv
   APP_ENV=development
   DATA_SOURCE=google
   CALENDAR_YEAR=2027
   GOOGLE_DOCUMENT_ID=ID_DE_LA_COPIA
   GOOGLE_TAB_ID=
   GOOGLE_TABLE_INDEX=0
   GOOGLE_CREDENTIALS_PATH=/ruta/privada/cuenta-de-servicio.json
   FRONTEND_ORIGIN=http://127.0.0.1:5173
   ```

   Cambia el año para que coincida con la copia. Una pestaña única se detecta automáticamente; si hay varias debes configurar su ID.

9. Arranca FastAPI. Abre [el estado](http://127.0.0.1:8000/api/document/status) y confirma que `source` es `google` y `connected` es `true`. Si falla, comprueba la API habilitada, la ruta, el ID, la pestaña y el permiso Editor.
10. Abre [la estructura](http://127.0.0.1:8000/api/document/structure). Compara encabezados, columnas adicionales, fechas y separadores con la copia. Si aparecen filas `unknown`, revisa su contenido, estilo o celdas combinadas antes de probar la escritura.
11. Arranca Vite y comprueba que la cabecera muestra **Google Docs konektatuta**. Añade desde **Ekitaldia gehitu** un evento identificable en un mes con bloque. Elige una fecha anterior a algún evento de ese mes. Espera la confirmación de la web.
12. Abre **Dokumentua → Ireki Google Docs-en** y comprueba en la copia real que solo se añadió una fila, que la fecha está en euskera, que se insertó en el lugar correcto y que los separadores, filas anteriores, encabezado, bordes y anchos mantienen su aspecto. Repite el mismo alta para comprobar que no se duplica. Si es necesario, elimina manualmente la fila de prueba desde la copia.

La integración usa [documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get) y [documents.batchUpdate con WriteControl](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate). La escritura inserta con [insertTableRow y rellena con insertText](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request); entre ambas operaciones se vuelve a leer el documento para comprobar la revisión y obtener los índices nuevos.

Si aparece `revision_conflict`, vuelve a cargar la agenda. Si aparece `manual_review`, inspecciona la copia antes de repetir: la fila podría estar vacía o el evento ya guardado. Corrige el documento si hace falta y reinicia FastAPI antes de volver a escribir.
