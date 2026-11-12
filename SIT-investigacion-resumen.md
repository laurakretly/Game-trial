# SIT (Sistema de Información Trust) — Investigación técnica y opciones de migración

Fecha: 12 de noviembre de 2026. Preparado a partir de: código abierto ActionApps (release 2.50 y repositorio GitHub actual), documentación pública del proyecto, y documentos/correos/chats internos de The Trust (SharePoint, Outlook, Teams).

Nota: desde esta sesión no fue posible abrir `registro.trustfortheamericas.org` ni `nuevo.sit.trustfortheamericas.org` (dominios fuera de la política de red del entorno), ni `aa.ecn.cz` ni el SVN de SourceForge. Todo lo que sigue se apoya en el código fuente público y en la documentación interna.

---

## 1. Qué es el SIT, técnicamente

- El SIT está construido sobre **APC ActionApps (apc-aa)**, un CMS/plataforma de publicación de código abierto (GPL v2) creado en 2000 por la Association for Progressive Communications (APC). La ruta `/apc-aa/admin/` es, literalmente, el panel de administración estándar de ActionApps.
- Stack: **PHP + MySQL/MariaDB** sobre Linux. Los archivos `.php3` que aparecen en los errores (`include/zids.php3`, `filler.php3`) son los nombres históricos de ActionApps. La ruta del servidor es `/data/registro.trustfortheamericas.org/apc-aa/`.
- Piezas visibles del SIT que corresponden a ActionApps:
  - `/apc-aa/admin/` → back-end ("Administrador de ítems", "Importar CSV", "Export to file", "añadir un ítem", "por aprobar / marcar visibles").
  - `/apc-aa/filler.php3` → receptor de los formularios públicos de registro (por ejemplo el formulario de nuevo participante BR, con `slice_id` oculto).
  - `/apc-aa-files/<hash>/...` → archivos subidos (PDF, imágenes de reportes, manuales).
  - `nuevo.sit.trustfortheamericas.org/es/...` → el "SIT 2.0", la capa de usuario para Socios Locales/Centros (Mis Participantes, Mi Centro, Mis Cursos, Monitoreo Mensual, Reportes PDS, Propuestas, Reporte Financiero, Estadísticas, Instrucciones, Mi Cuenta, Directorios, Empleadores). Las URLs llevan IDs hexadecimales de 32 caracteres (por ejemplo `/es/ee1739e0.../pt-consultar-monitoramento-mensal?idpds=...`), que es el formato interno de ID de ActionApps. Todo indica que es el módulo "site"/vistas de ActionApps leyendo la misma base de datos, no un sistema aparte.
- Concepto central de ActionApps: el **"slice"** (en la interfaz en español: **"canal"**). Cada canal es una colección de ítems con campos definidos por el administrador, sin cambiar el esquema de la base. En el SIT existen, entre otros: canal 4A "Cursos NEW", canal 5 "Participante: Perfil" (55 campos), canal 6 "Participante: Cursos", canal 22 (documentos para compartir), SIT7/SIT8/SIT10 (oportunidades económicas), más canales de Monitoreo Mensual, Reportes, Propuestas, Socios Locales, Centros, Directorio.
- Modelo de datos (clave para cualquier migración): ActionApps guarda los ítems en formato **EAV** (entidad-atributo-valor):
  - tabla `item`: id (16 caracteres), slice_id, headline, publish_date, expiry_date, status_code (activo / pendiente / papelera), etc.
  - tabla `content`: item_id, field_id, text/number/flag. El `field_id` es un código de 16 caracteres rellenado con puntos, que es exactamente lo que se ve en los exportes del SIT: `headline........`, `text...........2`, `category.......4`, `publish_date....`.
  - tablas `slice`, `field` (definición de campos por canal), `view` (plantillas HTML), `constant` / `constant_slice` (catálogos: países, géneros, vulnerabilidad, etc.), `auth_user`/`users`/`profile` (usuarios y permisos), `relation`, `feeds` (alimentación entre canales), `discussion`, `offline`, `log`, `pagecache`, `site`/`site_spot` (módulo de sitio), `module`, `toexecute`, `cron`, `change`.
  - Las fechas se almacenan como **Unix timestamp** (por eso el manual de importación obliga a convertir fechas y a sumar el desfase horario).
  - Los IDs de participante que ve el usuario (ej. `52881789846br`) son un campo propio del SIT, no el ID interno.
- Herramientas nativas útiles para migrar: "Export to file" (CSV/HTML/XLS por canal), importador CSV (límite 2 MB por archivo, mapeo manual campo a campo), feeds, y en la versión actual una **API JSON** (`/api/v1/...`) y una cola de tareas para importaciones largas. En la 2.50 hay además `misc/export_by_sql` (scripts que aplanan el EAV a tablas `export_*`).

## 2. Historia y actores

