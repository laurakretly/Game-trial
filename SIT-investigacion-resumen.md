# SIT (Sistema de Información Trust): qué es, sobre qué código abierto está construido y cómo modernizarlo

Fecha: 12 de noviembre de 2026.
Fuentes: código fuente público de ActionApps (release 2.50 de 2009 y repositorio GitHub actual), documentación pública del proyecto (SourceForge, actionapps.org) y documentos de trabajo de The Trust guardados en SharePoint/OneDrive (manuales del SIT, cronograma 2024, presentaciones de M&E, documento histórico de la FSP) y el correo de soporte de mayo 2025. No se usaron conversaciones de Teams.
Limitación: desde este entorno no se pudo abrir `registro.trustfortheamericas.org`, `nuevo.sit.trustfortheamericas.org` ni `aa.ecn.cz` (dominios fuera de la política de red de la sesión). Lo que sigue se apoya en el código y en los documentos.

## 1. Qué es el SIT técnicamente

El SIT es una instalación personalizada de **APC ActionApps (apc-aa)**, una plataforma de publicación y gestión de contenidos de código abierto (licencia GPL v2) creada por la **Association for Progressive Communications (APC)**, red internacional de ONG. La URL `registro.trustfortheamericas.org/apc-aa/admin/` es el panel de administración estándar de ActionApps, sin renombrar.

Tecnología: **PHP + MySQL/MariaDB** sobre Linux (el servidor guarda el sitio en `/data/registro.trustfortheamericas.org/apc-aa/`). Es una aplicación clásica de servidor, sin framework moderno ni API REST en las versiones antiguas.

Partes del SIT que son piezas estándar de ActionApps:
- `/apc-aa/admin/` → back-end ("Administrador de ítems", "Importar CSV", "Export to file", "añadir un ítem", "por aprobar / marcar visibles", "modificación masiva").
- `/apc-aa/filler.php3` → receptor de los "formularios anónimos" (los formularios públicos de registro de participantes envían un `slice_id` oculto a este script).
- `/apc-aa-files/<hash>/...` → carpeta de archivos subidos (PDF, imágenes, manuales).
- `nuevo.sit.trustfortheamericas.org/es/...` ("SIT 2.0", manual de marzo 2022) → la capa para Socios Locales y Centros (Mis Participantes, Mi Centro, Mis Cursos, Monitoreo Mensual, Reportes PDS, Propuestas, Reporte Financiero, Estadísticas, Instrucciones, Mi Cuenta, Directorios, Empleadores). Sus URLs contienen IDs hexadecimales de 32 caracteres (por ejemplo `/es/ee1739e05d8b.../pt-consultar-monitoramento-mensal`), que es el formato interno de identificador de ActionApps. Esto indica que el front es el módulo de sitio y las vistas de ActionApps leyendo la misma base de datos, no un sistema separado.

## 2. Cómo guarda los datos (lo que importa para migrar)

El concepto central de ActionApps es el **slice**, traducido en la interfaz como **canal**. Cada canal es una colección de ítems con campos que el administrador define en pantalla, sin tocar el esquema de la base. Canales del SIT identificados en los manuales: 4A "Cursos NEW", 5 "Participante: Perfil" (55 campos), 6 "Participante: Cursos", 22 (documentos para compartir), SIT7/SIT8/SIT10 (oportunidades económicas), más canales de Monitoreo Mensual, Reportes, Propuestas, Socios Locales, Centros y Directorio.

