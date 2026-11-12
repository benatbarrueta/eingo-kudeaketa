# EINGO Kudeaketa

## Alcance y arquitectura

- La aplicación gestiona EINGO, sus bolos y, como funcionalidad pendiente, su escuela. Distinguir siempre lo implementado de lo planificado.
- Frontend con React, TypeScript, Vite, React Router, Lucide y CSS por pantalla o componente. Seguir las convenciones del repositorio.
- Backend con FastAPI. Separar reglas de negocio, repositorios e integraciones de Google.

## Autenticación y credenciales

- Por decisión explícita del usuario, esta fase no aplica comprobación de token administrativo ni autenticación de usuarios. No añadir prompts, campos de claves ni restricciones de acceso administrativas.
- El login, las sesiones y los distintos roles se implementarán más adelante exactamente según las indicaciones del usuario. No anticipar ese diseño ni reintroducir el control de ADMIN_TOKEN.
- Conservar las validaciones de datos, los límites de frecuencia y las protecciones contra conflictos de sincronización.
- El JSON de Google se mantiene del lado del servidor. Nunca exponerlo mediante variables VITE_, respuestas públicas, commits o mensajes.
- .env, credenciales y .local-sync deben quedar fuera de Git. No mostrar sus valores al inspeccionarlos.

## Datos y sincronización

- Sheets y la web muestran las nueve columnas. Docs muestra las siete comunes. WAWA y WEWE son exclusivas de Sheets y la web.
- Mantener sincronización bidireccional, detección de conflictos y recuperación segura. Ante ambigüedad, detener la escritura y comunicar la incidencia.
- Conservar formato, filas existentes y separadores mensuales de Docs. Un separador mensual identificado permite añadir el primer evento de ese mes.
- No declarar comprobada una escritura real sin verificarla. Para pruebas remotas, respetar los archivos y operaciones autorizados por el usuario.

## Interfaz acordada

- Idioma principal en euskera y traducciones centralizadas.
- Navegación en la cabecera superior. Vistas de inicio, eventos, calendario, Excel y documento.
- Excel y documento comparten diseño de cabecera, sincronización y acceso al archivo correspondiente.
- Editar mediante lápiz y eliminar mediante papelera roja, con etiquetas accesibles y confirmación de borrado.
- ORDUA usa selector de hora; FAKTURAZIOA usa números; AZALPENA permite Erromeria, Ibiltaria o Beste bat con texto obligatorio.
- Las altas proponen fecha y hora actuales dentro del año permitido. Las ediciones muestran los datos guardados.

- Al abrir la web, sincronizar Sheets y Docs antes de mostrar datos. Comparar con la última visita de ese navegador y mostrar diferencias; no avanzar el punto de referencia si falla la sincronización. La primera visita establece el punto de partida. No atribuir autor ni cambios intermedios que no se pueden conocer.

## Git y validación

- La rama principal es master. Trabajar en ramas de funcionalidad y usar PR para incorporarlas. No eludir el ruleset.
- No publicar credenciales, identificadores reales del cliente ni su estado de sincronización.
- Frontend: npm --prefix frontend run build.
- Backend, cuando corresponda: desde backend, ../.venv/bin/python -m pytest -q.
- Informar de lo validado y de las limitaciones pendientes, especialmente para despliegues públicos.