- 2011–2012: nace el SIT. En julio de 2012, en Bogotá, se presentó la "versión Beta del Sistema de Información TRUST (SIT), a cargo de **COLNODO** y Diana Andrade" (documento "Cómo se creó la FSP", junio 2016). La presentación de septiembre 2026 al Senior Staff dice "Desde 2011, el SIT permite centralizar y gestionar los datos de participantes".
- **Colnodo** (Bogotá, Colombia) es una ONG miembro de APC desde 1994. Eso explica la elección de ActionApps: es el CMS de la red APC. Colnodo aparece en finanzas ("2018-SEP: Contract between TFTA and COLNODO to support the Digital Transformation", "Bolsa horas CICTE COLNODO 2019") y en las notas de check-in de 2026 ("Diana y Colnodo trabajando", "con el apoyo de Colnodo esta semana"). El "Conoldo" del pedido es, con toda probabilidad, **Colnodo**; en Teams la propia Laura escribió "Conoldo (??)".
- **Core Group Solutions (CGS)**, México (Oscar Ortega, Laura Estela Martínez, Gabriela Mendoza, Kimberly González): soporte de TI y Microsoft 365/Azure de The Trust (Capacita-te en Azure, Power Automate, Monday.com, herramienta de time tracking). En Teams (junio 2026): "SIT es de Colnodo con CGS y Aula Virtual de Roberto". El cronograma SIT 2024 asigna a "Oscar / Laura" la documentación de manuales, base de datos y consultas SQL.
- **Diana Andrade** (Senior IT and Data Systems Coordinator, Washington) es la dueña funcional del SIT desde 2012: crea canales, vistas, roles, formularios; pide traducciones editando el HTML de las vistas "en el bloc de notas para no modificar el código" (correos de 2024 y 2025).
- Manual SIT 2.0 para Socios Locales: marzo 2022 (versión 2.1). Manual de Importación Masiva: mayo/junio 2026.

## 3. Señales de fragilidad observadas

- Mayo 2025: error fatal "Maximum execution time of 350 seconds exceeded in /data/registro.trustfortheamericas.org/apc-aa/include/zids.php3 on line 115" al añadir participantes (OSJC, Brasil). `zids` es la rutina que calcula conjuntos de IDs de ítems; el error indica consultas que ya no escalan con el volumen de datos.
- La importación masiva es manual y frágil: CSV ≤ 2 MB, fechas en Unix timestamp, 55 campos a mapear a mano, valores "en rojo" cuando una clave no coincide con los catálogos, control por etiquetas (`CONTROL DE IMPORTACIÓN`).
- Cada cambio de formulario o idioma implica duplicar vistas HTML por rol (Centro PDS ES/PT, Centro sin proyecto, Socio local ES/PT, Lab DIA EN/ES, Lector Trust), como muestra el cronograma 2024.
- Dependencia de proveedores: en Teams (junio 2026) el equipo describe que "todo está en manos de proveedores que dicen que es muy complejo, costoso".
- Volumen: solo DigiSpark FY26 discutió registrar 53.898 personas con atribución y 110.347 sin atribución. Hay datos desde 2011.
- Integraciones actuales que dependen del SIT: tableros Power BI (actualizados 3 veces al día; el mecanismo de extracción no está documentado en lo que revisé), KPIs de M&E en Excel ("SIT importar"), formularios públicos, enlaces de descarga de archivos en `apc-aa-files`.

## 4. El código base abierto: ActionApps

- Proyecto SourceForge `apc-aa` registrado el 31-05-2000. Releases: 1.8 (2001), 2.0 (2001), 2.2 (2002), 2.4 (2002), 2.6 (2003), 2.8.1 (2005), **2.50.0 (mayo 2009, último con PHP 4)**, **2.90.0 (agosto 2020, último con PHP 5)**. Entre releases el desarrollo fue continuo en SVN.
- Desde septiembre de 2026 el desarrollo está en **GitHub: github.com/apc-aa/ActionApps** (6.365 commits; último commit 11-11-2026; ramas `main` para fuente y `dist` para instalar/actualizar; el SVN quedó como espejo de `dist`).
- Requisitos actuales: **PHP ≥ 8.2** (extensiones ctype, curl, dom, gd, intl, mbstring, pdo_mysql, xsl…), **MariaDB ≥ 10.0.2 o MySQL ≥ 5.7.5**, base en `utf8mb4`, Apache 2.4 o nginx, git. Composer no es necesario (vendor incluido en `dist`).
- Mantenedor principal: Honza Malík (Econnect / ecnstudio, Praga). Equipo muy pequeño; el propio PRODUCT.md lo reconoce.
- Tamaño del código actual: ~1.700 archivos PHP y ~860.000 líneas (incluye copias legacy `.php3`, módulos alerts, polls, links, jump, site, API JSON, tests PHPUnit, PHPStan).
- Documentación: README/INSTALL.md/UPDATE.md/DESIGN.md/PRODUCT.md/FILEMAP.md en el repo; `doc/AAdb.html` y `doc/AAdb_ER.html` (descripción y diagrama de la base); referencia de expresiones en actionapps.org/expressions; manual antiguo en documentation.actionapps.org y aa.ecn.cz/aa/doc.
- Actualización: `git pull` de `dist` + `service/sql_update.php` (o AA → Optimize) + State Check. Respaldo recomendado: `mysqldump --single-transaction`.
- Licencia GPL-2.0: The Trust es dueña de sus datos y de cualquier personalización; no hay licencia que pagar.