El almacenamiento es de tipo **EAV (entidad–atributo–valor)**:
- Tabla `item`: id (16 caracteres), `slice_id`, `headline`, `publish_date`, `expiry_date`, `status_code` (1 activo, 2 pendiente/por aprobar, 3 papelera), `created_by`, `last_edit`.
- Tabla `content`: `item_id`, `field_id`, valor (texto, número o bandera). El `field_id` es un código de 16 caracteres rellenado con puntos; es exactamente lo que aparece en la primera fila de los exportes del SIT: `headline........`, `text...........2`, `category.......4`, `publish_date....`, `abstract.......9`.
- Tablas de definición: `slice`, `field` (campos de cada canal, tipo, obligatorio, widget), `view` (plantillas HTML con el lenguaje de alias `{...}`), `constant` y `constant_slice` (catálogos: países, géneros, vulnerabilidad, tipos de documento, etc.).
- Usuarios y permisos: `auth_user`, `users`, `profile`, con roles autor, editor, administrador (de canal) y superadministrador (de la instalación).
- Otras: `relation` (ítems relacionados), `feeds` (alimentación entre canales), `discussion`, `offline`, `log`, `pagecache`, `site` y `site_spot` (módulo de sitio), `module`, `toexecute`/`cron` (tareas programadas), `change`.
- Las fechas se guardan como **Unix timestamp** (segundos desde 1970). Por eso el manual de importación obliga a convertir fechas y a sumar el desfase horario.
- El identificador de participante que ven los usuarios (ej. `52881789846br`) es un campo propio del SIT, distinto del id interno.
- Los archivos no están en la base: están en el disco, en `apc-aa-files/`, con su ruta guardada como texto en `content`.

Consecuencia práctica: todos los datos del SIT caben en un `mysqldump` de una sola base más una copia de la carpeta `apc-aa-files/`. Migrar significa "pivotar" la tabla `content` (una fila por campo) a tablas relacionales normales (una fila por participante, por curso, por inscripción), usando `field` para saber qué significa cada código y `constant` para traducir los catálogos.

## 3. Historia del SIT

- 2011–2012: nace el SIT. En julio de 2012, en Bogotá, se presentó la "versión Beta del Sistema de Información TRUST (SIT), a cargo de COLNODO y Diana Andrade" (documento interno "Cómo se creó la FSP", junio 2016). La presentación de M&E de septiembre 2026 dice "Desde 2011, el SIT permite centralizar y gestionar los datos de participantes".
- **Colnodo** es una ONG de Bogotá, Colombia, miembro de APC desde 1994. Eso explica la elección de ActionApps: es el CMS histórico de la red APC y Colnodo lo conoce. En los registros financieros de The Trust aparece un contrato con Colnodo en septiembre de 2018 ("Contract between TFTA and COLNODO to support the Digital Transformation") y una "bolsa de horas" en 2019.
- Marzo 2022: manual "SIT 2.0" para Socios Locales (versión 2.1), con el front `nuevo.sit`.
- 2024: cronograma SIT 2024 (sitio "Transformación Digital" en SharePoint): documentación de manuales, de la base de datos y consultas SQL, creación de vistas y roles por idioma (Centro PDS ES/PT, Centro sin proyecto, Socio local ES/PT, Lab DIA EN/ES, Lector Trust), sección "Mis Cursos", y análisis del registro masivo de capacitaciones.
- Mayo–junio 2026: "Manual de Importación Masiva SIT" (canales 5 y 6).

## 4. Señales de que el sistema ya pide modernización

- Mayo 2025: un centro de Brasil recibió al añadir participantes el error "Fatal error: Maximum execution time of 350 seconds exceeded in /data/registro.trustfortheamericas.org/apc-aa/include/zids.php3 on line 115". `zids` es la rutina que calcula los conjuntos de ítems de un canal; el error indica consultas que ya no escalan con el volumen acumulado.
- La importación masiva es manual y frágil: CSV de máximo 2 MB, fechas en Unix timestamp calculadas a mano, mapeo de 55 campos uno por uno, valores "en rojo" cuando no coinciden con los catálogos, control de lotes por etiquetas de texto, y la fecha de publicación se agrega después con una "modificación masiva".
- Cada idioma o rol exige duplicar vistas HTML a mano (el cronograma 2024 lista "4 vistas: nuevo, edición, lectura y descarga" por cada rol e idioma).
- Volumen: solo DigiSpark FY26 analizó registrar 53.898 personas con atribución y 110.347 sin atribución; hay datos desde 2011.
- Dependencias actuales del SIT: tableros Power BI (actualizados tres veces al día; el mecanismo de extracción no está documentado en lo revisado), Excel de KPIs de M&E, formularios públicos de registro y enlaces de descarga a `apc-aa-files` incluidos en documentos y reportes.