Qué versión corre el SIT: no pude verificarlo. Las rutas `.php3`, `filler.php3` y `apc-aa-files` existen tanto en 2.50 (2009) como en el código actual, así que la versión instalada puede ser cualquiera entre ~2.50 y una revisión SVN. Es la primera pregunta a hacer a Colnodo (con `php -v` del servidor y el `CHANGES`/revisión instalada).

## 5. Posibilidades de migración (sin perder datos)

Lo que hay que obtener primero (inventario, 1–2 semanas, con Colnodo y CGS):
1. `mysqldump` completo de la base `aadb` (todas las tablas) y copia de `apc-aa-files/` y de `include/config.php` (sin contraseñas en el correo).
2. Lista de canales (slices) con sus definiciones de campos (`field`), catálogos (`constant`), vistas (`view`), roles/usuarios (`auth_user`, `perms`), feeds y crons.
3. Versión de ActionApps y PHP/MySQL del servidor, proveedor de hosting, política de respaldos, dominio y certificados.
4. Mapa de consumidores: Power BI, formularios públicos embebidos, enlaces a `apc-aa-files` en documentos, Excel de KPIs.

Opciones:

- **A. Modernizar en el mismo ActionApps.** Actualizar a la rama `dist` (PHP 8.2, utf8mb4, API JSON, cola de importación, State Check). Riesgo bajo para los datos (es el camino oficial de upgrade), resuelve parte del rendimiento, pero mantiene el modelo EAV, las vistas HTML artesanales y la dependencia de un proyecto de nicho.
- **B. Sistema nuevo con migración ETL.** Diseñar un modelo relacional propio (participantes, centros, socios locales, proyectos, cursos, inscripciones/certificaciones, monitoreos mensuales, reportes, propuestas, oportunidades económicas, usuarios/roles) y migrar con scripts que "pivoten" `item`+`content` por canal a tablas normalizadas, conservando los IDs antiguos como clave heredada (`legacy_id`, `id_sit`), los catálogos (`constant`) como tablas de referencia y los archivos con su URL original mapeada. Validación por conteos y muestreo por canal/centro/año; corrida en paralelo; congelar importaciones en el corte; dejar el ActionApps en solo lectura como archivo histórico. Plataformas candidatas: base PostgreSQL gestionada (Supabase o Azure Database) + aplicación web moderna; o, si se prefiere low-code, Dataverse/Power Apps o Monday.com (que CGS ya está implantando para reemplazar Dynamics), con Power BI leyendo directo de la base nueva.
- **C. Híbrido por etapas.** Mantener la base ActionApps como fuente de verdad unos meses, construir primero la capa nueva (API + front) leyendo de una réplica, y migrar canal por canal (primero Cursos/Academia y Participantes, luego Monitoreo y Reportes). Reduce el "big bang" pero exige mantener dos sistemas.

Recomendación de partida: hacer el inventario (sección arriba) antes de decidir; con el dump en mano se puede estimar con precisión el esfuerzo del ETL (cantidad de canales, campos, ítems por canal, calidad de catálogos). La estructura EAV de ActionApps es perfectamente exportable; el riesgo real está en la semántica de 14 años de campos y catálogos que solo Diana y Colnodo conocen, por lo que ambos deben estar en la mesa del diseño del modelo nuevo.

## 6. Qué no pude verificar

- Acceso a las URLs del SIT (bloqueadas en esta sesión), versión instalada, tamaño de la base, hosting y respaldos.
- Contrato/alcance vigente con Colnodo (solo vi referencias financieras de 2018–2019 y menciones de 2026).
- Cómo se alimentan hoy los tableros Power BI desde el SIT.

## 7. Fuentes principales

Internas: "Cómo se creó la FSP MCP Junio 2016.docx"; "Manual para uso del SIT_V2022.pdf"; "Manual_Importacion_SIT.pdf" (2026); "Manual Trust.docx"; "SIT-Cronograma2024.xlsx"; "Tratamiento_Datos_DSFY2026 Presentación SS.pptx"; "Dashboard manual.docx"; correos "Erro na página do SIT" (mayo 2025), "BR SIT novo participante" (2024), "Estructura Monitoreo Mensual Brasil" (2025), "Actualización Sistemas + M&E | 14 de octubre de 2026"; chats de Teams (junio 2025 y junio 2026).
Externas: sourceforge.net/projects/apc-aa (news, files); github.com/apc-aa/ActionApps (README, INSTALL.md, UPDATE.md, PRODUCT.md, composer.json, include/metabase.class.php, doc/AAdb.html); release aa-2.50.0.tgz; actionapps.org; documentation.actionapps.org.