## 5. El código abierto: ActionApps, de qué año es y dónde está

- Origen: el archivo CHANGES de la versión 2.50 registra entradas desde **noviembre de 1999**; el proyecto `apc-aa` se registró en SourceForge el **31 de mayo de 2000**. Autores: desarrolladores de la red APC, principalmente de Econnect (Praga, República Checa). Mantenedor principal actual: Honza Malík (Econnect / ecnstudio). Equipo muy pequeño.
- Dónde ver el código:
  - **GitHub: https://github.com/apc-aa/ActionApps** — desde septiembre de 2026 es el repositorio oficial (6.365 commits, último commit el 11-11-2026; rama `main` con el fuente y rama `dist` con los archivos listos para instalar). Es público: cualquiera puede leerlo, clonarlo y auditarlo.
  - **SourceForge: https://sourceforge.net/projects/apc-aa/** — histórico (SVN, hoy espejo de `dist`, y descargas: `aa-2.50.0.tgz`, 4,6 MB).
  - Documentación: actionapps.org (referencia de expresiones), documentation.actionapps.org (manual), y dentro del repo `README`, `INSTALL.md`, `UPDATE.md`, `PRODUCT.md`, `DESIGN.md`, `FILEMAP.md`, `doc/AAdb.html` (descripción de la base) y `doc/AAdb_ER.html` (diagrama entidad-relación).
- Releases: 1.8 (2001), 2.0 (2001), 2.2 (2002), 2.4 (2002), 2.6 (2003), 2.8.1 (2005), **2.50.0 (mayo 2009, último con PHP 4)**, **2.90.0 (agosto 2020, último con PHP 5)**; después, desarrollo continuo en SVN y ahora en git.
- Requisitos de la versión actual: **PHP 8.2 o superior**, **MariaDB 10.0.2+ o MySQL 5.7.5+**, base en `utf8mb4`, Apache 2.4 o nginx. Actualización oficial: `git pull` de `dist` y luego `service/sql_update.php` (o "AA → Optimize"), con `mysqldump` previo.
- Tamaño: unos 1.700 archivos PHP y ~860.000 líneas (incluye las copias históricas `.php3`, los módulos alerts, polls, links, jump y site, pruebas PHPUnit y análisis PHPStan).
- Qué trae la versión actual que la antigua no tiene: API JSON (`/api/v1/ping`, `/v1/files`, `/v1/translate`, `/v1/speech/transcribe`, `/v1/expressions`), importadores ("grabbers") desde CSV, RSS, XML, JSON-LD, iCal, SOAP, FTP, otra base SQL y otro canal; cola de tareas para importaciones largas; "State Check"; transcripción de voz con OpenAI (modelo `gpt-4o-transcribe`, clave `AA_APIKEY_OPENAI` en `config.php`); salidas RSS y JSON por vista.
- Versión instalada en el SIT: no fue posible determinarla desde fuera. Las rutas `.php3`, `filler.php3` y `apc-aa-files` existen tanto en la 2.50 (2009) como en el código actual. El error de 2025 cita `include/zids.php3`; en el repositorio actual ese archivo ya se llama `include/zids.php`, lo que sugiere que el SIT corre una versión anterior a la migración a PHP 8.

## 6. Qué se puede extraer sin pedir nada a nadie

Con el código público:
- Reconstruir el esquema completo de la base (tablas, columnas, claves) a partir de `include/metabase.class.php`, `doc/AAdb.html` y `doc/AAdb_ER.html`. Ya está hecho en este análisis.
- Saber el formato exacto de los exportes e importaciones (clases `AA_Exporter_Csv`, `AA_Exporter_Excel`, `AA_Exporter_Html`; importador `IO/Grabber/CSV`).
- Saber cómo se calculan los IDs, cómo se guardan fechas y catálogos, y cómo funcionan los formularios anónimos (`filler`) y las vistas.

Con el acceso de administradora de canal que ya tienes (sin superadmin), desde `/apc-aa/admin/`:
- **Export to file** en el Administrador de ítems de cada canal visible: exporta todos los ítems a CSV, Excel o HTML con los códigos de campo en la cabecera. Es la vía más directa para obtener un volcado completo de participantes, cursos, inscripciones, centros y monitoreos, canal por canal.
- **Administración del canal → Campos**: lista de todos los campos del canal con su `field_id`, tipo, widget, obligatoriedad y catálogo asociado. Esto es el "diccionario de datos" que necesita cualquier migración.
- **Constantes / catálogos**: valores y códigos de cada lista (países, géneros, vulnerabilidad, tipos de discapacidad).
- **Vistas**: plantillas HTML de cada pantalla del front; muestran qué campos usa cada rol.
- **Importar CSV**: muestra en el paso 2 el mapeo completo de campos del canal (el manual de 2026 ya lo documenta para los canales 5 y 6).
- `view.php3` y `slice.php3` con una vista configurada pueden devolver listados en RSS o JSON para consumo automático.
Lo que sí requiere superadmin o acceso al servidor: la lista de todos los canales, los usuarios de toda la instalación, `config.php`, el `mysqldump` completo, los crons y feeds, y la versión instalada.

## 7. Caminos de modernización

Objetivo declarado: menos trabajo manual, integración con la base de datos institucional y uso de IA.

- **A. Modernizar dentro de ActionApps.** Actualizar a la rama `dist` (PHP 8.2, utf8mb4, API JSON, importador con cola, transcripción con IA). Es el camino oficial de upgrade y conserva todos los datos sin transformación. Mejora rendimiento y seguridad, pero mantiene el modelo EAV, las vistas HTML artesanales por rol e idioma, y la dependencia de un proyecto de nicho con un mantenedor principal.
- **B. Sistema nuevo con migración ETL (recomendado si el objetivo es IA e integraciones).** Diseñar un modelo relacional propio: personas/participantes, centros, socios locales, programas y proyectos, cursos, inscripciones y certificaciones, monitoreos mensuales, reportes, propuestas, oportunidades económicas, usuarios y roles. Migrar con scripts que pivoten `item`+`content` por canal, conservando los IDs antiguos como clave heredada, los catálogos como tablas de referencia y los archivos con un mapa de URLs antiguas a nuevas. Validar por conteos y muestras por canal, centro y año; corrida en paralelo; congelar importaciones en el corte; dejar el ActionApps en solo lectura como archivo histórico. Sobre una base PostgreSQL o SQL gestionada (por ejemplo Supabase, Azure Database) se pueden construir con poco esfuerzo: formularios web modernos con validación, importaciones con limpieza automática, API para Power BI y para la base institucional, y funciones de IA (deduplicación de personas, normalización de nombres y catálogos, asistente de carga desde Excel, resúmenes de monitoreos, chat sobre los datos).
- **C. Híbrido por etapas.** Mantener la base ActionApps como fuente de verdad unos meses, construir la capa nueva leyendo de una réplica, y migrar canal por canal (primero Cursos/Academia y Participantes, luego Monitoreo y Reportes). Evita el "big bang" a costa de mantener dos sistemas un tiempo.

Primer paso concreto, sin depender de terceros: exportar con "Export to file" cada canal visible con tu usuario y copiar la pantalla de "Campos" de cada uno. Con esos archivos se puede construir el diccionario de datos y un prototipo de ETL, y estimar con precisión el esfuerzo de la opción B.

## 8. Lo que no pude verificar

- Versión exacta de ActionApps instalada, versión de PHP/MySQL del servidor, proveedor de hosting y política de respaldos.
- Tamaño real de la base y número total de ítems por canal.
- Cómo se alimentan hoy los tableros Power BI desde el SIT.
- Alcance del contrato vigente con Colnodo.
